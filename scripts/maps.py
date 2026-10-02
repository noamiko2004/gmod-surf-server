#!/usr/bin/env python3
"""Install surf maps from the Steam Workshop without a Workshop collection.

Reads maps/sources.txt (item and collection IDs), asks the Steam API which of
those are Garry's Mod items naming a wanted map, downloads the best match per
map with SteamCMD, and unpacks the .bsp (plus models) into the server.
Writes garrysmod/data/surfline/map_ws.txt so clients get each map from the
Workshop. Only uses the Python standard library.
"""
import argparse
import json
import lzma
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request

API = "https://api.steampowered.com/ISteamRemoteStorage/{}/v1/"
GMOD_APPID = 4000
MAX_SIZE = 400 * 1024 * 1024
KEEP_DIRS = ("maps/", "models/")


def log(msg):
    print(f"[maps] {msg}", flush=True)


def steam_post(method, fields, tries=3):
    data = urllib.parse.urlencode(fields).encode()
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(API.format(method), data=data), timeout=30) as r:
                return json.load(r)["response"]
        except Exception as e:  # network hiccup or rate limit
            if attempt == tries - 1:
                raise
            log(f"{method} failed ({e}), retrying")
            time.sleep(3 * (attempt + 1))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def expand_collections(ids):
    """Returns ({collection_id: [child ids]}, set of ids that are not collections)."""
    children = {}
    for part in chunks(ids, 50):
        fields = {"collectioncount": len(part)}
        for i, fid in enumerate(part):
            fields[f"publishedfileids[{i}]"] = fid
        resp = steam_post("GetCollectionDetails", fields)
        for c in resp.get("collectiondetails", []):
            if c.get("result") == 1 and c.get("children"):
                children[c["publishedfileid"]] = [ch["publishedfileid"] for ch in c["children"] if ch.get("filetype", 0) == 0]
    return children


def file_details(ids):
    out = {}
    for part in chunks(ids, 100):
        fields = {"itemcount": len(part)}
        for i, fid in enumerate(part):
            fields[f"publishedfileids[{i}]"] = fid
        resp = steam_post("GetPublishedFileDetails", fields)
        for d in resp.get("publishedfiledetails", []):
            if d.get("result") == 1:
                out[d["publishedfileid"]] = d
    return out


def map_tokens(text):
    """Map names written with underscores, e.g. "surf_utopia_v3 [GMOD]"."""
    text = re.sub(r"\.(gma|bsp|bin)$", "", (text or "").lower())
    return {t.rstrip("_") for t in re.findall(r"surf_[a-z0-9_]+", text)}


def word_names(text):
    """Map names written as words, e.g. "Surf Kitsune - GMod" -> surf_kitsune, surf_kitsune_gmod."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    out = set()
    for i, w in enumerate(words):
        if w == "surf":
            for j in range(i + 2, min(i + 6, len(words) + 1)):
                out.add("_".join(words[i:j]))
    return out


def choose(details, wanted, preferred):
    """Pick the best Workshop item per wanted map name."""
    best = {}
    for fid, d in details.items():
        if int(d.get("consumer_app_id", 0)) != GMOD_APPID or d.get("banned"):
            continue
        if int(d.get("file_size", 0) or 0) > MAX_SIZE:
            continue
        tokens = map_tokens(d.get("title")) | map_tokens(d.get("filename"))
        if len(tokens) > 2:
            continue  # a map pack; too big for players to download per map
        tokens |= word_names(d.get("title"))
        score = int(d.get("subscriptions", 0) or 0) + (10 ** 9 if fid in preferred else 0)
        for name in tokens & wanted:
            if name not in best or score > best[name][0]:
                best[name] = (score, fid)
    return {name: fid for name, (score, fid) in best.items()}


# GMA parsing ---------------------------------------------------------------

def read_cstr(buf, pos):
    end = buf.index(b"\0", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def parse_gma(buf):
    """Yields (path, bytes) for every file in a .gma archive."""
    if buf[:4] != b"GMAD":
        raise ValueError("not a GMA file")
    version = buf[4]
    pos = 5 + 8 + 8  # steamid, timestamp
    if version > 1:
        while True:
            s, pos = read_cstr(buf, pos)
            if s == "":
                break
    for _ in range(3):  # name, description, author
        _, pos = read_cstr(buf, pos)
    pos += 4  # addon version
    entries = []
    while True:
        (num,) = struct.unpack_from("<I", buf, pos)
        pos += 4
        if num == 0:
            break
        name, pos = read_cstr(buf, pos)
        (size,) = struct.unpack_from("<q", buf, pos)
        pos += 8 + 4  # size, crc
        entries.append((name, size))
    for name, size in entries:
        yield name.replace("\\", "/").lower(), buf[pos:pos + size]
        pos += size


def load_gma(path):
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != b"GMAD":
        buf = lzma.decompress(buf, format=lzma.FORMAT_ALONE)  # legacy *_legacy.bin
    return buf


def extract(gma_buf, garrysmod_dir):
    """Writes maps and models into the server. Returns the surf map names found."""
    maps = []
    files = list(parse_gma(gma_buf))
    bsps = [p for p, _ in files if p.startswith("maps/") and p.endswith(".bsp")]
    for path, data in files:
        if ".." in path or not path.startswith(KEEP_DIRS):
            continue  # never unpack lua or anything outside maps/models
        if path.startswith("maps/"):
            if not path.endswith(".bsp"):
                continue
            name = os.path.basename(path)[:-4]
            if not name.startswith("surf_"):
                continue
            maps.append(name)
            dest = os.path.join(garrysmod_dir, "maps", name + ".bsp")
        else:
            dest = os.path.join(garrysmod_dir, "addons", "surfline_maps", path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    if not bsps:
        log("  no .bsp inside")
    return maps


# Downloading ---------------------------------------------------------------

def find_download(content_dir, fid):
    d = os.path.join(content_dir, fid)
    if not os.path.isdir(d):
        return None
    for root, _, names in os.walk(d):
        for n in names:
            if n.endswith((".gma", ".bin")):
                return os.path.join(root, n)
    return None


def steamcmd_download(steamcmd, workdir, ids):
    for part in chunks(ids, 25):
        cmd = [steamcmd, "+force_install_dir", workdir, "+login", "anonymous"]
        for fid in part:
            cmd += ["+workshop_download_item", str(GMOD_APPID), fid]
        cmd += ["+quit"]
        log(f"SteamCMD downloading {len(part)} item(s)")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)


def url_download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


# Main ----------------------------------------------------------------------

def read_list(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line.split()[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--garrysmod", required=True)
    ap.add_argument("--steamcmd", required=True)
    ap.add_argument("--workdir", required=True)
    args = ap.parse_args()

    wanted = {f[:-5] for f in os.listdir(os.path.join(args.repo, "zones")) if f.endswith(".json")}
    wanted |= set(read_list(os.path.join(args.repo, "maps", "extra_maps.txt")))
    sources = [s for s in read_list(os.path.join(args.repo, "maps", "sources.txt")) if s.isdigit()]

    collections = expand_collections(sources)
    preferred = {s for s in sources if s not in collections}
    candidates = list(dict.fromkeys(list(preferred) + [c for kids in collections.values() for c in kids]))
    log(f"{len(sources)} sources, {len(collections)} collections, {len(candidates)} candidate items")

    details = file_details(candidates)
    picks = choose(details, wanted, preferred)
    log(f"{len(picks)} wanted maps found on the Garry's Mod Workshop")

    state_path = os.path.join(args.workdir, "installed.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    content_dir = os.path.join(args.workdir, "steamapps", "workshop", "content", str(GMOD_APPID))

    todo = sorted({fid for fid in picks.values()
                   if fid not in state or state[fid].get("updated") != details[fid].get("time_updated")})
    if todo:
        steamcmd_download(args.steamcmd, args.workdir, todo)

    for fid in todo:
        d = details[fid]
        path = find_download(content_dir, fid)
        if not path and d.get("file_url"):
            try:
                path = url_download(d["file_url"], os.path.join(args.workdir, "direct", fid + ".bin"))
            except Exception as e:
                log(f"  direct download of {fid} failed: {e}")
        if not path:
            log(f"could not download {fid} ({d.get('title')})")
            continue
        try:
            maps = extract(load_gma(path), args.garrysmod)
        except Exception as e:
            log(f"could not unpack {fid} ({d.get('title')}): {e}")
            continue
        state[fid] = {"updated": d.get("time_updated"), "maps": maps, "title": d.get("title")}
        log(f"installed {', '.join(maps) or 'nothing'} from {fid} ({d.get('title')})")
        json.dump(state, open(state_path, "w"), indent=1)

    # map -> workshop id, so clients download the right item for each map
    lines = []
    installed = set()
    for fid, info in sorted(state.items()):
        for m in info.get("maps", []):
            if os.path.exists(os.path.join(args.garrysmod, "maps", m + ".bsp")):
                lines.append(f"{m} {fid}")
                installed.add(m)
    data_dir = os.path.join(args.garrysmod, "data", "surfline")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "map_ws.txt"), "w") as f:
        f.write("\n".join(sorted(lines)) + "\n")

    zoned = installed & {f[:-5] for f in os.listdir(os.path.join(args.repo, "zones")) if f.endswith(".json")}
    log(f"done: {len(installed)} surf maps installed, {len(zoned)} with ready-made zones")
    missing = sorted(wanted - installed)
    if missing:
        log(f"not found on the Workshop: {len(missing)} maps")
    print(f"MAPS_INSTALLED={len(installed)}")
    return 0 if installed else 1


if __name__ == "__main__":
    sys.exit(main())
