-- !spec: watch other surfers. Left/right click cycles targets, jump switches
-- between first person, third person and free roam.
SURF.Spec = {}
local Spec = SURF.Spec
local MODES = { OBS_MODE_IN_EYE, OBS_MODE_CHASE, OBS_MODE_ROAMING }

local function Targets(ply)
	local out = {}
	for _, p in ipairs(player.GetAll()) do
		if p ~= ply and p:Alive() and p:Team() ~= TEAM_SPECTATOR then out[#out + 1] = p end
	end
	return out
end

function Spec.Begin(ply)
	local list = Targets(ply)
	if #list == 0 then
		ply:Spectate(OBS_MODE_ROAMING)
		return
	end
	ply.SurfSpecMode = ply.SurfSpecMode or 1
	ply:Spectate(MODES[ply.SurfSpecMode])
	ply:SpectateEntity(list[1])
end

function Spec.Toggle(ply)
	if ply:Team() == TEAM_SPECTATOR then
		ply:SetTeam(TEAM_SURF)
		ply:UnSpectate()
		ply:Spawn()
		SURF.Chat(ply, SURF.Config.Accent, "[Spec] ", color_white, "Back to surfing.")
	else
		SURF.Timer.Reset(ply)
		ply:SetTeam(TEAM_SPECTATOR)
		ply:KillSilent()
		SURF.Trails.Apply(ply)
		Spec.Begin(ply)
		SURF.Chat(ply, SURF.Config.Accent, "[Spec] ", color_white, "Spectating. Click to switch players, jump to change view, !spec to go back.")
	end
end

-- Spectate one player (from !spec <name>, the scoreboard or the admin panel)
function Spec.Watch(ply, target)
	if ply:Team() ~= TEAM_SPECTATOR then Spec.Toggle(ply) end
	if (ply.SurfSpecMode or 1) == 3 then ply.SurfSpecMode = 1 end
	ply:Spectate(MODES[ply.SurfSpecMode or 1])
	ply:SpectateEntity(target)
end

local function Cycle(ply, dir)
	local list = Targets(ply)
	if #list == 0 then
		ply:Spectate(OBS_MODE_ROAMING)
		return
	end
	local cur = ply:GetObserverTarget()
	local idx = 0
	for i, p in ipairs(list) do
		if p == cur then idx = i break end
	end
	idx = ((idx - 1 + dir) % #list) + 1
	if ply:GetObserverMode() == OBS_MODE_ROAMING then
		ply.SurfSpecMode = 1
		ply:Spectate(MODES[1])
	end
	ply:SpectateEntity(list[idx])
end

hook.Add("KeyPress", "surf_spec_keys", function(ply, key)
	if ply:Team() ~= TEAM_SPECTATOR then return end
	if key == IN_ATTACK then
		Cycle(ply, 1)
	elseif key == IN_ATTACK2 then
		Cycle(ply, -1)
	elseif key == IN_JUMP then
		ply.SurfSpecMode = ((ply.SurfSpecMode or 1) % #MODES) + 1
		ply:Spectate(MODES[ply.SurfSpecMode])
		if ply.SurfSpecMode ~= 3 and not IsValid(ply:GetObserverTarget()) then Cycle(ply, 1) end
	end
end)

-- Move spectators off a target that left or started spectating, and keep who
-- is watching on each player for the HUD's spectator list: the count, then up
-- to 8 names, one per line (short enough for an NW2String)
local MAX_NAMES = 8
timer.Create("surf_spec_fix", 1, 0, function()
	local watching = {}
	for _, p in ipairs(player.GetAll()) do
		if p:Team() == TEAM_SPECTATOR and p:GetObserverMode() ~= OBS_MODE_ROAMING then
			local t = p:GetObserverTarget()
			if not IsValid(t) or not t:IsPlayer() or t:Team() == TEAM_SPECTATOR then
				Cycle(p, 1)
				t = p:GetObserverTarget()
			end
			if IsValid(t) and t:IsPlayer() then
				watching[t] = watching[t] or {}
				table.insert(watching[t], string.sub(p:Nick(), 1, 24))
			end
		end
	end
	for _, p in ipairs(player.GetAll()) do
		local list, value = watching[p], ""
		if list then value = #list .. "\n" .. table.concat(list, "\n", 1, math.min(#list, MAX_NAMES)) end
		if p:GetNW2String("surf_watchers", "") ~= value then p:SetNW2String("surf_watchers", value) end
	end
end)
