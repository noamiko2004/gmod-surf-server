"""Signed cookies, sessions, CSRF tokens and Steam OpenID 2.0 login."""
import base64
import calendar
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request

SESSION_COOKIE = "surf_session"
NEXT_COOKIE = "surf_next"
FLASH_COOKIE = "surf_flash"
SESSION_TTL = 14 * 86400
OPENID_NS = "http://specs.openid.net/auth/2.0"
IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"
CLAIMED_RE = re.compile(r"^https?://steamcommunity\.com/openid/id/(7656\d{13})$")
NONCE_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)")


def load_secret(path):
    """Read the HMAC secret, creating it (32 random bytes, hex, mode 0600) if missing."""
    try:
        with open(path, encoding="ascii", errors="replace") as f:
            s = f.read().strip()
        if len(s) >= 32:
            return s.encode()
    except OSError:
        pass
    s = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(s + "\n")
        os.chmod(path, 0o600)
    except OSError as ex:
        print(f"[portal] cannot write secret file {path} ({ex}); sessions reset on restart", flush=True)
    return s.encode()


def origin_of(url):
    p = urllib.parse.urlsplit(url)
    if not p.scheme or not p.hostname:
        return ""
    host = p.hostname
    if ":" in host:
        host = "[" + host + "]"
    default = {"http": 80, "https": 443}.get(p.scheme)
    port = f":{p.port}" if p.port and p.port != default else ""
    return f"{p.scheme}://{host}{port}"


def safe_next(path):
    """Only local absolute paths: '/x', never '//host' or '/\\host'."""
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return "/"
    if "\\" in path or any(ord(c) < 32 for c in path) or len(path) > 300:
        return "/"
    return path


class Auth:
    def __init__(self, secret, base_url, endpoint, timeout=10):
        self.secret = secret
        self.base = base_url.rstrip("/")
        self.endpoint = endpoint
        self.secure = self.base.startswith("https://")
        self.timeout = timeout
        self._nonces = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ signing
    def mac(self, msg):
        return hmac.new(self.secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def make_session(self, sid, now=None):
        exp = int((now or time.time()) + SESSION_TTL)
        return f"{sid}.{exp}.{self.mac(f'session|{sid}|{exp}')}"

    def parse_session(self, value):
        """Return (steamid, expiry) for a valid unexpired session cookie, else None."""
        if not value or value.count(".") != 2:
            return None
        sid, exp, sig = value.split(".")
        if not re.match(r"^7656\d{13}$", sid) or not exp.isdigit():
            return None
        if not hmac.compare_digest(sig, self.mac(f"session|{sid}|{exp}")):
            return None
        if int(exp) < time.time():
            return None
        return sid, int(exp)

    def csrf_token(self, session):
        if not session:
            return ""
        sid, exp = session
        return self.mac(f"csrf|{sid}|{exp}")

    def check_csrf(self, session, token):
        if not session or not token:
            return False
        return hmac.compare_digest(str(token), self.csrf_token(session))

    def pack(self, payload, ttl):
        """Short-lived signed value for small cookies (next path, flash)."""
        exp = int(time.time() + ttl)
        b = base64.urlsafe_b64encode(payload.encode("utf-8")).decode().rstrip("=")
        return f"{b}.{exp}.{self.mac(f'pack|{b}|{exp}')}"

    def unpack(self, value):
        if not value or value.count(".") != 2:
            return None
        b, exp, sig = value.split(".")
        if not exp.isdigit() or not hmac.compare_digest(sig, self.mac(f"pack|{b}|{exp}")):
            return None
        if int(exp) < time.time():
            return None
        try:
            return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def cookie(self, name, value, max_age):
        parts = [f"{name}={value}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={int(max_age)}"]
        if self.secure:
            parts.append("Secure")
        return "; ".join(parts)

    # ------------------------------------------------------------ OpenID
    @property
    def return_to(self):
        return self.base + "/auth/steam"

    def login_url(self):
        params = {
            "openid.ns": OPENID_NS,
            "openid.mode": "checkid_setup",
            "openid.return_to": self.return_to,
            "openid.realm": self.base + "/",
            "openid.identity": IDENTIFIER_SELECT,
            "openid.claimed_id": IDENTIFIER_SELECT,
        }
        sep = "&" if "?" in self.endpoint else "?"
        return self.endpoint + sep + urllib.parse.urlencode(params)

    def _nonce_ok(self, nonce):
        if not nonce or len(nonce) > 256:
            return False
        now = time.time()
        m = NONCE_RE.match(nonce)
        if m:
            try:
                ts = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ"))
                if abs(now - ts) > 600:
                    return False
            except ValueError:
                return False
        with self._lock:
            for k in [k for k, t in self._nonces.items() if now - t > 3600]:
                del self._nonces[k]
            if nonce in self._nonces:
                return False
            self._nonces[nonce] = now
        return True

    def check_authentication(self, params):
        data = {k: v for k, v in params.items() if k.startswith("openid.")}
        data["openid.mode"] = "check_authentication"
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(self.endpoint, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain",
            "User-Agent": "surf-portal/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            text = resp.read(65536).decode("utf-8", "replace")
        return any(line.strip() == "is_valid:true" for line in text.splitlines())

    def verify(self, params):
        """Validate a Steam id_res response. Returns (steamid, None) or (None, reason)."""
        g = lambda k: params.get(k, "")
        if g("openid.mode") != "id_res":
            return None, "Login was cancelled."
        if g("openid.ns") and g("openid.ns") != OPENID_NS:
            return None, "Unexpected OpenID namespace."
        if not g("openid.return_to").startswith(self.return_to):
            return None, "Return address mismatch."
        if g("openid.op_endpoint") != self.endpoint:
            return None, "Unexpected login provider."
        m = CLAIMED_RE.match(g("openid.claimed_id"))
        if not m:
            return None, "Invalid Steam identity."
        if g("openid.identity") and g("openid.identity") != g("openid.claimed_id"):
            return None, "Identity mismatch."
        signed = g("openid.signed").split(",")
        for need in ("claimed_id", "identity", "return_to", "response_nonce", "op_endpoint"):
            if need not in signed:
                return None, "Response is not fully signed."
        if not self._nonce_ok(g("openid.response_nonce")):
            return None, "Login response expired or was already used."
        try:
            ok = self.check_authentication(params)
        except Exception as ex:  # network errors, HTTP errors
            print(f"[portal] steam check_authentication failed: {ex}", flush=True)
            return None, "Could not reach Steam to verify the login. Try again."
        if not ok:
            return None, "Steam did not confirm the login."
        return m.group(1), None
