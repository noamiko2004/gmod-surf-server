"""Everything the portal reads: status.json, the SQLite DB, map files, logs.

Nothing here raises for a missing file or table: a missing status means the
server is offline, a missing DB or table means empty lists.
"""
import glob
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.parse

from .fmt import (MAPNAME_RE, STYLE_NAMES, as_dict, as_list, clean_text, key_points, make_key, opt_num,
                  parse_key, style_order, title_index, title_index_by_name, to_bool, to_float, to_int, to_str,
                  valid_steamid)

STALE_AFTER = 30
RANK_TTL = 30
MAPS_TTL = 10
STATES = {"running", "start", "finished", "idle", "nozones", "spec"}
# surf_times columns besides map/steamid/time; older DBs may lack any of them (v4 added the stats)
TIME_COLS = ("name", "date", "completions")
STAT_COLS = ("jumps", "strafes", "sync", "avgspeed", "maxspeed")
PREVIEW_HOSTS = ("images.steamusercontent.com", "steamuserimages-a.akamaihd.net",
                 "steamcdn-a.akamaihd.net")


def log(*a):
    print("[portal]", *a, file=sys.stderr, flush=True)


def safe_image_url(url, extra_hosts=()):
    """Return url if it is an https Steam image URL we allow in the CSP, else ''."""
    if not isinstance(url, str) or not url or len(url) > 1000:
        return ""
    if url.startswith("http://"):
        url = "https://" + url[7:]
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or p.username or p.password or p.port:
            return ""
    except ValueError:  # malformed host or port
        return ""
    ok = host in PREVIEW_HOSTS or host in extra_hosts or host == "steamstatic.com" or host.endswith(".steamstatic.com")
    if not ok:
        return ""
    if any(c in url for c in "\"'<> \\\n\r\t"):
        return ""
    return url


def tail_lines(path, n=200, max_bytes=262144):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            data = f.read()
    except OSError:
        return None
    lines = data.decode("utf-8", "replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    return lines[-n:]


def read_json(path):
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None


def _rec(v):
    v = as_dict(v)
    t = to_float(v.get("time"))
    if t <= 0:
        return None
    return {"time": t, "name": to_str(v.get("name"), "unknown", 128)}


def normalize_status(o):
    o = as_dict(o)
    players = []
    for p in as_list(o.get("players")):
        p = as_dict(p)
        if not p:
            continue
        sid = to_str(p.get("steamid"), "", 24)
        points = max(0, to_int(p.get("points")))
        title = to_str(p.get("title"), "", 32)
        tidx = title_index_by_name(title)
        if tidx < 0:
            tidx = title_index(points)
        state = to_str(p.get("state"), "idle", 16)
        style = to_str(p.get("style"), "n", 8)
        players.append({
            "steamid": sid if valid_steamid(sid) else "",
            "name": to_str(p.get("name"), "unnamed", 128) or "unnamed",
            "points": points,
            "title": title or None,
            "title_idx": tidx,
            "rank": max(0, to_int(p.get("rank"))),
            "state": state if state in STATES else "idle",
            "track": max(0, to_int(p.get("track"))),
            "style": style if style in STYLE_NAMES else "n",
            "time": max(0.0, to_float(p.get("time"))),
            "pb": max(0.0, to_float(p.get("pb"))),
            "vip": to_bool(p.get("vip")),
            "admin": to_bool(p.get("admin")),
            "ping": max(0, to_int(p.get("ping"))),
            "connected": max(0, to_int(p.get("connected"))),
        })
    maps = []
    for m in as_list(o.get("maps")):
        m = as_dict(m)
        name = to_str(m.get("name"), "", 96)
        if name and MAPNAME_RE.match(name):
            maps.append({"name": name, "tier": max(0, to_int(m.get("tier"))), "zoned": to_bool(m.get("zoned"))})
    cur = to_str(o.get("map"), "", 96)
    return {
        "updated": to_int(o.get("updated")),
        "hostname": to_str(o.get("hostname"), "", 128),
        "brand": to_str(o.get("brand"), "", 64),
        "map": cur if MAPNAME_RE.match(cur or "-") else "",
        "tier": max(0, to_int(o.get("tier"))),
        "mapper": to_str(o.get("mapper"), "", 128),
        "maxplayers": max(0, to_int(o.get("maxplayers"))),
        "timeleft": max(0, to_int(o.get("timeleft"))),
        "map_started": to_int(o.get("map_started")),
        "wr": _rec(o.get("wr")),
        "replay": _rec(o.get("replay")),
        "players": players,
        "maps": maps,
    }


class Store:
    def __init__(self, data_dir, db_path, gmod_dir, logs_dir):
        self.data_dir = data_dir
        self.db_path = db_path
        self.gmod_dir = gmod_dir
        self.logs_dir = logs_dir
        self.portal_dir = os.path.join(data_dir, "portal")
        self._lock = threading.Lock()
        self._last_good = None
        self._rank = None
        self._rank_at = 0.0
        self._rank_lock = threading.Lock()
        self._maps = None
        self._maps_at = 0.0

    # ------------------------------------------------------------ status
    def _read_status_file(self):
        path = os.path.join(self.portal_dir, "status.json")
        for attempt in range(2):
            try:
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError:
                return None, "missing"
            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
                if isinstance(obj, dict):
                    return obj, None
            except ValueError:
                pass
            if attempt == 0:
                time.sleep(0.1)  # GMOD rewrites the file in place; it may be half written
        return None, "invalid"

    def status(self):
        now = time.time()
        obj, err = self._read_status_file()
        st = None
        if obj is not None:
            st = normalize_status(obj)
            with self._lock:
                self._last_good = st  # the latest file that parsed, used if the next read catches a partial write
        elif err == "invalid":
            with self._lock:
                lg = self._last_good
            if lg and now - lg["updated"] < STALE_AFTER:
                st = lg
        if st is None:
            st = normalize_status({})
        st = dict(st)
        st["online"] = st["updated"] > 0 and now - st["updated"] < STALE_AFTER
        st["age"] = max(0.0, now - st["updated"]) if st["updated"] else 0.0
        if not st["online"]:
            st["players"] = []
        return st

    # ------------------------------------------------------------ database
    def query(self, sql, args=()):
        if not os.path.isfile(self.db_path):
            return []
        try:
            uri = "file:" + urllib.parse.quote(self.db_path) + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=3)
        except sqlite3.Error as ex:
            log("db open failed:", ex)
            return []
        try:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, args).fetchall()
        except sqlite3.Error as ex:
            if "no such table" not in str(ex) and "no such column" not in str(ex):
                log("db query failed:", ex)
            return []
        finally:
            conn.close()

    def scalar(self, sql, args=(), default=0):
        rows = self.query(sql, args)
        if not rows or rows[0][0] is None:
            return default
        return rows[0][0]

    def player_names(self):
        return {r["steamid"]: r["name"] for r in self.query("SELECT steamid, name FROM surf_players")
                if r["steamid"]}

    # ------------------------------------------------------------ ranking
    def ranking(self):
        with self._rank_lock:
            if self._rank is not None and time.time() - self._rank_at < RANK_TTL:
                return self._rank
            self._rank = self._compute_ranking()
            self._rank_at = time.time()
            return self._rank

    def invalidate(self):
        with self._rank_lock:
            self._rank_at = 0.0
        self._maps_at = 0.0

    def time_columns(self):
        """Lower-case column names of surf_times (empty when the table is missing)."""
        return {to_str(r["name"]).lower() for r in self.query("PRAGMA table_info(surf_times)")}

    def _compute_ranking(self):
        cols = self.time_columns()
        rows = []
        if {"map", "steamid", "time"} <= cols:
            sel = ", ".join(c if c in cols else f"NULL AS {c}" for c in ("map", "steamid", "time") + TIME_COLS + STAT_COLS)
            rows = self.query(f"SELECT {sel} FROM surf_times")
        names = self.player_names()
        keys = {}
        latest_name = {}
        finishes = 0
        for r in rows:
            d = dict(r)
            key = to_str(d.get("map"), "", 128)
            sid = to_str(d.get("steamid"), "", 24)
            t = to_float(d.get("time"))
            if not key or not sid or t <= 0:
                continue
            date = to_int(d.get("date"))
            nm = to_str(d.get("name"), "", 128)
            if nm and date >= latest_name.get(sid, (-1, ""))[0]:
                latest_name[sid] = (date, nm)
            finishes += max(1, to_int(d.get("completions"), 1))
            row = {"sid": sid, "name": nm, "time": t, "date": date}
            for c in STAT_COLS:
                row[c] = opt_num(d.get(c))
            keys.setdefault(key, []).append(row)

        def name_of(sid):
            return names.get(sid) or latest_name.get(sid, (0, ""))[1] or sid

        # every key is its own leaderboard; variants[map][track][style] -> key
        points, finished, bonuses, records, times, variants = {}, {}, {}, {}, {}, {}
        for key, lst in keys.items():
            lst.sort(key=lambda x: (x["time"], x["date"] or 0, x["sid"]))
            base, track, style = parse_key(key)
            slot = variants.setdefault(base, {}).setdefault(track, {})
            if style not in slot or key == make_key(base, track, style):
                slot[style] = key
            total = len(lst)
            for pos, row in enumerate(lst, 1):
                sid = row["sid"]
                row["pos"] = pos
                row["name"] = name_of(sid)
                points[sid] = points.get(sid, 0) + key_points(pos, key)
                if track:
                    bonuses.setdefault(sid, set()).add((base, track))
                else:
                    finished.setdefault(sid, set()).add(base)
                if pos == 1:
                    records[sid] = records.get(sid, 0) + 1
                times.setdefault(sid, []).append({"key": key, "map": base, "track": track, "style": style,
                                                  "pos": pos, "total": total, "time": row["time"], "date": row["date"],
                                                  "gap": row["time"] - lst[0]["time"]})
        order = sorted(points, key=lambda s: (-points[s], s))
        players, by_sid = [], {}
        for i, sid in enumerate(order, 1):
            ent = {"sid": sid, "name": name_of(sid), "points": points[sid], "pos": i,
                   "finished": len(finished.get(sid, ())), "bonuses": len(bonuses.get(sid, ())),
                   "records": records.get(sid, 0), "title_idx": title_index(points[sid])}
            players.append(ent)
            by_sid[sid] = ent
        return {"keys": keys, "variants": variants, "players": players, "by_sid": by_sid, "times": times,
                "finishes": finishes, "names": names}

    # ------------------------------------------------------------ maps
    def installed_maps(self):
        out = []
        for p in glob.glob(os.path.join(self.gmod_dir, "maps", "surf_*.bsp")):
            name = os.path.basename(p)[:-4]
            if MAPNAME_RE.match(name):
                out.append(name)
        return sorted(set(out))

    def _kv_file(self, name):
        out = {}
        try:
            with open(os.path.join(self.data_dir, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(None, 1)
                    if len(parts) == 2 and MAPNAME_RE.match(parts[0]):
                        out[parts[0]] = parts[1].strip()
        except OSError:
            pass
        return out

    def maps_report(self):
        rep = as_dict(read_json(os.path.join(self.data_dir, "maps_report.json")))
        installed, failed = [], []
        for m in as_list(rep.get("installed")):
            m = as_dict(m)
            name = to_str(m.get("map"), "", 96)
            if not name or not MAPNAME_RE.match(name):
                continue
            wsid = to_str(m.get("wsid"), "", 24)
            installed.append({"map": name, "wsid": wsid if wsid.isdigit() else "",
                              "title": to_str(m.get("title"), "", 200),
                              "zoned": to_bool(m.get("zoned")),
                              "preview": safe_image_url(to_str(m.get("preview"), "", 1000))})
        for m in as_list(rep.get("failed")):
            m = as_dict(m)
            wsid = to_str(m.get("wsid"), "", 24)
            failed.append({"wsid": wsid if wsid.isdigit() else "", "title": to_str(m.get("title"), "", 200),
                           "error": to_str(m.get("error"), "", 500)})
        return {"present": bool(rep), "generated": to_int(rep.get("generated")), "installed": installed,
                "failed": failed, "not_found": max(0, to_int(rep.get("not_found")))}

    def _map_files(self):
        """File-based map facts, cached for a few seconds."""
        if self._maps is not None and time.time() - self._maps_at < MAPS_TTL:
            return self._maps
        zone_dir = os.path.join(self.data_dir, "zones")
        try:
            ready = {f[:-5] for f in os.listdir(zone_dir) if f.endswith(".json")}
        except OSError:
            ready = set()
        files = {
            "installed": set(self.installed_maps()),
            "tiers": self._kv_file("tiers.txt"),
            "mappers": self._kv_file("mappers.txt"),
            "report": {m["map"]: m for m in self.maps_report()["installed"]},
            "ready": ready,
            "placed": {to_str(r[0]) for r in self.query("SELECT DISTINCT map FROM surf_zones")},
        }
        self._maps, self._maps_at = files, time.time()
        return files

    def maps(self, status=None):
        """name -> info for every map we know about (installed, in status, or with times)."""
        status = status or self.status()
        f = self._map_files()
        online = status.get("online")
        st_maps = {m["name"]: m for m in status["maps"]} if online else {}
        rank = self.ranking()
        names = f["installed"] | set(st_maps) | set(rank["variants"])
        if online and status.get("map"):
            names.add(status["map"])
        out = {}
        for name in names:
            if not MAPNAME_RE.match(name):
                continue
            rep = f["report"].get(name, {})
            st = st_maps.get(name)
            tier = st["tier"] if st else 0
            if not tier and f["tiers"].get(name):
                tier = to_int(f["tiers"][name].split()[0])
            zoned = st["zoned"] if st is not None else (name in f["ready"] or name in f["placed"])
            main = rank["keys"].get(name, [])  # the record shown for a map is main track, Normal
            out[name] = {
                "name": name,
                "installed": name in f["installed"] or name in st_maps,
                "tier": max(0, tier),
                "mapper": f["mappers"].get(name, ""),
                "wsid": rep.get("wsid", ""),
                "title": rep.get("title", ""),
                "preview": rep.get("preview", ""),
                "zoned": bool(zoned),
                "zone_src": "in game" if name in f["placed"] else ("ready-made" if name in f["ready"] else ""),
                "record": main[0] if main else None,
                "finishers": len(main),
                "bonuses": sorted(t for t in rank["variants"].get(name, {}) if t),
                "current": bool(online and status.get("map") == name),
            }
        cur = status.get("map")
        if online and cur in out:
            if status.get("tier"):
                out[cur]["tier"] = status["tier"]
            if status.get("mapper"):
                out[cur]["mapper"] = status["mapper"]
        return out

    # ------------------------------------------------------------ records, stats
    def recent_records(self, limit=10, mapname=None):
        if mapname:
            rows = self.query("SELECT * FROM surf_records WHERE map = ? OR substr(map, 1, ?) = ? OR substr(map, 1, ?) = ? "
                              "ORDER BY id DESC LIMIT ?",
                              (mapname, len(mapname) + 2, mapname + "#b", len(mapname) + 1, mapname + "@", limit))
        else:
            rows = self.query("SELECT * FROM surf_records ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            key = to_str(d.get("map"), "", 128)
            base, track, style = parse_key(key)
            sid = to_str(d.get("steamid"), "", 24)
            out.append({"key": key, "map": base, "track": track, "style": style,
                        "steamid": sid if valid_steamid(sid) else "",
                        "name": to_str(d.get("name"), "unknown", 128), "time": to_float(d.get("time")),
                        "prev_time": to_float(d.get("prev_time")), "prev_name": to_str(d.get("prev_name"), "", 128),
                        "date": to_int(d.get("date"))})
        return out

    def stats(self):
        rank = self.ranking()
        players = to_int(self.scalar("SELECT COUNT(*) FROM surf_players"))
        if not players:
            players = len({s for lst in rank["keys"].values() for s in (x["sid"] for x in lst)})
        return {"players": players, "finishes": rank["finishes"], "maps": len(self.installed_maps()),
                "records": to_int(self.scalar("SELECT COUNT(*) FROM surf_records")), "ranked": len(rank["players"])}

    # ------------------------------------------------------------ players
    def vip_map(self):
        now = time.time()
        out = {}
        for r in self.query("SELECT steamid, expires FROM surf_vip"):
            exp = to_int(r["expires"])
            if exp == 0 or exp > now:
                out[r["steamid"]] = exp
        return out

    def player(self, sid):
        rows = self.query("SELECT * FROM surf_players WHERE steamid = ?", (sid,))
        prow = dict(rows[0]) if rows else None
        rank = self.ranking()
        ent = rank["by_sid"].get(sid)
        times = sorted(rank["times"].get(sid, []), key=lambda x: (x["map"], x["track"], style_order(x["style"])))
        if not prow and not ent:
            return None
        vip = self.vip_map().get(sid)
        bans = self.query("SELECT * FROM surf_bans WHERE steamid = ?", (sid,))
        ban = dict(bans[0]) if bans else None
        if ban:
            exp = to_int(ban.get("expires"))
            if exp and exp < time.time():
                ban = None
        name = (prow or {}).get("name") or (ent or {}).get("name") or sid
        points = ent["points"] if ent else 0
        return {"steamid": sid, "name": to_str(name, sid, 128), "points": points,
                "pos": ent["pos"] if ent else 0, "ranked": len(rank["players"]),
                "title_idx": title_index(points), "finished": ent["finished"] if ent else 0,
                "bonuses": ent["bonuses"] if ent else 0, "records": ent["records"] if ent else 0,
                "playtime": to_int((prow or {}).get("playtime")), "firstseen": to_int((prow or {}).get("firstseen")),
                "lastseen": to_int((prow or {}).get("lastseen")), "vip": vip, "ban": ban, "times": times,
                "known": prow is not None}

    def search_players(self, q, limit=50):
        q = clean_text(q, 64)
        if not q:
            rows = self.query("SELECT steamid, name, playtime, lastseen FROM surf_players "
                              "ORDER BY lastseen DESC LIMIT ?", (limit,))
        elif valid_steamid(q):
            rows = self.query("SELECT steamid, name, playtime, lastseen FROM surf_players WHERE steamid = ?", (q,))
        else:
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            rows = self.query("SELECT steamid, name, playtime, lastseen FROM surf_players "
                              "WHERE name LIKE ? ESCAPE '\\' OR steamid LIKE ? ESCAPE '\\' "
                              "ORDER BY lastseen DESC LIMIT ?", (like, like, limit))
        return [dict(r) for r in rows]

    def bans(self):
        now = time.time()
        out = []
        for r in self.query("SELECT * FROM surf_bans ORDER BY created DESC"):
            d = dict(r)
            exp = to_int(d.get("expires"))
            if exp == 0 or exp > now:
                out.append(d)
        return out

    def vips(self):
        names = self.player_names()
        out = [{"steamid": sid, "expires": exp, "name": names.get(sid, "")} for sid, exp in self.vip_map().items()]
        out.sort(key=lambda d: (d["expires"] != 0, d["expires"]))
        return out

    # ------------------------------------------------------------ portal files
    def read_results(self):
        out = {}
        for line in tail_lines(os.path.join(self.portal_dir, "results.txt"), 500) or []:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict) and isinstance(d.get("id"), str):
                out[d["id"]] = {"ok": to_bool(d.get("ok")), "msg": to_str(d.get("msg"), "", 500),
                                "time": to_int(d.get("time"))}
        return out

    def cmd_pending(self, cid):
        return os.path.exists(os.path.join(self.portal_dir, "cmd", cid + ".txt"))

    def audit_entries(self, n=50):
        out = []
        for line in tail_lines(os.path.join(self.portal_dir, "audit.log"), n) or []:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict):
                out.append(d)
        return out

    def append_audit(self, entry):
        os.makedirs(self.portal_dir, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with open(os.path.join(self.portal_dir, "audit.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
