"""Admin commands to the game server (cmd files) and the privileged ctl helper."""
import json
import os
import re
import secrets
import subprocess
import time

from .fmt import MAPKEY_RE, clean_text, valid_steamid

INT_RE = re.compile(r"^\d{1,9}$")
SIGNED_RE = re.compile(r"^-?\d{1,7}$")
ITEM_RE = re.compile(r"^[a-z0-9_]{1,16}:[a-z0-9_]{1,32}$")

# action -> (label for messages)
ACTIONS = {
    "say": "Broadcast",
    "changelevel": "Change map",
    "extend": "Extend",
    "vote": "Map vote",
    "kick": "Kick",
    "ban": "Ban",
    "unban": "Unban",
    "givevip": "Give VIP",
    "removevip": "Remove VIP",
    "deltime": "Delete time",
    "givecoins": "Give coins",
    "giveitem": "Give item",
    "removeitem": "Remove item",
}


class Invalid(ValueError):
    pass


def _int(form, key, lo, hi, label):
    v = str(form.get(key, "")).strip()
    if not INT_RE.match(v):
        raise Invalid(f"{label} must be a whole number.")
    n = int(v)
    if n < lo or n > hi:
        raise Invalid(f"{label} must be between {lo} and {hi}.")
    return n


def _sid(form):
    v = str(form.get("steamid", "")).strip()
    if not valid_steamid(v):
        raise Invalid("That is not a valid SteamID64 (17 digits starting with 7656).")
    return v


def _reason(form, key="reason"):
    v = clean_text(form.get(key, ""), 10000)
    if len(v) > 200:
        raise Invalid("Reason is too long (max 200 characters).")
    return v


def validate(form, known_maps):
    """Turn a submitted form into a command dict. Raises Invalid."""
    action = str(form.get("action", ""))
    if action not in ACTIONS:
        raise Invalid("Unknown action.")
    cmd = {"action": action}
    if action == "say":
        text = clean_text(form.get("text", ""), 10000)
        if not text:
            raise Invalid("Message is empty.")
        if len(text) > 200:
            raise Invalid("Message is too long (max 200 characters).")
        cmd["text"] = text
    elif action == "changelevel":
        m = str(form.get("map", "")).strip()
        if m not in known_maps:
            raise Invalid("That map is not installed.")
        cmd["map"] = m
    elif action == "extend":
        cmd["minutes"] = _int(form, "minutes", 1, 120, "Minutes")
    elif action == "vote":
        pass
    elif action == "kick":
        cmd["steamid"] = _sid(form)
        cmd["reason"] = _reason(form)
    elif action == "ban":
        cmd["steamid"] = _sid(form)
        cmd["minutes"] = _int(form, "minutes", 0, 5256000, "Minutes")
        cmd["reason"] = _reason(form)
    elif action in ("unban", "removevip"):
        cmd["steamid"] = _sid(form)
    elif action == "givevip":
        cmd["steamid"] = _sid(form)
        cmd["days"] = _int(form, "days", 0, 3650, "Days")
    elif action == "givecoins":
        cmd["steamid"] = _sid(form)
        v = str(form.get("amount", "")).strip()
        if not SIGNED_RE.match(v) or int(v) == 0 or abs(int(v)) > 1000000:
            raise Invalid("Coins must be a whole number from -1000000 to 1000000, not 0.")
        cmd["amount"] = int(v)
    elif action in ("giveitem", "removeitem"):
        cmd["steamid"] = _sid(form)
        item = str(form.get("item", "")).strip().lower()
        if not ITEM_RE.match(item):
            raise Invalid("Items look like trail:gold or tag:wave.")
        cmd["item"] = item
    elif action == "deltime":
        key = str(form.get("key", "")).strip()
        if not MAPKEY_RE.match(key):
            raise Invalid("Invalid map key.")
        cmd["key"] = key
        cmd["steamid"] = _sid(form)
    return cmd


def write_command(portal_dir, cmd):
    """Atomically drop DATA/portal/cmd/<epoch_ms>_<8 hex>.txt. Returns its id."""
    d = os.path.join(portal_dir, "cmd")
    os.makedirs(d, exist_ok=True)
    cid = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
    tmp = os.path.join(d, cid + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cmd, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(d, cid + ".txt"))
    return cid


def describe(cmd):
    a = cmd.get("action")
    label = ACTIONS.get(a, a or "?")
    if a == "say":
        return f'{label}: "{cmd.get("text", "")}"'
    if a == "changelevel":
        return f"{label} to {cmd.get('map')}"
    if a == "extend":
        return f"{label} map by {cmd.get('minutes')} min"
    if a == "ban":
        mins = cmd.get("minutes")
        dur = "permanently" if mins == 0 else f"for {mins} min"
        return f"{label} {cmd.get('steamid')} {dur}"
    if a == "givevip":
        days = cmd.get("days")
        return f"{label} to {cmd.get('steamid')} " + ("(permanent)" if days == 0 else f"for {days} days")
    if a == "givecoins":
        return f"{label}: {cmd.get('amount'):+d} to {cmd.get('steamid')}"
    if a in ("giveitem", "removeitem"):
        return f"{label} {cmd.get('item')} " + ("to " if a == "giveitem" else "from ") + str(cmd.get("steamid"))
    if a == "deltime":
        return f"{label} of {cmd.get('steamid')} on {cmd.get('key')}"
    if "steamid" in cmd:
        return f"{label} {cmd.get('steamid')}"
    return label


def run_ctl(argv, sub, timeout=20):
    """Run `<ctl> <sub>`. Returns (ok, output)."""
    try:
        p = subprocess.run(list(argv) + [sub], capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return False, "The control helper is not installed (" + " ".join(argv) + ")."
    except subprocess.TimeoutExpired:
        return False, f"The control helper did not answer within {timeout} seconds."
    except OSError as ex:
        return False, f"Could not run the control helper: {ex}"
    out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr and p.returncode else "")
    if p.returncode != 0:
        return False, out.strip() or f"The control helper failed (exit code {p.returncode})."
    return True, out


def parse_ctl_status(text):
    out = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            if re.match(r"^[a-z_]{1,32}$", k):
                out[k] = v.strip()[:200]
    return out
