"""Reading the game server: A2S queries, the portal's status.json and the DB.

No Discord code here. Embeds are built as plain dicts (discord.Embed.from_dict
turns them into the real thing), so everything is testable offline.
"""
import os
import socket
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO_DIR, "portal"))

from surfweb import fmt  # noqa: E402  (the portal's formatting, so times look the same everywhere)
from surfweb.conf import Config  # noqa: E402
from surfweb.store import Store  # noqa: E402

from . import layout  # noqa: E402

A2S_INFO = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"


# ---------------------------------------------------------------- A2S

def _cstr(data, i):
    j = data.index(b"\x00", i)
    return data[i:j].decode("utf-8", "replace"), j + 1


def parse_a2s_info(data):
    """Parses an A2S_INFO reply (the 0x49 packet). Returns a dict or None."""
    try:
        if len(data) < 6 or data[:4] != b"\xFF\xFF\xFF\xFF" or data[4] != 0x49:
            return None
        i = 6  # header + protocol byte
        name, i = _cstr(data, i)
        mapname, i = _cstr(data, i)
        _folder, i = _cstr(data, i)
        _game, i = _cstr(data, i)
        i += 2  # app id
        players, maxplayers, bots = data[i], data[i + 1], data[i + 2]
        return {"name": name, "map": mapname, "players": players, "maxplayers": maxplayers, "bots": bots}
    except (ValueError, IndexError):
        return None


def query_a2s(host, port, timeout=2.0):
    """Blocking A2S_INFO with the challenge step newer servers ask for."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(A2S_INFO, (host, port))
        data, _ = s.recvfrom(1400)
        if len(data) >= 9 and data[4] == 0x41:  # challenge
            s.sendto(A2S_INFO + data[5:9], (host, port))
            data, _ = s.recvfrom(1400)
        return parse_a2s_info(data)
    except OSError:
        return None
    finally:
        s.close()


def build_a2s_reply(name, mapname, players, maxplayers, bots=0):
    """For tests: what a server sends back."""
    return (b"\xFF\xFF\xFF\xFF\x49\x11" + name.encode() + b"\x00" + mapname.encode() + b"\x00"
            + b"garrysmod\x00Surf\x00" + struct.pack("<H", 4000) + bytes([players, maxplayers, bots])
            + b"dl\x00\x01")


# ---------------------------------------------------------------- the game

class Game:
    def __init__(self, repo_dir=REPO_DIR, gmod_home=None, host="127.0.0.1"):
        self.config = Config(os.path.join(repo_dir, "config.env"))
        home = gmod_home or self.config.gmod_home
        gmod_dir = os.path.join(home, "server", "garrysmod")
        self.store = Store(os.path.join(gmod_dir, "data", "surfline"), os.path.join(gmod_dir, "sv.db"),
                           gmod_dir, home)
        self.config.site_dir = self.store.portal_dir  # the store address set on the website or reported by Tebex
        self.config.reload()
        self.home = home
        self.host = host

    @property
    def port(self):
        return int(self.config.port)

    def public_addr(self):
        ip = self.config.get("PUBLIC_IP") or os.environ.get("SURF_PUBLIC_IP", "")
        if not ip:
            ip = _public_ip()
        return f"{ip}:{self.port}" if ip else f"<server ip>:{self.port}"

    def portal_url(self):
        try:
            with open(os.path.join(self.home, "portal_url.txt")) as f:
                url = f.read().strip()
            return url if url.startswith("https://") else ""
        except OSError:
            return ""

    def status(self, a2s=None):
        """status.json merged with an A2S answer (pass query_a2s(...) in).

        The game stops writing status.json while it hibernates with nobody on,
        so a fresh A2S answer alone still counts as online."""
        st = self.store.status()
        out = {"online": st["online"], "map": st["map"], "tier": st["tier"], "mapper": st["mapper"],
               "players": st["players"], "count": len(st["players"]), "maxplayers": st["maxplayers"],
               "timeleft": st["timeleft"], "wr": st["wr"], "hostname": st["hostname"], "detail": bool(st["online"])}
        if a2s:
            out["online"] = True
            out["hostname"] = out["hostname"] or a2s["name"]
            out["maxplayers"] = out["maxplayers"] or a2s["maxplayers"]
            if not st["online"]:
                out["map"] = a2s["map"]
                out["count"] = max(0, a2s["players"] - a2s["bots"])
                out["players"] = []
                out["timeleft"] = 0
                out["wr"] = None
                out["tier"] = self.map_tier(a2s["map"])
        out["changing"] = out["online"] and not out["map"].startswith("surf_")
        return out

    def map_tier(self, name):
        info = self.store.maps().get(name)
        return fmt.to_int(info.get("tier")) if info else 0

    def records_since(self, last_id):
        rows = self.store.query("SELECT * FROM surf_records WHERE id > ? ORDER BY id LIMIT 20", (last_id,))
        return [dict(r) for r in rows]

    def last_record_id(self):
        return fmt.to_int(self.store.scalar("SELECT MAX(id) FROM surf_records"))

    def own_record_feed(self):
        """The game posts records itself when DISCORD_WEBHOOK is set; then the bot doesn't."""
        return not self.config.get("DISCORD_WEBHOOK")


def _public_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 53))
        ip = s.getsockname()[0]
        s.close()
        return "" if ip.startswith(("10.", "192.168.", "127.")) else ip
    except OSError:
        return ""


# ---------------------------------------------------------------- embeds

def esc(s):
    """Shows names as typed instead of as Discord formatting."""
    out = []
    for c in str(s or ""):
        if c in "*_~`|>\\[]#@:":
            out.append("\\" + c)
        else:
            out.append(c)
    return "".join(out)[:64]


STATE_ICON = {"running": "\U0001F3C4", "finished": "\U0001F3C1", "start": "\U0001F7E2", "spec": "\U0001F441",
              "idle": "\U0001F4A4", "nozones": "\U0001F6A7"}


def tier_label(tier):
    return f"Tier {tier}" if tier else "Unrated"


def status_name(st):
    """Name of the live voice channel. Discord allows 2 renames per 10 minutes."""
    if not st["online"]:
        return "\U0001F534 Server offline"
    if st["changing"]:
        return f"\U0001F7E1 Changing map | {st['count']}/{st['maxplayers'] or '?'}"
    return f"\U0001F7E2 {st['count']}/{st['maxplayers'] or '?'} on {st['map']}"[:100]


def presence_text(st):
    if not st["online"]:
        return "server offline"
    return f"{st['count']}/{st['maxplayers'] or '?'} on {st['map']}"[:120]


def status_embed(st, server_name, addr, portal_url, now=None):
    now = int(now or time.time())
    if not st["online"]:
        return {"title": server_name or "Surf server", "color": layout.RED,
                "description": "\U0001F534 **Offline** right now. It usually comes back within a few minutes "
                               "(nightly update at 05:00 server time).",
                "footer": f"Checked <t:{now}:R>", "timestamp": now}
    fields = []
    if st["changing"]:
        desc = "\U0001F7E1 **Online**, switching to a surf map..."
    else:
        desc = f"\U0001F7E2 **Online** | **{st['map']}** | {tier_label(st['tier'])}"
        if st["mapper"]:
            desc += f" | by {esc(st['mapper'])}"
    desc += "\n" + layout.connect_line(addr)
    fields.append({"name": "Players", "value": f"**{st['count']}** / {st['maxplayers'] or '?'}", "inline": True})
    if st["timeleft"] and not st["changing"]:
        fields.append({"name": "Map vote in", "value": fmt.fmt_duration(st["timeleft"]), "inline": True})
    if st["wr"] and not st["changing"]:
        fields.append({"name": "Server record", "value": f"**{fmt.fmt_time(st['wr']['time'])}** by {esc(st['wr']['name'])}",
                       "inline": True})
    if st["players"]:
        rows = []
        for p in sorted(st["players"], key=lambda p: (p["state"] == "spec", -p["points"]))[:20]:
            line = f"{STATE_ICON.get(p['state'], '')} **{esc(p['name'])}**"
            if p.get("title"):
                line += f" | {p['title']}"
            if p["state"] == "running" and p["time"] > 0:
                line += f" | on a run, {fmt.fmt_time(p['time'])}"
            elif p["pb"] > 0:
                line += f" | PB {fmt.fmt_time(p['pb'])}"
            rows.append(line)
        if len(st["players"]) > 20:
            rows.append(f"...and {len(st['players']) - 20} more")
        fields.append({"name": "Surfing now", "value": "\n".join(rows)[:1024], "inline": False})
    elif st["count"] == 0:
        fields.append({"name": "Surfing now", "value": "Nobody yet. Be the first and take the record!", "inline": False})
    e = {"title": server_name or "Surf server", "color": layout.GREEN, "description": desc, "fields": fields,
         "footer": "Updates every minute", "timestamp": now}
    if portal_url and st["map"].startswith("surf_"):
        e["url"] = f"{portal_url}/maps/{st['map']}"
    return e


def record_embed(row, portal_url, tier=0):
    base, track, style = fmt.parse_key(fmt.to_str(row.get("map")))
    where = f"**{esc(base)}**"
    if track:
        where += f" (Bonus {track})"
    if style and style != "n":
        where += f" on **{fmt.STYLE_NAMES.get(style, style)}**"
    t = fmt.to_float(row.get("time"))
    prev = fmt.to_float(row.get("prev_time"))
    desc = f"**{esc(row.get('name'))}** set the server record on {where} with **{fmt.fmt_time(t)}**"
    if prev > 0:
        desc += f" ({fmt.fmt_improve(prev - t)}"
        pn = fmt.to_str(row.get("prev_name"))
        if pn and pn != row.get("name"):
            desc += f", beating {esc(pn)}"
        desc += ")"
    e = {"title": "\U0001F3C6 New server record", "description": desc + ".", "color": layout.GOLD}
    if tier:
        e["fields"] = [{"name": "Tier", "value": str(tier), "inline": True}]
    date = fmt.to_int(row.get("date"))
    if date:
        e["timestamp"] = date
    if portal_url:
        e["url"] = f"{portal_url}/maps/{base}"
    return e


def top_embed(rank, portal_url, n=10):
    rows = rank["players"][:n]
    medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
    if not rows:
        desc = "No ranked players yet. Finish a map to get on the board."
    else:
        desc = "\n".join(
            f"{medals.get(p['pos']) or '`#%d`' % p['pos']} **{esc(p['name'])}** | {p['points']} pts | "
            f"{fmt.title_name(p['points'])} | {p['finished']} maps, {p['records']} records" for p in rows)
    e = {"title": "\U0001F3C5 Top surfers", "color": layout.GOLD, "description": desc}
    if portal_url:
        e["url"] = f"{portal_url}/leaderboard"
    return e


def map_embed(name, rank, tier, mapper, portal_url, n=10):
    lst = rank["keys"].get(name, [])
    e = {"title": f"\U0001F5FA {name}", "color": layout.ACCENT,
         "description": f"{tier_label(tier)}" + (f" | by {esc(mapper)}" if mapper else "") + f" | {len(lst)} finishers"}
    if lst:
        best = lst[0]["time"]
        lines = []
        for r in lst[:n]:
            gap = "" if r["pos"] == 1 else f" ({fmt.fmt_gap(r['time'] - best)})"
            lines.append(f"`#{r['pos']}` **{fmt.fmt_time(r['time'])}**{gap} {esc(r['name'])}")
        e["fields"] = [{"name": "Top times (Normal)", "value": "\n".join(lines)[:1024], "inline": False}]
    else:
        e["fields"] = [{"name": "Top times", "value": "Nobody has finished it yet.", "inline": False}]
    if portal_url:
        e["url"] = f"{portal_url}/maps/{name}"
    return e


def player_embed(ent, times, portal_url):
    e = {"title": f"\U0001F3C4 {esc(ent['name'])}", "color": layout.ACCENT,
         "description": f"**#{ent['pos']}** on the server | **{ent['points']}** points | {fmt.title_name(ent['points'])}",
         "fields": [{"name": "Maps finished", "value": str(ent["finished"]), "inline": True},
                    {"name": "Bonuses", "value": str(ent["bonuses"]), "inline": True},
                    {"name": "Server records", "value": str(ent["records"]), "inline": True}]}
    best = sorted((t for t in times if t["track"] == 0 and t["style"] == "n"), key=lambda t: (t["pos"], -t["total"]))[:5]
    if best:
        e["fields"].append({"name": "Best ranks", "value": "\n".join(
            f"**{t['map']}** #{t['pos']}/{t['total']} | {fmt.fmt_time(t['time'])}" for t in best), "inline": False})
    if portal_url and ent.get("sid"):
        e["url"] = f"{portal_url}/players/{ent['sid']}"
    return e


def recent_embed(recs, portal_url):
    if not recs:
        desc = "No records yet."
    else:
        lines = []
        for r in recs:
            where = r["map"] + (f" B{r['track']}" if r["track"] else "") + (f" {r['style'].upper()}" if r["style"] != "n" else "")
            when = f" <t:{r['date']}:R>" if r["date"] else ""
            lines.append(f"**{fmt.fmt_time(r['time'])}** {esc(r['name'])} on **{esc(where)}**{when}")
        desc = "\n".join(lines)
    e = {"title": "\U0001F3C6 Latest server records", "color": layout.GOLD, "description": desc[:4000]}
    if portal_url:
        e["url"] = portal_url
    return e


def weekly_embed(game, now=None):
    now = int(now or time.time())
    since = now - 7 * 86400
    recs = game.store.query("SELECT name, steamid FROM surf_records WHERE date >= ?", (since,))
    new_players = fmt.to_int(game.store.scalar("SELECT COUNT(*) FROM surf_players WHERE firstseen >= ?", (since,)))
    active = fmt.to_int(game.store.scalar("SELECT COUNT(*) FROM surf_players WHERE lastseen >= ?", (since,)))
    by = {}
    names = {}
    for r in recs:
        by[r["steamid"]] = by.get(r["steamid"], 0) + 1
        names[r["steamid"]] = r["name"]
    top = sorted(by.items(), key=lambda kv: -kv[1])[:3]
    desc = (f"**{len(recs)}** server records | **{active}** players surfed | **{new_players}** new faces")
    if top:
        desc += "\n\n**Record hunters of the week**\n" + "\n".join(
            f"{i}. **{esc(names[s])}** with {c} record{'s' if c != 1 else ''}" for i, (s, c) in enumerate(top, 1))
    return {"title": "\U0001F4C5 Week on the server", "color": layout.ACCENT, "description": desc, "timestamp": now}
