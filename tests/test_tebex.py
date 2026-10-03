"""Offline test of the Tebex poller (portal/surfweb/tebex.py) against a fake Plugin API.
Run: python3 tests/test_tebex.py
"""
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "portal"))
from surfweb import tebex as T  # noqa: E402

fails = []


def check(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        fails.append(m)


A = "76561198000000011"

# ------------------------------------------------------------------ Steam IDs and commands
check(T.to_steamid64(A) == A and T.to_steamid64("STEAM_0:1:20") == "76561197960265769"
      and T.to_steamid64("STEAM_1:0:20") == "76561197960265768" and T.to_steamid64("[U:1:40]") == "76561197960265768",
      "SteamID64, STEAM_X:Y:Z and [U:1:N] all convert")
check(T.to_steamid64("123") is None and T.to_steamid64("STEAM_0:2:1") is None and T.to_steamid64("") is None, "bad ids are refused")
cases = {
    f"surf_givevip {A} 30": {"action": "givevip", "steamid": A, "days": 30, "by": "tebex"},
    f"surf_givevip {A}": {"action": "givevip", "steamid": A, "days": 30, "by": "tebex"},
    f"SURF_GIVEVIP {A} 0": {"action": "givevip", "steamid": A, "days": 0, "by": "tebex"},
    f"surf_removevip {A}": {"action": "removevip", "steamid": A, "by": "tebex"},
    f"surf_givecoins {A} 5000": {"action": "givecoins", "steamid": A, "amount": 5000, "by": "tebex"},
    f"surf_givecoins {A} -100": {"action": "givecoins", "steamid": A, "amount": -100, "by": "tebex"},
    f"surf_giveitem {A} Color:Rainbow": {"action": "giveitem", "steamid": A, "item": "color:rainbow", "by": "tebex"},
    f"surf_removeitem {A} trail:gold": {"action": "removeitem", "steamid": A, "item": "trail:gold", "by": "tebex"},
}
for line, want in cases.items():
    check(T.translate(line) == want, f"translate {line!r}")
for line in ["", "say hi", f"surf_givevip {A} 99999", f"surf_givevip {A} -1", f"surf_givecoins {A} 0", f"surf_givecoins {A} lots",
             f"surf_giveitem {A} ../etc", f"surf_removevip {A} now", "surf_givevip {id} 30", f"ulx adduser {A} vip",
             f"surf_givecoins {A} 5000; quit"]:
    check(T.translate(line) is None, f"not run: {line!r}")


# ------------------------------------------------------------------ fake Plugin API
class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeTebex:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.offline = [{"id": 1, "command": f"surf_givevip {A} 30", "player": {"id": 7, "name": "Alice", "uuid": A}},
                        {"id": 2, "command": "surf_givecoins STEAM_0:1:20 5000", "player": {"id": 8, "name": "Bob"}},
                        {"id": 3, "command": "say thanks {username}", "player": {"id": 8, "name": "Bob"}}]
        self.online = {9: [{"id": 4, "command": "surf_giveitem [U:1:40] color:rainbow"}]}

    def __call__(self, req, timeout=None):
        url = urllib.parse.urlsplit(req.full_url)
        body = req.data.decode() if req.data else ""
        self.calls.append((req.get_method(), url.path, req.get_header("X-tebex-secret"), body))
        if self.status != 200:
            raise urllib.error.HTTPError(req.full_url, self.status, "nope", {}, None)
        if url.path == "/queue" and req.get_method() == "GET":
            out = {"meta": {"execute_offline": True, "next_check": 45, "more": False},
                   "players": [{"id": 9, "name": "Cara", "uuid": "76561197960265768"}]}
        elif url.path == "/queue/offline-commands":
            out = {"meta": {"limited": False}, "commands": self.offline}
        elif url.path.startswith("/queue/online-commands/"):
            out = {"commands": self.online.get(int(url.path.rsplit("/", 1)[1]), [])}
        elif url.path == "/queue" and req.get_method() == "DELETE":
            return FakeResp(b"")
        else:
            raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)
        return FakeResp(json.dumps(out).encode())


class Conf:
    def __init__(self, secret):
        self.secret = secret

    def get(self, key, default=""):
        return self.secret if key == "TEBEX_SECRET" else default


tmp = tempfile.mkdtemp()
portal_dir = os.path.join(tmp, "portal")
cmd_dir = os.path.join(portal_dir, "cmd")


def cmds():
    if not os.path.isdir(cmd_dir):
        return []
    return [json.load(open(os.path.join(cmd_dir, f))) for f in sorted(os.listdir(cmd_dir)) if f.endswith(".txt")]


fake = FakeTebex()
t = T.Tebex(Conf(""), portal_dir, api="https://tebex.test", opener=fake)
check(t.poll_once() == 60 and fake.calls == [], "without TEBEX_SECRET nothing is asked")

t.conf = Conf("s3cret")
wait = t.poll_once()
got = cmds()
check(wait == 45, f"waits as long as Tebex says ({wait})")
check(all(c[2] == "s3cret" for c in fake.calls), "every request carries the secret")
check(sorted(json.dumps(c, sort_keys=True) for c in got) == sorted(json.dumps(c, sort_keys=True) for c in [
    {"action": "givevip", "steamid": A, "days": 30, "by": "tebex"},
    {"action": "givecoins", "steamid": "76561197960265769", "amount": 5000, "by": "tebex"},
    {"action": "giveitem", "steamid": "76561197960265768", "item": "color:rainbow", "by": "tebex"}]),
      f"offline and online purchases become portal commands ({got})")
dels = [c for c in fake.calls if c[0] == "DELETE"]
check(len(dels) == 1 and urllib.parse.parse_qs(dels[0][3]) == {"ids[]": ["1", "2", "4"]}, f"done commands are deleted, the unknown one stays ({dels})")
check(json.load(open(os.path.join(portal_dir, "tebex_done.json"))) == [1, 2, 4], "ids already run are saved")

# Tebex didn't drop them (or the delete failed): nothing runs twice, even after a restart
t2 = T.Tebex(Conf("s3cret"), portal_dir, api="https://tebex.test", opener=fake)
fake.calls = []
t2.poll_once()
check(len(cmds()) == 3, "a command id never runs twice, even after a portal restart")
dels = [c for c in fake.calls if c[0] == "DELETE"]
check(len(dels) == 1 and urllib.parse.parse_qs(dels[0][3]) == {"ids[]": ["1", "2", "4"]}, "and they are deleted again")

fake.status = 403
check(t2.poll_once() == 120, "a refused secret waits and retries later")
fake.status = 200
fake.offline = [{"id": 5, "command": None}, {"id": "6", "command": f"surf_givevip {A} 30"}, {"command": "x"}]
fake.online = {}
t2.poll_once()
check(len(cmds()) == 3, "malformed commands are skipped")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
