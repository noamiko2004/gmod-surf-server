#!/usr/bin/env python3
"""Build a realistic fake server tree and run the portal against it.

  python3 portal/dev/demo.py [--dir /tmp/surf-demo] [--port 8091] [--shots OUTDIR]

Creates config.env, a garrysmod dir with map files, data files, a SQLite DB
with players/times/records, keeps status.json fresh, prints an owner session
cookie, and (with --shots) takes Playwright screenshots via screenshots.js.
"""
import argparse
import hashlib
import hmac
import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORTAL = os.path.dirname(HERE)
OWNER = "76561198000000042"

MAPS = [  # name, tier, mapper, zoned, base time
    ("surf_kitsune", 1, "Kitsune", True, 92.0),
    ("surf_utopia_v3", 1, "Utopia team", True, 71.5),
    ("surf_mesa", 1, "Mesa", True, 118.2),
    ("surf_beginner", 1, "Bombs", True, 64.9),
    ("surf_forbidden_ways_ksf", 1, "Forbidden", True, 105.3),
    ("surf_lux", 2, "Lux", True, 141.7),
    ("surf_aircontrol_ksf", 2, "Aircontrol", True, 210.4),
    ("surf_deathstar", 2, "Deathstar", True, 158.0),
    ("surf_greatriver_xdre", 2, "xdre", True, 245.6),
    ("surf_rebel_scaz", 3, "Scaz", True, 188.8),
    ("surf_calycate", 3, "Calycate", False, 300.1),
    ("surf_ski_2", 1, "Ski", True, 55.4),
    ("surf_classics", 2, "Various", False, 260.0),
    ("surf_egypt_ksf", 5, "Pharaoh", False, 402.9),
    ("surf_christmas", 1, "Santa", True, 88.8),
    ("surf_sandtrap", 2, "Sandtrap", True, 175.2),
]
NAMES = ["Kairo", "nyx", "Aurelia", "bhop_bob", "Shredder", "Mira", "velocity", "Tempo", "frostbyte", "Juno",
         "rampwalker", "Oskar", "lumen", "Pixel", "Saffron", "Drift", "kestrel", "Nova", "Wren", "Atlas",
         "Echo", "Rook", "sable", "Cinder", "Moth", "Quill", "Vesper", "Halo", "Zephyr", "Indigo"]


def sid(i):
    return str(76561198000000100 + i)


def shop_catalog():
    """The catalog the game writes to portal/shop.json, read from sh_config.lua (simple items only)."""
    import re
    cfg = open(os.path.join(PORTAL, "..", "gamemode", "surf", "gamemode", "sh_config.lua")).read()
    cats = []
    for cid, name, block in (("trail", "Trails", "Trails"), ("tag", "Chat tags", "ChatTags"),
                             ("color", "Name colors", "NameColors"), ("sound", "Finish sounds", "FinishSounds")):
        body = re.search(r"\t" + block + r" = \{(.*?)\n\t\},", cfg, re.S).group(1)
        items = []
        for line in re.findall(r"\{ id = .*\}", body):
            iid = re.search(r'id = "(\w+)"', line).group(1)
            if iid == "none":
                continue
            col = re.search(r"Color\((\d+), (\d+), (\d+)\)", line)
            price = re.search(r"price = (\d+)", line)
            items.append({"id": iid, "name": re.search(r'name = "([^"]+)"', line).group(1),
                          "price": int(price.group(1)) if price else 0, "vip": "vip = true" in line,
                          "rainbow": "rainbow = true" in line,
                          "color": "#%02x%02x%02x" % tuple(int(x) for x in col.groups()) if col else None})
        cats.append({"id": cid, "name": name, "items": items})
    coins = {"FirstFinish": 50, "PerTier": 25, "Improved": 15, "Record": 100, "Repeat": 5, "RepeatPerDay": 30,
             "Daily": 25, "Playtime": 2, "VIPBonus": 0.5}
    return {"updated": int(time.time()), "coins": coins, "categories": cats}


def build(root):
    rnd = random.Random(7)
    repo = os.path.join(root, "repo")
    gm = os.path.join(root, "garrysmod")
    data = os.path.join(gm, "data", "surfline")
    for d in (repo, os.path.join(gm, "maps"), os.path.join(data, "portal"), os.path.join(data, "zones")):
        os.makedirs(d, exist_ok=True)
    with open(os.path.join(repo, "config.env"), "w") as f:
        f.write(f'SERVER_NAME="[EU] SURF | Timer, Ranks, WR Replays | Easy to Hard Maps"\nBRAND_NAME="SURF"\n'
                f'OWNER_STEAMIDS="{OWNER}"\nPORT=27015\nDISCORD_URL="https://discord.gg/example"\n'
                f'STORE_URL="https://example.tebex.io"\nGMOD_HOME="{root}"\n')
    for name, tier, mapper, zoned, _ in MAPS:
        open(os.path.join(gm, "maps", name + ".bsp"), "wb").write(b"VBSP")
        if zoned and name not in ("surf_sandtrap",):
            open(os.path.join(data, "zones", name + ".json"), "w").write("[]")
    with open(os.path.join(data, "tiers.txt"), "w") as f:
        f.write("".join(f"{n} {t}\n" for n, t, *_ in MAPS))
    with open(os.path.join(data, "mappers.txt"), "w") as f:
        f.write("".join(f"{n} {m}\n" for n, _, m, *_ in MAPS))
    report = {"generated": int(time.time()) - 5400,
              "installed": [{"map": n, "wsid": str(1000000 + i), "title": n.replace("_", " ").title(), "zoned": z, "preview": ""}
                            for i, (n, _, _, z, _) in enumerate(MAPS)],
              "failed": [{"wsid": "2875411", "title": "surf_eclipse", "error": "SteamCMD: download timed out"}],
              "not_found": 3}
    json.dump(report, open(os.path.join(data, "maps_report.json"), "w"))
    with open(os.path.join(root, "maps.log"), "w") as f:
        f.write("".join(f"2026-10-03 05:0{i % 10}:00 installed {n}\n" for i, (n, *_) in enumerate(MAPS)))
    with open(os.path.join(root, "update.log"), "w") as f:
        f.write("2026-10-03 05:00:01 update start\n2026-10-03 05:03:12 steamcmd ok\n2026-10-03 05:04:40 restart ok\n")

    db = sqlite3.connect(os.path.join(gm, "sv.db"))
    db.executescript("""
    CREATE TABLE surf_times(map TEXT, steamid TEXT, name TEXT, time REAL, date INTEGER, completions INTEGER, splits TEXT,
                            jumps INTEGER, strafes INTEGER, sync REAL, avgspeed REAL, maxspeed REAL, PRIMARY KEY(map, steamid));
    CREATE TABLE surf_players(steamid TEXT PRIMARY KEY, name TEXT, trail TEXT, autohop INTEGER, playtime INTEGER, firstseen INTEGER, lastseen INTEGER);
    CREATE TABLE surf_vip(steamid TEXT PRIMARY KEY, expires INTEGER);
    CREATE TABLE surf_records(id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT, steamid TEXT, name TEXT, time REAL, prev_time REAL, prev_name TEXT, date INTEGER);
    CREATE TABLE surf_bans(steamid TEXT PRIMARY KEY, name TEXT, reason TEXT, admin TEXT, created INTEGER, expires INTEGER);
    CREATE TABLE surf_zones(map TEXT, ztype TEXT, x1 REAL, y1 REAL, z1 REAL, x2 REAL, y2 REAL, z2 REAL);
    """)
    now = int(time.time())
    skill = {}
    for i, n in enumerate(NAMES):
        skill[sid(i)] = rnd.uniform(0.0, 1.0) ** 1.6
        db.execute("INSERT INTO surf_players VALUES (?,?,?,?,?,?,?)",
                   (sid(i), n, "blue", 1, rnd.randint(1800, 400000), now - rnd.randint(86400 * 5, 86400 * 90), now - rnd.randint(0, 86400 * 6)))
    db.execute("INSERT INTO surf_players VALUES (?,?,?,?,?,?,?)", (OWNER, "Noam", "gold", 1, 720000, now - 86400 * 40, now - 600))
    skill[OWNER] = 0.3
    events = []
    # (style, share of players, time factor): Normal everywhere, styles on the first maps' main track and bonus 1
    styles = [("n", 1.0, 1.0), ("sw", 0.35, 1.45), ("hsw", 0.3, 1.2), ("w", 0.2, 1.6), ("lg", 0.4, 0.85)]
    for mi, (name, tier, _, zoned, base) in enumerate(MAPS):
        if not zoned:
            continue
        for track in (0, 1, 2) if base > 100 else (0, 1):
            for style, share, factor in styles:
                if style != "n" and (mi > 5 or track > 1 or (track == 1 and style not in ("lg", "sw"))):
                    continue
                key = (name if not track else f"{name}#b{track}") + ("" if style == "n" else "@" + style)
                tbase = (base if not track else base * (0.18 + 0.07 * track)) * factor
                players = [s for s in skill if rnd.random() < (0.75 - 0.08 * tier - 0.15 * track) * share]
                for s in players:
                    t = tbase * (1 + 0.02 + skill[s] * 0.35 + rnd.uniform(0, 0.05))
                    d = now - rnd.randint(600, 86400 * 30)
                    nm = "Noam" if s == OWNER else NAMES[int(s) - 76561198000000100]
                    if d < now - 86400 * 12:  # set before v4: no strafe stats
                        stats = (None,) * 5
                    else:
                        avg = rnd.uniform(900, 1600) * (0.8 if style == "lg" else 1.0)
                        sync = None if style in ("sw", "w") else round(rnd.uniform(62, 94) - skill[s] * 15, 2)
                        stats = (rnd.randint(8, 60), rnd.randint(20, 140), sync, round(avg, 1), round(avg * rnd.uniform(1.4, 2.2), 1))
                    db.execute("INSERT INTO surf_times VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                               (key, s, nm, round(t, 3), d, rnd.randint(1, 30), "[]") + stats)
                    events.append((d, key, s, nm, round(t, 3)))
    events.sort()
    best = {}
    for d, key, s, nm, t in events:
        if key not in best or t < best[key][0]:
            prev = best.get(key, (0, ""))
            db.execute("INSERT INTO surf_records(map, steamid, name, time, prev_time, prev_name, date) VALUES (?,?,?,?,?,?,?)",
                       (key, s, nm, t, prev[0], prev[1], d))
            best[key] = (t, nm)
    for s in (sid(0), sid(4), sid(9)):
        db.execute("INSERT INTO surf_vip VALUES (?,?)", (s, 0 if s == sid(0) else now + 86400 * 21))
    db.execute("INSERT INTO surf_bans VALUES (?,?,?,?,?,?)", ("76561198000099999", "cheater_x", "Speedhack in surf_mesa", OWNER, now - 86400 * 2, 0))
    db.execute("INSERT INTO surf_bans VALUES (?,?,?,?,?,?)", ("76561198000099998", "spammer", "Mic spam after warnings", OWNER, now - 3600, now + 86400))
    db.execute("INSERT INTO surf_zones VALUES ('surf_sandtrap','start',0,0,0,1,1,1)")
    # v5 shop: the owner's coins and items, and the catalog the game writes
    db.executescript("""
    CREATE TABLE surf_coins(steamid TEXT PRIMARY KEY, coins INTEGER, earned INTEGER, daily INTEGER, rep_day INTEGER, repeats INTEGER);
    CREATE TABLE surf_items(steamid TEXT, item TEXT, source TEXT, date INTEGER);
    CREATE TABLE surf_equipped(steamid TEXT, slot TEXT, item TEXT);
    CREATE TABLE surf_coin_log(id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT, amount INTEGER, reason TEXT, date INTEGER);
    """)
    db.execute("INSERT INTO surf_coins VALUES (?, 1460, 3060, 0, 0, 0)", (OWNER,))
    for item in ("trail:gold", "tag:wave", "color:sky"):
        db.execute("INSERT INTO surf_items VALUES (?,?,'coins',?)", (OWNER, item, now - 86400))
    db.executemany("INSERT INTO surf_equipped VALUES (?,?,?)", [(OWNER, "tag", "wave"), (OWNER, "color", "sky")])
    for amount, reason, ago in [(25, "daily visit, spend coins in !shop", 7200), (-800, "bought trail:gold", 6000),
                                (75, "first finish on surf_kitsune", 5000), (15, "new personal best", 3000),
                                (100, "new personal best + server record", 1200), (5, "finished surf_mesa", 300)]:
        db.execute("INSERT INTO surf_coin_log(steamid, amount, reason, date) VALUES (?,?,?,?)", (OWNER, amount, reason, now - ago))
    json.dump(shop_catalog(), open(os.path.join(data, "portal", "shop.json"), "w"))
    db.commit()
    db.close()
    ctl = os.path.join(root, "fakectl.sh")
    with open(ctl, "w") as f:
        f.write('#!/bin/sh\ncase "$1" in\n status) printf "active=active\\nsince=Fri 2026-10-03 05:04:40 UTC\\nupdate_running=no\\n";;\n'
                ' logs) for i in $(seq 1 40); do echo "Oct 03 12:0$((i % 10)):00 srcds[1234]: [Surf] tick $i ok"; done;;\n'
                ' *) echo ok;;\nesac\n')
    os.chmod(ctl, 0o755)
    return repo, gm, data, ctl


def status_obj():
    now = int(time.time())
    states = [("running", 0, "n", 47.215, 92.884), ("start", 0, "sw", 0, 95.12), ("finished", 0, "n", 93.402, 93.402),
              ("running", 1, "lg", 12.5, 0), ("idle", 0, "n", 0, 110.3), ("spec", 0, "n", 0, 0), ("running", 0, "hsw", 81.03, 99.2)]
    players = []
    for i, (st, tr, style, t, pb) in enumerate(states):
        s = sid(i * 3)
        players.append({"steamid": s, "name": NAMES[i * 3], "points": 420 - i * 50.0, "title": "", "rank": i + 1.0,
                        "state": st, "track": float(tr), "style": style, "time": t, "pb": pb if pb else False, "vip": i % 3 == 0,
                        "admin": False, "ping": 30.0 + i * 7, "connected": 300.0 + i * 600})
    return {"updated": now, "hostname": "[EU] SURF | Timer, Ranks, WR Replays | Easy to Hard Maps", "brand": "SURF",
            "map": "surf_kitsune", "tier": 1.0, "mapper": "Kitsune", "maxplayers": 24.0, "timeleft": 1462.0,
            "map_started": now - 900, "wr": {"time": 92.884, "name": "Kairo"}, "replay": {"time": 92.884, "name": "Kairo"},
            "players": players, "maps": [{"name": n, "tier": float(t), "zoned": z} for n, t, _, z, _ in MAPS]}


def keep_status(data, stop):
    path = os.path.join(data, "portal", "status.json")
    while not stop.is_set():
        json.dump(status_obj(), open(path, "w"))
        stop.wait(4)


def session_cookie(secret_file, steamid):
    secret = open(secret_file).read().strip().encode()
    exp = int(time.time()) + 14 * 86400
    mac = hmac.new(secret, f"session|{steamid}|{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{steamid}.{exp}.{mac}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--shots", help="take screenshots into this dir, then exit")
    a = ap.parse_args()
    root = a.dir or tempfile.mkdtemp(prefix="surf-demo-")
    repo, gm, data, ctl = build(root) if not os.path.exists(os.path.join(root, "repo")) else (
        os.path.join(root, "repo"), os.path.join(root, "garrysmod"), os.path.join(root, "garrysmod", "data", "surfline"),
        os.path.join(root, "fakectl.sh"))
    stop = threading.Event()
    threading.Thread(target=keep_status, args=(data, stop), daemon=True).start()
    base = f"http://127.0.0.1:{a.port}"
    secret = os.path.join(root, "secret")
    proc = subprocess.Popen([sys.executable, os.path.join(PORTAL, "server.py"), "--repo", repo, "--gmod-dir", gm,
                             "--logs-dir", root, "--listen", f"127.0.0.1:{a.port}", "--base-url", base,
                             "--public-addr", "128.140.7.178:27015", "--ctl", ctl, "--secret-file", secret, "--no-avatars"])
    time.sleep(1.0)
    cookie = session_cookie(secret, OWNER)
    print(f"demo tree: {root}\nportal:    {base}\nloading screen: {base}/loading?steamid={sid(0)}&map=surf_kitsune\n"
          f"owner cookie: surf_session={cookie}", flush=True)
    try:
        if a.shots:
            rc = subprocess.call(["node", os.path.join(HERE, "screenshots.js"), base, cookie, a.shots])
            sys.exit(rc)
        proc.wait()
    finally:
        stop.set()
        proc.terminate()


if __name__ == "__main__":
    main()
