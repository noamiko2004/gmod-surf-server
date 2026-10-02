-- Chat commands. Both !cmd and /cmd work; the message itself is hidden.
SURF.Commands = { list = {}, order = {} }
local C = SURF.Commands

local function Add(names, help, fn, adminOnly)
	local entry = { names = names, help = help, fn = fn, admin = adminOnly }
	for _, n in ipairs(names) do C.list[n] = entry end
	C.order[#C.order + 1] = entry
end

function C.Run(ply, name, args)
	local entry = C.list[string.lower(name)]
	if not entry then return false end
	if entry.admin and not ply:IsAdmin() then
		SURF.Chat(ply, Color(255, 80, 80), "You don't have access to that command.")
		return true
	end
	entry.fn(ply, args)
	return true
end

function C.HelpList(isAdmin)
	local out = {}
	for _, e in ipairs(C.order) do
		if isAdmin or not e.admin then
			out[#out + 1] = { cmd = "!" .. table.concat(e.names, " !"), help = e.help, admin = e.admin }
		end
	end
	return out
end

local acc, white = SURF.Config.Accent, color_white

Add({ "r", "restart", "start" }, "Go back to the start", function(ply) SURF.Timer.GoToStart(ply) end)

Add({ "wr", "top", "records" }, "Top 10 times on this map", function(ply, args)
	local map = args[1] and string.lower(args[1]) or game.GetMap()
	SURF.Menu.Open(ply, "records", { map = map, rows = SURF.DB.Top(map, 50), total = SURF.DB.Count(map) })
end)

Add({ "pb", "rank" }, "Your best time and rank here", function(ply)
	local pb = ply:GetNW2Float("surf_pb", 0)
	if pb <= 0 then
		SURF.Chat(ply, acc, "[Timer] ", white, "You haven't finished " .. game.GetMap() .. " yet.")
		return
	end
	local map = game.GetMap()
	SURF.Chat(ply, acc, "[Timer] ", white, "Your best: ", acc, SURF.FormatTime(pb), white,
		" (rank " .. SURF.DB.RankOf(map, pb) .. "/" .. SURF.DB.Count(map) .. ")")
end)

Add({ "spec", "spectate" }, "Spectate other players (again to return)", function(ply) SURF.Spec.Toggle(ply) end)

Add({ "auto", "autohop" }, "Toggle holding jump to bunnyhop", function(ply)
	local on = not ply:GetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop)
	ply:SetNW2Bool("surf_autohop", on)
	SURF.Chat(ply, acc, "[Settings] ", white, "Autohop " .. (on and "enabled" or "disabled") .. ".")
end)

Add({ "hide", "show" }, "Hide or show other players", function(ply) SURF.ClientAction(ply, "hide") end)

Add({ "trail", "trails" }, "Pick a trail", function(ply) SURF.Menu.Open(ply, "trails") end)

Add({ "rtv", "rockthevote" }, "Vote to change the map", function(ply) SURF.MapVote.RTV(ply) end)

Add({ "nominate", "nom" }, "Nominate a map for the next vote", function(ply, args) SURF.MapVote.Nominate(ply, args[1]) end)

Add({ "maps", "maplist" }, "List the maps on the server", function(ply)
	SURF.Menu.Open(ply, "maps", { maps = SURF.MapVote.MapList() })
end)

Add({ "timeleft" }, "Time until the map vote", function(ply)
	local left = math.max(0, GetGlobal2Int("surf_mapend") - CurTime())
	SURF.Chat(ply, acc, "[Vote] ", white, string.format("%d:%02d left on this map.", math.floor(left / 60), math.floor(left % 60)))
end)

Add({ "vip", "store", "donate" }, "VIP perks and how to support the server", function(ply)
	SURF.Menu.Open(ply, "vip", { url = SURF.Config.StoreURL, vip = SURF.IsVIP(ply), expires = ply.SurfVIPExpires })
end)

Add({ "discord" }, "Join our Discord", function(ply)
	if SURF.Config.DiscordURL ~= "" then
		ply:SendLua("gui.OpenURL(" .. string.format("%q", SURF.Config.DiscordURL) .. ")")
	else
		SURF.Chat(ply, acc, "[Info] ", white, "Discord coming soon.")
	end
end)

Add({ "help", "commands", "cmds" }, "Show this list", function(ply) SURF.Menu.Open(ply, "help", { cmds = C.HelpList(ply:IsAdmin()) }) end)

-- Admin -----------------------------------------------------------------

Add({ "zone", "zones" }, "Place start/end zones", function(ply, args) SURF.Zones.EditCommand(ply, args) end, true)

Add({ "deltime" }, "!deltime <steamid64> removes a time on this map", function(ply, args)
	if not args[1] then return SURF.Chat(ply, white, "Usage: !deltime <steamid64>") end
	SURF.DB.DeleteTime(game.GetMap(), args[1])
	SURF.Chat(ply, acc, "[Admin] ", white, "Deleted the time for " .. args[1] .. ".")
end, true)

Add({ "forcevote" }, "Start a map vote now", function() if not SURF.MapVote.active then SURF.MapVote.Start(true) end end, true)

hook.Add("PlayerSay", "surf_commands", function(ply, text)
	local first = string.sub(text, 1, 1)
	if first ~= "!" and first ~= "/" then return end
	local parts = string.Explode(" ", string.Trim(string.sub(text, 2)))
	local name = table.remove(parts, 1) or ""
	local args = {}
	for _, a in ipairs(parts) do
		if a ~= "" then args[#args + 1] = a end
	end
	if C.Run(ply, name, args) then return "" end
end)

-- HUD menus need the help list from the client too (F1)
local oldOpen = SURF.Menu.Open
function SURF.Menu.Open(ply, kind, data)
	if kind == "help" and not data then data = { cmds = C.HelpList(ply:IsAdmin()) } end
	if kind == "vip" and not data then data = { url = SURF.Config.StoreURL, vip = SURF.IsVIP(ply), expires = ply.SurfVIPExpires } end
	oldOpen(ply, kind, data)
end
