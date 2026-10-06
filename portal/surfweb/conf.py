"""config.env parsing (a bash file; parsed, never executed) with periodic reload."""
import os
import re
import subprocess
import threading
import time

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_SID = re.compile(r"7656\d{13}")
_INVITE = re.compile(r"https://(?:discord\.gg|discord\.com/invite)/[A-Za-z0-9-]{2,64}")


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
        self._invite = (0.0, "")

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
    def discord_url(self):
        """DISCORD_URL, else the invite the Discord bot made (<GMOD_HOME>/discord/invite.txt)."""
        url = self.https_url("DISCORD_URL")
        if url:
            return url
        path = os.path.join(self.gmod_home, "discord", "invite.txt")  # before the lock: get() takes it too
        with self._lock:
            if time.time() - self._invite[0] >= self.interval:
                self._invite = (time.time(), read_invite(path))
            return self._invite[1]

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


def read_invite(path):
    """The first line of the bot's invite file if it is a Discord invite link, else ''."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            line = f.readline(200).strip()
    except OSError:
        return ""
    return line if _INVITE.fullmatch(line) else ""


def read_version(repo):
    """(short commit, commit time) of the checkout, or ("", 0). Read once when the
    portal starts, so the footer shows the version the site is really running."""
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h %ct"],
                             capture_output=True, text=True, timeout=5)
        parts = out.stdout.split()
        if out.returncode == 0 and len(parts) == 2 and parts[1].isdigit() and re.fullmatch(r"[0-9a-f]{4,40}", parts[0]):
            return parts[0], int(parts[1])
    except (OSError, subprocess.SubprocessError):
        pass
    return "", 0
