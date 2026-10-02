include("shared.lua")
include("cl_hud.lua")
include("cl_scoreboard.lua")
include("cl_menus.lua")
include("cl_mapvote.lua")

local function Font(name, size, weight)
	surface.CreateFont(name, { font = "Roboto", size = size, weight = weight or 500, antialias = true, extended = true })
end
Font("SurfTimer", 40, 700)
Font("SurfLarge", 24, 600)
Font("SurfMedium", 18, 500)
Font("SurfSmall", 15, 500)

-- Colored chat from the server
net.Receive("surf.Chat", function()
	local n = net.ReadUInt(8)
	local args = {}
	for i = 1, n do
		if net.ReadBool() then args[i] = net.ReadColor() else args[i] = net.ReadString() end
	end
	chat.AddText(unpack(args))
end)

-- Chat line with title / VIP / admin tags
function GM:OnPlayerChat(ply, text, teamChat, dead)
	local parts = {}
	local function add(col, str) parts[#parts + 1] = col parts[#parts + 1] = str end
	if IsValid(ply) then
		local title = SURF.Config.Titles[ply:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
		add(title.color, "[" .. title.name .. "] ")
		if ply:IsAdmin() then
			add(Color(255, 80, 80), "[ADMIN] ")
		elseif SURF.IsVIP(ply) then
			add(Color(255, 200, 40), "[VIP] ")
		end
		if ply:Team() == TEAM_SPECTATOR then add(Color(160, 160, 160), "*SPEC* ") end
		add(SURF.IsVIP(ply) and Color(255, 220, 120) or team.GetColor(ply:Team()), ply:Nick())
	else
		add(Color(160, 160, 160), "Console")
	end
	add(color_white, ": " .. text)
	chat.AddText(unpack(parts))
	return true
end

-- Client-only toggles
local hidePlayers = CreateClientConVar("surf_hideplayers", "0", true, false)
local showKeys = CreateClientConVar("surf_showkeys", "1", true, false)

net.Receive("surf.Action", function()
	local action = net.ReadString()
	if action == "hide" then
		local on = not hidePlayers:GetBool()
		RunConsoleCommand("surf_hideplayers", on and "1" or "0")
		chat.AddText(SURF.Config.Accent, "[Settings] ", color_white, "Other players are now " .. (on and "hidden" or "visible") .. ".")
	elseif action == "keys" then
		local on = not showKeys:GetBool()
		RunConsoleCommand("surf_showkeys", on and "1" or "0")
		chat.AddText(SURF.Config.Accent, "[Settings] ", color_white, "Key display " .. (on and "on" or "off") .. ".")
	end
end)

hook.Add("PrePlayerDraw", "surf_hide", function(ply)
	if hidePlayers:GetBool() and ply ~= LocalPlayer() and ply ~= LocalPlayer():GetObserverTarget() then
		return true
	end
end)

timer.Create("surf_hide_trails", 0.5, 0, function()
	local hide = hidePlayers:GetBool()
	local me = LocalPlayer()
	if not IsValid(me) then return end
	for _, p in ipairs(player.GetAll()) do
		local trail = p:GetNW2Entity("surf_trail")
		if IsValid(trail) then
			trail:SetNoDraw(hide and p ~= me and p ~= me:GetObserverTarget())
		end
	end
end)

-- Zones: drawn as floor outlines (start green, end red, bonuses blue/purple)
SURF.ClientZones = {}
net.Receive("surf.Zones", function()
	local list = {}
	for _, z in ipairs(net.ReadTable()) do
		list[#list + 1] = { ztype = z.t, track = z.k, index = z.i, min = z.a, max = z.b }
	end
	SURF.ClientZones = list
end)

function SURF.ClientCPCount(track)
	local n = 0
	for _, z in ipairs(SURF.ClientZones) do
		if z.ztype == "cp" and z.track == track then n = math.max(n, z.index) end
	end
	return n
end

local ZONE_COLORS = {
	start = Color(0, 255, 120), ["end"] = Color(255, 60, 60),
	bstart = Color(60, 160, 255), bend = Color(200, 90, 255),
}
hook.Add("PostDrawTranslucentRenderables", "surf_zones", function(depth, skybox)
	if skybox then return end
	for _, z in ipairs(SURF.ClientZones) do
		if z.ztype ~= "cp" then
			local key = (z.track > 0 and "b" or "") .. z.ztype
			render.DrawWireframeBox(vector_origin, angle_zero, z.min, Vector(z.max.x, z.max.y, z.min.z + 2), ZONE_COLORS[key] or color_white, true)
		end
	end
end)

hook.Add("InitPostEntity", "surf_ready", function()
	net.Start("surf.Ready")
	net.SendToServer()
end)
