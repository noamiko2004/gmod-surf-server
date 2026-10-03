AddCSLuaFile("shared.lua")
AddCSLuaFile("sh_config.lua")
AddCSLuaFile("cl_init.lua")
AddCSLuaFile("cl_hud.lua")
AddCSLuaFile("cl_scoreboard.lua")
AddCSLuaFile("cl_menus.lua")
AddCSLuaFile("cl_mapvote.lua")
AddCSLuaFile("cl_visuals.lua")

include("shared.lua")
include("sv_util.lua")
include("sv_db.lua")
include("sv_zones.lua")
include("sv_stats.lua")
include("sv_timer.lua")
include("sv_replay.lua")
include("sv_ranks.lua")
include("sv_vip.lua")
include("sv_trails.lua")
include("sv_mapvote.lua")
include("sv_spectate.lua")
include("sv_afk.lua")
include("sv_social.lua")
include("sv_discord.lua")
include("sv_discord_bridge.lua")
include("sv_commands.lua")
include("sv_portal.lua")

-- Make clients download the current map's workshop addon and any extras
local function AddWorkshopDownloads()
	local map = game.GetMap()
	-- Maps installed by scripts/maps.py ("map wsid" per line)
	for line in string.gmatch(file.Read("surfline/map_ws.txt", "DATA") or "", "[^\n]+") do
		local name, id = string.match(line, "^(%S+)%s+(%d+)")
		if name == map then resource.AddWorkshop(id) end
	end
	for _, addon in ipairs(engine.GetAddons()) do
		if addon.mounted and addon.wsid and file.Exists("maps/" .. map .. ".bsp", addon.title) then
			resource.AddWorkshop(addon.wsid)
		end
	end
	for _, id in ipairs(SURF.Config.ClientWorkshop) do
		resource.AddWorkshop(id)
	end
end

-- Short server name for the HUD and chat, Discord and store links
-- (BRAND_NAME, DISCORD_URL and STORE_URL in config.env)
local function LoadBrand()
	local brand = string.Trim(file.Read("surfline/brand.txt", "DATA") or "")
	if brand ~= "" then SURF.Config.Name = brand end
	SetGlobal2String("surf_brand", SURF.Config.Name)
	local links = util.JSONToTable(file.Read("surfline/links.json", "DATA") or "") or {}
	if isstring(links.discord) and string.StartWith(links.discord, "https://") then SURF.Config.DiscordURL = links.discord end
	if isstring(links.store) and string.StartWith(links.store, "https://") then SURF.Config.StoreURL = links.store end
end

function GM:Initialize()
	AddWorkshopDownloads()
	LoadBrand()
end

-- Some maps are built for a higher sv_maxvelocity (zones/maxvel.txt)
hook.Add("InitPostEntity", "surf_maxvel", function()
	local vel = 3500
	for line in string.gmatch(file.Read("surfline/maxvel.txt", "DATA") or "", "[^\n]+") do
		local name, v = string.match(line, "^(%S+)%s+(%d+)")
		if name == game.GetMap() then vel = tonumber(v) end
	end
	RunConsoleCommand("sv_maxvelocity", tostring(vel))
	-- server.cfg may run after this on some map loads, so set it again
	timer.Simple(5, function() RunConsoleCommand("sv_maxvelocity", tostring(vel)) end)
end)

-- Owners listed in config.env (OWNER_STEAMIDS) become superadmin
local function IsOwner(ply)
	local list = file.Read("surfline/owners.txt", "DATA") or ""
	for id in string.gmatch(list, "%d+") do
		if id == ply:SteamID64() then return true end
	end
	return false
end

function GM:PlayerInitialSpawn(ply)
	ply:SetTeam(TEAM_SURF)
	if ply:IsBot() then return end
	if IsOwner(ply) and not ply:IsSuperAdmin() then ply:SetUserGroup("superadmin") end
	ply:SetNW2Int("surf_state", SURF.STATE_IDLE)
	SURF.DB.LoadPlayer(ply)
	SURF.Timer.SetTrack(ply, 0, true)
	SURF.Ranks.Apply(ply)
end

-- The client says when its Lua is loaded, so net messages aren't dropped
net.Receive("surf.Ready", function(_, ply)
	if ply.SurfReady then return end
	ply.SurfReady = true
	SURF.Zones.SendTo(ply)
	SURF.Chat(ply, SURF.Config.Accent, "Welcome to " .. SURF.Config.Name .. "! ", color_white, "Type ", SURF.Config.Accent, "!help", color_white, " for commands.")
	hook.Run("SurfPlayerReady", ply)
end)

function GM:PlayerSpawn(ply)
	if ply:Team() == TEAM_SPECTATOR then
		SURF.Spec.Begin(ply)
		return
	end
	ply:UnSpectate()
	player_manager.SetPlayerClass(ply, "player_default")
	self:PlayerSetModel(ply)
	ply:SetupHands()
	ply:StripWeapons()

	if ply:IsBot() then
		SURF.Replay.bot = ply
		SURF.Replay.SetupBot(ply)
		return
	end

	ply:SetWalkSpeed(SURF.Config.WalkSpeed)
	ply:SetRunSpeed(SURF.Config.WalkSpeed)
	ply:SetMaxSpeed(SURF.Config.WalkSpeed)
	ply:SetJumpPower(SURF.Config.JumpPower)
	ply:SetGravity(SURF.StyleOf(ply).gravity or 1)
	ply:SetCrouchedWalkSpeed(0.34)
	ply:SetAvoidPlayers(false)
	ply:SetNoCollideWithTeammates(true)
	ply:AllowFlashlight(true)

	SURF.Timer.Reset(ply)
	SURF.Trails.Apply(ply)
	-- Spawn in the start zone when the map has one
	timer.Simple(0, function()
		if IsValid(ply) and ply:Alive() and SURF.Zones.StartPos(0) then SURF.Timer.GoToStart(ply, 0) end
	end)
end

function GM:PlayerSetModel(ply)
	local mdl = player_manager.TranslatePlayerModel(ply:GetInfo("cl_playermodel"))
	util.PrecacheModel(mdl)
	ply:SetModel(mdl)
end

function GM:PlayerLoadout(ply) return true end

function GM:GetFallDamage() return 0 end

function GM:PlayerShouldTakeDamage(ply, attacker)
	-- Map hazards (trigger_hurt) still work; players can't hurt each other
	return not (IsValid(attacker) and attacker:IsPlayer())
end

function GM:PlayerDeath(ply)
	ply.SurfRespawnAt = CurTime() + SURF.Config.RespawnDelay
	SURF.Timer.Reset(ply)
end

function GM:PlayerDeathThink(ply)
	if ply:Team() == TEAM_SPECTATOR then return end
	if ply:IsBot() then ply:Spawn() return end
	if CurTime() >= (ply.SurfRespawnAt or 0) then
		ply:Spawn()
	end
end

function GM:PlayerNoClip(ply, on)
	if not ply:IsAdmin() then return false end
	if on then SURF.Timer.Stop(ply, "noclip") end
	return true
end

function GM:CanPlayerSuicide(ply) return ply:Team() ~= TEAM_SPECTATOR end

function GM:PlayerDisconnected(ply)
	if ply:IsBot() then return end
	SURF.DB.SavePlayer(ply)
	SURF.MapVote.OnDisconnect(ply)
end

function GM:ShowHelp(ply) SURF.Menu.Open(ply, "help") end
function GM:ShowTeam(ply) SURF.Commands.Run(ply, "wr", {}) end
function GM:ShowSpare1(ply) SURF.Menu.Open(ply, "trails") end
function GM:ShowSpare2(ply) SURF.Spec.Toggle(ply) end
