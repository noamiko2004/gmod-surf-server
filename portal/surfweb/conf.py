"""config.env parsing (a bash file; parsed, never executed) with periodic reload."""
import os
import re
import threading
import time

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_SID = re.compile(r"7656\d{13}")


def _parse_value(raw):
    raw = raw.strip()
    out, i, n = [], 0, len(raw)
    while i < n:
        c = raw[i]
        if c == '"':
            i += 1
            while i < n and raw[i] != '"':
                if raw[i] == "\\" and i + 1 < n and raw[i + 1] in '"\\$`':
                    i += 1
                out.append(raw[i])
                i += 1
            i += 1
        elif c == "'":
            i += 1
            while i < n and raw[i] != "'":
                out.append(raw[i])
                i += 1
            i += 1
        elif c.isspace():
            # unquoted whitespace ends the value; anything after is a comment
            break
        elif c == "\\" and i + 1 < n:
            out.append(raw[i + 1])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_env(path):
    data = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return data
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _LINE.match(line)
        if m:
            data[m.group(1)] = _parse_value(m.group(2))
    return data


def parse_owners(value):
    return set(_SID.findall(value or ""))


class Config:
    """Reads config.env, re-reading it at most every `interval` seconds."""

    def __init__(self, path, interval=30):
        self.path = path
        self.interval = interval
        self._lock = threading.Lock()
        self._data = parse_env(path)
        self._read_at = time.time()

    def _fresh(self):
        with self._lock:
            if time.time() - self._read_at >= self.interval:
                self._data = parse_env(self.path)
                self._read_at = time.time()
            return self._data

    def get(self, key, default=""):
        v = self._fresh().get(key)
        return default if v is None or v == "" else v

    @property
    def owners(self):
        return parse_owners(self.get("OWNER_STEAMIDS"))

    @property
    def brand(self):
        return self.get("BRAND_NAME", "Surf")

    @property
    def server_name(self):
        return self.get("SERVER_NAME", "")

    def https_url(self, key):
        v = self.get(key)
        return v if v.startswith("https://") and len(v) < 500 and not any(c in v for c in "<>\"' ") else ""

    @property
    def gmod_home(self):
        return self.get("GMOD_HOME", "/home/gmod")

    @property
    def port(self):
        v = self.get("PORT", "27015")
        return v if v.isdigit() else "27015"


def file_exists(path):
    try:
        return os.path.isfile(path)
    except OSError:
        return False
