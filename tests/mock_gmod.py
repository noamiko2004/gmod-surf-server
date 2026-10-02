"""Runs the server-side Surfline gamemode against a mock Garry's Mod API.

Uses LuaJIT (same as GMOD) via lupa and a real SQLite database, so SQL,
zone loading, the timer flow, splits, records and ranks get exercised.
Run: python3 tests/mock_gmod.py
"""
import json
import os
import sqlite3
import sys

import lupa.luajit21 as lj

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM = os.path.join(ROOT, "gamemode", "surfline", "gamemode")
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


def file_read(path, where):
    if path.startswith("surfline/zones/"):
        p = os.path.join(ZONES, os.path.basename(path))
        return open(p).read() if os.path.exists(p) else None
    return None


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
util = { AddNetworkString = function() end, JSONToTable = py_json_to_table, TableToJSON = py_table_to_json,
         SteamIDTo64 = function(s) return "7656" end, SpriteTrail = function() return nil end }
sql = { Query = py_sql_query, SQLStr = function(s) return "'" .. tostring(s):gsub("'", "''") .. "'" end,
        LastError = function() return __sql_error end }
file = { Read = py_file_read, Exists = function(p) return py_file_read(p) ~= nil end, Find = function() return {} end,
         CreateDir = function() end, Open = function() return nil end }
globals2 = {}
function SetGlobal2Int(k, v) globals2[k] = v end
SetGlobal2Float, SetGlobal2String = SetGlobal2Int, SetGlobal2Int
function GetGlobal2Float(k, d) return globals2[k] or d end
GetGlobal2Int, GetGlobal2String = GetGlobal2Float, GetGlobal2Float
mapname = "surf_kitsune"
game = { GetMap = function() return mapname end, MaxPlayers = function() return 24 end }
engine = { TickInterval = function() return 0.01 end }
ents = { Create = function() return { SetPos = function() end, Spawn = function() end, Remove = function() end } end }
team = { SetUp = function() end, GetColor = function() return color_white end }
humans = {}
player = { GetHumans = function() return humans end, GetAll = function() return humans end, GetBySteamID64 = function() end }
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
	p.nw = nw
	return p
end
''')

def include(name):
    L.execute(open(os.path.join(GM, name)).read())

G.include = lambda n: include(n)
include("sh_config.lua")
include("shared.lua")
for f in ["sv_util.lua", "sv_db.lua", "sv_zones.lua", "sv_timer.lua", "sv_replay.lua", "sv_ranks.lua"]:
    include(f)
# SURF.Chat is real (net stubs); capture messages instead
L.execute('''
SURF.Chat = function(target, ...) local s = "" for _, v in ipairs({...}) do if type(v) == "string" then s = s .. v end end chats[#chats + 1] = s end
SURF.Spec = { Toggle = function() end }
SURF.VIP = { Load = function() end }
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

# Admin zones override ready-made ones
L.execute('''
SURF.Zones.Save("start", Vector(0, 0, 0), Vector(100, 100, 0))
SURF.Zones.Save("end", Vector(500, 0, 0), Vector(600, 100, 0))
''')
check(Z.source == "admin" and Z.HasTimer(0) and Z.cpCount[0] is None, "admin zones replace ready-made zones")
L.execute('SURF.Zones.ResetToMap()')
check(Z.source == "map", "!zone reset returns to ready-made zones")

# Every bundled zone file parses and has a main start+end
bad = []
for f in sorted(os.listdir(ZONES)):
    if f.endswith(".json"):
        G.mapname = f[:-5]
        L.execute("SURF.Zones.Load()")
        if not Z.HasTimer(0):
            bad.append(f[:-5])
check(not bad, f"all zone files give a main start+end (missing: {bad})")

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
