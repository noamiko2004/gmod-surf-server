#!/usr/bin/env python3
"""Converts SurfTimer's zone, tier and mapper dumps into zones/.

Run on a developer machine, not on the server:
  git clone --depth 1 https://github.com/surftimer/SurfTimer /tmp/SurfTimer
  python3 scripts/dev/import_surftimer.py /tmp/SurfTimer

Writes zones/<map>.json (same format as the wrldspawn files) for maps that
don't already have zones from another source, plus zones/tiers.txt,
zones/mappers.txt and extra lines in zones/maxvel.txt. zones/SOURCES.txt
records where each map's zones came from.
"""
import json
import os
import re
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ZONES = os.path.join(REPO, "zones")

# SurfTimer zone types: Stop, Start, End, Stage, Checkpoint, SpeedStart, ...
START, END, STAGE, CHECKPOINT = 1, 2, 3, 4


def sql_rows(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"INSERT INTO `(\w+)` \(([^)]*)\) VALUES\s*(.*?);\s*$", txt, re.S | re.M):
        cols = [c.strip(" `") for c in m.group(2).split(",")]
        for t in re.finditer(r"\((.*?)\)(?:,\s*|\s*$)", m.group(3), re.S):
            vals = []
            for s, null, num in re.findall(r"'((?:[^'\\]|\\.)*)'|(NULL)|(-?[0-9.eE+-]+)", t.group(1)):
                if null:
                    vals.append(None)
                elif num:
                    vals.append(float(num))
                else:
                    vals.append(s.replace("\\'", "'"))
            if len(vals) == len(cols):
                yield dict(zip(cols, vals))


def valid_name(name):
    return re.fullmatch(r"surf_[a-z0-9_]+", name or "") is not None


def convert(rows):
    """Returns our zone list for one map, or None if it has no main start and end."""
    by_track = defaultdict(list)
    for z in rows:
        by_track[int(z["zonegroup"])].append(z)
    out = []
    for track, zs in sorted(by_track.items()):
        def pick(ztype):
            cands = sorted((z for z in zs if int(z["zonetype"]) == ztype), key=lambda z: int(z["zonetypeid"]))
            return cands[:1]
        stages = [z for z in zs if int(z["zonetype"]) == STAGE]
        cps = [] if stages else [z for z in zs if int(z["zonetype"]) == CHECKPOINT]
        for z in pick(START) + pick(END) + stages + cps:
            ztype = int(z["zonetype"])
            entry = {"track": track, "type": {START: "start", END: "end", STAGE: "stage", CHECKPOINT: "checkpoint"}[ztype]}
            if ztype == STAGE:
                entry["data"] = int(z["zonetypeid"]) + 2  # SurfTimer's stage 0 is the start of stage 2
            elif ztype == CHECKPOINT:
                entry["data"] = int(z["zonetypeid"]) + 1
            a = [z["pointa_x"], z["pointa_y"], z["pointa_z"]]
            b = [z["pointb_x"], z["pointb_y"], z["pointb_z"]]
            hook = z.get("hookname")
            if hook and hook != "None" and not any(a + b):
                entry["hook"] = hook  # zone is a trigger brush in the map itself
            else:
                lo, hi = min(a[2], b[2]), max(a[2], b[2])
                if hi - lo < 16:  # flat zone: give it some height so it's easy to touch
                    lo, hi = lo - 8, lo + 72
                a[2], b[2] = lo, hi
            entry["point_a"], entry["point_b"] = [round(v, 3) for v in a], [round(v, 3) for v in b]
            out.append(entry)
    types = {(e["track"], e["type"]) for e in out}
    if (0, "start") not in types or (0, "end") not in types:
        return None
    for i, e in enumerate(out):
        e["id"] = i + 1
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/SurfTimer"
    sqldir = os.path.join(src, "scripts", "mysql-files")
    sources_path = os.path.join(ZONES, "SOURCES.txt")
    sources = {}
    if os.path.exists(sources_path):
        for line in open(sources_path):
            parts = line.split()
            if len(parts) == 2 and not line.startswith("#"):
                sources[parts[0]] = parts[1]
    for f in os.listdir(ZONES):
        if f.endswith(".json") and f[:-5] not in sources:
            sources[f[:-5]] = "wrldspawn"

    by_map = defaultdict(list)
    for z in sql_rows(os.path.join(sqldir, "ck_zones.sql")):
        if valid_name(z["mapname"]):
            by_map[z["mapname"]].append(z)
    added = 0
    for name, rows in sorted(by_map.items()):
        if sources.get(name, "surftimer") != "surftimer":
            continue
        zones = convert(rows)
        if not zones:
            continue
        with open(os.path.join(ZONES, name + ".json"), "w") as f:
            json.dump(zones, f, separators=(",", ":"))
        sources[name] = "surftimer"
        added += 1

    tiers, mappers, maxvel = {}, {}, {}
    for r in sql_rows(os.path.join(sqldir, "mappernames.sql")):
        if valid_name(r["mapname"]):
            tiers[r["mapname"]] = int(r["tier"])
            if r.get("mapper"):
                mappers[r["mapname"]] = " ".join(r["mapper"].split())
            maxvel.setdefault(r["mapname"], r["maxvelocity"])
    for r in sql_rows(os.path.join(sqldir, "ck_maptier.sql")):
        if valid_name(r["mapname"]):
            tiers[r["mapname"]] = int(r["tier"])
            maxvel[r["mapname"]] = r["maxvelocity"]

    with open(os.path.join(ZONES, "tiers.txt"), "w") as f:
        f.write("# map tier (1 easy .. 6+ hard), from SurfTimer's map tier tables\n")
        for m in sorted(tiers):
            if 1 <= tiers[m] <= 8:
                f.write(f"{m} {tiers[m]}\n")
    with open(os.path.join(ZONES, "mappers.txt"), "w") as f:
        f.write("# map mapper, from SurfTimer's mapper table\n")
        for m in sorted(mappers):
            f.write(f"{m} {mappers[m]}\n")

    mv_path = os.path.join(ZONES, "maxvel.txt")
    lines = open(mv_path).read().splitlines()
    have = {l.split()[0] for l in lines if l and not l.startswith("#")}
    extra = [f"{m} {int(v)}" for m, v in sorted(maxvel.items())
             if m not in have and v and int(v) != 3500 and int(v) < 9999]
    marker = "# from SurfTimer's map tier table"
    if extra:
        if marker in lines:
            lines = lines[:lines.index(marker)]
        lines += [marker] + extra
        open(mv_path, "w").write("\n".join(lines) + "\n")

    with open(sources_path, "w") as f:
        f.write("# map source (wrldspawn = wrldspawn/surf-zones, surftimer = surftimer/SurfTimer ck_zones.sql)\n")
        for m in sorted(sources):
            f.write(f"{m} {sources[m]}\n")
    print(f"surftimer zones written: {added}; maps with zones: {len(sources)}; tiers: {len(tiers)}; mappers: {len(mappers)}; maxvel extra: {len(extra)}")


if __name__ == "__main__":
    main()
