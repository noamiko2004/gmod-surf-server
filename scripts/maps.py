#!/usr/bin/env python3
"""Install surf maps from the Steam Workshop without a Workshop collection.

Reads maps/sources.txt (item and collection IDs), asks the Steam API which of
those are Garry's Mod items naming a wanted map (one that has zones in zones/,
or is listed in maps/extra_maps.txt), downloads the best match per map with
SteamCMD, and unpacks the .bsp (plus models) into the server.
Writes garrysmod/data/surfline/map_ws.txt so clients get each map from the
Workshop, and maps_report.json for the web portal. Standard library only.
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
MIN_FREE_GB = 6  # stop downloading maps when the disk gets this full
EASY_SLOTS = 25  # always keep this many tier 1-2 maps for new players


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
        if pos + size > len(buf):
            raise ValueError("archive is cut off (incomplete download)")
        yield name.replace("\\", "/").lower(), buf[pos:pos + size]
        pos += size


def load_gma(path):
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != b"GMAD":
        # Legacy *_legacy.bin items are LZMA-compressed GMAs. Some lack the
        # end-of-stream marker, so take what decodes and let parse_gma check it.
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        buf = dec.decompress(buf)
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
    # Downloads are deleted after unpacking, so drop SteamCMD's record of them
    # too; otherwise it may skip an item it thinks is still there.
    manifest = os.path.join(workdir, "steamapps", "workshop", "appworkshop_%d.acf" % GMOD_APPID)
    if os.path.exists(manifest):
        os.remove(manifest)
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


def read_sources(path):
    """IDs from maps/sources.txt. Items above the [pools] line are preferred
    picks for their map; IDs below it only add candidates."""
    preferred, pools = [], []
    section = preferred
    if os.path.exists(path):
        for line in open(path):
            if line.strip().lower() == "[pools]":
                section = pools
                continue
            word = line.split("#", 1)[0].strip().split()
            if word and word[0].isdigit():
                section.append(word[0])
    return preferred, pools


def read_tiers(path):
    tiers = {}
    if os.path.exists(path):
        for line in open(path):
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                tiers[parts[0]] = int(parts[1])
    return tiers


def free_gb(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1024 ** 3


def plan(picks, details, zoned, tiers, installed_maps, max_maps):
    """Orders the wanted maps: already installed first, then a set of easy
    maps for new players, then the most popular of the rest."""
    def subs(name):
        return int(details[picks[name]].get("subscriptions", 0) or 0)
    names = sorted(picks, key=lambda n: (-subs(n), n))
    order = [n for n in names if n in installed_maps]
    zoned_new = [n for n in names if n in zoned and n not in installed_maps]
    easy = [n for n in zoned_new if tiers.get(n, 3) <= 2][:EASY_SLOTS]
    order += easy
    order += [n for n in zoned_new if n not in easy]
    order += [n for n in names if n not in zoned and n not in installed_maps]
    return order[:max(max_maps, len([n for n in order if n in installed_maps]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--garrysmod", required=True)
    ap.add_argument("--steamcmd", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--max-maps", type=int, default=int(os.environ.get("MAX_MAPS") or 100))
    args = ap.parse_args()

    zones_dir = os.path.join(args.repo, "zones")
    zoned = {f[:-5] for f in os.listdir(zones_dir) if f.endswith(".json")}
    data_dir = os.path.join(args.garrysmod, "data", "surfline")
    # Maps that loaded in game without a working start and end (sv_zones.lua
    # lists them in bad_zones.txt) count as having no zones, so maps that work
    # get their slots. Placing zones in game with !zone takes a map off the list.
    zoned -= set(read_list(os.path.join(data_dir, "bad_zones.txt")))
    wanted = zoned | set(read_list(os.path.join(args.repo, "maps", "extra_maps.txt")))
    # Maps we never want: maps/blocked_maps.txt and the ones admins hid in game (!hidemap)
    blocked = set(read_list(os.path.join(args.repo, "maps", "blocked_maps.txt"))) | \
        set(read_list(os.path.join(data_dir, "hidden_maps.txt")))
    wanted -= blocked
    tiers = read_tiers(os.path.join(zones_dir, "tiers.txt"))
    preferred_ids, pool_ids = read_sources(os.path.join(args.repo, "maps", "sources.txt"))
    sources = list(dict.fromkeys(preferred_ids + pool_ids))

    collections = expand_collections(sources)
    preferred = {s for s in preferred_ids if s not in collections}
    candidates = list(dict.fromkeys([s for s in sources if s not in collections] +
                                    [c for kids in collections.values() for c in kids]))
    log(f"{len(sources)} sources, {len(collections)} collections, {len(candidates)} candidate items")

    details = file_details(candidates)
    picks = choose(details, wanted, preferred)
    found_zoned = len(set(picks) & zoned)
    log(f"{len(picks)} wanted maps found on the Garry's Mod Workshop ({found_zoned} with ready-made zones)")

    state_path = os.path.join(args.workdir, "installed.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    content_dir = os.path.join(args.workdir, "steamapps", "workshop", "content", str(GMOD_APPID))
    removed = False
    for info in state.values():
        for m in [m for m in info.get("maps", []) if m in blocked]:
            bsp = os.path.join(args.garrysmod, "maps", m + ".bsp")
            if os.path.exists(bsp):
                os.remove(bsp)
                log(f"removed blocked map {m}")
            info["maps"].remove(m)
            removed = True
    if removed:
        json.dump(state, open(state_path, "w"), indent=1)
    installed_maps = {m for info in state.values() for m in info.get("maps", [])
                      if os.path.exists(os.path.join(args.garrysmod, "maps", m + ".bsp"))}

    order = plan(picks, details, zoned, tiers, installed_maps, args.max_maps)
    if len(order) < len(picks):
        log(f"keeping {len(order)} maps (MAX_MAPS={args.max_maps}); {len(picks) - len(order)} more are available")
    todo = []
    for name in order:
        fid = picks[name]
        if fid in todo:
            continue
        if fid not in state or state[fid].get("updated") != details[fid].get("time_updated") or \
                not all(os.path.exists(os.path.join(args.garrysmod, "maps", m + ".bsp")) for m in state[fid].get("maps", [])):
            todo.append(fid)

    failed = {}
    for part in chunks(todo, 10):
        if free_gb(args.garrysmod) < MIN_FREE_GB:
            log(f"stopping: less than {MIN_FREE_GB} GB of disk left")
            break
        steamcmd_download(args.steamcmd, args.workdir, part)
        for fid in part:
            d = details[fid]
            path = find_download(content_dir, fid)
            maps, error = None, None
            for attempt in ("steamcmd", "direct"):
                if attempt == "direct":
                    if not d.get("file_url"):
                        break
                    try:
                        path = url_download(d["file_url"], os.path.join(args.workdir, "direct", fid + ".bin"))
                    except Exception as e:
                        error = f"direct download failed: {e}"
                        break
                if not path:
                    error = "download failed"
                    continue
                try:
                    maps = extract(load_gma(path), args.garrysmod)
                    break
                except Exception as e:
                    error = str(e)
                    path = None
            for leftover in (os.path.join(content_dir, fid), os.path.join(args.workdir, "direct", fid + ".bin")):
                if os.path.isdir(leftover):
                    shutil.rmtree(leftover, ignore_errors=True)
                elif os.path.exists(leftover):
                    os.remove(leftover)
            if maps is None:
                failed[fid] = error or "unknown error"
                log(f"could not install {fid} ({d.get('title')}): {failed[fid]}")
                continue
            state[fid] = {"updated": d.get("time_updated"), "maps": maps, "title": d.get("title")}
            log(f"installed {', '.join(maps) or 'nothing'} from {fid} ({d.get('title')})")
            json.dump(state, open(state_path, "w"), indent=1)

    # map -> workshop id, so clients download the right item for each map
    lines, report = [], []
    installed = set()
    for fid, info in sorted(state.items()):
        for m in info.get("maps", []):
            if m not in installed and os.path.exists(os.path.join(args.garrysmod, "maps", m + ".bsp")):
                lines.append(f"{m} {fid}")
                installed.add(m)
                d = details.get(fid, {})
                report.append({"map": m, "wsid": fid, "title": info.get("title") or d.get("title") or "",
                               "zoned": m in zoned, "tier": tiers.get(m, 0), "preview": d.get("preview_url") or ""})
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "map_ws.txt"), "w") as f:
        f.write("\n".join(sorted(lines)) + "\n")
    with open(os.path.join(data_dir, "maps_report.json"), "w") as f:
        json.dump({
            "generated": int(time.time()),
            "installed": sorted(report, key=lambda r: r["map"]),
            "failed": [{"wsid": fid, "title": details.get(fid, {}).get("title", ""), "error": err} for fid, err in failed.items()],
            "not_found": len(wanted - set(picks)),
            "available": len(picks),
        }, f, indent=1)

    log(f"done: {len(installed)} surf maps installed, {len(installed & zoned)} with ready-made zones")
    if failed:
        log(f"{len(failed)} item(s) failed and will be retried next time")
    log(f"not on the Garry's Mod Workshop (in our sources): {len(wanted - set(picks))} maps")
    print(f"MAPS_INSTALLED={len(installed)}")
    return 0 if installed else 1


if __name__ == "__main__":
    sys.exit(main())
