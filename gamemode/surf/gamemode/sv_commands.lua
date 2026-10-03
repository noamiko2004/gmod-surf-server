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

Add({ "r", "restart", "start" }, "Go back to the start", function(ply) SURF.Timer.GoToStart(ply, 0) end)

Add({ "b", "bonus" }, "!b [number] goes to a bonus start", function(ply, args)
	local bonuses = SURF.Zones.Bonuses()
	local n = tonumber(args[1] or "") or bonuses[1]
	if not n or not SURF.Zones.HasTimer(n) then
		SURF.Chat(ply, acc, "[Timer] ", white, #bonuses > 0 and ("Bonuses on this map: " .. table.concat(bonuses, ", ")) or "This map has no bonuses.")
		return
	end
	SURF.Timer.GoToStart(ply, n)
end)

Add({ "stage", "s" }, "!stage <number> practice from a stage/checkpoint", function(ply, args)
	local n = tonumber(args[1] or "")
	local pos = n and (n <= 1 and SURF.Zones.StartPos(0) or SURF.Zones.StagePos(n))
	if not pos then
		local count = SURF.Zones.cpCount[0] or 0
		SURF.Chat(ply, acc, "[Practice] ", white, count > 0 and ("Stages/checkpoints here: 1-" .. count) or "This map has no stages.")
		return
	end
	if n <= 1 then return SURF.Timer.GoToStart(ply, 0) end
	SURF.Timer.PracticeTeleport(ply, pos)
	SURF.Chat(ply, acc, "[Practice] ", white, "Stage " .. n .. ". Your timer is off until you go back with !r.")
end)

Add({ "saveloc", "cp", "save" }, "Save your position for practice", function(ply)
	if not ply:Alive() or ply:Team() == TEAM_SPECTATOR then return end
	ply.SurfSaves = ply.SurfSaves or {}
	table.insert(ply.SurfSaves, { pos = ply:GetPos(), ang = ply:EyeAngles(), vel = ply:GetVelocity() })
	if #ply.SurfSaves > 20 then table.remove(ply.SurfSaves, 1) end
	SURF.Chat(ply, acc, "[Practice] ", white, "Saved #" .. #ply.SurfSaves .. ". !tele goes back (stops your timer).")
end)

Add({ "tele", "tp", "load" }, "!tele [number] goes back to a saved position", function(ply, args)
	local saves = ply.SurfSaves or {}
	local s = saves[tonumber(args[1] or "") or #saves]
	if not s then return SURF.Chat(ply, acc, "[Practice] ", white, "Nothing saved yet. Use !saveloc first.") end
	SURF.Timer.PracticeTeleport(ply, s.pos, s.ang, s.vel)
end)

Add({ "wr", "records", "maptop" }, "Top times on this map (!wr <map>)", function(ply, args)
	local map = args[1] and string.lower(args[1]) or game.GetMap()
	SURF.Menu.Open(ply, "records", { map = map, rows = SURF.DB.Top(map, 50), total = SURF.DB.Count(map) })
end)

Add({ "bwr", "btop" }, "Top times on a bonus (!bwr [number])", function(ply, args)
	local n = tonumber(args[1] or "") or SURF.Zones.Bonuses()[1] or 1
	local key = SURF.MapKey(n)
	SURF.Menu.Open(ply, "records", { map = game.GetMap() .. " bonus " .. n, rows = SURF.DB.Top(key, 50), total = SURF.DB.Count(key) })
end)

Add({ "pb" }, "Your best time and rank here", function(ply)
	local track = ply.SurfTrack or 0
	local key = SURF.MapKey(track)
	local pb = SURF.DB.GetRecord(key, ply:SteamID64())
	local where = track > 0 and ("bonus " .. track) or game.GetMap()
	if not pb then
		SURF.Chat(ply, acc, "[Timer] ", white, "You haven't finished " .. where .. " yet.")
		return
	end
	SURF.Chat(ply, acc, "[Timer] ", white, "Your best on " .. where .. ": ", acc, SURF.FormatTime(pb), white,
		" (rank " .. SURF.DB.RankOf(key, pb) .. "/" .. SURF.DB.Count(key) .. ")")
end)

Add({ "rank", "points" }, "Your points, title and server rank", function(ply) SURF.Ranks.Describe(ply) end)

Add({ "top", "toplist", "leaderboard" }, "Best players on the server", function(ply)
	SURF.Menu.Open(ply, "players", { rows = SURF.Ranks.TopMenuData(50), total = #SURF.Ranks.list })
end)

Add({ "replay", "wrbot" }, "Watch the server record replay", function(ply) SURF.Replay.Spectate(ply) end)

Add({ "keys", "showkeys" }, "Show or hide the key display", function(ply) SURF.ClientAction(ply, "keys") end)

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
	SURF.Menu.Open(ply, "maps", { maps = SURF.MapVote.Info(SURF.MapVote.Playable()) })
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

Add({ "zone", "zones" }, "Place zones (!zone start|end|delete|reset|info)", function(ply, args) SURF.Zones.EditCommand(ply, args) end, true)

Add({ "deltime" }, "!deltime <steamid64> removes a time on this map", function(ply, args)
	if not args[1] then return SURF.Chat(ply, white, "Usage: !deltime <steamid64>") end
	SURF.DB.DeleteTime(game.GetMap(), args[1])
	SURF.Chat(ply, acc, "[Admin] ", white, "Deleted the time for " .. args[1] .. ".")
end, true)

Add({ "forcevote" }, "Start a map vote now", function() if not SURF.MapVote.active then SURF.MapVote.Start(true) end end, true)

Add({ "map", "changelevel" }, "!map <name> switches to any installed map (also ones without zones)", function(ply, args)
	local map = SURF.MapVote.ResolveMap(args[1], SURF.MapVote.MapList())
	if not map then return SURF.Chat(ply, acc, "[Admin] ", white, "No installed map matches \"" .. tostring(args[1] or "") .. "\".") end
	SURF.Chat(nil, acc, "[Admin] ", white, ply:Nick() .. " is changing the map to ", acc, map, white, ".")
	timer.Simple(3, function()
		for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
		RunConsoleCommand("changelevel", map)
	end)
end, true)

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
