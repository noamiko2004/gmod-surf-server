"""Public pages: home, leaderboard, maps, map detail, player profile, /api/status."""
import time

from .fmt import (TITLES, e, fmt_clock, fmt_duration, fmt_gap, fmt_improve, fmt_int, fmt_time, hash_index,
                  track_label, track_of)
from .views import (avatar, empty, icon, layout, map_url, page_head, player_link, player_url, short_map,
                    thumb, tier_badge, title_chip, ttime, when)

STATE_TEXT = {"start": "In start zone", "idle": "Surfing", "nozones": "Free surf", "spec": "Spectating"}


def state_html(p):
    st, track = p["state"], p["track"]
    bonus = f' <span class="tag tag-bonus">Bonus {int(track)}</span>' if track else ""
    if st == "running":
        return (f'<span class="state st-run"><span class="pulse" aria-hidden="true"></span>Running '
                f'<span class="mono js-run" data-t="{p["time"]:.3f}">{e(fmt_time(p["time"]))}</span></span>{bonus}')
    if st == "finished":
        t = f' <span class="mono">{e(fmt_time(p["time"]))}</span>' if p["time"] > 0 else ""
        return f'<span class="state st-fin">{icon("flag")}Finished{t}</span>{bonus}'
    cls = {"start": "st-start", "spec": "st-spec"}.get(st, "st-idle")
    return f'<span class="state {cls}">{e(STATE_TEXT.get(st, "Surfing"))}</span>{bonus}'


def live_player_rows(ctx, players):
    rows = []
    for p in players:
        vip = ' <span class="badge badge-vip">VIP</span>' if p["vip"] else ""
        pb = f'<span class="pb">PB {ttime(p["pb"])}</span>' if p["pb"] > 0 else '<span class="pb muted">No PB yet</span>'
        rank = f'<span class="muted">#{int(p["rank"])}</span> ' if p["rank"] else ""
        rows.append(
            f'<li class="prow">{avatar(ctx, p["steamid"], p["name"])}'
            f'<div class="prow-main"><div class="prow-name">{player_link(p["steamid"], p["name"])}{vip}</div>'
            f'<div class="prow-sub">{rank}{title_chip(p["title_idx"], p["title"])} <span class="muted">{fmt_int(p["points"])} pts</span></div></div>'
            f'<div class="prow-state">{state_html(p)}{pb}</div></li>')
    return "".join(rows)


def status_card(ctx, st, maps):
    online = st["online"]
    cur = st["map"]
    info = maps.get(cur, {}) if cur else {}
    preview = info.get("preview", "")
    tier = st["tier"] or info.get("tier", 0)
    mapper = st["mapper"] or info.get("mapper", "")
    n = len(st["players"])
    pill = ('<span class="pill pill-on js-pill"><span class="dot"></span><span class="js-pilltext">Online</span></span>' if online else
            '<span class="pill pill-off js-pill"><span class="dot"></span><span class="js-pilltext">Offline</span></span>')
    if cur:
        overlay = (f'<div class="sc-map"><div class="sc-badges"><span class="js-tier">{tier_badge(tier)}</span>'
                   f'<span class="badge badge-live js-livebadge"{"" if online else " hidden"}>Live</span></div>'
                   f'<a class="sc-mapname js-map" href="{e(map_url(cur))}">{e(cur)}</a>'
                   f'<p class="sc-mapper js-mapper">{("by " + e(mapper)) if mapper else ""}</p></div>')
    else:
        overlay = ('<div class="sc-map"><div class="sc-badges"><span class="js-tier"></span></div>'
                   '<span class="sc-mapname js-map">No map</span><p class="sc-mapper js-mapper"></p></div>')
    wr = st["wr"]
    wr_html = (f'<dd class="gold mono js-wr">{e(fmt_time(wr["time"]))}</dd><dd class="sub js-wrname">{e(wr["name"])}</dd>' if wr else
               '<dd class="js-wr muted">No record</dd><dd class="sub js-wrname">Be the first</dd>')
    left = st["timeleft"] - int(st["age"]) if online else 0
    return f'''<aside class="card status-card{"" if online else " is-off"}" id="live" data-age="{st["age"]:.2f}" data-left="{max(0, left)}" aria-live="polite">
<div class="sc-head">{pill}<span class="sc-count"><b class="js-count">{n}</b><span class="muted">/<span class="js-max">{int(st["maxplayers"]) or "?"}</span> players</span></span></div>
<div class="sc-thumb js-thumb" data-map="{e(cur)}" data-preview="{e(preview)}">{thumb(cur or "surf", preview, "", overlay)}</div>
<p class="sc-offline js-offmsg"{" hidden" if online else ""}>The server is restarting or updating. It is usually back within a minute or two.</p>
<dl class="sc-stats">
<div><dt>{icon("clock")}Time left</dt><dd class="mono js-left">{e(fmt_clock(left)) if online else "-"}</dd><dd class="sub">until map vote</dd></div>
<div><dt>{icon("trophy")}<span class="hide-sm">Server </span>record</dt>{wr_html}</div>
</dl>
</aside>'''


def home(ctx):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    rank = app.store.ranking()
    stats = app.store.stats()
    brand = app.conf.brand
    server_name = app.conf.server_name or st["hostname"] or brand
    addr = app.public_addr
    players = st["players"]
    plist = live_player_rows(ctx, players)
    if st["online"]:
        p_empty = empty("Nobody is surfing right now.", "Hop on and take the first record of the session.", "users")
    else:
        p_empty = empty("The server is offline.", "Live players show up here once it is back.", "users")
    top = []
    for ent in rank["players"][:10]:
        top.append(f'<li><span class="pos pos-{min(ent["pos"], 4)}">{ent["pos"]}</span>{avatar(ctx, ent["sid"], ent["name"], "sm")}'
                   f'<div class="tl-main">{player_link(ent["sid"], ent["name"])}{title_chip(ent["title_idx"])}</div>'
                   f'<span class="tl-pts mono">{fmt_int(ent["points"])}<small>pts</small></span></li>')
    top_html = f'<ol class="toplist">{"".join(top)}</ol>' if top else empty("No ranked players yet.", "Finish any map to get on the board.", "trophy")
    recs = record_items(ctx, app.store.recent_records(10))
    rec_html = f'<ul class="reclist">{recs}</ul>' if recs else empty("No records yet.", "The first finish on a map sets the record.", "trophy")
    join = (f'<a class="btn btn-primary btn-lg" href="steam://connect/{e(addr)}">{icon("play")}<span>Join server</span></a>'
            f'<button class="btn btn-ghost btn-lg js-copy" type="button" data-copy="{e(addr)}" title="Copy the server address">'
            f'{icon("copy")}<span class="mono js-copytext">{e(addr)}</span></button>') if addr else ""
    zoned = sum(1 for m in maps.values() if m["installed"] and m["zoned"])
    body = f'''
<section class="hero">
<div class="hero-bg" aria-hidden="true"><div class="glow glow-a"></div><div class="glow glow-b"></div>
<svg class="waves" viewBox="0 0 2880 220" preserveAspectRatio="none">
<path class="wave w1" d="M0 120 C240 60 480 60 720 120 S1200 180 1440 120 S1920 60 2160 120 S2640 180 2880 120 V220 H0Z"/>
<path class="wave w2" d="M0 150 C240 100 480 100 720 150 S1200 200 1440 150 S1920 100 2160 150 S2640 200 2880 150 V220 H0Z"/>
<path class="wave w3" d="M0 175 C240 145 480 145 720 175 S1200 205 1440 175 S1920 145 2160 175 S2640 205 2880 175 V220 H0Z"/>
</svg></div>
<div class="wrap hero-in">
<div class="hero-copy">
<span class="eyebrow">Garry's Mod surf server</span>
<h1 class="hero-title">{e(brand)}</h1>
<p class="server-name">{e(server_name)}</p>
<p class="lead">Classic surf maps with a server-side timer, splits, bonuses and a record replay bot. Earn points on every map and climb from Newbie to Legend. Free to play, no pay to win.</p>
<div class="cta">{join}</div>
<ul class="hero-stats">
<li><b>{fmt_int(stats["players"])}</b><span>players seen</span></li>
<li><b>{fmt_int(stats["finishes"])}</b><span>finishes</span></li>
<li><b>{fmt_int(stats["maps"])}</b><span>maps</span></li>
<li><b>{fmt_int(stats["records"])}</b><span>records set</span></li>
</ul>
</div>
{status_card(ctx, st, maps)}
</div>
</section>
<div class="wrap home-grid">
<div class="col">
<section class="card live-card">
<header class="card-h"><h2>{icon("users")}Live players</h2><span class="muted small js-online">{len(players)} online</span></header>
<ul class="plist js-plist"{" hidden" if not players else ""}>{plist}</ul>
<div class="js-pempty"{" hidden" if players else ""}>{p_empty}</div>
</section>
<section class="card rec-card">
<header class="card-h"><h2>{icon("bolt")}Recent records</h2><a class="link-more" href="/maps">All maps{icon("arrow")}</a></header>
{rec_html}
</section>
</div>
<div class="col">
<section class="card top-card">
<header class="card-h"><h2>{icon("trophy")}Top 10</h2><a class="link-more" href="/leaderboard">Leaderboard{icon("arrow")}</a></header>
{top_html}
</section>
<section class="card how-card">
<header class="card-h"><h2>{icon("star")}How it works</h2></header>
<ol class="steps">
<li><b>Join</b><span>Click Join server or paste <span class="mono">connect {e(addr or "the address")}</span> in the GMOD console.</span></li>
<li><b>Surf</b><span>Leave the start zone to start the timer. <span class="kbd">!r</span> restarts, <span class="kbd">!b</span> picks a bonus.</span></li>
<li><b>Climb</b><span>Every finish earns points; the record is worth +50. {zoned} maps are ready to run.</span></li>
</ol>
</section>
{community_card(app)}
</div>
</div>'''
    return layout(ctx, "", body, page="home")


def community_card(app):
    discord, store = app.conf.https_url("DISCORD_URL"), app.conf.https_url("STORE_URL")
    if not discord and not store:
        return ""
    btns = ""
    if discord:
        btns += f'<a class="btn btn-primary btn-sm" href="{e(discord)}" rel="noopener noreferrer">{icon("discord")}<span>Join the Discord</span></a>'
    if store:
        btns += f'<a class="btn btn-gold btn-sm" href="{e(store)}" rel="noopener noreferrer">{icon("cart")}<span>VIP store</span></a>'
    return (f'<section class="card community-card"><header class="card-h"><h2>{icon("users")}Community</h2></header>'
            f'<p class="muted">New maps, record alerts and events. VIP is cosmetic only: trails, a gold name and tag.</p>'
            f'<div class="btn-row">{btns}</div></section>')


def record_items(ctx, recs, show_map=True):
    out = []
    for r in recs:
        where = f'<a href="{e(map_url(r["map"]))}">{e(r["map"])}</a>' if show_map else ""
        if r["track"]:
            where += f' <span class="tag tag-bonus">Bonus {int(r["track"])}</span>'
        if r["prev_time"] > 0:
            delta = f' <span class="delta">({e(fmt_improve(r["prev_time"] - r["time"]))})</span>'
            beat = f'beat {e(r["prev_name"])}' if r["prev_name"] else "new record"
        else:
            delta = ""
            beat = "first finish"
        verb = "set the record on " + where if show_map else ("set the record" + (" on " + where if where else ""))
        out.append(f'<li><span class="rec-ic">{icon("trophy")}</span><div class="rec-main"><p>{player_link(r["steamid"], r["name"])} '
                   f'{verb}: <b class="gold mono">{e(fmt_time(r["time"]))}</b>{delta}</p>'
                   f'<p class="muted small">{beat} · {when(r["date"])}</p></div></li>')
    return "".join(out)


# ------------------------------------------------------------------ leaderboard

def leaderboard(ctx):
    rank = ctx.app.store.ranking()
    top = rank["players"][:100]
    podium = ""
    if len(top) >= 3:
        cards = []
        for ent, cls in ((top[1], "p2"), (top[0], "p1"), (top[2], "p3")):
            cards.append(f'<a class="podium-card {cls}" href="{e(player_url(ent["sid"]))}">'
                         f'<span class="podium-pos pos pos-{ent["pos"]}">{ent["pos"]}</span>{avatar(ctx, ent["sid"], ent["name"], "lg")}'
                         f'<span class="podium-name">{e(ent["name"])}</span>{title_chip(ent["title_idx"])}'
                         f'<span class="podium-pts mono">{fmt_int(ent["points"])} <small>pts</small></span></a>')
        podium = f'<div class="podium">{"".join(cards)}</div>'
    rows = []
    for ent in top:
        recs = (f'<span class="recs">{icon("trophy", "ic ic-gold")}{fmt_int(ent["records"])}</span>' if ent["records"]
                else '<span class="muted">0</span>')
        rows.append(f'<tr><td class="c-pos"><span class="pos pos-{min(ent["pos"], 4)}">{ent["pos"]}</span></td>'
                    f'<td class="c-player"><div class="pcell">{avatar(ctx, ent["sid"], ent["name"], "sm")}<div class="pcell-txt">{player_link(ent["sid"], ent["name"])}'
                    f'<span class="show-sm">{title_chip(ent["title_idx"])}</span></div></div></td>'
                    f'<td class="hide-sm">{title_chip(ent["title_idx"])}</td>'
                    f'<td class="num strong">{fmt_int(ent["points"])}</td>'
                    f'<td class="num hide-sm">{fmt_int(ent["finished"])}</td>'
                    f'<td class="num">{recs}</td></tr>')
    if rows:
        table = (f'<div class="card flush"><div class="table-scroll"><table class="tbl">'
                 f'<thead><tr><th class="c-pos">#</th><th>Player</th><th class="hide-sm">Title</th><th class="num">Points</th>'
                 f'<th class="num hide-sm">Maps</th><th class="num"><span class="hide-sm">Records</span><span class="show-sm" title="Records">WRs</span></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')
    else:
        table = f'<div class="card">{empty("Nobody is ranked yet.", "Finish any map to earn points.", "trophy")}</div>'
    titles = "".join(f'<li>{title_chip(i)}<span class="mono">{need:,}+</span></li>' for i, (n, need, _) in enumerate(TITLES))
    how = f'''<section class="card howto">
<header class="card-h"><h2>{icon("star")}How points work</h2></header>
<p>Each map and bonus is ranked by time. Position 1 earns 110 points, 2nd 55, 3rd 50, then 5 less per place down to 10 for everyone below 10th. Bonus tracks are worth half. Your total decides your title.</p>
<ul class="title-scale">{titles}</ul>
</section>'''
    sub = f"Top {min(100, len(rank['players']))} of {fmt_int(len(rank['players']))} ranked surfers by points." if rank["players"] else "Points from every finished map and bonus."
    body = page_head("Leaderboard", e(sub), "Rankings") + f'<div class="wrap stack">{podium}{table}{how}</div>'
    return layout(ctx, "Leaderboard", body, page="leaderboard")


# ------------------------------------------------------------------ maps

def maps_page(ctx):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    installed = [m for m in maps.values() if m["installed"]]
    installed.sort(key=lambda m: (not m["current"], m["name"]))
    tiers = sorted({m["tier"] for m in installed if m["tier"]})
    cards = []
    for m in installed:
        badges = tier_badge(m["tier"])
        if m["current"]:
            badges += '<span class="badge badge-live"><span class="dot"></span>Playing now</span>'
        zone = ('<span class="badge badge-ok">Zoned</span>' if m["zoned"] else '<span class="badge badge-warn">Zones needed</span>')
        overlay = f'<div class="thumb-badges">{badges}<span class="tb-right">{zone}</span></div>'
        rec = m["record"]
        if rec:
            rec_html = (f'<div class="mc-rec">{icon("trophy", "ic ic-gold")}<span class="gold mono">{e(fmt_time(rec["time"]))}</span>'
                        f'<span class="mc-holder">{e(rec["name"])}</span></div>')
        else:
            rec_html = f'<div class="mc-rec muted">{icon("trophy", "ic")}<span>No record yet</span></div>'
        bon = f'<span class="muted">{len(m["bonuses"])} bonus{"es" if len(m["bonuses"]) != 1 else ""}</span>' if m["bonuses"] else ""
        mapper = f'<p class="mc-mapper">by {e(m["mapper"])}</p>' if m["mapper"] else '<p class="mc-mapper muted">Mapper unknown</p>'
        search = " ".join([m["name"], short_map(m["name"]), m["mapper"], m["title"]]).lower()
        cards.append(f'<a class="map-card{" is-live" if m["current"] else ""}" href="{e(map_url(m["name"]))}" data-search="{e(search)}" data-tier="{int(m["tier"])}">'
                     f'{thumb(m["name"], m["preview"], "", overlay)}'
                     f'<div class="mc-body"><h3>{e(m["name"])}</h3>{mapper}{rec_html}'
                     f'<div class="mc-foot"><span>{icon("users", "ic")}{fmt_int(m["finishers"])} finisher{"s" if m["finishers"] != 1 else ""}</span>{bon}</div></div></a>')
    chips = '<button type="button" class="chip on" data-tier="all" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" class="chip" data-tier="{t}" aria-pressed="false">T{t}</button>' for t in tiers)
    filters = (f'<div class="filters"><label class="search">{icon("search")}<span class="sr">Search maps</span>'
               f'<input type="search" class="js-mapsearch" placeholder="Search maps or mappers" autocomplete="off"></label>'
               f'<div class="chips js-tiers" role="group" aria-label="Filter by tier">{chips}</div></div>') if installed else ""
    zoned = sum(1 for m in installed if m["zoned"])
    sub = f"{len(installed)} surf maps installed, {zoned} with zones and a timer." if installed else "Maps appear here once the server installs them."
    grid = (f'<div class="map-grid js-mapgrid">{"".join(cards)}</div>'
            f'<div class="js-nomaps" hidden>{empty("No maps match your search.", "", "search")}</div>') if installed else \
        f'<div class="card">{empty("No maps installed yet.", "The server installs maps on its next update.", "map")}</div>'
    body = page_head("Maps", e(sub), "Map pool", filters) + f'<div class="wrap">{grid}</div>'
    return layout(ctx, "Maps", body, page="maps")


def map_detail(ctx, name):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    m = maps.get(name)
    if not m:
        return None
    rank = app.store.ranking()
    try:
        track = int(ctx.query.get("track", "0") or 0)
    except ValueError:
        track = 0
    tracks = [0] + m["bonuses"]
    if track not in tracks:
        track = 0
    key = name if not track else f"{name}#b{track}"
    rows_data = rank["keys"].get(key, [])[:100]
    best = rows_data[0]["time"] if rows_data else 0
    rows = []
    for r in rows_data:
        gap = '<span class="gold">Record</span>' if r["pos"] == 1 else e(fmt_gap(r["time"] - best))
        rows.append(f'<tr{" class=is-wr" if r["pos"] == 1 else ""}><td class="c-pos"><span class="pos pos-{min(r["pos"], 4)}">{r["pos"]}</span></td>'
                    f'<td class="c-player"><div class="pcell">{avatar(ctx, r["sid"], r["name"], "sm")}{player_link(r["sid"], r["name"])}</div></td>'
                    f'<td class="num mono strong">{e(fmt_time(r["time"]))}</td><td class="num mono muted">{gap}</td>'
                    f'<td class="num muted hide-sm">{when(r["date"], "date")}</td></tr>')
    tabs = ""
    if len(tracks) > 1:
        tabs = '<nav class="tabs" aria-label="Track">' + "".join(
            f'<a href="{e(map_url(name))}{"" if not t else "?track=" + str(t)}"{" class=on aria-current=page" if t == track else ""}>{e(track_label(t))}</a>'
            for t in tracks) + "</nav>"
    if rows:
        table = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th class="c-pos">#</th><th>Player</th>'
                 f'<th class="num">Time</th><th class="num">Gap</th><th class="num hide-sm">Date</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    else:
        table = empty("No times on this track yet.", "Be the first to finish and take the record.", "flag")
    total = len(rank["keys"].get(key, []))
    recs = record_items(ctx, app.store.recent_records(10, name), show_map=False)
    rec_html = f'<ul class="reclist compact">{recs}</ul>' if recs else empty("No records yet.", "", "trophy")
    rec = m["record"]
    badges = tier_badge(m["tier"], long=True)
    if m["current"]:
        badges += '<span class="badge badge-live"><span class="dot"></span>Playing now</span>'
    badges += '<span class="badge badge-ok">Zoned</span>' if m["zoned"] else '<span class="badge badge-warn">Zones needed</span>'
    if not m["installed"]:
        badges += '<span class="badge">Not installed</span>'
    actions = []
    if m["current"] and app.public_addr:
        actions.append(f'<a class="btn btn-primary" href="steam://connect/{e(app.public_addr)}">{icon("play")}<span>Join now</span></a>')
    if m["wsid"]:
        actions.append(f'<a class="btn btn-ghost" href="https://steamcommunity.com/sharedfiles/filedetails/?id={e(m["wsid"])}" rel="noopener noreferrer">'
                       f'{icon("external")}<span>Workshop page</span></a>')
    mapper = f'<p class="mh-mapper">by {e(m["mapper"])}</p>' if m["mapper"] else ""
    stat_rec = (f'<dd class="gold mono">{e(fmt_time(rec["time"]))}</dd><dd class="sub">{e(rec["name"])}</dd>' if rec
                else '<dd class="muted">None yet</dd>')
    body = f'''<section class="map-hero">
<div class="map-hero-bg" aria-hidden="true">{thumb(name, m["preview"], "bg")}</div>
<div class="wrap map-hero-in">
<div class="mh-thumb">{thumb(name, m["preview"])}</div>
<div class="mh-copy">
<a class="back" href="/maps">{icon("back")}<span>All maps</span></a>
<h1>{e(name)}</h1>{mapper}
<div class="mh-badges">{badges}</div>
<div class="mh-actions">{"".join(actions)}</div>
</div>
<dl class="mh-stats">
<div><dt>Server record</dt>{stat_rec}</div>
<div><dt>Finishers</dt><dd class="mono">{fmt_int(m["finishers"])}</dd></div>
<div><dt>Bonuses</dt><dd class="mono">{len(m["bonuses"])}</dd></div>
</dl>
</div>
</section>
<div class="wrap map-grid-2">
<section class="card flush">
<header class="card-h pad"><h2>{icon("flag")}{e(track_label(track))} leaderboard</h2><span class="muted small">{fmt_int(total)} finisher{"s" if total != 1 else ""}</span></header>
{tabs}
{table}
</section>
<section class="card">
<header class="card-h"><h2>{icon("bolt")}Record history</h2></header>
{rec_html}
</section>
</div>'''
    return layout(ctx, name, body, page="map", description=f"{name}: server records and leaderboard.")


# ------------------------------------------------------------------ players

def player_page(ctx, sid):
    app = ctx.app
    p = app.store.player(sid)
    if not p:
        return None
    st = app.store.status()
    online = next((x for x in st["players"] if x["steamid"] == sid), None)
    idx = p["title_idx"]
    nxt = TITLES[idx + 1] if idx + 1 < len(TITLES) else None
    if nxt:
        lo = TITLES[idx][1]
        prog = (f'<div class="progress"><div class="progress-top"><span><b>{fmt_int(p["points"])}</b> points</span>'
                f'<span class="muted">{fmt_int(nxt[1] - p["points"])} more for {title_chip(idx + 1)}</span></div>'
                f'<progress max="{nxt[1] - lo}" value="{max(0, p["points"] - lo)}"></progress></div>')
    else:
        prog = f'<div class="progress"><div class="progress-top"><span><b>{fmt_int(p["points"])}</b> points</span><span class="muted">Top title reached</span></div><progress max="1" value="1"></progress></div>'
    badges = title_chip(idx)
    if p["vip"] is not None:
        badges += '<span class="badge badge-vip">VIP</span>'
    if online:
        badges += '<span class="badge badge-live"><span class="dot"></span>Online now</span>'
    badges += (f'<a class="badge badge-link" href="https://steamcommunity.com/profiles/{e(sid)}" rel="noopener noreferrer">'
               f'{icon("steam", "ic")}Steam profile</a>')
    rank_txt = f'#{p["pos"]}' if p["pos"] else "-"
    stats = [
        ("Rank", f'<dd class="mono">{rank_txt}</dd><dd class="sub">of {fmt_int(p["ranked"])}</dd>' if p["pos"] else '<dd class="muted">Unranked</dd>'),
        ("Maps finished", f'<dd class="mono">{fmt_int(p["finished"])}</dd><dd class="sub">+{fmt_int(p["bonuses"])} bonus</dd>'),
        ("Records", f'<dd class="mono gold">{fmt_int(p["records"])}</dd>' if p["records"] else '<dd class="mono">0</dd>'),
        ("Playtime", f'<dd class="mono">{e(fmt_duration(p["playtime"]))}</dd>'),
        ("First seen", f'<dd class="dd-date">{when(p["firstseen"], "date")}</dd>'),
        ("Last seen", f'<dd class="dd-date">{"Now" if online else when(p["lastseen"])}</dd>'),
    ]
    stat_html = "".join(f'<div><dt>{e(k)}</dt>{v}</div>' for k, v in stats)
    held = [t for t in p["times"] if t["pos"] == 1]
    held_html = ""
    if held:
        chips = "".join(
            f'<a class="rec-chip" href="{e(map_url(track_of(t["key"])[0]))}{"?track=" + str(track_of(t["key"])[1]) if track_of(t["key"])[1] else ""}">'
            f'{icon("trophy", "ic ic-gold")}<span>{e(track_of(t["key"])[0])}</span>'
            f'{(" <span class=tag>B" + str(track_of(t["key"])[1]) + "</span>") if track_of(t["key"])[1] else ""}'
            f'<span class="mono gold">{e(fmt_time(t["time"]))}</span></a>' for t in held)
        held_html = f'<section class="card"><header class="card-h"><h2>{icon("trophy")}Records held</h2><span class="muted small">{len(held)}</span></header><div class="rec-chips">{chips}</div></section>'
    rows = []
    for t in sorted(p["times"], key=lambda x: (track_of(x["key"])[0], track_of(x["key"])[1])):
        base, tr = track_of(t["key"])
        href = map_url(base) + (f"?track={tr}" if tr else "")
        pos_cls = " gold" if t["pos"] == 1 else ""
        btag = f' <span class="show-sm tag tag-bonus">B{tr}</span>' if tr else ""
        rows.append(f'<tr{" class=is-wr" if t["pos"] == 1 else ""}><td class="wrap-sm"><a href="{e(href)}">{e(base)}</a>{btag}</td>'
                    f'<td class="hide-sm">{e(track_label(tr)) if tr else "<span class=muted>Main</span>"}</td>'
                    f'<td class="num mono strong{pos_cls}">{e(fmt_time(t["time"]))}</td>'
                    f'<td class="num mono"><span class="{"gold" if t["pos"] == 1 else ""}">#{t["pos"]}</span><span class="muted">/{t["total"]}</span></td>'
                    f'<td class="num mono muted hide-sm">{"-" if t["pos"] == 1 else e(fmt_gap(t["gap"]))}</td>'
                    f'<td class="num muted hide-sm">{when(t["date"], "date")}</td></tr>')
    times = (f'<div class="table-scroll"><table class="tbl"><thead><tr><th>Map</th><th class="hide-sm">Track</th><th class="num">Time</th>'
             f'<th class="num">Pos</th><th class="num hide-sm">Gap</th><th class="num hide-sm">Date</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
             if rows else empty("No finished maps yet.", "", "flag"))
    body = f'''<section class="profile-hero">
<div class="wrap profile-in">
<div class="profile-id">{avatar(ctx, sid, p["name"], "xl")}
<div class="profile-copy"><span class="eyebrow">Player</span><h1>{e(p["name"])}</h1>
<div class="profile-badges">{badges}</div>
{prog}</div></div>
<dl class="stat-grid">{stat_html}</dl>
</div>
</section>
<div class="wrap stack">
{held_html}
<section class="card flush"><header class="card-h pad"><h2>{icon("flag")}Times</h2><span class="muted small">{len(p["times"])} track{"s" if len(p["times"]) != 1 else ""}</span></header>{times}</section>
</div>'''
    return layout(ctx, p["name"], body, page="player", description=f"{p['name']} on the surf server: rank, points and times.")


# ------------------------------------------------------------------ API

def api_status(ctx):
    app = ctx.app
    st = app.store.status()
    maps = app.store.maps(st)
    info = maps.get(st["map"], {}) if st["map"] else {}
    players = []
    for p in st["players"]:
        players.append({
            "steamid": p["steamid"], "name": p["name"], "title": p["title"] or TITLES[p["title_idx"]][0],
            "title_idx": p["title_idx"], "points": p["points"], "rank": p["rank"], "state": p["state"],
            "track": p["track"], "time": round(p["time"], 3), "pb": round(p["pb"], 3), "vip": p["vip"],
            "connected": p["connected"], "avatar": app.avatars.get(p["steamid"]) if p["steamid"] else "",
            "av": hash_index(p["steamid"] or p["name"] or "?", 8),
        })
    return {
        "online": st["online"], "now": int(time.time()), "updated": st["updated"], "age": round(st["age"], 2),
        "hostname": st["hostname"], "brand": st["brand"] or app.conf.brand, "map": st["map"],
        "map_url": map_url(st["map"]) if st["map"] else "",
        "tier": st["tier"] or info.get("tier", 0), "mapper": st["mapper"] or info.get("mapper", ""),
        "preview": info.get("preview", ""), "map_g": hash_index(st["map"] or "surf", 8), "maxplayers": st["maxplayers"], "timeleft": st["timeleft"],
        "map_started": st["map_started"], "wr": st["wr"], "replay": st["replay"],
        "join": app.public_addr, "players": players,
    }

