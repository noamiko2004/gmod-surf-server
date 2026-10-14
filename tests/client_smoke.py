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
vmt.__sub = function(a, b) return Vector(a.x - b.x, a.y - b.y, a.z - b.z) end
function vmt:Rotate() end
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
function Lerp(t, a, b) return a + (b - a) * t end
table.RemoveByValue = function(t, v) for i, x in ipairs(t) do if x == v then table.remove(t, i) return i end end end
math.Round = function(n, d) local m = 10 ^ (d or 0) return math.floor(n * m + 0.5) / m end
math.Clamp = function(n, a, b) return math.min(math.max(n, a), b) end
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
hook = { Add = function(ev, name, fn) hooks = hooks or {} if name ~= "surf_ui" and name ~= "surf_ui_toasts" then hooks[ev] = fn end end }
ent = { LookupSequence = function() return 3 end, ResetSequence = noop, SetAngles = noop, LookupAttachment = function() return 1 end,
	GetAttachment = function() return { Pos = Vector(0, 0, 64), Ang = Angle() } end,
	GetPos = function() return Vector() end, GetForward = function() return Vector(1, 0, 0) end,
	GetRight = function() return Vector(0, 1, 0) end }
drawn = {}
function ClientsideModel(mdl)
	local e = { mdl = mdl }
	function e:GetModelBounds() return Vector(-6, -3, -4), Vector(6, 3, 5) end
	function e:DrawModel() drawn[#drawn + 1] = self.mdl end
	return setmetatable(e, { __index = function(_, k) if k:sub(1, 1):match("%u") then return noop end end })
end
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
function P:Remove() self.removed = true for _, c in ipairs(self.children) do c:Remove() end end
function P:IsHovered() return false end
function P:GetParent() return self.parent end
function P:GetEntity() return ent end
function P:SetSize(w, h) self.w, self.h = w, h end
function P:Clear() for _, c in ipairs(self.children) do c:Remove() end self.children = {} end
function P:GetVBar() return vgui.Create("DVScrollBar", self) end
function P:IsEnabled() return not self.disabled end
function P:SetEnabled(on) self.disabled = not on end
function P:GetPos() return 0, 0 end
function P:GetWide() return self.w end
vgui = { Create = function(class, parent)
	local p = setmetatable({ class = class, parent = parent, children = {}, w = 200, h = 120 }, P)
	if parent then parent.children[#parent.children + 1] = p end
	if class == "DFrame" then
		p.lblTitle, p.btnMaxim, p.btnMinim = vgui.Create("DLabel"), vgui.Create("DButton"), vgui.Create("DButton")
		p.btnClose = vgui.Create("DButton", p)
	end
	panels[#panels + 1] = p
	return p
end }
""")
L.execute(open(os.path.join(GM, "sh_config.lua"), encoding="utf-8").read())
L.execute(open(os.path.join(GM, "shared.lua"), encoding="utf-8").read())
L.execute(open(os.path.join(GM, "cl_ui.lua"), encoding="utf-8").read())
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
# Picking an item, buying and equipping keep the item list (and its scroll
# position); the preview shows everything you have on
L.execute(r"""
f = SURF.UI.Open.shop
f.lookZoom = 0
data = { coins = 5000, owned = { "trail:gold", "hat:cone" }, equipped = { trail = "gold", hat = "cone" }, vip = false,
	tab = "trail", url = "" }
SURF.Menus.shop(data)
grid1, scroll1 = f.grid, f.grid.parent
look1 = f.stage.look
local other
for _, t in ipairs(grid1.children) do other = other or t end
-- the first tile is not the equipped trail (gold), so clicking it changes the selection
other.DoClick(other)
sel2, look2 = f.sel, f.stage.look
same2 = f.grid == grid1 and not grid1.removed and not scroll1.removed
SURF.Menus.shop({ coins = 4000, owned = { "trail:gold", "hat:cone", "trail:red" }, equipped = { trail = "red", hat = "cone" },
	vip = false, tab = "trail", refresh = true, url = "" })
same3, look3, counts3 = f.grid == grid1 and not grid1.removed and not scroll1.removed, f.stage.look, f.counts
-- the preview's own button (Put it on / Take it off) sends to the server
local function find(p, pred)
	for _, c in ipairs(p.children) do
		if pred(c) then return c end
		local r = find(c, pred)
		if r then return r end
	end
end
netlog = {}
local off = find(f.look, function(c) return c.uiText == "Put it on" or c.uiText == "Take it off" end)
if off then off.DoClick(off) end
sentEquip = netlog[1] == "surf.ShopEquip" and netlog[2] == "trail"
-- double-clicking an owned tile puts it on
netlog = {}
local goldTile
for _, t in ipairs(grid1.children) do goldTile = goldTile or t end
for _, t in ipairs(grid1.children) do t.DoDoubleClick(t) end
sentDouble = #netlog > 0
f.stage.OnMouseWheeled(f.stage, 1)
zoom = f.lookZoom
data.tab = "skin"
SURF.Menus.shop(data)
skinSel = SURF.ItemByKey[f.sel]
look4 = f.stage.look
same4 = f.grid == grid1
paintAll()
""")
G2 = G
check(G2.look1.hat is not None and G2.look1.hat.id == "cone" and G2.look1.trail.id == "gold" and not G2.look1.trying,
      "the preview starts on your look: equipped hat and trail")
check(G2.same2 and G2.sel2 != "trail:gold",
      "picking an item keeps the item list (no jump to the top)")
check(G2.look2.trail.key == G2.sel2 and G2.look2.hat.id == "cone",
      "the picked trail is tried on together with the equipped hat")
check(G2.same3 and G2.look3.trail.key == G2.sel2,
      "buying or equipping (a refresh) keeps the item list and the selection")
check(G2.counts3.trail.have >= 3, f"sidebar counts follow the refresh ({G2.counts3.trail.have})")
check(abs(G2.zoom - 0.25) < 1e-9, "scrolling on the preview zooms")
check(G2.sentEquip and G2.sentDouble, "the preview button and double-clicking a tile send equip messages")
check(not G2.same4 and G2.look4.model == G2.skinSel.model and G2.look4.hat.id == "cone",
      "a skin is previewed on the model with your hat on")
# A VIP item still equipped after VIP ran out is a try-on, not "your look";
# the preview body is the model the server says you will spawn as
L.execute(r"""
SURF.Menus.shop({ coins = 0, owned = {}, equipped = { hat = "halo" }, vip = false, tab = "hat", url = "",
	model = "models/player/group01/female_02.mdl" })
expiredSel, expiredLook = f.sel, f.stage.look
-- a long name is cut to fit the nameplate and chat line (no paint errors)
me.Nick = function() return "A Very Long Steam Name That Goes On And On" end
fitted = nil
local simple = draw.SimpleText
draw.SimpleText = function(t, ...) if tostring(t):find("%.%.%.$") then fitted = t end end
data.tab = "tag"
SURF.Menus.shop(data)
paintAll()
draw.SimpleText = simple
me.Nick = function() return "Tester" end
""")
check(G.expiredSel == "hat:halo" and G.expiredLook.trying and G.expiredLook.hat.id == "halo"
      and G.expiredLook.model == "models/player/group01/female_02.mdl",
      "an expired VIP hat shows as a try-on, on the model you will spawn as")
check(G.fitted is not None and len(G.fitted) < 30, f"long names are cut with ... ({G.fitted})")

# The replay bot wears the film camera head (and no shop hat), with the REC light
L.execute(r"""
drawn, sprites = {}, 0
render.DrawSprite = function() sprites = sprites + 1 end
bot = { nw = { surf_replay = true, surf_hat = "cone" } }
function bot:Alive() return true end
function bot:GetNW2Bool(k, d) local v = self.nw[k] if v == nil then return d end return v end
function bot:GetNW2String(k, d) return self.nw[k] or d end
function bot:EyeAngles() return Angle(80, 90, 0) end
function bot:LookupBone() return 6 end
function bot:GetBoneMatrix() return { GetTranslation = function() return Vector(0, 0, 60) end } end
function bot:EyePos() return Vector(0, 0, 64) end
local ok, err = pcall(hooks.PostPlayerDraw, bot)
botErr = not ok and tostring(err) or nil
botDrawn = table.concat(drawn, ",")
botSprites = sprites
""")
check(G.botErr is None and G.botDrawn == "models/dav0r/camera.mdl" and G.botSprites > 0,
      f"the replay bot gets the film camera head and REC light, not a shop hat ({G.botErr} {G.botDrawn} {G.botSprites})")
errs = list(G.errors.values())
check(not errs, f"every panel paints and every button clicks without errors ({errs[:5]})")
check(G.painted > 200, f"enough panels were painted ({G.painted})")
check(G.cone.price is None and G.cone.hidden and G.SURF.Config.Coins.Daily == 40 and G.SURF.Config.VIPPackages[1].days == 3,
      "admin changes reach the client")
check("surf.ShopBuyVIP" in G.netlog.values() or "surf.ShopBuy" in G.netlog.values() or "surf.ShopEquip" in G.netlog.values(),
      "buttons send shop messages")
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
