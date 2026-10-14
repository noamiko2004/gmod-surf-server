#!/usr/bin/env python3
"""Tests for the update flow: scripts/updater.py (when the automatic update runs,
the in-game warning, the website check) and scripts/update.sh end to end in a
sandbox with a fake game, fake systemctl and SteamCMD, and a real git remote.
Run: python3 tests/test_updater.py"""
import fcntl
import http.server
import importlib.util
import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def sh(*args, cwd=None, env=None):
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{args}: {r.stderr}")
    return r.stdout


GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def make_repo(tmp, src_files=None):
    """A bare origin and a checkout tracking it (like /home/gmod/surfline)."""
    origin = os.path.join(tmp, "origin.git")
    repo = os.path.join(tmp, "repo")
    sh("git", "init", "-q", "--bare", "-b", "main", origin)
    if src_files:
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "config.env", "node_modules"))
    else:
        os.makedirs(repo)
        open(os.path.join(repo, "README.md"), "w").write("x\n")
    sh("git", "init", "-q", "-b", "main", repo)
    sh("git", "add", "-A", cwd=repo)
    sh("git", "commit", "-q", "-m", "first", cwd=repo, env=GIT_ENV)
    sh("git", "remote", "add", "origin", origin, cwd=repo)
    sh("git", "push", "-q", "-u", "origin", "main", cwd=repo)
    return origin, repo


def push_change(tmp, origin, name):
    """Someone merges a change on GitHub."""
    other = os.path.join(tmp, "other_" + name)
    if not os.path.isdir(other):
        sh("git", "clone", "-q", origin, other)
    sh("git", "pull", "-q", cwd=other)
    open(os.path.join(other, name + ".txt"), "w").write(name)
    sh("git", "add", "-A", cwd=other)
    sh("git", "commit", "-q", "-m", "change " + name, cwd=other, env=GIT_ENV)
    sh("git", "push", "-q", cwd=other)


STEAM_OUT = """Connecting anonymously to Steam Public...OK
AppID : 4020, change number : 123/0, last change : Mon Oct 13 2026
"4020"
{
	"common" { "name" "Garry's Mod Dedicated Server" }
	"depots"
	{
		"branches"
		{
			"beta" { "buildid" "999" }
			"public"
			{
				"buildid"		"%s"
				"timeupdated"		"1760000000"
			}
		}
	}
}
AppID : 232330, change number : 77/0
"232330"
{
	"depots"
	{
		"branches"
		{
			"public"
			{
				"buildid"		"%s"
			}
		}
	}
}
"""


def load_updater(env):
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location("updater_" + str(len(env)) + str(time.time()), os.path.join(ROOT, "scripts", "updater.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ===================================================================== unit
tmp = tempfile.mkdtemp(prefix="updater_")
home = os.path.join(tmp, "home")
server = os.path.join(home, "server")
css = os.path.join(home, "css")
portal = os.path.join(server, "garrysmod", "data", "surfline", "portal")
for d in (os.path.join(server, "steamapps"), os.path.join(css, "steamapps"), os.path.join(portal, "cmd"), os.path.join(home, "steamcmd")):
    os.makedirs(d)
origin, repo = make_repo(tmp)


def manifest(d, app, build):
    open(os.path.join(d, "steamapps", f"appmanifest_{app}.acf"), "w").write(
        f'"AppState"\n{{\n\t"appid"\t\t"{app}"\n\t"buildid"\t\t"{build}"\n}}\n')


manifest(server, "4020", "100")
manifest(css, "232330", "50")
steam_reply = os.path.join(tmp, "steam_reply.txt")
open(steam_reply, "w").write(STEAM_OUT % ("100", "50"))
steamcmd = os.path.join(home, "steamcmd", "steamcmd.sh")
open(steamcmd, "w").write(f'#!/bin/sh\necho "$@" >> "{tmp}/steam_calls.txt"\ncat "{steam_reply}"\n')
os.chmod(steamcmd, 0o755)
starts = os.path.join(tmp, "starts.txt")
starter = os.path.join(tmp, "start.sh")
open(starter, "w").write(f'#!/bin/sh\necho "$1" >> "{starts}"\n')
os.chmod(starter, 0o755)

U = load_updater({"REPO_DIR": repo, "GMOD_HOME": home, "GMOD_USER": "nobody", "SERVER_DIR": server, "CSS_DIR": css,
                  "STEAMCMD_DIR": os.path.join(home, "steamcmd"), "UPDATER_START": starter})
now = [1_760_000_000.0]
U.clock = lambda: now[0]
U.is_root = lambda: False  # as root it runs SteamCMD through sudo; the tests run it directly

game = {"players": [], "answer": "ok", "kick_at": None, "commands": []}


def write_status(players, age=0):
    with open(os.path.join(portal, "status.json"), "w") as f:
        json.dump({"updated": int(now[0] - age), "players": players}, f)


def run_game():
    """What sv_portal.lua does every 2 s: run commands, answer, write status."""
    d = os.path.join(portal, "cmd")
    for name in sorted(os.listdir(d)):
        if not name.endswith(".txt"):
            continue
        cmd = json.load(open(os.path.join(d, name)))
        os.remove(os.path.join(d, name))
        game["commands"].append(cmd)
        if game["answer"] is None:
            continue
        ok, msg = True, "done"
        if cmd["action"] == "update":
            if game["answer"] == "old":
                ok, msg = False, "unknown action"
            else:
                game["kick_at"] = now[0] + cmd["seconds"]
        elif cmd["action"] == "kick":
            game["players"] = [p for p in game["players"] if p["steamid"] != cmd["steamid"]]
        with open(os.path.join(portal, "results.txt"), "a") as f:
            f.write(json.dumps({"id": name[:-4], "ok": ok, "msg": msg}) + "\n")
    if game["kick_at"] and now[0] >= game["kick_at"]:
        game["players"], game["kick_at"] = [], None
    write_status(game["players"])


def fake_sleep(s):
    now[0] += s
    if game["answer"] is not None or game["players"]:
        run_game()


U.sleep = fake_sleep


def player(n):
    return {"steamid": f"765611980000000{n:02d}", "name": f"P{n}"}


# --- parsing
check(U.parse_app_info(STEAM_OUT % ("123", "45")) == {"4020": "123", "232330": "45"}, "SteamCMD's public build ids are read (not the beta's)")
check(U.parse_app_info("Connecting...FAILED") == {}, "an unreadable SteamCMD answer gives nothing")
check(U.installed_build("4020") == "100" and U.installed_build("232330") == "50", "installed builds come from the app manifests")

# --- the rules
D = 86400
cases = [((0, 0), True), ((1, 0.5 * D), False), ((3, 1.9 * D), False), ((3, 2 * D), True), ((4, 2.5 * D), False),
         ((4, 4 * D), True), ((20, 4 * D), True)]
check(all(U.decide(now[0] - waited, n, now[0])[0] == go for (n, waited), go in cases),
      "empty: now; 3 or fewer after 2 days; anyone after 4 days")

# --- players online
write_status([player(1), player(2)])
check(len(U.players_online()) == 2, "players are read from status.json")
write_status([player(1)], age=120)
check(U.players_online() == [], "an old status.json means the game isn't running: nobody is on")


def state():
    return json.load(open(os.path.join(home, "update_state.json")))


def started():
    return open(starts).read().splitlines() if os.path.exists(starts) else []


# --- automatic update: nothing new
write_status([])
U.auto()
st = state()
check(not started() and "due_since" not in st and st["checked"] == now[0], "nothing new: nothing happens")
check(st.get("steam_latest") == {"4020": "100", "232330": "50"}, "Steam was asked for the newest builds")

# --- a change on GitHub while 2 are on
push_change(tmp, origin, "a")
game["players"] = [player(1), player(2)]
write_status(game["players"])
due_at = now[0]
U.auto()
st = state()
check(not started() and st.get("due_since") == due_at and st.get("players") == 2 and "1 new change from GitHub" in st.get("due", []),
      "a new change with players on waits")
now[0] += 1.5 * D
write_status(game["players"])
U.auto()
check(not started() and state().get("due_since") == due_at, "still waiting after a day and a half with 2 on")
now[0] = due_at + 2 * D + 60
write_status(game["players"])
U.auto()
check(len(started()) == 1 and "waited 2 days" in started()[0], f"after 2 days, 2 players don't stop it ({started()})")

# update.sh ran: the change is installed
before = sh("git", "rev-parse", "HEAD", cwd=repo).strip()
sh("git", "pull", "-q", cwd=repo)
U.done(before)
st = state()
check("due_since" not in st and st.get("last_update") == now[0] and st.get("version") == sh("git", "log", "-1", "--format=%h", cwd=repo).strip(),
      "after the update nothing is due and the version is recorded")

# --- many players: waits the full 4 days
push_change(tmp, origin, "b")
game["players"] = [player(i) for i in range(1, 9)]
write_status(game["players"])
due_at = now[0]
U.auto()
now[0] = due_at + 3 * D
write_status(game["players"])
U.auto()
check(len(started()) == 1, "8 players: still waiting after 3 days")
now[0] = due_at + 4 * D + 1
write_status(game["players"])
U.auto()
check(len(started()) == 2 and "waited 4 days" in started()[-1], "after 4 days it goes ahead no matter what")
sh("git", "pull", "-q", cwd=repo)
U.done(before)

# --- empty server: right away
push_change(tmp, origin, "c")
write_status([])
U.auto()
check(len(started()) == 3 and "empty" in started()[-1], "an empty server updates right away")

# --- an update that failed to install the change doesn't loop
U.done(before)  # the pull "failed": the change is still on GitHub only
st = state()
check(st.get("hold", {}).get("git", 0) == now[0] + D, "a change the update didn't install waits a day")
now[0] += 3600
write_status([])
U.auto()
check(len(started()) == 3 and "due_since" not in state(), "...so the server isn't restarted every 15 minutes")
now[0] += D
write_status([])
U.auto()
check(len(started()) == 4, "a day later it is tried again")
sh("git", "pull", "-q", cwd=repo)
U.done(before)

# --- Steam: a Garry's Mod update
open(steam_reply, "w").write(STEAM_OUT % ("101", "50"))
now[0] += 2 * 3600
game["players"] = [player(1)]
write_status(game["players"])
U.auto()
st = state()
check("Garry's Mod update" in st.get("due", []) and len(started()) == 4, "a new Garry's Mod build is due, waiting for the player")
calls = len(open(os.path.join(tmp, "steam_calls.txt")).read().splitlines())
now[0] += 900
write_status(game["players"])
U.auto()
check(len(open(os.path.join(tmp, "steam_calls.txt")).read().splitlines()) == calls, "Steam is asked at most once an hour")
game["players"] = []
write_status([])
now[0] += 900
U.auto()
check(len(started()) == 5, "the Garry's Mod update installs once the server is empty")
manifest(server, "4020", "101")
U.done(before)
now[0] += 900
write_status([])
U.auto()
check(len(started()) == 5 and "due_since" not in state(), "installed: nothing more to do")

# --- Steam can't be read for a day: updates anyway, like the old nightly
open(steam_reply, "w").write("Connecting anonymously to Steam Public...FAILED\n")
for _ in range(24):
    now[0] += 3600
    write_status([player(1)])
    U.auto()
st = state()
check(any("couldn't be read" in d for d in st.get("due", [])), "Steam unreadable for a day: an update is due anyway")
U.done(before)
now[0] += 3600
write_status([])
U.auto()
check(len(started()) == 5, "...once a day at most")

# --- the in-game warning
game.update(players=[player(1), player(2)], answer="ok", commands=[])
write_status(game["players"])
t0 = now[0]
U.warn(30)
upd = [c for c in game["commands"] if c["action"] == "update"]
check(len(upd) == 1 and upd[0]["seconds"] == 30 and "updating" in upd[0]["reason"] and upd[0]["by"] == "update",
      "the game gets the countdown command with the kick message")
check(not game["players"] and 30 <= now[0] - t0 <= 40, f"warn returns once everyone is disconnected ({now[0] - t0:.0f} s)")

game.update(players=[player(1), player(2)], answer="old", commands=[])
write_status(game["players"])
U.warn(30)
acts = [c["action"] for c in game["commands"]]
check(acts[:3] == ["update", "say", "say"] and acts.count("kick") == 2 and not game["players"],
      f"an older gamemode gets chat messages and kicks instead ({acts})")
kicks = [c for c in game["commands"] if c["action"] == "kick"]
check(all("updating" in k["reason"] for k in kicks), "kicked players see why")

game.update(players=[player(1)], answer=None, commands=[])
write_status(game["players"])
t0 = now[0]
U.warn(30)
check(now[0] - t0 <= 12, "a game that doesn't answer doesn't hold up the update")
game.update(players=[], answer="ok", commands=[])
write_status([])
U.warn(30)
check(game["commands"] == [], "nobody on: no warning")

# --- the website check
served = {"ver": "abc1234"}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'<footer><span class="footer-ver">Version {served["ver"]}, 2026-10-14 21:00 UTC</span></footer>'.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
U.SITE_URL = f"http://127.0.0.1:{srv.server_address[1]}/"
check(U.site("abc1234", tries=2) == 0, "the website check sees the new version")
check(U.site("fff0000", tries=2) == 1, "a website still on the old version is reported")
srv.shutdown()

# ===================================================================== update.sh end to end
box = tempfile.mkdtemp(prefix="update_sh_")
origin2, repo2 = make_repo(box, src_files=True)
home2 = os.path.join(box, "home")
server2 = os.path.join(home2, "server")
gm2 = os.path.join(server2, "garrysmod")
portal2 = os.path.join(gm2, "data", "surfline", "portal")
for d in (os.path.join(gm2, "cfg"), os.path.join(portal2, "cmd"), os.path.join(home2, "steamcmd"), os.path.join(box, "bin"),
          os.path.join(box, "etc", "cron.d"), os.path.join(box, "usr", "bin")):
    os.makedirs(d, exist_ok=True)
me = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
cfg = open(os.path.join(ROOT, "config.env.example")).read()
cfg = cfg.replace('GMOD_USER="gmod"', f'GMOD_USER="{me}"').replace('GMOD_HOME="/home/gmod"', f'GMOD_HOME="{home2}"')
cfg += '\nSKIP_MAPS="1"\n'
open(os.path.join(repo2, "config.env"), "w").write(cfg)
# System paths and the website's setup point into the sandbox
for name in ("deploy.sh",):
    p = os.path.join(repo2, "scripts", name)
    s = open(p).read().replace("/etc/cron.d/", os.path.join(box, "etc", "cron.d") + "/").replace("/usr/local/bin/", os.path.join(box, "usr", "bin") + "/")
    open(p, "w").write(s)
open(os.path.join(repo2, "scripts", "portal.sh"), "w").write(f'#!/bin/sh\necho "portal.sh ran" >> "{box}/calls.txt"\n')
sh("git", "add", "-A", cwd=repo2)
sh("git", "commit", "-q", "-m", "sandbox", cwd=repo2, env=GIT_ENV)
sh("git", "push", "-q", cwd=repo2)
open(os.path.join(home2, "steamcmd", "steamcmd.sh"), "w").write(f'#!/bin/sh\necho "steamcmd $*" >> "{box}/calls.txt"\n')
os.chmod(os.path.join(home2, "steamcmd", "steamcmd.sh"), 0o755)
open(os.path.join(box, "bin", "systemctl"), "w").write(f'#!/bin/sh\necho "systemctl $*" >> "{box}/calls.txt"\n'
                                                       'case "$1" in is-active) exit 3 ;; esac\nexit 0\n')
os.chmod(os.path.join(box, "bin", "systemctl"), 0o755)
for tool in ("sqlite3",):
    open(os.path.join(box, "bin", tool), "w").write("#!/bin/sh\nexit 0\n")
    os.chmod(os.path.join(box, "bin", tool), 0o755)


class Site(http.server.BaseHTTPRequestHandler):
    """The website: its footer shows the commit checked out in the sandbox."""
    def do_GET(self):
        ver = sh("git", "log", "-1", "--format=%h", cwd=repo2).strip()
        body = f'<span class="footer-ver">Version {ver}, 2026-10-14 21:00 UTC</span>'.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


site = http.server.HTTPServer(("127.0.0.1", 0), Site)
threading.Thread(target=site.serve_forever, daemon=True).start()
ENV = dict(os.environ, PATH=os.path.join(box, "bin") + ":" + os.environ["PATH"], UPDATE_WARN_SECONDS="5",
           PORTAL_LOCAL_URL=f"http://127.0.0.1:{site.server_address[1]}/")
for k in ("REPO_DIR", "GMOD_HOME", "SERVER_DIR", "CSS_DIR", "STEAMCMD_DIR", "UPDATER_START", "GMOD_USER"):
    ENV.pop(k, None)

stop_game = threading.Event()
real = {"players": []}


def real_game():
    """The game in real time: runs commands every 0.5 s and writes status."""
    kick_at = None
    while not stop_game.is_set():
        d = os.path.join(portal2, "cmd")
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not name.endswith(".txt"):
                continue
            cmd = json.load(open(os.path.join(d, name)))
            os.remove(os.path.join(d, name))
            with open(os.path.join(box, "calls.txt"), "a") as f:
                f.write(f"game {cmd['action']} {cmd.get('seconds', '')}\n")
            if cmd["action"] == "update":
                kick_at = time.time() + cmd["seconds"]
            with open(os.path.join(portal2, "results.txt"), "a") as f:
                f.write(json.dumps({"id": name[:-4], "ok": True, "msg": "ok"}) + "\n")
        if kick_at and time.time() >= kick_at:
            real["players"], kick_at = [], None
        os.makedirs(portal2, exist_ok=True)
        with open(os.path.join(portal2, "status.json"), "w") as f:
            json.dump({"updated": int(time.time()), "players": real["players"]}, f)
        time.sleep(0.5)


threading.Thread(target=real_game, daemon=True).start()
update_sh = os.path.join(repo2, "scripts", "update.sh")


def calls():
    p = os.path.join(box, "calls.txt")
    return open(p).read().splitlines() if os.path.exists(p) else []


def run_tty(args, answer):
    """update.sh in a terminal, typing `answer` at the question."""
    master, slave = pty.openpty()
    p = subprocess.Popen(args, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV, text=True)
    os.close(slave)
    time.sleep(1.5)
    os.write(master, (answer + "\n").encode())
    out, _ = p.communicate(timeout=120)
    os.close(master)
    return p.returncode, out


# In the console with players on: it asks first, and "n" changes nothing
real["players"] = [player(1), player(2)]
time.sleep(1.2)
push_change(box, origin2, "x")
head0 = sh("git", "rev-parse", "HEAD", cwd=repo2).strip()
code, out = run_tty(["bash", update_sh], "n")
check(code == 0 and "2 player(s) on the server now: P1, P2" in out and "Cancelled" in out, f"the console asks first when players are on ({out[-300:]!r})")
check(sh("git", "rev-parse", "HEAD", cwd=repo2).strip() == head0 and not calls(), "answering no changes nothing")

# "y": countdown, kick, update, game and website restarted on the new code
code, out = run_tty(["bash", update_sh], "y")
c = calls()
check(code == 0 and "Update complete" in out, f"answering yes updates ({out[-400:]!r})")
check(sh("git", "rev-parse", "HEAD", cwd=repo2).strip() != head0, "the new change from GitHub is pulled")
order = [x for x in c if x.startswith(("game update", "systemctl stop gmod-surf", "steamcmd", "systemctl start gmod-surf",
                                       "systemctl restart surf-portal"))]
check([o.split()[0] + " " + o.split()[1] for o in order[:2]] == ["game update", "systemctl stop"] and "game update 5" in c,
      f"players get the countdown before the game stops ({order})")
starts_at = [i for i, x in enumerate(c) if x == "systemctl start gmod-surf"]
restart_at = [i for i, x in enumerate(c) if x == "systemctl restart surf-portal"]
check(starts_at and restart_at and restart_at[0] > starts_at[0] and "portal.sh ran" in c,
      f"the website is set up and restarted after the game starts ({c})")
check("The website runs the new version" in out, "the website is checked to run the new version")
st2 = json.load(open(os.path.join(home2, "update_state.json")))
check(st2.get("version") == sh("git", "log", "-1", "--format=%h", cwd=repo2).strip() and "Installed 1 change" in out,
      "the update is recorded, with what it installed")
cron_path = os.path.join(box, "etc", "cron.d", "gmod-surf")
cron = open(cron_path).read() if os.path.exists(cron_path) else f"missing; {os.listdir(os.path.join(box, 'etc', 'cron.d'))}; {out}"
check("*/15 * * * * root bash" in cron and "autoupdate.sh" in cron and "/scripts/update.sh" not in cron and "backup.sh" in cron,
      f"cron checks for updates every 15 minutes instead of updating at 05:00 ({cron[:3000]})")

# --yes (the website's button): no question, and no warning with nobody on
open(os.path.join(box, "calls.txt"), "w").close()
real["players"] = []
time.sleep(1.2)
r = subprocess.run(["bash", update_sh, "--yes"], stdin=subprocess.DEVNULL, capture_output=True, text=True, env=ENV, timeout=120)
check(r.returncode == 0 and "Update complete" in r.stdout and "Update now?" not in r.stdout
      and not any(x.startswith("game update") for x in calls()), "--yes doesn't ask, and nobody on means no warning")

# One at a time
lock = open(os.path.join(home2, ".update.lock"), "w")
fcntl.flock(lock, fcntl.LOCK_EX)
r = subprocess.run(["bash", update_sh, "--yes"], stdin=subprocess.DEVNULL, capture_output=True, text=True, env=ENV, timeout=60)
check(r.returncode == 0 and "already running" in r.stdout, "a second update doesn't start while one runs")
fcntl.flock(lock, fcntl.LOCK_UN)
lock.close()

# autoupdate.sh (cron): starts update.sh in its own unit once the server is empty
open(os.path.join(box, "calls.txt"), "w").close()
open(os.path.join(box, "bin", "systemd-run"), "w").write(f'#!/bin/sh\necho "systemd-run $*" >> "{box}/calls.txt"\n')
os.chmod(os.path.join(box, "bin", "systemd-run"), 0o755)
push_change(box, origin2, "y")
r = subprocess.run(["bash", os.path.join(repo2, "scripts", "autoupdate.sh")], capture_output=True, text=True, env=ENV, timeout=120)
runs = [x for x in calls() if x.startswith("systemd-run")]
check(r.returncode == 0 and len(runs) == 1 and "--unit=surfline-update" in runs[0] and "update.sh\" --yes" in runs[0]
      and "UPDATE_WHY=automatic, because the server is empty" in runs[0], f"the 15-minute check starts the update when empty ({runs}, {r.stdout}{r.stderr})")

stop_game.set()
site.shutdown()
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(box, ignore_errors=True)
print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
