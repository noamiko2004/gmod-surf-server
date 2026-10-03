-- AFK players: after SURF.Config.AFKTime without input they move to the
-- spectators, and they never count towards the !rtv votes needed.
SURF.AFK = {}
local A = SURF.AFK

local function Touch(ply)
	ply.SurfActiveAt = CurTime()
end
A.Touch = Touch

function A.IdleTime(ply)
	if not ply.SurfActiveAt then Touch(ply) end
	return CurTime() - ply.SurfActiveAt
end

function A.IsAFK(ply)
	return A.IdleTime(ply) >= SURF.Config.AFKTime
end

-- Players who count for votes
function A.Active()
	local out = {}
	for _, p in ipairs(player.GetHumans()) do
		if not A.IsAFK(p) then out[#out + 1] = p end
	end
	return out
end

hook.Add("SetupMove", "surf_afk", function(ply, mv)
	if ply:IsBot() then return end
	local buttons = mv:GetButtons()
	local ang = mv:GetAngles()
	local last = ply.SurfAFKLast
	if not last or last.b ~= buttons or math.abs(last.p - ang.p) > 0.5 or math.abs(last.y - ang.y) > 0.5 then
		ply.SurfAFKLast = { b = buttons, p = ang.p, y = ang.y }
		Touch(ply)
	end
end)

hook.Add("PlayerSay", "surf_afk", function(ply) Touch(ply) end)
hook.Add("PlayerInitialSpawn", "surf_afk", Touch)

function A.Check()
	for _, p in ipairs(player.GetHumans()) do
		if p:Team() ~= TEAM_SPECTATOR and A.IsAFK(p) then
			SURF.Spec.Toggle(p)
			SURF.Chat(p, SURF.Config.Accent, "[AFK] ", color_white, "You were moved to the spectators for being away. Type !spec to surf again.")
		end
	end
	-- Fewer active players can mean enough !rtv votes now
	SURF.MapVote.CheckRTV()
end
timer.Create("surf_afk_check", 15, 0, A.Check)
