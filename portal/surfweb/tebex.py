"""Tebex, the paid VIP store, to the game server.

Off until TEBEX_SECRET (the store's secret key from Tebex > Integrations > Game
servers) is set in config.env. Then the portal asks Tebex's Plugin API for paid
commands every minute or so, turns the ones it knows into portal commands (the
game runs them within seconds, or when it is back if it is down), and tells
Tebex they are done. Anything else stays in the Tebex queue and is logged.

Package commands to set up in Tebex ({id} is the buyer's Steam ID):
  surf_givevip {id} 30          VIP for 30 days (0 = permanent; buying again adds days)
  surf_removevip {id}           for an expiry or chargeback command
  surf_givecoins {id} 5000      a coin pack (a negative amount takes coins away)
  surf_giveitem {id} trail:gold a shop item
  surf_removeitem {id} trail:gold

Each Tebex command id runs at most once, even if Tebex keeps it queued
(the ids already run are kept in portal/tebex_done.json).
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .actions import ITEM_RE, write_command
from .store import log

API = "https://plugin.tebex.io"
STEAM64_BASE = 76561197960265728
DONE_KEEP = 5000
_STEAM2 = re.compile(r"^STEAM_[0-5]:([01]):(\d{1,10})$")
_STEAM3 = re.compile(r"^\[?U:1:(\d{1,10})\]?$")
_STEAM64 = re.compile(r"^7656\d{13}$")


def to_steamid64(v):
    v = str(v or "").strip()
    if _STEAM64.match(v):
        return v
    m = _STEAM2.match(v)
    if m:
        return str(STEAM64_BASE + int(m.group(2)) * 2 + int(m.group(1)))
    m = _STEAM3.match(v)
    if m:
        return str(STEAM64_BASE + int(m.group(1)))
    return None


def translate(command):
    """A Tebex command line -> portal command dict, or None when it isn't one we run."""
    parts = str(command or "").split()
    if len(parts) < 2:
        return None
    name, sid = parts[0].lower(), to_steamid64(parts[1])
    if not sid:
        return None
    args = parts[2:]
    if name == "surf_givevip":
        days = args[0] if args else "30"
        if not days.isdigit() or int(days) > 3650:
            return None
        return {"action": "givevip", "steamid": sid, "days": int(days), "by": "tebex"}
    if name == "surf_removevip" and not args:
        return {"action": "removevip", "steamid": sid, "by": "tebex"}
    if name == "surf_givecoins" and len(args) == 1 and re.match(r"^-?\d{1,7}$", args[0]) and int(args[0]) != 0:
        return {"action": "givecoins", "steamid": sid, "amount": int(args[0]), "by": "tebex"}
    if name in ("surf_giveitem", "surf_removeitem") and len(args) == 1 and ITEM_RE.match(args[0].lower()):
        return {"action": name[5:], "steamid": sid, "item": args[0].lower(), "by": "tebex"}
    return None


class Tebex:
    def __init__(self, conf, portal_dir, api=API, opener=None):
        self.conf = conf
        self.portal_dir = portal_dir
        self.api = api.rstrip("/")
        self.opener = opener or urllib.request.urlopen
        self.done_path = os.path.join(portal_dir, "tebex_done.json")
        self.done = self._load_done()
        self.warned = set()

    def _load_done(self):
        try:
            with open(self.done_path, encoding="utf-8") as f:
                return [int(x) for x in json.load(f)][-DONE_KEEP:]
        except (OSError, ValueError, TypeError):
            return []

    def _save_done(self):
        os.makedirs(self.portal_dir, exist_ok=True)
        tmp = self.done_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.done[-DONE_KEEP:], f)
        os.replace(tmp, self.done_path)

    def request(self, method, path, secret, form=None):
        data = urllib.parse.urlencode(form, doseq=True).encode() if form is not None else None
        req = urllib.request.Request(self.api + path, data=data, method=method, headers={
            "X-Tebex-Secret": secret, "Accept": "application/json", "User-Agent": "SurfPortal/1.0"})
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with self.opener(req, timeout=15) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw.strip() else {}

    def poll_once(self):
        """One round. Returns how many seconds to wait before the next one."""
        secret = self.conf.get("TEBEX_SECRET")
        if not secret:
            return 60
        try:
            queue = self.request("GET", "/queue", secret)
            meta = queue.get("meta") or {}
            wait = min(600, max(30, int(meta.get("next_check") or 60)))
            due = []
            if meta.get("execute_offline"):
                due += (self.request("GET", "/queue/offline-commands", secret).get("commands") or [])
            for p in queue.get("players") or []:
                pid = p.get("id")
                if isinstance(pid, int):
                    for c in self.request("GET", f"/queue/online-commands/{pid}", secret).get("commands") or []:
                        c.setdefault("player", p)
                        due.append(c)
            finished = []
            for c in due:
                cid = c.get("id")
                if not isinstance(cid, int):
                    continue
                if cid in self.done:
                    finished.append(cid)
                    continue
                cmd = translate(c.get("command"))
                if not cmd:
                    if cid not in self.warned:
                        self.warned.add(cid)
                        log(f"tebex: command {cid} is not one the portal runs, left in the Tebex queue: {str(c.get('command'))[:200]}")
                    continue
                write_command(self.portal_dir, cmd)
                self.done.append(cid)
                self._save_done()
                finished.append(cid)
                log(f"tebex: ran command {cid}: {cmd['action']} for {cmd['steamid']}")
            if finished:
                self.request("DELETE", "/queue", secret, {"ids[]": finished})
            return wait
        except urllib.error.HTTPError as ex:
            log(f"tebex: HTTP {ex.code} from Tebex" + (" (check TEBEX_SECRET)" if ex.code in (401, 403) else ""))
        except (OSError, ValueError, AttributeError, TypeError) as ex:
            log(f"tebex: poll failed: {ex}")
        return 120

    def run_forever(self):
        while True:
            time.sleep(self.poll_once())


def start(conf, portal_dir):
    """Run the poller in the background (it idles while TEBEX_SECRET is empty)."""
    t = threading.Thread(target=Tebex(conf, portal_dir).run_forever, name="tebex", daemon=True)
    t.start()
    return t
