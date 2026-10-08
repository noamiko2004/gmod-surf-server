"""Offline test of scripts/maps.py: fake Steam API + fake SteamCMD downloads.
Run: python3 tests/test_maps.py"""
import json, lzma, os, struct, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maps as M


def gma(files):
    c = lambda s: s.encode() + b"\0"
    b = b"GMAD" + bytes([3]) + struct.pack("<QQ", 1, 2) + c("") + c("n") + c("d") + c("a") + struct.pack("<i", 1)
    for i, (n, d) in enumerate(files, 1):
        b += struct.pack("<I", i) + c(n) + struct.pack("<qI", len(d), 0)
    b += struct.pack("<I", 0)
    for _, d in files:
        b += d
    return b + struct.pack("<I", 0)


ITEMS = {
    "101": {"consumer_app_id": 4000, "title": "surf_kitsune", "subscriptions": 50, "time_updated": 1, "preview_url": "https://images.steamusercontent.com/k.jpg"},
    "102": {"consumer_app_id": 730, "title": "surf_kitsune", "subscriptions": 99999, "time_updated": 1},
    "103": {"consumer_app_id": 4000, "title": "Surf Utopia v3", "subscriptions": 10, "time_updated": 1},
    "104": {"consumer_app_id": 4000, "title": "Some Sandbox Map", "subscriptions": 10, "time_updated": 1},
    "105": {"consumer_app_id": 4000, "title": "surf_beginner", "subscriptions": 10, "time_updated": 1},
    # pool items: 107 is more popular than 101 but 101 is a preferred pick
    "107": {"consumer_app_id": 4000, "title": "surf_kitsune (reupload)", "subscriptions": 1000, "time_updated": 1},
    "108": {"consumer_app_id": 4000, "title": "surf_mesa", "subscriptions": 5, "time_updated": 1, "file_url": "http://x/108"},
    "109": {"consumer_app_id": 4000, "title": "surf_old", "subscriptions": 7, "time_updated": 1},
}
COLLECTIONS = {"900": ["103", "104", "105"]}
DIRECT = {"http://x/108": gma([("maps/surf_mesa.bsp", b"M" * 50)])}
CONTENT = {
    "101": ("gma", gma([("maps/surf_kitsune.bsp", b"K"), ("lua/autorun/x.lua", b"bad")])),
    "103": ("bin", lzma.compress(gma([("maps/surf_utopia_v3.bsp", b"U")]), format=lzma.FORMAT_ALONE)),
    # 105 fails to download
    # 108 arrives cut off from SteamCMD; the direct file_url copy is good
    "108": ("gma", gma([("maps/surf_mesa.bsp", b"M" * 50)])[:-30]),
    # 109 is a legacy item missing the last bytes of its LZMA stream
    "109": ("bin", lzma.compress(gma([("maps/surf_old.bsp", b"O" * 3000)]), format=lzma.FORMAT_ALONE)[:-4]),
}
calls = []


def fake_post(method, fields):
    ids = [v for k, v in fields.items() if k.startswith("publishedfileids")]
    if method == "GetCollectionDetails":
        return {"collectiondetails": [{"publishedfileid": i, "result": 1 if i in COLLECTIONS else 9,
                                       "children": [{"publishedfileid": c, "filetype": 0} for c in COLLECTIONS.get(i, [])]} for i in ids]}
    return {"publishedfiledetails": [dict(ITEMS[i], publishedfileid=i, result=1) for i in ids if i in ITEMS]}


def fake_download(steamcmd, workdir, ids):
    calls.append(list(ids))
    for fid in ids:
        if fid in CONTENT:
            kind, data = CONTENT[fid]
            d = os.path.join(workdir, "steamapps", "workshop", "content", "4000", fid)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "x." + kind), "wb").write(data)


def fake_url(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "wb").write(DIRECT[url])
    return dest


M.steam_post = fake_post
M.steamcmd_download = fake_download
M.url_download = fake_url
tmp = tempfile.mkdtemp()
repo, gm, work = os.path.join(tmp, "repo"), os.path.join(tmp, "garrysmod"), os.path.join(tmp, "work")
for d in (os.path.join(repo, "zones"), os.path.join(repo, "maps"), gm, work):
    os.makedirs(d)
open(os.path.join(repo, "zones", "surf_kitsune.json"), "w").write("[]")
open(os.path.join(repo, "zones", "surf_beginner.json"), "w").write("[]")
open(os.path.join(repo, "zones", "surf_mesa.json"), "w").write("[]")
open(os.path.join(repo, "zones", "surf_old.json"), "w").write("[]")
open(os.path.join(repo, "zones", "tiers.txt"), "w").write("# map tier\nsurf_beginner 1\nsurf_kitsune 1\n")
open(os.path.join(repo, "maps", "extra_maps.txt"), "w").write("surf_utopia_v3\n")
open(os.path.join(repo, "maps", "sources.txt"), "w").write("101 kitsune\n102 csgo\n[pools]\n900 coll\n107 reupload\n108 mesa\n109 old\n")
sys.argv = ["maps.py", "--repo", repo, "--garrysmod", gm, "--steamcmd", "x", "--workdir", work]

fails = []
def check(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: fails.append(m)

rc = M.main()
check(rc == 0, "exit 0 when maps installed")
check(os.path.exists(os.path.join(gm, "maps", "surf_kitsune.bsp")), "kitsune bsp installed (GMOD item, not the CS:GO one)")
check(os.path.exists(os.path.join(gm, "maps", "surf_utopia_v3.bsp")), "utopia from legacy LZMA inside a collection")
check(not any("lua" in r for r, _, _ in os.walk(gm)), "no lua extracted")
ws = open(os.path.join(gm, "data", "surfline", "map_ws.txt")).read().split()
check(ws == ["surf_kitsune", "101", "surf_mesa", "108", "surf_old", "109", "surf_utopia_v3", "103"], f"map_ws.txt ({ws})")
check(sorted(sum(calls, [])) == ["101", "103", "105", "108", "109"], f"downloads requested {calls}")
check(open(os.path.join(gm, "maps", "surf_mesa.bsp"), "rb").read() == b"M" * 50, "cut-off SteamCMD copy replaced by the direct download")
check(open(os.path.join(gm, "maps", "surf_old.bsp"), "rb").read() == b"O" * 3000, "legacy item without its LZMA end marker still unpacks")
content = os.path.join(work, "steamapps", "workshop", "content", "4000")
check(not os.listdir(content) if os.path.isdir(content) else True, "downloads deleted after unpacking")
rep = json.load(open(os.path.join(gm, "data", "surfline", "maps_report.json")))
by = {r["map"]: r for r in rep["installed"]}
check(set(by) == {"surf_kitsune", "surf_utopia_v3", "surf_mesa", "surf_old"}, f"report lists installed maps ({sorted(by)})")
check(by["surf_kitsune"]["zoned"] and by["surf_kitsune"]["tier"] == 1 and by["surf_kitsune"]["preview"].endswith("k.jpg"), "report has zones, tier and preview")
check(not by["surf_utopia_v3"]["zoned"], "report marks maps without zones")
check([f["wsid"] for f in rep["failed"]] == ["105"], f"report lists the failed item ({rep['failed']})")
rc = M.main()
check(calls[-1] == ["105"], f"second run only retries the failed item ({calls[-1]})")

# Blocked maps (maps/blocked_maps.txt) and maps hidden in game are removed and not installed again
open(os.path.join(repo, "maps", "blocked_maps.txt"), "w").write("surf_old   # weird\n")
open(os.path.join(gm, "data", "surfline", "hidden_maps.txt"), "w").write("surf_mesa\n")
calls.clear()
M.main()
check(not os.path.exists(os.path.join(gm, "maps", "surf_old.bsp")) and not os.path.exists(os.path.join(gm, "maps", "surf_mesa.bsp")), "blocked and hidden maps are deleted")
ws = open(os.path.join(gm, "data", "surfline", "map_ws.txt")).read().split()
check("surf_old" not in ws and "surf_mesa" not in ws and "surf_kitsune" in ws, f"and left out of map_ws.txt ({ws})")
check(not any(f in ("108", "109") for f in sum(calls, [])), f"and not downloaded again ({calls})")
os.remove(os.path.join(repo, "maps", "blocked_maps.txt"))

# MAX_MAPS: a fresh server with room for one map gets an easy (tier 1-2) one
gm2, work2 = os.path.join(tmp, "gm2"), os.path.join(tmp, "work2")
os.makedirs(gm2); os.makedirs(work2)
calls.clear()
sys.argv = ["maps.py", "--repo", repo, "--garrysmod", gm2, "--steamcmd", "x", "--workdir", work2, "--max-maps", "2"]
M.main()
got = sorted(f[:-4] for f in os.listdir(os.path.join(gm2, "maps")))
check(sum(calls, [])[:2] == ["101", "105"], f"MAX_MAPS=2 picks the easy maps first ({sum(calls, [])})")
check(len(got) == 2, f"a map that fails to download gives its slot to the next one ({got})")

# A map that loaded in game without a working start and end (bad_zones.txt) gives its slot to one that works
gm3, work3 = os.path.join(tmp, "gm3"), os.path.join(tmp, "work3")
os.makedirs(os.path.join(gm3, "data", "surfline")); os.makedirs(work3)
open(os.path.join(gm3, "data", "surfline", "bad_zones.txt"), "w").write("surf_kitsune\n")
calls.clear()
sys.argv = ["maps.py", "--repo", repo, "--garrysmod", gm3, "--steamcmd", "x", "--workdir", work3, "--max-maps", "2"]
M.main()
check("101" not in sum(calls, []) and "105" in sum(calls, []), f"maps with broken zones aren't installed ({sum(calls, [])})")

# Texture check: maps that would show the purple checkerboard to players without CS:S
import io, zipfile
import mapcheck


def vpk(names):
    tree = b""
    by_ext = {}
    for n in names:
        folder, base = n.rsplit("/", 1)
        stem, ext = base.rsplit(".", 1)
        by_ext.setdefault(ext, {}).setdefault(folder, []).append(stem)
    for ext, folders in by_ext.items():
        tree += ext.encode() + b"\0"
        for folder, stems in folders.items():
            tree += folder.encode() + b"\0"
            for stem in stems:
                tree += stem.encode() + b"\0" + struct.pack("<IHHIIH", 0, 0, 0x7FFF, 0, 0, 0xFFFF)
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"
    return struct.pack("<III", 0x55AA1234, 1, len(tree)) + tree


def bsp(faces, sky="sky_day01_01", packed=None, props=()):
    """faces: [(material, count)]; packed: {path: bytes} for the pakfile."""
    names = [m for m, _ in faces]
    strings, table = b"", b""
    for n in names:
        table += struct.pack("<i", len(strings))
        strings += n.encode() + b"\0"
    texdata = b"".join(struct.pack("<3fi4i", 0, 0, 0, i, 64, 64, 64, 64) for i in range(len(names)))
    texinfo = b"".join(struct.pack("<16f", *[0] * 16) + struct.pack("<ii", 0, i) for i in range(len(names)))
    texinfo += struct.pack("<16f", *[0] * 16) + struct.pack("<ii", 0x4, 0)  # sky face
    fdata = b""
    for i, (_, n) in enumerate(faces):
        fdata += (struct.pack("<HBBihh", 0, 0, 0, 0, 4, i) + b"\0" * 44) * n
    fdata += (struct.pack("<HBBihh", 0, 0, 0, 0, 4, len(names)) + b"\0" * 44) * 500  # sky faces don't count
    ents = ('{ "classname" "worldspawn" "skyname" "%s" }' % sky).encode()
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_STORED) as z:
        for path, data in (packed or {}).items():
            z.writestr(path, data)
    lumps = {0: ents, 2: texdata, 6: texinfo, 7: fdata, 40: zbuf.getvalue(), 43: strings, 44: table}
    head_len = 8 + 64 * 16 + 4
    body, dirs, pos = b"", [(0, 0, 0, 0)] * 64, head_len
    # game lump with a static prop dictionary (offsets are from the start of the file)
    sprp_ofs = head_len
    sprp = struct.pack("<i", len(props)) + b"".join(p.encode().ljust(128, b"\0") for p in props)
    body += sprp
    pos += len(sprp)
    game = struct.pack("<i", 1) + struct.pack("<iHHii", int.from_bytes(b"sprp", "big"), 0, 10, sprp_ofs, len(sprp))
    lumps[35] = game
    dirs = list(dirs)
    for i, data in sorted(lumps.items()):
        dirs[i] = (pos, len(data), 0, 0)
        body += data
        pos += len(data)
    return b"VBSP" + struct.pack("<i", 20) + b"".join(struct.pack("<iiii", *d) for d in dirs) + struct.pack("<i", 1) + body


BASE = ["materials/tools/toolsnodraw.vmt", "materials/concrete/wall.vmt", "materials/skybox/sky_day01_01rt.vmt",
        "materials/concrete/wall.vtf", "models/props/rock.mdl"]
CSSF = ["materials/cs_havana/wall.vmt", "materials/cs_havana/wall.vtf", "materials/skybox/sky_cs15rt.vmt", "models/props/de_crate.mdl"]
srv = os.path.join(tmp, "srv")
gm4, work4, css4 = os.path.join(srv, "garrysmod"), os.path.join(tmp, "work4"), os.path.join(tmp, "css")
for d in (os.path.join(srv, "sourceengine"), gm4, work4, os.path.join(css4, "cstrike")):
    os.makedirs(d, exist_ok=True)
open(os.path.join(srv, "sourceengine", "hl2_textures_dir.vpk"), "wb").write(vpk(BASE))
open(os.path.join(css4, "cstrike", "cstrike_pak_dir.vpk"), "wb").write(vpk(CSSF))

base = mapcheck.base_content(srv)
check(mapcheck.has_base(base) and "materials/concrete/wall.vmt" in base, f"base game content read from the .vpk ({sorted(base)})")
check("materials/cs_havana/wall.vmt" in mapcheck.css_content(css4), "CS:S content read from its .vpk")

css_map = bsp([("concrete/wall", 10), ("cs_havana/wall", 90), ("tools/toolsnodraw", 30)], sky="sky_cs15", props=["models/props/de_crate.mdl"])
ok_map = bsp([("concrete/wall", 98), ("cs_havana/wall", 2)])
packed_map = bsp([("custom/glass", 50), ("maps/surf_packed/concrete/wall_1_2_3", 50)], packed={
    "materials/custom/glass.vmt": b'"LightmappedGeneric" { "$basetexture" "custom/glass" }',
    "materials/custom/glass.vtf": b"x",
    "materials/maps/surf_packed/concrete/wall_1_2_3.vmt": b'"patch" { "include" "materials/concrete/wall.vmt" }'})
half_packed = bsp([("custom/glass", 50), ("concrete/wall", 50)], packed={
    "materials/custom/glass.vmt": b'"LightmappedGeneric" { "$basetexture" "cs_havana/wall" }'})
for name, data in (("css", css_map), ("ok", ok_map), ("packed", packed_map), ("half", half_packed)):
    open(os.path.join(work4, name + ".bsp"), "wb").write(data)
cssdata = mapcheck.css_content(css4)
r = mapcheck.check_map(os.path.join(work4, "css.bsp"), set(), base, cssdata)
check(r["faces"] == 130 and r["missing_faces"] == 90 and r["css_faces"] == 90, f"CS:S faces counted, sky faces skipped ({r})")
check(r["sky"] == "sky_cs15" and r["props"] == ["models/props/de_crate.mdl"], "missing sky and props reported")
check("Counter-Strike" in (mapcheck.verdict(r) or ""), f"map made of CS:S textures is taken out ({mapcheck.verdict(r)})")
r = mapcheck.check_map(os.path.join(work4, "css.bsp"), {"materials/cs_havana/wall.vmt", "materials/cs_havana/wall.vtf"}, base, cssdata)
check(mapcheck.verdict(r) is None, "the same map is fine when its Workshop item ships the textures")
r = mapcheck.check_map(os.path.join(work4, "ok.bsp"), set(), base, cssdata)
check(mapcheck.verdict(r) is None and r["missing"] == ["cs_havana/wall"], f"a few missing faces are tolerated ({r})")
r = mapcheck.check_map(os.path.join(work4, "packed.bsp"), set(), base, cssdata)
check(mapcheck.verdict(r) is None and not r["missing"], f"textures packed in the .bsp and patched materials count ({r})")
r = mapcheck.check_map(os.path.join(work4, "half.bsp"), set(), base, cssdata)
check(r["missing"] == ["custom/glass"] and mapcheck.verdict(r), f"a packed material whose texture is missing counts as missing ({r})")

# The installer tries the next Workshop copy of a map, and leaves a map out
# (giving its slot to the next one) when no copy works
ITEMS.update({
    "201": {"consumer_app_id": 4000, "title": "surf_utopia_v3", "subscriptions": 900, "time_updated": 1},
    "202": {"consumer_app_id": 4000, "title": "surf_utopia_v3 (textures fixed)", "subscriptions": 50, "time_updated": 1},
    "203": {"consumer_app_id": 4000, "title": "surf_cssonly", "subscriptions": 800, "time_updated": 1},
    "204": {"consumer_app_id": 4000, "title": "surf_fine", "subscriptions": 1, "time_updated": 1},
})
CONTENT.update({
    "201": ("gma", gma([("maps/surf_utopia_v3.bsp", css_map)])),
    "202": ("gma", gma([("maps/surf_utopia_v3.bsp", css_map), ("materials/cs_havana/wall.vmt", b"v"), ("materials/cs_havana/wall.vtf", b"t")])),
    "203": ("gma", gma([("maps/surf_cssonly.bsp", css_map)])),
    "204": ("gma", gma([("maps/surf_fine.bsp", ok_map)])),
})
repo5 = os.path.join(tmp, "repo5")
os.makedirs(os.path.join(repo5, "zones")); os.makedirs(os.path.join(repo5, "maps"))
for m in ("surf_utopia_v3", "surf_cssonly", "surf_fine"):
    open(os.path.join(repo5, "zones", m + ".json"), "w").write("[]")
open(os.path.join(repo5, "maps", "sources.txt"), "w").write("201\n202\n203\n204\n")
calls.clear()
sys.argv = ["maps.py", "--repo", repo5, "--garrysmod", gm4, "--steamcmd", "x", "--workdir", work4, "--css", css4, "--max-maps", "2"]
M.main()
ws = open(os.path.join(gm4, "data", "surfline", "map_ws.txt")).read().split()
check(ws == ["surf_fine", "204", "surf_utopia_v3", "202"], f"utopia comes from the copy with textures, cssonly's slot goes to surf_fine ({ws})")
check(not os.path.exists(os.path.join(gm4, "maps", "surf_cssonly.bsp")), "the map without a working copy isn't installed")
rep = json.load(open(os.path.join(gm4, "data", "surfline", "maps_report.json")))
check(any("surf_cssonly left out" in f["error"] and "Counter-Strike" in f["error"] for f in rep["failed"]) and
      not any("surf_utopia_v3" in f["error"] for f in rep["failed"]), f"report says why a map was left out ({rep['failed']})")
calls.clear()
M.main()
check(sum(calls, []) == [], f"checked items aren't downloaded again ({calls})")

# Maps installed before the check existed are checked once: ones whose .bsp
# passes on its own aren't downloaded again, the rest are and are taken out if they fail
st = json.load(open(os.path.join(work4, "installed.json")))
st["202"].pop("scan")
st["204"].pop("scan")
json.dump(st, open(os.path.join(work4, "installed.json"), "w"))
calls.clear()
M.main()
check(sum(calls, []) == ["202"], f"only the map needing its Workshop item's textures is downloaded to re-check ({calls})")
# Maps installed before the check existed are checked once and taken out if they fail
st = json.load(open(os.path.join(work4, "installed.json")))
st["203"] = {"updated": 1, "maps": ["surf_cssonly"], "title": "surf_cssonly"}  # no "scan": an old install
del st["204"]
json.dump(st, open(os.path.join(work4, "installed.json"), "w"))
open(os.path.join(gm4, "maps", "surf_cssonly.bsp"), "wb").write(css_map)
os.remove(os.path.join(gm4, "maps", "surf_fine.bsp"))
calls.clear()
M.main()
ws = open(os.path.join(gm4, "data", "surfline", "map_ws.txt")).read().split()
check("203" in sum(calls, []) and not os.path.exists(os.path.join(gm4, "maps", "surf_cssonly.bsp")),
      f"an old install of a CS:S-only map is re-checked and removed ({calls})")
check(ws == ["surf_fine", "204", "surf_utopia_v3", "202"], f"and the next map takes its slot ({ws})")

# Safety net: when most maps fail the check (a fault in it, or missing game
# files), maps are kept instead of the rotation being emptied
gm6, work6, repo6 = os.path.join(srv, "gm6"), os.path.join(tmp, "work6"), os.path.join(tmp, "repo6")
os.makedirs(os.path.join(repo6, "zones")); os.makedirs(os.path.join(repo6, "maps")); os.makedirs(work6); os.makedirs(gm6)
src = []
for i in range(14):
    fid, m = str(300 + i), f"surf_many{i}"
    ITEMS[fid] = {"consumer_app_id": 4000, "title": m, "subscriptions": 100 - i, "time_updated": 1}
    CONTENT[fid] = ("gma", gma([(f"maps/{m}.bsp", css_map)]))
    open(os.path.join(repo6, "zones", m + ".json"), "w").write("[]")
    src.append(fid)
open(os.path.join(repo6, "maps", "sources.txt"), "w").write("\n".join(src) + "\n")
sys.argv = ["maps.py", "--repo", repo6, "--garrysmod", gm6, "--steamcmd", "x", "--workdir", work6, "--css", css4]
M.main()
got = [f for f in os.listdir(os.path.join(gm6, "maps"))]
check(len(got) == 5, f"after 9 fail, the rest are kept rather than all removed ({len(got)})")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
