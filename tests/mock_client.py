"""Smoke test for the client menus (cl_ui.lua, cl_menus.lua, cl_admin.lua)
against a permissive mock of Derma. (The shop has tests/client_smoke.py.)

Panels accept any method call, so this can't prove the Derma calls are right;
it runs every menu's building, layout, painting and click code to catch Lua
errors (nil values, typos, bad arithmetic) without the game.
Run: python3 tests/mock_client.py
"""
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
function Vector(x, y, z) return { x = x or 0, y = y or 0, z = z or 0 } end
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
gui = { MouseX = function() return 0 end, MouseY = function() return 0 end, OpenURL = function(u) openedURL = u end }
input = { IsKeyDown = function() return false end }
chatLines = {}
chat = { AddText = function(...) chatLines[#chatLines + 1] = { ... } end, GetChatBoxPos = function() return 0, 0 end,
         GetChatBoxSize = function() return 400, 200 end }
consoleCmds = {}
function RunConsoleCommand(...) consoleCmds[#consoleCmds + 1] = table.concat({ ... }, " ") end
function CreateClientConVar(name, def) return { GetBool = function() return def == "1" end, GetInt = function() return tonumber(def) end } end
function GetHostName() return "Test Server" end
function GetGlobal2String(k, d) return d end
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
function PM:TimeConnected() return 300 end
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
	"SetMultiline", "SetEditable", "SetBackgroundColor", "SetTextStyleColor", "SetHeight" }) do
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
	local label = p.uiText or (p.uiRow and p.uiRow.title) or p.text or ""
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
include("shared.lua")
for f in ["cl_ui.lua", "cl_menus.lua"] + [f for f in ("cl_admin.lua",) if os.path.exists(os.path.join(GM, f))]:
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
SURF.Visuals = { Presets = { { id = "off", name = "Off", help = "x" } }, Current = function() return nil end, ZonesOn = function() return true end,
	ToggleZones = function() end, MapLightOn = function() return false end, ToggleMapLight = function() end, SetPreset = function() end }
Deliver("surf.Menu", "graphics", {})
for _, f in ipairs(created) do if f.class == "DFrame" then PaintTree(f) end end
''', "server menus open and paint")
if ok:
    check(True, "records, top players, help, maps, styles and graphics menus open")

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
