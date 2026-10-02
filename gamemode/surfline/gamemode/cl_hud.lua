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

local function Box(x, y, w, h)
	draw.RoundedBox(8, x, y, w, h, BG)
end

local function TimerText(target)
	local state = target:GetNW2Int("surf_state", SURF.STATE_IDLE)
	if state == SURF.STATE_NOZONES then return "No zones yet", DIM end
	if state == SURF.STATE_START then return "In start zone", Color(0, 255, 120) end
	if state == SURF.STATE_RUNNING then
		return SURF.FormatTime(CurTime() - target:GetNW2Float("surf_start")), color_white
	end
	if state == SURF.STATE_FINISHED then return SURF.FormatTime(target:GetNW2Float("surf_final")), GOLD end
	return "Press !r to start", DIM
end

function GM:HUDPaint()
	local me = LocalPlayer()
	if not IsValid(me) then return end
	local target = me
	local obs = me:GetObserverTarget()
	if IsValid(obs) and obs:IsPlayer() then target = obs end

	local sw, sh = ScrW(), ScrH()
	local acc = SURF.Config.Accent

	-- Timer panel (bottom center)
	local w, h = 300, 112
	local x, y = sw / 2 - w / 2, sh - h - 30
	if target:Alive() then
		Box(x, y, w, h)
		local txt, col = TimerText(target)
		draw.SimpleText(txt, "SurfTimer", sw / 2, y + 30, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		local speed = math.floor(target:GetVelocity():Length2D())
		draw.SimpleText(speed .. " u/s", "SurfLarge", sw / 2, y + 66, acc, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		local pb = target:GetNW2Float("surf_pb", 0)
		draw.SimpleText("PB " .. SURF.FormatTime(pb), "SurfSmall", x + 14, y + h - 16, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local wr = GetGlobal2Float("surf_wr", 0)
		draw.SimpleText("WR " .. SURF.FormatTime(wr), "SurfSmall", x + w - 14, y + h - 16, wr > 0 and GOLD or DIM, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end

	if target ~= me then
		draw.SimpleText("Spectating " .. target:Nick(), "SurfLarge", sw / 2, y - 22, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	elseif me:Team() == TEAM_SPECTATOR then
		draw.SimpleText("Free roam. Click to watch a player, !spec to surf", "SurfMedium", sw / 2, sh - 60, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end

	-- Info panel (top left)
	local left = math.max(0, GetGlobal2Int("surf_mapend") - CurTime())
	Box(16, 16, 260, 82)
	draw.SimpleText(SURF.Config.Name, "SurfLarge", 30, 32, acc, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	draw.SimpleText(game.GetMap(), "SurfMedium", 30, 58, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	local wrName = GetGlobal2String("surf_wr_name", "")
	local info = string.format("%d:%02d left", math.floor(left / 60), math.floor(left % 60))
	if wrName ~= "" then info = info .. "  |  WR by " .. wrName end
	draw.SimpleText(info, "SurfSmall", 30, 80, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)

	self:DrawMapVote()
end
