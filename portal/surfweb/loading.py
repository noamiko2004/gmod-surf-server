"""In-game loading screen: GET /loading?steamid=<SteamID64>&map=<map>.

GMOD shows the server's sv_loadingurl in an embedded browser while a player
connects. Some clients still run Awesomium (about Chrome 18), which fails on
modern TLS, so Caddy passes /loading* through on plain HTTP. The page sets no
cookies, loads only same-origin files under /loading/ plus Steam CDN images,
and is complete without JavaScript: static/loading.js only drives the download
progress and the rotating tips (ES5, no modern CSS required).
"""
import re
import time

from .fmt import MAPNAME_RE, e, fmt_int, fmt_time, hash_index, initial, valid_steamid
from .views import icon, tier_badge, title_chip

TIPS = [
    "Type !r to go back to the start and restart your timer.",
    "Try another style with !style: Sideways, Half-Sideways, W-Only or Low Gravity. Each has its own records.",
    "Type !replay to watch the server record run.",
    "!wr shows the top times on this map.",
    "!mapinfo shows the map's tier, stages, record and your best.",
    "!saveloc saves your spot and !tele takes you back, for practice.",
    "!spec lets you watch other players. Type it again to jump back in.",
    "Want a different map? Type !rtv to vote for a change.",
    "Type !help to see every command.",
]
TIP_SECONDS = 6
_CMD = re.compile(r"(![a-z]+)")


def params(query):
    """(steamid, map) from the query string; anything invalid becomes ''."""
    sid = str(query.get("steamid", "")).strip()
    mapname = str(query.get("map", "")).strip()
    return (sid if valid_steamid(sid) else "", mapname if MAPNAME_RE.match(mapname) else "")


def tip_html(text):
    return "".join(f'<span class="kbd">{e(p)}</span>' if i % 2 else e(p) for i, p in enumerate(_CMD.split(text)))


def map_title(name):
    """surf_kitsune -> dim 'surf_' prefix, the rest bold, line breaks allowed after underscores."""
    pre, rest = "", name
    if name.lower().startswith("surf_") and len(name) > 5:
        pre, rest = name[:5], name[5:]
    body = "_<wbr>".join(e(p) for p in rest.split("_"))
    return (f'<span class="ld-pre">{e(pre)}</span>' if pre else "") + body


def size_class(name):
    n = len(name)
    return "xl" if n <= 14 else "lg" if n <= 20 else "md" if n <= 26 else "sm"


def welcome_card(ctx, sid, p, cur):
    if not p:
        return ('<div class="ld-card ld-new"><p class="ld-hello">Welcome!</p><p class="ld-name">First time here?</p>'
                '<p class="ld-txt">Leave the start zone to start your timer. Finish maps to earn points and climb from '
                f'Newbie to Legend.</p><p class="ld-txt">Type {tip_html("!help")} in chat to see every command.</p></div>')
    av_url = ctx.app.avatars.get(sid)
    img = f'<img src="{e(av_url)}" alt="">' if av_url else ""
    av = f'<span class="ld-av av-c{hash_index(sid or p["name"], 8)}" aria-hidden="true"><span>{e(initial(p["name"]))}</span>{img}</span>'
    chips = title_chip(p["title_idx"])
    if p["vip"] is not None:
        chips += ' <span class="ld-vip">VIP</span>'
    rank = (f'<b>#{fmt_int(p["pos"])}</b><span>of {fmt_int(p["ranked"])} ranked</span>' if p["pos"]
            else '<b>-</b><span>not ranked yet</span>')
    stats = (f'<div class="ld-stats"><div><b>{fmt_int(p["points"])}</b><span>points</span></div>'
             f'<div>{rank}</div>'
             f'<div><b>{fmt_int(p["records"])}</b><span>record{"" if p["records"] == 1 else "s"}</span></div></div>')
    pb = ""
    if cur:
        mine = next((t for t in p["times"] if t["map"] == cur and t["track"] == 0 and t["style"] == "n"), None)
        if mine:
            gold = " ld-gold" if mine["pos"] == 1 else ""
            pb = (f'<p class="ld-pb">Your best here <b class="ld-mono{gold}">{e(fmt_time(mine["time"]))}</b>'
                  f'<span>#{fmt_int(mine["pos"])} of {fmt_int(mine["total"])}</span></p>')
        else:
            pb = '<p class="ld-pb ld-dim">You have not finished this map yet.</p>'
    return (f'<div class="ld-card ld-back"><div class="ld-who">{av}<div class="ld-who-txt">'
            f'<p class="ld-hello">Welcome back,</p><p class="ld-name">{e(p["name"])}</p><p class="ld-chips">{chips}</p></div></div>'
            f'{stats}{pb}</div>')


def page(ctx, sid="", mapname="", light=False):
    """The loading screen. light=True (rate limited) skips the status file and the database."""
    app = ctx.app
    brand = app.conf.brand
    if light:
        st = {"online": False, "hostname": "", "map": "", "players": [], "maxplayers": 0, "wr": None}
    else:
        st = app.store.status()
    online = st["online"]
    server_name = app.conf.server_name or st["hostname"]
    cur = mapname or (st["map"] if online else "")
    info = (app.store.maps(st).get(cur) or {}) if cur and not light else {}
    preview = info.get("preview", "")
    rec = info.get("record")
    wr = (rec["time"], rec["name"]) if rec else None
    if not wr and online and cur and st["map"] == cur and st["wr"]:
        wr = (st["wr"]["time"], st["wr"]["name"])
    player = app.store.player(sid) if sid and not light else None

    # top bar
    sub = f'<p class="ld-server">{e(server_name)}</p>' if server_name and server_name != brand else ""
    count = ""
    if online:
        mx = int(st["maxplayers"])
        of = f'<span class="ld-of"> / {mx}</span>' if mx else ""
        count = (f'<div class="ld-online"><span class="ld-pill"><span class="ld-dot"></span><b>{len(st["players"])}</b>'
                 f'{of} online</span></div>')
    top = (f'<div class="ld-top"><div class="ld-brand"><img class="ld-logo" src="{e(app.loading_url("logo.svg"))}" alt="" width="56" height="56">'
           f'<div class="ld-brand-txt"><p class="ld-brandname">{e(brand)}</p>{sub}</div></div>{count}</div>')

    # map
    if cur:
        meta = []
        tb = tier_badge(info.get("tier", 0), long=True)
        if tb:
            meta.append(tb)
        if info.get("mapper"):
            meta.append(f'<span class="ld-mapper">by {e(info["mapper"])}</span>')
        if info.get("bonuses"):
            n = len(info["bonuses"])
            meta.append(f'<span class="ld-dim">{n} bonus{"es" if n != 1 else ""}</span>')
        meta_html = f'<p class="ld-meta">{" ".join(meta)}</p>' if meta else ""
        if wr:
            rec_html = (f'<p class="ld-wr">{icon("trophy", "ld-ic")}<span class="ld-wr-label">Server record</span>'
                        f'<b class="ld-mono ld-gold">{e(fmt_time(wr[0]))}</b><span class="ld-wr-by">by {e(wr[1])}</span></p>')
        elif info:
            rec_html = (f'<p class="ld-wr ld-wr-none">{icon("trophy", "ld-ic")}<span class="ld-wr-label">No record yet.</span>'
                        f'<span class="ld-wr-by">Finish it first and the record is yours.</span></p>')
        else:
            rec_html = ""
        title = (f'<h1 class="ld-mapname ld-sz-{size_class(cur)}" id="ld-map" data-known="1">{map_title(cur)}</h1>')
        mapcol = f'<p class="ld-eyebrow">Now loading</p>{title}{meta_html}{rec_html}'
    else:
        mapcol = (f'<p class="ld-eyebrow">Now loading</p>'
                  f'<h1 class="ld-mapname ld-sz-lg" id="ld-map" data-known="0">Joining {e(brand)}</h1>')

    tip0 = int(time.time() // TIP_SECONDS) % len(TIPS)
    tips = "".join(f'<li class="ld-tip{" on" if i == tip0 else ""}"><span class="ld-tiplabel">Tip</span>{tip_html(t)}</li>'
                   for i, t in enumerate(TIPS))
    g = hash_index(cur or brand, 8)
    img = f'<div class="ld-photo"><img class="ld-img" id="ld-img" src="{e(preview)}" alt=""></div>' if preview else ""
    waves = ('<svg class="ld-waves" viewBox="0 0 2880 220" preserveAspectRatio="none">'
             '<path class="ld-w1" d="M0 120 C240 60 480 60 720 120 S1200 180 1440 120 S1920 60 2160 120 S2640 180 2880 120 V220 H0Z"/>'
             '<path class="ld-w2" d="M0 150 C240 100 480 100 720 150 S1200 200 1440 150 S1920 100 2160 150 S2640 200 2880 150 V220 H0Z"/>'
             '</svg>')
    title_txt = f"Loading {cur} · {brand}" if cur else f"Joining {brand}"
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{e(title_txt)}</title>
<link rel="stylesheet" href="{e(app.loading_url("loading.css"))}">
<script src="{e(app.loading_url("loading.js"))}"></script>
</head>
<body class="ld g{g}{" has-img" if preview else ""}">
<div class="ld-bg" aria-hidden="true"><div class="ld-glow ld-glow-a"></div><div class="ld-glow ld-glow-b"></div>{img}{waves}<div class="ld-shade"></div></div>
<div class="ld-shell">
<div class="ld-row ld-row-top"><div class="ld-cell">{top}</div></div>
<div class="ld-row ld-row-mid"><div class="ld-cell ld-cell-mid">
<div class="ld-main"><div class="ld-mapcol">{mapcol}</div><div class="ld-side">{welcome_card(ctx, sid, player, cur)}</div></div>
</div></div>
<div class="ld-row ld-row-bot"><div class="ld-cell"><div class="ld-bottom">
<div class="ld-prog">
<p class="ld-statusrow"><span class="ld-count" id="ld-count"></span><span class="ld-spin" aria-hidden="true"></span><span class="ld-status" id="ld-status" aria-live="polite">Connecting to the server</span></p>
<div class="ld-bar is-indet" id="ld-bar"><div class="ld-fill" id="ld-fill"></div></div>
<p class="ld-file" id="ld-file"></p>
</div>
<div class="ld-tipbox"><ul class="ld-tips" id="ld-tips" data-seconds="{TIP_SECONDS}">{tips}</ul></div>
</div></div></div>
</div>
</body>
</html>'''
