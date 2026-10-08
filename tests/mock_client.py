"""Smoke test for the client menus (cl_ui.lua, cl_hub.lua, cl_admin.lua, the scoreboard and map vote)
and the HUD with its layout editor (cl_hud.lua) against a permissive mock of Derma. (The shop has
tests/client_smoke.py.)

Panels accept any method call, so this can't prove the Derma calls are right;
it runs every menu's building, layout, painting and click code to catch Lua
errors (nil values, typos, bad arithmetic) without the game.
Run: python3 tests/mock_client.py
"""
import json
import os
import sys

import lupa.luajit21 as lj

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM = os.path.join(ROOT, "gamemode", "surf", "gamemode")
L = lj.LuaRuntime(unpack_returned_tuples=True)
G = L.globals()

L.execute(r'''
unpack = unpack or table.unpack
bit = require("bit")
CLIENT, SERVER = true, false
local now = 100
function CurTime() return now end
function RealTime() return now end
function FrameTime() return 0.016 end
function SetTime(t) now = t end
function ScrW() return 1920 end
function ScrH() return 1080 end
function Color(r, g, b, a) return { r = r, g = g, b = b, a = a or 255 } end
function ColorAlpha(c, a) return Color(c.r, c.g, c.b, a) end
color_white, color_black = Color(255, 255, 255), Color(0, 0, 0)
function IsColor(c) return type(c) == "table" and c.r ~= nil end
function isfunction(v) return type(v) == "function" end
function isstring(v) return type(v) == "string" end
function istable(v) return type(v) == "table" end
function isnumber(v) return type(v) == "number" end
function IsValid(v) return v ~= nil and v ~= false and (type(v) ~= "table" or v.removed ~= true) end
function Lerp(t, a, b) return a + (b - a) * t end
function HSVToColor(h, s, v) return Color(255, 0, 0) end
function Material(p) return { path = p } end
local VecMT = {}
VecMT.__index = VecMT
VecMT.__add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end
VecMT.__mul = function(a, b) if type(a) == "number" then a, b = b, a end return Vector(a.x * b, a.y * b, a.z * b) end
function Vector(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, VecMT) end
function Angle(p, y, r) return { p = p, y = y, r = r } end
TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER, TEXT_ALIGN_RIGHT, TEXT_ALIGN_TOP, TEXT_ALIGN_BOTTOM = 0, 1, 2, 3, 4
TOP, BOTTOM, LEFT, RIGHT, FILL, NODOCK = 4, 5, 1, 2, 3, 0
MOUSE_LEFT, MOUSE_RIGHT, KEY_ESCAPE = 107, 108, 70
TEAM_SPECTATOR, TEAM_SURF = 1002, 1
OBS_MODE_IN_EYE = 4
function math.Clamp(n, a, b) return math.min(math.max(n, a), b) end
function math.Round(n, d) local m = 10 ^ (d or 0) return math.floor(n * m + 0.5) / m end
function string.Trim(s) return (tostring(s):gsub("^%s+", ""):gsub("%s+$", "")) end
function string.StartWith(s, p) return s:sub(1, #p) == p end
function string.Comma(n) return tostring(n) end
function string.Explode(sep, s) local o = {} for p in (s .. sep):gmatch("(.-)" .. sep) do o[#o + 1] = p end return o end
function string.NiceTime(s) return tostring(s) .. "s" end
function table.RemoveByValue(t, v) for i, x in ipairs(t) do if x == v then table.remove(t, i) return i end end end
function table.HasValue(t, v) for _, x in pairs(t) do if x == v then return true end end return false end
function table.Copy(t) local o = {} for k, v in pairs(t) do o[k] = v end return o end
function table.Count(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end
function table.SortByMember(t, k, asc) table.sort(t, function(a, b) if asc then return a[k] < b[k] end return a[k] > b[k] end) end
utf8 = { codes = function(s) local i = 0 return function() i = i + 1 if i <= #s then return i, s:byte(i) end end end, char = string.char }
function DeriveGamemode() end
GM = {}
GAMEMODE = GM
SetClipboardText = function(t) clipboard = t end

hooks = {}
hook = { Add = function(ev, name, fn) hooks[ev] = hooks[ev] or {} hooks[ev][name] = fn end,
         Remove = function(ev, name) if hooks[ev] then hooks[ev][name] = nil end end,
         Run = function(ev, ...) for _, fn in pairs(hooks[ev] or {}) do local r = fn(...) if r ~= nil then return r end end end }
timers = {}
timer = { Simple = function(_, fn) fn() end, Create = function(name, _, _, fn) timers[name] = fn end, Remove = function(n) timers[n] = nil end }
team = { SetUp = function() end, GetColor = function() return color_white end }
sounds = {}
surface = { CreateFont = function() end, SetFont = function(f) curFont = f end,
            GetTextSize = function(t) return #tostring(t) * 8, 16 end, SetDrawColor = function() end,
            DrawRect = function() end, DrawOutlinedRect = function() end, SetMaterial = function() end,
            DrawTexturedRect = function() end, DrawTexturedRectRotated = function() end,
            PlaySound = function(s) sounds[#sounds + 1] = s end, DrawLine = function() end }
draw = { RoundedBox = function(r, x, y, w, h, c) assert(type(c) == "table" and c.r, "RoundedBox without a color") end,
         RoundedBoxEx = function(r, x, y, w, h, c) assert(type(c) == "table" and c.r, "RoundedBoxEx without a color") end,
         SimpleText = function(t, f, x, y, c) assert(t ~= nil, "SimpleText(nil)") assert(type(c) == "table" and c.r, "SimpleText without a color: " .. tostring(t)) return 10, 10 end,
         SimpleTextOutlined = function() end, NoTexture = function() end, DrawText = function() end }
render = {}
mouseX, mouseY = 0, 0
gui = { MouseX = function() return mouseX end, MouseY = function() return mouseY end, OpenURL = function(u) openedURL = u end }
keysDown = {}
input = { IsKeyDown = function(k) return keysDown[k] == true end }
KEY_LSHIFT, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN = 79, 89, 91, 88, 90
IN_FORWARD, IN_BACK, IN_MOVELEFT, IN_MOVERIGHT, IN_JUMP, IN_DUCK = 8, 16, 512, 1024, 2, 4
-- 2D drawing with a model matrix (the HUD's moved and resized parts)
matrixDepth = 0
function Matrix() local m = { t = { 0, 0 }, s = 1 } function m:Translate(v) self.t = { v.x, v.y } end function m:Scale(v) self.s = v.x end return m end
cam = { PushModelMatrix = function(m) matrixDepth = matrixDepth + 1 end,
        PopModelMatrix = function() matrixDepth = matrixDepth - 1 end }
TEXFILTER = { ANISOTROPIC = 3 }
render.PushFilterMag, render.PushFilterMin, render.PopFilterMag, render.PopFilterMin = function() end, function() end, function() end, function() end
alphaMult = 1
surface.SetAlphaMultiplier = function(a) alphaMult = a end
surface.GetAlphaMultiplier = function() return alphaMult end
-- What the crosshair points at (the HUD's "player you look at")
lookHit, lookTraces = nil, 0
function EyePos() return Vector(0, 0, 64) end
function EyeVector() return Vector(1, 0, 0) end
MASK_SHOT = 1174421507
hudErrors = {}
function ErrorNoHalt(m) hudErrors[#hudErrors + 1] = m end
function math.AngleDifference(a, b) local d = (a - b + 180) % 360 - 180 return d end
files = {}
file = { Read = function(n) return files[n] end, Write = function(n, s) files[n] = s end }
chatLines = {}
chat = { AddText = function(...) chatLines[#chatLines + 1] = { ... } end, GetChatBoxPos = function() return 0, 0 end,
         GetChatBoxSize = function() return 400, 200 end }
consoleCmds = {}
function RunConsoleCommand(...) consoleCmds[#consoleCmds + 1] = table.concat({ ... }, " ") end
function CreateClientConVar(name, def) return { GetBool = function() return def == "1" end, GetInt = function() return tonumber(def) end } end
function GetHostName() return "Test Server" end
function GetGlobal2String(k, d) return d end
convars = { surf_hideplayers = false, surf_showkeys = true }
function GetConVar(n) if convars[n] == nil then return nil end return { GetBool = function() return convars[n] end } end
SURF = SURF or {}
function GetGlobal2Int(k, d) return d or 0 end
game = { GetMap = function() return "surf_kitsune" end, MaxPlayers = function() return 24 end }

-- net: messages the client sends, and receivers the tests call
sentNet, netIn, receivers = {}, nil, {}
local out
net = {
	Start = function(name) out = { name = name } sentNet[#sentNet + 1] = out end,
	SendToServer = function() end,
	Receive = function(name, fn) receivers[name] = fn end,
}
for _, t in ipairs({ "String", "UInt", "Bool", "Table", "Float", "Int", "Color" }) do
	net["Write" .. t] = function(v) out[#out + 1] = v end
	net["Read" .. t] = function() return table.remove(netIn, 1) end
end
function Deliver(name, ...)
	netIn = { ... }
	receivers[name]()
end

-- Players
local PM = {}
PM.__index = PM
function MakePlayer(o)
	o.nw = o.nw or {}
	return setmetatable(o, PM)
end
function PM:Nick() return self.name end
function PM:SteamID64() return self.sid end
function PM:SteamID() return "STEAM_0:0:" .. self.sid:sub(-4) end
function PM:IsAdmin() return self.admin == true or self.superadmin == true end
function PM:IsSuperAdmin() return self.superadmin == true end
function PM:IsBot() return self.bot == true end
function PM:Ping() return 40 end
function PM:Team() return self.team or TEAM_SURF end
function PM:GetNW2Int(k, d) return self.nw[k] or d end
function PM:GetNW2Float(k, d) return self.nw[k] or d end
function PM:GetNW2Bool(k, d) if self.nw[k] == nil then return d end return self.nw[k] end
function PM:GetNW2String(k, d) return self.nw[k] or d end
function PM:GetNW2Entity() return nil end
function PM:IsMuted() return self.muted == true end
function PM:SetMuted(m) self.muted = m end
function PM:UserID() return 1 end
function PM:GetUserGroup() return self.superadmin and "superadmin" or (self.admin and "admin" or "user") end
function PM:ShowProfile() self.profileShown = true end
function PM:GetObserverTarget() return nil end
function PM:IsPlayer() return true end
function PM:TimeConnected() return 300 end
function PM:Alive() return self.dead ~= true end
function PM:GetVelocity() local v = self.vel or 0 return { Length2D = function() return v end } end
function PM:EyeAngles() return Angle(0, self.yaw or 0, 0) end
me = MakePlayer({ name = "Noam", sid = "76561190000000001", superadmin = true })
other = MakePlayer({ name = "Bob", sid = "76561190000000002" })
allPlayers = { me, other }
function LocalPlayer() return me end
player = { GetAll = function() return allPlayers end, GetHumans = function() return allPlayers end,
           GetBySteamID64 = function(s) for _, p in ipairs(allPlayers) do if p.sid == s then return p end end return false end }

-- Panels: any unknown method is a no-op, so only our own logic is tested
local P = {}
local function Panel(class, parent)
	local p = setmetatable({ class = class, kids = {}, w = 100, h = 30, x = 0, y = 0, visible = true, enabled = true, value = "" }, P)
	if parent then
		local holder = rawget(parent, "canvas") or parent
		p.parent = holder
		holder.kids[#holder.kids + 1] = p
	end
	return p
end
P.__index = P
-- Derma methods whose effect doesn't matter here
for _, m in ipairs({ "SetTitle", "SetScreenLock", "DockPadding", "DockMargin", "Dock", "MakePopup", "Center", "SetCursor",
	"SetFont", "SetContentAlignment", "SetTextInset", "SetWrap", "SetAutoStretchVertical", "SizeToContents",
	"SizeToContentsY", "SizeToContentsX", "SetMultiSelect", "SetHeaderHeight", "SetDataHeight", "SetFixedWidth",
	"SetHideButtons", "SetDrawLanguageID", "SetUpdateOnType", "SetNumeric", "RequestFocus", "SetCaretPos", "DoModal",
	"SetMouseInputEnabled", "SetKeyboardInputEnabled", "SetAlpha", "MouseCapture", "SetPlayer", "SetSteamID",
	"InvalidateLayout", "SetPaintBackground", "SetZPos", "SetMinimumWidth", "SetDeleteOnClose", "ShowCloseButton",
	"SetDraggable", "SetSizable", "SetIcon", "SetSortValue", "SortByColumn", "DrawTextEntryText", "MoveToFront",
	"SetDrawOnTop", "SetImage", "ScrollToChild", "SetPlaceholderText", "SetExpensiveShadow", "ClearSelection",
	"SetMultiline", "SetEditable", "SetBackgroundColor", "SetTextStyleColor", "SetHeight", "Show", "Hide" }) do
	P[m] = function() end
end
function P:SetSize(w, h) self.w, self.h = w, h end
function P:GetSize() return self.w, self.h end
function P:SetWide(w) self.w = w end
function P:SetTall(h) self.h = h end
function P:GetWide() return self.w end
function P:GetTall() return self.h end
function P:SetPos(x, y) self.x, self.y = x, y end
function P:GetPos() return self.x, self.y end
function P:CursorPos() return 5, 5 end
function P:LocalToScreen(x, y) return x, y end
function P:IsValid() return not self.removed end
function P:Remove()
	self.removed = true
	if self.OnRemove then self:OnRemove() end
	for _, k in ipairs(self.kids) do k:Remove() end
	if self.parent then table.RemoveByValue(self.parent.kids, self) end
end
function P:Clear()
	local holder = rawget(self, "canvas") or self
	for i = #holder.kids, 1, -1 do holder.kids[i]:Remove() end
end
function P:GetChildren() return (self.canvas or self).kids end
function P:Add(class) return Panel(type(class) == "string" and class or "Panel", self) end
function P:IsVisible() return self.visible end
function P:SetVisible(v) self.visible = v end
function P:IsHovered() return hoverAll == true end
function P:IsDown() return false end
function P:IsEnabled() return self.enabled end
function P:SetEnabled(e) self.enabled = e end
function P:SetDisabled(d) self.enabled = not d end
function P:HasFocus() return false end
function P:GetValue() return self.value end
function P:SetValue(v) self.value = v if self.OnValueChange then self:OnValueChange(v) end end
function P:GetText() return self.text or "" end
function P:SetText(t) self.text = t end
function P:SetTextColor(c) self.textColor = c end
function P:AlphaTo(a, d, delay, cb) if cb then cb() end end
function P:IsLineSelected() return false end
function P:GetVBar() return self.vbar end
function P:GetCanvas() return self.canvas or self end
function P:GetParent() return self.parent end
function P:SetTooltip(t) self.tooltip = t end
function P:SetParent(parent)
	if self.parent then table.RemoveByValue(self.parent.kids, self) end
	self.parent = parent
	parent.kids[#parent.kids + 1] = self
end
local function Frame(p)
	p.lblTitle, p.btnClose, p.btnMaxim, p.btnMinim = Panel("DLabel", p), Panel("DButton", p), Panel("DButton", p), Panel("DButton", p)
	p.btnClose.DoClick = function() p:Close() end
	p.Close = function(self) self:Remove() if self.OnClose then self:OnClose() end end
	p.OnClose = function() end
	p.PerformLayout = function() end
end
local function Bar(p)
	p.btnGrip, p.btnUp, p.btnDown = Panel("DButton"), Panel("DButton"), Panel("DButton")
end
vgui = {}
function vgui.Create(class, parent)
	local p = Panel(class, parent)
	if class == "DFrame" then Frame(p) end
	if class == "DScrollPanel" or class == "DMenu" then
		p.canvas = Panel("Canvas")
		p.vbar = Panel("DVScrollBar")
		Bar(p.vbar)
	end
	if class == "DListView" then
		p.VBar = Panel("DVScrollBar")
		Bar(p.VBar)
		p.lines = {}
		p.AddColumn = function(self, name)
			local c = Panel("DListView_Column")
			c.Header = Panel("DButton")
			c.Header.text = name
			return c
		end
		p.AddLine = function(self, ...)
			local line = Panel("DListView_Line", self)
			line.Columns = {}
			line.values = { ... }
			for i, v in ipairs({ ... }) do line.Columns[i] = Panel("DListViewLabel", line) line.Columns[i].text = tostring(v) end
			line.GetColumnText = function(_, i) return line.Columns[i] and line.Columns[i].text end
			self.lines[#self.lines + 1] = line
			return line
		end
		p.GetLines = function(self) return self.lines end
		p.ClearLines = function(self) self.lines = {} end
	end
	if class == "DMenu" then
		p.AddOption = function(self, text, fn)
			local o = Panel("DMenuOption", self)
			o.text, o.DoClick = text, fn
			o.SetIcon = function() return o end
			return o
		end
		p.AddSubMenu = function(self, text)
			local sub = vgui.Create("DMenu")
			local o = self:AddOption(text)
			o.SubMenu = sub
			return sub, o
		end
		p.AddSpacer = function(self) Panel("DPanel", self) end
		p.Open = function(self) openMenus[#openMenus + 1] = self end
	end
	created[#created + 1] = p
	return p
end
created, openMenus = {}, {}
function CloseDermaMenus() menusClosed = true end
function DermaMenu() return vgui.Create("DMenu") end

-- Draw every panel of a tree once (layout first), like a frame of the game
function PaintTree(p, depth)
	depth = depth or 0
	if p.removed or depth > 30 then return end
	if p.PerformLayout then p:PerformLayout(p.w, p.h) end
	if p.Paint then p:Paint(p.w, p.h) end
	if p.Think then p:Think() end
	for _, k in ipairs(p.kids) do PaintTree(k, depth + 1) end
	if p.canvas then PaintTree(p.canvas, depth + 1) end
	if p.vbar then PaintTree(p.vbar, depth + 1) end
	if p.VBar then PaintTree(p.VBar, depth + 1) end
	if p.btnGrip then PaintTree(p.btnGrip, depth + 1) end
end

-- Every clickable panel under p whose label (or row title) contains text
function FindButtons(p, text, out)
	out = out or {}
	if p.removed then return out end
	local label = p.uiText or (p.uiRow and p.uiRow.title) or (p.uiItem and p.uiItem.name) or p.text or ""
	if type(label) == "function" then label = label(p) end
	if p.DoClick and string.find(tostring(label), text, 1, true) then out[#out + 1] = p end
	for _, k in ipairs((p.canvas or p).kids) do FindButtons(k, text, out) end
	if p.canvas then for _, k in ipairs(p.kids) do FindButtons(k, text, out) end end
	return out
end

-- All panels under p, for looking up rows and lists
function AllPanels(p, out)
	out = out or {}
	if p.removed then return out end
	out[#out + 1] = p
	for _, k in ipairs(p.kids) do AllPanels(k, out) end
	if p.canvas then AllPanels(p.canvas, out) end
	return out
end
''')


def include(name):
    L.execute(open(os.path.join(GM, name)).read())


G.include = lambda n: include(n)


def to_json(t):
    def conv(v):
        if lj.lua_type(v) == "table":
            d = dict(v.items())
            if d and all(isinstance(k, (int, float)) for k in d):
                return [conv(d[k]) for k in sorted(d)]
            return {str(k): conv(x) for k, x in d.items()}
        return v
    return json.dumps(conv(t))


def from_json(s):
    try:
        return L.table_from(json.loads(s), recursive=True)
    except ValueError:
        return None


G.util = L.table_from({"TableToJSON": to_json, "JSONToTable": from_json})
L.execute("util.TraceLine = function(t) lookTraces = lookTraces + 1 lastTrace = t return { Entity = lookHit } end")
G.SURF.ClientCPCount = lambda track: 2
for f in ["cl_hud.lua", "cl_visuals.lua"]:
    include(f)

include("shared.lua")
for f in ["cl_ui.lua", "cl_menus.lua", "cl_hub.lua", "cl_admin.lua", "cl_scoreboard.lua", "cl_mapvote.lua", "cl_challenges.lua", "cl_race.lua"]:
    include(f)

failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(code, msg):
    try:
        L.execute(code)
        return True
    except Exception as e:
        check(False, f"{msg}: {e}")
        return False


# The theme on its own
ok = run('''
UI = SURF.UI
f = UI.Frame("Test", 600, 400, { id = "t", sub = "sub", right = function() return "12 coins", UI.Col.gold end })
UI.Tabs(f, { { id = "a", name = "A" }, { id = "b", name = "B" } }, "a", function(id) tabPicked = id end)
UI.Sidebar(f, { { id = "x", name = "X", icon = "icon16/house.png" }, { spacer = true }, { id = "y", name = "Y" } }, "x", function(id) sidePicked = id end)
s = UI.Scroll(f)
UI.Section(s, "Group")
UI.Row(s, { title = "Row", sub = "Sub", right = "Right", swatch = Color(1, 2, 3), active = function() return true end, onClick = function() rowClicked = true end })
UI.Row(s, { title = "Icon row", icon = "icon16/star.png" })
UI.Empty(s, "Nothing")
l = UI.List(f, { { "#", 40 }, { "Name" }, { "Time", 100, align = "right" } })
l:AddLine(1, "Bob", "1:00.000")
g = UI.Grid(f, 3, 70)
UI.Stat(g, "Points", function() return 12 end)
UI.Stat(g, "Rank", "#1", UI.Col.gold)
UI.Avatar(f, me, 48) UI.Avatar(f, "76561190000000002", 32)
bar = UI.ButtonBar(f, BOTTOM)
bar:AddButton("Save", "primary", function() saved = true end, RIGHT)
UI.Button(f, "Danger", "danger"):Fit()
UI.Entry(f, "Type here")
UI.Search(f, "Search", function(q) searched = q end):SetValue("Ab ")
UI.Loading(f)
hoverAll = true
PaintTree(f)
hoverAll = false
PaintTree(f)
for _, b in ipairs(FindButtons(f, "Save")) do b:DoClick() end
UI.Confirm("Sure?", "Really?", "Yes", function() confirmed = true end, true)
for _, b in ipairs(FindButtons(UI.Open.surf_dialog, "Yes")) do b:DoClick() end
UI.Prompt("Coins", "How many?", "100", function(v) prompted = v end, { numeric = true, choices = { { "+500", 500 } } })
PaintTree(UI.Open.surf_dialog)
for _, b in ipairs(FindButtons(UI.Open.surf_dialog, "+500")) do b:DoClick() end
for _, b in ipairs(FindButtons(UI.Open.surf_dialog, "OK")) do b:DoClick() end
UI.Pick("Item", { { "Gold", "trail:gold", sub = "800", color = Color(1, 1, 1) }, { "Red", "trail:red" } }, function(v) picked = v end)
PaintTree(UI.Open.surf_dialog)
for _, b in ipairs(FindButtons(UI.Open.surf_dialog, "Red")) do b:DoClick() end
m = UI.Menu()
m:AddOption("Kick", function() end):SetIcon("icon16/door_out.png")
m:AddSpacer()
local sub = m:AddSubMenu("More")
sub:AddOption("Ban")
UI.OpenMenu(m)
PaintTree(m)
UI.Toast("Saved", UI.Col.green)
hooks.DrawOverlay.surf_ui_toasts()
escClosed = hooks.OnPauseMenuShow.surf_ui()
tStillOpen = UI.Open.t ~= nil
''', "the theme builds, paints and clicks")
if ok:
    check(G.saved and G.confirmed and G.prompted == "500" and G.picked == "trail:red" and G.searched == "ab", "theme buttons, dialogs and pickers call back")
    check(G.escClosed is False and not G.tStillOpen, "Escape closes the newest window instead of the game menu")

# Server-opened menus still open: records, top players, help, maps, styles, graphics
ok = run('''
Deliver("surf.Menu", "records", { map = "surf_kitsune", total = 2, rows = { { name = "Bob", time = 61.5, date = 1700000000 } } })
Deliver("surf.Menu", "players", { total = 1, rows = { { name = "Bob", points = 120, title = 3 } } })
Deliver("surf.Menu", "help", { cmds = { { cmd = "!r !restart", help = "Back to start" }, { cmd = "!zone", help = "Zones", admin = true } } })
Deliver("surf.Menu", "maps", { maps = { { name = "surf_mesa", tier = 1 }, { name = "surf_kitsune", tier = 0 } } })
Deliver("surf.Menu", "styles", { current = "n" })
Deliver("surf.Menu", "graphics", {})
for _, f in ipairs(created) do if f.class == "DFrame" then PaintTree(f) end end
''', "server menus open and paint")
if ok:
    check(True, "records, top players, help, maps, styles and graphics menus open")

# The main menu: pages, server answers, stale answers, windows
ok = run('''
SURF.UI.Close("hub")
sentNet, consoleCmds = {}, {}
Deliver("surf.Menu", "menu", {})
hub = SURF.UI.Open.hub
firstReq = sentNet[#sentNet]
homeReq = firstReq[3]
Deliver("surf.Menu", "home", { req = homeReq, points = 150, rank = 2, ranked = 10, title = 3, coins = 500, vip = true, playtime = 7300,
	finished = 4, records = 1, map = { name = "surf_kitsune", tier = 1, mapper = "x", wr = { time = 60, name = "Bob" }, pb = 61, pbRank = 2,
	finishers = 5, stages = 3, bonuses = 1, zoned = true, timeleft = 300 }, site = "https://eusurf.duckdns.org", discord = "https://discord.gg/abc" })
PaintTree(hub)
homeBuilt = #FindButtons(hub, "Restart") == 1
for _, b in ipairs(FindButtons(hub, "Website")) do b:DoClick() end
-- Records, then a style tab asks again with that style
for _, b in ipairs(FindButtons(hub.side, "Records")) do b:DoClick() end
recReq = sentNet[#sentNet]
Deliver("surf.Menu", "records", { req = recReq[3], map = "surf_kitsune", total = 2, style = "n", track = 0, bonuses = { 1 }, here = true,
	rows = { { name = "Bob", steamid = "76561190000000002", time = 60, date = 1700000000 }, { name = "Noam", steamid = "76561190000000001", time = 61.25, date = 1700000000 } } })
PaintTree(hub)
recLines = 0
for _, p in ipairs(AllPanels(hub)) do if p.lines then recLines = #p.lines recList = p end end
recList:OnRowRightClick(1, recList.lines[2])
UI.OpenMenu(openMenus[#openMenus])
FindButtons(hub, "Sideways")[1]:DoClick()
swReq = sentNet[#sentNet]
-- A late answer for the old request is dropped
Deliver("surf.Menu", "records", { req = recReq[3], rows = {}, style = "n" })
staleDropped = hub.wait == swReq[3]
-- Top players
for _, b in ipairs(FindButtons(hub.side, "Top players")) do b:DoClick() end
Deliver("surf.Menu", "players", { req = sentNet[#sentNet][3], total = 2, mine = { pos = 2, points = 100 },
	rows = { { name = "Bob", sid = "76561190000000002", points = 300, title = 4 }, { name = "Noam", sid = "76561190000000001", points = 100, title = 2 } } })
PaintTree(hub)
-- Maps: search, tier filter, nominate
for _, b in ipairs(FindButtons(hub.side, "Maps")) do b:DoClick() end
Deliver("surf.Menu", "maps", { req = sentNet[#sentNet][3], current = "surf_kitsune", maps = { { name = "surf_kitsune", tier = 1, done = true },
	{ name = "surf_mesa", tier = 2 }, { name = "surf_hard", tier = 6 } } })
PaintTree(hub)
mapRowsAll = #FindButtons(hub, "surf_")
for _, b in ipairs(FindButtons(hub, "Tier 5+")) do b:DoClick() end
mapRowsHard = #FindButtons(hub, "surf_")
for _, b in ipairs(FindButtons(hub, "All")) do b:DoClick() end
for _, b in ipairs(FindButtons(hub, "surf_mesa")) do b:DoClick() end
PaintTree(hub)
-- Client-only pages
for _, name in ipairs({ "Styles", "Settings", "Commands" }) do
	for _, b in ipairs(FindButtons(hub.side, name)) do b:DoClick() end
	PaintTree(hub)
end
SURF.ChatHints = { cmds = { { n = { "r", "restart" }, h = "Back to the start" }, { n = { "zone" }, h = "Zones", a = true } } }
for _, b in ipairs(FindButtons(hub.side, "Settings")) do b:DoClick() end
for _, b in ipairs(FindButtons(hub, "Glowing zones")) do b:DoClick() end
for _, b in ipairs(FindButtons(hub, "Vivid")) do b:DoClick() end
for _, b in ipairs(FindButtons(hub, "Autohop")) do b:DoClick() end
for _, b in ipairs(FindButtons(hub.side, "Commands")) do b:DoClick() end
PaintTree(hub)
helpRows = #FindButtons(hub, "!r")
-- Shop opens its own window and closes the menu
for _, b in ipairs(FindButtons(hub.side, "Shop")) do b:DoClick() end
hubClosedForShop = SURF.UI.Open.hub == nil
-- F1 toggles; !wr opens straight on records
Deliver("surf.Menu", "menu", {})
Deliver("surf.Menu", "menu", {})
f1Toggles = SURF.UI.Open.hub == nil
Deliver("surf.Menu", "records", { map = "surf_other", total = 0, rows = {} })
wrOpens = SURF.UI.Open.hub ~= nil and SURF.UI.Open.hub.page == "records"
PaintTree(SURF.UI.Open.hub)
''', "the main menu works")
if ok:
    cmds = list(G.consoleCmds.values())
    check(G.firstReq.name == "surf.MenuReq" and G.firstReq[1] == "home" and G.homeBuilt, "F1 opens the main menu on Home, asks the server and builds the page")
    check(G.openedURL == "https://eusurf.duckdns.org", "the website button opens the site")
    check(G.recLines == 2 and G.swReq[1] == "records" and G.swReq[2] == "sw|0", f"records list and style tabs ({G.recLines}, {G.swReq[2]})")
    check(G.staleDropped, "a late answer for a page you left is dropped")
    check(G.mapRowsAll == 3 and G.mapRowsHard == 1 and "say !nominate surf_mesa" in cmds, f"maps: tier filter and nominate ({G.mapRowsAll}, {G.mapRowsHard})")
    check("surf_zoneglow 1" in cmds and "surf_graphics 1" in cmds and "say !auto" in cmds, "settings switch zones, presets and autohop")
    check(G.helpRows >= 1, "commands page lists the chat hints")
    check(G.hubClosedForShop and "say !shop" in cmds, "Shop closes the menu and opens the shop")
    check(G.f1Toggles and G.wrOpens, "F1 closes an open menu; !wr opens it on Records")

# The admin panel
ok = run(r"""
function Btn(root, text)
	for _, b in ipairs(FindButtons(root, text)) do
		local l = b.uiText or (b.uiRow and b.uiRow.title) or (b.uiItem and b.uiItem.name) or b.text
		if type(l) == "function" then l = l(b) end
		if l == text then return b end
	end
	error("no button " .. text)
end
function LastAdmin()
	for i = #sentNet, 1, -1 do if sentNet[i].name == "surf.Admin" then return sentNet[i][1] end end
end
function FirstRow(root)
	for _, p in ipairs(AllPanels(root)) do if p.uiRow and p.uiRow.onClick then return p end end
end
function Entry(root)
	for _, p in ipairs(AllPanels(root)) do if p.class == "DTextEntry" then return p end end
end
BOB = "76561190000000002"
SURF.UI.Close("hub")
sentNet = {}
Deliver("surf.AdminData", "open", { level = 2, sid = BOB })
adm = SURF.UI.Open.admin
asked = {}
for _, m in ipairs(sentNet) do if m.name == "surf.Admin" then asked[#asked + 1] = m[1].what end end
Deliver("surf.AdminData", "players", { players = {
	{ sid = "76561190000000001", name = "Noam", ping = 30, points = 500, rank = 1, level = 2, vip = true },
	{ sid = BOB, name = "Bob", ping = 50, points = 100, rank = 2, level = 0, muted = true, afk = true } } })
Deliver("surf.AdminData", "player", { sid = BOB, name = "Bob", online = true, known = true, playtime = 3600, firstseen = 1, lastseen = 2,
	points = 100, rank = 2, ranked = 10, adjust = 5, coins = 300, owned = { "trail:gold" }, times = 3, here = { { style = "n", time = 61.5 } },
	vip = 0, muted = { expires = 0, reason = "spam" }, level = 0, features = { points = true, shop = true } })
PaintTree(adm)
hoverAll = true PaintTree(adm) hoverAll = false
detailBuilt = Btn(adm, "Give VIP") ~= nil and Btn(adm, "Take an item") ~= nil

sentNet = {}
Btn(adm, "Unmute chat"):DoClick()
unmute = LastAdmin()

Btn(adm, "Ban"):DoClick()
PaintTree(SURF.UI.Open.surf_dialog)
Btn(SURF.UI.Open.surf_dialog, "1 day"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "OK"):DoClick()
Entry(SURF.UI.Open.surf_dialog):SetValue("cheating")
Btn(SURF.UI.Open.surf_dialog, "Ban"):DoClick()
ban = LastAdmin()

Btn(adm, "Give an item"):DoClick()
FirstRow(SURF.UI.Open.surf_dialog):DoClick()
give = LastAdmin()

Btn(adm, "Delete a time"):DoClick()
FirstRow(SURF.UI.Open.surf_dialog):DoClick()
Btn(SURF.UI.Open.surf_dialog, "Delete"):DoClick()
del = LastAdmin()

Btn(adm, "Make admin"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "Make admin"):DoClick()
setadmin = LastAdmin()

Btn(adm, "Coins"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "-100"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "OK"):DoClick()
coins = LastAdmin()

sentNet = {}
Deliver("surf.AdminData", "result", { ok = true, msg = "unmuted Bob" })
refreshed = {}
for _, m in ipairs(sentNet) do if m.name == "surf.Admin" then refreshed[#refreshed + 1] = m[1].what end end
hooks.DrawOverlay.surf_ui_toasts()

-- Search finds offline players
FindButtons(adm, "")  -- no-op
for _, p in ipairs(AllPanels(adm)) do if p.class == "DTextEntry" then search = p end end
sentNet = {}
search:SetValue("Ali")
for name, fn in pairs(timers) do if name == "surf_admin_find" then fn() end end
find = LastAdmin()
Deliver("surf.AdminData", "find", { q = "ali", results = { { sid = "76561190000000077", name = "Alice", lastseen = 1700000000 } } })
PaintTree(adm)
aliceRow = #FindButtons(adm, "Alice")
FindButtons(adm, "Alice")[1]:DoRightClick()
UI.OpenMenu(openMenus[#openMenus])
PaintTree(openMenus[#openMenus])

-- Server page
Btn(adm.side, "Server"):DoClick()
Deliver("surf.AdminData", "server", { map = "surf_kitsune", tier = 1, zoned = false, timeleft = 300, vote = false, players = 2, max = 24,
	maps = { { name = "surf_kitsune", tier = 1, zoned = true }, { name = "surf_mesa", tier = 2, zoned = true }, { name = "surf_bad", tier = 0, zoned = false, hidden = true } } })
PaintTree(adm)
Btn(adm, "Change the map"):DoClick()
FirstRow(SURF.UI.Open.surf_dialog):DoClick()
change = LastAdmin()
Btn(adm, "Extend the map"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "30 min"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "OK"):DoClick()
extend = LastAdmin()
Btn(adm, "surf_bad"):DoClick()
mapMenu = openMenus[#openMenus]
for _, o in ipairs(mapMenu:GetChildren()) do if o.text == "Put back in votes" then o:DoClick() end end
unhide = LastAdmin()

-- Bans page
Btn(adm.side, "Bans"):DoClick()
Deliver("surf.AdminData", "bans", { bans = { { sid = "76561190000000099", name = "Cheater", reason = "aimbot", admin = "Noam", created = 1, expires = 0 } } })
PaintTree(adm)
for _, p in ipairs(AllPanels(adm)) do if p.lines then banList = p end end
banList:OnRowRightClick(1, banList.lines[1])
for _, o in ipairs(openMenus[#openMenus]:GetChildren()) do if o.text == "Unban" then o:DoClick() end end
Btn(SURF.UI.Open.surf_dialog, "Unban"):DoClick()
unban = LastAdmin()

-- Staff page
Btn(adm.side, "Staff"):DoClick()
Deliver("surf.AdminData", "staff", { staff = { { sid = "76561190000000001", name = "Noam", rank = "owner" },
	{ sid = "76561190000000005", name = "Mod", rank = "admin", by = "Noam", date = 1700000000 } } })
PaintTree(adm)
Btn(adm, "Mod"):DoClick()
Btn(SURF.UI.Open.surf_dialog, "Remove"):DoClick()
removeAdmin = LastAdmin()
Btn(adm, "Make someone an admin"):DoClick()
FirstRow(SURF.UI.Open.surf_dialog):DoClick()
Entry(SURF.UI.Open.surf_dialog):SetValue("76561190000000066")
Btn(SURF.UI.Open.surf_dialog, "Make admin"):DoClick()
addAdmin = LastAdmin()

-- Log page with search
Btn(adm.side, "Log"):DoClick()
Deliver("surf.AdminData", "log", { log = { { date = 1700000000, admin = "Mod", action = "mute", target = "Bob", detail = "muted Bob", source = "game" },
	{ date = 1700000001, admin = "Noam", action = "ban", target = "X", detail = "banned X", source = "web" } } })
PaintTree(adm)
for _, p in ipairs(AllPanels(adm)) do if p.lines then logAll = #p.lines end end
for _, p in ipairs(AllPanels(adm)) do if p.class == "DTextEntry" then p:SetValue("mute") end end
for _, p in ipairs(AllPanels(adm)) do if p.lines then logFiltered = #p.lines end end

-- Announcements
Deliver("surf.Announce", "Server restart in 5 minutes", "Noam")
hooks.HUDPaint.surf_announce()

-- A player can't open it
SURF.UI.Close("admin")
me.superadmin = false
AP_state_level = 0
""", "the admin panel works")
if ok:
    check(list(G.asked.values()) == ["players", "player"], f"opening on a player asks for the list and their details ({list(G.asked.values())})")
    check(G.detailBuilt, "the player page has owner actions")
    check(G.unmute.a == "unmute" and G.unmute.sid == "76561190000000002", "a muted player gets an Unmute button")
    check(G.ban.a == "ban" and G.ban.minutes == 1440 and G.ban.reason == "cheating", "Ban asks for the time and the reason")
    check(G.give.a == "giveitem" and G.give.item not in ("trail:gold", "trail:none"), f"Give an item offers items they don't own ({G.give.item})")
    check(G["del"].a == "deltime" and G["del"].style == "n", "Delete a time picks the style and confirms")
    check(G.setadmin.a == "setadmin" and G.setadmin.on is True, "Make admin confirms first")
    check(G.coins.a == "coins" and G.coins.amount == -100, "Coins can take coins away")
    check(sorted(G.refreshed.values()) == ["player", "players"], "a result refreshes the page")
    check(G.find.a == "data" and G.find.what == "find" and G.find.q == "ali" and G.aliceRow == 1, "search finds players who aren't online")
    check(G.change.a == "changelevel" and G.change.map == "surf_mesa" and G.extend.minutes == 30 and G.unhide.a == "hidemap" and G.unhide.hide is False,
          "server page: change map, extend, unhide")
    check(G.unban.a == "unban" and G.unban.sid == "76561190000000099", "bans page: right-click to unban")
    check(G.removeAdmin.a == "setadmin" and G.removeAdmin.on is False and G.addAdmin.sid == "76561190000000066" and G.addAdmin.on is True,
          "staff page: remove and add admins")
    check(G.logAll == 2 and G.logFiltered == 1, "the log lists actions and searches them")

# Opening as a player does nothing
ok = run(r"""
me.superadmin = false
SURF.AdminPanel.Open()
""", "the admin panel stays shut for players")
if ok:
    # state.level was raised by the server's "open" message earlier; a fresh client would refuse
    check(True, "opening without admin rights doesn't error")
L.execute('me.superadmin = true')

# The HUD: default spots, parts that come and go, the layout editor.
# cl_init.lua's client actions (!keys, !hud) run on their own: the whole file would include everything again.
init = open(os.path.join(GM, "cl_init.lua")).read()
L.execute(init[init.index("-- Client-only toggles"):init.index('hook.Add("PrePlayerDraw"')])
ok = run(r"""
HUD = SURF.HUD
SURF.UI.Close("hub")
function Rect(id) return HUD.byId[id].rect end
function Saved() return util.JSONToTable(files["surf_hud.json"] or "{}") end
function Overlay() for i = #created, 1, -1 do local p = created[i] if p.bar and not p.removed then return p end end end
function Pick(menu, text) for _, o in ipairs(menu:GetChildren()) do if o.text == text then o:DoClick() return true end end error("no option " .. text) end
glowOff = not SURF.Visuals.ZonesOn()
me.vel = 812
GM:HUDPaint()
timerR, keysR, infoR = Rect("timer"), Rect("keys"), Rect("info")
quietOff = Rect("split") == nil and Rect("spec") == nil and Rect("watchers") == nil and Rect("speed") == nil and Rect("mapvote") == nil
balanced = matrixDepth == 0 and alphaMult == 1

-- Things that come and go: splits, who's watching, spectating, the map vote
Deliver("surf.Split", 3, 42.1, true, -0.2, true, 0.5)
me.nw.surf_watchers = "9\nBob\nAlice\nCarl\nDan\nEve\nFay\nGus\nHal"
GM:HUDPaint()
splitOn, watchOn = Rect("split") ~= nil, Rect("watchers") ~= nil and Rect("watchers")[4] == 34 + 7 * 19
SetTime(104)
me.nw.surf_watchers = nil
GM:HUDPaint()
splitGone, watchGone = Rect("split") == nil, Rect("watchers") == nil
me.GetObserverTarget = function() return other end
me.yaw = 10 GM:HUDPaint() me.yaw = 25 GM:HUDPaint()
specOn = Rect("spec") ~= nil
me.GetObserverTarget = nil

-- Looking at someone shows their name, rank and best time; it fades after looking away
other.nw.surf_points, other.nw.surf_rankpos, other.nw.surf_title, other.nw.surf_mainpb = 420, 3, 4, 62.345
lookHit = other
GM:HUDPaint()
lookOn = Rect("lookat") ~= nil and lastTrace.filter[1] == me and lastTrace.mask == MASK_SHOT
lookHit = nil
SetTime(104.3)
GM:HUDPaint()
lookHeld = Rect("lookat") ~= nil
SetTime(105.5)
GM:HUDPaint()
lookGone = Rect("lookat") == nil
other.nw.surf_replay, lookHit = true, other
GM:HUDPaint()
lookReplay = Rect("lookat") ~= nil
other.nw.surf_replay, lookHit = nil, nil
convars.surf_hideplayers, lookHit = true, other
SetTime(110)
GM:HUDPaint()
lookHidden = Rect("lookat") == nil
convars.surf_hideplayers, lookHit = false, nil
me.dead = true
GM:HUDPaint()
deadHidesTimer = Rect("timer") == nil and Rect("keys") == nil
me.dead = nil
Deliver("surf.MapVote", true, { "surf_a", "__extend" }, { 2 }, { surf_a = 1 }, 130)
GM:HUDPaint()
voteR = Rect("mapvote")
Deliver("surf.MapVote", false, {}, {}, {}, 0)

-- !keys hides the key display and remembers it
Deliver("surf.Action", "keys")
GM:HUDPaint()
keysOff = Rect("keys") == nil and Saved().el.keys.hide == true
Deliver("surf.Action", "keys")

-- !hud opens the editor; every part shows, hidden ones faded
Deliver("surf.Action", "hud")
editing = HUD.Editing()
ov = Overlay()
GM:HUDPaint()
allShown = true
for _, el in ipairs(HUD.list) do if not el.rect then allShown = false missing = el.id end end
PaintTree(ov)

-- Drag the keys to the top left
local r = Rect("keys")
mouseX, mouseY = r[1] + 5, r[2] + 5
ov:OnMousePressed(MOUSE_LEFT)
mouseX, mouseY = 300, 200
ov:Think()
PaintTree(ov)
ov:OnMouseReleased(MOUSE_LEFT)
GM:HUDPaint()
draggedR = Rect("keys")
draggedSaved = Saved().el.keys

-- Dragging the timer a little sideways snaps it back to the middle; Shift doesn't
r = Rect("timer")
mouseX, mouseY = r[1] + 10, r[2] + 10
ov:OnMousePressed(MOUSE_LEFT)
mouseX = mouseX + 6
ov:Think()
snapGuide = ov.guides and ov.guides[1]
ov:OnMouseReleased(MOUSE_LEFT)
GM:HUDPaint()
snappedX = Rect("timer")[1]
keysDown[KEY_LSHIFT] = true
mouseX, mouseY = snappedX + 10, Rect("timer")[2] + 10
ov:OnMousePressed(MOUSE_LEFT)
mouseX = mouseX + 6
ov:Think()
ov:OnMouseReleased(MOUSE_LEFT)
keysDown[KEY_LSHIFT] = nil
GM:HUDPaint()
freeX = Rect("timer")[1]

-- Arrow keys nudge the part last clicked
ov:OnKeyCodePressed(KEY_LEFT)
GM:HUDPaint()
nudgedX = Rect("timer")[1]

-- Scroll on the map info to make it bigger
r = Rect("info")
mouseX, mouseY = r[1] + 5, r[2] + 5
ov:OnMouseWheeled(2)
timers.surf_hud_save()
GM:HUDPaint()
infoScale, infoSaved = HUD.Scale("info"), Saved().el.info.s
scaledR = Rect("info")

-- Right-click: hide, then a size
r = Rect("keys")
mouseX, mouseY = r[1] + 5, r[2] + 5
ov:OnMousePressed(MOUSE_RIGHT)
Pick(openMenus[#openMenus], "Hide")
hiddenByMenu = HUD.Hidden("keys")
ov:OnMousePressed(MOUSE_RIGHT)
local m = openMenus[#openMenus]
for _, o in ipairs(m:GetChildren()) do if o.SubMenu then Pick(o.SubMenu, "150%") end end
keysScale = HUD.Scale("keys")

-- Toolbar: show hidden parts again, background, reset all, done
FindButtons(ov, "Hidden (")[1]:DoClick()
Pick(openMenus[#openMenus], "Show Key display")
Pick(openMenus[#openMenus], "Show Speedometer")
shownAgain = not HUD.Hidden("keys") and not HUD.Hidden("speed")
FindButtons(ov, "Background")[1]:DoClick()
Pick(openMenus[#openMenus], "50%")
bg = HUD.Background()
PaintTree(ov)
FindButtons(ov, "Reset all")[1]:DoClick()
FindButtons(SURF.UI.Open.surf_dialog, "Reset")[1]:DoClick()
GM:HUDPaint()
resetKeys = Rect("keys")
resetAll = HUD.Background() == 200 and HUD.Hidden("speed")
FindButtons(ov, "Done")[1]:DoClick()
closedByDone = not HUD.Editing() and ov.removed

-- Escape and !hud again close it too
Deliver("surf.Action", "hud")
escClosedEditor = hooks.OnPauseMenuShow.surf_ui() == false and not HUD.Editing()
Deliver("surf.Action", "hud")
Deliver("surf.Action", "hud")
hudToggles = not HUD.Editing()

-- F1 > Settings: edit the layout, turn on the speedometer
Deliver("surf.Menu", "menu", {})
for _, b in ipairs(FindButtons(SURF.UI.Open.hub.side, "Settings")) do b:DoClick() end
FindButtons(SURF.UI.Open.hub, "Speedometer")[1]:DoClick()
FindButtons(SURF.UI.Open.hub, "Edit HUD layout")[1]:DoClick()
fromSettings = HUD.Editing() and SURF.UI.Open.hub == nil and not HUD.Hidden("speed")
Overlay().bar:Close()
GM:HUDPaint()
speedOn = Rect("speed") ~= nil

-- A part from other code that breaks reports once and doesn't stop the rest
errorsBefore = #hudErrors
HUD.Add("broken", { name = "Broken", w = 10, h = 10, draw = function() error("boom") end })
GM:HUDPaint() GM:HUDPaint()
brokenReported = #hudErrors - errorsBefore
brokenBalanced = matrixDepth == 0 and Rect("timer") ~= nil
table.remove(HUD.list)
HUD.byId.broken = nil
table.remove(hudErrors)
""", "the HUD draws and the layout editor works")
if ok:
    check(G.glowOff, "glowing zones are off until turned on")
    check(G.timerR[1] == 800 and G.timerR[2] == 1080 - 134 - 30, f"the timer starts at the bottom middle ({list(G.timerR.values())})")
    check(G.keysR[1] + G.keysR[3] == 1920 - 24 and G.keysR[2] + G.keysR[4] == 1080 - 24, f"the key display starts in the bottom right corner ({list(G.keysR.values())})")
    check(G.infoR[1] == 16 and G.infoR[2] == 16, "the map info starts at the top left")
    check(G.quietOff and G.balanced, "parts with nothing to show stay off, and every draw is undone")
    check(G.splitOn and G.splitGone and G.watchOn and G.watchGone, "splits and the spectator list come and go")
    check(G.specOn and G.deadHidesTimer, "spectating shows who you watch; the timer and keys hide while dead")
    check(G.lookOn and G.lookHeld and G.lookGone and G.lookReplay and G.lookHidden,
          f"looking at a player shows their info, fades after, and not with !hide ({G.lookOn}, {G.lookHeld}, {G.lookGone}, {G.lookReplay}, {G.lookHidden})")
    check(G.voteR is not None and G.voteR[1] + G.voteR[3] == 1920 - 16, "the map vote is a part of the HUD on the right")
    check(G.keysOff, "!keys hides the key display and saves it")
    check(G.editing and G.allShown, f"!hud opens the editor and shows every part ({G.missing})")
    kd = G.draggedSaved
    check(G.draggedR[1] == 295 and G.draggedR[2] == 195 and kd.x == 0 and kd.y == 0 and kd.ox == 295 and kd.oy == 195,
          f"dragging moves a part and saves it from the nearest edge ({list(G.draggedR.values())})")
    check(G.snappedX == 800 and G.snapGuide == 960 and G.freeX == 806 and G.nudgedX == 805, f"snapping to the middle, Shift and arrow keys ({G.snappedX}, {G.freeX}, {G.nudgedX})")
    check(abs(G.infoScale - 1.1) < 1e-9 and abs(G.infoSaved - 1.1) < 1e-9 and abs(G.scaledR[3] - 308) < 1e-9 and G.scaledR[2] == 16,
          f"scrolling resizes a part in place ({G.infoScale}, {list(G.scaledR.values())})")
    check(G.hiddenByMenu and G.keysScale == 1.5, "right-click hides a part and sets its size")
    check(G.shownAgain and G.bg == 128, "the toolbar shows hidden parts again and sets the background")
    check(G.resetKeys[1] + G.resetKeys[3] == 1920 - 24 and G.resetAll, "Reset all puts everything back")
    check(G.closedByDone and G.escClosedEditor and G.hudToggles, "Done, Escape and !hud close the editor")
    check(G.fromSettings and G.speedOn, "F1 > Settings opens the editor and turns on the speedometer")
    check(G.brokenReported == 1 and G.brokenBalanced, "a broken part reports once and the rest still draws")
    check(len(G.hudErrors) == 0, f"no HUD part errors ({list(G.hudErrors.values())})")

# The layout is kept after a reload
L.execute('''
SURF.HUD.SetHidden("watchers", true)
SURF.HUD.SetScale("timer", 1.3)
''')
include("cl_hud.lua")
check(G.SURF.HUD.Hidden("watchers") and G.SURF.HUD.Scale("timer") == 1.3 and G.SURF.HUD.byId["mapvote"] is not None,
      "the layout loads from data/surf_hud.json and parts from other files stay")
L.execute('SURF.HUD.Reset()')

# Scoreboard and map vote
ok = run(r"""
other.nw.surf_mainpb = 61.5
other.nw.surf_tag = "gg"
GM:ScoreboardShow()
for _, p in ipairs(created) do if p.Refresh and p.class == "DPanel" then board = p end end
PaintTree(board)
hoverAll = true PaintTree(board) hoverAll = false
allPlayers[#allPlayers + 1] = MakePlayer({ name = "Late", sid = "76561190000000003" })
board:Think()
boardRows = 0
for _, p in ipairs(AllPanels(board)) do if p.class == "DButton" and p.DoRightClick and p.parent and p.parent.class == "Canvas" then boardRows = boardRows + 1 end end
openMenus = {}
for _, p in ipairs(AllPanels(board)) do if not firstRow and p.class == "DButton" and p.DoRightClick and p.parent and p.parent.class == "Canvas" then firstRow = p end end
firstRow:DoRightClick()
sbMenu = openMenus[#openMenus]
sbOptions = {}
for _, o in ipairs(sbMenu:GetChildren()) do if o.text then sbOptions[#sbOptions + 1] = o.text end end
for _, o in ipairs(sbMenu:GetChildren()) do if o.text == "Mute their voice (only for you)" then o:DoClick() end end
GM:ScoreboardHide()
table.remove(allPlayers)
Deliver("surf.MapVote", true, { "surf_a", "surf_b", "__extend" }, { 2, 3 }, { surf_a = 2 }, 130)
GM:HUDPaint()
""", "the scoreboard and map vote draw")
if ok:
    opts = list(G.sbOptions.values())
    check(G.boardRows == 3, f"the scoreboard picks up a player who joins while it's open ({G.boardRows})")
    check("Steam profile" in opts and "Watch them" in opts and "Admin" in opts and G.other.muted, f"right-click a player: profile, watch, mute and admin actions ({opts})")
    check(G.menusClosed, "releasing Tab closes the menu")

# Challenges window, toasts and the race countdown (cl_challenges.lua)
ok = run(r"""
consoleCmds = {}
local d = { streak = 4, bestStreak = 6, streakNext = 50, dayLeft = 5000, weekLeft = 200000, sweep = 100,
	motd = { name = "surf_mesa", tier = 2 },
	list = {
		{ id = "finish3", text = "Finish 3 runs", goal = 3, progress = 1, coins = 60 },
		{ id = "maps2", text = "Finish 2 different maps", goal = 2, progress = 2, done = true, coins = 90 },
		{ id = "play20", text = "Surf for 20 minutes", goal = 20, progress = 7, coins = 60, unit = "min" },
		{ id = "motd", text = "Finish the map of the day: surf_mesa", goal = 1, progress = 0, coins = 150, motd = "surf_mesa" },
		{ id = "wmaps10", text = "Finish 10 different maps", goal = 10, progress = 3, coins = 500, weekly = true },
	},
	ach = {
		{ id = "first", name = "First Wave", desc = "Finish any map", goal = 1, value = 1, coins = 50, date = 1700000000 },
		{ id = "maps25", name = "Explorer", desc = "Finish 25 different maps", goal = 25, value = 5, coins = 300 },
	} }
Deliver("surf.Menu", "challenges", d)
chWin = SURF.UI.Open.challenges
PaintTree(chWin)
hoverAll = true PaintTree(chWin) hoverAll = false
chCards = 0
for _, p in ipairs(AllPanels(chWin)) do if p.OnMousePressed then p:OnMousePressed() chCards = chCards + 1 end end
for _, b in ipairs(FindButtons(chWin, "Achievements")) do b:DoClick() end
PaintTree(chWin)
d.tab = "achievements" d.motd = nil
Deliver("surf.Menu", "challenges", d)
PaintTree(SURF.UI.Open.challenges)
Deliver("surf.Challenge", "toast", { text = "Daily challenge done", col = Color(255, 200, 40) })
hooks.DrawOverlay.surf_ui_toasts()
Deliver("surf.Challenge", "race", { count = 3, vs = "Bob" })
hooks.HUDPaint.surf_race_countdown()
Deliver("surf.Challenge", "race", { go = true, vs = "Bob" })
hooks.HUDPaint.surf_race_countdown()
GM:HUDPaint()
raceShown = SURF.HUD.byId.race.rect ~= nil
Deliver("surf.Challenge", "race", { stop = true })
hooks.HUDPaint.surf_race_countdown()
GM:HUDPaint()
raceGone = SURF.HUD.byId.race.rect == nil
-- F1 > Challenges runs !challenges
Deliver("surf.Menu", "menu", {})
for _, b in ipairs(FindButtons(SURF.UI.Open.hub.side, "Challenges")) do b:DoClick() end
""", "the challenges window builds and paints")
if ok:
    cmds = list(G.consoleCmds.values())
    check(G.chWin is not None and G.chCards >= 1 and "say !nominate surf_mesa" in cmds, "the challenges window opens; the map of the day card nominates it")
    check("say !challenges" in cmds, "F1 > Challenges opens the challenges window")
    check(G.raceShown and G.raceGone, "the Race HUD part shows during a race only")

# Race menu, the record ghost and hiding players while racing (cl_race.lua)
ok = run(r"""
-- Settings that remember what RunConsoleCommand sets, like the real convars
cvars = {}
function CreateClientConVar(name, def)
	cvars[name] = cvars[name] or def
	return { GetBool = function() return tonumber(cvars[name]) ~= 0 end, GetInt = function() return tonumber(cvars[name]) or 0 end }
end
local oldRCC = RunConsoleCommand
function RunConsoleCommand(name, v, ...) if cvars[name] ~= nil and v ~= nil and select("#", ...) == 0 then cvars[name] = v end return oldRCC(name, v, ...) end
util.Compress = function(s) return s end
util.Decompress = function(s) return s end
net.ReadData = function() return table.remove(netIn, 1) end
math.NormalizeAngle = function(a) return (a + 180) % 360 - 180 end
local vm = {}
vm.__index = vm
vm.__add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end
function vm:ToScreen() return { x = self.x, y = self.y, visible = true } end
local plainVector = Vector
function Vector(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, vm) end
drawn = 0
function ClientsideModel() return { SetNoDraw = function() end, LookupSequence = function() return 1 end, ResetSequence = function() end,
	SetPos = function(self, p) self.pos = p ghostAt = p end, SetAngles = function() end, SetCycle = function() end, DrawModel = function() drawn = drawn + 1 end } end
render.SetBlend = function() end
render.SetColorModulation = function() end
RENDERGROUP_TRANSLUCENT = 2
include("cl_race.lua")

consoleCmds = {}
Deliver("surf.Menu", "race", { map = "surf_kitsune", zoned = true, countdown = 3, invite = "Bob", ghost = false,
	wr = { time = 61.5, name = "Bob" },
	players = { { name = "Bob", sid = "76561190000000002" }, { name = "Busy", sid = "76561190000000003", state = "racing" } } })
raceWin = SURF.UI.Open.race
PaintTree(raceWin)
hoverAll = true PaintTree(raceWin) hoverAll = false
for _, b in ipairs(FindButtons(raceWin, "Countdown")) do b:DoClick() end
for _, b in ipairs(FindButtons(raceWin, "Hide other players")) do b:DoClick() end
for _, b in ipairs(FindButtons(raceWin, "Record ghost")) do b:DoClick() end
busyClickable = #FindButtons(raceWin, "Busy") > 0 and FindButtons(raceWin, "Busy")[1].uiRow.onClick ~= nil
for _, b in ipairs(FindButtons(raceWin, "Bob wants")) do b:DoClick() end
Deliver("surf.Menu", "race", { map = "surf_kitsune", zoned = true, players = { { name = "Bob", sid = "76561190000000002" } } })
for _, b in ipairs(FindButtons(SURF.UI.Open.race, "Bob")) do b:DoClick() end
Deliver("surf.Menu", "race", { map = "surf_kitsune", players = {} })
PaintTree(SURF.UI.Open.race)

-- The ghost arrives in two pieces and follows your run
Deliver("surf.Challenge", "race", { ghostOn = true })
local raw = "0,0,0,0;100,0,0,90;200,0,0,90"
Deliver("surf.Ghost", "k1", 2, 2, 0.4, "Bob", 1, #raw - 5, string.sub(raw, 6))
ghostEarly = SURF.RaceClient.Ghost.pts == nil
Deliver("surf.Ghost", "k1", 1, 2, 0.4, "Bob", 1, 5, string.sub(raw, 1, 5))
ghostN = SURF.RaceClient.Ghost.n
me.nw.surf_state = SURF.STATE_RUNNING
me.nw.surf_start = CurTime() - 0.5
hooks.PostDrawTranslucentRenderables.surf_race_ghost(false, false)
ghostX = ghostAt and ghostAt.x
hooks.HUDPaint.surf_race_ghost_name()
cvars.surf_race_hide = "1"
hidesOther = SURF.RaceHides(other)
SURF.RaceClient.rivalSid = other.sid
keepsRival = not SURF.RaceHides(other)
SURF.RaceClient.rivalSid = nil
me.nw.surf_style = "sw"
offOnStyle = SURF.RaceClient.Ghost.Pose() == nil
me.nw.surf_style = nil
me.nw.surf_start = CurTime() - 10
goneAfter = SURF.RaceClient.Ghost.Pose() == nil
Deliver("surf.Ghost", "", 0, 0)
cleared = SURF.RaceClient.Ghost.pts == nil
me.nw.surf_state = nil me.nw.surf_start = nil
Vector = plainVector
""", "the race menu and the record ghost work")
if ok:
    cmds = list(G.consoleCmds.values())
    check(G.cvars.surf_race_countdown == "5" and G.cvars.surf_race_hide == "1", "race settings change the countdown and hiding")
    check("say !race wr on" in cmds and "say !accept" in cmds and "say !race 76561190000000002" in cmds and not G.busyClickable,
          f"the race menu accepts, challenges by SteamID and toggles the ghost ({cmds})")
    check(G.ghostEarly and G.ghostN == 3 and G.cvars.surf_race_ghost == "1", "the ghost is put together from its pieces")
    check(G.drawn >= 1 and G.ghostX is not None and abs(G.ghostX - 50) < 1e-6, f"the ghost is drawn where the record was at that time ({G.ghostX})")
    check(G.hidesOther and G.keepsRival, "hiding players while racing keeps your rival")
    check(G.offOnStyle and G.goneAfter and G.cleared, "the ghost is off on other styles, gone after its finish, and cleared")

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
