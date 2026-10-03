-- Server-authoritative run timer with checkpoint splits and bonus tracks.
-- State is networked through NW2 vars so spectators see the timer of
-- whoever they watch.
SURF.Timer = {}
local T = SURF.Timer

util.AddNetworkString("surf.Split")

local function SetState(ply, state)
	ply:SetNW2Int("surf_state", state)
end

local function TrackName(track)
	return track > 0 and ("Bonus " .. track) or "the map"
end

-- " (Sideways)" for styles other than Normal
local function StyleSuffix(style)
	local st = SURF.StyleByID[style or "n"]
	return (st and st.id ~= "n") and (" (" .. st.name .. ")") or ""
end
T.StyleSuffix = StyleSuffix

-- Loads PB/WR (and their splits) for the track the player is on
function T.SetTrack(ply, track, force)
	if ply.SurfTrack == track and not force then return end
	ply.SurfTrack = track
	ply:SetNW2Int("surf_track", track)
	local key = SURF.MapKey(track, ply.SurfStyle)
	local pb, splits = SURF.DB.GetRecord(key, ply:SteamID64())
	ply.SurfPBSplits = splits or {}
	ply:SetNW2Float("surf_pb", pb or 0)
	local wr = SURF.DB.GetWR(key)
	ply:SetNW2Float("surf_wr", wr and wr.time or 0)
	ply:SetNW2String("surf_wrname", wr and wr.name or "")
end

local function ClearRun(ply)
	ply.SurfSplits = {}
	ply.SurfLastCP = 0
	ply:SetNW2Int("surf_cp", 0)
	SURF.Replay.StopRecording(ply)
	SURF.Stats.Stop(ply)
end

function T.Reset(ply)
	ply.SurfInStart = false
	ClearRun(ply)
	ply:SetNW2Float("surf_start", 0)
	SetState(ply, SURF.Zones.HasTimer(0) and SURF.STATE_IDLE or SURF.STATE_NOZONES)
end

function T.Stop(ply, reason)
	if ply:GetNW2Int("surf_state") == SURF.STATE_RUNNING then
		ClearRun(ply)
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

local function Watchers(ply)
	local out = { ply }
	for _, p in ipairs(player.GetHumans()) do
		if p ~= ply and p:GetObserverTarget() == ply then out[#out + 1] = p end
	end
	return out
end

local function Split(ply, index)
	local elapsed = CurTime() - ply:GetNW2Float("surf_start")
	ply.SurfSplits[index] = elapsed
	ply.SurfLastCP = index
	ply:SetNW2Int("surf_cp", index)

	local pb = ply.SurfPBSplits and ply.SurfPBSplits[index]
	local wr = SURF.DB.GetWR(SURF.MapKey(ply.SurfTrack or 0, ply.SurfStyle))
	local wrs = wr and wr.splits and wr.splits[index]
	net.Start("surf.Split")
	net.WriteUInt(index, 8)
	net.WriteFloat(elapsed)
	net.WriteBool(pb ~= nil)
	net.WriteFloat(pb and (elapsed - pb) or 0)
	net.WriteBool(wrs ~= nil)
	net.WriteFloat(wrs and (elapsed - wrs) or 0)
	net.Send(Watchers(ply))
end

function T.OnZoneEnter(ply, zone)
	if not zone or ply:IsBot() or not ply:Alive() or ply:Team() == TEAM_SPECTATOR then return end
	if not SURF.Zones.HasTimer(zone.track) then return end
	local running = ply:GetNW2Int("surf_state") == SURF.STATE_RUNNING
	if zone.ztype == "start" then
		T.SetTrack(ply, zone.track)
		ply.SurfInStart = true
		ClearRun(ply)
		ply:SetNW2Float("surf_start", 0)
		SetState(ply, SURF.STATE_START)
	elseif zone.ztype == "end" and running and zone.track == ply.SurfTrack then
		if ply:GetMoveType() == MOVETYPE_NOCLIP then
			T.Stop(ply, "noclip")
			return
		end
		T.Finish(ply, CurTime() - ply:GetNW2Float("surf_start"))
	elseif zone.ztype == "cp" and running and zone.track == ply.SurfTrack and zone.index > (ply.SurfLastCP or 0) then
		Split(ply, zone.index)
	end
end

function T.OnZoneLeave(ply, zone)
	if not zone or zone.ztype ~= "start" or not ply.SurfInStart or zone.track ~= ply.SurfTrack then return end
	ply.SurfInStart = false
	if ply:IsBot() or not ply:Alive() or ply:GetMoveType() == MOVETYPE_NOCLIP then return end
	CapSpeed(ply)
	ClearRun(ply)
	ply:SetNW2Float("surf_start", CurTime())
	SetState(ply, SURF.STATE_RUNNING)
	SURF.Stats.Start(ply)
	-- The replay bot shows the Normal style record of the main track
	if zone.track == 0 and (ply.SurfStyle or "n") == "n" then SURF.Replay.StartRecording(ply) end
end

-- Shown on the HUD under the final time
local function PublishStats(ply, st)
	ply:SetNW2Int("surf_fin_jumps", st and st.jumps or 0)
	ply:SetNW2Int("surf_fin_strafes", st and st.strafes or 0)
	ply:SetNW2Float("surf_fin_sync", (st and st.sync) or -1)
	ply:SetNW2Float("surf_fin_max", st and st.max or 0)
end

function T.Finish(ply, time)
	local track = ply.SurfTrack or 0
	local style = ply.SurfStyle or "n"
	local frames, nframes = SURF.Replay.StopRecording(ply)
	local stats = SURF.Stats.Stop(ply)
	ply:SetNW2Float("surf_final", time)
	PublishStats(ply, stats)
	SetState(ply, SURF.STATE_FINISHED)

	local res = SURF.DB.SubmitTime(ply, SURF.MapKey(track, style), time, ply.SurfSplits, stats)
	local acc, white = SURF.Config.Accent, color_white
	local gold = Color(255, 200, 40)
	local where = (track > 0 and ("Bonus " .. track .. " of " .. game.GetMap()) or game.GetMap()) .. StyleSuffix(style)

	local diff = ""
	if res.oldPB then
		local d = time - res.oldPB
		diff = string.format(" (PB %s%.3f)", d < 0 and "-" or "+", math.abs(d))
	end

	if res.wr then
		local wrdiff = res.oldWR > 0 and string.format(" (-%.3f)", res.oldWR - time) or ""
		SURF.Chat(nil, gold, "[NEW SERVER RECORD] ", team.GetColor(ply:Team()), ply:Nick(), white,
			" set the record on ", acc, where, white, " with ", gold, SURF.FormatTime(time), white, wrdiff .. "!")
		for _, p in ipairs(player.GetHumans()) do p:SendLua([[surface.PlaySound("garrysmod/save_load4.wav")]]) end
		if track == 0 and style == "n" and frames then SURF.Replay.SetRecord(ply, time, frames, nframes) end
		hook.Run("SurfNewRecord", ply, time, res, track, style)
	elseif res.improved then
		SURF.Chat(nil, acc, "[Timer] ", team.GetColor(ply:Team()), ply:Nick(), white, " finished " .. TrackName(track) .. StyleSuffix(style) .. " in ", acc, SURF.FormatTime(time),
			white, diff .. " and is now rank ", acc, res.rank .. "/" .. res.total, white, ".")
		ply:SendLua([[surface.PlaySound("buttons/blip1.wav")]])
	else
		SURF.Chat(ply, acc, "[Timer] ", white, "You finished " .. TrackName(track) .. StyleSuffix(style) .. " in ", acc, SURF.FormatTime(time), white, diff .. ".")
	end
	if stats then
		for _, p in ipairs(Watchers(ply)) do SURF.Chat(p, acc, "[Stats] ", white, SURF.Stats.Describe(stats)) end
	end

	-- Refresh PB/WR display and everyone's WR on this track
	for _, p in ipairs(player.GetHumans()) do
		if p == ply or (res.wr and p.SurfTrack == track) then T.SetTrack(p, p.SurfTrack or 0, true) end
	end
	if res.improved then timer.Simple(0, SURF.Ranks.Recalc) end
	hook.Run("SurfFinish", ply, time, res, track, style)
end

-- Switch style (!style). Each style has its own records, so the player goes
-- back to the start of the track they were on.
function T.SetStyle(ply, id)
	local st = SURF.StyleByID[id or ""]
	if not st then return false end
	ply.SurfStyle = st.id
	ply:SetNW2String("surf_style", st.id)
	ply:SetGravity(st.gravity or 1)
	return true
end

function T.ChangeStyle(ply, id)
	local st = SURF.StyleByID[id or ""]
	if not st then return false end
	local acc, white = SURF.Config.Accent, color_white
	if (ply.SurfStyle or "n") == st.id then
		SURF.Chat(ply, acc, "[Style] ", white, "You are already on " .. st.name .. ".")
		return true
	end
	T.SetStyle(ply, st.id)
	local track = ply.SurfTrack or 0
	if ply:Team() ~= TEAM_SPECTATOR and SURF.Zones.StartPos(track) then
		T.GoToStart(ply, track)
	else
		T.Stop(ply)
	end
	T.SetTrack(ply, track, true)
	SURF.Chat(ply, acc, "[Style] ", white, "Style: ", acc, st.name, white, " (" .. st.help .. "). It has its own records; !style n goes back to Normal.")
	return true
end

-- Put a player in a start zone (main track by default, or a bonus)
function T.GoToStart(ply, track)
	track = track or 0
	if ply:Team() == TEAM_SPECTATOR then
		SURF.Spec.Toggle(ply)
		return
	end
	if not ply:Alive() then ply:Spawn() end
	local pos = SURF.Zones.StartPos(track)
	if not pos then
		if track == 0 then ply:Spawn() end
		return
	end
	if ply:GetMoveType() == MOVETYPE_NOCLIP then ply:SetMoveType(MOVETYPE_WALK) end
	ply:SetPos(pos)
	ply:SetLocalVelocity(vector_origin)
	-- Face the way the map goes
	local yaw = SURF.Zones.StartYaw(track)
	if yaw then ply:SetEyeAngles(Angle(0, yaw, 0)) end
	T.Reset(ply)
	T.SetTrack(ply, track)
	-- Already inside the start trigger, so StartTouch may not fire again
	if SURF.Zones.HasTimer(track) then
		ply.SurfInStart = true
		SetState(ply, SURF.STATE_START)
	end
end

-- Teleports used for practice end the current run
function T.PracticeTeleport(ply, pos, ang, vel)
	if ply:Team() == TEAM_SPECTATOR or not ply:Alive() then return end
	T.Stop(ply)
	ply.SurfInStart = false
	SetState(ply, SURF.Zones.HasTimer(0) and SURF.STATE_IDLE or SURF.STATE_NOZONES)
	ply:SetPos(pos)
	if ang then ply:SetEyeAngles(ang) end
	ply:SetLocalVelocity(vel or vector_origin)
end

-- Key presses for the spectator key display
hook.Add("SetupMove", "surf_keys", function(ply, mv)
	local keys = bit.band(mv:GetButtons(), IN_FORWARD + IN_BACK + IN_MOVELEFT + IN_MOVERIGHT + IN_JUMP + IN_DUCK)
	if ply.SurfKeys ~= keys then
		ply.SurfKeys = keys
		ply:SetNW2Int("surf_keys", keys)
	end
end)
