"""Owner-only pages. Every form posts with a CSRF token; the server validates again."""
import json
import os
import time

from .actions import COIN_RATES, describe, parse_ctl_status, run_ctl
from .fmt import (MAPKEY_RE, e, fmt_clock, fmt_date, fmt_duration, fmt_int, fmt_time, to_int, to_str, track_label,
                  valid_steamid)
from .store import tail_lines
from .views import (avatar, csrf_field, empty, icon, key_label, layout, map_url, player_link, player_url,
                    q, style_tag, tier_badge, title_chip, track_url, when)
from .pages import state_html

VIP_BADGE = ' <span class="badge badge-vip">VIP</span>'
NOW_BADGE = ' <span class="badge badge-live">Now</span>'
SUBNAV = [("/admin", "Dashboard", "bolt"), ("/admin/players", "Players", "users"), ("/admin/bans", "Bans", "shield"),
          ("/admin/vip", "VIP", "star"), ("/admin/shop", "Shop", "cart"), ("/admin/maps", "Maps", "map"),
          ("/admin/logs", "Logs", "refresh")]


def admin_layout(ctx, title, body, sub=""):
    links = "".join(
        f'<a href="{href}"{" class=on aria-current=page" if ctx.path == href else ""}>{icon(ic)}<span>{label}</span></a>'
        for href, label, ic in SUBNAV)
    s = f'<p class="lead">{sub}</p>' if sub else ""
    page = (f'<section class="page-head admin-head"><div class="wrap"><span class="eyebrow">{icon("shield")}Admin</span>'
            f'<h1>{e(title)}</h1>{s}</div></section>'
            f'<div class="wrap"><nav class="subnav" aria-label="Admin">{links}</nav>{body}</div>')
    return layout(ctx, "Admin · " + title, page, page="admin")


def form(ctx, action, inner, back, cls="", confirm=""):
    c = f' data-confirm="{e(confirm)}"' if confirm else ""
    return (f'<form method="post" action="/admin/cmd" class="{cls}"{c}>{csrf_field(ctx)}'
            f'<input type="hidden" name="action" value="{e(action)}"><input type="hidden" name="back" value="{e(back)}">'
            f'{inner}</form>')


def hidden(name, value):
    return f'<input type="hidden" name="{e(name)}" value="{e(value)}">'


def sid_field(sid):
    return hidden("steamid", sid)


def button(label, cls="btn-ghost"):
    return f'<button class="btn {cls} btn-sm" type="submit">{e(label)}</button>'


def player_action_forms(ctx, sid, name, back, online=True, vip=False, banned=False):
    out = []
    if online:
        out.append(form(ctx, "kick", sid_field(sid) +
                        '<label class="field grow"><span>Kick reason</span><input name="reason" maxlength="200" placeholder="Optional"></label>'
                        '<button class="btn btn-ghost btn-sm" type="submit">Kick</button>', back, "row-form",
                        f"Kick {name}?"))
    if banned:
        out.append(form(ctx, "unban", sid_field(sid) + '<button class="btn btn-ghost btn-sm" type="submit">Unban</button>',
                        back, "row-form", f"Unban {name}?"))
    else:
        out.append(form(ctx, "ban", sid_field(sid) +
                        '<label class="field w-sm"><span>Minutes</span><input name="minutes" type="number" min="0" max="5256000" value="1440" required></label>'
                        '<label class="field grow"><span>Ban reason</span><input name="reason" maxlength="200" placeholder="0 minutes = permanent"></label>'
                        '<button class="btn btn-danger btn-sm" type="submit">Ban</button>', back, "row-form",
                        f"Ban {name}?"))
    out.append(form(ctx, "givevip", sid_field(sid) +
                    '<label class="field w-sm"><span>VIP days</span><input name="days" type="number" min="0" max="3650" value="30" required></label>'
                    '<button class="btn btn-gold btn-sm" type="submit">Give VIP</button>', back, "row-form"))
    out.append(form(ctx, "givecoins", sid_field(sid) +
                    '<label class="field w-sm"><span>Coins</span><input name="amount" type="number" min="-1000000" max="1000000" value="500" required></label>'
                    '<button class="btn btn-ghost btn-sm" type="submit">Give coins</button>', back, "row-form"))
    out.append(form(ctx, "giveitem", sid_field(sid) +
                    '<label class="field grow"><span>Shop item</span><input name="item" maxlength="49" pattern="[a-z0-9_]+:[a-z0-9_]+" placeholder="trail:gold" required></label>'
                    '<button class="btn btn-ghost btn-sm" type="submit">Give item</button>', back, "row-form"))
    out.append(form(ctx, "adjustpoints", sid_field(sid) +
                    '<label class="field w-sm"><span>Points</span><input name="points" type="number" min="-1000000" max="1000000" value="100" required></label>'
                    '<label class="field grow"><span>Why</span><input name="reason" maxlength="200" placeholder="Optional, e.g. event prize"></label>'
                    '<button class="btn btn-ghost btn-sm" type="submit">Add points</button>', back, "row-form"))
    if vip:
        out.append(form(ctx, "removevip", sid_field(sid) + '<button class="btn btn-ghost btn-sm" type="submit">Remove VIP</button>',
                        back, "row-form", f"Remove VIP from {name}?"))
    return "".join(out)


def recent_commands(ctx, limit=15):
    store = ctx.app.store
    results = store.read_results()
    names = store.player_names()
    entries = [a for a in reversed(store.audit_entries(400)) if isinstance(a.get("id"), str) and a.get("kind") == "cmd"][:limit]
    if not entries:
        return empty("No commands sent yet.", "Commands you send from here show up with the server's answer.", "bolt")
    items = []
    for a in entries:
        cid = a["id"]
        cmd = a.get("cmd") if isinstance(a.get("cmd"), dict) else {}
        res = results.get(cid)
        if res:
            cls, label = ("ok", "Done") if res["ok"] else ("err", "Failed")
            msg = res["msg"]
        elif store.cmd_pending(cid):
            cls, label, msg = "wait", "Queued", "Waiting for the game server to pick it up."
        else:
            cls, label, msg = "sent", "Sent", ""
        by = to_str(a.get("by"), "", 24)
        who = names.get(by) or by
        items.append(f'<li><span class="res res-{cls}">{label}</span><div class="cmd-main"><p>{e(describe(cmd))}</p>'
                     f'<p class="muted small">{e(msg) + " · " if msg else ""}{when(to_int(a.get("time")))} by {e(who)}</p></div></li>')
    return f'<ul class="cmdlist">{"".join(items)}</ul>'


def ctl_card(ctx):
    ok, out = run_ctl(ctx.app.ctl, "status")
    if not ok:
        return (f'<section class="card"><header class="card-h"><h2>{icon("bolt")}Game server</h2></header>'
                f'<div class="alert alert-err">{icon("shield")}<div><b>Could not read the server state.</b><p class="small">{e(out)}</p></div></div></section>'), None
    s = parse_ctl_status(out)
    active = s.get("active", "unknown")
    cls = {"active": "ok", "inactive": "idle", "failed": "err"}.get(active, "idle")
    label = {"active": "Running", "inactive": "Stopped", "failed": "Failed"}.get(active, active.capitalize() or "Unknown")
    upd = s.get("update_running") == "yes"
    since = f'<p class="muted small">since {e(s.get("since"))}</p>' if s.get("since") else ""
    upd_html = ('<span class="pill pill-busy"><span class="spinner" aria-hidden="true"></span>Update running</span>' if upd else "")
    btns = (f'<form method="post" action="/admin/ctl" data-confirm="Restart the game server now? Everyone gets disconnected for about a minute.">'
            f'{csrf_field(ctx)}<input type="hidden" name="op" value="restart"><button class="btn btn-danger" type="submit">{icon("refresh")}<span>Restart</span></button></form>'
            f'<form method="post" action="/admin/ctl" data-confirm="Start an update now? It updates GMOD, maps and the gamemode, then restarts the server.">'
            f'{csrf_field(ctx)}<input type="hidden" name="op" value="update"><button class="btn btn-ghost" type="submit"{" disabled" if upd else ""}>{icon("download")}<span>Update</span></button></form>')
    html = (f'<section class="card server-card"><header class="card-h"><h2>{icon("bolt")}Game server</h2>{upd_html}</header>'
            f'<div class="server-state"><span class="state-dot sd-{cls}"></span><div><p class="big">{e(label)}</p>{since}</div></div>'
            f'<div class="btn-row">{btns}</div></section>')
    return html, s


def dashboard(ctx):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    vips = app.store.vip_map()
    back = "/admin"
    ctl_html, _ = ctl_card(ctx)
    # live game state
    if st["online"]:
        game = (f'<div class="kv"><span>Map</span><b><a href="{e(map_url(st["map"]))}">{e(st["map"])}</a> {tier_badge(st["tier"])}</b></div>'
                f'<div class="kv"><span>Players</span><b>{len(st["players"])}/{st["maxplayers"]}</b></div>'
                f'<div class="kv"><span>Time left</span><b class="mono">{e(fmt_clock(st["timeleft"] - st["age"]))}</b></div>'
                f'<div class="kv"><span>Status file</span><b>{int(st["age"])}s old</b></div>')
    else:
        game = ('<div class="alert alert-warn">' + icon("shield") + '<div><b>No live status from the game.</b>'
                '<p class="small">status.json is missing or older than 30 seconds, so the server is down, changing maps or still starting. '
                'Commands wait in the queue until it is back.</p></div></div>')
    game_card = f'<section class="card"><header class="card-h"><h2>{icon("map")}Live game</h2></header>{game}</section>'
    # players: expandable rows so the action forms get full width (no clipped dropdowns)
    prow = []
    for p in st["players"]:
        sid, name = p["steamid"], p["name"]
        vip_badge = VIP_BADGE if p["vip"] else ""
        head = (f'<div class="pcell">{avatar(ctx, sid, name, "sm")}<div class="pcell-txt"><span class="ap-name">{player_link(sid, name)}{vip_badge}</span>'
                f'<span class="muted small mono">{e(sid or "no SteamID")}</span></div></div>'
                f'<div class="ap-state">{state_html(p)}</div>'
                f'<div class="ap-meta muted small"><span class="mono">{p["ping"]}</span> ms · {e(fmt_duration(p["connected"]))}</div>')
        if sid:
            prow.append(f'<li><details class="aprow"><summary>{head}<span class="btn btn-ghost btn-sm ap-btn">Actions</span></summary>'
                        f'<div class="ap-body">{player_action_forms(ctx, sid, name, back, True, sid in vips)}</div></details></li>')
        else:
            prow.append(f'<li><div class="aprow"><div class="ap-sum">{head}</div></div></li>')
    players = f'<ul class="aplist">{"".join(prow)}</ul>' if prow else empty("No players online.", "", "users")
    # map controls
    choices = sorted((m for m in maps.values() if m["installed"]), key=lambda m: (not m["zoned"], m["name"]))
    zoned = "".join(f'<option value="{e(m["name"])}"{" selected" if m["current"] else ""}>{e(m["name"])}{" (T" + str(m["tier"]) + ")" if m["tier"] else ""}</option>'
                    for m in choices if m["zoned"])
    unz = "".join(f'<option value="{e(m["name"])}"{" selected" if m["current"] else ""}>{e(m["name"])}</option>' for m in choices if not m["zoned"])
    opts = (f'<optgroup label="Zoned">{zoned}</optgroup>' if zoned else "") + (f'<optgroup label="Needs zones">{unz}</optgroup>' if unz else "")
    map_ctrl = (form(ctx, "changelevel", f'<label class="field grow"><span>Change map</span><select name="map" required>{opts}</select></label>'
                     '<button class="btn btn-primary btn-sm" type="submit">Change</button>', back, "row-form",
                     "Change the map now? Runs in progress are lost.") if choices else
                '<p class="muted">No maps installed.</p>')
    map_ctrl += form(ctx, "extend", '<label class="field w-sm"><span>Extend (min)</span><input name="minutes" type="number" min="1" max="120" value="15" required></label>'
                     '<button class="btn btn-ghost btn-sm" type="submit">Extend</button>', back, "row-form")
    map_ctrl += form(ctx, "vote", '<div class="field grow"><span>Map vote</span><p class="muted small">Starts a vote for the next map right away.</p></div>'
                     '<button class="btn btn-ghost btn-sm" type="submit">Start vote</button>', back, "row-form", "Start a map vote now?")
    say = form(ctx, "say", '<label class="field grow"><span>Message to everyone</span><input name="text" maxlength="200" required placeholder="Shown in chat to all players"></label>'
               '<button class="btn btn-primary btn-sm" type="submit">Send</button>', back, "row-form")
    body = f'''<div class="admin-grid">
{ctl_html}
{game_card}
<section class="card span-2"><header class="card-h"><h2>{icon("users")}Players online</h2><span class="muted small">{len(st["players"])}</span></header>{players}</section>
<section class="card"><header class="card-h"><h2>{icon("bolt")}Broadcast</h2></header>{say}</section>
<section class="card"><header class="card-h"><h2>{icon("map")}Map</h2></header><div class="form-stack">{map_ctrl}</div></section>
<section class="card span-2"><header class="card-h"><h2>{icon("refresh")}Recent commands</h2><span class="muted small">The game runs them within 2 seconds</span></header>{recent_commands(ctx)}</section>
</div>'''
    return admin_layout(ctx, "Dashboard", body)


def players(ctx):
    app = ctx.app
    sid = ctx.query.get("sid", "")
    if sid:
        if not valid_steamid(sid):
            return admin_layout(ctx, "Players", f'<div class="card">{empty("Invalid SteamID64.", "", "users")}</div>')
        return player_detail(ctx, sid)
    qtxt = ctx.query.get("q", "")
    rows = app.store.search_players(qtxt)
    rank = app.store.ranking()
    vips = app.store.vip_map()
    trs = []
    for r in rows:
        psid = to_str(r.get("steamid"), "", 24)
        if not valid_steamid(psid):
            continue
        name = to_str(r.get("name"), psid, 128)
        ent = rank["by_sid"].get(psid)
        trs.append(f'<tr><td class="c-player"><div class="pcell">{avatar(ctx, psid, name, "sm")}<div><a class="pname" href="/admin/players?sid={e(q(psid))}">{e(name)}</a>'
                   f'{VIP_BADGE if psid in vips else ""}<div class="muted small mono">{e(psid)}</div></div></div></td>'
                   f'<td class="num hide-sm">{(title_chip(ent["title_idx"]) + " " + fmt_int(ent["points"])) if ent else "<span class=muted>-</span>"}</td>'
                   f'<td class="num hide-sm">{e(fmt_duration(r.get("playtime")))}</td><td class="num">{when(to_int(r.get("lastseen")))}</td>'
                   f'<td class="c-act"><a class="btn btn-ghost btn-sm" href="/admin/players?sid={e(q(psid))}">Manage</a></td></tr>')
    search = (f'<form class="searchbar" method="get" action="/admin/players"><label class="search">{icon("search")}<span class="sr">Search</span>'
              f'<input type="search" name="q" value="{e(qtxt)}" placeholder="Name or SteamID64" autocomplete="off"></label>'
              f'<button class="btn btn-primary" type="submit">Search</button></form>')
    title = f'Results for "{e(qtxt)}"' if qtxt else "Recently seen"
    table = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Player</th><th class="num hide-sm">Points</th><th class="num hide-sm">Playtime</th>'
             f'<th class="num">Last seen</th><th></th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>') if trs else \
        empty("No players found.", "Players appear once they have joined the server.", "users")
    body = f'{search}<section class="card flush"><header class="card-h pad"><h2>{title}</h2><span class="muted small">{len(trs)}</span></header>{table}</section>'
    return admin_layout(ctx, "Players", body)


def player_detail(ctx, sid):
    app = ctx.app
    p = app.store.player(sid)
    st = app.store.status()
    online = any(x["steamid"] == sid for x in st["players"])
    back = f"/admin/players?sid={sid}"
    name = p["name"] if p else sid
    if p:
        vip = p["vip"]
        ban = p["ban"]
    else:
        vip, ban = None, None
    vip_txt = ("Permanent VIP" if vip == 0 else f"VIP until {fmt_date(vip)}") if vip is not None else "No VIP"
    if ban:
        exp = to_int(ban.get("expires"))
        ban_txt = f'Banned {"permanently" if exp == 0 else "until " + fmt_date(exp)}: {to_str(ban.get("reason"), "no reason")}'
    else:
        ban_txt = "Not banned"
    info = (f'<div class="kv"><span>SteamID64</span><b class="mono">{e(sid)}</b></div>'
            f'<div class="kv"><span>VIP</span><b>{e(vip_txt)}</b></div>'
            f'<div class="kv"><span>Ban</span><b class="{"bad" if ban else ""}">{e(ban_txt)}</b></div>')
    if p:
        w = app.store.wallet(sid)
        info += (f'<div class="kv"><span>Coins</span><b class="gold">{fmt_int(w["coins"])}</b></div>'
                 f'<div class="kv"><span>Shop items</span><b>{e(", ".join(sorted(w["owned"])) or "None")}</b></div>')
        adj = app.store.point_adjustments().get(sid, 0)
        adj_txt = f' <span class="muted small">({adj:+,} from admins)</span>' if adj else ""
        info += (f'<div class="kv"><span>Points</span><b>{fmt_int(p["points"])}{adj_txt} {title_chip(p["title_idx"])}</b></div>'
                 f'<div class="kv"><span>Playtime</span><b>{e(fmt_duration(p["playtime"]))}</b></div>'
                 f'<div class="kv"><span>Last seen</span><b>{"Online now" if online else when(p["lastseen"])}</b></div>')
    head = (f'<section class="card admin-player"><div class="pcell big">{avatar(ctx, sid, name, "lg")}<div>'
            f'<h2>{e(name)}</h2><p><a href="{e(player_url(sid))}">Public profile</a> · '
            f'<a href="https://steamcommunity.com/profiles/{e(sid)}" rel="noopener noreferrer">Steam</a></p></div></div>{info}</section>')
    acts = (f'<section class="card"><header class="card-h"><h2>{icon("shield")}Actions</h2></header><div class="form-stack">'
            f'{player_action_forms(ctx, sid, name, back, online, vip is not None, bool(ban))}</div></section>')
    rows = []
    for t in (p["times"] if p else []):
        base, label = key_label(t["key"])
        if MAPKEY_RE.match(t["key"]):
            delete = form(ctx, "deltime", sid_field(sid) + hidden("key", t["key"]) + button("Delete", "btn-danger"), back, "inline",
                          f"Delete {name}'s time on {base} · {label}? This cannot be undone.")
        else:  # a key the game would not accept (e.g. a style this portal does not know)
            delete = f'<span class="muted small" title="{e(t["key"])}">Unknown key</span>'
        tr = track_label(t["track"])
        btag = f' <span class="show-sm tag tag-bonus">{e(tr)}</span>' if t["track"] else ""
        if t["style"] != "n":
            btag += " " + style_tag(t["style"])
        rows.append(f'<tr><td class="wrap-sm"><a href="{e(track_url(base, t["track"], t["style"]))}">{e(base)}</a>{btag}</td><td class="hide-sm">{e(tr)}</td>'
                    f'<td class="num mono strong">{e(fmt_time(t["time"]))}</td><td class="num mono">#{t["pos"]}<span class="muted">/{t["total"]}</span></td>'
                    f'<td class="num muted hide-sm">{when(t["date"], "date")}</td>'
                    f'<td class="c-act">{delete}</td></tr>')
    times = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Map</th><th class="hide-sm">Track</th><th class="num">Time</th>'
             f'<th class="num">Pos</th><th class="num hide-sm">Date</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>') if rows else \
        empty("No times.", "", "flag")
    body = (f'<p class="crumbs"><a href="/admin/players">{icon("back")}<span>All players</span></a></p>'
            f'<div class="admin-grid">{head}{acts}'
            f'<section class="card span-2 flush"><header class="card-h pad"><h2>{icon("flag")}Times</h2><span class="muted small">{len(rows)}</span></header>{times}</section></div>')
    return admin_layout(ctx, name, body)


def bans(ctx):
    app = ctx.app
    names = app.store.player_names()
    back = "/admin/bans"
    rows = []
    for b in app.store.bans():
        sid = to_str(b.get("steamid"), "", 24)
        if not valid_steamid(sid):
            continue
        name = to_str(b.get("name"), "") or names.get(sid) or sid
        exp = to_int(b.get("expires"))
        admin = to_str(b.get("admin"), "")
        exp_html = '<span class="badge badge-bad">Permanent</span>' if exp == 0 else f'{e(fmt_date(exp))}<div class="muted small">{e(fmt_duration(exp - time.time()))} left</div>'
        rows.append(f'<tr><td class="c-player"><div class="pcell">{avatar(ctx, sid, name, "sm")}<div><a class="pname" href="/admin/players?sid={e(q(sid))}">{e(name)}</a>'
                    f'<div class="muted small mono">{e(sid)}</div></div></div></td>'
                    f'<td class="wrap-text">{e(to_str(b.get("reason"), "") or "-")}</td><td class="hide-sm">{e(names.get(admin) or admin or "-")}</td>'
                    f'<td class="num hide-sm">{when(to_int(b.get("created")), "date")}</td><td class="num">{exp_html}</td>'
                    f'<td class="c-act">{form(ctx, "unban", sid_field(sid) + button("Unban"), back, "inline", f"Unban {name}?")}</td></tr>')
    table = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Player</th><th>Reason</th><th class="hide-sm">By</th><th class="num hide-sm">Banned</th>'
             f'<th class="num">Expires</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>') if rows else \
        empty("No active bans.", "", "shield")
    add = form(ctx, "ban", '<label class="field grow"><span>SteamID64</span><input name="steamid" pattern="7656[0-9]{13}" required placeholder="7656119..."></label>'
               '<label class="field w-sm"><span>Minutes</span><input name="minutes" type="number" min="0" max="5256000" value="0" required></label>'
               '<label class="field grow"><span>Reason</span><input name="reason" maxlength="200" placeholder="0 minutes = permanent"></label>'
               '<button class="btn btn-danger btn-sm" type="submit">Ban</button>', back, "row-form", "Ban this SteamID?")
    body = (f'<section class="card flush"><header class="card-h pad"><h2>{icon("shield")}Active bans</h2><span class="muted small">{len(rows)}</span></header>{table}</section>'
            f'<section class="card"><header class="card-h"><h2>Ban by SteamID64</h2></header>{add}</section>')
    return admin_layout(ctx, "Bans", f'<div class="stack">{body}</div>')


def vip(ctx):
    app = ctx.app
    back = "/admin/vip"
    rows = []
    for v in app.store.vips():
        sid = v["steamid"]
        if not valid_steamid(sid):
            continue
        name = v["name"] or sid
        exp = v["expires"]
        exp_html = '<span class="badge badge-vip">Permanent</span>' if exp == 0 else f'{e(fmt_date(exp))}<div class="muted small">{e(fmt_duration(exp - time.time()))} left</div>'
        rows.append(f'<tr><td class="c-player"><div class="pcell">{avatar(ctx, sid, name, "sm")}<div><a class="pname" href="/admin/players?sid={e(q(sid))}">{e(name)}</a>'
                    f'<div class="muted small mono">{e(sid)}</div></div></div></td><td class="num">{exp_html}</td>'
                    f'<td class="c-act">{form(ctx, "removevip", sid_field(sid) + button("Remove"), back, "inline", f"Remove VIP from {name}?")}</td></tr>')
    table = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Player</th><th class="num">Expires</th><th></th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>') if rows else empty("No VIPs yet.", "", "star")
    add = form(ctx, "givevip", '<label class="field grow"><span>SteamID64</span><input name="steamid" pattern="7656[0-9]{13}" required placeholder="7656119..."></label>'
               '<label class="field w-sm"><span>Days</span><input name="days" type="number" min="0" max="3650" value="30" required></label>'
               '<button class="btn btn-gold btn-sm" type="submit">Give VIP</button>', back, "row-form")
    body = (f'<section class="card flush"><header class="card-h pad"><h2>{icon("star")}VIP players</h2><span class="muted small">{len(rows)}</span></header>{table}</section>'
            f'<section class="card"><header class="card-h"><h2>Give VIP by SteamID64</h2><span class="muted small">0 days = permanent</span></header>{add}</section>')
    return admin_layout(ctx, "VIP", f'<div class="stack">{body}</div>')


def shop_item_form(ctx, it, owners, back):
    price = it["price"] or ""
    chk = lambda on: " checked" if on else ""  # noqa: E731
    flags = []
    if it["hidden"]:
        flags.append('<span class="badge">Hidden</span>')
    if it["changed"]:
        flags.append('<span class="badge badge-live">Changed</span>')
    label = f'[{e(it["name"])}]' if it["cat"] == "tag" else e(it["name"])
    inner = (hidden("item", it["key"]) +
             f'<div class="si-name"><b>{label} {"".join(flags)}</b><span class="muted small mono">{e(it["key"])} · {owners} owner{"s" if owners != 1 else ""}</span></div>'
             f'<label class="field w-sm"><span>Coins</span><input name="price" type="number" min="0" max="10000000" value="{e(price)}" placeholder="0"></label>'
             f'<label class="check"><input type="checkbox" name="vip" value="1"{chk(it["vip"])}><span>VIP</span></label>'
             f'<label class="check"><input type="checkbox" name="hidden" value="1"{chk(it["hidden"])}><span>Hidden</span></label>'
             + button("Save"))
    return form(ctx, "shopitem", inner, back, "row-form shop-item")


def tebex_status(app):
    try:
        with open(os.path.join(app.store.portal_dir, "tebex_status.json"), encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def store_card(ctx):
    """Selling VIP with Tebex: paste the secret key and see whether Tebex accepts it."""
    app = ctx.app
    conf = app.conf
    secret = conf.get("TEBEX_SECRET")
    st = tebex_status(app)
    if not secret:
        state = ('<div class="alert"><div><b>Not connected.</b><p class="small">Paste the secret key from Tebex below to start '
                 'handing out what people buy.</p></div></div>')
    elif st.get("key_end") != secret[-4:] or not st.get("checked"):
        state = ('<div class="alert"><div><b>Checking the key with Tebex...</b><p class="small">This takes up to a minute. '
                 'Reload the page to see the result.</p></div></div>')
    elif st.get("ok"):
        polled = f' Last checked for purchases {when(to_int(st.get("polled")))}.' if st.get("polled") else ""
        state = (f'<div class="alert alert-ok"><div><b>Connected to Tebex.</b><p class="small">Store '
                 f'<b>{e(to_str(st.get("account"), "?"))}</b>, game server <b>{e(to_str(st.get("server"), "?"))}</b>.{e(polled)}</p></div></div>')
    else:
        state = (f'<div class="alert alert-err"><div><b>Not working.</b><p class="small">{e(to_str(st.get("error"), "Tebex refused the key."))} '
                 f'Copy the key again from Tebex (Integrations &gt; Game servers).</p></div></div>')
    src = conf.source("TEBEX_SECRET")
    if secret:
        ph = f"Saved (ends in {secret[-4:]}). Paste a new one to replace it"
        if src == "config":
            ph += " (now set in config.env)"
    else:
        ph = "Paste the secret key from Tebex"
    url_src = conf.source("STORE_URL")
    url_val = conf.get("STORE_URL") if url_src == "website" else ""
    url_ph = conf.https_url("STORE_URL") or "https://yourstore.tebex.io"
    form_html = (f'<form method="post" action="/admin/store" class="form-stack store-form">{csrf_field(ctx)}'
                 f'<label class="field"><span>Tebex secret key</span><input name="tebex_secret" type="password" autocomplete="off" '
                 f'spellcheck="false" maxlength="128" placeholder="{e(ph)}"></label>'
                 f'<label class="field"><span>Store address</span><input name="store_url" maxlength="200" value="{e(url_val)}" '
                 f'placeholder="{e(url_ph)}"></label>'
                 f'<div class="btn-row">{button("Save", "btn-gold")}</div></form>')
    disc = ""
    if secret and src == "website":
        disc = (f'<form method="post" action="/admin/store" data-confirm="Disconnect Tebex? Purchases wait in Tebex until you connect again.">'
                f'{csrf_field(ctx)}<input type="hidden" name="disconnect" value="1">{button("Disconnect")}</form>')
    help_html = ('<p class="muted small">In Tebex: Integrations &gt; Game servers &gt; your server shows the secret key. '
                 'You don\'t need the Tebex addon on the game server; this website does that job. '
                 'Package command: <b class="mono">surf_givevip {id} 30</b> (0 days = lifetime), coins: '
                 '<b class="mono">surf_givecoins {id} 5000</b>, refund or chargeback: <b class="mono">surf_removevip {id}</b>. '
                 'Leave the store address empty to use the one Tebex reports.</p>')
    return (f'<section class="card"><header class="card-h"><h2>{icon("cart")}Selling VIP with Tebex</h2></header>'
            f'{state}{form_html}{disc}{help_html}</section>')


def shop_admin(ctx):
    app = ctx.app
    back = "/admin/shop"
    cat = app.store.shop_catalog()
    if cat is None:
        body = (f'<div class="stack">{store_card(ctx)}<section class="card">'
                f'{empty("The game server has not written the shop yet.", "It does once it runs this update.", "cart")}</section></div>')
        return admin_layout(ctx, "Shop", body)
    stats = app.store.shop_stats()
    names = app.store.player_names()
    item_names = {it["key"]: it["name"] for c in cat["categories"] for it in c["items"]}
    tiles = [("Coins held", fmt_int(stats["circulating"]), f'{fmt_int(stats["holders"])} players'),
             ("Coins earned", fmt_int(stats["earned"]), f'{fmt_int(stats["earned_week"])} this week'),
             ("Coins spent", fmt_int(stats["spent"]), f'{fmt_int(stats["spent_week"])} this week'),
             ("Items sold", fmt_int(sum(stats["popular"].values())), f'{len(stats["popular"])} different')]
    grid = "".join(f'<div><dt>{e(a)}</dt><dd>{b}</dd><dd class="sub">{e(c)}</dd></div>' for a, b, c in tiles)
    sections = []
    for c in cat["categories"]:
        rows = "".join(shop_item_form(ctx, it, stats["popular"].get(it["key"], 0), back) for it in c["items"])
        sections.append(f'<section class="card"><header class="card-h"><h2>{e(c["name"])}</h2><span class="muted small">{len(c["items"])} items</span></header>'
                        f'<div class="shop-items">{rows}</div></section>')
    rate_forms = "".join(form(ctx, "coinrate", hidden("name", k) +
                              f'<label class="field grow"><span>{e(label)}</span><input name="value" inputmode="decimal" pattern="[0-9]{{1,6}}([.][0-9]{{1,3}})?" '
                              f'value="{e(("%g" % cat["coins"][k]) if k in cat["coins"] else "")}" required></label>' + button("Save"), back, "row-form")
                         for k, label in COIN_RATES.items())
    vip_forms = "".join(form(ctx, "vipprice", hidden("days", p["days"]) +
                             f'<label class="field grow"><span>{p["days"]} days</span><input name="price" type="number" min="0" max="10000000" value="{p["price"]}" required></label>'
                             + button("Save"), back, "row-form") for p in cat["vip"])
    vip_forms += form(ctx, "vipprice", '<label class="field w-sm"><span>New: days</span><input name="days" type="number" min="1" max="3650" required></label>'
                      '<label class="field grow"><span>Coins</span><input name="price" type="number" min="1" max="10000000" required></label>'
                      + button("Add"), back, "row-form")
    top = "".join(f'<li><a href="/admin/players?sid={e(q(t["sid"]))}">{e(names.get(t["sid"]) or t["sid"])}</a>'
                  f'<b class="mono gold">{fmt_int(t["coins"])}</b></li>' for t in stats["top"] if valid_steamid(t["sid"]))
    recent = "".join(f'<li><a href="/admin/players?sid={e(q(r["sid"]))}">{e(names.get(r["sid"]) or r["sid"])}</a>'
                     f'<span>{e(item_names.get(r["reason"][7:], r["reason"][7:]))}</span>'
                     f'<span class="mono gold">{fmt_int(-r["amount"])}</span><span class="muted small">{when(r["date"])}</span></li>'
                     for r in stats["recent"] if valid_steamid(r["sid"]))
    body = (f'{store_card(ctx)}<dl class="stat-grid stat-4">{grid}</dl>'
            f'<p class="muted small">Changes reach the game within a few seconds and are saved on the server. Coins 0 means no coin price: '
            f'the item is then free, or VIP only when VIP is ticked. VIP ticked with a price means it is bought with coins and free for VIPs. '
            f'Hidden items leave the shop, but players who own them keep them.</p>'
            f'<div class="admin-grid">'
            f'<section class="card"><header class="card-h"><h2>{icon("trophy")}Coin rates</h2></header><div class="form-stack">{rate_forms}</div></section>'
            f'<section class="card"><header class="card-h"><h2>{icon("star")}VIP for coins</h2><span class="muted small">0 removes a package</span></header>'
            f'<div class="form-stack">{vip_forms}</div></section>'
            f'<section class="card"><header class="card-h"><h2>{icon("users")}Most coins</h2></header>'
            f'{f"<ul class=rank-list>{top}</ul>" if top else empty("Nobody has coins yet.", "", "users")}</section>'
            f'<section class="card"><header class="card-h"><h2>{icon("cart")}Recent purchases</h2></header>'
            f'{f"<ul class=buy-list>{recent}</ul>" if recent else empty("Nothing bought yet.", "", "cart")}</section></div>'
            f'{"".join(sections)}')
    return admin_layout(ctx, "Shop", f'<div class="stack">{body}</div>',
                        "Prices, coin rates and VIP for coins. Give coins, items or points to one player from their page under Players.")


def pre_box(lines, empty_msg):
    if lines is None:
        return f'<p class="muted">{e(empty_msg)}</p>'
    if not lines:
        return '<p class="muted">The log is empty.</p>'
    return f'<pre class="log js-bottom">{e(chr(10).join(lines))}</pre>'


def maps_admin(ctx):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    rep = app.store.maps_report()
    back = "/admin/maps"
    installed = sorted((m for m in maps.values() if m["installed"]), key=lambda m: m["name"])
    need = [m for m in installed if not m["zoned"]]
    rows = []
    for m in installed:
        zone = (f'<span class="badge badge-ok">{e(m["zone_src"] or "zoned")}</span>' if m["zoned"] else '<span class="badge badge-warn">Needs zones</span>')
        ws = (f'<a href="https://steamcommunity.com/sharedfiles/filedetails/?id={e(m["wsid"])}" rel="noopener noreferrer">{e(m["wsid"])}</a>'
              if m["wsid"] else '<span class="muted">-</span>')
        go = form(ctx, "changelevel", f'<input type="hidden" name="map" value="{e(m["name"])}"><button class="btn btn-ghost btn-sm" type="submit">Play</button>',
                  back, "inline", f"Change the map to {m['name']} now?")
        rows.append(f'<tr><td><a href="{e(map_url(m["name"]))}">{e(m["name"])}</a>{NOW_BADGE if m["current"] else ""}</td>'
                    f'<td>{tier_badge(m["tier"])}</td><td>{zone}</td><td class="num hide-sm">{fmt_int(m["finishers"])}</td><td class="mono hide-sm">{ws}</td><td class="c-act">{go}</td></tr>')
    table = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Map</th><th>Tier</th><th>Zones</th><th class="num hide-sm">Finishers</th>'
             f'<th class="hide-sm">Workshop</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>') if rows else empty("No maps installed.", "", "map")
    need_html = ""
    if need:
        chips = "".join(f'<li><span class="mono">{e(m["name"])}</span></li>' for m in need)
        need_html = (f'<section class="card"><header class="card-h"><h2>{icon("flag")}Maps that need zones</h2><span class="muted small">{len(need)}</span></header>'
                     f'<p>These maps have no start/end zones yet, so they are hidden from the vote and <span class="kbd">!maps</span>. To zone one: in game type '
                     f'<span class="kbd">!map &lt;name&gt;</span>, stand at one corner of the start area and type <span class="kbd">!zone start</span>, '
                     f'move to the opposite corner and type it again; do the same at the end with <span class="kbd">!zone end</span>.</p>'
                     f'<ul class="need-list">{chips}</ul></section>')
    failed = ""
    if rep["failed"]:
        frows = "".join(f'<tr><td>{e(f["title"] or "-")}</td><td class="mono">{e(f["wsid"] or "-")}</td><td class="wrap-text">{e(f["error"])}</td></tr>'
                        for f in rep["failed"])
        failed = (f'<section class="card flush"><header class="card-h pad"><h2>Failed downloads</h2><span class="muted small">{len(rep["failed"])}</span></header>'
                  f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Title</th><th>Workshop ID</th><th>Error</th></tr></thead><tbody>{frows}</tbody></table></div></section>')
    summary = (f'<div class="mini-stats">'
               f'<div><b>{len(installed)}</b><span>installed</span></div>'
               f'<div><b>{len(installed) - len(need)}</b><span>zoned</span></div>'
               f'<div><b class="{"warn" if need else ""}">{len(need)}</b><span>need zones</span></div>'
               f'<div><b class="{"bad" if rep["failed"] else ""}">{len(rep["failed"])}</b><span>failed</span></div>'
               f'<div><b>{rep["not_found"]}</b><span>wanted, not found</span></div></div>')
    gen = f'<p class="muted small">Map report from {when(rep["generated"])}.</p>' if rep["generated"] else '<p class="muted small">No map report yet (maps_report.json is written by the map installer).</p>'
    log = pre_box(tail_lines(os.path.join(app.logs_dir, "maps.log"), 200), "maps.log not found.")
    body = (f'<div class="stack">{summary}{gen}{need_html}'
            f'<section class="card flush"><header class="card-h pad"><h2>{icon("map")}Installed maps</h2><span class="muted small">{len(installed)}</span></header>{table}</section>'
            f'{failed}<section class="card"><header class="card-h"><h2>maps.log</h2><span class="muted small">last 200 lines</span></header>{log}</section></div>')
    return admin_layout(ctx, "Maps", body)


def logs(ctx):
    app = ctx.app
    ok, out = run_ctl(app.ctl, "logs")
    journal = f'<pre class="log js-bottom">{e(out)}</pre>' if ok else \
        f'<div class="alert alert-err">{icon("shield")}<div><b>Could not read the server journal.</b><p class="small">{e(out)}</p></div></div>'
    upd = pre_box(tail_lines(os.path.join(app.logs_dir, "update.log"), 200), "update.log not found.")
    mlog = pre_box(tail_lines(os.path.join(app.logs_dir, "maps.log"), 200), "maps.log not found.")
    audit = pre_box(tail_lines(os.path.join(app.store.portal_dir, "audit.log"), 200), "No admin actions logged yet.")
    health = pre_box(tail_lines(os.path.join(app.logs_dir, "health.txt"), 200),
                     "No health report yet. It is written every 10 minutes after the next update.")
    body = (f'<div class="stack">'
            f'<section class="card"><header class="card-h"><h2>Health check</h2><span class="muted small">every 10 min, or sudo surfcheck</span></header>{health}</section>'
            f'<section class="card"><header class="card-h"><h2>Server journal</h2><span class="muted small">last 300 lines</span></header>{journal}</section>'
            f'<section class="card"><header class="card-h"><h2>update.log</h2><span class="muted small">last 200 lines</span></header>{upd}</section>'
            f'<section class="card"><header class="card-h"><h2>maps.log</h2><span class="muted small">last 200 lines</span></header>{mlog}</section>'
            f'<section class="card"><header class="card-h"><h2>Admin audit log</h2><span class="muted small">last 200 lines</span></header>{audit}</section></div>')
    return admin_layout(ctx, "Logs", body)
