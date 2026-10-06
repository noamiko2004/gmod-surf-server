"""Tebex, the paid VIP store, to the game server.

Off until TEBEX_SECRET (the store's secret key from Tebex > Integrations > Game
servers) is set, on the website (Admin > Shop) or in config.env. Then the portal asks Tebex's Plugin API for paid
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
from .conf import TEBEX_STATUS_FILE
from .store import log

API = "https://plugin.tebex.io"
STEAM64_BASE = 76561197960265728
DONE_KEEP = 5000
_STEAM2 = re.compile(r"^STEAM_[0-5]:([01]):(\d{1,10})$")
_STEAM3 = re.compile(r"^\[?U:1:(\d{1,10})\]?$")
_STEAM64 = re.compile(r"^7656\d{13}$")


SECRET_RE = re.compile(r"^[A-Za-z0-9]{16,128}$")
STORE_URL_RE = re.compile(r"^https://[A-Za-z0-9.-]{3,100}(/[A-Za-z0-9._~/-]{0,90})?$")


def write_store_url(portal_dir, url):
    """The store address for the game's !vip and shop menu (portal/store_url.txt)."""
    try:
        os.makedirs(portal_dir, exist_ok=True)
        tmp = os.path.join(portal_dir, "store_url.txt.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write((url or "") + "\n")
        os.replace(tmp, os.path.join(portal_dir, "store_url.txt"))
    except OSError as ex:
        log(f"tebex: cannot write store_url.txt: {ex}")


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
        self.status_path = os.path.join(portal_dir, TEBEX_STATUS_FILE)
        self.checked_secret = None
        self.status = {}

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

    def _save_status(self, **kw):
        """What the admin page shows: the store Tebex knows the key for, the last poll and the last error."""
        self.status.update(kw)
        try:
            os.makedirs(self.portal_dir, exist_ok=True)
            tmp = self.status_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.status, f)
            os.replace(tmp, self.status_path)
        except OSError as ex:
            log(f"tebex: cannot save status: {ex}")

    def check_key(self, secret):
        """Ask Tebex which store and server the key belongs to (GET /information)."""
        self.checked_secret = secret
        self.status = {"key_end": secret[-4:]}
        try:
            info = self.request("GET", "/information", secret)
        except urllib.error.HTTPError as ex:
            self._save_status(ok=False, checked=int(time.time()),
                              error="Tebex refused this secret key." if ex.code in (401, 403) else f"Tebex answered HTTP {ex.code}.")
            return False
        except (OSError, ValueError) as ex:
            self._save_status(ok=False, checked=int(time.time()), error=f"Could not reach Tebex ({str(ex)[:120]}).")
            self.checked_secret = None  # try again next round
            return False
        account = info.get("account") if isinstance(info.get("account"), dict) else {}
        server = info.get("server") if isinstance(info.get("server"), dict) else {}
        domain = str(account.get("domain") or "")
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        self._save_status(ok=True, checked=int(time.time()), error="", account=str(account.get("name") or "")[:80],
                          server=str(server.get("name") or "")[:80],
                          domain=domain[:200] if domain.startswith("https://") and not any(c in domain for c in "<>\"' ") else "")
        log(f"tebex: connected to store {self.status['account']!r} (server {self.status['server']!r})")
        if hasattr(self.conf, "reload"):
            self.conf.reload()
            write_store_url(self.portal_dir, self.conf.https_url("STORE_URL"))
        return True

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
            if self.checked_secret is not None or self.status:
                self.checked_secret, self.status = None, {}
                try:
                    os.remove(self.status_path)
                except OSError:
                    pass
            return 60
        if secret != self.checked_secret and not self.check_key(secret):
            return 120
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
            self._save_status(ok=True, error="", polled=int(time.time()))
            return wait
        except urllib.error.HTTPError as ex:
            log(f"tebex: HTTP {ex.code} from Tebex" + (" (check TEBEX_SECRET)" if ex.code in (401, 403) else ""))
            self._save_status(ok=False, error="Tebex refused this secret key." if ex.code in (401, 403) else f"Tebex answered HTTP {ex.code}.")
        except (OSError, ValueError, AttributeError, TypeError) as ex:
            log(f"tebex: poll failed: {ex}")
            self._save_status(error=f"Could not reach Tebex ({str(ex)[:120]}).")
        return 120

    def run_forever(self):
        while True:
            time.sleep(self.poll_once())


def start(conf, portal_dir):
    """Run the poller in the background (it idles while TEBEX_SECRET is empty)."""
    t = threading.Thread(target=Tebex(conf, portal_dir).run_forever, name="tebex", daemon=True)
    t.start()
    return t
