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


def file_rename(src, dst):
    if src not in vfs:
        return False
    vfs[dst] = vfs.pop(src)
    return True


def file_find(pattern, where, sorting=None):
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
G.py_file_rename = file_rename
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
function vmeta:Length() return math.sqrt(self.x ^ 2 + self.y ^ 2 + self.z ^ 2) end
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
function istable(v) return type(v) == "table" end
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
	return { GetName = function() return e.name end, WorldSpaceAABB = function() return e.min, e.max end,
	         GetPos = function() return e.pos or e.min end, GetAngles = function() return Angle(0, e.yaw or 0, 0) end }
end
function ents_FindByName(name)
	local out = {}
	for _, e in ipairs(mapEnts) do if e.name == name then out[#out + 1] = MockEnt(e) end end
	if anyHook and #out == 0 then out[1] = MockEnt({ name = name, min = Vector(0, 0, 0), max = Vector(64, 64, 64) }) end
	return out
end
function ents_FindByClass(pat)
	local out = {}
	local prefix = string.match(pat, "^(.-)%*$")
	for _, e in ipairs(mapEnts) do
		if e.class == pat or (prefix and string.sub(e.class, 1, #prefix) == prefix) then out[#out + 1] = MockEnt(e) end
	end
	return out
end
-- A straight line through the mock world, stopped by the first solid box
function util_TraceLine(t)
	local d, steps = t.endpos - t.start, 512
	for i = 1, steps do
		local p = t.start + d * (i / steps)
		if bit.band(util_PointContents(p), CONTENTS_SOLID) ~= 0 or not util_IsInWorld(p) then
			return { Fraction = (i - 1) / steps, Hit = true }
		end
	end
	return { Fraction = 1, Hit = false }
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
         IsInWorld = util_IsInWorld, PointContents = util_PointContents, TraceLine = util_TraceLine }
sql = { Query = py_sql_query, SQLStr = function(s) return "'" .. tostring(s):gsub("'", "''") .. "'" end,
        LastError = function() return __sql_error end }
file = { Read = py_file_read, Exists = function(p) return py_file_read(p) ~= nil end, Find = py_file_find,
         CreateDir = function() end, Open = function() return nil end, Write = py_file_write, Append = py_file_append,
         Delete = py_file_delete, Size = py_file_size, Rename = py_file_rename }
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
function math.NormalizeAngle(a) return (a + 180) % 360 - 180 end
function string.Replace(s, find, rep) local i, j = string.find(s, find, 1, true) if not i then return s end return s:sub(1, i - 1) .. rep .. s:sub(j + 1) end
httpCalls = {}
function HTTP(t) httpCalls[#httpCalls + 1] = t return true end

-- Move data and user commands for the movement hooks
function MakeMove(o)
	local mv = {}
	function mv:GetVelocity() return o.vel or Vector(0, 0, 0) end
	function mv:GetAngles() return Angle(o.pitch or 0, o.yaw or 0, 0) end
	function mv:KeyDown(k) return bit.band(o.buttons or 0, k) ~= 0 end
	function mv:KeyPressed(k) return bit.band(o.pressed or 0, k) ~= 0 end
	function mv:GetSideSpeed() return o.side or 0 end
	function mv:GetForwardSpeed() return o.fwd or 0 end
	function mv:GetButtons() return o.buttons or 0 end
	function mv:SetButtons(b) o.buttons = b end
	return mv
end
function MakeCmd(fwd, side, buttons)
	local c = { fwd = fwd, side = side, buttons = buttons }
	function c:GetForwardMove() return self.fwd end
	function c:SetForwardMove(v) self.fwd = v end
	function c:GetSideMove() return self.side end
	function c:SetSideMove(v) self.side = v end
	function c:KeyDown(k) return bit.band(self.buttons, k) ~= 0 end
	function c:RemoveKey(k) self.buttons = bit.band(self.buttons, bit.bnot(k)) end
	return c
end

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
	function p:GetNW2Int(k, d) if nw[k] == nil then if d == nil then return 0 end return d end return nw[k] end
	p.GetNW2Float, p.GetNW2String, p.GetNW2Bool = p.GetNW2Int, p.GetNW2Int, p.GetNW2Int
	function p:GetMoveType() return self.mt end
	function p:SetMoveType(m) self.mt = m end
	function p:GetVelocity() return self.vel end
	function p:SetLocalVelocity(v) self.vel = v end
	function p:SetPos(v) self.pos = v end
	function p:GetPos() return self.pos end
	function p:SetEyeAngles(a) self.eye = a end
	function p:EyeAngles() return self.eye or Angle(0, 0, 0) end
	function p:SendLua() end
	function p:GetObserverTarget() return nil end
	function p:IsAdmin() return false end
	function p:IsUserGroup() return false end
	function p:Spawn() end
	function p:Ping() return 42 end
	function p:TimeConnected() return 120.5 end
	function p:Kick(reason) self.kicked = reason end
	p.gravity, p.ground = 1, false
	function p:SetGravity(g) self.gravity = g end
	function p:OnGround() return self.ground end
	function p:WaterLevel() return 0 end
	p.nw = nw
	return p
end
''')

def include(name):
    L.execute(open(os.path.join(GM, name)).read())

G.include = lambda n: include(n)
include("sh_config.lua")
include("shared.lua")
# The webhook and website address are files deploy.sh writes
vfs["surfline/webhook.txt"] = "https://discord.com/api/webhooks/123456/abc_DEF-ghi\n"
vfs["surfline/portal_url.txt"] = "https://128.140.7.178\n"
for f in ["sv_util.lua", "sv_db.lua", "sv_zones.lua", "sv_stats.lua", "sv_timer.lua", "sv_replay.lua", "sv_ranks.lua", "sv_mapvote.lua",
          "sv_afk.lua", "sv_social.lua", "sv_discord.lua", "sv_discord_bridge.lua", "sv_commands.lua", "sv_portal.lua"]:
    include(f)
# SURF.Chat is real (net stubs); capture messages instead
L.execute('''
SURF.Chat = function(target, ...) local s = "" for _, v in ipairs({...}) do if type(v) == "string" then s = s .. v end end chats[#chats + 1] = s end
specToggles = {}
SURF.Spec = { Toggle = function(p) specToggles[#specToggles + 1] = p.name end }
menus = {}
SURF.Menu.Open = function(ply, kind, data) menus[#menus + 1] = { kind = kind, data = data } end
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

# Discord record feed (the webhook file is set above)
posts = [json.loads(c["body"]) for c in G.httpCalls.values()]
check(len(posts) == 2 and all(c["url"] == "https://discord.com/api/webhooks/123456/abc_DEF-ghi" and c["method"] == "POST" for c in G.httpCalls.values()),
      f"both records were posted to the webhook ({len(posts)})")
d2 = posts[-1]["embeds"][0]
check("**Bob** set the server record on **surf\\_kitsune** with **0:58.500** (-1.500, beating Alice)." == d2["description"], f"record post text ({d2['description']})")
check(d2["url"] == "https://128.140.7.178/maps/surf_kitsune" and not posts[-1]["allowed_mentions"]["parse"], "post links the map page and pings nobody")
check(G.SURF.Discord.Escape("*x_y*") == "\\*x\\_y\\*", "player names can't add Discord formatting")

# Styles: key limits (shared StartCommand hook)
L.execute(r"""
local hk = hooks.StartCommand.surf_style
local all = IN_FORWARD + IN_BACK + IN_MOVELEFT + IN_MOVERIGHT
c_sw = MakeCmd(10000, -10000, all)  a.nw.surf_style = "sw"  hk(a, c_sw)
c_w = MakeCmd(-10000, 10000, all)   a.nw.surf_style = "w"   hk(a, c_w)
c_hsw1 = MakeCmd(0, -10000, IN_MOVELEFT)  a.nw.surf_style = "hsw" hk(a, c_hsw1)
c_hsw2 = MakeCmd(10000, -10000, IN_FORWARD + IN_MOVELEFT) hk(a, c_hsw2)
c_n = MakeCmd(10000, -10000, all)   a.nw.surf_style = "n"   hk(a, c_n)
a.nw.surf_style = nil
""")
check(G.c_sw.side == 0 and G.c_sw.fwd == 10000 and G.c_sw.buttons == 8 + 16, "Sideways keeps W/S and drops A/D")
check(G.c_w.side == 0 and G.c_w.fwd == 0 and G.c_w.buttons == 8, "W-Only drops S, A and D")
check(G.c_hsw1.side == 0 and G.c_hsw1.buttons == 0, "Half-Sideways ignores A on its own")
check(G.c_hsw2.side == -10000 and G.c_hsw2.fwd == 10000, "Half-Sideways allows W+A")
check(G.c_n.side == -10000 and G.c_n.buttons == 8 + 16 + 512 + 1024, "Normal is untouched")

# Styles: own records, same map
L.execute(r"""
chats = {} httpCalls = {}
SURF.Commands.Run(a, "style", { "sw" })
""")
check(G.a.nw["surf_style"] == "sw" and G.a.SurfStyle == "sw", "!style sw switches to Sideways")
check(G.a.nw["surf_pb"] == 0 and G.a.nw["surf_wr"] == 0, "Sideways shows its own (empty) PB and WR")
L.execute(r"""
Run(a, 1100, { { cp2, 15 } }, 75)
""")
row = db.execute("select time from surf_times where map='surf_kitsune@sw' and steamid='76561190000000001'").fetchone()
check(row is not None and abs(row[0] - 75) < 1e-6, f"Sideways time stored under surf_kitsune@sw ({row})")
check(abs(G.globals2["surf_wr"] - 58.5) < 1e-6, "the map record shown everywhere stays the Normal one")
check(any("(Sideways)" in c and "NEW SERVER RECORD" in c for c in G.chats.values()), "Sideways record is announced with the style")
check(G.SURF.Replay.info is None or G.SURF.Replay.info.time != 75, "Sideways runs don't replace the replay")
check("on **Sideways**" in json.loads(G.httpCalls[1]["body"])["embeds"][0]["description"], "Discord post names the style")
L.execute('SURF.Ranks.Recalc()')
check(G.a.nw["surf_points"] == 110 and G.a.nw["surf_rankpos"] == 1,
      f"a Sideways record is worth half (Alice 55 + 55 = {G.a.nw['surf_points']}, rank {G.a.nw['surf_rankpos']})")
L.execute('SURF.Commands.Run(a, "lg", {})')
check(G.a.SurfStyle == "lg" and G.a.gravity == 0.6, "!lg switches to Low Gravity at 60% gravity")
L.execute('SURF.Commands.Run(a, "normal", {})')
check(G.a.SurfStyle == "n" and G.a.gravity == 1 and abs(G.a.nw["surf_pb"] - 60) < 1e-6, "!normal goes back with the Normal PB")
L.execute('chats = {} SURF.Commands.Run(a, "style", { "zz" })')
check(any("Styles:" in c for c in G.chats.values()), "unknown style lists the styles")
L.execute('menus = {} SURF.Commands.Run(a, "style", {})')
check(G.menus[1].kind == "styles" and G.menus[1].data.current == "n", "!style opens the style menu")
L.execute('menus = {} SURF.Commands.Run(a, "wr", { "sw" })')
check(G.menus[1].data.map == "surf_kitsune (Sideways)" and G.menus[1].data.rows[1].time == 75, "!wr sw shows the Sideways top")
L.execute('SURF.DB.SavePlayer(a)')
check(db.execute("select style from surf_players where steamid='76561190000000001'").fetchone()[0] == "n", "style is saved with the player")

# Strafe stats
L.execute(r"""
chats = {}
cara = MakePlayer("Cara", "76561190000000003")
SURF.DB.LoadPlayer(cara) SURF.Timer.SetTrack(cara, 0, true)
SetCurTime(1500)
SURF.Timer.OnZoneEnter(cara, startz)
cara.vel = Vector(300, 0, 0)
SURF.Timer.OnZoneLeave(cara, startz)
local hk = hooks.SetupMove.surf_stats
cara.ground = true
hk(cara, MakeMove({ vel = Vector(290, 0, 0), buttons = IN_JUMP, yaw = 0 }))       -- autohop jump
cara.ground = false
local yaw = 0
for i = 1, 3 do yaw = yaw + 2 hk(cara, MakeMove({ vel = Vector(600 + i * 100, 0, 0), side = -10000, yaw = yaw })) end  -- A + left: good
for i = 1, 2 do yaw = yaw - 2 hk(cara, MakeMove({ vel = Vector(1000, 0, 0), side = 10000, yaw = yaw })) end          -- D + right: good
yaw = yaw + 2 hk(cara, MakeMove({ vel = Vector(2310, 0, 0), side = 10000, yaw = yaw }))                                 -- D + left: bad
SetCurTime(1580)
SURF.Timer.OnZoneEnter(cara, endz)
""")
row = db.execute("select jumps, strafes, sync, maxspeed from surf_times where map='surf_kitsune' and steamid='76561190000000003'").fetchone()
check(row is not None and row[0] == 1 and row[1] == 2 and abs(row[2] - 83.33) < 0.01 and abs(row[3] - 2310) < 0.01,
      f"stats stored with the PB: 1 jump, 2 strafes, 83.33% sync, 2310 max ({row})")
check(G.cara.nw["surf_fin_strafes"] == 2 and abs(G.cara.nw["surf_fin_sync"] - 83.33) < 0.01, "stats shown on the HUD after the finish")
check(any(c.startswith("[Stats] Jumps 1  |  Strafes 2  |  Sync 83.3%") for c in G.chats.values()), f"stats in chat ({[c for c in G.chats.values() if 'Stats' in c]})")
L.execute(r"""
chats = {}
SetCurTime(1600) SURF.Timer.OnZoneEnter(cara, startz) cara.vel = Vector(300, 0, 0) SURF.Timer.OnZoneLeave(cara, startz)
SURF.Timer.ChangeStyle(cara, "sw")
""")
check(G.cara.SurfStats is None, "switching style ends the run's stats")
L.execute(r"""
SURF.Timer.ChangeStyle(cara, "n")
SetCurTime(1700) SURF.Timer.OnZoneEnter(cara, startz) cara.vel = Vector(300, 0, 0) SURF.Timer.OnZoneLeave(cara, startz)
SetCurTime(1790) SURF.Timer.OnZoneEnter(cara, endz)
""")
row = db.execute("select time, jumps, strafes, completions from surf_times where map='surf_kitsune' and steamid='76561190000000003'").fetchone()
check(row == (80.0, 1, 2, 2), f"a slower finish keeps the PB's stats ({row})")
db.execute("insert into surf_times (map, steamid, name, time, date) values ('surf_old', '76561190000000009', 'Old', 50, 1)")
check(db.execute("select jumps, sync from surf_times where map='surf_old'").fetchone() == (None, None), "times from before v4 have no stats")

# Join messages, rank-ups and tips
L.execute(r"""
chats = {}
dan = MakePlayer("Dan", "76561190000000004")
SURF.DB.LoadPlayer(dan)
hook.Run("SurfPlayerReady", dan)
SURF.DB.LoadPlayer(b)  -- Bob comes back
SURF.Ranks.Apply(b)
hook.Run("SurfPlayerReady", b)
a.SurfTitleIdx = 1
SURF.Ranks.Apply(a)
""")
msgs = list(G.chats.values())
check("[Join] Dan joined for the first time. Welcome!" in msgs, f"first visit welcome ({msgs})")
check(any(m.startswith("[Join] Bob joined (") and "#2" in m for m in msgs), f"join message shows title and rank ({msgs})")
check("[Rank] Alice ranked up to Rookie!" in msgs, "rank-up is announced")
L.execute('chats = {} SURF.Ranks.Apply(a)')
check(len(G.chats) == 0, "no announcement without a new title")
tips = [G.SURF.Social.NextTip() for _ in range(len(G.SURF.Config.Tips))]
check(any("https://128.140.7.178" in t for t in tips) and not any("{portal}" in t for t in tips), "tips cycle and fill in the website address")

# AFK players
L.execute(r"""
chats = {} specToggles = {}
SetCurTime(5000)
SURF.AFK.Touch(a) SURF.AFK.Touch(b)
SetCurTime(5000 + 299)
hooks.SetupMove.surf_afk(b, MakeMove({ buttons = IN_FORWARD, yaw = 10 }))
SetCurTime(5000 + 301)
active = SURF.AFK.Active()
SURF.AFK.Check()
""")
check(len(G.active) == 1 and G.active[1].name == "Bob", "Alice is AFK after 5 minutes, Bob moved")
check(list(G.specToggles.values()) == ["Alice"] and any("[AFK]" in c for c in G.chats.values()), "AFK player moved to spectators")

# !mapinfo
L.execute('chats = {} SURF.Commands.Run(a, "mapinfo", {})')
msgs = list(G.chats.values())
check(any("Tier 1" in m and "9 stages" in m for m in msgs) and any("finishers" in m and "record 0:58.500 by Bob" in m for m in msgs),
      f"!mapinfo shows tier, stages and the record ({msgs})")

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

# Facing the way the map goes in the start zone
L.execute('''
sp = SURF.Zones.StartPos(0)
local function Spawn(cls, dx, dy, yaw) mapEnts[#mapEnts + 1] = { class = cls, pos = sp + Vector(dx, dy, 0), yaw = yaw } end
mapEnts = {}
Spawn("info_player_counterterrorist", 40, 0, 90) Spawn("info_player_counterterrorist", 80, 0, 92) Spawn("info_player_counterterrorist", 120, 0, 88)
Spawn("info_player_terrorist", 0, 0, -90)
Spawn("info_player_start", 6000, 0, 0)
Spawn("trigger_teleport", 0, 0, 180)
yaw1, how1 = SURF.Zones.FindStartYaw(0)
solidBoxes = { { sp + Vector(-500, 60, -100), sp + Vector(500, 100, 300) } }
yaw2, how2 = SURF.Zones.FindStartYaw(0)
mapEnts = {}
solidBoxes = {
	{ sp + Vector(100, -1000, -100), sp + Vector(140, 1000, 300) },
	{ sp + Vector(-3000, 100, -100), sp + Vector(1000, 140, 300) },
	{ sp + Vector(-3000, -140, -100), sp + Vector(1000, -100, 300) },
}
yaw3, how3 = SURF.Zones.FindStartYaw(0)
solidBoxes = {}
Spawn("info_player_counterterrorist", 40, 0, 90)
SURF.Zones.Load()
a.eye = nil
SURF.Timer.GoToStart(a, 0)
eye1 = a.eye
''')
check(G.how1 == "spawn" and G.yaw1 == 90, f"faces the way most spawns near the start face ({G.how1} {G.yaw1})")
check(G.how2 == "spawn" and G.yaw2 == -90, f"skips spawn angles that look into a wall ({G.how2} {G.yaw2})")
check(G.how3 == "open" and abs(abs(G.yaw3) - 180) < 0.01, f"without spawns, faces the open way out ({G.how3} {G.yaw3})")
check(G.eye1 is not None and G.eye1.y == 90 and G.eye1.p == 0, "!r turns the player that way")
L.execute('''
a.eye = Angle(10, 45, 0)
SURF.Zones.EditCommand(a, { "angle" })
SURF.Zones.Load()
adminYaw = SURF.Zones.StartYaw(0)
SURF.Timer.GoToStart(a, 0)
eye2 = a.eye
SURF.Zones.ResetToMap()
resetYaw = SURF.Zones.StartYaw(0)
mapEnts = {}
SURF.Zones.Load()
''')
check(G.adminYaw == 45 and G.eye2.y == 45, f"!zone angle sets the facing and survives a reload ({G.adminYaw})")
check(G.resetYaw == 90, f"!zone reset goes back to the map's spawns ({G.resetYaw})")

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

# Hidden maps: the blocked list from the repo and !hidemap
vfs["surfline/blocked_maps.txt"] = "surf_lessons  # too weird\n"
L.execute('''
chats = {}
SURF.Commands.Run(b, "hidemap", { "kitsune" })
notAdmin = file.Read("surfline/hidden_maps.txt", "DATA")
userIsAdmin = a.IsAdmin
a.IsAdmin = function() return true end
SURF.Commands.Run(a, "hidemap", { "mesa" })
playable2 = SURF.MapVote.Playable()
info2 = SURF.MapVote.Info(SURF.MapVote.MapList())
SURF.Commands.Run(a, "unhidemap", {})
''')
playable2 = list(G.playable2.values())
check(G.notAdmin is None, "players who aren't admins can't hide maps")
check("surf_lessons" not in playable2 and "surf_mesa" not in playable2 and "surf_kitsune" in playable2, f"blocked and hidden maps leave the vote pool ({playable2})")
check(vfs.get("surfline/hidden_maps.txt") == "surf_mesa\n", "!hidemap saves the map")
check(any(m["name"] == "surf_mesa" and m["hidden"] for m in G.info2.values()), "map info marks hidden maps")
check(any("Hidden maps: surf_mesa" in c for c in G.chats.values()), "!unhidemap without a match lists hidden maps")
L.execute('''
SURF.Commands.Run(a, "unhidemap", { "mesa" })
playable3 = SURF.MapVote.Playable()
a.IsAdmin = userIsAdmin
''')
check("surf_mesa" in list(G.playable3.values()) and vfs.get("surfline/hidden_maps.txt") == "", "!unhidemap puts it back")
del vfs["surfline/blocked_maps.txt"]

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
check(pa["style"] == "n", "player rows carry the style")

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
cmd("8_del_sw", {"action": "deltime", "key": "surf_kitsune@sw", "steamid": "76561190000000001"})
cmd("8_del_bad", {"action": "deltime", "key": "surf_kitsune@zz", "steamid": "76561190000000001"})
L.execute('SURF.Portal.RunCommands()')
res = {r["id"]: r for r in map(json.loads, vfs["surfline/portal/results.txt"].strip().split("\n"))}
check(res["8_del_sw"]["ok"] and db.execute("select count(*) from surf_times where map='surf_kitsune@sw'").fetchone()[0] == 0, "deltime removes a Sideways time")
check(not res["8_del_bad"]["ok"], "deltime refuses unknown styles")
cmd("9_unban", {"action": "unban", "steamid": "76561190000000002"})
L.execute('SURF.Portal.RunCommands()')
check(L.eval('hooks.CheckPassword.surf_bans("76561190000000002")') is None, "unban lets the player back in")

# Discord bridge: files in surfline/discord/ shared with the bot
OUTBOX, INBOX = "surfline/discord/to_discord/", "surfline/discord/to_game/"
def bridge_events():
    out = [json.loads(vfs.pop(k)) for k in sorted(k for k in list(vfs) if k.startswith(OUTBOX) and k.endswith(".json"))]
    return out
bridge_events()
L.execute(r"""
mapname = "surf_kitsune"
function Say(p, text, team)
	for _, fn in pairs(hooks.PlayerSay or {}) do local r = fn(p, text, team) if r ~= nil then return r end end
	return GM:PlayerSay(p, text, team)
end
chats = {}
SetCurTime(5000)
a.SurfDiscordFlood = nil
said = { Say(a, "hello\nworld"), Say(a, "!r"), Say(a, "!nosuchcommand"), Say(a, "team only", true), Say(a, "   ") }
""")
ev = bridge_events()
check(ev == [{"t": "chat", "sid": "76561190000000001", "name": "Alice", "text": "hello world", "at": ev[0]["at"]}] if ev else False,
      f"public chat goes to Discord, commands and team chat don't ({ev})")
check(G.said[1] == "hello\nworld" and G.said[2] == "", "chat still shows in game and commands stay hidden")
check(not any(k.startswith(OUTBOX) for k in vfs), "no half-written files are left behind")
L.execute(r"""
a.SurfDiscordFlood = nil
for i = 1, 7 do Say(a, "spam " .. i) end
SetCurTime(5011)
Say(a, "later")
""")
ev = bridge_events()
check([e["text"] for e in ev] == ["spam 1", "spam 2", "spam 3", "spam 4", "spam 5", "later"], f"at most 5 lines in 10 seconds per player ({[e['text'] for e in ev]})")
L.execute(r"""
cut = SURF.DiscordBridge.Clean(string.rep("\195\169", 150))
cut3 = SURF.DiscordBridge.Clean("ab" .. string.rep("\226\130\172", 100), 201)
""")
cut = G.cut if isinstance(G.cut, bytes) else G.cut.encode("utf-8", "surrogateescape")
cut3 = G.cut3 if isinstance(G.cut3, bytes) else G.cut3.encode("utf-8", "surrogateescape")
ok = True
for c in (cut, cut3):
    try:
        c.decode("utf-8")
    except UnicodeDecodeError:
        ok = False
check(ok and len(cut) == 200 and len(cut3) == 200, f"cut at a character boundary ({len(cut)}, {len(cut3)})")

# !link
L.execute(r"""
chats = {}
SetCurTime(6000)
hidden = Say(a, "!link abc-12")
Say(a, "!link ZZZ999")
Say(a, "!link")
""")
ev = bridge_events()
check(ev == [{"t": "link", "sid": "76561190000000001", "name": "Alice", "code": "ABC12", "at": ev[0]["at"]}] if ev else False, f"!link sends the code once ({ev})")
check(G.hidden == "" and any("Checking your code" in c for c in G.chats.values()), "!link is hidden from chat and answers")
check(any("Wait a few seconds" in c for c in G.chats.values()) and any("Type /link in our Discord" in c for c in G.chats.values()),
      "!link is rate limited and explains itself without a code")
check(any("!link" in c["cmd"] for c in G.SURF.Commands.HelpList(False).values()), "!link is listed in !help")

# Join, leave and map change
L.execute(r"""
hook.Run("SurfPlayerReady", b)
hooks.PlayerDisconnected.surf_discord_bridge(b)
hooks.InitPostEntity.surf_discord_bridge()
""")
ev = bridge_events()
check([(e["t"], e.get("name"), e.get("count"), e.get("max")) for e in ev[:2]] == [("join", "Bob", 2, 24), ("leave", "Bob", 1, 24)], f"join and leave with the player count ({ev[:2]})")
check(ev[2:] and ev[2]["t"] == "map" and ev[2]["map"] == "surf_kitsune" and ev[2]["tier"] == 1, f"map change with the tier ({ev[2:]})")

# Messages from the bot
vfs[INBOX + "1_00001.json"] = json.dumps({"t": "chat", "name": "Noam\u0007", "text": "gg everyone"})
vfs[INBOX + "1_00002.json"] = json.dumps({"t": "linked", "sid": "76561190000000001", "discord": "noam"})
vfs[INBOX + "1_00003.json"] = "{broken"
vfs[INBOX + "1_00004.json"] = json.dumps({"t": "linkfail", "sid": "76561190000000099", "reason": "nobody here"})
vfs[INBOX + "1_00005.tmp"] = "{}"
for i in range(30):
    vfs[INBOX + f"2_{i:05d}.json"] = json.dumps({"t": "chat", "name": "x", "text": f"m{i}"})
L.execute('chats = {} SURF.DiscordBridge.Poll()')
msgs = list(G.chats.values())
check("[Discord] Noam : gg everyone".replace(" :", ":") in msgs, f"Discord chat shows in game ({msgs[:3]})")
check(any("Linked to noam" in c for c in msgs), "the player hears that the link worked")
check(not any("nobody here" in c for c in msgs), "link answers for players who left are dropped")
left = sorted(k for k in vfs if k.startswith(INBOX))
check(len([k for k in left if k.endswith(".json")]) == 14 and INBOX + "1_00005.tmp" in left, f"20 files per tick, oldest first; .tmp files are left alone ({len(left)})")
L.execute('SURF.DiscordBridge.Poll()')
check(not any(k.endswith(".json") for k in vfs if k.startswith(INBOX)), "the rest is read on the next tick")
del vfs[INBOX + "1_00005.tmp"]

# Command list for the chat hints, !discord and the Discord tip
L.execute(r"""
sent = {}
hook.Run("SurfPlayerReady", b)
userList = SURF.Commands.ClientList(false)
adminList = SURF.Commands.ClientList(true)
""")
names = lambda lst: [n for c in lst.values() for n in c["n"].values()]
check(any(e[1] == "Start" and e[2] == "surf.Commands" for e in G.sent.values()), "players get the command list when they join")
check({"r", "style", "link", "light", "discord", "graphics"} <= set(names(G.userList)) and "hidemap" not in names(G.userList),
      "the list has player commands only")
check("hidemap" in names(G.adminList) and any(c["a"] for c in G.adminList.values()), "admins also get admin commands, marked")
bridge_events()
L.execute(r"""
chats = {}
SURF.Commands.Run(a, "discord", {})
noInvite = SURF.DiscordURL()
""")
check(G.noInvite is None and any("isn't set up yet" in c for c in G.chats.values()), "!discord without an invite says so")
check(not any("{discord}" in (G.SURF.Social.NextTip() or "") or "!discord" in (G.SURF.Social.NextTip() or "") for _ in range(len(G.SURF.Config.Tips))),
      "the Discord tip is skipped without an invite")
vfs["surfline/discord/invite.txt"] = "https://discord.gg/SurfEU42\n"
L.execute(r"""
chats = {}
SURF.Commands.Run(a, "dc", {})
invite = SURF.DiscordURL()
""")
check(G.invite == "https://discord.gg/SurfEU42" and any("https://discord.gg/SurfEU42" in c and "!link" in c for c in G.chats.values()),
      "!discord shows the bot's invite and how to link")
tips = [G.SURF.Social.NextTip() for _ in range(len(G.SURF.Config.Tips))]
check(any("https://discord.gg/SurfEU42" in t for t in tips), "the Discord tip carries the invite")
vfs["surfline/discord/invite.txt"] = "javascript:alert(1)"
check(G.SURF.DiscordURL() is None, "anything but a Discord invite is ignored")
del vfs["surfline/discord/invite.txt"]
L.execute('SURF.ClientAction = function(p, act) lastAction = act end SURF.Commands.Run(a, "light", {})')
check(G.lastAction == "maplight", "!light toggles the map light on the client")

# Bot not running: stop queueing at 500 files
for i in range(500):
    vfs[OUTBOX + f"0_{i:05d}.json"] = "{}"
L.execute(r"""
chats = {}
SetCurTime(9000)
a.SurfLinkAt = nil
Say(a, "anyone there?")
Say(a, "!link ABC123")
""")
check(sum(1 for k in vfs if k.startswith(OUTBOX)) == 500 and any("isn't answering" in c for c in G.chats.values()),
      "nothing more is queued while the bot isn't reading")
bridge_events()

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
