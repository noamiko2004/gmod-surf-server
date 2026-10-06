#!/usr/bin/env python3
"""Server health check: services, logs of the last 24 hours, website, Discord
bridge, updates, maps, backups, disk. Run as root on the VPS:

    sudo surfcheck            (installed by deploy.sh; same as the line below)
    sudo python3 /home/gmod/surfline/scripts/health.py

Prints a one-screen summary. Also writes the full report to
GMOD_HOME/health.txt (shown on the website's Admin > Logs page) and a public
summary with no secrets to GMOD_HOME/health.json (served at /health.json, so
Claude can check the server without screenshots). Cron runs it every 10
minutes with --quiet.
"""
import argparse, json, os, re, shutil, sqlite3, subprocess, sys, time, urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAY = 86400
OK, WARN, BAD = "ok", "warn", "bad"
MARK = {OK: "OK ", WARN: "?? ", BAD: "!! "}
UNITS = [("gmod-surf", "Game server"), ("surf-portal", "Website"), ("surf-discord", "Discord bot"), ("caddy", "HTTPS (Caddy)")]


def read_config(path):
    conf = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line.strip())
                if m:
                    conf[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    return conf


def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace")
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired) as ex:
        return -1, str(ex)


# ------------------------------------------------------------------ redaction
# health.json is public: no addresses, keys, links or IPs of players
_SECRETISH = [
    (re.compile(r"https?://\S+"), "<link>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\b[A-Za-z0-9_\-.]{32,}\b"), "<key>"),
    (re.compile(r"(?i)(token|secret|password|passwd|key|authorization)\s*[=:]\s*\S+"), r"\1=<hidden>"),
]


def redact(s):
    s = str(s)
    for rx, rep in _SECRETISH:
        s = rx.sub(rep, s)
    return s[:240]


# -------------------------------------------------------------------- checks
class Report:
    def __init__(self):
        self.items = []   # (level, area, line)
        self.details = {}  # area -> list of lines (full report only)

    def add(self, level, area, line, details=None):
        self.items.append((level, area, line))
        if details:
            self.details.setdefault(area, []).extend(details)

    def worst(self):
        lv = [i[0] for i in self.items]
        return BAD if BAD in lv else WARN if WARN in lv else OK


def journal(unit, since=DAY, n=50000):
    code, out = run(["journalctl", "-u", unit, "--since", f"-{since}s", "-o", "cat", "--no-pager", "-n", str(n)], timeout=60)
    return out.splitlines() if code == 0 else []


def unit_state(unit):
    code, out = run(["systemctl", "show", unit, "-p", "ActiveState,SubState,NRestarts,ActiveEnterTimestamp,LoadState,UnitFileState"])
    d = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        d[k] = v
    return d


def ago(sec):
    if sec is None:
        return "never"
    sec = int(max(0, sec))
    if sec < 120:
        return f"{sec}s ago"
    if sec < 7200:
        return f"{sec // 60} min ago"
    if sec < 2 * DAY:
        return f"{sec // 3600} h ago"
    return f"{sec // DAY} days ago"


def check_services(r, units=UNITS):
    for unit, label in units:
        s = unit_state(unit)
        if s.get("LoadState") == "not-found":
            r.add(BAD if unit != "surf-discord" else WARN, label, f"{label}: not installed ({unit})")
            continue
        active = s.get("ActiveState", "?")
        restarts = int(s.get("NRestarts") or 0)
        since = s.get("ActiveEnterTimestamp", "")
        if active != "active":
            r.add(BAD, label, f"{label}: {active} ({s.get('SubState', '?')}). See: journalctl -u {unit} -n 50")
        elif restarts:
            r.add(WARN, label, f"{label}: running, but restarted {restarts} times (crash loop?) since {since}")
        else:
            r.add(OK, label, f"{label}: running since {since}")


# Lua errors on a GMOD server: "[ERROR] path.lua:12: message" or "Lua Error: ..."
LUA_ERR = re.compile(r"^\s*(?:\[ERROR\]|Lua Error:|\[(?:surf|SURF)[^\]]*\]\s*(?:error|ERROR))\s*(.*)$")
CRASH = re.compile(r"(Segmentation fault|core dumped|Server restart in|FATAL ERROR|Host_Error|Engine Error)", re.I)
NUM = re.compile(r"\b\d+\b")


def signature(msg):
    """Same error with other numbers/names counts once: keep file:line, mask the rest's numbers."""
    m = re.match(r"^(\S+\.lua:\d+):\s*(.*)$", msg)
    if m:
        return m.group(1) + ": " + NUM.sub("N", m.group(2))[:160]
    return NUM.sub("N", msg)[:180]


def top(counter, k=5):
    return [f"{n}x {s}" for s, n in counter.most_common(k)]


def check_game_log(r, lines):
    errs, crashes = Counter(), Counter()
    for i, line in enumerate(lines):
        m = LUA_ERR.match(line)
        if m:
            msg = m.group(1).strip()
            if not msg and i + 1 < len(lines):
                msg = lines[i + 1].strip()
            errs[signature(msg)] += 1
        elif CRASH.search(line):
            crashes[signature(line.strip())] += 1
    total = sum(errs.values())
    if crashes:
        r.add(BAD, "Game log", f"Game crashed or errored hard {sum(crashes.values())} times in 24 h", top(crashes))
    if total:
        lvl = BAD if total >= 50 else WARN
        r.add(lvl, "Game log", f"{total} Lua errors in 24 h ({len(errs)} different). Top: {next(iter(top(errs, 1)))}", top(errs, 10))
    elif not crashes:
        r.add(OK, "Game log", f"No Lua errors in 24 h ({len(lines)} log lines)")
    return errs


PY_ERR = re.compile(r"^(?:ERROR|CRITICAL)\b|Traceback \(most recent call last\)|^\w+(?:\.\w+)*(?:Error|Exception): ")
PY_WARN = re.compile(r"^WARNING\b")
ACCESS_5XX = re.compile(r'"[A-Z]+ (\S+) HTTP/[\d.]+" (5\d\d) ')
PORTAL_ERR = re.compile(r"^\[(?:portal|tebex)\].*\b(error|failed|exception|could not)\b", re.I)


def check_py_log(r, area, lines):
    errs, warns = Counter(), Counter()
    tb = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("Traceback"):
            tb += 1
            # the exception is the first unindented line after the traceback
            for nxt in lines[i + 1:i + 60]:
                if nxt and not nxt.startswith(" "):
                    errs[signature(nxt.strip())] += 1
                    break
        elif ACCESS_5XX.search(s):
            m = ACCESS_5XX.search(s)
            errs[f"HTTP {m.group(2)} on {m.group(1).split('?')[0][:80]}"] += 1
        elif PORTAL_ERR.search(s):
            errs[signature(s)] += 1
        elif PY_ERR.search(s) and not re.match(r"^\w+(?:\.\w+)*(?:Error|Exception): ", s):
            errs[signature(s)] += 1
        elif PY_WARN.search(s):
            warns[signature(s)] += 1
    n = sum(errs.values())
    if n:
        r.add(WARN if n < 20 else BAD, area, f"{area}: {n} errors in 24 h. Top: {next(iter(top(errs, 1)))}", top(errs, 8) + top(warns, 4))
    elif warns:
        r.add(OK, area, f"{area}: no errors, {sum(warns.values())} warnings in 24 h", top(warns, 5))
    else:
        r.add(OK, area, f"{area}: no errors in 24 h")
    return errs


def check_caddy_log(r, lines):
    errs = Counter()
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            if " error" in line.lower():
                errs[signature(line.strip())] += 1
            continue
        if isinstance(d, dict) and d.get("level") in ("error", "fatal"):
            errs[signature(f"{d.get('logger', '')}: {d.get('msg', '')} {d.get('error', '')}".strip())] += 1
    if errs:
        r.add(WARN, "HTTPS (Caddy)", f"Caddy: {sum(errs.values())} errors in 24 h. Top: {next(iter(top(errs, 1)))}", top(errs, 5))


def http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read(200000)
    except Exception as ex:  # noqa: BLE001 - any failure is the finding
        return None, str(ex).encode()


def check_website(r, port=8090):
    code, body = http_get(f"http://127.0.0.1:{port}/healthz")
    if code != 200:
        r.add(BAD, "Website", f"Website does not answer on 127.0.0.1:{port} ({body.decode(errors='replace')[:80]})")
        return
    code, body = http_get(f"http://127.0.0.1:{port}/api/status")
    try:
        st = json.loads(body)
    except ValueError:
        st = {}
    if not st.get("online"):
        r.add(BAD, "Game data", "Website says the game server is offline (no fresh status.json from the game)")
    else:
        r.add(OK, "Game data", f"Game reports in: {len(st.get('players') or [])}/{st.get('maxplayers')} players on {st.get('map')}, data {int(st.get('age') or 0)}s old")


def file_age(path, now):
    try:
        return now - os.path.getmtime(path)
    except OSError:
        return None


def check_bridge(r, data, now):
    root = os.path.join(data, "discord")
    if not os.path.isdir(root):
        r.add(WARN, "Discord bridge", "Discord bridge folder missing (game never started the bridge)")
        return
    lines = []
    for sub, who in (("to_discord", "bot"), ("to_game", "game")):
        d = os.path.join(root, sub)
        try:
            files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json")]
        except OSError:
            files = []
        stale = [f for f in files if (file_age(f, now) or 0) > 120]
        if stale:
            oldest = max(file_age(f, now) or 0 for f in stale)
            lines.append((WARN, f"{len(files)} messages waiting in {sub} (oldest {ago(oldest)}): the {who} is not reading them"))
    if lines:
        for lv, line in lines:
            r.add(lv, "Discord bridge", "Bridge: " + line)
    else:
        r.add(OK, "Discord bridge", "Bridge: no messages stuck between game and Discord")


def check_links(r, data, home, conf):
    try:
        with open(os.path.join(data, "links.json"), encoding="utf-8") as f:
            links = json.load(f)
    except (OSError, ValueError):
        links = {}
    if links.get("discord"):
        r.add(OK, "Links", "!discord has an invite link")
    elif os.path.isfile(os.path.join(home, "discord", "invite.txt")):
        r.add(WARN, "Links", "!discord has no link, though the bot wrote invite.txt (run update.sh to pick it up)")
    else:
        r.add(WARN, "Links", "!discord has no link: set DISCORD_URL in config.env or let the bot make one")


UPDATE_DONE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Update complete")
PROBLEM = re.compile(r"WARNING|ERROR|failed|problems|Could not|Error!|No space", re.I)


def check_updates(r, home, now):
    path = os.path.join(home, "update.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-3000:]
    except OSError:
        r.add(WARN, "Updates", "No update.log yet (the nightly update never ran)")
        return
    last_i, last_t = None, None
    for i, line in enumerate(lines):
        m = UPDATE_DONE.match(line)
        if m:
            last_i = i
            last_t = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
    if last_t is None:
        r.add(BAD, "Updates", "update.log has no finished update")
        return
    start = 0
    for i in range(last_i, -1, -1):
        if "Pulling latest server files" in lines[i] or "Backing up before update" in lines[i]:
            start = i
            break
    probs = [l.strip() for l in lines[start:last_i] if PROBLEM.search(l)]
    age = now - last_t
    lvl = WARN if age > 1.5 * DAY or probs else OK
    msg = f"Last update finished {ago(age)}"
    if probs:
        msg += f" with {len(probs)} problem lines: {probs[0][:100]}"
    r.add(lvl, "Updates", msg, probs[:10])
    if not os.path.isfile("/etc/cron.d/gmod-surf"):
        r.add(WARN, "Updates", "Nightly update and backup are not scheduled (/etc/cron.d/gmod-surf missing)")


def check_backups(r, home, now):
    d = os.path.join(home, "backups")
    try:
        dbs = [os.path.join(d, f) for f in os.listdir(d) if f.startswith("sv_") and f.endswith(".db")]
    except OSError:
        dbs = []
    if not dbs:
        r.add(WARN, "Backups", "No database backups in " + d)
        return
    newest = min(file_age(f, now) or 1e12 for f in dbs)
    r.add(OK if newest < 1.5 * DAY else WARN, "Backups", f"{len(dbs)} database backups, newest {ago(newest)}")


def check_maps(r, gm, data, home):
    maps = [f for f in os.listdir(os.path.join(gm, "maps")) if f.startswith("surf_") and f.endswith(".bsp")] if os.path.isdir(os.path.join(gm, "maps")) else []
    try:
        with open(os.path.join(data, "bad_zones.txt"), encoding="utf-8") as f:
            bad = [l.split()[0] for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        bad = []
    lvl = BAD if len(maps) < 5 else WARN if len(maps) < 25 else OK
    msg = f"{len(maps)} surf maps installed"
    if bad:
        msg += f", {len(bad)} without a working start/end (kept out of votes)"
    r.add(lvl, "Maps", msg, ["Without working zones: " + ", ".join(bad[:40])] if bad else None)


def check_db(r, gm):
    path = os.path.join(gm, "sv.db")
    if not os.path.isfile(path):
        r.add(BAD, "Database", "sv.db not found (records, ranks, shop)")
        return
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        res = con.execute("PRAGMA quick_check").fetchone()[0]
        con.close()
    except sqlite3.Error as ex:
        r.add(WARN, "Database", f"Could not check sv.db: {ex}")
        return
    size = os.path.getsize(path) / 1e6
    r.add(OK if res == "ok" else BAD, "Database", f"sv.db {'is fine' if res == 'ok' else 'is DAMAGED: ' + res} ({size:.1f} MB)")


def check_system(r, home):
    du = shutil.disk_usage(home if os.path.isdir(home) else "/")
    pct = du.used * 100 // du.total
    free_gb = du.free / 1e9
    r.add(BAD if free_gb < 2 else WARN if pct >= 85 else OK, "System", f"Disk {pct}% used, {free_gb:.1f} GB free")
    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0])
        avail = mem["MemAvailable"] / 1e6
        total = mem["MemTotal"] / 1e6
        load = os.getloadavg()[1]
        cpus = os.cpu_count() or 1
        lvl = BAD if avail < 0.2 else WARN if avail < 0.5 or load > cpus * 1.5 else OK
        r.add(lvl, "System", f"Memory {avail:.1f} of {total:.1f} GB free, load {load:.2f} on {cpus} CPUs")
    except (OSError, KeyError, ValueError):
        pass
    code, out = run(["journalctl", "-k", "--since", "-1d", "-o", "cat", "--no-pager", "-g", "Out of memory|oom-kill"], timeout=20)
    if code == 0 and out.strip():
        r.add(BAD, "System", f"The kernel killed programs for lack of memory {len(out.strip().splitlines())} times in 24 h")


def check_version(r, repo):
    code, head = run(["git", "-C", repo, "rev-parse", "--short", "HEAD"])
    head = head.strip() if code == 0 else "unknown"
    code, out = run(["git", "-C", repo, "ls-remote", "origin", "refs/heads/main"], timeout=15)
    remote = out.split()[0][:len(head)] if code == 0 and out.strip() else ""
    if remote and remote != head:
        r.add(WARN, "Version", f"Running {head}; GitHub has {remote} (run update.sh, or wait for the 05:00 update)")
    else:
        r.add(OK, "Version", f"Running {head}" + (", same as GitHub" if remote else ""))
    return head


# ------------------------------------------------------------------- report
def collect(conf, repo, now=None):
    now = now or time.time()
    home = conf.get("GMOD_HOME") or f"/home/{conf.get('GMOD_USER') or 'gmod'}"
    gm = os.path.join(home, "server", "garrysmod")
    data = os.path.join(gm, "data", "surfline")
    r = Report()
    version = check_version(r, repo)
    check_services(r)
    check_game_log(r, journal("gmod-surf"))
    check_website(r)
    check_py_log(r, "Website log", journal("surf-portal"))
    check_py_log(r, "Discord bot log", journal("surf-discord"))
    check_caddy_log(r, journal("caddy"))
    check_bridge(r, data, now)
    check_links(r, data, home, conf)
    check_updates(r, home, now)
    check_backups(r, home, now)
    check_maps(r, gm, data, home)
    check_db(r, gm)
    check_system(r, home)
    return r, version, home


def render_text(r, version, now, full):
    t = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    worst = r.worst()
    head = {OK: "All good", WARN: "Some things to look at", BAD: "PROBLEMS FOUND"}[worst]
    out = [f"SURF health {t}  version {version}  {head}"]
    order = {BAD: 0, WARN: 1, OK: 2}
    for lv, area, line in sorted(r.items, key=lambda i: order[i[0]]):
        out.append(MARK[lv] + line)
    if full and r.details:
        out.append("")
        out.append("Details")
        for area, lines in r.details.items():
            out.append(f"  {area}:")
            out.extend("    " + l for l in lines)
    return "\n".join(out) + "\n"


def render_json(r, version, now):
    return {
        "time": int(now),
        "version": version,
        "status": r.worst(),
        "checks": [{"level": lv, "area": a, "text": redact(line)} for lv, a, line in r.items],
        "details": {a: [redact(l) for l in lines[:12]] for a, lines in r.details.items()},
    }


def write_atomic(path, text, mode=0o644):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true", help="only write the report files (for cron)")
    ap.add_argument("--full", action="store_true", help="print the details too")
    ap.add_argument("--repo", default=ROOT)
    a = ap.parse_args(argv)
    conf = read_config(os.path.join(a.repo, "config.env"))
    now = time.time()
    r, version, home = collect(conf, a.repo, now)
    full_txt = render_text(r, version, now, True)
    if os.path.isdir(home) and os.access(home, os.W_OK):
        write_atomic(os.path.join(home, "health.txt"), full_txt)
        write_atomic(os.path.join(home, "health.json"), json.dumps(render_json(r, version, now), indent=1) + "\n")
    if not a.quiet:
        sys.stdout.write(full_txt if a.full else render_text(r, version, now, False))
        if not a.full:
            print("More: sudo surfcheck full   (or the website, Admin > Logs)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        sys.argv[1] = "--full"
    sys.exit(main())
