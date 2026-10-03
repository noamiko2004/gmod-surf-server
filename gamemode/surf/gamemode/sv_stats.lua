-- Strafe stats of the current run: jumps, strafes, sync, average and top
-- speed. Shown when the run ends and stored with the personal best.
--   strafes: how often the strafe key changed in the air (A/D, or W/S on
--            Sideways)
--   sync:    share of air ticks where the mouse turned the same way as the
--            strafe key (A while turning left, D while turning right). Only
--            measured when A or D is used, so Sideways and W-Only have none.
SURF.Stats = {}
local S = SURF.Stats

function S.Start(ply)
	ply.SurfStats = { jumps = 0, strafes = 0, dir = 0, good = 0, turns = 0, ticks = 0, speedSum = 0, max = 0 }
end

-- Ends the run's stats and returns a summary (nil if none were recording)
function S.Stop(ply)
	local s = ply.SurfStats
	ply.SurfStats = nil
	if not s then return nil end
	return {
		jumps = s.jumps, strafes = s.strafes,
		sync = s.turns > 0 and math.Round(s.good / s.turns * 100, 2) or nil,
		avg = s.ticks > 0 and math.Round(s.speedSum / s.ticks, 1) or 0,
		max = math.Round(s.max, 1),
	}
end

function S.Describe(st)
	local parts = { "Jumps " .. st.jumps, "Strafes " .. st.strafes }
	if st.sync then parts[#parts + 1] = string.format("Sync %.1f%%", st.sync) end
	parts[#parts + 1] = "Avg " .. math.floor(st.avg) .. " u/s"
	parts[#parts + 1] = "Max " .. math.floor(st.max) .. " u/s"
	return table.concat(parts, "  |  ")
end

hook.Add("SetupMove", "surf_stats", function(ply, mv)
	local s = ply.SurfStats
	if not s then return end
	local speed = mv:GetVelocity():Length2D()
	s.ticks = s.ticks + 1
	s.speedSum = s.speedSum + speed
	if speed > s.max then s.max = speed end

	local yaw = mv:GetAngles().y
	local lastYaw = s.yaw
	s.yaw = yaw
	if ply:GetMoveType() ~= MOVETYPE_WALK or ply:WaterLevel() >= 2 then return end

	if ply:OnGround() then
		-- Autohop jumps while jump is held; otherwise it needs a fresh press
		if mv:KeyDown(IN_JUMP) and (mv:KeyPressed(IN_JUMP) or ply:GetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop)) then
			s.jumps = s.jumps + 1
		end
		return
	end

	local side, fwd = mv:GetSideSpeed(), mv:GetForwardSpeed()
	local dir = side > 0 and 1 or (side < 0 and -1 or 0)
	if dir == 0 then dir = fwd > 0 and 2 or (fwd < 0 and -2 or 0) end
	if dir ~= 0 and dir ~= s.dir then
		s.strafes = s.strafes + 1
		s.dir = dir
	end

	if lastYaw and side ~= 0 then
		local turn = math.NormalizeAngle(yaw - lastYaw)
		if turn ~= 0 then
			s.turns = s.turns + 1
			-- Yaw goes up when turning left; A is a negative side move
			if (turn > 0 and side < 0) or (turn < 0 and side > 0) then s.good = s.good + 1 end
		end
	end
end)
