-- Chat commands. Both !cmd and /cmd work; the message itself is hidden.
SURF.Commands = { list = {}, order = {} }
local C = SURF.Commands

local function Add(names, help, fn, adminOnly)
	local entry = { names = names, help = help, fn = fn, admin = adminOnly }
	for _, n in ipairs(names) do C.list[n] = entry end
	C.order[#C.order + 1] = entry
end
C.Add = Add

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

-- Names and help of the commands a player may use, for the chat autocomplete
function C.ClientList(isAdmin)
	local out = {}
	for _, e in ipairs(C.order) do
		if isAdmin or not e.admin then out[#out + 1] = { n = e.names, h = e.help, a = e.admin or nil } end
	end
	return out
end

function C.SendList(ply)
	net.Start("surf.Commands")
	net.WriteTable(C.ClientList(ply:IsAdmin()))
	net.Send(ply)
end
hook.Add("SurfPlayerReady", "surf_command_list", function(ply) C.SendList(ply) end)

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

-- "!wr", "!wr sw", "!wr surf_x", "!wr surf_x sw": the style defaults to your own
local function MapAndStyle(ply, args)
	local map, style = nil, nil
	for _, a in ipairs(args) do
		a = string.lower(a)
		if SURF.StyleByID[a] then style = a else map = map or a end
	end
	return map, style or ply.SurfStyle or "n"
end

Add({ "wr", "records", "maptop" }, "Top times on this map (!wr [map] [style])", function(ply, args)
	local map, style = MapAndStyle(ply, args)
	local key = (map or game.GetMap()) .. (style ~= "n" and ("@" .. style) or "")
	SURF.Menu.Open(ply, "records", { map = (map or game.GetMap()) .. SURF.Timer.StyleSuffix(style), rows = SURF.DB.Top(key, 50), total = SURF.DB.Count(key) })
end)

Add({ "bwr", "btop" }, "Top times on a bonus (!bwr [number] [style])", function(ply, args)
	local n
	local rest = {}
	for _, a in ipairs(args) do
		if not n and tonumber(a) then n = tonumber(a) else rest[#rest + 1] = a end
	end
	n = n or SURF.Zones.Bonuses()[1] or 1
	local _, style = MapAndStyle(ply, rest)
	local key = SURF.MapKey(n, style)
	SURF.Menu.Open(ply, "records", { map = game.GetMap() .. " bonus " .. n .. SURF.Timer.StyleSuffix(style), rows = SURF.DB.Top(key, 50), total = SURF.DB.Count(key) })
end)

Add({ "pb" }, "Your best time and rank here", function(ply)
	local track = ply.SurfTrack or 0
	local key = SURF.MapKey(track, ply.SurfStyle)
	local pb = SURF.DB.GetRecord(key, ply:SteamID64())
	local where = (track > 0 and ("bonus " .. track) or game.GetMap()) .. SURF.Timer.StyleSuffix(ply.SurfStyle)
	if not pb then
		SURF.Chat(ply, acc, "[Timer] ", white, "You haven't finished " .. where .. " yet.")
		return
	end
	SURF.Chat(ply, acc, "[Timer] ", white, "Your best on " .. where .. ": ", acc, SURF.FormatTime(pb), white,
		" (rank " .. SURF.DB.RankOf(key, pb) .. "/" .. SURF.DB.Count(key) .. ")")
end)

Add({ "style", "styles" }, "Pick a style: !style sw|hsw|w|lg|n (own records each)", function(ply, args)
	local id = string.lower(args[1] or "")
	if id == "" then return SURF.Menu.Open(ply, "styles", { current = ply.SurfStyle or "n", styles = SURF.Config.Styles }) end
	if not SURF.Timer.ChangeStyle(ply, id) then
		local ids = {}
		for _, st in ipairs(SURF.Config.Styles) do ids[#ids + 1] = st.id .. " (" .. st.name .. ")" end
		SURF.Chat(ply, acc, "[Style] ", white, "Styles: " .. table.concat(ids, ", ") .. ".")
	end
end)

-- Shortcuts: !normal, !sw, !hsw, !wonly, !lg
for id, names in pairs({ n = { "normal", "n", "nm" }, sw = { "sw", "sideways" }, hsw = { "hsw", "halfsideways" }, w = { "wonly", "w-only" }, lg = { "lg", "lowgrav", "lowgravity" } }) do
	for _, name in ipairs(names) do
		C.list[name] = { names = names, help = "", fn = function(ply) SURF.Timer.ChangeStyle(ply, id) end }
	end
end

Add({ "mapinfo", "tier" }, "Tier, mapper, stages, record and your best on this map", function(ply)
	local map = game.GetMap()
	local tier, mapper = SURF.MapVote.Tier(map), SURF.MapVote.Mapper(map)
	local stages, bonuses = SURF.Zones.cpCount[0] or 0, SURF.Zones.Bonuses()
	local parts = { tier > 0 and ("Tier " .. tier) or "Tier unknown" }
	if mapper ~= "" then parts[#parts + 1] = "by " .. mapper end
	parts[#parts + 1] = stages > 0 and (stages .. " stages/checkpoints") or "linear"
	parts[#parts + 1] = #bonuses > 0 and (#bonuses .. (#bonuses == 1 and " bonus" or " bonuses")) or "no bonuses"
	SURF.Chat(ply, acc, "[Map] ", white, map .. ": " .. table.concat(parts, ", ") .. ".")
	local key = SURF.MapKey(0, ply.SurfStyle)
	local wr = SURF.DB.GetWR(key)
	local pb = SURF.DB.GetRecord(key, ply:SteamID64())
	local line = SURF.DB.Count(key) .. " finishers" .. SURF.Timer.StyleSuffix(ply.SurfStyle)
	if wr then line = line .. ", record " .. SURF.FormatTime(wr.time) .. " by " .. wr.name end
	line = line .. (pb and (", your best " .. SURF.FormatTime(pb) .. " (#" .. SURF.DB.RankOf(key, pb) .. ")") or ", you haven't finished it yet") .. "."
	SURF.Chat(ply, acc, "[Map] ", white, line)
end)

Add({ "rank", "points" }, "Your points, title and server rank", function(ply) SURF.Ranks.Describe(ply) end)

Add({ "top", "toplist", "leaderboard" }, "Best players on the server", function(ply)
	SURF.Menu.Open(ply, "players", { rows = SURF.Ranks.TopMenuData(50), total = #SURF.Ranks.list })
end)

Add({ "replay", "wrbot" }, "Watch the server record replay", function(ply) SURF.Replay.Spectate(ply) end)

Add({ "keys", "showkeys" }, "Show or hide the key display", function(ply) SURF.ClientAction(ply, "keys") end)

Add({ "spec", "spectate" }, "Spectate other players (again to return); !spec <name> watches that player", function(ply, args)
	if not args[1] then return SURF.Spec.Toggle(ply) end
	local t, err = SURF.Admin.FindPlayer(table.concat(args, " "))
	if not t then return SURF.Chat(ply, acc, "[Spec] ", white, err) end
	if t == ply or not t:Alive() or t:Team() == TEAM_SPECTATOR then return SURF.Chat(ply, acc, "[Spec] ", white, t:Nick() .. " isn't surfing right now.") end
	SURF.Spec.Watch(ply, t)
end)

Add({ "auto", "autohop" }, "Toggle holding jump to bunnyhop", function(ply)
	local on = not ply:GetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop)
	ply:SetNW2Bool("surf_autohop", on)
	SURF.Chat(ply, acc, "[Settings] ", white, "Autohop " .. (on and "enabled" or "disabled") .. ".")
end)

Add({ "hide", "show" }, "Hide or show other players", function(ply) SURF.ClientAction(ply, "hide") end)

Add({ "light", "maplight", "fullbright" }, "Light up the whole map for yourself (or press F)", function(ply) SURF.ClientAction(ply, "maplight") end)

Add({ "graphics", "gfx" }, "Color presets and glowing zones (!graphics vivid|cinematic|off)", function(ply, args)
	if args[1] then return SURF.ClientAction(ply, "graphics:" .. string.lower(args[1])) end
	SURF.Menu.Open(ply, "graphics")
end)

Add({ "zonefx" }, "Glowing zones on or off", function(ply) SURF.ClientAction(ply, "zonefx") end)

Add({ "trail", "trails" }, "Pick a trail", function(ply) SURF.Shop.OpenMenu(ply, "trail") end)

Add({ "rtv", "rockthevote" }, "Vote to change the map", function(ply) SURF.MapVote.RTV(ply) end)

Add({ "nominate", "nom" }, "Nominate a map for the next vote", function(ply, args) SURF.MapVote.Nominate(ply, args[1]) end)

Add({ "maps", "maplist" }, "List the maps on the server", function(ply)
	SURF.Menu.Open(ply, "maps", { maps = SURF.MapVote.Info(SURF.MapVote.Playable()) })
end)

Add({ "timeleft" }, "Time until the map vote", function(ply)
	local left = math.max(0, GetGlobal2Int("surf_mapend") - CurTime())
	SURF.Chat(ply, acc, "[Vote] ", white, string.format("%d:%02d left on this map.", math.floor(left / 60), math.floor(left % 60)))
end)

Add({ "vip", "store", "donate" }, "VIP perks, buying VIP with coins, and how to support the server", function(ply)
	SURF.Shop.OpenMenu(ply, "vip")
end)

Add({ "discord", "dc" }, "Join our Discord (live status, records, chat with the server)", function(ply)
	local url = SURF.DiscordURL()
	if not url then
		return SURF.Chat(ply, acc, "[Discord] ", white, "The Discord invite isn't set up yet.")
	end
	SURF.Chat(ply, Color(88, 101, 242), "[Discord] ", white, "Join us at ", acc, url, white,
		" (opening it in the Steam overlay). Then type /link there and !link <code> here to get your rank as a Discord role.")
	ply:SendLua("gui.OpenURL(" .. string.format("%q", url) .. ")")
end)

Add({ "link" }, "Link your Steam account to Discord (/link on Discord gives the code)", function(ply, args)
	SURF.DiscordBridge.Link(ply, args[1])
end)

Add({ "help", "commands", "cmds" }, "Show this list", function(ply) SURF.Menu.Open(ply, "help", { cmds = C.HelpList(ply:IsAdmin()) }) end)

-- Admin -----------------------------------------------------------------

Add({ "zone", "zones" }, "Place zones (!zone start|end|delete|reset|info)", function(ply, args) SURF.Zones.EditCommand(ply, args) end, true)

Add({ "deltime" }, "!deltime <steamid64> [style] removes a main-track time on this map", function(ply, args)
	if not args[1] then return SURF.Chat(ply, white, "Usage: !deltime <steamid64> [style]") end
	local style = SURF.StyleByID[string.lower(args[2] or "n")] and string.lower(args[2] or "n") or "n"
	SURF.DB.DeleteTime(SURF.MapKey(0, style), args[1])
	SURF.Chat(ply, acc, "[Admin] ", white, "Deleted the time for " .. args[1] .. SURF.Timer.StyleSuffix(style) .. ".")
end, true)

Add({ "hidemap" }, "!hidemap [map] takes a map out of votes and !maps (the next update also deletes it)", function(ply, args)
	local map = args[1] and SURF.MapVote.ResolveMap(args[1], SURF.MapVote.MapList()) or game.GetMap()
	if not map then return SURF.Chat(ply, acc, "[Admin] ", white, "No installed map matches \"" .. tostring(args[1]) .. "\".") end
	SURF.MapVote.SetHidden(map, true)
	SURF.Chat(ply, acc, "[Admin] ", white, map .. " is hidden from votes and !maps. !unhidemap " .. map .. " brings it back."
		.. (map == game.GetMap() and " !forcevote leaves it now." or ""))
end, true)

Add({ "unhidemap" }, "!unhidemap <map> puts a hidden map back", function(ply, args)
	local query = string.lower(args[1] or "")
	local hidden = SURF.MapVote.HiddenByAdmin()
	local map = hidden[query] and query or nil
	if not map then
		for m in pairs(hidden) do if string.find(m, query, 1, true) then map = m break end end
	end
	if not map or query == "" then
		local names = {}
		for m in pairs(hidden) do names[#names + 1] = m end
		table.sort(names)
		return SURF.Chat(ply, acc, "[Admin] ", white, #names > 0 and ("Hidden maps: " .. table.concat(names, ", ")) or "No maps are hidden.")
	end
	SURF.MapVote.SetHidden(map, false)
	SURF.Chat(ply, acc, "[Admin] ", white, map .. " is back in the rotation (the next update installs it again if it was deleted).")
end, true)

Add({ "forcevote" }, "Start a map vote now", function() if not SURF.MapVote.active then SURF.MapVote.Start(true) end end, true)

Add({ "map", "changelevel" }, "!map <name> switches to any installed map (also ones without zones)", function(ply, args)
	local map = SURF.MapVote.ResolveMap(args[1], SURF.MapVote.MapList())
	if not map then return SURF.Chat(ply, acc, "[Admin] ", white, "No installed map matches \"" .. tostring(args[1] or "") .. "\".") end
	SURF.Chat(nil, acc, "[Admin] ", white, ply:Nick() .. " is changing the map to ", acc, map, white, ".")
	timer.Simple(3, function()
		for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
		SURF.MapVote.MarkAdminMap(map) -- stays even without zones, to place them
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
