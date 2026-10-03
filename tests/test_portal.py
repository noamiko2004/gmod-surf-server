"""Offline test of the web portal (portal/server.py).

Builds a fake server tree (config.env, garrysmod dir, data files, SQLite DB with
malicious names), a fake Steam OpenID provider and a fake ctl script, starts the
portal on a free port and checks pages, escaping, points, login, CSRF, admin
commands and the ctl. Run: python3 tests/test_portal.py
"""
import http.client
import json
import os
import re
import secrets
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL = os.path.join(ROOT, "portal")
sys.path.insert(0, PORTAL)
from surfweb import conf as C  # noqa: E402
from surfweb import fmt as F  # noqa: E402
from surfweb.store import Store  # noqa: E402

fails = []


def check(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        fails.append(m)


OWNER = "76561198000000001"
OTHER = "76561198000000002"
A, B, CC, D, E = (f"765611980000000{n}" for n in (11, 12, 13, 14, 15))
FIO, GUS = "76561198000000016", "76561198000000017"  # style runners
XSS1 = "<script>alert(1)</script>"
XSS2 = '"><img src=x onerror=alert(1)>'
RAW_BAD = [XSS1, "<img src=x onerror=alert(1)>", "<b>bold</b>", "<i>x</i>", "javascript:alert(1)", "evil.example.com"]
BASE = "https://portal.test"
NOW = int(time.time())

# ------------------------------------------------------------------ unit checks
check(F.fmt_time(12.345) == "0:12.345", f"fmt_time 12.345 ({F.fmt_time(12.345)})")
check(F.fmt_time(83.4567) == "1:23.457", f"fmt_time 83.4567 ({F.fmt_time(83.4567)})")
check(F.fmt_time(3723.5) == "1:02:03.500", f"fmt_time past an hour ({F.fmt_time(3723.5)})")
check(F.fmt_time(0) == "-" and F.fmt_time(False) == "-", "fmt_time of no time")
check([F.points_for(p, False) for p in (1, 2, 3, 10, 11, 12)] == [110, 55, 50, 15, 10, 10], "points per position")
check([F.points_for(p, True) for p in (1, 2, 3)] == [55, 27, 25], "bonus points are half, floored")
# styles (v4): halved for a style other than Normal, after the bonus halving
check(F.points_for(1, True, True) == 27, "pos 1 on a bonus with a style = floor(floor(110/2)/2) = 27")
check([F.points_for(p, False, True) for p in (1, 2, 3, 11)] == [55, 27, 25, 5], "style points are half, floored")
check([F.points_for(p, True, True) for p in (1, 2, 3, 11)] == [27, 13, 12, 2], "bonus on a style is halved twice")
check([F.key_points(1, k) for k in ("surf_kitsune", "surf_kitsune@sw", "surf_kitsune#b2", "surf_kitsune#b2@lg")] == [110, 55, 55, 27],
      "points by key: main, style, bonus, bonus with a style")
check(F.parse_key("surf_kitsune") == ("surf_kitsune", 0, "n") and F.parse_key("surf_kitsune@sw") == ("surf_kitsune", 0, "sw")
      and F.parse_key("surf_kitsune#b2") == ("surf_kitsune", 2, "n") and F.parse_key("surf_kitsune#b2@lg") == ("surf_kitsune", 2, "lg"),
      "time keys parse into map, track and style")
check(F.parse_key("surf_x@zz") == ("surf_x", 0, "zz") and F.style_label("zz") == "zz" and F.parse_key(None) == ("", 0, "n")
      and F.parse_key("surf_x#bx@") == ("surf_x", 0, "n"), "unknown style ids are kept (labelled by id), junk does not crash")
check(F.track_of("surf_x#b2@sw") == ("surf_x", 2) and F.make_key("surf_x", 2, "sw") == "surf_x#b2@sw"
      and F.make_key("surf_x", 0, "n") == "surf_x" and F.make_key("surf_x", 3) == "surf_x#b3", "make_key and track_of with styles")
check([F.style_label(s) for s, _ in F.STYLES] == ["Normal", "Sideways", "Half-Sideways", "W-Only", "Low Gravity"]
      and sorted(["zz", "lg", "n", "sw"], key=F.style_order) == ["n", "sw", "lg", "zz"], "style names and display order")
good_keys = ["surf_x", "surf_x#b2", "surf_x@sw", "surf_x#b2@sw", "surf_x@hsw", "surf_x@w", "surf_x#b10@lg", "surf_x@n"]
bad_keys = ["surf_x@zz", "surf_x@sw#b2", "surf_x@", "surf_x@SW", "surf_x#b2@sw@lg", "surf_x#b@sw", "surf_x@sw@", "x@sw"]
check(all(F.MAPKEY_RE.match(k) for k in good_keys) and not any(F.MAPKEY_RE.match(k) for k in bad_keys),
      f"MAPKEY_RE: track then optional known style ({[k for k in good_keys if not F.MAPKEY_RE.match(k)]}, {[k for k in bad_keys if F.MAPKEY_RE.match(k)]})")
check(F.fmt_sync(78.24) == "78.2%" and F.fmt_sync(None) == "-" and F.fmt_sync(False) == "-" and F.fmt_sync(0) == "0.0%",
      "sync format")
check(F.fmt_speed(2310.4) == "2,310 u/s" and F.fmt_speed(None) == "-" and F.fmt_speed(float("nan")) == "-" and F.fmt_speed("x") == "-",
      "speed format")
check(F.e(XSS2) == "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;", "escape helper")
check(F.clean_text("Hi\x07 there\x1b‮!") == "Hi there!", "control characters stripped")
check(F.to_int(24.0) == 24 and F.to_int(False) == 0 and F.to_float("x") == 0.0, "GMOD JSON number coercion")
check(F.as_list({"2": "b", "1": "a"}) == ["a", "b"] and F.as_list([]) == [] and F.as_list(False) == [], "Lua arrays as lists")
from surfweb.avatars import AV_RE, safe_avatar_url  # noqa: E402
xml = "<profile><avatarMedium>\n<![CDATA[https://avatars.steamstatic.com/ab12_medium.jpg]]>\n</avatarMedium></profile>"
m = AV_RE.search(xml)
check(m and safe_avatar_url(m.group(1)) == "https://avatars.steamstatic.com/ab12_medium.jpg", "avatar URL parsed from profile XML")
check(safe_avatar_url("https://evilsteamstatic.com/a.jpg") == "" and safe_avatar_url("https://x.steamstatic.com:bad/") == "",
      "avatar hosts restricted to Steam")

tmp = tempfile.mkdtemp(prefix="portal-test-")
envf = os.path.join(tmp, "parse.env")
with open(envf, "w") as f:
    f.write('# comment\nA="a # b"\nB=val # trailing\nexport C=\'x y\'\nD=\nE="say \\"hi\\""\n'
            'OWNER_STEAMIDS="76561198000000001, 76561198000000002 76561198000000003,bad"\n')
env = C.parse_env(envf)
check(env.get("A") == "a # b" and env.get("B") == "val" and env.get("C") == "x y" and env.get("D") == ""
      and env.get("E") == 'say "hi"', f"config.env parsing ({env})")
check(C.parse_owners(env["OWNER_STEAMIDS"]) == {"76561198000000001", "76561198000000002", "76561198000000003"}, "owner list parsing")
cfg = C.Config(envf, interval=0)
with open(envf, "a") as f:
    f.write('OWNER_STEAMIDS="76561198000000009"\n')
check(cfg.owners == {"76561198000000009"}, "config re-read picks up owner changes")

# ------------------------------------------------------------------ fake server tree
repo = os.path.join(tmp, "repo")
gm = os.path.join(tmp, "garrysmod")
data = os.path.join(gm, "data", "surfline")
logs = os.path.join(tmp, "logs")
for d in (repo, os.path.join(gm, "maps"), os.path.join(data, "portal"), os.path.join(data, "zones"), logs):
    os.makedirs(d)
with open(os.path.join(repo, "config.env"), "w") as f:
    f.write(f'# test config\nSERVER_NAME="Test Surf | <b>bold</b>"\nBRAND_NAME=\'TestSurf\'\nOWNER_STEAMIDS="{OWNER}"\n'
            'PORT=27015\nDISCORD_URL="https://discord.gg/testsurf"\nSTORE_URL="javascript:alert(1)"\nGMOD_HOME=/nonexistent\n')
for m in ("surf_alpha", "surf_beta", "surf_gamma", "surf_evil<b>"):
    open(os.path.join(gm, "maps", m + ".bsp"), "wb").write(b"VBSP")
open(os.path.join(data, "zones", "surf_alpha.json"), "w").write("[]")
with open(os.path.join(data, "tiers.txt"), "w") as f:
    f.write("# tiers\nsurf_alpha 1\nsurf_beta 3\n")
with open(os.path.join(data, "mappers.txt"), "w") as f:
    f.write("surf_alpha Alpha Mapper <i>x</i>\n")
json.dump({"generated": NOW - 600,
           "installed": [{"map": "surf_alpha", "wsid": "123456", "title": "Alpha", "zoned": True,
                          "preview": "https://images.steamusercontent.com/ugc/1/alpha.jpg"},
                         {"map": "surf_beta", "wsid": 777.0, "title": "Beta", "zoned": False,
                          "preview": "https://evil.example.com/x.jpg"},
                         {"map": "surf_gamma", "wsid": "javascript:alert(1)", "title": XSS1, "zoned": False,
                          "preview": "https://images.steamusercontent.com:bad/x.jpg"}],
           "failed": [{"wsid": "999", "title": XSS1, "error": "timed out <b>bold</b>"}],
           "not_found": 4.0}, open(os.path.join(data, "maps_report.json"), "w"))
open(os.path.join(logs, "maps.log"), "w").write("".join(f"maps line {i}\n" for i in range(300)) + XSS1 + "\n")
open(os.path.join(logs, "update.log"), "w").write("update started\nupdate finished OK\n")
json.dump({A: {"url": "https://avatars.steamstatic.com/abc_medium.jpg", "t": NOW},
           CC: {"url": "https://evil.example.com/a.jpg", "t": NOW}},
          open(os.path.join(data, "portal", "avatars.json"), "w"))


def status(updated=None, **over):
    s = {"updated": float(updated if updated is not None else time.time()), "hostname": "SURF | test", "brand": "TestSurf",
         "map": "surf_alpha", "tier": 1.0, "mapper": "", "maxplayers": 24.0, "timeleft": 1800.0, "map_started": NOW - 100.0,
         "wr": {"time": 10.0, "name": XSS2}, "replay": False,
         "players": [{"steamid": A, "name": "Alice", "points": 137.0, "title": "Surfer", "rank": 2.0, "state": "running",
                      "track": 0.0, "style": "hsw", "time": 12.3, "pb": 10.0, "vip": True, "admin": False, "ping": 40.0,
                      "connected": 360.0, "ip": "203.0.113.7:27005", "address": "203.0.113.7"},
                     {"steamid": B, "name": XSS1, "points": 110.0, "title": "Rookie", "rank": 3.0, "state": "finished",
                      "track": 1.0, "style": "zz", "time": 5.0, "pb": False, "vip": False, "admin": True, "ping": 80.0,
                      "connected": 60.0},
                     {"steamid": "BOT", "name": XSS2, "points": 0, "title": [], "rank": 0, "state": "weird", "track": 0,
                      "time": 0, "pb": 0, "vip": False, "admin": False, "ping": 0, "connected": 0}],
         "maps": [{"name": "surf_alpha", "tier": 1.0, "zoned": True}, {"name": "surf_beta", "tier": 3.0, "zoned": True},
                  {"name": "surf_gamma", "tier": 0, "zoned": False}, {"name": "surf_delta", "tier": 2.0, "zoned": False},
                  {"name": "<script>", "tier": 1, "zoned": True}]}
    s.update(over)
    return s


STATUS = os.path.join(data, "portal", "status.json")


def write_status(obj):
    with open(STATUS, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))


write_status(status())

db = sqlite3.connect(os.path.join(gm, "sv.db"))
db.executescript("""
CREATE TABLE surf_times(map TEXT, steamid TEXT, name TEXT, time REAL, date INTEGER, completions INTEGER, splits TEXT,
                        jumps INTEGER, strafes INTEGER, sync REAL, avgspeed REAL, maxspeed REAL);
CREATE TABLE surf_players(steamid TEXT PRIMARY KEY, name TEXT, trail TEXT, autohop INTEGER, playtime INTEGER, firstseen INTEGER, lastseen INTEGER);
CREATE TABLE surf_vip(steamid TEXT PRIMARY KEY, expires INTEGER);
CREATE TABLE surf_records(id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT, steamid TEXT, name TEXT, time REAL, prev_time REAL, prev_name TEXT, date INTEGER);
CREATE TABLE surf_bans(steamid TEXT PRIMARY KEY, name TEXT, reason TEXT, admin TEXT, created INTEGER, expires INTEGER);
CREATE TABLE surf_zones(map TEXT, ztype TEXT, x1 REAL, y1 REAL, z1 REAL, x2 REAL, y2 REAL, z2 REAL);
""")
times = [("surf_alpha", A, 10.0), ("surf_alpha", B, 11.0), ("surf_alpha", CC, 12.0),
         ("surf_alpha#b1", B, 5.0), ("surf_alpha#b1", A, 6.0),
         ("surf_beta", CC, 20.0), ("surf_beta#b2", D, 30.0), ("surf_gamma", E, 40.0),
         # v4 styles: each key is its own leaderboard; "zz" is a style this portal does not know
         ("surf_alpha@sw", FIO, 14.0), ("surf_alpha@sw", GUS, 15.0), ("surf_alpha#b1@lg", FIO, 7.0),
         ("surf_alpha#b1@lg", GUS, 8.0), ("surf_alpha@zz", GUS, 50.0), ("surf_gamma", FIO, 45.0)]
# strafe stats (jumps, strafes, sync, avgspeed, maxspeed); every other row is NULL like pre-v4 times
run_stats = {("surf_alpha", A): (31, 58, 78.24, 1820.2, 3456.6), ("surf_alpha@sw", FIO): (12, 40, None, 1500.0, 2310.4)}
names = {A: "Alice", B: XSS1, CC: XSS2, D: "Dave", E: "Eve", FIO: "Fiona", GUS: "Gus"}
for key, sid, t in times:
    db.execute("INSERT INTO surf_times VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (key, sid, names[sid], t, NOW - 3600, 2, "[]") + run_stats.get((key, sid), (None,) * 5))
for sid, nm in list(names.items()) + [(OWNER, "Owner"), (OTHER, "Other")]:
    db.execute("INSERT INTO surf_players VALUES (?,?,?,?,?,?,?)", (sid, nm, "", 1, 7200, NOW - 86400 * 10, NOW - 300))
db.execute("INSERT INTO surf_vip VALUES (?, 0)", (A,))
db.execute("INSERT INTO surf_vip VALUES (?, ?)", (D, NOW - 10))  # expired
db.execute("INSERT INTO surf_records(map, steamid, name, time, prev_time, prev_name, date) VALUES ('surf_alpha', ?, ?, 10.0, 10.512, ?, ?)",
           (A, "Alice", XSS2, NOW - 60))
db.execute("INSERT INTO surf_records(map, steamid, name, time, prev_time, prev_name, date) VALUES ('surf_alpha#b1', ?, ?, 5.0, 0, '', ?)",
           (B, XSS1, NOW - 30))
db.execute("INSERT INTO surf_records(map, steamid, name, time, prev_time, prev_name, date) VALUES ('surf_alpha@sw', ?, 'Fiona', 14.0, 0, '', ?)",
           (FIO, NOW - 20))
db.execute("INSERT INTO surf_bans VALUES (?,?,?,?,?,?)", ("76561198000000099", XSS2, XSS1, OWNER, NOW - 100, 0))
db.execute("INSERT INTO surf_zones VALUES ('surf_beta','start',0,0,0,1,1,1)")
db.commit()
db.close()

# expected ranking: C 50+110=160, A 110+27=137, B 55+55=110, E 110 (tie with B, B's steamid sorts first), D 55,
# Fiona 55 (sw #1) + 27 (b1@lg #1) + 55 (gamma #2) = 137 (tie with A, A sorts first),
# Gus 27 (sw #2) + 13 (b1@lg #2: 55 -> 27 -> 13) + 55 (unknown style zz #1, halved like any style) = 95
EXPECT = [(CC, 160), (A, 137), (FIO, 137), (B, 110), (E, 110), (GUS, 95), (D, 55)]
st = Store(data, os.path.join(gm, "sv.db"), gm, logs)
rk = st.ranking()
got = [(p["sid"], p["points"]) for p in rk["players"]]
check(got == EXPECT, f"points and order match the formula ({got})")
check([p["pos"] for p in rk["players"]] == list(range(1, len(EXPECT) + 1)), "ranks are sequential")
check(F.title_name(160) == "Surfer" and F.title_name(110) == "Rookie" and F.title_name(2500) == "Legend", "titles by points")
check(rk["by_sid"][A]["records"] == 1 and rk["by_sid"][A]["finished"] == 1 and rk["by_sid"][A]["bonuses"] == 1, "records/maps counted")
fio = rk["by_sid"][FIO]
check(fio["records"] == 2 and fio["finished"] == 2 and fio["bonuses"] == 1, f"style runs count as maps/bonuses finished and records ({fio})")
check(rk["variants"]["surf_alpha"] == {0: {"n": "surf_alpha", "sw": "surf_alpha@sw", "zz": "surf_alpha@zz"},
                                       1: {"n": "surf_alpha#b1", "lg": "surf_alpha#b1@lg"}}, "leaderboards indexed by map, track and style")
row_a = rk["keys"]["surf_alpha"][0]
check(row_a["sid"] == A and row_a["sync"] == 78.24 and row_a["maxspeed"] == 3456.6 and row_a["jumps"] == 31
      and rk["keys"]["surf_alpha"][1]["sync"] is None, "strafe stats read, NULL stays None")
missing = Store(os.path.join(tmp, "nodata"), os.path.join(tmp, "missing.db"), os.path.join(tmp, "nogm"), tmp)
check(missing.ranking()["players"] == [] and missing.status()["online"] is False and missing.bans() == [], "missing DB and files mean empty")
old_root = os.path.join(tmp, "old")  # a pre-v4 server: surf_times without the strafe stat columns
old_gm = os.path.join(old_root, "gm")
os.makedirs(os.path.join(old_gm, "maps"))
os.makedirs(os.path.join(old_root, "repo"))
open(os.path.join(old_gm, "maps", "surf_old.bsp"), "wb").write(b"VBSP")
odb = sqlite3.connect(os.path.join(old_gm, "sv.db"))
odb.execute("CREATE TABLE surf_times(map TEXT, steamid TEXT, name TEXT, time REAL, date INTEGER, completions INTEGER, splits TEXT)")
odb.executemany("INSERT INTO surf_times VALUES (?,?,?,?,?,?,?)", [("surf_old", A, "Alice", 10.0, NOW - 60, 1, "[]"),
                                                                  ("surf_old@sw", B, "Bob", 12.0, NOW - 60, 1, "[]")])
odb.commit()
odb.close()
ork = Store(os.path.join(old_gm, "data", "surfline"), os.path.join(old_gm, "sv.db"), old_gm, old_root).ranking()
check([(p["sid"], p["points"]) for p in ork["players"]] == [(A, 110), (B, 55)]
      and ork["keys"]["surf_old"][0]["sync"] is None and ork["keys"]["surf_old@sw"][0]["maxspeed"] is None,
      "DB without the stat columns: times and points read, stats None")
tiny = os.path.join(tmp, "tiny.db")  # the oldest schema: no name, date or completions either
tdb = sqlite3.connect(tiny)
tdb.execute("CREATE TABLE surf_times(map TEXT, steamid TEXT, time REAL)")
tdb.executemany("INSERT INTO surf_times VALUES (?,?,?)", [("surf_t#b1@w", A, 3.0), ("surf_t#b1@w", B, 4.0)])
tdb.commit()
tdb.close()
trk = Store(os.path.join(tmp, "nodata"), tiny, os.path.join(tmp, "nogm"), tmp).ranking()
check([(p["sid"], p["points"]) for p in trk["players"]] == [(A, 27), (B, 13)] and trk["finishes"] == 2,
      f"oldest schema still ranks ({[(p['sid'], p['points']) for p in trk['players']]})")

# ------------------------------------------------------------------ fake ctl
ctl_log = os.path.join(tmp, "ctl.log")
ctl = os.path.join(tmp, "fakectl.sh")
with open(ctl, "w") as f:
    f.write(f'#!/bin/sh\necho "$@" >> "{ctl_log}"\ncase "$1" in\n'
            ' status) printf "active=active\\nsince=Sat 2026-10-03 05:00:00 UTC\\nupdate_running=no\\n";;\n'
            ' restart|update) echo started;;\n'
            ' logs) echo "journal is broken" >&2; exit 3;;\n'
            ' *) exit 2;;\nesac\n')
os.chmod(ctl, 0o755)

# ------------------------------------------------------------------ fake Steam OpenID
issued = {}


class FakeSteam(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        sid = q.get("as", "")
        claimed = "https://steamcommunity.com/openid/id/" + sid
        p = {"openid.ns": "http://specs.openid.net/auth/2.0", "openid.mode": "id_res", "openid.op_endpoint": ENDPOINT,
             "openid.claimed_id": claimed, "openid.identity": claimed, "openid.return_to": q.get("openid.return_to", ""),
             "openid.response_nonce": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + secrets.token_hex(4),
             "openid.assoc_handle": "1234567890",
             "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"}
        p["openid.sig"] = secrets.token_urlsafe(16)
        issued[p["openid.sig"]] = dict(p)
        self.send_response(302)
        self.send_header("Location", p["openid.return_to"] + "?" + urllib.parse.urlencode(p))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        q = dict(urllib.parse.parse_qsl(body))
        ok = q.get("openid.mode") == "check_authentication"
        orig = issued.get(q.get("openid.sig"))
        ok = ok and orig is not None and all(q.get("openid." + k) == orig.get("openid." + k)
                                             for k in orig["openid.signed"].split(","))
        out = ("ns:http://specs.openid.net/auth/2.0\nis_valid:%s\n" % ("true" if ok else "false")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


steam = ThreadingHTTPServer(("127.0.0.1", 0), FakeSteam)
ENDPOINT = f"http://127.0.0.1:{steam.server_address[1]}/openid/login"
threading.Thread(target=steam.serve_forever, daemon=True).start()


# ------------------------------------------------------------------ start the portal
def start_portal(extra, logname):
    logf = open(os.path.join(tmp, logname), "w")
    proc = subprocess.Popen([sys.executable, os.path.join(PORTAL, "server.py"), "--listen", "127.0.0.1:0", "--no-avatars"] + extra,
                            stdout=subprocess.PIPE, stderr=logf, text=True)
    port = None
    deadline = time.time() + 15
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        m = re.search(r"listening on http://[^:]+:(\d+)", line)
        if m:
            port = int(m.group(1))
            break
    threading.Thread(target=lambda: [None for _ in proc.stdout], daemon=True).start()
    return proc, port


secret_file = os.path.join(tmp, "secret", "portal_secret")
proc, PORT = start_portal(["--repo", repo, "--gmod-dir", gm, "--logs-dir", logs, "--base-url", BASE,
                           "--public-addr", "1.2.3.4:27015", "--steam-openid", ENDPOINT, "--ctl", ctl,
                           "--secret-file", secret_file], "portal.log")
check(PORT is not None, f"portal started (port {PORT})")
if PORT is None:
    print(open(os.path.join(tmp, "portal.log")).read())
    print(f"\n{len(fails)} failure(s)")
    sys.exit(1)
check(os.path.exists(secret_file) and stat.S_IMODE(os.stat(secret_file).st_mode) == 0o600
      and re.match(r"^[0-9a-f]{64}$", open(secret_file).read().strip()) is not None, "secret file created, 64 hex, mode 0600")


class Resp:
    def __init__(self, r, body):
        self.status = r.status
        self.headers = {k.lower(): v for k, v in r.getheaders()}
        self.cookies = r.msg.get_all("Set-Cookie") or []
        self.body = body.decode("utf-8", "replace")

    @property
    def location(self):
        return self.headers.get("location", "")

    def cookie(self, name):
        for c in self.cookies:
            if c.startswith(name + "="):
                return c.split(";")[0].split("=", 1)[1], c
        return None, None


def req(method, path, cookies=None, form=None, ip="10.0.0.1", headers=None, port=None):
    conn = http.client.HTTPConnection("127.0.0.1", port or PORT, timeout=15)
    h = {"X-Forwarded-For": "198.51.100.9, " + ip}
    if cookies:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form)
        h["Content-Type"] = "application/x-www-form-urlencoded"
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    out = Resp(r, r.read())
    conn.close()
    return out


def get(path, **kw):
    return req("GET", path, **kw)


def no_raw(body):
    return [b for b in RAW_BAD if b in body]


# ------------------------------------------------------------------ public pages
home = get("/")
check(home.status == 200 and "TestSurf" in home.body and "Test Surf | &lt;b&gt;bold&lt;/b&gt;" in home.body, "home: brand and escaped server name")
check('href="steam://connect/1.2.3.4:27015"' in home.body and 'data-copy="1.2.3.4:27015"' in home.body, "home: join and copy-IP buttons")
check("Alice" in home.body and "Running" in home.body and "Finished" in home.body and "Bonus 1" in home.body, "home: live players and what they do")
check("&lt;script&gt;alert(1)&lt;/script&gt;" in home.body and "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;" in home.body, "home: malicious names shown escaped")
check("set the record on" in home.body and "(-0.512)" in home.body, "home: recent records with improvement")
live = home.body.split('<ul class="plist js-plist"')[1].split("</ul>")[0]
check('<span class="tag tag-style">Half-Sideways</span>' in live and live.count("tag-style") == 1,
      "home: style badge for a live player on a style (unknown style shows as Normal)")
recs_home = home.body.split('<ul class="reclist">')[1].split("</ul>")[0]
check('href="/maps/surf_alpha?style=sw">surf_alpha</a> <span class="tag tag-style">Sideways</span>' in recs_home
      and '<span class="tag tag-bonus">Bonus 1</span>' in recs_home and recs_home.count("tag-style") == 1,
      "home: recent records name the style when it is not Normal")
top = home.body.split('<ol class="toplist">')[1].split("</ol>")[0] if '<ol class="toplist">' in home.body else ""
check(top.find(f"/players/{CC}") < top.find(f"/players/{A}") < top.find(f"/players/{B}") and top.find(f"/players/{CC}") >= 0, "home: top 10 in order")
check("pill-on" in home.body and "Online" in home.body, "home: server online")
check("https://discord.gg/testsurf" in home.body and "Store" not in home.body, "footer: Discord shown, non-https store hidden")
check(no_raw(home.body) == [], f"home: no raw malicious markup ({no_raw(home.body)})")

csp = home.headers.get("content-security-policy", "")
check("default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
      and f"form-action 'self' http://127.0.0.1:{steam.server_address[1]}" in csp and "https://*.steamstatic.com" in csp
      and "images.steamusercontent.com" in csp and "img-src 'self' data:" in csp, "CSP header")
check(home.headers.get("x-content-type-options") == "nosniff" and home.headers.get("referrer-policy") == "same-origin", "nosniff and referrer policy")

pages = {"/": home}
for path in ["/leaderboard", "/maps", "/maps/surf_alpha", "/maps/surf_alpha?track=1", "/maps/surf_beta?track=2",
             f"/players/{A}", f"/players/{B}", f"/players/{CC}", "/maps/surf_delta", "/maps/surf_beta",
             "/maps/surf_alpha?style=sw", "/maps/surf_alpha?track=1&style=lg", "/maps/surf_alpha?style=zz",
             "/maps/surf_alpha?style=lg", "/maps/surf_alpha?style=%3Cscript%3E", "/maps/surf_alpha?track=1&style=sw",
             f"/players/{FIO}", f"/players/{GUS}"]:
    pages[path] = r = get(path)
    check(r.status == 200, f"GET {path} is 200 ({r.status})")
for path, r in pages.items():
    check(no_raw(r.body) == [], f"{path}: no raw malicious markup ({no_raw(r.body)})")
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", r.body)
    check(not inline and " onerror=" not in r.body.replace("onerror=alert(1)&gt;", "") and 'style="' not in r.body,
          f"{path}: no inline scripts, handlers or style attributes")

lb = pages["/leaderboard"].body
order = [lb.find(f'href="/players/{sid}"', lb.find("<tbody>")) for sid, _ in EXPECT]
check(all(x > 0 for x in order) and order == sorted(order), "leaderboard: order by points, ties by steamid")
check(">160<" in lb and ">137<" in lb and "t2" in lb and "t1" in lb, "leaderboard: points and title colors")
check("Sideways, Half-Sideways, W-Only, Low Gravity" in lb and "worth a quarter" in lb, "leaderboard: points rule mentions styles")

mp = pages["/maps"].body
check("surf_alpha" in mp and "surf_beta" in mp and "surf_gamma" in mp and "surf_evil" not in mp, "maps: installed maps listed, bad file name skipped")
check("Playing now" in mp and "Zones needed" in mp and "tier-3" in mp, "maps: playing now, zones needed, tier badge")
check('src="https://images.steamusercontent.com/ugc/1/alpha.jpg"' in mp, "maps: preview from allowed host")
check('data-tier="3"' in mp and "js-mapsearch" in mp, "maps: client-side filter hooks")
alpha_card = mp.split('href="/maps/surf_alpha"')[1].split("</a>")[0]
check("0:10.000" in alpha_card and "Alice" in alpha_card and "Fiona" not in alpha_card and "3 finishers" in alpha_card
      and "1 bonus<" in alpha_card, "maps: the record shown is main track, Normal")

ma = pages["/maps/surf_alpha"].body
check("https://steamcommunity.com/sharedfiles/filedetails/?id=123456" in ma, "map page: workshop link")
check("Alpha Mapper &lt;i&gt;x&lt;/i&gt;" in ma and "+1.000" in ma and "Record" in ma and "?track=1" in ma, "map page: mapper, gap to #1, bonus tab")
check("0:10.000" in ma and "Record history" in ma, "map page: time format and records")
check("Bonus 1 leaderboard" in pages["/maps/surf_alpha?track=1"].body, "map page: bonus track view")


def style_nav(body):
    m = re.search(r'<nav class="tabs tabs-style" aria-label="Style">(.*?)</nav>', body)
    return re.findall(r">([^<]+)</a>", m.group(1)) if m else []


def stat_rows(body):
    """Sync and max speed cell texts per leaderboard row."""
    tb = body.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in body else ""
    return [re.findall(r'<td class="[^"]*\bc-stat\b[^"]*"[^>]*>([^<]*)</td>', tr) for tr in tb.split("</tr>") if "<td" in tr]


def board_names(body):
    tb = body.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in body else ""
    return re.findall(r'class="pname"[^>]*>([^<]*)<', tb)


check(style_nav(ma) == ["Normal", "Sideways", "zz"] and 'href="/maps/surf_alpha?style=sw"' in ma and "Main leaderboard" in ma,
      f"map page: style tabs, Normal first, only styles with times, unknown id last ({style_nav(ma)})")
check(style_nav(pages["/maps/surf_alpha?track=1"].body) == ["Normal", "Low Gravity"]
      and 'href="/maps/surf_alpha?track=1&amp;style=lg"' in pages["/maps/surf_alpha?track=1"].body,
      "map page: bonus 1 shows Low Gravity but no Sideways tab")
mb = pages["/maps/surf_beta"].body
check(style_nav(mb) == [] and "tabs-style" not in mb and "Sideways" not in mb and "style=" not in mb,
      "map page: no style tabs on a map without style times")
check(">Sync</th>" in ma and ">Max speed</th>" in ma and stat_rows(ma) == [["78.2%", "3,457 u/s"], ["-", "-"], ["-", "-"]],
      f"map page: sync and max speed, '-' for NULL ({stat_rows(ma)})")
check('title="58 strafes · 31 jumps"' in ma and 'title="Average 1,820 u/s"' in ma, "map page: strafes, jumps and average speed on hover")
msw = pages["/maps/surf_alpha?style=sw"].body
check("Main · Sideways leaderboard" in msw and board_names(msw) == ["Fiona", "Gus"] and "+1.000" in msw
      and stat_rows(msw) == [["-", "2,310 u/s"], ["-", "-"]] and "2 finishers" in msw,
      f"map page: Sideways leaderboard ({board_names(msw)}, {stat_rows(msw)})")
check('class=on aria-current=page>Sideways</a>' in msw and "0:10.000" in msw, "map page: Sideways tab active, hero keeps the Normal record")
mlg = pages["/maps/surf_alpha?track=1&style=lg"].body
check("Bonus 1 · Low Gravity leaderboard" in mlg and board_names(mlg) == ["Fiona", "Gus"], "map page: bonus on a style")
check("Main · zz leaderboard" in pages["/maps/surf_alpha?style=zz"].body and board_names(pages["/maps/surf_alpha?style=zz"].body) == ["Gus"],
      "map page: unknown style labelled by its id")
for path in ["/maps/surf_alpha?style=lg", "/maps/surf_alpha?style=%3Cscript%3E", "/maps/surf_alpha?track=1&style=sw"]:
    body = pages[path].body
    check(board_names(body)[:1] == (["Alice"] if "track" not in path else [F.e(XSS1)]) and "· " not in body.split("leaderboard</h2>")[0][-80:],
          f"map page: {path} falls back to Normal")
mhist = ma.split("Record history")[1]
check('<span class="tag tag-style">Sideways</span>' in mhist and '<span class="tag tag-bonus">Bonus 1</span>' in mhist,
      "map page: record history includes style records")
check(get("/maps/surf_nope").status == 404 and get("/maps/..%2F..%2Fetc").status == 404, "unknown map is 404")

pa = pages[f"/players/{A}"].body
check("Alice" in pa and "#2" in pa and "137" in pa and "badge-vip" in pa and "Surfer" in pa, "player page: name, rank, points, VIP, title")
check("surf_alpha" in pa and "Bonus 1" in pa and "#1" in pa and "/2" in pa and "Records held" in pa, "player page: times with position/total")
check('src="https://avatars.steamstatic.com/abc_medium.jpg"' in pa, "player page: cached Steam avatar")
check("evil.example.com" not in pages[f"/players/{CC}"].body, "avatar from a foreign host ignored")
pf = pages[f"/players/{FIO}"].body
check("Fiona" in pf and "<b>137</b> points" in pf and '<dd class="mono">#3</dd>' in pf, "player page: style points count")
check('href="/maps/surf_alpha?style=sw">surf_alpha</a> <span class="tag tag-style">Sideways</span>' in pf
      and 'href="/maps/surf_alpha?track=1&amp;style=lg">surf_alpha</a> <span class="show-sm tag tag-bonus">B1</span> <span class="tag tag-style">Low Gravity</span>' in pf,
      "player page: times name the style next to map and track")
held = pf.split("Records held")[1].split("</section>")[0]
check(held.count('class="rec-chip"') == 2 and "Sideways" in held and "Low Gravity" in held, "player page: records held on styles")
check(pf.find(">Sideways<") < pf.find(">Low Gravity<") and pf.find('href="/maps/surf_gamma"') > pf.find(">Low Gravity<"),
      "player page: times sorted by map, track, style")
check('<span class="tag tag-style">zz</span>' in pages[f"/players/{GUS}"].body, "player page: unknown style labelled by id")
check("tag-style" not in pages[f"/players/{CC}"].body, "player page: no style tag for Normal times")
check(get("/players/123").status == 404 and get("/players/76561198999999999").status == 404, "unknown player is 404")
check(get("/nope").status == 404 and get("/static/../server.py").status == 404, "404s, no path traversal")
check(get("/static/style.css").status == 200 and "javascript" in get("/static/app.js?v=1").headers.get("content-type", ""),
      "static files served")

api = get("/api/status")
j = json.loads(api.body)
check(api.status == 200 and api.headers.get("content-type", "").startswith("application/json"), "api: JSON")
check(j["online"] is True and j["map"] == "surf_alpha" and j["maxplayers"] == 24 and len(j["players"]) == 3, "api: live fields")
allowed = {"steamid", "name", "title", "title_idx", "points", "rank", "state", "track", "style", "time", "pb", "vip", "connected", "avatar", "av"}
check(all(set(p) <= allowed for p in j["players"]), f"api: player fields whitelisted ({sorted(set().union(*map(set, j['players'])))})")
check("203.0.113.7" not in api.body and '"ip"' not in api.body and '"admin"' not in api.body and '"ping"' not in api.body, "api: no IPs or admin flags")
check(j["players"][2]["state"] == "idle" and j["players"][2]["steamid"] == "" and j["wr"]["name"] == XSS2, "api: odd values normalized")
check([p.get("style") for p in j["players"]] == ["hsw", "n", "n"], "api: style republished, missing or unknown is Normal")

# ------------------------------------------------------------------ offline detection
write_status(status(updated=time.time() - 60))
r = get("/")
check("pill-off" in r.body and "Offline" in r.body and "Alice" not in r.body.split("Live players")[1].split("</section>")[0],
      "stale status.json means offline")
check(json.loads(get("/api/status").body)["online"] is False, "api: offline when stale")
os.remove(STATUS)
check(get("/").status == 200 and json.loads(get("/api/status").body)["players"] == [], "missing status.json means offline")
write_status(status(updated=time.time() - 28))
check(json.loads(get("/api/status").body)["online"] is True, "fresh status is online")
write_status('{"updated": 17594')  # half-written by GMOD
check(json.loads(get("/api/status").body)["online"] is True, "half-written status: last good one is used")
time.sleep(2.2)
check(json.loads(get("/api/status").body)["online"] is False, "half-written status: offline once the last good one is 30 s old")
write_status(status())

# ------------------------------------------------------------------ Steam login
r = get("/admin")
check(r.status == 302 and r.location == "/login?next=%2Fadmin", f"anonymous /admin redirects to login ({r.status} {r.location})")


def login(sid, nxt="/admin", ip="10.0.1.1", tamper=None):
    r = get("/login?next=" + urllib.parse.quote(nxt, safe=""), ip=ip)
    nxt_cookie, _ = r.cookie("surf_next")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r.location).query))
    u = urllib.parse.urlsplit(r.location)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    conn.request("GET", u.path + "?" + u.query + "&as=" + sid)
    s = conn.getresponse()
    s.read()
    back = s.getheader("Location")
    conn.close()
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(back).query))
    if tamper:
        tamper(params)
    r2 = get("/auth/steam?" + urllib.parse.urlencode(params), cookies={"surf_next": nxt_cookie} if nxt_cookie else None, ip=ip)
    return r, q, back, params, r2


r, q, back, params, r2 = login(OWNER)
check(r.status == 302 and r.location.startswith(ENDPOINT + "?"), "login redirects to the OpenID endpoint")
check(q.get("openid.mode") == "checkid_setup" and q.get("openid.ns") == "http://specs.openid.net/auth/2.0"
      and q.get("openid.return_to") == BASE + "/auth/steam" and q.get("openid.realm") == BASE + "/"
      and q.get("openid.identity") == q.get("openid.claimed_id") == "http://specs.openid.net/auth/2.0/identifier_select",
      "login: OpenID parameters")
check(back.startswith(BASE + "/auth/steam?"), "fake Steam returns to return_to")
sess, raw_cookie = r2.cookie("surf_session")
check(r2.status == 303 and r2.location == "/admin" and sess and sess.startswith(OWNER + "."), f"owner login sets session and follows next ({r2.status} {r2.location})")
check(raw_cookie and "HttpOnly" in raw_cookie and "SameSite=Lax" in raw_cookie and "Secure" in raw_cookie
      and "Max-Age=1209600" in raw_cookie and "Path=/" in raw_cookie, f"session cookie flags ({raw_cookie})")
OWN = {"surf_session": sess}
adm = get("/admin", cookies=OWN)
check(adm.status == 200 and "Dashboard" in adm.body and "Running" in adm.body and "update" in adm.body.lower(), "owner sees the admin dashboard")
m = re.search(r'name="csrf" value="([0-9a-f]{64})"', adm.body)
CSRF = m.group(1) if m else ""
check(bool(CSRF), "admin forms carry a CSRF token")

r2 = login(OTHER)[4]
osess = r2.cookie("surf_session")[0]
check(r2.status == 303 and osess and osess.startswith(OTHER + "."), "non-owner can sign in")
check(get("/admin", cookies={"surf_session": osess}).status == 403 and get("/admin/bans", cookies={"surf_session": osess}).status == 403,
      "non-owner gets 403 on /admin")
ocsrf = re.search(r'name="csrf" value="([0-9a-f]{64})"', get("/", cookies={"surf_session": osess}).body)
r = req("POST", "/admin/cmd", cookies={"surf_session": osess}, form={"csrf": ocsrf.group(1) if ocsrf else "", "action": "vote"})
check(r.status == 403, "non-owner POST to admin is 403 even with a valid token")

r2 = login(OTHER, tamper=lambda p: p.update({"openid.claimed_id": "https://steamcommunity.com/openid/id/" + OWNER,
                                               "openid.identity": "https://steamcommunity.com/openid/id/" + OWNER}))[4]
check(r2.status == 403 and not r2.cookie("surf_session")[0], "forged claimed_id rejected by check_authentication")
r2 = login(OWNER, tamper=lambda p: p.update({"openid.claimed_id": "https://evil.example/openid/id/" + OWNER,
                                               "openid.identity": "https://evil.example/openid/id/" + OWNER}))[4]
check(r2.status == 403 and not r2.cookie("surf_session")[0], "claimed_id from another host rejected")
r2 = login(OWNER, tamper=lambda p: p.update({"openid.sig": "forged"}))[4]
check(r2.status == 403 and not r2.cookie("surf_session")[0], "failed check_authentication rejected")
r2 = login(OWNER, tamper=lambda p: p.update({"openid.op_endpoint": "https://evil.example/openid/login"}))[4]
check(r2.status == 403, "wrong op_endpoint rejected")
r2 = login(OWNER, tamper=lambda p: p.update({"openid.return_to": "https://evil.example/auth/steam"}))[4]
check(r2.status == 403, "wrong return_to rejected")
r2 = login(OWNER, tamper=lambda p: p.update({"openid.mode": "cancel"}))[4]
check(r2.status == 403, "cancelled login rejected")
r, q, back, params, r2 = login(OWNER, nxt="//evil.example/x")
check(r2.status == 303 and r2.location == "/", f"next must be a local path ({r2.location})")
replay = get("/auth/steam?" + urllib.parse.urlencode(params), ip="10.0.1.1")
check(replay.status == 403 and not replay.cookie("surf_session")[0], "replayed login response rejected")
check(get("/admin", cookies={"surf_session": sess[:-1] + ("0" if sess[-1] != "0" else "1")}).status == 302, "tampered session cookie ignored")

# ------------------------------------------------------------------ CSRF and origin
CMD_DIR = os.path.join(data, "portal", "cmd")


def cmd_files():
    return sorted(f for f in os.listdir(CMD_DIR)) if os.path.isdir(CMD_DIR) else []


before = cmd_files()
check(req("POST", "/admin/cmd", cookies=OWN, form={"action": "vote"}, ip="10.0.2.1").status == 403, "POST without CSRF token is 403")
check(req("POST", "/admin/cmd", cookies=OWN, form={"action": "vote", "csrf": "0" * 64}, ip="10.0.2.1").status == 403, "POST with wrong CSRF token is 403")
check(req("POST", "/admin/cmd", form={"action": "vote", "csrf": CSRF}, ip="10.0.2.1").status == 403, "POST without session is 403")
check(req("POST", "/admin/cmd", cookies=OWN, form={"action": "vote", "csrf": CSRF}, ip="10.0.2.1",
          headers={"Origin": "https://evil.example"}).status == 403, "POST from a foreign Origin is 403")
check(cmd_files() == before, "rejected POSTs wrote no command")


def send(form, ip="10.0.3.1", origin=BASE):
    before = set(cmd_files())
    f = dict(form)
    f["csrf"] = CSRF
    r = req("POST", "/admin/cmd", cookies=OWN, form=f, ip=ip, headers={"Origin": origin} if origin else None)
    new = sorted(set(cmd_files()) - before)
    obj = json.load(open(os.path.join(CMD_DIR, new[0]))) if len(new) == 1 else None
    return r, new, obj


ok_cases = [
    ({"action": "say", "text": "Hello <b>all</b>\x07"}, {"action": "say", "text": "Hello <b>all</b>"}),
    ({"action": "changelevel", "map": "surf_beta"}, {"action": "changelevel", "map": "surf_beta"}),
    ({"action": "changelevel", "map": "surf_delta"}, {"action": "changelevel", "map": "surf_delta"}),
    ({"action": "extend", "minutes": "15"}, {"action": "extend", "minutes": 15}),
    ({"action": "vote"}, {"action": "vote"}),
    ({"action": "kick", "steamid": B, "reason": "spam"}, {"action": "kick", "steamid": B, "reason": "spam"}),
    ({"action": "ban", "steamid": B, "minutes": "0", "reason": "cheating"}, {"action": "ban", "steamid": B, "minutes": 0, "reason": "cheating"}),
    ({"action": "ban", "steamid": B, "minutes": "60", "reason": ""}, {"action": "ban", "steamid": B, "minutes": 60, "reason": ""}),
    ({"action": "unban", "steamid": B}, {"action": "unban", "steamid": B}),
    ({"action": "givevip", "steamid": A, "days": "30"}, {"action": "givevip", "steamid": A, "days": 30}),
    ({"action": "givevip", "steamid": A, "days": "0"}, {"action": "givevip", "steamid": A, "days": 0}),
    ({"action": "removevip", "steamid": A}, {"action": "removevip", "steamid": A}),
    ({"action": "deltime", "key": "surf_alpha#b1", "steamid": A}, {"action": "deltime", "key": "surf_alpha#b1", "steamid": A}),
]
for i, (form, want) in enumerate(ok_cases):
    r, new, obj = send(form, origin=BASE if i % 2 else None)
    want = dict(want, by=OWNER)
    check(r.status == 303 and r.location == "/admin" and len(new) == 1 and re.match(r"^\d{13}_[0-9a-f]{8}\.txt$", new[0])
          and obj == want, f"{form['action']} writes {want} ({r.status}, {new}, {obj})")
check(not [f for f in os.listdir(CMD_DIR) if f.endswith(".tmp")], "no temp files left behind")

bad_cases = [
    {"action": "say", "text": ""}, {"action": "say", "text": "x" * 201}, {"action": "say", "text": "\x07\x08"},
    {"action": "changelevel", "map": "surf_nope"}, {"action": "changelevel", "map": "../../etc/passwd"},
    {"action": "changelevel", "map": "<script>"},
    {"action": "extend", "minutes": "0"}, {"action": "extend", "minutes": "121"}, {"action": "extend", "minutes": "abc"},
    {"action": "extend", "minutes": "-5"}, {"action": "extend", "minutes": "1.5"}, {"action": "extend"},
    {"action": "kick", "steamid": "123"}, {"action": "kick", "steamid": "7656119800000000x"},
    {"action": "kick", "steamid": B, "reason": "r" * 201}, {"action": "ban", "steamid": B, "minutes": "-1"},
    {"action": "ban", "steamid": "76561198000000001 OR 1=1", "minutes": "5"}, {"action": "unban", "steamid": ""},
    {"action": "givevip", "steamid": A, "days": "3651"}, {"action": "givevip", "steamid": A},
    {"action": "removevip", "steamid": "86561198000000011"},
    {"action": "deltime", "key": "surf_alpha#x", "steamid": A}, {"action": "deltime", "key": "SURF_ALPHA", "steamid": A},
    {"action": "deltime", "key": "surf_alpha'; drop table surf_times;--", "steamid": A},
    {"action": "deltime", "key": "surf_alpha", "steamid": "1"},
    {"action": "deltime", "key": "surf_x@zz", "steamid": A}, {"action": "deltime", "key": "surf_x@sw#b2", "steamid": A},
    {"action": "deltime", "key": "surf_x@", "steamid": A}, {"action": "deltime", "key": "surf_x@SW", "steamid": A},
    {"action": "deltime", "key": "surf_x#b2@sw@lg", "steamid": A},
    {"action": "rcon", "cmd": "quit"}, {},
]
for form in bad_cases:
    r, new, obj = send(form, ip="10.0.4.1")
    flash = r.cookie("surf_flash")[0]
    check(r.status == 303 and not new and flash, f"rejected: {form} ({r.status}, {new})")
r, new, _ = send({"action": "kick", "steamid": B, "reason": "x", "back": "https://evil.example/"}, ip="10.0.4.1")
check(r.location == "/admin", "redirect after POST stays on the admin pages")
r, new, _ = send({"action": "say", "text": XSS1}, ip="10.0.4.2")
page = get(r.location, cookies=dict(OWN, surf_flash=r.cookie("surf_flash")[0]))
check("Sent: Broadcast" in page.body and F.e(XSS1) in page.body and XSS1 not in page.body, "flash message shown and escaped")
check(page.cookie("surf_flash")[0] == "", "flash cookie cleared after display")
r, new, _ = send({"action": "extend", "minutes": "500", "back": "/admin/maps"}, ip="10.0.4.2")
page = get(r.location, cookies=dict(OWN, surf_flash=r.cookie("surf_flash")[0]))
check(r.location == "/admin/maps" and "Minutes must be between 1 and 120" in page.body, "validation error shown after redirect")

audit = [json.loads(line) for line in open(os.path.join(data, "portal", "audit.log"))]
cmds = [a for a in audit if a.get("kind") == "cmd"]
check(len(cmds) == len(ok_cases) + 2 and all(a["by"] == OWNER and a.get("id") and a.get("ip") for a in cmds),
      f"every admin command is in audit.log ({len(cmds)})")
check(any(a.get("kind") == "login" and a["by"] == OWNER for a in audit), "owner logins are audited")

# results: one done, one failed (with markup), one picked up without result, others still queued
ids = [a["id"] for a in cmds]
with open(os.path.join(data, "portal", "results.txt"), "w") as f:
    f.write(json.dumps({"id": ids[0], "ok": True, "msg": "Broadcast sent", "time": NOW}) + "\n")
    f.write("garbage line\n")
    f.write(json.dumps({"id": ids[1], "ok": False, "msg": "map missing " + XSS1, "time": NOW}) + "\n")
os.remove(os.path.join(CMD_DIR, ids[2] + ".txt"))
adm = get("/admin", cookies=OWN).body
check("Broadcast sent" in adm and "res-ok" in adm and "res-err" in adm and F.e("map missing " + XSS1) in adm, "results matched by id and escaped")
check("res-sent" in adm and "res-wait" in adm, "commands without result show sent/queued")
check(no_raw(adm) == [], f"admin: no raw malicious markup ({no_raw(adm)})")
check('data-confirm="Restart the game server' in adm and 'optgroup label="Zoned"' in adm and "surf_delta" in adm, "admin: confirm hooks and map select")
# time keys with a style (v4); sent after the checks above so the first commands stay in the dashboard list
for form, want in [({"action": "deltime", "key": "surf_x#b2@sw", "steamid": A}, {"action": "deltime", "key": "surf_x#b2@sw", "steamid": A}),
                   ({"action": "deltime", "key": " surf_alpha@lg ", "steamid": B}, {"action": "deltime", "key": "surf_alpha@lg", "steamid": B})]:
    r, new, obj = send(form, ip="10.0.4.3")
    check(r.status == 303 and len(new) == 1 and obj == dict(want, by=OWNER), f"deltime with a style writes {want} ({r.status}, {obj})")

# ------------------------------------------------------------------ ctl
open(ctl_log, "w").close()
r = req("POST", "/admin/ctl", cookies=OWN, form={"op": "restart", "csrf": CSRF}, ip="10.0.5.1", headers={"Origin": BASE})
check(r.status == 303 and open(ctl_log).read().split() == ["restart"], "restart runs the ctl")
r = req("POST", "/admin/ctl", cookies=OWN, form={"op": "update", "csrf": CSRF}, ip="10.0.5.1")
check(r.status == 303 and open(ctl_log).read().split()[-1] == "update", "update runs the ctl")
r = req("POST", "/admin/ctl", cookies=OWN, form={"op": "rm -rf", "csrf": CSRF}, ip="10.0.5.1")
check(r.status == 303 and open(ctl_log).read().split() == ["restart", "update"], "unknown ctl op refused")
r = req("POST", "/admin/ctl", cookies=OWN, form={"op": "restart"}, ip="10.0.5.1")
check(r.status == 403 and open(ctl_log).read().split() == ["restart", "update"], "ctl without CSRF is 403")
lg = get("/admin/logs", cookies=OWN)
check(lg.status == 200 and "Could not read the server journal" in lg.body and "journal is broken" in lg.body
      and "update finished OK" in lg.body and "maps line 299" in lg.body and "maps line 50" not in lg.body, "logs: ctl failure is friendly, log tails shown")
check(any(a.get("kind") == "ctl" and a.get("op") == "restart" for a in map(json.loads, open(os.path.join(data, "portal", "audit.log")))),
      "ctl actions are audited")

# ------------------------------------------------------------------ other admin pages
for path in ["/admin/players", "/admin/players?q=Ali", "/admin/players?q=%25_", f"/admin/players?sid={A}", "/admin/players?sid=bad",
             "/admin/bans", "/admin/vip", "/admin/maps", "/admin/logs"]:
    r = get(path, cookies=OWN)
    check(r.status == 200 and no_raw(r.body) == [], f"{path}: 200 and escaped ({r.status}, {no_raw(r.body)})")
check("Alice" in get("/admin/players?q=Ali", cookies=OWN).body, "player search by name")
det = get(f"/admin/players?sid={A}", cookies=OWN).body
check('name="key" value="surf_alpha#b1"' in det and 'value="deltime"' in det and 'value="removevip"' in det, "player detail: delete time and VIP buttons")
detf = get(f"/admin/players?sid={FIO}", cookies=OWN).body
keys_f = re.findall(r'name="key" value="([^"]*)"', detf)
check(sorted(keys_f) == ["surf_alpha#b1@lg", "surf_alpha@sw", "surf_gamma"] and "Low Gravity" in detf and "Sideways" in detf,
      f"player detail: delete buttons for style times ({keys_f})")
r, new, obj = send({"action": "deltime", "key": keys_f[keys_f.index("surf_alpha#b1@lg")], "steamid": FIO,
                    "back": f"/admin/players?sid={FIO}"}, ip="10.0.7.1")
check(r.status == 303 and r.location == f"/admin/players?sid={FIO}" and obj == {"action": "deltime", "key": "surf_alpha#b1@lg", "steamid": FIO, "by": OWNER},
      f"delete a style time end to end: form, validation, command file ({obj})")
detg = get(f"/admin/players?sid={GUS}", cookies=OWN).body
check('value="surf_alpha@zz"' not in detg and "Unknown key" in detg and 'name="key" value="surf_alpha@sw"' in detg,
      "player detail: no delete button for a key the game would refuse")
check("Half-Sideways" in get("/admin", cookies=OWN).body, "admin dashboard: live player style")
bans = get("/admin/bans", cookies=OWN).body
check(F.e(XSS1) in bans and 'value="unban"' in bans and "Permanent" in bans, "bans list with unban")
vip = get("/admin/vip", cookies=OWN).body
check("Alice" in vip and "Dave" not in vip, "VIP list hides expired VIP")
mapsadm = get("/admin/maps", cookies=OWN).body
check("!zone start" in mapsadm and "!zone end" in mapsadm and "!map &lt;name&gt;" in mapsadm and "surf_gamma" in mapsadm, "admin maps: zoning instructions")
check(">4<" in mapsadm and "Failed downloads" in mapsadm and "timed out &lt;b&gt;bold&lt;/b&gt;" in mapsadm and "maps line 299" in mapsadm,
      "admin maps: failed, not found, maps.log")

# ------------------------------------------------------------------ logout, rate limit
other_csrf = re.search(r'name="csrf" value="([0-9a-f]{64})"', get("/", cookies=OWN).body).group(1)
r = req("POST", "/logout", cookies=OWN, form={"csrf": other_csrf}, ip="10.0.6.1")
check(r.status == 303 and r.cookie("surf_session")[1] and "Max-Age=0" in r.cookie("surf_session")[1], "logout clears the session")
check(req("POST", "/logout", cookies=OWN, form={}, ip="10.0.6.1").status == 403, "logout needs CSRF")
codes = [get("/login", ip="10.66.66.66").status for _ in range(25)]
check(429 in codes and codes[0] == 302, f"login is rate limited per IP ({codes.count(429)} x 429)")
check(get("/login", ip="10.66.66.67").status == 302, "other IPs are not affected")
check(get("/healthz").status == 200 and get("/robots.txt").status == 200, "healthz and robots")

# ------------------------------------------------------------------ portal with nothing to read
empty_root = os.path.join(tmp, "empty")
os.makedirs(os.path.join(empty_root, "repo"))
proc2, port2 = start_portal(["--repo", os.path.join(empty_root, "repo"), "--gmod-dir", os.path.join(empty_root, "gm"),
                             "--logs-dir", empty_root, "--secret-file", os.path.join(empty_root, "s"),
                             "--ctl", os.path.join(empty_root, "missing-ctl")], "portal2.log")
check(port2 is not None, "second portal (no config, DB or data) started")
if port2:
    for path in ["/", "/leaderboard", "/maps", "/api/status", "/maps/surf_alpha"]:
        r = get(path, port=port2)
        check(r.status in (200, 404) and r.status != 500 and (path != "/" or "Offline" in r.body), f"no data: {path} -> {r.status}")
    check("Surf" in get("/", port=port2).body, "BRAND_NAME defaults to Surf")
    proc2.terminate()

proc3, port3 = start_portal(["--repo", os.path.join(old_root, "repo"), "--gmod-dir", old_gm, "--logs-dir", old_root,
                             "--secret-file", os.path.join(old_root, "s"), "--ctl", os.path.join(old_root, "missing-ctl")], "portal3.log")
check(port3 is not None, "third portal (pre-v4 DB without stat columns) started")
if port3:
    r = get("/maps/surf_old", port=port3)
    check(r.status == 200 and ">Sync</th>" in r.body and stat_rows(r.body) == [["-", "-"]] and style_nav(r.body) == ["Normal", "Sideways"],
          f"old DB: map page shows '-' for missing stat columns ({r.status}, {stat_rows(r.body)})")
    r = get("/maps/surf_old?style=sw", port=port3)
    check(r.status == 200 and "Main · Sideways leaderboard" in r.body and stat_rows(r.body) == [["-", "-"]], "old DB: style leaderboard")
    for path in ["/", "/leaderboard", "/maps", f"/players/{A}", f"/players/{B}"]:
        check(get(path, port=port3).status == 200, f"old DB: {path} is 200")
    proc3.terminate()
    check("Traceback" not in open(os.path.join(tmp, "portal3.log")).read(), "old DB: no server-side exceptions")

proc.terminate()
steam.shutdown()
err = open(os.path.join(tmp, "portal.log")).read()
check("Traceback" not in err, "no server-side exceptions logged")
if "Traceback" in err:
    print(err[-3000:])
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
