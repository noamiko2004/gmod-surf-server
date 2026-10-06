-- The Challenges window (!challenges, !achievements, or F1 > Challenges):
-- today's challenges, the weekly ones, the map of the day, your streak and
-- every achievement with its progress. Also the race countdown and the
-- challenge toasts (net message surf.Challenge, sv_challenges.lua).
local UI = SURF.UI
local C = UI.Col
local S = UI.S
local Menus = SURF.Menus

local TIER_COLORS = { Color(90, 210, 120), Color(150, 220, 90), Color(240, 210, 70), Color(255, 150, 60), Color(240, 80, 80), Color(200, 100, 255) }

surface.CreateFont("SurfRaceCount", { font = "Roboto", size = S(110), weight = 800, antialias = true })
hook.Add("OnScreenSizeChanged", "surf_race_font", function()
	-- after cl_ui.lua has the new scale
	timer.Simple(0, function() surface.CreateFont("SurfRaceCount", { font = "Roboto", size = S(110), weight = 800, antialias = true }) end)
end)

local function Countdown(sec)
	sec = math.max(0, math.floor(sec or 0))
	local h = math.floor(sec / 3600)
	if h >= 24 then return math.floor(h / 24) .. "d " .. (h % 24) .. "h" end
	return h .. "h " .. math.floor(sec % 3600 / 60) .. "m"
end

local function Date(ts)
	return ts and ts > 0 and os.date("%d %b %Y", ts) or ""
end

-- A card with a title, a line under it, a progress bar and the reward on the right
local function Progress(parent, o)
	local p = parent:Add("DPanel")
	p:Dock(TOP)
	p:DockMargin(0, 0, 0, S(6))
	p:SetTall(S(62))
	p.Paint = function(_, w, h)
		local done = o.done
		local acc = UI.Accent()
		draw.RoundedBox(6, 0, 0, w, h, done and Color(C.gold.r, C.gold.g, C.gold.b, 18) or C.card)
		if o.highlight then draw.RoundedBox(2, 0, S(8), S(3), h - S(16), o.highlight) end
		local right = done and (o.doneText or "Done") or ("+" .. string.Comma(o.coins) .. " coins")
		local rcol = done and C.green or C.gold
		draw.SimpleText(right, "SurfUI_Body", w - S(14), S(18), rcol, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		local room = w - S(28) - UI.TextWidth(right, "SurfUI_Body") - S(16)
		draw.SimpleText(UI.Fit(o.title, "SurfUI_Body", room), "SurfUI_Body", S(14), S(18), done and C.gold or C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		if o.sub and o.sub ~= "" then
			draw.SimpleText(UI.Fit(o.sub, "SurfUI_Small", room), "SurfUI_Small", S(14), S(37), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		-- Bar along the bottom with the count on its right
		local goal = math.max(1, o.goal or 1)
		local frac = math.Clamp((o.value or 0) / goal, 0, 1)
		local count = o.countText or (string.Comma(math.floor(o.value or 0)) .. " / " .. string.Comma(goal) .. (o.unit and (" " .. o.unit) or ""))
		local cw = UI.TextWidth(count, "SurfUI_Small") + S(12)
		local bx, by, bw, bh = S(14), h - S(14), w - S(28) - cw, S(6)
		draw.RoundedBox(bh / 2, bx, by, bw, bh, Color(255, 255, 255, 14))
		if frac > 0 then draw.RoundedBox(bh / 2, bx, by, math.max(bh, bw * frac), bh, done and C.green or acc) end
		draw.SimpleText(count, "SurfUI_Small", w - S(14), by + bh / 2, C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
	return p
end

-- A card with a label, a big value and a small line
local function Info(parent, label, value, sub, col)
	local c = vgui.Create("DPanel", parent)
	c.Paint = function(_, w, h)
		draw.RoundedBox(8, 0, 0, w, h, C.card)
		draw.SimpleText(string.upper(label), "SurfUI_Tiny", S(14), S(18), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(UI.Fit(value, "SurfUI_Head", w - S(28)), "SurfUI_Head", S(14), S(44), col or C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(UI.Fit(sub or "", "SurfUI_Small", w - S(28)), "SurfUI_Small", S(14), h - S(18), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	return c
end

local BUILD = {}

function BUILD.today(parent, d)
	local g = UI.Grid(parent, 3, 92)
	local m = d.motd
	if m then
		local card = Info(g, "Map of the day", m.name, m.here and "You're on it! Finish it today" or "Always in the map vote. Click to nominate",
			TIER_COLORS[math.Clamp(m.tier or 0, 1, #TIER_COLORS)])
		if not m.here then
			card:SetCursor("hand")
			card.OnMousePressed = function()
				UI.Click()
				RunConsoleCommand("say", "!nominate " .. m.name)
			end
		end
	else
		Info(g, "Map of the day", "None yet", "Needs a map with zones")
	end
	local streak = d.streak or 0
	Info(g, "Streak", streak .. (streak == 1 and " day" or " days"), "Tomorrow: +" .. (d.streakNext or 0) .. " coins (best " .. (d.bestStreak or 0) .. ")",
		streak >= 2 and C.gold or C.text)
	Info(g, "New challenges in", Countdown(d.dayLeft), "Weekly ones in " .. Countdown(d.weekLeft))

	local scroll = UI.Scroll(parent)
	UI.Section(scroll, "Today")
	local dailyDone, dailyCount = 0, 0
	for _, c in ipairs(d.list or {}) do
		if not c.weekly then
			Progress(scroll, { title = c.text, coins = c.coins, goal = c.goal, value = c.progress, done = c.done, unit = c.unit,
				highlight = c.motd and C.gold or nil, sub = c.motd and "Map of the day, doesn't count for the sweep" or nil })
			if not c.motd then
				dailyCount = dailyCount + 1
				if c.done then dailyDone = dailyDone + 1 end
			end
		end
	end
	Progress(scroll, { title = "Daily sweep", sub = "Do all " .. dailyCount .. " daily challenges above", coins = d.sweep or 0,
		goal = math.max(1, dailyCount), value = dailyDone, done = d.swept, doneText = "Swept!" })
	UI.Section(scroll, "This week")
	for _, c in ipairs(d.list or {}) do
		if c.weekly then
			Progress(scroll, { title = c.text, coins = c.coins, goal = c.goal, value = c.progress, done = c.done, unit = c.unit })
		end
	end
	local note = UI.Label(scroll, "Everyone gets the same challenges. Days start at midnight UTC, weeks on Monday. Rewards are coins for !shop.",
		"SurfUI_Small", C.faint, true)
	note:Dock(TOP)
	note:DockMargin(S(2), S(8), 0, 0)
end

function BUILD.achievements(parent, d)
	local list = d.ach or {}
	local got, total = 0, 0
	for _, a in ipairs(list) do
		if a.date then got = got + 1 end
		total = total + 1
	end
	local bar = vgui.Create("DPanel", parent)
	bar:Dock(TOP)
	bar:SetTall(S(26))
	bar:DockMargin(0, 0, 0, S(8))
	bar.Paint = function(_, w, h)
		draw.SimpleText(got .. " of " .. total .. " unlocked", "SurfUI_Body", 0, h / 2, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText("Each one pays coins once", "SurfUI_Small", w, h / 2, C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
	local scroll = UI.Scroll(parent)
	-- Unlocked last, the closest ones first
	table.sort(list, function(a, b)
		if (a.date ~= nil) ~= (b.date ~= nil) then return b.date ~= nil end
		local fa, fb = a.value / math.max(1, a.goal), b.value / math.max(1, b.goal)
		if fa ~= fb then return fa > fb end
		return a.coins < b.coins
	end)
	for _, a in ipairs(list) do
		Progress(scroll, { title = a.name, sub = a.desc .. (a.date and (" · unlocked " .. Date(a.date)) or ""), coins = a.coins, goal = a.goal,
			value = a.value, done = a.date ~= nil, doneText = "Unlocked" })
	end
end

local win
local function Open(d)
	local tab = BUILD[d.tab or ""] and d.tab or "today"
	win = UI.Frame("Challenges", 760, 620, { id = "challenges", sub = "Daily, weekly and achievements",
		right = function() return string.Comma(LocalPlayer():GetNW2Int("surf_coins", 0)) .. " coins", C.gold end })
	local body
	local tabs = UI.Tabs(win, { { id = "today", name = "Challenges" }, { id = "achievements", name = "Achievements" } }, tab, function(id)
		body:Clear()
		BUILD[id](body, d)
	end)
	tabs:Dock(TOP)
	body = vgui.Create("DPanel", win)
	body:Dock(FILL)
	body.Paint = nil
	BUILD[tab](body, d)
end

Menus.challenges = Open

-- Toasts and the race countdown ---------------------------------------------------

local race -- the countdown: { vs, goAt, untilAt }
local racing -- the race after the go: { vs, since }

net.Receive("surf.Challenge", function()
	local kind, d = net.ReadString(), net.ReadTable()
	if kind == "toast" then
		UI.Toast(d.text or "", d.col and Color(d.col.r, d.col.g, d.col.b) or nil)
	elseif kind == "race" then
		if d.stop then
			race, racing = nil, nil
		elseif d.count then
			race = { vs = d.vs, goAt = RealTime() + d.count, untilAt = RealTime() + d.count + 1.2 }
			surface.PlaySound("buttons/blip1.wav")
		elseif d.go then
			race = { vs = d.vs, goAt = RealTime(), untilAt = RealTime() + 1.2 }
			racing = { vs = d.vs, since = RealTime() }
			surface.PlaySound("buttons/button9.wav")
			UI.Toast("Racing " .. tostring(d.vs) .. ": first to the end wins! (!forfeit gives up)", Color(255, 120, 60))
		end
	end
end)

local lastBeep
hook.Add("HUDPaint", "surf_race_countdown", function()
	if not race then return end
	local now = RealTime()
	if now > race.untilAt then
		race = nil
		return
	end
	local left = race.goAt - now
	local text, col = "GO!", Color(70, 210, 120)
	if left > 0 then
		local n = math.ceil(left)
		text, col = tostring(n), color_white
		if lastBeep ~= n then
			lastBeep = n
			if n < 3 then surface.PlaySound("buttons/blip1.wav") end
		end
	end
	local x, y = ScrW() / 2, ScrH() * 0.32
	draw.SimpleTextOutlined(text, "SurfRaceCount", x, y, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER, 3, Color(0, 0, 0, 200))
	draw.SimpleTextOutlined("Race vs " .. tostring(race.vs or "?"), "SurfUI_Head", x, y + S(76), color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER, 1, Color(0, 0, 0, 200))
end)

-- A movable HUD part (!hud) while a race is on: who against and for how long
if SURF.HUD and SURF.HUD.Add then
	SURF.HUD.Add("race", {
		name = "Race", w = 220, h = 50, pos = { 0.5, 0, 0, 120 },
		show = function(ctx) return racing ~= nil or ctx.preview end,
		draw = function(w, h, ctx)
			SURF.HUD.Box(w, h)
			local vs = racing and racing.vs or "Bob"
			local t = racing and (RealTime() - racing.since) or 42
			draw.SimpleText("Race vs " .. tostring(vs), "SurfSmall", w / 2, h * 0.32, Color(255, 120, 60), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			draw.SimpleText(SURF.FormatTime(t) .. "   !forfeit gives up", "SurfSmall", w / 2, h * 0.7, SURF.HUD.Colors.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end,
	})
end
