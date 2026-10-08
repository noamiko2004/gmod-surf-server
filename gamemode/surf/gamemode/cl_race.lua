-- The race menu (!race), the record ghost and hiding other players while
-- racing. The server side is sv_race.lua; the countdown and the Race HUD part
-- are in cl_challenges.lua.
local UI = SURF.UI
local C = UI.Col
local S = UI.S
local Menus = SURF.Menus
local RC = SURF.RaceClient or {}
SURF.RaceClient = RC

-- Settings, kept on this computer. The server reads the countdown and the
-- ghost switch (userinfo) when you challenge someone or join.
local cvCountdown = CreateClientConVar("surf_race_countdown", "3", true, true)
local cvGhost = CreateClientConVar("surf_race_ghost", "0", true, true)
local cvHide = CreateClientConVar("surf_race_hide", "0", true, false)
local cvGhostName = CreateClientConVar("surf_race_ghostname", "1", true, false)
local COUNTDOWNS = { 3, 5, 10 }
local GHOST_COL = Color(255, 200, 40)
local RACE_COL = Color(255, 120, 60)

local function Say(text) RunConsoleCommand("say", text) end

-- The record ghost -------------------------------------------------------------------

local Ghost = { parts = {} } -- pts: flat x, y, z, yaw list; n points, step seconds apart
RC.Ghost = Ghost

net.Receive("surf.Ghost", function()
	local key, i, total = net.ReadString(), net.ReadUInt(8), net.ReadUInt(8)
	if total == 0 then
		Ghost.pts, Ghost.key, Ghost.loading = nil, nil, nil
		return
	end
	local time, name, step = net.ReadFloat(), net.ReadString(), net.ReadFloat()
	local data = net.ReadData(net.ReadUInt(32))
	if Ghost.loading ~= key then Ghost.loading, Ghost.parts = key, {} end
	Ghost.parts[i] = data
	for j = 1, total do
		if not Ghost.parts[j] then return end
	end
	local raw = util.Decompress(table.concat(Ghost.parts)) or ""
	local pts, n = {}, 0
	for x, y, z, yaw in string.gmatch(raw, "([%-%d%.]+),([%-%d%.]+),([%-%d%.]+),([%-%d%.]+)") do
		local b = n * 4
		pts[b + 1], pts[b + 2], pts[b + 3], pts[b + 4] = tonumber(x), tonumber(y), tonumber(z), tonumber(yaw)
		n = n + 1
	end
	Ghost.parts, Ghost.loading = {}, nil
	if n < 2 then return end
	Ghost.pts, Ghost.n, Ghost.step, Ghost.time, Ghost.name, Ghost.key = pts, n, math.max(step, 0.001), time, name, key
end)

-- Where the ghost is now: it starts when your run on the main track (Normal
-- style) starts, waits in the start zone with you, and stays at the end for a
-- moment after finishing.
function Ghost.Pose()
	local me = LocalPlayer()
	if not Ghost.pts or not cvGhost:GetBool() or not IsValid(me) then return end
	if me:GetNW2Int("surf_track", 0) ~= 0 or SURF.StyleOf(me).id ~= "n" then return end
	local state = me:GetNW2Int("surf_state", 0)
	local t = 0
	if state == SURF.STATE_RUNNING then
		t = CurTime() - me:GetNW2Float("surf_start", CurTime())
	elseif state ~= SURF.STATE_START then
		return
	end
	local fi = t / Ghost.step
	if fi > Ghost.n - 1 + 2 / Ghost.step then return end -- gone two seconds after its finish
	fi = math.Clamp(fi, 0, Ghost.n - 1)
	local i = math.floor(fi)
	local j = math.min(i + 1, Ghost.n - 1)
	local frac = fi - i
	local p, a, b = Ghost.pts, i * 4, j * 4
	local pos = Vector(Lerp(frac, p[a + 1], p[b + 1]), Lerp(frac, p[a + 2], p[b + 2]), Lerp(frac, p[a + 3], p[b + 3]))
	local yaw = p[a + 4] + math.NormalizeAngle(p[b + 4] - p[a + 4]) * frac
	return pos, yaw, t >= Ghost.time
end

local model
hook.Add("PostDrawTranslucentRenderables", "surf_race_ghost", function(depth, sky)
	if depth or sky then return end
	local pos, yaw = Ghost.Pose()
	if not pos then return end
	if not IsValid(model) then
		model = ClientsideModel("models/player/kleiner.mdl", RENDERGROUP_TRANSLUCENT)
		if not IsValid(model) then return end
		model:SetNoDraw(true)
		local seq = model:LookupSequence("run_all_01")
		if seq and seq >= 0 then model:ResetSequence(seq) end
	end
	model:SetPos(pos)
	model:SetAngles(Angle(0, yaw, 0))
	model:SetCycle(RealTime() * 1.1 % 1)
	render.SetBlend(0.45)
	render.SetColorModulation(GHOST_COL.r / 255, GHOST_COL.g / 255, GHOST_COL.b / 255)
	model:DrawModel()
	render.SetColorModulation(1, 1, 1)
	render.SetBlend(1)
end)

hook.Add("HUDPaint", "surf_race_ghost_name", function()
	if not cvGhostName:GetBool() then return end
	local pos, _, done = Ghost.Pose()
	if not pos then return end
	local sp = (pos + Vector(0, 0, 82)):ToScreen()
	if not sp.visible then return end
	local text = done and ("Record: " .. SURF.FormatTime(Ghost.time)) or ("Record ghost: " .. tostring(Ghost.name))
	draw.SimpleTextOutlined(text, "SurfUI_Small", sp.x, sp.y, GHOST_COL, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER, 1, Color(0, 0, 0, 180))
end)

-- Hiding other players while racing -----------------------------------------------------

-- True for players to hide right now: everyone but you, your rival and who
-- you watch, while you race a player or run with the ghost
function SURF.RaceHides(ply)
	if not cvHide:GetBool() then return false end
	local me = LocalPlayer()
	if not IsValid(me) or ply == me or ply == me:GetObserverTarget() then return false end
	if RC.rivalSid then return ply:SteamID64() ~= RC.rivalSid end
	return Ghost.Pose() ~= nil and me:GetNW2Int("surf_state", 0) == SURF.STATE_RUNNING
end

hook.Add("PrePlayerDraw", "surf_race_hide", function(ply)
	if SURF.RaceHides(ply) then return true end
end)

-- The menu --------------------------------------------------------------------------------

local function Switch(on)
	return function(_, w, h)
		local sw, sh = S(40), S(22)
		local x, y = w - sw - S(14), h / 2 - sh / 2
		local acc = UI.Accent()
		draw.RoundedBox(sh / 2, x, y, sw, sh, on() and Color(acc.r, acc.g, acc.b, 220) or Color(255, 255, 255, 30))
		local k = sh - S(6)
		draw.RoundedBox(k / 2, on() and (x + sw - k - S(3)) or (x + S(3)), y + S(3), k, k, color_white)
	end
end

local function Toggle(parent, title, sub, cv, name)
	return UI.Row(parent, { title = title, sub = sub, paint = Switch(function() return cv:GetBool() end), onClick = function()
		RunConsoleCommand(name, cv:GetBool() and "0" or "1")
	end })
end

local function Open(d)
	local f = UI.Frame("Race", 620, 640, { id = "race", sub = d.map or game.GetMap() })
	local scroll = UI.Scroll(f)

	if d.invite then
		UI.Section(scroll, "Waiting for you")
		UI.Row(scroll, { title = d.invite .. " wants to race you", sub = "Click to accept, right-click to turn it down", right = "Accept",
			rightColor = C.green, titleColor = RACE_COL, onClick = function() f:Close() Say("!accept") end,
			onRightClick = function() f:Close() Say("!decline") end })
	end
	if d.vs then
		UI.Section(scroll, "Your race")
		UI.Row(scroll, { title = "Racing " .. d.vs, sub = "First to the end wins", right = "Give up", rightColor = C.red,
			onClick = function() f:Close() Say("!forfeit") end })
	end

	UI.Section(scroll, "Challenge a player")
	local any = false
	for _, p in ipairs(d.players or {}) do
		any = true
		local busy = p.state ~= nil
		UI.Row(scroll, { title = p.name, sub = busy and ("Can't race now: " .. p.state) or "First to the end of the map wins",
			right = busy and "" or "Race", rightColor = RACE_COL, titleColor = busy and C.faint or nil,
			onClick = (not busy and d.zoned and not d.vs) and function()
				f:Close()
				Say("!race " .. p.sid)
			end or nil })
	end
	if not any then UI.Empty(scroll, "Nobody else is on right now. Race the record instead!") end

	UI.Section(scroll, "Race the server record")
	if d.wr then
		UI.Row(scroll, { title = "Record ghost: " .. d.wr.name .. " (" .. SURF.FormatTime(d.wr.time) .. ")",
			sub = "A gold ghost of the record run starts with each of your runs (Normal style)", titleColor = GHOST_COL,
			paint = Switch(function() return d.ghost == true end), onClick = function()
				d.ghost = not d.ghost
				Say("!race wr " .. (d.ghost and "on" or "off"))
			end })
	else
		UI.Row(scroll, { title = "No record replay on this map yet", sub = "Set the record and others will race your ghost", titleColor = C.faint })
	end

	UI.Section(scroll, "Settings")
	local function CountdownNow()
		local n = cvCountdown:GetInt()
		return table.HasValue(COUNTDOWNS, n) and n or 3
	end
	UI.Row(scroll, { title = "Countdown", sub = "How long the start is held when you challenge someone. Click to change",
		right = function() return CountdownNow() .. " seconds" end, onClick = function()
			local cur, nextN = CountdownNow(), COUNTDOWNS[1]
			for i, n in ipairs(COUNTDOWNS) do
				if n == cur then nextN = COUNTDOWNS[i % #COUNTDOWNS + 1] end
			end
			RunConsoleCommand("surf_race_countdown", tostring(nextN))
		end })
	Toggle(scroll, "Hide other players while racing", "Only your rival (or the ghost) stays visible", cvHide, "surf_race_hide")
	Toggle(scroll, "Show the ghost's name", "A label over the record ghost", cvGhostName, "surf_race_ghostname")
end

Menus.race = Open
