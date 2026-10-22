#!/usr/bin/env python3
"""Server updates: who is on, when the automatic update may run, and the warning
players get before the server goes down. scripts/update.sh does the update
itself; this decides when and talks to the game.

  updater.py players     count of players online, then their names
  updater.py auto        every 15 minutes (cron, scripts/autoupdate.sh): starts
                         the update once something new is out and the server is
                         empty enough
  updater.py warn        30-second countdown in game, then everyone is
                         disconnected with a message saying why
  updater.py done REV    update.sh finished (REV = the commit it started from)
  updater.py site REV    checks the website restarted on commit REV

An update is due when there are new changes on GitHub, a new Garry's Mod or
CS:S build on Steam, or a new version of a map's Workshop item (players would
download it and get "Client's map differs from the server's" until the server
has it too; those maps sit out map votes meanwhile). The automatic update then
waits for an empty server. After two days of waiting it also goes ahead with 3
or fewer players on, and after four days whatever the count. Its state is
$GMOD_HOME/update_state.json, which the website's admin page shows.

Paths come from the environment (common.sh sets them): REPO_DIR, GMOD_HOME,
GMOD_USER, SERVER_DIR, CSS_DIR, STEAMCMD_DIR.
"""
import fcntl
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("REPO_DIR") or os.path.dirname(HERE)
HOME = os.environ.get("GMOD_HOME") or "/home/gmod"
GMOD_USER = os.environ.get("GMOD_USER") or "gmod"
SERVER_DIR = os.environ.get("SERVER_DIR") or os.path.join(HOME, "server")
CSS_DIR = os.environ.get("CSS_DIR") or os.path.join(HOME, "css")
STEAMCMD = os.path.join(os.environ.get("STEAMCMD_DIR") or os.path.join(HOME, "steamcmd"), "steamcmd.sh")
DATA_DIR = os.path.join(SERVER_DIR, "garrysmod", "data", "surfline")
PORTAL_DATA = os.environ.get("PORTAL_DATA") or os.path.join(DATA_DIR, "portal")
MAPS_INSTALLED = os.path.join(HOME, "workshop", "installed.json")  # scripts/maps.sh keeps it
STATE_FILE = os.path.join(HOME, "update_state.json")
SITE_URL = os.environ.get("PORTAL_LOCAL_URL") or "http://127.0.0.1:8090/"

DAY = 86400
WAIT_FEW = 2 * DAY      # after this, 3 or fewer players don't stop the update
WAIT_ANY = 4 * DAY      # after this, nothing does
FEW = 3
WARN_SECONDS = int(os.environ.get("UPDATE_WARN_SECONDS") or 30)
STEAM_EVERY = 3600      # how often Steam is asked for new Garry's Mod builds
MAPS_EVERY = 1800       # how often the Workshop is asked whether installed maps changed
STEAM_BLIND = DAY       # Steam unreadable this long: update anyway, as the old nightly did
RETRY_AFTER = DAY       # something an update didn't manage to install waits this long
LOG_WAIT_EVERY = 3 * 3600
STATUS_FRESH = 30       # status.json older than this: the game isn't running

WORKSHOP_API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
KICK_MESSAGE = "The server is updating to a new version. It is back in a few minutes, just rejoin!"
# Steam app id -> (name, install folder)
APPS = {"4020": ("Garry's Mod", SERVER_DIR), "232330": ("Counter-Strike: Source content", CSS_DIR)}

clock = time.time   # tests replace these
sleep = time.sleep


def is_root():
    return os.geteuid() == 0


def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def when(t):
    return time.strftime("%b %d %H:%M", time.localtime(t))


# ------------------------------------------------------------------ state

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)  # the website (gmod user) shows it
    os.replace(tmp, STATE_FILE)


# ------------------------------------------------------------------ the game

def players_online():
    """Players in status.json (humans only; the game writes it every 5 s), or []
    when the game isn't running."""
    try:
        with open(os.path.join(PORTAL_DATA, "status.json"), encoding="utf-8", errors="replace") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(st, dict) or clock() - float(st.get("updated") or 0) > STATUS_FRESH:
        return []
    return [p for p in st.get("players") or [] if isinstance(p, dict)]


def send_command(cmd):
    """Drops a command for the game, like the website does (sv_portal.lua runs
    cmd/*.txt every 2 s and answers in results.txt). Returns its id."""
    d = os.path.join(PORTAL_DATA, "cmd")
    os.makedirs(d, exist_ok=True)
    cid = f"{int(clock() * 1000)}_{secrets.token_hex(4)}"
    tmp = os.path.join(d, cid + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dict(cmd, by="update"), f)
    os.chmod(tmp, 0o644)
    if is_root():  # the game runs as the folder's owner and deletes the file
        s = os.stat(d)
        try:
            os.chown(tmp, s.st_uid, s.st_gid)
        except OSError:
            pass
    os.replace(tmp, os.path.join(d, cid + ".txt"))
    return cid


def wait_result(cid, timeout):
    """The game's answer to command cid, or None if it didn't answer in time."""
    end = clock() + timeout
    while True:
        try:
            with open(os.path.join(PORTAL_DATA, "results.txt"), encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and r.get("id") == cid:
                        return r
        except OSError:
            pass
        if clock() >= end:
            return None
        sleep(1)


def wait_empty(timeout):
    end = clock() + timeout
    while players_online() and clock() < end:
        sleep(2)
    return not players_online()


def warn(seconds=WARN_SECONDS):
    """Counts down in game, then disconnects everyone with KICK_MESSAGE, so
    nobody just loses connection. Returns once the server is empty (or the time
    is up)."""
    ps = players_online()
    if not ps:
        log("Nobody is on the server, so no countdown is needed")
        return
    log(f"Telling {plural(len(ps), 'player')} in game: the server goes down for the update in {seconds} seconds")
    res = wait_result(send_command({"action": "update", "seconds": seconds, "reason": KICK_MESSAGE}), 10)
    if res is None:
        log("The game didn't answer, so it is stopped without a countdown")
        return
    if not res.get("ok"):
        # A gamemode from before the countdown: the same with chat and kicks
        log("The game has no update countdown yet, so it gets chat messages and kicks instead")
        send_command({"action": "say", "text": f"The server restarts for an update in {seconds} seconds. Your times and coins are saved."})
        sleep(max(0, seconds - 10))
        send_command({"action": "say", "text": "The server restarts for an update in 10 seconds. Rejoin in a few minutes!"})
        sleep(min(10, seconds))
        for p in players_online():
            if re.fullmatch(r"7656\d{13}", str(p.get("steamid") or "")):
                send_command({"action": "kick", "steamid": p["steamid"], "reason": KICK_MESSAGE})
        wait_empty(15)
        return
    if wait_empty(seconds + 15):
        log("Everyone was told and disconnected")
    else:
        log("Some players are still shown as online; stopping the game anyway")


# ------------------------------------------------------------------ what's new

def git(*args, timeout=120):
    try:
        return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def git_behind(fetch=True):
    """Commits on GitHub that aren't installed, or None if that can't be told."""
    if not os.path.isdir(os.path.join(REPO, ".git")):
        return None
    if fetch:
        r = git("fetch", "--quiet")
        if not r or r.returncode != 0:
            return None
    r = git("rev-list", "--count", "HEAD..@{u}", timeout=30)
    if not r or r.returncode != 0 or not r.stdout.strip().isdigit():
        return None
    return int(r.stdout.strip())


def git_head():
    r = git("rev-parse", "HEAD", timeout=30)
    return r.stdout.strip() if r and r.returncode == 0 else ""


def git_short():
    """The short commit, the way the website's footer shows it."""
    r = git("log", "-1", "--format=%h", timeout=30)
    return r.stdout.strip() if r and r.returncode == 0 else ""


def installed_build(app):
    path = os.path.join(APPS[app][1], "steamapps", f"appmanifest_{app}.acf")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            m = re.search(r'"buildid"\s+"(\d+)"', f.read())
        return m.group(1) if m else None
    except OSError:
        return None


def parse_app_info(text):
    """{app id: public build id} from SteamCMD's app_info_print output."""
    out = {}
    parts = re.split(r"AppID\s*:\s*(\d+)", text)
    for i in range(1, len(parts) - 1, 2):
        app, body = parts[i], parts[i + 1]
        b = body.find('"branches"')
        if b < 0:
            continue
        m = re.search(r'"public"\s*\{([^{}]*)\}', body[b:])
        n = m and re.search(r'"buildid"\s+"(\d+)"', m.group(1))
        if n:
            out[app] = n.group(1)
    return out


def steam_latest():
    """{app id: newest public build} from Steam, {} if it couldn't be read."""
    cmd = [STEAMCMD, "+login", "anonymous", "+app_info_update", "1"]
    for app in APPS:
        cmd += ["+app_info_print", app]
    cmd.append("+quit")
    if is_root():
        cmd = ["sudo", "-u", GMOD_USER, "-H"] + cmd
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return {}
    return parse_app_info(r.stdout or "")


# ------------------------------------------------------------------ maps

def read_names(path):
    """The first word of each line, without # comments."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [ln.split("#", 1)[0].split()[0] for ln in f if ln.split("#", 1)[0].strip()]
    except OSError:
        return []


def map_sources():
    """{map: Workshop item} for the maps players download (map_ws.txt, which
    scripts/maps.py writes)."""
    out = {}
    try:
        with open(os.path.join(DATA_DIR, "map_ws.txt"), encoding="utf-8", errors="replace") as f:
            for ln in f:
                parts = ln.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    out[parts[0]] = parts[1]
    except OSError:
        pass
    return out


def workshop_times(ids):
    """{Workshop item: when it last changed} from Steam, or None if Steam
    couldn't be asked."""
    out = {}
    for i in range(0, len(ids), 100):
        part = ids[i:i + 100]
        fields = {"itemcount": len(part)}
        for j, fid in enumerate(part):
            fields[f"publishedfileids[{j}]"] = fid
        req = urllib.request.Request(WORKSHOP_API, data=urllib.parse.urlencode(fields).encode())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                details = json.load(r)["response"].get("publishedfiledetails") or []
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        for d in details:
            if isinstance(d, dict) and d.get("result") == 1 and isinstance(d.get("time_updated"), int):
                out[str(d.get("publishedfileid"))] = d["time_updated"]
    return out


def outdated_maps(latest):
    """Installed maps whose Workshop item changed after the server got its copy.
    Players download the new one, so they'd get "Client's map differs from the
    server's" until the next update installs it."""
    try:
        with open(MAPS_INSTALLED, encoding="utf-8") as f:
            installed = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(installed, dict):
        return []
    out = []
    for m, fid in sorted(map_sources().items()):
        info, new = installed.get(fid), latest.get(fid)
        if not isinstance(info, dict) or not isinstance(new, int):
            continue  # not installed by maps.py, or Steam didn't say
        have = info.get("updated")
        if not isinstance(have, int) or new > have:
            out.append(m)
    return out


def write_outdated(maps):
    """outdated_maps.txt keeps those maps out of map votes until they're
    installed (sv_mapvote.lua)."""
    path = os.path.join(DATA_DIR, "outdated_maps.txt")
    text = "".join(m + "\n" for m in maps)
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    except OSError:
        if not maps:
            return
    if not os.path.isdir(DATA_DIR):
        return
    if not maps:
        os.remove(path)
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    if is_root():  # like the game's other files there
        s = os.stat(DATA_DIR)
        try:
            os.chown(tmp, s.st_uid, s.st_gid)
        except OSError:
            pass
    os.replace(tmp, path)


def names(maps, most=3):
    return ", ".join(maps[:most]) + (f" and {len(maps) - most} more" if len(maps) > most else "")


def map_news(st, t, hold):
    """Map items for whats_new; keeps st["maps_latest"] and outdated_maps.txt
    up to date."""
    items = []
    if t - st.get("maps_checked", 0) >= MAPS_EVERY:
        st["maps_checked"] = t
        ids = sorted(set(map_sources().values()))
        latest = workshop_times(ids) if ids else {}
        if latest is not None:
            st["maps_latest"] = latest
    old = outdated_maps(st.get("maps_latest") or {})
    write_outdated(old)
    if old and t >= hold.get("maps", 0):
        items.append({"kind": "maps", "text": f"new Workshop version of {names(old)}"})
    # Maps players couldn't join (sv_joinguard.lua lists them); the map
    # installer downloads them again
    failed = read_names(os.path.join(DATA_DIR, "join_failed.txt"))
    if failed and t >= hold.get("joinfail", 0):
        items.append({"kind": "joinfail", "text": f"a fresh copy of {names(failed)} (players couldn't join it)"})
    return items


def whats_new(st, t):
    """What an update would install now: [{"kind", "text"}]. Updates the Steam
    fields of st."""
    hold = st.get("hold") or {}
    items = []
    n = git_behind()
    if n and t >= hold.get("git", 0):
        items.append({"kind": "git", "text": plural(n, "new change") + " from GitHub"})
    st.setdefault("steam_since", t)
    if t - st.get("steam_checked", 0) >= STEAM_EVERY:
        st["steam_checked"] = t
        latest = steam_latest()
        if latest:
            st["steam_ok"], st["steam_latest"] = t, latest
    latest = st.get("steam_latest") or {}
    for app, (name, _) in APPS.items():
        have, new = installed_build(app), latest.get(app)
        if have and new and new.isdigit() and int(new) > int(have) and t >= hold.get(app, 0):
            items.append({"kind": app, "text": name + " update"})
    if t - st.get("steam_ok", st["steam_since"]) >= STEAM_BLIND and t >= hold.get("steam", 0):
        items.append({"kind": "steam", "text": "Garry's Mod check (Steam's version couldn't be read for a day)"})
    try:
        items += map_news(st, t, hold)
    except Exception as ex:  # never let the map check stop other updates
        log(f"Couldn't check the maps for Workshop updates: {ex!r}")
    return items


# ------------------------------------------------------------------ when

def decide(due_since, players, t):
    """(go, why) for an update due since due_since with this many players on."""
    waited = t - due_since
    if players == 0:
        return True, "the server is empty"
    if waited >= WAIT_ANY:
        return True, f"it waited 4 days and {plural(players, 'player')} are on"
    if waited >= WAIT_FEW and players <= FEW:
        return True, f"it waited 2 days and only {plural(players, 'player')} are on"
    return False, ""


def waiting_text(due_since, players):
    if due_since + WAIT_FEW > clock():
        return (f"{plural(players, 'player')} on, so it waits for an empty server. From {when(due_since + WAIT_FEW)} "
                f"it also goes ahead with {FEW} or fewer on, and from {when(due_since + WAIT_ANY)} no matter what")
    return (f"{plural(players, 'player')} on, so it waits for {FEW} or fewer. "
            f"From {when(due_since + WAIT_ANY)} it goes ahead no matter what")


def update_running():
    r = subprocess.run(["systemctl", "is-active", "--quiet", "surfline-update"], capture_output=True)
    return r.returncode == 0


def start_update(why):
    """update.sh in its own unit, like the website's Update button, so the
    admin page shows it running and only one runs at a time."""
    cmd = os.environ.get("UPDATER_START")  # tests
    if cmd:
        return subprocess.run([cmd, why]).returncode == 0
    subprocess.run(["systemctl", "reset-failed", "surfline-update"], capture_output=True)
    r = subprocess.run(["systemd-run", "--unit=surfline-update", "--collect", f"--setenv=UPDATE_WHY={why}",
                        "/bin/bash", "-c",
                        f'bash "{REPO}/scripts/update.sh" --yes >> "{HOME}/update.log" 2>&1'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log("Could not start the update: " + (r.stderr or r.stdout).strip()[-300:])
    return r.returncode == 0


def auto():
    lock = open(os.path.join(HOME, ".updater.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # the last check is still running (a slow fetch)
    if not os.environ.get("UPDATER_START") and update_running():
        return 0
    t = clock()
    st = load_state()
    items = whats_new(st, t)
    st["checked"] = t
    if not items:
        if st.get("due_since"):
            log("Nothing left to install (it was installed another way)")
        for k in ("due_since", "due", "due_kinds", "logged", "players"):
            st.pop(k, None)
        save_state(st)
        return 0
    texts = ", ".join(i["text"] for i in items)
    if not st.get("due_since"):
        st["due_since"] = t
        log(f"Update ready: {texts}")
    st["due"], st["due_kinds"] = [i["text"] for i in items], [i["kind"] for i in items]
    n = len(players_online())
    st["players"] = n
    go, why = decide(st["due_since"], n, t)
    if not go:
        if t - st.get("logged", 0) >= LOG_WAIT_EVERY:
            log(f"Update waiting: {waiting_text(st['due_since'], n)}")
            st["logged"] = t
        save_state(st)
        return 0
    log(f"Updating now, because {why}: {texts}")
    st["started"] = t
    save_state(st)
    return 0 if start_update(f"automatic, because {why}") else 1


def done(before):
    """update.sh finished: what was due is cleared, and what it didn't manage to
    install waits a day before it counts again (so a broken download can't
    restart the server every 15 minutes)."""
    t = clock()
    st = load_state()
    hold = {k: v for k, v in (st.get("hold") or {}).items() if v > t}
    missed = []
    if git_behind(fetch=False):
        hold["git"] = t + RETRY_AFTER
        missed.append("the new changes from GitHub")
    latest = st.get("steam_latest") or {}
    for app, (name, _) in APPS.items():
        have, new = installed_build(app), latest.get(app)
        if have and new and new.isdigit() and int(new) > int(have):
            hold[app] = t + RETRY_AFTER
            missed.append(name)
    if "steam" in (st.get("due_kinds") or []):
        hold["steam"] = t + RETRY_AFTER
    try:
        still = outdated_maps(st.get("maps_latest") or {})
        write_outdated(still)
        if still:
            hold["maps"] = t + RETRY_AFTER
            missed.append(f"the new Workshop version of {names(still)}")
        if read_names(os.path.join(DATA_DIR, "join_failed.txt")):
            hold["joinfail"] = t + RETRY_AFTER
            missed.append("the maps players couldn't join")
    except Exception as ex:
        log(f"Couldn't check the maps: {ex!r}")
    for k in ("due_since", "due", "due_kinds", "logged", "players", "started"):
        st.pop(k, None)
    st["hold"], st["last_update"], st["version"] = hold, t, git_short()
    save_state(st)
    if missed:
        log(f"WARNING: this update didn't install {', '.join(missed)}; the automatic update tries again from {when(t + RETRY_AFTER)}")
    after = git_head()
    if before and after and before != after:
        r = git("log", "--format=  %h %s", f"{before}..{after}", timeout=30)
        if r and r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.rstrip().splitlines()
            log(f"Installed {plural(len(lines), 'change')}:\n" + "\n".join(lines[:30]))
    return 0


def site(expected, tries=20):
    """1 unless the website answers with commit `expected` in its footer."""
    seen = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(SITE_URL, timeout=5) as r:
                body = r.read(500000).decode("utf-8", "replace")
            m = re.search(r"Version ([0-9a-f]{4,40}),", body)
            seen = m.group(1) if m else "no version"
            if seen == expected:
                log(f"The website runs the new version ({expected})")
                return 0
        except OSError as ex:
            seen = f"no answer ({ex})"
        sleep(2)
    log(f"WARNING: the website should run {expected} but shows {seen}. Check: systemctl status surf-portal")
    return 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "players":
        ps = players_online()
        print(len(ps))
        print(", ".join(str(p.get("name") or "?") for p in ps))
        return 0
    if cmd == "auto":
        return auto()
    if cmd == "warn":
        warn(int(argv[2]) if len(argv) > 2 else WARN_SECONDS)
        return 0
    if cmd == "done":
        return done(argv[2] if len(argv) > 2 else "")
    if cmd == "site":
        return site(argv[2] if len(argv) > 2 else git_short())
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
