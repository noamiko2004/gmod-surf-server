local HIDE = {
	CHudHealth = true, CHudBattery = true, CHudAmmo = true, CHudSecondaryAmmo = true,
	CHudDamageIndicator = true, CHudZoom = true,
}
function GM:HUDShouldDraw(name)
	if HIDE[name] then return false end
	return true
end

local BG = Color(10, 12, 18, 200)
local DIM = Color(170, 180, 195)
local GOLD = Color(255, 200, 40)
local GREEN = Color(80, 255, 120)
local RED = Color(255, 90, 90)

local function ShowKeys()
	local cv = GetConVar("surf_showkeys")
	return not cv or cv:GetBool()
end

local function Box(x, y, w, h)
	draw.RoundedBox(8, x, y, w, h, BG)
end

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

local function Diff(d)
	return string.format("%s%.3f", d < 0 and "-" or "+", math.abs(d)), d < 0 and GREEN or RED
end

-- Checkpoint split popups ---------------------------------------------------

local split
net.Receive("surf.Split", function()
	split = { index = net.ReadUInt(8), time = net.ReadFloat(), until_ = CurTime() + 3 }
	if net.ReadBool() then split.pb = net.ReadFloat() else net.ReadFloat() end
	if net.ReadBool() then split.wr = net.ReadFloat() else net.ReadFloat() end
	surface.PlaySound("buttons/blip2.wav")
end)

local function DrawSplit(cx, y)
	if not split or CurTime() > split.until_ then return end
	local alpha = math.Clamp((split.until_ - CurTime()) * 255, 0, 255)
	local parts = { { "CP " .. split.index .. "  " .. SURF.FormatTime(split.time), color_white } }
	if split.pb then
		local t, c = Diff(split.pb)
		parts[#parts + 1] = { "PB " .. t, c }
	end
	if split.wr then
		local t, c = Diff(split.wr)
		parts[#parts + 1] = { "WR " .. t, c }
	end
	surface.SetFont("SurfLarge")
	local total, widths = 0, {}
	for i, p in ipairs(parts) do
		widths[i] = surface.GetTextSize(p[1])
		total = total + widths[i] + (i > 1 and 24 or 0)
	end
	draw.RoundedBox(8, cx - total / 2 - 14, y - 18, total + 28, 36, Color(10, 12, 18, alpha * 0.8))
	local x = cx - total / 2
	for i, p in ipairs(parts) do
		draw.SimpleText(p[1], "SurfLarge", x, y, ColorAlpha(p[2], alpha), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		x = x + widths[i] + 24
	end
end

-- Speed with a color hint: green while gaining speed, red while losing it ----

local speedState = {}
local function SpeedColor(target, speed)
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

-- Key display ---------------------------------------------------------------

local function Key(label, x, y, w, on)
	draw.RoundedBox(4, x, y, w, 26, on and Color(255, 255, 255, 220) or Color(10, 12, 18, 150))
	draw.SimpleText(label, "SurfSmall", x + w / 2, y + 13, on and Color(10, 12, 18) or DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
end

local function DrawKeys(target, cx, y)
	local k = target:GetNW2Int("surf_keys", 0)
	local function on(b) return bit.band(k, b) ~= 0 end
	Key("W", cx - 13, y, 26, on(IN_FORWARD))
	Key("A", cx - 43, y + 30, 26, on(IN_MOVELEFT))
	Key("S", cx - 13, y + 30, 26, on(IN_BACK))
	Key("D", cx + 17, y + 30, 26, on(IN_MOVERIGHT))
	Key("JUMP", cx - 43, y + 60, 41, on(IN_JUMP))
	Key("DUCK", cx + 2, y + 60, 41, on(IN_DUCK))
end

-- Main HUD ------------------------------------------------------------------

function GM:HUDPaint()
	local me = LocalPlayer()
	if not IsValid(me) then return end
	local target = me
	local obs = me:GetObserverTarget()
	if IsValid(obs) and obs:IsPlayer() then target = obs end
	local isReplay = target:GetNW2Bool("surf_replay", false)

	local sw, sh = ScrW(), ScrH()
	local acc = SURF.Config.Accent

	-- Timer panel (bottom center)
	local w, h = 320, 134
	local x, y = sw / 2 - w / 2, sh - h - 30
	if target:Alive() then
		Box(x, y, w, h)
		local txt, col = TimerText(target)
		draw.SimpleText(txt, "SurfTimer", sw / 2, y + 28, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)

		local speed = math.floor(target:GetVelocity():Length2D())
		draw.SimpleText(speed .. " u/s", "SurfLarge", sw / 2, y + 62, SpeedColor(target, speed), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)

		local info
		if isReplay then
			info = "Replay of " .. target:GetNW2String("surf_replay_name", "?")
		else
			local track = target:GetNW2Int("surf_track", 0)
			local cps = SURF.ClientCPCount(track)
			info = track > 0 and ("Bonus " .. track) or "Main"
			if cps > 0 then info = info .. "  |  CP " .. target:GetNW2Int("surf_cp", 0) .. "/" .. cps end
		end
		draw.SimpleText(info, "SurfSmall", sw / 2, y + 88, acc, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)

		local pb = target:GetNW2Float("surf_pb", 0)
		draw.SimpleText("PB " .. SURF.FormatTime(pb), "SurfSmall", x + 14, y + h - 16, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local wr = target:GetNW2Float("surf_wr", 0)
		draw.SimpleText("WR " .. SURF.FormatTime(wr), "SurfSmall", x + w - 14, y + h - 16, wr > 0 and GOLD or DIM, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end

	DrawSplit(sw / 2, y - 34)

	if target ~= me then
		local label = isReplay and ("Watching the server record replay") or ("Spectating " .. target:Nick())
		draw.SimpleText(label, "SurfLarge", sw / 2, 60, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	elseif me:Team() == TEAM_SPECTATOR then
		draw.SimpleText("Free roam. Click to watch a player, !spec to surf", "SurfMedium", sw / 2, sh - 60, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end

	if ShowKeys() and target:Alive() then
		DrawKeys(target, sw / 2, sh / 2 + 70)
	end

	-- Info panel (top left)
	local left = math.max(0, GetGlobal2Int("surf_mapend") - CurTime())
	Box(16, 16, 280, 104)
	draw.SimpleText(SURF.Config.Name, "SurfLarge", 30, 32, acc, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	draw.SimpleText(game.GetMap(), "SurfMedium", 30, 58, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	local wrName = GetGlobal2String("surf_wr_name", "")
	local info = string.format("%d:%02d left", math.floor(left / 60), math.floor(left % 60))
	if wrName ~= "" then info = info .. "  |  WR by " .. wrName end
	draw.SimpleText(info, "SurfSmall", 30, 80, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	local title = SURF.Config.Titles[me:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
	local pos = me:GetNW2Int("surf_rankpos", 0)
	draw.SimpleText(title.name, "SurfSmall", 30, 100, title.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	draw.SimpleText(me:GetNW2Int("surf_points", 0) .. " pts" .. (pos > 0 and ("  |  #" .. pos) or ""), "SurfSmall", 110, 100, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)

	self:DrawMapVote()
end
