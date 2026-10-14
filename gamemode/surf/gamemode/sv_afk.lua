-- AFK players: after SURF.Config.AFKTime without input they move to the
-- spectators, and they never count towards the !rtv votes needed. Any key
-- brings them straight back to surfing. Menus and the chat box count as being
-- here (the client says so), so reading the shop never moves anyone.
SURF.AFK = {}
local A = SURF.AFK
util.AddNetworkString("surf.Active")

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
	-- Watching someone turns your view with theirs, so then only keys count
	local obs = ply:GetObserverMode()
	local looks = obs == OBS_MODE_NONE or obs == OBS_MODE_ROAMING
	if not last or last.b ~= buttons or (looks and (math.abs(last.p - ang.p) > 0.5 or math.abs(last.y - ang.y) > 0.5)) then
		ply.SurfAFKLast = { b = buttons, p = ang.p, y = ang.y }
		Touch(ply)
	end
end)

hook.Add("PlayerSay", "surf_afk", function(ply) Touch(ply) end)
hook.Add("PlayerInitialSpawn", "surf_afk", Touch)
-- Again once their game has loaded, so a slow load isn't time away
hook.Add("SurfPlayerReady", "surf_afk", Touch)

-- The client pings while its mouse moves in a menu or the player types in chat
net.Receive("surf.Active", function(_, ply)
	if CurTime() - (ply.SurfActivePing or -60) < 10 then return end
	ply.SurfActivePing = CurTime()
	Touch(ply)
end)

-- Moved for being away: any key (but the scoreboard's) puts them back
function A.Clear(ply)
	if not ply.SurfAFKMoved then return end
	ply.SurfAFKMoved = nil
	ply:SetNW2Bool("surf_afk", false)
end

function A.Back(ply)
	if not ply.SurfAFKMoved then return end
	A.Clear(ply)
	Touch(ply)
	if ply:Team() == TEAM_SPECTATOR then SURF.Spec.Toggle(ply) end
end

hook.Add("KeyPress", "surf_afk_back", function(ply, key)
	if not ply.SurfAFKMoved or key == IN_SCORE then return end
	-- After this key's own movement step, which would undo a respawn
	timer.Simple(0, function() if IsValid(ply) then A.Back(ply) end end)
end)

function A.Check()
	for _, p in ipairs(player.GetHumans()) do
		if p:Team() ~= TEAM_SPECTATOR and A.IsAFK(p) then
			SURF.Spec.Toggle(p, true)
			p.SurfAFKMoved = true
			p:SetNW2Bool("surf_afk", true)
			SURF.Chat(p, SURF.Config.Accent, "[AFK] ", color_white, "You were away, so you're watching for now. Press any key to surf again.")
		end
	end
	-- Fewer active players can mean enough !rtv votes now
	SURF.MapVote.CheckRTV()
end
timer.Create("surf_afk_check", 15, 0, A.Check)
