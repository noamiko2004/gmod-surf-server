"""config.env parsing (a bash file; parsed, never executed) with periodic reload.

A few settings can also be set by the owner on the website (Admin > Shop):
they are kept in <data>/portal/settings.json and win over config.env."""
import json
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


# Settings the owner may set on the website instead of in config.env
SITE_KEYS = ("TEBEX_SECRET", "STORE_URL")
SITE_FILE = "settings.json"
TEBEX_STATUS_FILE = "tebex_status.json"


def read_json_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def save_site_settings(site_dir, updates):
    """Merge updates ({key: value or ""}) into settings.json, readable by this user only."""
    path = os.path.join(site_dir, SITE_FILE)
    data = {k: v for k, v in read_json_file(path).items() if k in SITE_KEYS and isinstance(v, str)}
    for k, v in updates.items():
        if k in SITE_KEYS:
            if v:
                data[k] = v
            else:
                data.pop(k, None)
    os.makedirs(site_dir, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


class Config:
    """Reads config.env, re-reading it at most every `interval` seconds.
    With site_dir set, settings saved on the website (SITE_KEYS) win, and the
    store address falls back to the one Tebex reports for the store."""

    def __init__(self, path, interval=30, site_dir=None):
        self.path = path
        self.interval = interval
        self.site_dir = site_dir
        self._lock = threading.Lock()
        self._data = parse_env(path)
        self._site = {}
        self._read_at = 0.0
        self._invite = (0.0, "")
        self._fresh()

    def _fresh(self):
        with self._lock:
            if time.time() - self._read_at >= self.interval:
                self._data = parse_env(self.path)
                self._site = self._read_site()
                self._read_at = time.time()
            return self._data

    def _read_site(self):
        if not self.site_dir:
            return {}
        site = {k: v for k, v in read_json_file(os.path.join(self.site_dir, SITE_FILE)).items()
                if k in SITE_KEYS and isinstance(v, str) and v}
        domain = read_json_file(os.path.join(self.site_dir, TEBEX_STATUS_FILE)).get("domain")
        if isinstance(domain, str) and domain.startswith("https://"):
            site["_TEBEX_DOMAIN"] = domain
        return site

    def reload(self):
        """Re-read config.env and the website settings now (after the owner saves)."""
        with self._lock:
            self._read_at = 0.0
        self._fresh()

    def source(self, key):
        """Where a setting comes from: "website", "config" or ""."""
        self._fresh()
        if self._site.get(key):
            return "website"
        return "config" if self._data.get(key) else ""

    def get(self, key, default=""):
        data = self._fresh()
        v = self._site.get(key) if key in SITE_KEYS else None
        if not v:
            v = data.get(key)
        if not v and key == "STORE_URL":
            v = self._site.get("_TEBEX_DOMAIN")
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
