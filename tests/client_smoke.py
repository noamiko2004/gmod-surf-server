"""Runs the client shop menu (cl_shop.lua) against stubbed Derma, opens every tab
and paints every panel, to catch Lua errors that only show up in game.
Run: python3 tests/client_smoke.py
"""
import os
import sys

from lupa import luajit21

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM = os.path.join(ROOT, "gamemode", "surf", "gamemode")
L = luajit21.LuaRuntime(unpack_returned_tuples=True)
G = L.globals()

L.execute(r"""
CLIENT, SERVER = true, false
local unpack = unpack or table.unpack
function Color(r, g, b, a) return { r = r, g = g, b = b, a = a or 255 } end
color_white = Color(255, 255, 255)
local vmt = {}
vmt.__index = vmt
vmt.__add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end
vmt.__mul = function(a, b) if type(a) == "number" then a, b = b, a end return Vector(a.x * b, a.y * b, a.z * b) end
function Vector(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, vmt) end
local amt = {}
amt.__index = amt
function amt:Forward() return Vector(1, 0, 0) end
function amt:Up() return Vector(0, 0, 1) end
function amt:Right() return Vector(0, 1, 0) end
function amt:RotateAroundAxis() end
function Angle(p, y, r) return setmetatable({ p = p or 0, y = y or 0, r = r or 0 }, amt) end
function Matrix() return { Scale = function() end } end
function HSVToColor(h, s, v) return Color(h % 255, 100, 100) end
function isfunction(f) return type(f) == "function" end
function istable(t) return type(t) == "table" end
function isstring(t) return type(t) == "string" end
function CurTime() return 100 end
function RealTime() return 100 end
function FrameTime() return 0.016 end
function ScrW() return 1920 end
function ScrH() return 1080 end
function IsValid(x) return x ~= nil and x ~= false and (type(x) ~= "table" or not x.removed) end
function Material() return {} end
function AddCSLuaFile() end
function DeriveGamemode() end
GM = {}
team = { SetUp = function() end }
function CreateConVar() return { GetInt = function() return 0 end } end
function include() end
string.Comma = function(n) return tostring(n) end
table.Copy = function(t) local o = {} for k, v in pairs(t) do o[k] = v end return o end
utf8 = utf8 or {}
utf8.codes = function(s) local i = 0 return function() i = i + 1 if i <= #s then return i, s:byte(i) end end end
utf8.char = string.char
os = os
TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER, TEXT_ALIGN_RIGHT = 0, 1, 2
TEAM_SPECTATOR = 1002
FILL, LEFT, RIGHT, TOP, BOTTOM = 1, 2, 3, 4, 5
RENDERGROUP_OPAQUE, MOUSE_LEFT = 1, 107
painted, errors, sounds, netlog = 0, {}, {}, {}
local function noop() end
surface = setmetatable({ GetTextSize = function(t) return #tostring(t) * 8, 16 end, PlaySound = function(s) sounds[#sounds + 1] = s end },
	{ __index = function() return noop end })
draw = setmetatable({}, { __index = function() return noop end })
render = setmetatable({}, { __index = function() return noop end })
input = { IsMouseDown = function() return false end }
gui = { MouseX = function() return 0 end, OpenURL = noop }
chat = { AddText = noop }
net = { Receive = function(n, f) netrecv = netrecv or {} netrecv[n] = f end,
	Start = function(n) netlog[#netlog + 1] = n end, WriteString = function(s) netlog[#netlog + 1] = s end,
	WriteUInt = function(v) netlog[#netlog + 1] = v end, SendToServer = noop }
hook = { Add = function(ev, name, fn) hooks = hooks or {} hooks[ev] = fn end }
ent = { LookupSequence = function() return 3 end, ResetSequence = noop, SetAngles = noop, LookupAttachment = function() return 1 end,
	GetAttachment = function() return { Pos = Vector(0, 0, 64), Ang = Angle() } end }
function ClientsideModel() return setmetatable({}, { __index = function() return noop end }) end
me = { nw = { surf_title = 1 } }
function me:Nick() return "Tester" end
function me:GetModel() return "models/player/group01/male_02.mdl" end
function me:GetNW2Int(k, d) return self.nw[k] or d end
function me:GetNW2String(k, d) return self.nw[k] or d end
function me:GetNW2Bool(k, d) return self.nw[k] or d end
function me:Alive() return true end
function me:ShouldDrawLocalPlayer() return true end
function me:LookupAttachment() return 1 end
function me:GetAttachment() return { Pos = Vector(), Ang = Angle() } end
function LocalPlayer() return me end

panels = {}
local P = {}
P.__index = function(self, k)
	local v = rawget(P, k)
	if v then return v end
	-- Derma methods are CamelCase; anything else is a field that isn't set
	if k:sub(1, 1):match("%u") then return function() return nil end end
	return nil
end
function P:Add(class) return vgui.Create(class, self) end
function P:GetChildren() return self.children end
function P:Remove() self.removed = true end
function P:IsHovered() return false end
function P:GetParent() return self.parent end
function P:GetEntity() return ent end
function P:SetSize(w, h) self.w, self.h = w, h end
function P:Clear() self.children = {} end
vgui = { Create = function(class, parent)
	local p = setmetatable({ class = class, parent = parent, children = {}, w = 200, h = 120 }, P)
	if parent then parent.children[#parent.children + 1] = p end
	panels[#panels + 1] = p
	return p
end }
""")
L.execute(open(os.path.join(GM, "sh_config.lua"), encoding="utf-8").read())
L.execute(open(os.path.join(GM, "shared.lua"), encoding="utf-8").read())
L.execute("SURF.Menus = {}")
L.execute(open(os.path.join(GM, "cl_shop.lua"), encoding="utf-8").read())

fails = []


def check(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        fails.append(m)


L.execute(r"""
function paintAll()
	for _, p in ipairs(panels) do
		if not p.removed then
			for _, fn in ipairs({ "Paint", "PerformLayout" }) do
				local f = rawget(p, fn)
				if f then
					local ok, err = pcall(f, p, p.w, p.h)
					if not ok then errors[#errors + 1] = (p.class or "?") .. "." .. fn .. ": " .. tostring(err) end
					painted = painted + 1
				end
			end
			local le = rawget(p, "LayoutEntity")
			if le then local ok, err = pcall(le, p, ent) if not ok then errors[#errors + 1] = "LayoutEntity: " .. err end end
			local pd = rawget(p, "PostDrawModel")
			if pd then local ok, err = pcall(pd, p, ent) if not ok then errors[#errors + 1] = "PostDrawModel: " .. err end end
		end
	end
end
function clickAll()
	for _, p in ipairs(panels) do
		if not p.removed and rawget(p, "DoClick") and p.class == "DButton" then
			local ok, err = pcall(p.DoClick, p)
			if not ok then errors[#errors + 1] = "DoClick: " .. tostring(err) end
		end
	end
end
local data = { coins = 5000, owned = { "trail:gold", "hat:cone" }, equipped = { trail = "gold", hat = "cone" }, vip = false,
	tab = "trail", url = "https://store.example", rates = SURF.Config.Coins, vipPackages = SURF.Config.VIPPackages }
SURF.Menus.shop(data)
paintAll()
for _, c in ipairs(SURF.ShopCategories) do
	shopFrame_tab = c.id
	data.tab = c.id
	SURF.Menus.shop(data)
	paintAll()
end
data.tab = "vip"
SURF.Menus.shop(data)
paintAll()
data.refresh = true
data.vip, data.expires = true, 0
SURF.Menus.shop(data)
paintAll()
SURF.Menus.vip({ url = "" })
paintAll()
clickAll()
paintAll()
-- admin overrides arrive
net.ReadTable = function() return { items = { ["hat:cone"] = { price = 0, hidden = true } }, coins = { Daily = 40 }, vip = { { days = 3, price = 10 } } } end
netrecv["surf.ShopOverrides"]()
cone = SURF.ItemByKey["hat:cone"]
hooks.PostPlayerDraw(setmetatable({}, { __index = function(_, k) return me[k] end }))
me.nw.surf_hat = "balloon"
hooks.PostPlayerDraw(me)
""")
errs = list(G.errors.values())
check(not errs, f"every panel paints and every button clicks without errors ({errs[:5]})")
check(G.painted > 200, f"enough panels were painted ({G.painted})")
check(G.cone.price is None and G.cone.hidden and G.SURF.Config.Coins.Daily == 40 and G.SURF.Config.VIPPackages[1].days == 3,
      "admin changes reach the client")
check("surf.ShopBuyVIP" in G.netlog.values() or "surf.ShopBuy" in G.netlog.values() or "surf.ShopEquip" in G.netlog.values(),
      "buttons send shop messages")
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
