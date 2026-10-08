-- Ramp fix. Source's movement code sometimes stops a player dead on a surf
-- ramp ("rampbug"): where two brushes of a ramp meet, or when dropping onto
-- one, the collision trace comes back stuck and the engine zeroes the
-- velocity, so you hang on the ramp or slide off from a standstill.
--
-- After each move this checks for that: the player lost most of their speed
-- in one tick while sliding on a ramp (a surface steeper than walkable
-- ground), and the speed the engine should have kept by sliding along it is
-- much higher. Then it gives that speed back. Walls, floors, landings and
-- map teleports are left alone.
--
-- Shared, so client prediction does the same and there's no rubber banding.

local RAMP_MIN, RAMP_MAX = 0.05, 0.7 -- normal.z of a surf ramp (0.7+ is ground)
local MIN_SPEED = 250                -- slower than this nothing is fixed
local KEEP = 0.5                     -- the engine kept less than this share
local MAX_STREAK = 4                 -- ticks in a row before giving up (really stuck)

local function Hull(ply)
	if ply:Crouching() then return ply:GetHullDuck() end
	return ply:GetHull()
end

local function Trace(ply, from, to)
	local mins, maxs = Hull(ply)
	return util.TraceHull({
		start = from, endpos = to, mins = mins, maxs = maxs,
		mask = MASK_PLAYERSOLID, filter = ply, collisiongroup = COLLISION_GROUP_PLAYER_MOVEMENT,
	})
end

local function IsRamp(tr)
	return tr.Hit and not tr.StartSolid and tr.HitNormal.z > RAMP_MIN and tr.HitNormal.z < RAMP_MAX
end

-- The surface the player was moving into this tick: along the old velocity,
-- then just below. A wall or floor in the way means the stop was real.
local function FindRamp(ply, org, vel, dist)
	local dir = vel:GetNormalized()
	for _, start in ipairs({ org, org + Vector(0, 0, 1) }) do
		local tr = Trace(ply, start, start + dir * dist)
		if IsRamp(tr) then return tr.HitNormal end
		if tr.Hit and not tr.StartSolid then return nil end
	end
	local tr = Trace(ply, org, org - Vector(0, 0, 2))
	if IsRamp(tr) then return tr.HitNormal end
end

hook.Add("SetupMove", "surf_rampfix", function(ply, mv)
	ply.SurfRampVel = mv:GetVelocity()
	ply.SurfRampOrg = mv:GetOrigin()
end)

hook.Add("FinishMove", "surf_rampfix", function(ply, mv)
	local pre, from = ply.SurfRampVel, ply.SurfRampOrg
	ply.SurfRampVel = nil
	if not pre or ply:GetMoveType() ~= MOVETYPE_WALK or ply:WaterLevel() >= 2 or ply:OnGround() then return end
	local speed = pre:Length()
	local post = mv:GetVelocity()
	if speed < MIN_SPEED or post:Length() >= speed * KEEP then
		ply.SurfRampStreak = 0
		return
	end
	if (ply.SurfRampStreak or 0) >= MAX_STREAK then return end

	local org = mv:GetOrigin()
	local dist = speed * engine.TickInterval()
	-- Moved much further than the speed allows: a map teleport, not a ramp
	if org:Distance(from) > dist * 1.5 + 32 then return end

	local n = FindRamp(ply, org, pre, dist + 2)
	if not n then return end
	-- What sliding along the ramp keeps of the old velocity
	local slide = pre - n * pre:Dot(n)
	if slide:Length() < MIN_SPEED or post:Length() >= slide:Length() * KEEP then return end

	ply.SurfRampStreak = (ply.SurfRampStreak or 0) + 1
	mv:SetVelocity(slide)
	-- Off the surface a hair so the next trace doesn't start stuck in it
	local off = org + n * 0.25
	if not Trace(ply, off, off).StartSolid then mv:SetOrigin(off) end
end)
