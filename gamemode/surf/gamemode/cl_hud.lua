-- The HUD: timer, keys, map info and the rest. Each one is a part players can
-- move, resize or hide with !hud (or F1 > Settings > Edit HUD layout). The
-- layout is saved on the player's own computer, in data/surf_hud.json.
--
-- Other client files (included after this one) add parts the same way:
--
--   SURF.HUD.Add("coins", {
--       name = "Coins",                       -- its name in the editor
--       w = 150, h = 40,                      -- or size = function(ctx) return w, h end
--       pos = { 1, 0, -16, 140 },             -- where it starts out, see below
--       show = function(ctx) return true end, -- optional: when to draw it
--       draw = function(w, h, ctx)            -- draw inside 0..w, 0..h
--           SURF.HUD.Box(w, h)                -- the HUD's background
--           draw.SimpleText("1,200 coins", "SurfMedium", w / 2, h / 2, color_white,
--               TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
--       end,
--   })
--
-- pos is { ax, ay, ox, oy }: ax and ay pick what it hangs from (0 the left or
-- top edge, 0.5 the middle, 1 the right or bottom edge) and ox, oy move it
-- from there in pixels. hidden = true adds a part that stays off until a
-- player turns it on in the editor.
-- ctx: me, target (who you're watching, or you), replay, alive, speed,
-- speedColor, and preview (true while the editor is open: draw sample
-- content, so the part can be placed even when it would be empty).

local HIDE = {
	CHudHealth = true, CHudBattery = true, CHudAmmo = true, CHudSecondaryAmmo = true,
	CHudDamageIndicator = true, CHudZoom = true,
}
function GM:HUDShouldDraw(name)
	if HIDE[name] then return false end
	return true
end

SURF.HUD = SURF.HUD or {}
local HUD = SURF.HUD
HUD.list = HUD.list or {} -- parts, in drawing order
HUD.byId = HUD.byId or {}

local DIM = Color(170, 180, 195)
local GOLD = Color(255, 200, 40)
local GREEN = Color(80, 255, 120)
local RED = Color(255, 90, 90)
HUD.Colors = { dim = DIM, gold = GOLD, green = GREEN, red = RED }
-- Map tier badge colors, easy (green) to hard (red/purple)
local TIER_COLORS = {
	Color(80, 230, 120), Color(160, 230, 80), Color(240, 210, 60), Color(255, 150, 50),
	Color(255, 80, 80), Color(220, 70, 200), Color(170, 90, 255), Color(140, 140, 255),
}

local MARGIN = 16
local FILE = "surf_hud.json"
local MIN_SCALE, MAX_SCALE = 0.5, 2

-- Saved layout ----------------------------------------------------------------
-- { bg = background alpha, el = { [id] = { x, y, ox, oy (position), s (size), hide } } }

local layout = { bg = 200, el = {} }

local function Write()
	timer.Remove("surf_hud_save")
	file.Write(FILE, util.TableToJSON(layout))
end
-- For changes that come in bursts (the mouse wheel, arrow keys)
local function WriteSoon()
	timer.Create("surf_hud_save", 0.5, 1, Write)
end

local function Load()
	local raw = file.Read(FILE, "DATA")
	local t = raw and util.JSONToTable(raw)
	if not istable(t) then return false end
	layout.bg = math.Clamp(tonumber(t.bg) or 200, 0, 255)
	layout.el = istable(t.el) and t.el or {}
	return true
end

-- The key display used to have its own setting (!keys); carry it over once
local oldKeys = CreateClientConVar("surf_showkeys", "1", true, false)
if not Load() and not oldKeys:GetBool() then layout.el.keys = { hide = true } end

local function Entry(id)
	layout.el[id] = layout.el[id] or {}
	return layout.el[id]
end

function HUD.Hidden(id)
	local el, c = HUD.byId[id], layout.el[id]
	if c and c.hide ~= nil then return c.hide == true end
	return el ~= nil and el.hidden == true
end

function HUD.SetHidden(id, hide)
	Entry(id).hide = hide and true or false
	Write()
end

-- Shows or hides a part; returns true if it's showing now
function HUD.Toggle(id)
	HUD.SetHidden(id, not HUD.Hidden(id))
	return not HUD.Hidden(id)
end

function HUD.Scale(id)
	local c = layout.el[id]
	return math.Clamp(tonumber(c and c.s) or 1, MIN_SCALE, MAX_SCALE)
end

function HUD.SetScale(id, s, soon)
	s = math.Clamp(math.Round(s, 2), MIN_SCALE, MAX_SCALE)
	Entry(id).s = s ~= 1 and s or nil
	if soon then WriteSoon() else Write() end
end

-- Back to where it started; no id resets every part
function HUD.Reset(id)
	if id then
		layout.el[id] = nil
	else
		layout.el = {}
		layout.bg = 200
	end
	Write()
end

function HUD.Background() return layout.bg end
function HUD.SetBackground(a)
	layout.bg = math.Clamp(math.Round(a), 0, 255)
	Write()
end

-- The rounded background every part uses (its see-through amount is a setting)
local boxCol = Color(10, 12, 18, 200)
function HUD.Box(w, h, radius)
	if layout.bg <= 0 then return end
	boxCol.a = layout.bg
	draw.RoundedBox(radius or 8, 0, 0, w, h, boxCol)
end

function HUD.Add(id, def)
	def.id = id
	def.name = def.name or id
	def.pos = def.pos or { 0.5, 0.5, 0, 0 }
	if HUD.byId[id] then
		-- Same part again (the file was reloaded): replace it in place
		for i, el in ipairs(HUD.list) do
			if el.id == id then HUD.list[i] = def end
		end
	else
		HUD.list[#HUD.list + 1] = def
	end
	HUD.byId[id] = def
	return def
end

-- Drawing ---------------------------------------------------------------------

local function Size(el, ctx)
	if el.size then return el.size(ctx) end
	return el.w or 100, el.h or 40
end

-- Screen spot and size of a part
local function Place(el, ctx)
	local w, h = Size(el, ctx)
	local c = layout.el[el.id] or {}
	local p = el.pos
	local ax, ay = tonumber(c.x) or p[1], tonumber(c.y) or p[2]
	local ox, oy = tonumber(c.ox) or p[3] or 0, tonumber(c.oy) or p[4] or 0
	local s = HUD.Scale(el.id)
	local sw, sh = ScrW(), ScrH()
	local ew, eh = w * s, h * s
	local x = math.Clamp(ax * (sw - ew) + ox, 0, math.max(0, sw - ew))
	local y = math.Clamp(ay * (sh - eh) + oy, 0, math.max(0, sh - eh))
	return math.Round(x), math.Round(y), w, h, s
end

local function Paint(el, ctx)
	if not ctx.preview and el.show and not el.show(ctx) then return end
	local x, y, w, h, s = Place(el, ctx)
	el.rect = { x, y, w * s, h * s }
	local m = Matrix()
	m:Translate(Vector(x, y, 0))
	if s ~= 1 then m:Scale(Vector(s, s, 1)) end
	cam.PushModelMatrix(m, true)
	if s ~= 1 then
		render.PushFilterMag(TEXFILTER.ANISOTROPIC)
		render.PushFilterMin(TEXFILTER.ANISOTROPIC)
	end
	local ok, err = pcall(el.draw, w, h, ctx)
	if s ~= 1 then
		render.PopFilterMin()
		render.PopFilterMag()
	end
	cam.PopModelMatrix()
	if not ok then error(err, 0) end
end

local ctx = {}
function GM:HUDPaint()
	local me = LocalPlayer()
	if not IsValid(me) then return end
	local target = me
	local obs = me:GetObserverTarget()
	if IsValid(obs) and obs:IsPlayer() then target = obs end
	ctx.me, ctx.target = me, target
	ctx.replay = target:GetNW2Bool("surf_replay", false)
	ctx.alive = target:Alive()
	ctx.preview = HUD.Editing()
	ctx.speed = math.floor(target:GetVelocity():Length2D())
	ctx.speedColor = HUD.SpeedColor(target, ctx.speed)

	for _, el in ipairs(HUD.list) do
		el.rect = nil
		local hidden = HUD.Hidden(el.id)
		if ctx.preview or not hidden then
			-- Hidden parts show faded in the editor, so they can be turned back on
			if hidden then surface.SetAlphaMultiplier(0.3) end
			local ok, err = pcall(Paint, el, ctx)
			if hidden then surface.SetAlphaMultiplier(1) end
			if not ok and not el.failed then
				-- Once, so one broken part doesn't flood the console or stop the rest
				el.failed = true
				ErrorNoHalt("[HUD] " .. el.id .. ": " .. tostring(err) .. "\n")
			end
		end
	end
end

-- Speed with a color hint: green while gaining speed, red while losing it
local speedState = {}
function HUD.SpeedColor(target, speed)
	local st = speedState[target]
	if not st then
		st = { last = speed, at = CurTime(), col = Color(255, 255, 255) }
		speedState[target] = st
	end
	if CurTime() - st.at > 0.1 then
		local d = speed - st.last
		st.goal = d > 3 and GREEN or (d < -3 and RED or color_white)
		st.last, st.at = speed, CurTime()
	end
	local goal = st.goal or color_white
	local f = math.min(1, FrameTime() * 8)
	st.col.r = Lerp(f, st.col.r, goal.r)
	st.col.g = Lerp(f, st.col.g, goal.g)
	st.col.b = Lerp(f, st.col.b, goal.b)
	return st.col
end

-- Timer -------------------------------------------------------------------------

local function TimerText(target)
	local state = target:GetNW2Int("surf_state", SURF.STATE_IDLE)
	if state == SURF.STATE_NOZONES then return "No zones yet", DIM end
	if state == SURF.STATE_START then return "In start zone", GREEN end
	if state == SURF.STATE_RUNNING then
		return SURF.FormatTime(CurTime() - target:GetNW2Float("surf_start")), color_white
	end
	if state == SURF.STATE_FINISHED then return SURF.FormatTime(target:GetNW2Float("surf_final")), GOLD end
	return "Press !r to start", DIM
end

local function RunInfo(target, replay)
	if replay then return "Replay of " .. target:GetNW2String("surf_replay_name", "?") end
	if target:GetNW2Int("surf_state", 0) == SURF.STATE_FINISHED then
		-- Strafe stats of the run that just ended
		local sync = target:GetNW2Float("surf_fin_sync", -1)
		return "Jumps " .. target:GetNW2Int("surf_fin_jumps", 0) .. "  Strafes " .. target:GetNW2Int("surf_fin_strafes", 0)
			.. (sync >= 0 and string.format("  Sync %.1f%%", sync) or "") .. "  Max " .. math.floor(target:GetNW2Float("surf_fin_max", 0))
	end
	local track = target:GetNW2Int("surf_track", 0)
	local cps = SURF.ClientCPCount(track)
	local info = track > 0 and ("Bonus " .. track) or "Main"
	local style = SURF.StyleOf(target)
	if style.id ~= "n" then info = info .. "  |  " .. style.name end
	if cps > 0 then info = info .. "  |  CP " .. target:GetNW2Int("surf_cp", 0) .. "/" .. cps end
	return info
end

HUD.Add("timer", {
	name = "Timer",
	w = 320, h = 134,
	pos = { 0.5, 1, 0, -30 },
	show = function(c) return c.alive end,
	draw = function(w, h, c)
		local t = c.target
		HUD.Box(w, h)
		local txt, col = TimerText(t)
		draw.SimpleText(txt, "SurfTimer", w / 2, 28, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		draw.SimpleText(c.speed .. " u/s", "SurfLarge", w / 2, 62, c.speedColor, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		draw.SimpleText(RunInfo(t, c.replay), "SurfSmall", w / 2, 88, SURF.Config.Accent, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		local pb = t:GetNW2Float("surf_pb", 0)
		draw.SimpleText("PB " .. SURF.FormatTime(pb), "SurfSmall", 14, h - 16, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local wr = t:GetNW2Float("surf_wr", 0)
		draw.SimpleText("WR " .. SURF.FormatTime(wr), "SurfSmall", w - 14, h - 16, wr > 0 and GOLD or DIM, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end,
})

-- Checkpoint splits -------------------------------------------------------------

local split
net.Receive("surf.Split", function()
	split = { index = net.ReadUInt(8), time = net.ReadFloat(), until_ = CurTime() + 3 }
	if net.ReadBool() then split.pb = net.ReadFloat() else net.ReadFloat() end
	if net.ReadBool() then split.wr = net.ReadFloat() else net.ReadFloat() end
	surface.PlaySound("buttons/blip2.wav")
end)

local SAMPLE_SPLIT = { index = 3, time = 42.123, pb = -0.214, wr = 0.532 }

local function Diff(d)
	return string.format("%s%.3f", d < 0 and "-" or "+", math.abs(d)), d < 0 and GREEN or RED
end

local function SplitParts(c)
	local sp = (split and CurTime() <= split.until_) and split or (c.preview and SAMPLE_SPLIT)
	if not sp then return end
	local parts = { { "CP " .. sp.index .. "  " .. SURF.FormatTime(sp.time), color_white } }
	if sp.pb then
		local t, col = Diff(sp.pb)
		parts[#parts + 1] = { "PB " .. t, col }
	end
	if sp.wr then
		local t, col = Diff(sp.wr)
		parts[#parts + 1] = { "WR " .. t, col }
	end
	surface.SetFont("SurfLarge")
	local total = 0
	for i, p in ipairs(parts) do
		p.w = surface.GetTextSize(p[1])
		total = total + p.w + (i > 1 and 24 or 0)
	end
	return parts, total, sp == split and math.Clamp((split.until_ - CurTime()) * 255, 0, 255) or 255
end

HUD.Add("split", {
	name = "Checkpoint splits",
	size = function(c)
		local _, total = SplitParts(c)
		return (total or 200) + 28, 36
	end,
	pos = { 0.5, 1, 0, -180 },
	show = function() return split ~= nil and CurTime() <= split.until_ end,
	draw = function(w, h, c)
		local parts, _, alpha = SplitParts(c)
		if not parts then return end
		draw.RoundedBox(8, 0, 0, w, h, Color(10, 12, 18, alpha * math.max(layout.bg, 160) / 255))
		local x = 14
		for _, p in ipairs(parts) do
			draw.SimpleText(p[1], "SurfLarge", x, h / 2, ColorAlpha(p[2], alpha), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			x = x + p.w + 24
		end
	end,
})

-- Keys ------------------------------------------------------------------------------

local keyOn, keyText = Color(255, 255, 255, 220), Color(10, 12, 18)
local keyOff = Color(10, 12, 18, 150)
local function Key(label, x, y, w, on)
	draw.RoundedBox(4, x, y, w, 26, on and keyOn or keyOff)
	if label then draw.SimpleText(label, "SurfSmall", x + w / 2, y + 13, on and keyText or DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER) end
end

-- A small triangle made of 1px strips, its tip 3px from the middle; dir -1
-- points left, 1 right
local function Arrow(cx, cy, dir, col)
	surface.SetDrawColor(col)
	for i = 0, 5 do
		surface.DrawRect(cx + (3 - i) * dir, cy - i, 1, i * 2 + 1)
	end
end

-- Which way the watched player is turning their mouse: -1 left, 1 right
local turn = { dir = 0, at = 0 }
local function TurnDir(target)
	local yaw = target:EyeAngles().y
	if turn.ent ~= target or not turn.yaw then turn.ent, turn.yaw, turn.dir = target, yaw, 0 end
	local d = math.AngleDifference(yaw, turn.yaw)
	turn.yaw = yaw
	if d > 0.05 then
		turn.dir, turn.at = -1, RealTime()
	elseif d < -0.05 then
		turn.dir, turn.at = 1, RealTime()
	elseif RealTime() - turn.at > 0.06 then
		turn.dir = 0
	end
	return turn.dir
end

HUD.Add("keys", {
	name = "Key display",
	w = 86, h = 86,
	pos = { 1, 1, -24, -24 },
	show = function(c) return c.alive end,
	draw = function(w, h, c)
		keyOff.a = math.max(layout.bg * 0.75, 60)
		local k = c.target:GetNW2Int("surf_keys", 0)
		local function on(b) return bit.band(k, b) ~= 0 end
		local dir = TurnDir(c.target)
		-- Mouse turning on both sides of W
		Key(nil, 0, 0, 26, dir == -1)
		Arrow(13, 13, -1, dir == -1 and keyText or DIM)
		Key("W", 30, 0, 26, on(IN_FORWARD))
		Key(nil, 60, 0, 26, dir == 1)
		Arrow(73, 13, 1, dir == 1 and keyText or DIM)
		Key("A", 0, 30, 26, on(IN_MOVELEFT))
		Key("S", 30, 30, 26, on(IN_BACK))
		Key("D", 60, 30, 26, on(IN_MOVERIGHT))
		Key("JUMP", 0, 60, 41, on(IN_JUMP))
		Key("DUCK", 45, 60, 41, on(IN_DUCK))
	end,
})

-- Map info --------------------------------------------------------------------

HUD.Add("info", {
	name = "Map info",
	size = function()
		surface.SetFont("SurfMedium")
		local mapW = surface.GetTextSize(game.GetMap())
		return math.max(280, mapW + (GetGlobal2Int("surf_tier", 0) > 0 and 90 or 40)), 104
	end,
	pos = { 0, 0, 16, 16 },
	draw = function(w, h, c)
		local me = c.me
		local acc = SURF.Config.Accent
		HUD.Box(w, h)
		draw.SimpleText(GetGlobal2String("surf_brand", SURF.Config.Name), "SurfLarge", 14, 16, acc, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(game.GetMap(), "SurfMedium", 14, 42, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local tier = GetGlobal2Int("surf_tier", 0)
		if tier > 0 then
			surface.SetFont("SurfMedium")
			local mapW = surface.GetTextSize(game.GetMap())
			local tcol = TIER_COLORS[math.min(tier, #TIER_COLORS)]
			draw.RoundedBox(4, 20 + mapW, 33, 30, 18, ColorAlpha(tcol, 60))
			draw.SimpleText("T" .. tier, "SurfSmall", 35 + mapW, 42, tcol, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		local left = math.max(0, GetGlobal2Int("surf_mapend") - CurTime())
		local wrName = GetGlobal2String("surf_wr_name", "")
		local info = string.format("%d:%02d left", math.floor(left / 60), math.floor(left % 60))
		if wrName ~= "" then info = info .. "  |  WR by " .. wrName end
		draw.SimpleText(info, "SurfSmall", 14, 64, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local title = SURF.Config.Titles[me:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
		local pos = me:GetNW2Int("surf_rankpos", 0)
		draw.SimpleText(title.name, "SurfSmall", 14, 84, title.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		surface.SetFont("SurfSmall")
		local tw = surface.GetTextSize(title.name)
		draw.SimpleText(me:GetNW2Int("surf_points", 0) .. " pts" .. (pos > 0 and ("  |  #" .. pos) or ""), "SurfSmall",
			math.max(94, 26 + tw), 84, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end,
})

-- Spectating ------------------------------------------------------------------------

local function SpecText(c)
	if c.target ~= c.me then
		return c.replay and "Watching the server record replay" or ("Spectating " .. c.target:Nick())
	end
	if c.me:Team() == TEAM_SPECTATOR then return "Free roam. Click to watch a player, !spec to surf" end
	if c.preview then return "Spectating someone" end
end

HUD.Add("spec", {
	name = "Spectating",
	size = function(c)
		surface.SetFont("SurfLarge")
		return surface.GetTextSize(SpecText(c) or "") + 36, 40
	end,
	pos = { 0.5, 0, 0, 40 },
	show = function(c) return SpecText(c) ~= nil end,
	draw = function(w, h, c)
		HUD.Box(w, h)
		draw.SimpleText(SpecText(c) or "", "SurfLarge", w / 2, h / 2, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end,
})

-- Who is watching (sv_spectate.lua keeps the count and up to 8 names on the
-- watched player) ---------------------------------------------------------------

local MAX_WATCHERS = 6
local SAMPLE_WATCHERS = { "Bob", "Alice" }
local function Watchers(c)
	local s = c.target:GetNW2String("surf_watchers", "")
	if s == "" then
		if c.preview then return SAMPLE_WATCHERS, 2 end
		return
	end
	local names = string.Explode("\n", s)
	local n = tonumber(table.remove(names, 1)) or #names
	return names, n
end

HUD.Add("watchers", {
	name = "Spectators",
	size = function(c)
		local names, n = Watchers(c)
		names, n = names or {}, n or 0
		surface.SetFont("SurfSmall")
		local w = 150
		local shown = math.min(#names, MAX_WATCHERS)
		for i = 1, shown do w = math.max(w, surface.GetTextSize(names[i]) + 28) end
		return math.min(w, 260), 34 + (shown + (n > shown and 1 or 0)) * 19
	end,
	pos = { 1, 0, -16, 16 },
	show = function(c) return Watchers(c) ~= nil end,
	draw = function(w, h, c)
		local names, n = Watchers(c)
		if not names then return end
		HUD.Box(w, h)
		draw.SimpleText("Spectators (" .. n .. ")", "SurfSmall", 14, 17, SURF.Config.Accent, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local shown = math.min(#names, MAX_WATCHERS)
		for i = 1, shown do
			draw.SimpleText(names[i], "SurfSmall", 14, 17 + i * 19, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		if n > shown then
			draw.SimpleText("+" .. (n - shown) .. " more", "SurfSmall", 14, 17 + (shown + 1) * 19, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
	end,
})

-- A big speedometer under the crosshair (off until turned on) --------------------

local shadow = Color(0, 0, 0, 170)
HUD.Add("speed", {
	name = "Speedometer",
	w = 200, h = 56,
	pos = { 0.5, 0.5, 0, 140 },
	hidden = true,
	show = function(c) return c.alive end,
	draw = function(w, h, c)
		draw.SimpleTextOutlined(tostring(c.speed), "SurfTimer", w / 2, 22, c.speedColor, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER, 1, shadow)
		draw.SimpleTextOutlined("u/s", "SurfSmall", w / 2, 47, DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER, 1, shadow)
	end,
})

-- The player you look at: name, title, points, rank and best time here (on at
-- first; off with !hud or F1 > Settings) --------------------------------------------

local LOOK_RANGE, LOOK_HOLD = 6000, 0.6
local look = { at = -10 }
local SAMPLE_LOOK = { sample = true }

local function LookTrace(c)
	local hide = GetConVar("surf_hideplayers")
	if hide and hide:GetBool() then return end
	local start = EyePos()
	local tr = util.TraceLine({ start = start, endpos = start + EyeVector() * LOOK_RANGE, filter = { c.me, c.target }, mask = MASK_SHOT })
	local e = tr.Entity
	if IsValid(e) and e:IsPlayer() and e:Alive() then return e end
end

-- Kept for a moment after you look away, so it fades instead of flickering
local function Looked(c)
	if IsValid(look.ply) and RealTime() - look.at < LOOK_HOLD then return look.ply end
	if c.preview then return SAMPLE_LOOK end
end

-- Three lines: { text, font, color }
local function LookLines(p)
	if p.sample then
		return { { "Bob  [VIP]", "SurfMedium", Color(255, 220, 120) }, { "Skilled  |  420 pts  |  #3", "SurfSmall", Color(120, 140, 255) },
			{ "Best here 1:02.345", "SurfSmall", DIM } }
	end
	if p:GetNW2Bool("surf_replay", false) then
		local t = p:GetNW2Float("surf_mainpb", 0)
		return { { "Server record replay", "SurfMedium", GOLD }, { "by " .. p:GetNW2String("surf_replay_name", "?"), "SurfSmall", color_white },
			{ t > 0 and SURF.FormatTime(t) or "", "SurfSmall", DIM } }
	end
	local vip = SURF.IsVIP(p)
	local nc = SURF.NameColorOf(p)
	local name = p:Nick() .. (p:IsSuperAdmin() and "  [OWNER]" or (p:IsAdmin() and "  [ADMIN]" or (vip and "  [VIP]" or "")))
	local title = SURF.Config.Titles[p:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
	local pos = p:GetNW2Int("surf_rankpos", 0)
	local rank = title.name .. "  |  " .. string.Comma(p:GetNW2Int("surf_points", 0)) .. " pts" .. (pos > 0 and ("  |  #" .. pos) or "")
	local pb = p:GetNW2Float("surf_mainpb", 0)
	local best = pb > 0 and ("Best here " .. SURF.FormatTime(pb)) or "No time on this map yet"
	local style = SURF.StyleOf(p)
	if style.id ~= "n" then best = best .. "  |  " .. style.name end
	return { { name, "SurfMedium", nc and SURF.ItemColor(nc) or (vip and Color(255, 220, 120) or color_white) },
		{ rank, "SurfSmall", title.color }, { best, "SurfSmall", DIM } }
end

HUD.Add("lookat", {
	name = "Player you look at",
	size = function(c)
		local p = Looked(c)
		local w = 200
		for _, l in ipairs(p and LookLines(p) or {}) do
			surface.SetFont(l[2])
			w = math.max(w, surface.GetTextSize(l[1]) + 32)
		end
		return w, 70
	end,
	pos = { 0.5, 0.5, 0, 60 },
	show = function(c)
		local p = LookTrace(c)
		if p then look.ply, look.at = p, RealTime() end
		return Looked(c) ~= nil
	end,
	draw = function(w, h, c)
		local p = Looked(c)
		if not p then return end
		local fade = p.sample and 1 or math.Clamp((LOOK_HOLD - (RealTime() - look.at)) / 0.25, 0, 1)
		local base = surface.GetAlphaMultiplier()
		surface.SetAlphaMultiplier(base * fade)
		HUD.Box(w, h)
		for i, l in ipairs(LookLines(p)) do
			draw.SimpleText(l[1], l[2], w / 2, ({ 18, 40, 56 })[i], l[3], TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		surface.SetAlphaMultiplier(base)
	end,
})

-- Editor ------------------------------------------------------------------------------
-- A see-through layer over the screen: drag parts to move them, scroll on one
-- to resize it, right-click for hide / size / reset. Arrow keys nudge.

local editor
function HUD.Editing() return IsValid(editor) end

local SIZES = { 0.6, 0.75, 0.9, 1, 1.15, 1.3, 1.5, 1.75, 2 }
local SNAP = 10

-- The part under the mouse (the one drawn last, so on top)
local function PartAt(mx, my)
	for i = #HUD.list, 1, -1 do
		local r = HUD.list[i].rect
		if r and mx >= r[1] and mx <= r[1] + r[3] and my >= r[2] and my <= r[2] + r[4] then return HUD.list[i] end
	end
end

-- A part's spot is kept relative to the nearest screen edge (or the middle), so
-- it stays in the same place on other screen sizes
local function Anchor(pos, size, screen)
	local center = pos + size / 2
	local a = center < screen / 3 and 0 or (center > screen * 2 / 3 and 1 or 0.5)
	return a, math.Round(pos - a * (screen - size))
end

local function Store(el, x, y)
	local r = el.rect
	local c = Entry(el.id)
	c.x, c.ox = Anchor(x, r[3], ScrW())
	c.y, c.oy = Anchor(y, r[4], ScrH())
	r[1], r[2] = x, y
end

-- Pulls a left (axis 1) or top (axis 2) edge onto the screen margins and middle,
-- or else onto the edges and middles of the other parts. Returns the edge and
-- the guide line to draw.
local function Snap(v, size, screen, others, axis)
	local best, line, dist = v, nil, SNAP + 1
	local function try(c, l)
		local d = math.abs(v - c)
		if d < dist then best, line, dist = c, l, d end
	end
	try(MARGIN, MARGIN)
	try(screen / 2 - size / 2, screen / 2)
	try(screen - size - MARGIN, screen - MARGIN)
	-- The screen comes first, so a part near the middle doesn't hop between
	-- the edges of other centered parts
	if not line then
		for _, r in ipairs(others) do
			local a, len = r[axis], r[axis + 2]
			try(a, a)
			try(a + len - size, a + len)
			try(a + len / 2 - size / 2, a + len / 2)
		end
	end
	return math.Round(best), line
end

local function PartMenu(el)
	local UI = SURF.UI
	local m = UI.Menu()
	local hidden = HUD.Hidden(el.id)
	m:AddOption(hidden and "Show" or "Hide", function() HUD.SetHidden(el.id, not hidden) end):SetIcon("icon16/eye.png")
	local sub = m:AddSubMenu("Size")
	local now = HUD.Scale(el.id)
	for _, s in ipairs(SIZES) do
		sub:AddOption(math.Round(s * 100) .. "%" .. (math.abs(now - s) < 0.01 and "  (now)" or ""), function() HUD.SetScale(el.id, s) end)
	end
	m:AddOption("Reset", function() HUD.Reset(el.id) end):SetIcon("icon16/arrow_undo.png")
	UI.OpenMenu(m)
end

local function BackgroundMenu()
	local m = SURF.UI.Menu()
	for _, pct in ipairs({ 0, 25, 50, 65, 80, 90, 100 }) do
		m:AddOption(pct == 0 and "No background" or (pct .. "%"), function() HUD.SetBackground(pct * 255 / 100) end)
	end
	SURF.UI.OpenMenu(m)
end

local function HiddenMenu()
	local m = SURF.UI.Menu()
	local any = false
	for _, el in ipairs(HUD.list) do
		if HUD.Hidden(el.id) then
			any = true
			m:AddOption("Show " .. el.name, function() HUD.SetHidden(el.id, false) end):SetIcon("icon16/eye.png")
		end
	end
	if not any then m:AddOption("Nothing is hidden", function() end) end
	SURF.UI.OpenMenu(m)
end

local function HiddenCount()
	local n = 0
	for _, el in ipairs(HUD.list) do
		if HUD.Hidden(el.id) then n = n + 1 end
	end
	return n
end

local function PaintEditor(s, w, h)
	local UI = SURF.UI
	local C, S = UI.Col, UI.S
	local acc = UI.Accent()
	-- Faint middle lines
	surface.SetDrawColor(255, 255, 255, 14)
	surface.DrawRect(w / 2, 0, 1, h)
	surface.DrawRect(0, h / 2, w, 1)
	local hover = s.drag and s.drag.el or PartAt(gui.MouseX(), gui.MouseY())
	for _, el in ipairs(HUD.list) do
		local r = el.rect
		if r then
			local hidden = HUD.Hidden(el.id)
			local active = el == hover or el == s.selected
			if active then
				surface.SetDrawColor(acc.r, acc.g, acc.b, 24)
				surface.DrawRect(r[1], r[2], r[3], r[4])
			end
			surface.SetDrawColor(active and acc or Color(255, 255, 255, hidden and 40 or 90))
			surface.DrawOutlinedRect(r[1] - 1, r[2] - 1, r[3] + 2, r[4] + 2)
			local label = el.name
			local sc = HUD.Scale(el.id)
			if sc ~= 1 then label = label .. "  " .. math.Round(sc * 100) .. "%" end
			if hidden then label = label .. "  (hidden)" end
			local ty = r[2] > S(20) and r[2] - S(10) or r[2] + r[4] + S(10)
			draw.SimpleText(label, "SurfUI_Tiny", r[1], ty, active and acc or (hidden and C.faint or C.text), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
	end
	-- Snap guides while dragging
	local g = s.guides
	if g then
		surface.SetDrawColor(acc.r, acc.g, acc.b, 160)
		if g[1] then surface.DrawRect(g[1], 0, 1, h) end
		if g[2] then surface.DrawRect(0, g[2], w, 1) end
	end
end

function HUD.Edit()
	if IsValid(editor) then
		if IsValid(editor.bar) then editor.bar:Close() else editor:Remove() end
		return
	end
	local UI = SURF.UI
	local S = UI.S
	UI.Close("hub")
	CloseDermaMenus()

	local ov = vgui.Create("DPanel")
	editor = ov
	ov:SetPos(0, 0)
	ov:SetSize(ScrW(), ScrH())
	ov:MakePopup()
	ov:SetCursor("sizeall")
	ov.Paint = PaintEditor

	ov.OnMousePressed = function(s, code)
		local mx, my = gui.MouseX(), gui.MouseY()
		local el = PartAt(mx, my)
		s.selected = el
		s:RequestFocus()
		if not el then return end
		if code == MOUSE_LEFT then
			s.drag = { el = el, dx = mx - el.rect[1], dy = my - el.rect[2] }
			s:MouseCapture(true)
		elseif code == MOUSE_RIGHT then
			PartMenu(el)
		end
	end
	ov.OnMouseReleased = function(s, code)
		if code ~= MOUSE_LEFT or not s.drag then return end
		s:MouseCapture(false)
		s.drag, s.guides = nil, nil
		Write()
	end
	ov.Think = function(s)
		local d = s.drag
		if not d or not d.el.rect then return end
		local r = d.el.rect
		local sw, sh = ScrW(), ScrH()
		local x = math.Clamp(gui.MouseX() - d.dx, 0, sw - r[3])
		local y = math.Clamp(gui.MouseY() - d.dy, 0, sh - r[4])
		local gx, gy
		if not input.IsKeyDown(KEY_LSHIFT) then
			local others = {}
			for _, o in ipairs(HUD.list) do
				if o ~= d.el and o.rect then others[#others + 1] = o.rect end
			end
			x, gx = Snap(x, r[3], sw, others, 1)
			y, gy = Snap(y, r[4], sh, others, 2)
		end
		s.guides = { gx, gy }
		Store(d.el, x, y)
	end
	ov.OnMouseWheeled = function(_, delta)
		local el = PartAt(gui.MouseX(), gui.MouseY())
		if not el then return end
		HUD.SetScale(el.id, HUD.Scale(el.id) + delta * 0.05, true)
		return true
	end
	ov.OnKeyCodePressed = function(s, key)
		local el = s.selected
		if not el or not el.rect then return end
		local step = input.IsKeyDown(KEY_LSHIFT) and 10 or 1
		local dx = key == KEY_LEFT and -step or (key == KEY_RIGHT and step or 0)
		local dy = key == KEY_UP and -step or (key == KEY_DOWN and step or 0)
		if dx == 0 and dy == 0 then return end
		local r = el.rect
		Store(el, math.Clamp(r[1] + dx, 0, ScrW() - r[3]), math.Clamp(r[2] + dy, 0, ScrH() - r[4]))
		WriteSoon()
	end

	-- The toolbar: a normal window on the layer (drag it by its title if it's in the way)
	local bar = UI.Frame("Edit HUD", 620, 176, { id = "hud_edit", sub = "Only you see this layout", noPopup = true })
	bar:SetParent(ov)
	bar:SetPos(math.Round(ScrW() / 2 - bar:GetWide() / 2), math.Round(ScrH() * 0.3))
	ov.bar = bar
	UI.Label(bar, "Drag a part to move it. Scroll on a part to resize it, right-click it to hide or reset it. "
		.. "Arrow keys nudge the part you clicked. Hold Shift to stop snapping.", "SurfUI_Small", UI.Col.dim, true):Dock(TOP)
	local btns = UI.ButtonBar(bar, BOTTOM)
	btns:AddButton("Done", "primary", function() bar:Close() end, RIGHT)
	btns:AddButton("Reset all", "danger", function()
		UI.Confirm("Reset the HUD?", "Every part goes back to where it started, at its normal size.", "Reset", function() HUD.Reset() end, true)
	end, RIGHT)
	btns:AddButton(function() return "Background " .. math.Round(layout.bg * 100 / 255) .. "%" end, "ghost", BackgroundMenu, LEFT):SetWide(S(160))
	btns:AddButton(function() return "Hidden (" .. HiddenCount() .. ")" end, "ghost", HiddenMenu, LEFT):SetWide(S(110))
	bar.OnClose = function()
		Write()
		if IsValid(ov) then ov:Remove() end
	end
	ov.OnRemove = function()
		if editor == ov then editor = nil end
	end
end
