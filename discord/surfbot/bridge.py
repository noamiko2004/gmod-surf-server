"""File bridge between the game and the bot, plus account-link codes.

The game (sv_discord_bridge.lua) and the bot both run as the gmod user and
share garrysmod/data/surfline/discord/:

  to_discord/*.json   events from the game: chat, join, leave, map, link
  to_game/*.json      messages for the game: chat, linked, linkfail

Each file is one JSON object. Writers create the file under another name and
rename it to .json, and readers delete what they handled. A file that doesn't
parse yet is retried until it is old enough to count as broken.
"""
import json
import os
import re
import secrets
import time
import unicodedata

BROKEN_AFTER = 10      # seconds before an unparsable file is thrown away
STALE_CHAT = 300       # chat older than this (bot was down) isn't posted
MAX_PER_TICK = 50
MAX_TEXT = 200
MAX_QUEUED = 200       # to_game files kept while the game isn't reading them
CODE_TTL = 600
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I
SID_RE = re.compile(r"^7656\d{13}$")


class Bridge:
    def __init__(self, data_dir):
        self.root = os.path.join(data_dir, "discord")
        self.inbox = os.path.join(self.root, "to_discord")
        self.outbox = os.path.join(self.root, "to_game")
        self.seq = 0

    def ensure(self):
        for d in (self.inbox, self.outbox):
            os.makedirs(d, exist_ok=True)

    def read_events(self, now=None):
        """Events from the game, oldest first. Handled files are deleted."""
        now = now or time.time()
        try:
            names = sorted(n for n in os.listdir(self.inbox) if n.endswith(".json"))
        except OSError:
            return []
        out = []
        for name in names[:MAX_PER_TICK]:
            path = os.path.join(self.inbox, name)
            try:
                with open(path, "rb") as f:
                    raw = f.read(65536)
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            try:
                ev = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                ev = None
            if not isinstance(ev, dict):
                if now - mtime < BROKEN_AFTER:
                    continue  # still being written
                ev = None
            try:
                os.remove(path)
            except OSError:
                pass
            if ev is not None:
                ev.setdefault("at", int(mtime))
                out.append(ev)
        return out

    def send(self, obj):
        """One message for the game, written atomically."""
        self.ensure()
        try:
            queued = sorted(n for n in os.listdir(self.outbox) if n.endswith(".json"))
            for n in queued[:max(0, len(queued) - MAX_QUEUED + 1)]:  # the game is down or not reading
                os.remove(os.path.join(self.outbox, n))
        except OSError:
            pass
        self.seq = (self.seq + 1) % 100000
        base = os.path.join(self.outbox, f"{int(time.time() * 1000)}_{self.seq:05d}")
        tmp = base + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, base + ".json")


# ---------------------------------------------------------------- text

def one_line(text, limit=MAX_TEXT):
    """Single line, no control or invisible formatting characters, length-capped."""
    out = []
    for c in str(text or ""):
        cat = unicodedata.category(c)
        if c in "\r\n\t":
            out.append(" ")
        elif cat in ("Cc", "Cf", "Co", "Cs"):
            continue
        else:
            out.append(c)
    s = re.sub(r" {2,}", " ", "".join(out)).strip()
    return s[:limit]


def webhook_name(name):
    """Discord refuses webhook names containing 'discord' or 'clyde', or empty ones."""
    n = one_line(name, 80)
    n = re.sub(r"(?i)discord", "disc0rd", n)
    n = re.sub(r"(?i)clyde", "clyd3", n)
    return n if len(n) >= 1 and n.strip(" ") else "Player"


def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def valid_sid(sid):
    return isinstance(sid, str) and bool(SID_RE.match(sid))


# ---------------------------------------------------------------- link codes

def new_code(pending):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if code not in pending:
            return code


def prune_codes(pending, now=None):
    now = now or time.time()
    for code in [c for c, v in pending.items() if v.get("exp", 0) < now]:
        del pending[code]


def take_code(pending, code, now=None):
    """Discord user id for a valid code (and removes it), else None."""
    prune_codes(pending, now)
    code = one_line(code, 16).upper().replace("-", "").replace(" ", "")
    ent = pending.pop(code, None)
    return ent["user"] if ent else None
