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

-- Chat line with VIP / admin tags
function GM:OnPlayerChat(ply, text, teamChat, dead)
	local parts = {}
	if IsValid(ply) then
		if ply:IsAdmin() then
			parts[#parts + 1] = Color(255, 80, 80)
			parts[#parts + 1] = "[ADMIN] "
		elseif SURF.IsVIP(ply) then
			parts[#parts + 1] = Color(255, 200, 40)
			parts[#parts + 1] = "[VIP] "
		end
		if ply:Team() == TEAM_SPECTATOR then
			parts[#parts + 1] = Color(160, 160, 160)
			parts[#parts + 1] = "*SPEC* "
		end
		parts[#parts + 1] = SURF.IsVIP(ply) and Color(255, 220, 120) or team.GetColor(ply:Team())
		parts[#parts + 1] = ply:Nick()
	else
		parts[#parts + 1] = Color(160, 160, 160)
		parts[#parts + 1] = "Console"
	end
	parts[#parts + 1] = color_white
	parts[#parts + 1] = ": " .. text
	chat.AddText(unpack(parts))
	return true
end

-- Client-only toggles
local hidePlayers = CreateClientConVar("surf_hideplayers", "0", true, false)

net.Receive("surf.Action", function()
	local action = net.ReadString()
	if action == "hide" then
		local on = not hidePlayers:GetBool()
		RunConsoleCommand("surf_hideplayers", on and "1" or "0")
		chat.AddText(SURF.Config.Accent, "[Settings] ", color_white, "Other players are now " .. (on and "hidden" or "visible") .. ".")
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

-- Draw zone outlines
local zones = {}
net.Receive("surf.Zones", function() zones = net.ReadTable() end)

local ZONE_COLORS = { start = Color(0, 255, 120), ["end"] = Color(255, 60, 60) }
hook.Add("PostDrawTranslucentRenderables", "surf_zones", function(depth, skybox)
	if skybox then return end
	for ztype, z in pairs(zones) do
		render.DrawWireframeBox(vector_origin, angle_zero, z.min, Vector(z.max.x, z.max.y, z.min.z + 2), ZONE_COLORS[ztype] or color_white, true)
	end
end)

hook.Add("InitPostEntity", "surf_ready", function()
	net.Start("surf.Ready")
	net.SendToServer()
end)
