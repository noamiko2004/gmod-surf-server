#!/usr/bin/env python3
"""Web portal for the surf server: public stats plus owner-only admin tools.

Standard library only. Runs behind Caddy on 127.0.0.1. See portal/README.md.
  python3 portal/server.py --repo /home/gmod/surfline --base-url https://example.sslip.io
"""
import argparse
import collections
import hashlib
import ipaddress
import json
import os
import re
import shlex
import sys
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from surfweb import admin, loading, pages, shop, tebex, views  # noqa: E402
from surfweb.actions import Invalid, describe, run_ctl, validate, write_command  # noqa: E402
from surfweb.auth import (FLASH_COOKIE, NEXT_COOKIE, SESSION_COOKIE, SESSION_TTL, Auth, load_secret,  # noqa: E402
                          origin_of, safe_next)
from surfweb.avatars import Avatars  # noqa: E402
from surfweb.conf import Config, read_version  # noqa: E402
from surfweb.fmt import MAPNAME_RE, valid_steamid  # noqa: E402
from surfweb.store import Store, log  # noqa: E402

STATIC_DIR = os.path.join(HERE, "static")
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"}
IMG_HOSTS = ["https://*.steamstatic.com", "https://steamcdn-a.akamaihd.net",
             "https://images.steamusercontent.com", "https://steamuserimages-a.akamaihd.net"]
MAX_BODY = 65536
LIMITS = {"post": (60, 60), "login": (20, 60), "loading": (120, 60)}  # bucket -> (requests, seconds) per client IP
# /loading/<name> -> file in static/ (the in-game loading screen only loads files under /loading, see surfweb/loading.py)
LOADING_FILES = {"loading.css": "loading.css", "loading.js": "loading.js", "logo.svg": "favicon.svg"}


# ---------------------------------------------------------------------- settings

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Surf server web portal")
    ap.add_argument("--repo", required=True, help="repo checkout (holds config.env)")
    ap.add_argument("--config", help="config.env path (default <repo>/config.env)")
    ap.add_argument("--gmod-dir", help="garrysmod dir (default <GMOD_HOME>/server/garrysmod)")
    ap.add_argument("--data-dir", help="gamemode data dir (default <gmod-dir>/data/surfline)")
    ap.add_argument("--db", help="SQLite DB (default <gmod-dir>/sv.db)")
    ap.add_argument("--logs-dir", help="dir with maps.log and update.log (default GMOD_HOME)")
    ap.add_argument("--listen", default="127.0.0.1:8090", help="host:port (port 0 picks a free one)")
    ap.add_argument("--base-url", help="public URL, e.g. https://1-2-3-4.sslip.io")
    ap.add_argument("--public-addr", help="game server address for the Join button, e.g. 1.2.3.4:27015")
    ap.add_argument("--steam-openid", default="https://steamcommunity.com/openid/login")
    ap.add_argument("--ctl", default="sudo -n /usr/local/sbin/surfline-ctl")
    ap.add_argument("--secret-file", help="HMAC secret (default <GMOD_HOME>/.portal_secret)")
    ap.add_argument("--no-avatars", action="store_true", help="do not fetch Steam avatars")
    return ap.parse_args(argv)


def split_listen(s):
    s = s.strip()
    if s.startswith("["):
        host, _, port = s[1:].partition("]:")
    else:
        host, _, port = s.rpartition(":")
    return host or "127.0.0.1", int(port or 8090)


def derive_public_addr(base_url, port):
    host = (urllib.parse.urlsplit(base_url).hostname or "").lower()
    m = re.match(r"^(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})\.(sslip\.io|nip\.io)$", host)
    if m:
        host = ".".join(m.groups()[:4])
    if not host or host in ("localhost",) or host.startswith("127."):
        return ""
    return f"{host}:{port}"


class RateLimiter:
    def __init__(self):
        self.hits = {}
        self.lock = threading.Lock()
        self.calls = 0

    def allow(self, bucket, ip):
        limit, window = LIMITS[bucket]
        now = time.time()
        with self.lock:
            self.calls += 1
            if self.calls % 500 == 0:
                for k in [k for k, dq in self.hits.items() if not dq or now - dq[-1] > window]:
                    del self.hits[k]
            dq = self.hits.setdefault((bucket, ip), collections.deque())
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True


class App:
    def __init__(self, args):
        repo = os.path.abspath(args.repo)
        self.conf = Config(args.config or os.path.join(repo, "config.env"))
        self.version = read_version(repo)
        home = self.conf.gmod_home
        gmod_dir = args.gmod_dir or os.path.join(home, "server", "garrysmod")
        data_dir = args.data_dir or os.path.join(gmod_dir, "data", "surfline")
        db = args.db or os.path.join(gmod_dir, "sv.db")
        self.logs_dir = args.logs_dir or home
        self.listen = split_listen(args.listen)
        if args.base_url:
            self.base_url = args.base_url.rstrip("/")
        else:
            self.base_url = f"http://{self.listen[0]}:{self.listen[1]}"
            log("no --base-url given; Steam login returns to", self.base_url)
        self.origin = origin_of(self.base_url)
        self.public_addr = args.public_addr or derive_public_addr(self.base_url, self.conf.port)
        self.store = Store(data_dir, db, gmod_dir, self.logs_dir)
        secret = load_secret(args.secret_file or os.path.join(home, ".portal_secret"))
        self.auth = Auth(secret, self.base_url, args.steam_openid)
        self.avatars = Avatars(os.path.join(data_dir, "portal", "avatars.json"), enabled=not args.no_avatars)
        self.ctl = shlex.split(args.ctl)
        self.limiter = RateLimiter()
        self._static = {}
        self._static_lock = threading.Lock()
        steam_origin = origin_of(args.steam_openid)
        self.csp = ("default-src 'self'; script-src 'self'; style-src 'self'; "
                    f"img-src 'self' data: {' '.join(IMG_HOSTS)}; connect-src 'self'; font-src 'self'; "
                    f"object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self' {steam_origin}")
        # the loading screen (plain HTTP inside GMOD): own scripts/styles, Steam images, nothing else
        self.loading_csp = ("default-src 'none'; script-src 'self'; style-src 'self'; "
                            f"img-src 'self' data: {' '.join(IMG_HOSTS)}; object-src 'none'; frame-ancestors 'none'; "
                            "base-uri 'none'; form-action 'none'")

    def static_file(self, name):
        path = os.path.join(STATIC_DIR, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        with self._static_lock:
            ent = self._static.get(name)
            if ent and ent[0] == mtime:
                return ent
            with open(path, "rb") as f:
                data = f.read()
            ent = (mtime, data, hashlib.sha256(data).hexdigest()[:10])
            self._static[name] = ent
            return ent

    def static_url(self, name):
        ent = self.static_file(name)
        return f"/static/{name}?v={ent[2]}" if ent else f"/static/{name}"

    def loading_url(self, name):
        """Root-relative URL of a loading screen file, so it keeps the page's scheme (plain HTTP in GMOD)."""
        ent = self.static_file(LOADING_FILES[name])
        return f"/loading/{name}?v={ent[2]}" if ent else f"/loading/{name}"


# ---------------------------------------------------------------------- request plumbing

class Resp:
    def __init__(self, status=200, body=b"", ctype="text/html; charset=utf-8", headers=None, csp=None, cookieless=False):
        self.status = status
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.ctype = ctype
        self.headers = list(headers or [])
        self.csp = csp  # None: the app's default policy
        self.cookieless = cookieless  # never send Set-Cookie (the loading screen)

    def cookie(self, value):
        self.headers.append(("Set-Cookie", value))
        return self


def redirect(location, status=303):
    return Resp(status, b"", "text/plain; charset=utf-8", [("Location", location)])


def json_resp(obj, status=200):
    return Resp(status, json.dumps(obj, separators=(",", ":"), ensure_ascii=False), "application/json; charset=utf-8")


class Ctx:
    def __init__(self, app, method, path, query, cookies, ip, headers):
        self.app = app
        self.method = method
        self.path = path
        self.query = query
        self.cookies = cookies
        self.ip = ip
        self.headers = headers
        self.session = app.auth.parse_session(cookies.get(SESSION_COOKIE))
        self.sid = self.session[0] if self.session else None
        self.is_admin = bool(self.sid and self.sid in app.conf.owners)
        self.csrf = app.auth.csrf_token(self.session)
        self.flash = None
        self.clear_flash = False
        self._my_name = None
        raw = cookies.get(FLASH_COOKIE)
        if raw and method == "GET":
            self.clear_flash = True
            val = app.auth.unpack(raw)
            try:
                kind, msg = json.loads(val) if val else (None, None)
                if isinstance(kind, str) and isinstance(msg, str):
                    self.flash = (kind, msg[:500])
            except (ValueError, TypeError):
                pass

    @property
    def my_name(self):
        if self._my_name is None:
            rows = self.app.store.query("SELECT name FROM surf_players WHERE steamid = ?", (self.sid,))
            name = rows[0]["name"] if rows and rows[0]["name"] else ""
            if not name:
                ent = self.app.store.ranking()["by_sid"].get(self.sid)
                name = ent["name"] if ent else "You"
            self._my_name = str(name)[:64]
        return self._my_name

    def html(self, body, status=200):
        return Resp(status, body)

    def error(self, status, title, msg):
        return Resp(status, views.error_page(self, status, title, msg))

    def flash_redirect(self, location, kind, msg):
        val = self.app.auth.pack(json.dumps([kind, msg[:400]]), 120)
        return redirect(location).cookie(self.app.auth.cookie(FLASH_COOKIE, val, 120))


def parse_cookies(header):
    out = {}
    for part in (header or "").split(";"):
        k, sep, v = part.strip().partition("=")
        if sep and k and k not in out:
            out[k] = v.strip().strip('"')
    return out


def first_values(qs):
    out = {}
    for k, v in urllib.parse.parse_qsl(qs, keep_blank_values=True):
        if k not in out:
            out[k] = v
    return out


# ---------------------------------------------------------------------- routes

def r_home(ctx):
    return ctx.html(pages.home(ctx))


def r_leaderboard(ctx):
    return ctx.html(pages.leaderboard(ctx))


def r_maps(ctx):
    return ctx.html(pages.maps_page(ctx))


def r_map(ctx, name):
    name = urllib.parse.unquote(name)
    if not MAPNAME_RE.match(name):
        return ctx.error(404, "Map not found", "That map name is not valid.")
    html = pages.map_detail(ctx, name)
    if html is None:
        return ctx.error(404, "Map not found", f"There is no map called {name} on this server.")
    return ctx.html(html)


def r_player(ctx, sid):
    if not valid_steamid(sid):
        return ctx.error(404, "Player not found", "That is not a SteamID64.")
    html = pages.player_page(ctx, sid)
    if html is None:
        return ctx.error(404, "Player not found", "This player has not played on the server yet.")
    return ctx.html(html)


def r_shop(ctx):
    return ctx.html(shop.shop_page(ctx))


def r_shop_css(ctx):
    cache = "public, max-age=31536000, immutable" if ctx.query.get("v") else "public, max-age=300"
    return Resp(200, shop.shop_css(ctx.app.store.shop_catalog()), "text/css; charset=utf-8", [("Cache-Control", cache)])


def r_api_status(ctx):
    return json_resp(pages.api_status(ctx))


def r_health(ctx):
    return Resp(200, "ok\n", "text/plain; charset=utf-8")


def r_health_json(ctx):
    """Public server health summary from scripts/health.py (cron, every 10 min). It holds no secrets."""
    try:
        with open(os.path.join(ctx.app.logs_dir, "health.json"), "rb") as f:
            body = f.read(262144)
    except OSError:
        return json_resp({"status": "unknown", "error": "no health report yet (scripts/health.py runs from cron)"}, 404)
    return Resp(200, body, "application/json; charset=utf-8", [("Cache-Control", "no-store")])


def r_robots(ctx):
    return Resp(200, "User-agent: *\nDisallow: /admin\nDisallow: /login\nDisallow: /auth/\n", "text/plain; charset=utf-8")


def r_static(ctx, name):
    if not re.match(r"^[a-z0-9][a-z0-9_.-]*$", name) or os.path.splitext(name)[1] not in STATIC_TYPES:
        return ctx.error(404, "Not found", "No such file.")
    ent = ctx.app.static_file(name)
    if not ent:
        return ctx.error(404, "Not found", "No such file.")
    cache = "public, max-age=31536000, immutable" if ctx.query.get("v") else "public, max-age=300"
    return Resp(200, ent[1], STATIC_TYPES[os.path.splitext(name)[1]], [("Cache-Control", cache)])


def r_favicon(ctx):
    return r_static(ctx, "favicon.svg")


def r_loading(ctx):
    """In-game loading screen (sv_loadingurl). Public, cookieless, served on plain HTTP too."""
    sid, mapname = loading.params(ctx.query)
    light = not ctx.app.limiter.allow("loading", ctx.ip)  # over the limit: a page without status or DB reads
    try:
        body = loading.page(ctx, sid, mapname, light=light)
    except Exception:  # every joining player sees this page: fall back to the plain version, never an error page
        traceback.print_exc()
        body = loading.page(ctx, light=True)
    return Resp(429 if light else 200, body, csp=ctx.app.loading_csp, cookieless=True)


def r_loading_file(ctx, name):
    ent = ctx.app.static_file(LOADING_FILES[name]) if name in LOADING_FILES else None
    if not ent:
        return Resp(404, "Not found\n", "text/plain; charset=utf-8", csp=ctx.app.loading_csp, cookieless=True)
    cache = "public, max-age=31536000, immutable" if ctx.query.get("v") else "public, max-age=300"
    return Resp(200, ent[1], STATIC_TYPES[os.path.splitext(name)[1]], [("Cache-Control", cache)],
                csp=ctx.app.loading_csp, cookieless=True)


def r_login(ctx):
    if not ctx.app.limiter.allow("login", ctx.ip):
        return ctx.error(429, "Slow down", "Too many sign-in attempts. Wait a minute and try again.")
    nxt = safe_next(ctx.query.get("next", "/"))
    if ctx.sid:
        return redirect(nxt)
    auth = ctx.app.auth
    return redirect(auth.login_url(), 302).cookie(auth.cookie(NEXT_COOKIE, auth.pack(nxt, 600), 600))


def r_auth(ctx):
    app = ctx.app
    if not app.limiter.allow("login", ctx.ip):
        return ctx.error(429, "Slow down", "Too many sign-in attempts. Wait a minute and try again.")
    sid, err = app.auth.verify(ctx.query)
    if not sid:
        return ctx.error(403, "Sign-in failed", err)
    nxt = safe_next(app.auth.unpack(ctx.cookies.get(NEXT_COOKIE, "")) or "/")
    resp = redirect(nxt)
    resp.cookie(app.auth.cookie(SESSION_COOKIE, app.auth.make_session(sid), SESSION_TTL))
    resp.cookie(app.auth.cookie(NEXT_COOKIE, "", 0))
    if sid in app.conf.owners:
        app.store.append_audit({"time": int(time.time()), "by": sid, "ip": ctx.ip, "kind": "login"})
    return resp


def admin_only(fn):
    def wrapped(ctx, *a):
        if not ctx.sid:
            target = ctx.path + ("?" + urllib.parse.urlencode(ctx.query) if ctx.query else "")
            return redirect("/login?next=" + urllib.parse.quote(target, safe=""), 302)
        if not ctx.is_admin:
            return ctx.error(403, "Owners only", "This area is for the server owner. You are signed in, but your SteamID is not in OWNER_STEAMIDS.")
        return fn(ctx, *a)
    return wrapped


@admin_only
def r_admin(ctx):
    return ctx.html(admin.dashboard(ctx))


@admin_only
def r_admin_players(ctx):
    return ctx.html(admin.players(ctx))


@admin_only
def r_admin_bans(ctx):
    return ctx.html(admin.bans(ctx))


@admin_only
def r_admin_vip(ctx):
    return ctx.html(admin.vip(ctx))


@admin_only
def r_admin_shop(ctx):
    return ctx.html(admin.shop_admin(ctx))


@admin_only
def r_admin_maps(ctx):
    return ctx.html(admin.maps_admin(ctx))


@admin_only
def r_admin_logs(ctx):
    return ctx.html(admin.logs(ctx))


# POST handlers get (ctx, form); CSRF, origin and rate limits are checked before.

def p_logout(ctx, form):
    return redirect("/").cookie(ctx.app.auth.cookie(SESSION_COOKIE, "", 0))


def admin_back(form):
    back = safe_next(form.get("back", "/admin"))
    return back if back == "/admin" or back.startswith("/admin/") or back.startswith("/admin?") else "/admin"


def p_admin_cmd(ctx, form):
    app = ctx.app
    back = admin_back(form)
    st = app.store.status()
    known = set(app.store.installed_maps()) | {m["name"] for m in st["maps"]}
    try:
        cmd = validate(form, known)
    except Invalid as ex:
        return ctx.flash_redirect(back, "err", str(ex))
    cmd["by"] = ctx.sid
    try:
        cid = write_command(app.store.portal_dir, cmd)
    except OSError as ex:
        log("cannot write command:", ex)
        return ctx.flash_redirect(back, "err", "Could not queue the command (the data folder is not writable).")
    app.store.append_audit({"time": int(time.time()), "by": ctx.sid, "ip": ctx.ip, "kind": "cmd", "id": cid, "cmd": cmd})
    if st["online"]:
        msg = f"Sent: {describe(cmd)}. The server runs it within a few seconds."
    else:
        msg = f"Queued: {describe(cmd)}. The game server is offline, so it runs when the server is back."
    return ctx.flash_redirect(back, "ok", msg)


def p_admin_ctl(ctx, form):
    app = ctx.app
    op = form.get("op", "")
    if op not in ("restart", "update"):
        return ctx.flash_redirect("/admin", "err", "Unknown server operation.")
    ok, out = run_ctl(app.ctl, op)
    app.store.append_audit({"time": int(time.time()), "by": ctx.sid, "ip": ctx.ip, "kind": "ctl", "op": op,
                            "ok": ok, "out": out.strip()[-400:]})
    if not ok:
        return ctx.flash_redirect("/admin", "err", f"{op.capitalize()} failed: {out.strip()[-300:]}")
    if op == "restart":
        return ctx.flash_redirect("/admin", "ok", "Restarting the game server. It is back in about a minute.")
    return ctx.flash_redirect("/admin", "ok", "Update started in the background. Follow it under Logs > update.log.")


GET_ROUTES = [
    (re.compile(r"^/$"), r_home),
    (re.compile(r"^/leaderboard/?$"), r_leaderboard),
    (re.compile(r"^/maps/?$"), r_maps),
    (re.compile(r"^/maps/([^/]{1,200})$"), r_map),
    (re.compile(r"^/players/([0-9]{1,20})/?$"), r_player),
    (re.compile(r"^/shop/?$"), r_shop),
    (re.compile(r"^/shop\.css$"), r_shop_css),
    (re.compile(r"^/api/status$"), r_api_status),
    (re.compile(r"^/healthz$"), r_health),
    (re.compile(r"^/health\.json$"), r_health_json),
    (re.compile(r"^/robots\.txt$"), r_robots),
    (re.compile(r"^/favicon\.ico$"), r_favicon),
    (re.compile(r"^/static/([^/]{1,64})$"), r_static),
    (re.compile(r"^/loading$"), r_loading),
    (re.compile(r"^/loading/([^/]{1,64})$"), r_loading_file),
    (re.compile(r"^/login$"), r_login),
    (re.compile(r"^/auth/steam$"), r_auth),
    (re.compile(r"^/admin/?$"), r_admin),
    (re.compile(r"^/admin/players$"), r_admin_players),
    (re.compile(r"^/admin/bans$"), r_admin_bans),
    (re.compile(r"^/admin/vip$"), r_admin_vip),
    (re.compile(r"^/admin/maps$"), r_admin_maps),
    (re.compile(r"^/admin/logs$"), r_admin_logs),
    (re.compile(r"^/admin/shop$"), r_admin_shop),
]
POST_ROUTES = {"/logout": (p_logout, False), "/admin/cmd": (p_admin_cmd, True), "/admin/ctl": (p_admin_ctl, True)}


class Handler(BaseHTTPRequestHandler):
    server_version = "SurfPortal/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 30
    app = None  # set in main()

    def log_message(self, fmt, *args):
        sys.stderr.write("[portal] %s %s\n" % (getattr(self, "_ip", None) or self.client_address[0], fmt % args))

    def log_request(self, code="-", size="-"):
        # the live page polls /api/status every 5 s; keep the journal readable
        path = (self.path or "").split("?")[0]
        if str(code).startswith(("2", "3")) and (path == "/api/status" or path.startswith(("/static/", "/loading/")) or path == "/healthz"):
            return
        super().log_request(code, size)

    def client_ip(self):
        peer = self.client_address[0]
        if peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            xff = self.headers.get("X-Forwarded-For", "")
            if xff:
                last = xff.split(",")[-1].strip()
                try:
                    return str(ipaddress.ip_address(last))
                except ValueError:
                    pass
        return peer

    def do_GET(self):
        self.handle_any("GET")

    def do_HEAD(self):
        self.handle_any("HEAD")

    def do_POST(self):
        self.handle_any("POST")

    def handle_any(self, method):
        app = self.app
        self._ip = self.client_ip()
        try:
            url = urllib.parse.urlsplit(self.path)
            path = url.path or "/"
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/") or "/"
            query = first_values(url.query)
            ctx = Ctx(app, "GET" if method == "HEAD" else method, path, query,
                      parse_cookies(self.headers.get("Cookie")), self._ip, self.headers)
            if method == "POST":
                resp = self.handle_post(ctx)
            else:
                resp = None
                for rx, fn in GET_ROUTES:
                    m = rx.match(path)
                    if m:
                        resp = fn(ctx, *m.groups())
                        break
                if resp is None:
                    if path in POST_ROUTES:
                        resp = ctx.error(405, "Method not allowed", "Use the buttons on the site for this.")
                    else:
                        resp = ctx.error(404, "Page not found", "That page does not exist. It may have moved.")
            if ctx.clear_flash and not resp.cookieless and resp.status == 200 and resp.ctype.startswith("text/html"):
                resp.cookie(app.auth.cookie(FLASH_COOKIE, "", 0))
        except Exception:
            traceback.print_exc()
            resp = Resp(500, "<!doctype html><title>Error</title><p>Something went wrong. Try again in a moment.</p>")
        self.send(resp, head=method == "HEAD")

    def handle_post(self, ctx):
        app = self.app
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            return ctx.error(413, "Too large", "That request is too large.")
        raw = self.rfile.read(length) if length else b""  # always drain the body (keep-alive)
        route = POST_ROUTES.get(ctx.path)
        if not route:
            return ctx.error(404, "Page not found", "That page does not exist.")
        if not app.limiter.allow("post", ctx.ip):
            return ctx.error(429, "Slow down", "Too many requests. Wait a minute and try again.")
        origin = self.headers.get("Origin")
        if origin is not None and origin != app.origin:
            return ctx.error(403, "Forbidden", "Cross-site request blocked.")
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype not in ("application/x-www-form-urlencoded", ""):
            return ctx.error(400, "Bad request", "Unsupported form encoding.")
        form = first_values(raw.decode("utf-8", "replace"))
        if not app.auth.check_csrf(ctx.session, form.get("csrf")):
            return ctx.error(403, "Forbidden", "Your session expired or the form is stale. Reload the page and try again.")
        fn, needs_admin = route
        if needs_admin and not ctx.is_admin:
            return ctx.error(403, "Owners only", "This action is for the server owner.")
        return fn(ctx, form)

    def send(self, resp, head=False):
        try:
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.ctype)
            self.send_header("Content-Length", str(len(resp.body)))
            self.send_header("Content-Security-Policy", resp.csp or self.app.csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            if not any(k == "Cache-Control" for k, _ in resp.headers):
                self.send_header("Cache-Control", "no-store")
            for k, v in resp.headers:
                if resp.cookieless and k.lower() == "set-cookie":
                    continue
                self.send_header(k, v)
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            if not head:
                self.wfile.write(resp.body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler):
        if ":" in addr[0]:
            import socket
            self.address_family = socket.AF_INET6
        super().__init__(addr, handler)


def main(argv=None):
    args = parse_args(argv)
    app = App(args)
    Handler.app = app
    tebex.start(app.conf, app.store.portal_dir)  # paid store; idle until TEBEX_SECRET is set
    srv = Server(app.listen, Handler)
    host, port = srv.server_address[:2]
    print(f"[portal] listening on http://{host}:{port} (base {app.base_url})", flush=True)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
