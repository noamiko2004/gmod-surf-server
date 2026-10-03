"""Steam avatar URLs, fetched in a background thread and cached for 24 h.

Pages never wait for this: unknown avatars render as a colored initial.
"""
import collections
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

TTL = 86400
RETRY_FAILED = 3600
AV_RE = re.compile(r"<avatarMedium>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)\s*(?:\]\]>)?\s*</avatarMedium>")


def safe_avatar_url(url):
    if not isinstance(url, str) or len(url) > 500:
        return ""
    if url.startswith("http://"):
        url = "https://" + url[7:]
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or p.port or p.username:
            return ""
    except ValueError:  # malformed host or port
        return ""
    if not (host == "steamstatic.com" or host.endswith(".steamstatic.com") or host == "steamcdn-a.akamaihd.net"):
        return ""
    if any(c in url for c in "\"'<> \\"):
        return ""
    return url


class Avatars:
    def __init__(self, path, enabled=True):
        self.path = path
        self.enabled = enabled
        self._lock = threading.Lock()
        self._queue = collections.deque()
        self._queued = set()
        self._event = threading.Event()
        self._dirty = False
        self.cache = {}
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for sid, ent in raw.items():
                    if isinstance(ent, dict):
                        self.cache[sid] = {"url": safe_avatar_url(ent.get("url", "")), "t": float(ent.get("t", 0) or 0)}
        except (OSError, ValueError, TypeError):
            pass
        if enabled:
            threading.Thread(target=self._worker, name="avatars", daemon=True).start()

    def get(self, sid):
        if not sid:
            return ""
        with self._lock:
            ent = self.cache.get(sid)
            fresh = ent and time.time() - ent["t"] < (TTL if ent["url"] else RETRY_FAILED)
            if not fresh and self.enabled and sid not in self._queued and len(self._queue) < 1000:
                self._queue.append(sid)
                self._queued.add(sid)
                self._event.set()
            return ent["url"] if ent else ""

    def _fetch(self, sid):
        url = f"https://steamcommunity.com/profiles/{sid}/?xml=1"
        req = urllib.request.Request(url, headers={"User-Agent": "surf-portal/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read(262144).decode("utf-8", "replace")
        m = AV_RE.search(text)
        return safe_avatar_url(m.group(1)) if m else ""

    def _save(self):
        with self._lock:
            data = json.dumps(self.cache)
            self._dirty = False
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _worker(self):
        while True:
            self._event.wait(30)
            self._event.clear()
            while True:
                with self._lock:
                    if not self._queue:
                        break
                    sid = self._queue.popleft()
                try:
                    url = self._fetch(sid)
                except Exception:
                    url = ""
                with self._lock:
                    self._queued.discard(sid)
                    old = self.cache.get(sid, {}).get("url", "")
                    now = time.time()
                    if url:
                        self.cache[sid] = {"url": url, "t": now}
                    elif old:  # keep the old picture, try again in an hour
                        self.cache[sid] = {"url": old, "t": now - TTL + RETRY_FAILED}
                    else:
                        self.cache[sid] = {"url": "", "t": now}
                    self._dirty = True
                time.sleep(1.0)
            if self._dirty:
                self._save()
