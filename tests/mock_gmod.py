"""Runs the server-side Surf gamemode against a mock Garry's Mod API.

Uses LuaJIT (same as GMOD) via lupa and a real SQLite database, so SQL,
zone loading, the timer flow, splits, records, ranks, the map vote lists and
the web portal bridge get exercised.
Run: python3 tests/mock_gmod.py
"""
import fnmatch
import json
import os
import sqlite3
import sys

import lupa.luajit21 as lj

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM = os.path.join(ROOT, "gamemode", "surf", "gamemode")
ZONES = os.path.join(ROOT, "zones")

db = sqlite3.connect(":memory:")
L = lj.LuaRuntime(unpack_returned_tuples=True)
G = L.globals()


def sql_query(q):
    try:
        cur = db.execute(q)
    except Exception as e:
        G.__sql_error = str(e)
        print("SQL ERROR:", e, "\n  ", q)
        return False
    db.commit()
    if cur.description is None:
        return None
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    if not rows:
        return None
    out = L.table()
    for i, r in enumerate(rows, 1):
        t = L.table()
        for c, v in zip(cols, r):
            t[c] = "NULL" if v is None else str(v)
        out[i] = t
    return out


vfs = {}  # files the gamemode wrote to DATA


def file_read(path, where=None):
    if path in vfs:
        return vfs[path]
    if path.startswith("surfline/zones/"):
        p = os.path.join(ZONES, os.path.basename(path))
        return open(p).read() if os.path.exists(p) else None
    if path in ("surfline/tiers.txt", "surfline/mappers.txt"):
        return open(os.path.join(ZONES, os.path.basename(path))).read()
    return None


def file_write(path, data):
    vfs[path] = data


def file_append(path, data):
    vfs[path] = vfs.get(path, "") + data


def file_delete(path):
    vfs.pop(path, None)


def file_find(pattern, where):
    if where == "GAME":
        names = [m + ".bsp" for m in G.installed_maps.values()]
        return L.table(*[n for n in names if fnmatch.fnmatch("maps/" + n, pattern)])
    names = [k.rsplit("/", 1)[1] for k in vfs if fnmatch.fnmatch(k, pattern)]
    return L.table(*sorted(names))


def json_to_table(s):
    def conv(v):
        if isinstance(v, list):
            t = L.table()
            for i, x in enumerate(v, 1):
                t[i] = conv(x)
            return t
        if isinstance(v, dict):
            t = L.table()
            for k, x in v.items():
                t[k] = conv(x)
            return t
        return v
    return conv(json.loads(s))


def table_to_json(t):
    def conv(v):
        if lj.lua_type(v) == "table":
            keys = list(v.keys())
            if keys and all(isinstance(k, int) for k in keys):
                return [conv(v[i]) for i in range(1, len(keys) + 1)]
            return {str(k): conv(v[k]) for k in keys}
        return v
    return json.dumps(conv(t))


G.py_sql_query = sql_query
G.py_file_read = file_read
G.py_file_write = file_write
G.py_file_append = file_append
G.py_file_delete = file_delete
G.py_file_find = file_find
G.py_file_size = lambda p, w=None: len(vfs[p]) if p in vfs else None
G.py_json_to_table = json_to_table
G.py_table_to_json = table_to_json

L.execute(r'''
local now = 100
function SetCurTime(t) now = t end
function CurTime() return now end
local vmeta = {}
vmeta.__index = vmeta
function Vector(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, vmeta) end
vmeta.__add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end
vmeta.__sub = function(a, b) return Vector(a.x - b.x, a.y - b.y, a.z - b.z) end
vmeta.__div = function(a, n) return Vector(a.x / n, a.y / n, a.z / n) end
vmeta.__mul = function(a, n) return Vector(a.x * n, a.y * n, a.z * n) end
function vmeta:Length2D() return math.sqrt(self.x ^ 2 + self.y ^ 2) end
vector_origin = Vector(0, 0, 0)
function Angle(p, y, r) return { p = p, y = y, r = r } end
function Color(r, g, b, a) return { r = r, g = g, b = b, a = a or 255 } end
color_white = Color(255, 255, 255)
function IsValid(e) return e ~= nil and e ~= false end
function IsColor(c) return type(c) == "table" and c.r ~= nil end
SERVER, CLIENT = true, false
TEAM_SPECTATOR = 1002
MOVETYPE_WALK, MOVETYPE_NOCLIP, MOVETYPE_NONE = 2, 8, 0
IN_JUMP, IN_DUCK, IN_FORWARD, IN_BACK, IN_MOVELEFT, IN_MOVERIGHT, IN_ATTACK, IN_ATTACK2 = 2, 4, 8, 16, 512, 1024, 1, 2048
OBS_MODE_IN_EYE, OBS_MODE_CHASE, OBS_MODE_ROAMING = 4, 5, 6
COLLISION_GROUP_IN_VEHICLE = 10
bit = require("bit")
unpack = unpack or table.unpack
function table.HasValue(t, v) for _, x in pairs(t) do if x == v then return true end end return false end
function table.Shuffle(t) end
function table.Copy(t) local o = {} for k, v in pairs(t) do o[k] = v end return o end
function math.Round(n, d) local m = 10 ^ (d or 0) return math.floor(n * m + 0.5) / m end
function math.Clamp(n, a, b) return math.min(math.max(n, a), b) end
function isstring(v) return type(v) == "string" end
function GetHostName() return "Test Server" end
CONTENTS_SOLID = 1
solidBoxes = {}   -- {min, max} boxes the mock world treats as solid
function util_IsInWorld(v) return math.abs(v.x) < 16384 and math.abs(v.y) < 16384 and math.abs(v.z) < 16384 end
function util_PointContents(v)
	for _, b in ipairs(solidBoxes) do
		if v.x >= b[1].x and v.x <= b[2].x and v.y >= b[1].y and v.y <= b[2].y and v.z >= b[1].z and v.z <= b[2].z then return CONTENTS_SOLID end
	end
	return 0
end
mapEnts = {}      -- entities in the current map: { name, class, min, max }
anyHook = false   -- pretend every hooked trigger exists
local function MockEnt(e)
	return { GetName = function() return e.name end, WorldSpaceAABB = function() return e.min, e.max end }
end
function ents_FindByName(name)
	local out = {}
	for _, e in ipairs(mapEnts) do if e.name == name then out[#out + 1] = MockEnt(e) end end
	if anyHook and #out == 0 then out[1] = MockEnt({ name = name, min = Vector(0, 0, 0), max = Vector(64, 64, 64) }) end
	return out
end
function ents_FindByClass(pat)
	local out = {}
	for _, e in ipairs(mapEnts) do if string.match(e.class, "^trigger_") then out[#out + 1] = MockEnt(e) end end
	return out
end
function string.Trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
function string.StartWith(s, p) return s:sub(1, #p) == p end
function string.Explode(sep, s) local o = {} for p in (s .. sep):gmatch("(.-)" .. sep) do o[#o + 1] = p end return o end
function string.StripExtension(s) return (s:gsub("%.%w+$", "")) end

hooks = {}
hook = { Add = function(ev, name, fn) hooks[ev] = hooks[ev] or {} hooks[ev][name] = fn end,
         Run = function(ev, ...) for _, fn in pairs(hooks[ev] or {}) do local r = fn(...) if r ~= nil then return r end end end }
timer = { Simple = function(_, fn) fn() end, Create = function() end }
sent = {}
net = {}
for _, k in ipairs({ "Start", "WriteUInt", "WriteFloat", "WriteBool", "WriteString", "WriteTable", "WriteColor" }) do
	net[k] = function(...) sent[#sent + 1] = { k, ... } end
end
net.Send = function() end
net.Broadcast = function() end
net.Receive = function() end
util = { AddNetworkString = function() end, JSONToTable = function(s) local ok, t = pcall(py_json_to_table, s) if ok then return t end end,
         TableToJSON = py_table_to_json, SteamIDTo64 = function(s) return "7656" end, SpriteTrail = function() return nil end,
         IsInWorld = util_IsInWorld, PointContents = util_PointContents }
sql = { Query = py_sql_query, SQLStr = function(s) return "'" .. tostring(s):gsub("'", "''") .. "'" end,
        LastError = function() return __sql_error end }
file = { Read = py_file_read, Exists = function(p) return py_file_read(p) ~= nil end, Find = py_file_find,
         CreateDir = function() end, Open = function() return nil end, Write = py_file_write, Append = py_file_append,
         Delete = py_file_delete, Size = py_file_size }
installed_maps = { "surf_kitsune", "surf_lessons", "surf_mesa", "surf_nozones_test" }
globals2 = {}
function SetGlobal2Int(k, v) globals2[k] = v end
SetGlobal2Float, SetGlobal2String = SetGlobal2Int, SetGlobal2Int
function GetGlobal2Float(k, d) return globals2[k] or d end
GetGlobal2Int, GetGlobal2String = GetGlobal2Float, GetGlobal2Float
mapname = "surf_kitsune"
game = { GetMap = function() return mapname end, MaxPlayers = function() return 24 end }
engine = { TickInterval = function() return 0.01 end }
ents = { Create = function() return { SetPos = function() end, Spawn = function() end, Remove = function() end } end,
         FindByName = ents_FindByName, FindByClass = ents_FindByClass }
team = { SetUp = function() end, GetColor = function() return color_white end }
humans = {}
player = { GetHumans = function() return humans end, GetAll = function() return humans end,
           GetBySteamID64 = function(id) for _, p in ipairs(humans) do if p.sid == id then return p end end end }
concommand = { Add = function() end }
chats = {}
function DeriveGamemode() end
GM = {}
function ErrorNoHalt(m) print("ERROR: " .. m) end

function MakePlayer(name, sid)
	local nw = {}
	local p = { name = name, sid = sid, alive = true, team = 1, pos = Vector(0, 0, 0), vel = Vector(0, 0, 0), mt = MOVETYPE_WALK }
	function p:Nick() return self.name end
	function p:SteamID64() return self.sid end
	function p:IsBot() return false end
	function p:Alive() return self.alive end
	function p:Team() return self.team end
	function p:SetNW2Int(k, v) nw[k] = v end
	p.SetNW2Float, p.SetNW2String, p.SetNW2Bool, p.SetNW2Entity = p.SetNW2Int, p.SetNW2Int, p.SetNW2Int, p.SetNW2Int
	function p:GetNW2Int(k, d) if nw[k] == nil then return d or 0 end return nw[k] end
	p.GetNW2Float, p.GetNW2String, p.GetNW2Bool = p.GetNW2Int, p.GetNW2Int, p.GetNW2Int
	function p:GetMoveType() return self.mt end
	function p:SetMoveType(m) self.mt = m end
	function p:GetVelocity() return self.vel end
	function p:SetLocalVelocity(v) self.vel = v end
	function p:SetPos(v) self.pos = v end
	function p:GetPos() return self.pos end
	function p:SetEyeAngles() end
	function p:SendLua() end
	function p:GetObserverTarget() return nil end
	function p:IsAdmin() return false end
	function p:IsUserGroup() return false end
	function p:Spawn() end
	function p:Ping() return 42 end
	function p:TimeConnected() return 120.5 end
	function p:Kick(reason) self.kicked = reason end
	p.nw = nw
	return p
end
''')

def include(name):
    L.execute(open(os.path.join(GM, name)).read())

G.include = lambda n: include(n)
include("sh_config.lua")
include("shared.lua")
for f in ["sv_util.lua", "sv_db.lua", "sv_zones.lua", "sv_timer.lua", "sv_replay.lua", "sv_ranks.lua", "sv_mapvote.lua", "sv_portal.lua"]:
    include(f)
# SURF.Chat is real (net stubs); capture messages instead
L.execute('''
SURF.Chat = function(target, ...) local s = "" for _, v in ipairs({...}) do if type(v) == "string" then s = s .. v end end chats[#chats + 1] = s end
SURF.Spec = { Toggle = function() end }
vipCalls = {}
SURF.VIP = { Load = function() end, Give = function(sid, days) vipCalls[#vipCalls + 1] = "give " .. sid .. " " .. days return 0 end,
             Remove = function(sid) vipCalls[#vipCalls + 1] = "remove " .. sid end }
RunConsoleCommand = function(...) lastConsole = table.concat({ ... }, " ") end
hooks.InitPostEntity.surf_zones_init()
hooks.InitPostEntity.surf_db_wr()
''')

failures = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)

Z = G.SURF.Zones
check(Z.source == "map", "kitsune loads ready-made zones")
check(Z.HasTimer(0), "kitsune main track has start+end")
check(Z.cpCount[0] == 9, f"kitsune has 9 stages (got {Z.cpCount[0]})")
check(G.globals2["surf_cpcount"] == 9, "cp count published")

L.execute('''
a = MakePlayer("Alice", "76561190000000001")
b = MakePlayer("Bob", "76561190000000002")
humans = { a, b }
SURF.DB.LoadPlayer(a) SURF.DB.LoadPlayer(b)
SURF.Timer.SetTrack(a, 0, true) SURF.Timer.SetTrack(b, 0, true)
startz = SURF.Zones.Find("start", 0)
endz = SURF.Zones.Find("end", 0)
cp2 = SURF.Zones.Find("cp", 0, 2)
cp3 = SURF.Zones.Find("cp", 0, 3)
function Run(p, t0, cps, finish)
	SetCurTime(t0)
	SURF.Timer.OnZoneEnter(p, startz)
	p.vel = Vector(600, 0, 0)
	SURF.Timer.OnZoneLeave(p, startz)
	for _, c in ipairs(cps) do SetCurTime(t0 + c[2]) SURF.Timer.OnZoneEnter(p, c[1]) end
	SetCurTime(t0 + finish)
	SURF.Timer.OnZoneEnter(p, endz)
end
Run(a, 100, { { cp2, 10 }, { cp3, 20 } }, 60)
''')
check(abs(G.a.vel.x - 290) < 0.01, "speed capped to 290 leaving start")
check(G.a.nw["surf_state"] == G.SURF.STATE_FINISHED, "Alice finished")
check(abs(G.a.nw["surf_final"] - 60) < 1e-6, "Alice time is 60s")
check(abs(G.globals2["surf_wr"] - 60) < 1e-6, "global WR is 60s")
check(any("NEW SERVER RECORD" in c for c in G.chats.values()), "WR announced")

L.execute('''
sent = {}
Run(b, 300, { { cp2, 9 }, { cp3, 21 } }, 58.5)
''')
check(abs(G.globals2["surf_wr"] - 58.5) < 1e-6, "Bob takes WR with 58.5")
# split vs WR at cp2 should be 9 - 10 = -1
splits = [list(e.values()) for e in G.sent.values() if e[1] == "WriteFloat"]
check(any(abs(v[1] + 1.0) < 1e-6 for v in splits), f"Bob's cp2 split shows -1.000 vs WR (floats sent: {[v[1] for v in splits][:6]})")
row = db.execute("select splits from surf_times where steamid='76561190000000002'").fetchone()[0]
check(json.loads(row) == [[2, 9], [3, 21]], f"splits stored as pairs ({row})")

L.execute('''
Run(a, 500, { { cp2, 12 } }, 70)  -- slower, no improvement
SURF.Ranks.Recalc()
''')
check(G.a.nw["surf_pb"] == 60, "Alice PB stays 60 after slower run")
check(G.b.nw["surf_points"] == 110 and G.a.nw["surf_points"] == 55, f"points: Bob {G.b.nw['surf_points']}, Alice {G.a.nw['surf_points']}")
check(G.b.nw["surf_rankpos"] == 1, "Bob is #1")

# Checkpoints must be in order and only while running
L.execute('''
sent = {}
SetCurTime(900) SURF.Timer.OnZoneEnter(a, cp3)
''')
check(len(G.sent) == 0, "no split when not running")

# Bonus track on a map that has one
L.execute('''
mapname = "surf_lessons"
SURF.Zones.Load()
bonuses = SURF.Zones.Bonuses()
''')
check(len(G.bonuses) >= 1, f"surf_lessons has bonuses ({len(G.bonuses)})")
L.execute('''
local bs, be = SURF.Zones.Find("start", 1), SURF.Zones.Find("end", 1)
SetCurTime(1000) SURF.Timer.OnZoneEnter(a, bs) SURF.Timer.OnZoneLeave(a, bs)
SetCurTime(1012.5) SURF.Timer.OnZoneEnter(a, be)
''')
row = db.execute("select time from surf_times where map='surf_lessons#b1'").fetchone()
check(row is not None and abs(row[0] - 12.5) < 1e-6, f"bonus 1 time stored under surf_lessons#b1 ({row})")

# Admin zones replace the ready-made zone of the same type only
L.execute('''
SURF.Zones.Save("start", Vector(0, 0, 0), Vector(100, 100, 0))
SURF.Zones.Save("end", Vector(500, 0, 0), Vector(600, 100, 0))
''')
check(Z.source == "admin+map" and Z.HasTimer(0), f"admin start/end on top of ready-made zones ({Z.source})")
check(Z.Find("start", 0).admin and Z.Find("end", 0).admin, "main start and end are the admin ones")
check(len(Z.Bonuses()) >= 1, "ready-made bonus kept next to admin zones")
L.execute('SURF.Zones.ResetToMap()')
check(Z.source == "map" and not Z.Find("start", 0).admin, "!zone reset returns to ready-made zones")

# A ready-made zone in a wall means this copy of the map is different
L.execute('''
mapname = "surf_kitsune"
SURF.Zones.Load()
local z = SURF.Zones.Find("end", 0)
solidBoxes = { { z.min, z.max } }
SURF.Zones.Load()
''')
check(Z.source == "none" and not Z.HasTimer(0), f"zones rejected when the end zone is inside a wall ({Z.source})")
check("surf_kitsune" in G.SURF.Zones.KnownBad(), "map remembered as having bad zones")
check(not G.SURF.MapVote.HasZones("surf_kitsune"), "map vote treats it as unzoned")
L.execute('''
SURF.Zones.Save("start", Vector(0, 0, 0), Vector(100, 100, 0))
SURF.Zones.Save("end", Vector(500, 0, 0), Vector(600, 100, 0))
''')
check(Z.source == "admin" and Z.HasTimer(0), "admin zones still work on that map")
check(G.SURF.MapVote.HasZones("surf_kitsune"), "and make it votable again")
L.execute('''
SURF.Zones.ResetToMap()
solidBoxes = {}
SURF.Zones.Load()
''')
check(Z.source == "map" and "surf_kitsune" not in G.SURF.Zones.KnownBad(), "fits again once the world matches")

# Zones that are trigger brushes in the map (SurfTimer "hooked" zones)
L.execute('''
mapname = "surf_25_lighters"
mapEnts = {}
for _, z in ipairs(util.JSONToTable(file.Read("surfline/zones/surf_25_lighters.json"))) do
	if z.hook then mapEnts[#mapEnts + 1] = { name = z.hook, class = "trigger_multiple", min = Vector(0, 0, 0), max = Vector(10, 10, 10) } end
end
SURF.Zones.Load()
''')
check(Z.HasTimer(0), f"hooked zones resolve to the map's trigger brushes ({Z.source})")
L.execute('mapEnts = {} SURF.Zones.Load()')
check(not Z.HasTimer(0), "hooked zones are skipped when the triggers are missing")

# Maps without zone files but with timer triggers built in
L.execute('''
mapname = "surf_nozones_test"
mapEnts = {
	{ name = "mod_zone_start", class = "trigger_multiple", min = Vector(0, 0, 0), max = Vector(100, 100, 100) },
	{ name = "mod_zone_end", class = "trigger_multiple", min = Vector(900, 0, 0), max = Vector(1000, 100, 100) },
	{ name = "mod_zone_bonus_1_start", class = "trigger_multiple", min = Vector(0, 900, 0), max = Vector(100, 1000, 100) },
	{ name = "mod_zone_bonus_1_end", class = "trigger_multiple", min = Vector(900, 900, 0), max = Vector(1000, 1000, 100) },
	{ name = "mod_zone_checkpoint_2", class = "trigger_multiple", min = Vector(400, 0, 0), max = Vector(500, 100, 100) },
	{ name = "door1", class = "trigger_teleport", min = Vector(0, 0, 0), max = Vector(1, 1, 1) },
}
SURF.Zones.Load()
''')
check(Z.source == "triggers" and Z.HasTimer(0) and Z.HasTimer(1) and Z.cpCount[0] == 2,
      f"timer triggers built into the map become zones ({Z.source}, cps {Z.cpCount[0]})")
check("surf_nozones_test" in G.SURF.Zones.KnownZoned(), "map remembered as zoned")
L.execute('mapEnts = {}')

# Map vote: only maps with zones once there are a few of them
L.execute('''
installed_maps = { "surf_kitsune", "surf_lessons", "surf_mesa", "surf_nozones_test", "surf_unknown_map" }
playable = SURF.MapVote.Playable()
info = SURF.MapVote.Info(playable)
''')
playable = list(G.playable.values())
check("surf_unknown_map" not in playable and "surf_kitsune" in playable, f"vote pool leaves out maps without zones ({playable})")
check(G.SURF.MapVote.Tier("surf_kitsune") == 1, f"tier of kitsune is 1 ({G.SURF.MapVote.Tier('surf_kitsune')})")
check(G.SURF.MapVote.Mapper("surf_kitsune") != "", "mapper known for kitsune")

# Server records are logged for the portal
recs = db.execute("select map, name, time, prev_time from surf_records order by id").fetchall()
check(("surf_kitsune", "Bob", 58.5, 60.0) in recs and ("surf_kitsune", "Alice", 60.0, 0.0) in recs, f"surf_records logs each new record ({recs})")

# Portal bridge: status file
L.execute('''
mapname = "surf_kitsune"
SURF.Zones.Load()
SetCurTime(2000)
SURF.Portal.WriteStatus()
''')
st = json.loads(vfs["surfline/portal/status.json"])
check(st["map"] == "surf_kitsune" and st["tier"] == 1 and st["maxplayers"] == 24, "status.json has map, tier and slots")
check(len(st["players"]) == 2 and {p["name"] for p in st["players"]} == {"Alice", "Bob"}, "status.json lists the players")
pa = [p for p in st["players"] if p["name"] == "Alice"][0]
check(pa["steamid"] == "76561190000000001" and pa["ping"] == 42 and pa["title"] in [t["name"] for t in json.loads(G.py_table_to_json(G.SURF.Config.Titles))], "player rows carry steamid, ping and title")
check(st["wr"]["name"] == "Bob" and abs(st["wr"]["time"] - 58.5) < 1e-6, "status.json has the map record")
check(any(m["name"] == "surf_kitsune" and m["zoned"] for m in st["maps"]), "status.json lists maps with zone state")

# Portal bridge: commands
def cmd(name, obj):
    vfs[f"surfline/portal/cmd/{name}.txt"] = json.dumps(obj)
cmd("1_say", {"action": "say", "text": "hello\x07 world", "by": "76561190000000009"})
cmd("2_map", {"action": "changelevel", "map": "surf_mesa"})
cmd("3_badmap", {"action": "changelevel", "map": "surf_not_installed"})
cmd("4_ban", {"action": "ban", "steamid": "76561190000000002", "minutes": 0, "reason": "cheating", "by": "76561190000000009"})
cmd("5_vip", {"action": "givevip", "steamid": "76561190000000001", "days": 30})
cmd("6_bad", {"action": "givevip", "steamid": "123", "days": 30})
cmd("7_what", {"action": "format_c"})
cmd("8_del", {"action": "deltime", "key": "surf_kitsune", "steamid": "76561190000000001"})
L.execute('chats = {} SURF.Portal.RunCommands()')
res = {r["id"]: r for r in map(json.loads, vfs["surfline/portal/results.txt"].strip().split("\n"))}
check(not any(k.startswith("surfline/portal/cmd/") for k in vfs), "command files are deleted after running")
check(res["1_say"]["ok"] and any("hello  world" in c for c in G.chats.values()), "say broadcasts the text without control characters")
check(res["2_map"]["ok"] and G.lastConsole == "changelevel surf_mesa", f"changelevel switches map ({G.lastConsole})")
check(not res["3_badmap"]["ok"], "changelevel refuses maps that aren't installed")
check(res["4_ban"]["ok"] and G.b.kicked and db.execute("select reason, expires from surf_bans where steamid='76561190000000002'").fetchone() == ("cheating", 0), "ban kicks and stores a permanent ban")
banned = L.eval('{ hooks.CheckPassword.surf_bans("76561190000000002") }')
check(banned[1] is False and "cheating" in banned[2], f"banned player is refused on connect ({list(banned.values())})")
check(L.eval('hooks.CheckPassword.surf_bans("76561190000000001")') is None, "other players may connect")
check(res["5_vip"]["ok"] and "give 76561190000000001 30" in G.vipCalls.values(), "givevip grants VIP")
check(not res["6_bad"]["ok"] and not res["7_what"]["ok"], "bad steamid and unknown actions are refused")
check(res["8_del"]["ok"] and db.execute("select count(*) from surf_times where map='surf_kitsune' and steamid='76561190000000001'").fetchone()[0] == 0, "deltime removes the time")
cmd("9_unban", {"action": "unban", "steamid": "76561190000000002"})
L.execute('SURF.Portal.RunCommands()')
check(L.eval('hooks.CheckPassword.surf_bans("76561190000000002")') is None, "unban lets the player back in")

# Every bundled zone file parses and has a main start+end
bad = []
G.anyHook = True
count = 0
for f in sorted(os.listdir(ZONES)):
    if f.endswith(".json"):
        count += 1
        G.mapname = f[:-5]
        L.execute("SURF.Zones.Load()")
        if not Z.HasTimer(0):
            bad.append(f[:-5])
check(not bad and count > 700, f"all {count} zone files give a main start+end (missing: {bad[:20]})")

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
