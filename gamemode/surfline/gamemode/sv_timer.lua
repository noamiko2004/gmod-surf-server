-- Server-authoritative run timer. State is networked through NW2 vars so
-- spectators see the timer of whoever they watch.
SURF.Timer = {}
local T = SURF.Timer

local function SetState(ply, state)
	ply:SetNW2Int("surf_state", state)
end

function T.Reset(ply)
	ply.SurfInStart = false
	ply:SetNW2Float("surf_start", 0)
	SetState(ply, SURF.Zones.HasTimer() and SURF.STATE_IDLE or SURF.STATE_NOZONES)
end

function T.Stop(ply, reason)
	if ply:GetNW2Int("surf_state") == SURF.STATE_RUNNING then
		SetState(ply, SURF.STATE_IDLE)
		if reason then
			SURF.Chat(ply, SURF.Config.Accent, "[Timer] ", color_white, "Timer stopped (" .. reason .. ").")
		end
	end
end

local function CapSpeed(ply)
	local cap = SURF.Config.StartSpeedCap
	local vel = ply:GetVelocity()
	local speed2d = vel:Length2D()
	if speed2d > cap then
		local scale = cap / speed2d
		ply:SetLocalVelocity(Vector(vel.x * scale, vel.y * scale, vel.z))
	end
end

function T.OnZoneEnter(ply, ztype)
	if not ply:Alive() or ply:Team() == TEAM_SPECTATOR then return end
	if not SURF.Zones.HasTimer() then return end
	if ztype == "start" then
		ply.SurfInStart = true
		ply:SetNW2Float("surf_start", 0)
		SetState(ply, SURF.STATE_START)
	elseif ztype == "end" and ply:GetNW2Int("surf_state") == SURF.STATE_RUNNING then
		if ply:GetMoveType() == MOVETYPE_NOCLIP then
			T.Stop(ply, "noclip")
			return
		end
		T.Finish(ply, CurTime() - ply:GetNW2Float("surf_start"))
	end
end

function T.OnZoneLeave(ply, ztype)
	if ztype ~= "start" or not ply.SurfInStart then return end
	ply.SurfInStart = false
	if not ply:Alive() or ply:GetMoveType() == MOVETYPE_NOCLIP then return end
	CapSpeed(ply)
	ply:SetNW2Float("surf_start", CurTime())
	SetState(ply, SURF.STATE_RUNNING)
end

function T.Finish(ply, time)
	ply:SetNW2Float("surf_final", time)
	SetState(ply, SURF.STATE_FINISHED)

	local res = SURF.DB.SubmitTime(ply, time)
	local acc, white = SURF.Config.Accent, color_white
	local gold = Color(255, 200, 40)

	local diff = ""
	if res.oldPB then
		local d = time - res.oldPB
		diff = string.format(" (PB %s%.3f)", d < 0 and "-" or "+", math.abs(d))
	end

	if res.wr then
		local wrdiff = res.oldWR > 0 and string.format(" (-%.3f)", res.oldWR - time) or ""
		SURF.Chat(nil, gold, "[NEW SERVER RECORD] ", team.GetColor(ply:Team()), ply:Nick(), white,
			" set the record on ", acc, game.GetMap(), white, " with ", gold, SURF.FormatTime(time), white, wrdiff .. "!")
		for _, p in ipairs(player.GetHumans()) do p:SendLua([[surface.PlaySound("garrysmod/save_load4.wav")]]) end
		hook.Run("SurfNewRecord", ply, time, res)
	elseif res.improved then
		SURF.Chat(nil, acc, "[Timer] ", team.GetColor(ply:Team()), ply:Nick(), white, " finished in ", acc, SURF.FormatTime(time),
			white, diff .. " and is now rank ", acc, res.rank .. "/" .. res.total, white, ".")
		ply:SendLua([[surface.PlaySound("buttons/blip1.wav")]])
	else
		SURF.Chat(ply, acc, "[Timer] ", white, "You finished in ", acc, SURF.FormatTime(time), white, diff .. ".")
	end
	hook.Run("SurfFinish", ply, time, res)
end

function T.GoToStart(ply)
	if ply:Team() == TEAM_SPECTATOR then
		SURF.Spec.Toggle(ply)
		return
	end
	if not ply:Alive() then ply:Spawn() end
	local pos = SURF.Zones.StartPos()
	if not pos then
		ply:Spawn()
		return
	end
	ply:SetPos(pos)
	ply:SetLocalVelocity(vector_origin)
	T.Reset(ply)
	-- Already inside the start trigger, so StartTouch may not fire again
	if SURF.Zones.HasTimer() then
		ply.SurfInStart = true
		SetState(ply, SURF.STATE_START)
	end
end
