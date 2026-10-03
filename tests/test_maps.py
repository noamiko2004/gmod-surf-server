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

# MAX_MAPS: a fresh server with room for one map gets an easy (tier 1-2) one
gm2, work2 = os.path.join(tmp, "gm2"), os.path.join(tmp, "work2")
os.makedirs(gm2); os.makedirs(work2)
calls.clear()
sys.argv = ["maps.py", "--repo", repo, "--garrysmod", gm2, "--steamcmd", "x", "--workdir", work2, "--max-maps", "2"]
M.main()
got = sorted(f[:-4] for f in os.listdir(os.path.join(gm2, "maps")))
check(sorted(sum(calls, [])) == ["101", "105"], f"MAX_MAPS=2 picks the easy maps first ({sum(calls, [])})")
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
