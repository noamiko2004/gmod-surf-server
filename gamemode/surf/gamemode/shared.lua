DeriveGamemode("base")

GM.Name = "Surf"
GM.Author = "Surf"
GM.TeamBased = false

include("sh_config.lua")

TEAM_SURF = 1
team.SetUp(TEAM_SURF, "Surfers", Color(0, 200, 255))

-- Timer states stored in the player's "surf_state" NW2Int
SURF.STATE_NOZONES = 0
SURF.STATE_START = 1
SURF.STATE_RUNNING = 2
SURF.STATE_FINISHED = 3
SURF.STATE_IDLE = 4

function SURF.FormatTime(t)
	if not t or t <= 0 then return "--:--.---" end
	t = math.floor(t * 1000 + 0.5) / 1000
	local h = math.floor(t / 3600)
	local m = math.floor((t % 3600) / 60)
	local s = t % 60
	if h > 0 then
		return string.format("%d:%02d:%06.3f", h, m, s)
	end
	return string.format("%02d:%06.3f", m, s)
end

function SURF.IsVIP(ply)
	return IsValid(ply) and ply:GetNW2Bool("surf_vip", false)
end

-- Holding jump keeps bunnyhopping. Shared so client prediction matches.
hook.Add("SetupMove", "surf_autohop", function(ply, mv)
	if not ply:GetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop) then return end
	if ply:GetMoveType() ~= MOVETYPE_WALK or ply:WaterLevel() >= 2 then return end
	if not ply:OnGround() then
		mv:SetButtons(bit.band(mv:GetButtons(), bit.bnot(IN_JUMP)))
	end
end)
