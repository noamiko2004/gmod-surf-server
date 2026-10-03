"""Page shell and shared HTML components. Every dynamic value goes through e()."""
import urllib.parse

from .fmt import (TITLES, e, fmt_ago, fmt_date, fmt_datetime, fmt_time, hash_index, initial, iso,
                  parse_key, style_label, track_label)

ICONS = {
    "play": '<path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" fill="currentColor"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/>'
            '<path d="M5 15V6.5A1.5 1.5 0 0 1 6.5 5H15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "trophy": '<path d="M7 4h10v3a5 5 0 0 1-10 0V4z" fill="currentColor"/><path d="M7 6H4.5a.5.5 0 0 0-.5.5C4 9 5.5 10.5 7.5 10.8M17 6h2.5a.5.5 0 0 1 .5.5c0 2.5-1.5 4-3.5 4.3" fill="none" stroke="currentColor" stroke-width="1.8"/>'
              '<path d="M10.5 12.5h3l.5 3.5h-4l.5-3.5zM8 17.5h8a1 1 0 0 1 1 1V20H7v-1.5a1 1 0 0 1 1-1z" fill="currentColor"/>',
    "users": '<circle cx="9" cy="8.5" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 19c.8-3.2 3.2-5 6-5s5.2 1.8 6 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
             '<path d="M15.5 5.3a3.4 3.4 0 0 1 0 6.4M17.5 14.3c1.7.6 3 2.3 3.5 4.7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "clock": '<circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7.5V12l3 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "map": '<path d="M9 4.5l-5 2v13l5-2 6 2 5-2v-13l-5 2-6-2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 4.5v13M15 6.5v13" stroke="currentColor" stroke-width="2"/>',
    "flag": '<path d="M5.5 21V4.5M5.5 5h11l-2 4 2 4h-11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "external": '<path d="M14 5h5v5M19 5l-8 8M17 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "search": '<circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "arrow": '<path d="M5 12h13M13 6.5l5.5 5.5-5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "back": '<path d="M19 12H6M11 6.5L5.5 12l5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "shield": '<path d="M12 3.5l7 2.5v5.5c0 4.4-3 7.9-7 9-4-1.1-7-4.6-7-9V6l7-2.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "star": '<path d="M12 3.8l2.5 5.2 5.7.8-4.1 4 1 5.6-5.1-2.7-5.1 2.7 1-5.6-4.1-4 5.7-.8z" fill="currentColor"/>',
    "bolt": '<path d="M13 3L5 13.5h6L10.5 21 19 10h-6.2z" fill="currentColor"/>',
    "discord": '<path d="M19.3 5.6A16.6 16.6 0 0 0 15.2 4.3l-.5 1a15.3 15.3 0 0 0-5.4 0l-.5-1A16.6 16.6 0 0 0 4.7 5.6C2.1 9.5 1.4 13.3 1.8 17a16.8 16.8 0 0 0 5 2.6l1.1-1.7a10.8 10.8 0 0 1-1.7-.8l.4-.3a11.9 11.9 0 0 0 10.8 0l.4.3c-.5.3-1.1.6-1.7.8l1.1 1.7a16.8 16.8 0 0 0 5-2.6c.5-4.3-.8-8.1-2.9-11.4zM8.7 14.8c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2zm6.6 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2z" fill="currentColor"/>',
    "cart": '<path d="M3.5 4.5h2l2.2 10.2a1 1 0 0 0 1 .8h8.6a1 1 0 0 0 1-.8l1.4-6.7H6.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="9.5" cy="19" r="1.5" fill="currentColor"/><circle cx="17" cy="19" r="1.5" fill="currentColor"/>',
    "steam": '<path d="M12 2.5a9.5 9.5 0 0 0-9.46 8.66l5.09 2.1a2.68 2.68 0 0 1 1.52-.47h.15l2.27-3.28v-.05a3.6 3.6 0 1 1 3.6 3.6h-.08l-3.23 2.3v.13a2.7 2.7 0 0 1-5.35.52L3.04 14.6A9.5 9.5 0 1 0 12 2.5zm-3.53 14.4l-1.17-.48a2.03 2.03 0 1 0 1.11-2.77l1.2.5a1.5 1.5 0 1 1-1.14 2.75zm8.98-7.38a2.4 2.4 0 1 0-2.4 2.4 2.4 2.4 0 0 0 2.4-2.4zm-4.2 0a1.8 1.8 0 1 1 1.8 1.8 1.8 1.8 0 0 1-1.8-1.8z" fill="currentColor"/>',
    "logout": '<path d="M14 7.5V5.5a1 1 0 0 0-1-1H5.5a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1H13a1 1 0 0 0 1-1v-2M10 12h10M17 8.5l3.5 3.5-3.5 3.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "refresh": '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "download": '<path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
}


def icon(name, cls="ic"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICONS[name]}</svg>'


def q(s):
    return urllib.parse.quote(str(s), safe="")


def map_url(name):
    return "/maps/" + q(name)


def track_url(name, track=0, style="n"):
    """Map page for one leaderboard: /maps/surf_x?track=2&style=sw (Normal main has no query)."""
    args = []
    if track:
        args.append(f"track={int(track)}")
    if style and style != "n":
        args.append("style=" + q(style))
    return map_url(name) + ("?" + "&".join(args) if args else "")


def player_url(sid):
    return "/players/" + q(sid)


def avatar(ctx, sid, name, size="md"):
    url = ctx.app.avatars.get(sid) if sid else ""
    cls = f"av av-{size} av-c{hash_index(sid or name or '?', 8)}"
    img = f'<img src="{e(url)}" alt="" loading="lazy" decoding="async">' if url else ""
    return f'<span class="{cls}" aria-hidden="true"><span>{e(initial(name))}</span>{img}</span>'


def player_link(sid, name, cls="pname"):
    if sid:
        return f'<a class="{cls}" href="{e(player_url(sid))}">{e(name)}</a>'
    return f'<span class="{cls}">{e(name)}</span>'


def title_chip(idx, name=None):
    idx = max(0, min(len(TITLES) - 1, int(idx)))
    return f'<span class="ttl t{idx}">{e(name or TITLES[idx][0])}</span>'


def tier_badge(tier, long=False):
    if not tier:
        return '<span class="tier tier-0" title="Tier unknown">T?</span>' if not long else ""
    n = min(int(tier), 8)
    label = f"Tier {int(tier)}" if long else f"T{int(tier)}"
    return f'<span class="tier tier-{n}" title="Tier {int(tier)}">{label}</span>'


def short_map(name):
    s = str(name or "")
    if s.startswith("surf_"):
        s = s[5:]
    return s.replace("_", " ")


def thumb(name, preview, cls="", overlay=""):
    g = hash_index(name, 8)
    img = f'<img src="{e(preview)}" alt="" loading="lazy" decoding="async">' if preview else ""
    return (f'<div class="thumb g{g} {cls}"><span class="thumb-name" aria-hidden="true">{e(short_map(name))}</span>'
            f'{img}{overlay}</div>')


def ttime(t, cls="mono"):
    return f'<span class="{cls}">{e(fmt_time(t))}</span>'


def when(ts, mode="ago"):
    if not ts:
        return '<span class="muted">-</span>'
    text = fmt_ago(ts) if mode == "ago" else fmt_date(ts)
    return f'<time datetime="{e(iso(ts))}" title="{e(fmt_datetime(ts))}">{e(text)}</time>'


def key_label(key):
    """'surf_x#b2@sw' -> ('surf_x', 'Bonus 2 · Sideways'); Normal is not named."""
    base, track, style = parse_key(key)
    label = track_label(track)
    return base, (label if style == "n" else f"{label} · {style_label(style)}")


def bonus_tag(track, short=False):
    if not track:
        return ""
    return f'<span class="tag tag-bonus">{"B" if short else "Bonus "}{int(track)}</span>'


def style_tag(style):
    """Small tag for a run style; nothing for Normal."""
    if not style or style == "n":
        return ""
    return f'<span class="tag tag-style">{e(style_label(style))}</span>'


def empty(msg, sub="", ic="map"):
    s = f'<p class="empty-sub">{e(sub)}</p>' if sub else ""
    return f'<div class="empty">{icon(ic, "ic empty-ic")}<p>{e(msg)}</p>{s}</div>'


def csrf_field(ctx):
    return f'<input type="hidden" name="csrf" value="{e(ctx.csrf)}">'


def page_head(title, sub="", eyebrow="", extra=""):
    eb = f'<span class="eyebrow">{e(eyebrow)}</span>' if eyebrow else ""
    s = f'<p class="lead">{sub}</p>' if sub else ""
    return f'<section class="page-head"><div class="wrap">{eb}<h1>{e(title)}</h1>{s}{extra}</div></section>'


def logo_img(app):
    return f'<img class="logo-mark" src="{app.static_url("favicon.svg")}" alt="" width="32" height="32">'


def layout(ctx, title, body, page="", description="", head=""):
    app = ctx.app
    brand = app.conf.brand
    path = ctx.path
    nav = [("/", "Home"), ("/leaderboard", "Leaderboard"), ("/maps", "Maps"), ("/shop", "Shop")]
    if ctx.is_admin:
        nav.append(("/admin", "Admin"))

    def active(href):
        if href == "/":
            return path == "/"
        return path == href or path.startswith(href + "/") or (href == "/maps" and path.startswith("/maps"))

    links = "".join(
        f'<a href="{href}"{" class=on aria-current=page" if active(href) else ""}>{label}</a>' for href, label in nav)
    if ctx.sid:
        me_name = ctx.my_name
        user = (f'<a class="me" href="{e(player_url(ctx.sid))}" title="Your profile">{avatar(ctx, ctx.sid, me_name, "sm")}'
                f'<span class="me-name">{e(me_name)}</span></a>'
                f'<form method="post" action="/logout" class="inline">{csrf_field(ctx)}'
                f'<button class="iconbtn" type="submit" title="Sign out" aria-label="Sign out">{icon("logout")}</button></form>')
    else:
        nxt = path if path not in ("/login", "/auth/steam") else "/"
        user = (f'<a class="btn btn-steam btn-sm" href="/login?next={e(q(nxt))}">{icon("steam")}'
                f'<span>Sign in<span class="hide-sm"> with Steam</span></span></a>')
    flash = ""
    if ctx.flash:
        kind, msg = ctx.flash
        kind = "ok" if kind == "ok" else "err"
        flash = (f'<div class="wrap"><div class="flash flash-{kind}" role="status">'
                 f'{icon("check" if kind == "ok" else "shield")}<span>{e(msg)}</span></div></div>')
    footer_links = []
    if app.conf.discord_url:
        footer_links.append(f'<a class="btn btn-ghost btn-sm" href="{e(app.conf.discord_url)}" rel="noopener noreferrer">'
                            f'{icon("discord")}<span>Discord</span></a>')
    if app.conf.https_url("STORE_URL"):
        footer_links.append(f'<a class="btn btn-ghost btn-sm" href="{e(app.conf.https_url("STORE_URL"))}" rel="noopener noreferrer">'
                            f'{icon("cart")}<span>Store</span></a>')
    server_name = app.conf.server_name or brand
    desc = description or f"{server_name}: live server status, leaderboards and map records."
    full_title = f"{title} · {brand}" if title else f"{brand} · Garry's Mod surf server"
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#0a0d14">
<meta name="color-scheme" content="dark">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
<link rel="icon" href="{app.static_url("favicon.svg")}" type="image/svg+xml">
<link rel="stylesheet" href="{app.static_url("style.css")}">
<script src="{app.static_url("app.js")}" defer></script>
{head}
</head>
<body class="pg-{e(page)}">
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
<div class="wrap topbar-in">
<a class="logo" href="/" aria-label="{e(brand)} home">{logo_img(app)}<span>{e(brand)}</span></a>
<nav class="mainnav" aria-label="Main">{links}</nav>
<div class="user">{user}</div>
</div>
</header>
{flash}
<main id="main">
{body}
</main>
<footer class="footer">
<div class="wrap footer-in">
<div class="footer-brand"><a class="logo" href="/">{logo_img(app)}<span>{e(brand)}</span></a>
<p class="muted">{e(server_name)}</p></div>
<div class="footer-links">{"".join(footer_links)}</div>
<p class="footer-note muted">Garry's Mod surf server. Not affiliated with Valve or Facepunch. Steam sign-in only shares your public SteamID.</p>
</div>
</footer>
</body>
</html>'''


def error_page(ctx, code, title, msg):
    body = (f'<section class="page-head error-head"><div class="wrap"><span class="eyebrow">Error {int(code)}</span>'
            f'<h1>{e(title)}</h1><p class="lead">{e(msg)}</p>'
            f'<p><a class="btn btn-primary" href="/">{icon("back")}<span>Back to home</span></a></p></div></section>')
    return layout(ctx, title, body, page="error")
