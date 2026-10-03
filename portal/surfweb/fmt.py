"""Escaping, value coercion for GMOD JSON, and display formatting."""
import hashlib
import html
import math
import re
import time
import unicodedata

STEAMID_RE = re.compile(r"^7656\d{13}$")
MAPKEY_RE = re.compile(r"^surf_[a-z0-9_]+(#b[0-9]+)?$")
# Anything that can be a map file name. Pages for unknown maps 404 anyway.
MAPNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,96}$")

# (name, min points, rgb) - must match SURF.Config.Titles in sh_config.lua
TITLES = [
    ("Newbie", 0, (170, 170, 170)),
    ("Rookie", 30, (140, 220, 140)),
    ("Surfer", 120, (80, 200, 255)),
    ("Skilled", 300, (120, 140, 255)),
    ("Pro", 600, (200, 120, 255)),
    ("Elite", 1200, (255, 120, 60)),
    ("Legend", 2500, (255, 200, 40)),
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))


def e(value):
    """HTML-escape anything for use in text or a quoted attribute."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


# ---------------------------------------------------------------- coercion
# util.TableToJSON writes integers as floats, empty tables as [] and "no
# value" as false. These helpers turn whatever arrived into sane Python.

def to_float(v, default=0.0):
    if isinstance(v, bool) or v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def to_int(v, default=0):
    if isinstance(v, bool) or v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return int(f)


def to_str(v, default="", maxlen=256):
    if v is None or v is False or isinstance(v, (list, dict)):
        return default
    if v is True:
        return default
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v)
    return s[:maxlen]


def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return False


def as_list(v):
    """A Lua array: a JSON list, or an object with "1","2",... keys."""
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        def k(item):
            try:
                return (0, float(item[0]))
            except (TypeError, ValueError):
                return (1, str(item[0]))
        return [val for _, val in sorted(v.items(), key=k)]
    return []


def as_dict(v):
    return v if isinstance(v, dict) else {}


def clean_text(s, maxlen=200):
    """Strip control and bidi-override characters and surrounding space."""
    if s is None:
        return ""
    out = []
    for ch in str(s):
        if ch in "\t\n\r":
            out.append(" ")
            continue
        if unicodedata.category(ch) == "Cc" or ord(ch) in _BIDI:
            continue
        out.append(ch)
    return "".join(out).strip()


def valid_steamid(s):
    return isinstance(s, str) and bool(STEAMID_RE.match(s))


# ---------------------------------------------------------------- display

def fmt_time(t):
    """Like the game: m:ss.mmm, h:mm:ss.mmm past an hour, 0:12.345."""
    t = to_float(t, -1.0)
    if t <= 0:
        return "-"
    ms_total = int(math.floor(t * 1000 + 0.5))
    h, rem = divmod(ms_total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    if h:
        return f"{h}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m}:{s:02d}.{ms:03d}"


def fmt_gap(d):
    """Positive difference as +0.512 or +1:02.345."""
    d = to_float(d, 0.0)
    if d < 0.0005:
        return "+0.000"
    if d < 60:
        return "+%.3f" % (math.floor(d * 1000 + 0.5) / 1000)
    return "+" + fmt_time(d)


def fmt_improve(d):
    """Improvement shown as -0.512."""
    d = to_float(d, 0.0)
    if d < 60:
        return "-%.3f" % (math.floor(max(d, 0) * 1000 + 0.5) / 1000)
    return "-" + fmt_time(d)


def fmt_duration(sec):
    sec = max(0, to_int(sec))
    if sec < 60:
        return f"{sec}s"
    m = sec // 60
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    if h < 48:
        return f"{h}h {m}m" if m else f"{h}h"
    d, h = divmod(h, 24)
    return f"{d}d {h}h" if h else f"{d}d"


def fmt_clock(sec):
    """Countdown style 29:59 or 1:02:03."""
    sec = max(0, to_int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_date(ts):
    ts = to_int(ts)
    if ts <= 0:
        return "-"
    t = time.gmtime(ts)
    return f"{MONTHS[t.tm_mon - 1]} {t.tm_mday}, {t.tm_year}"


def fmt_datetime(ts):
    ts = to_int(ts)
    if ts <= 0:
        return "-"
    t = time.gmtime(ts)
    return f"{MONTHS[t.tm_mon - 1]} {t.tm_mday}, {t.tm_year} {t.tm_hour:02d}:{t.tm_min:02d} UTC"


def iso(ts):
    ts = to_int(ts)
    if ts <= 0:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def fmt_ago(ts, now=None):
    ts = to_int(ts)
    if ts <= 0:
        return "-"
    now = now or time.time()
    d = int(now - ts)
    if d < 0:
        return fmt_date(ts)
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{d // 60}m ago"
    if d < 86400:
        return f"{d // 3600}h ago"
    if d < 86400 * 30:
        days = d // 86400
        return "yesterday" if days == 1 else f"{days}d ago"
    return fmt_date(ts)


def fmt_int(n):
    return f"{to_int(n):,}"


def title_index(points):
    idx = 0
    for i, (_, need, _) in enumerate(TITLES):
        if points >= need:
            idx = i
    return idx


def title_name(points):
    return TITLES[title_index(points)][0]


def title_index_by_name(name):
    for i, (n, _, _) in enumerate(TITLES):
        if n.lower() == str(name or "").lower():
            return i
    return -1


def hash_index(s, n):
    h = hashlib.md5(str(s).encode("utf-8", "replace")).hexdigest()
    return int(h[:8], 16) % n


def initial(name):
    for ch in str(name or ""):
        if ch.isalnum():
            return ch.upper()
    return "?"


def track_of(key):
    """'surf_x#b2' -> ('surf_x', 2); 'surf_x' -> ('surf_x', 0)."""
    key = str(key or "")
    if "#b" in key:
        base, _, n = key.partition("#b")
        return base, to_int(n)
    return key, 0


def track_label(track):
    return "Main" if not track else f"Bonus {track}"


def points_for(pos, bonus):
    """Points for position pos (1-based) on a track. Same as sv_ranks.lua."""
    p = 10 + max(0, 50 - (pos - 1) * 5) + (50 if pos == 1 else 0)
    return p // 2 if bonus else p
