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
    "101": {"consumer_app_id": 4000, "title": "surf_kitsune", "subscriptions": 50, "time_updated": 1},
    "102": {"consumer_app_id": 730, "title": "surf_kitsune", "subscriptions": 99999, "time_updated": 1},
    "103": {"consumer_app_id": 4000, "title": "Surf Utopia v3", "subscriptions": 10, "time_updated": 1},
    "104": {"consumer_app_id": 4000, "title": "Some Sandbox Map", "subscriptions": 10, "time_updated": 1},
    "105": {"consumer_app_id": 4000, "title": "surf_beginner", "subscriptions": 10, "time_updated": 1},
}
COLLECTIONS = {"900": ["103", "104", "105"]}
CONTENT = {
    "101": ("gma", gma([("maps/surf_kitsune.bsp", b"K"), ("lua/autorun/x.lua", b"bad")])),
    "103": ("bin", lzma.compress(gma([("maps/surf_utopia_v3.bsp", b"U")]), format=lzma.FORMAT_ALONE)),
    # 105 fails to download
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


M.steam_post = fake_post
M.steamcmd_download = fake_download
tmp = tempfile.mkdtemp()
repo, gm, work = os.path.join(tmp, "repo"), os.path.join(tmp, "garrysmod"), os.path.join(tmp, "work")
for d in (os.path.join(repo, "zones"), os.path.join(repo, "maps"), gm, work):
    os.makedirs(d)
open(os.path.join(repo, "zones", "surf_kitsune.json"), "w").write("[]")
open(os.path.join(repo, "zones", "surf_beginner.json"), "w").write("[]")
open(os.path.join(repo, "maps", "extra_maps.txt"), "w").write("surf_utopia_v3\n")
open(os.path.join(repo, "maps", "sources.txt"), "w").write("101 kitsune\n102 csgo\n900 coll\n")
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
check(ws == ["surf_kitsune", "101", "surf_utopia_v3", "103"], f"map_ws.txt ({ws})")
check(sorted(calls[0]) == ["101", "103", "105"], f"downloads requested {calls}")
rc = M.main()
check(calls[-1] == ["105"], f"second run only retries the failed item ({calls[-1]})")
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
