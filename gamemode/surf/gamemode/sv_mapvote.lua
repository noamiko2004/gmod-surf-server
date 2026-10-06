-- Rock the vote, nominations and the end-of-map vote.
SURF.MapVote = { nominations = {}, votes = {}, active = false }
local MV = SURF.MapVote
local EXTEND = "__extend"

local mapStart = CurTime()
SetGlobal2Int("surf_mapend", math.floor(CurTime() + SURF.Config.MapTimeLimit))

function MV.MapList()
	local maps = {}
	local files = file.Find("maps/" .. SURF.Config.MapPrefix .. "*.bsp", "GAME")
	local seen = {}
	for _, f in ipairs(files or {}) do
		local name = string.StripExtension(f)
		if not seen[name] then
			seen[name] = true
			maps[#maps + 1] = name
		end
	end
	table.sort(maps)
	return maps
end

-- Tier (1 easy .. 6+ hard) and mapper per map, from zones/tiers.txt and zones/mappers.txt
local function ReadMapTable(path)
	local out = {}
	for line in string.gmatch(file.Read(path, "DATA") or "", "[^\n]+") do
		local name, rest = string.match(line, "^(surf_[%w_]+)%s+(.+)$")
		if name then out[name] = string.Trim(rest) end
	end
	return out
end
local tiers = ReadMapTable("surfline/tiers.txt")
local mappers = ReadMapTable("surfline/mappers.txt")

function MV.Tier(map) return tonumber(tiers[map] or "") or 0 end
function MV.Mapper(map) return mappers[map] or "" end

hook.Add("InitPostEntity", "surf_mapinfo", function()
	SetGlobal2Int("surf_tier", MV.Tier(game.GetMap()))
	SetGlobal2String("surf_mapper", MV.Mapper(game.GetMap()))
end)

-- A map has zones if an admin placed a start and an end, or it loaded with a
-- working start and end before, or it has ready-made zones and hasn't loaded
-- without a working start and end (bad_zones.txt, see sv_zones.lua).
function MV.HasZones(map, known, bad)
	local row = SURF.DB.Query("SELECT COUNT(DISTINCT ztype) AS n FROM surf_zones WHERE map = %s AND ztype IN ('start', 'end')", map)
	if row and tonumber(row[1].n) == 2 then return true end
	known = known or SURF.Zones.KnownZoned()
	if known[map] then return true end
	bad = bad or SURF.Zones.KnownBad()
	if bad[map] then return false end
	return file.Exists("surfline/zones/" .. map .. ".json", "DATA")
end

-- Maps kept out of votes, !maps and the map installer: maps/blocked_maps.txt
-- (deploy.sh copies it) and maps an admin hid in game with !hidemap
local HIDDEN_FILE = "surfline/hidden_maps.txt"
local function ReadNames(path)
	local out = {}
	for line in string.gmatch(file.Read(path, "DATA") or "", "[^\n]+") do
		local name = string.match(line, "^%s*(surf_[%w_]+)")
		if name then out[name] = true end
	end
	return out
end

function MV.Hidden()
	local out = ReadNames("surfline/blocked_maps.txt")
	for m in pairs(ReadNames(HIDDEN_FILE)) do out[m] = true end
	return out
end

function MV.HiddenByAdmin() return ReadNames(HIDDEN_FILE) end

function MV.SetHidden(map, hide)
	local list = ReadNames(HIDDEN_FILE)
	list[map] = hide and true or nil
	local names = {}
	for m in pairs(list) do names[#names + 1] = m end
	table.sort(names)
	file.Write(HIDDEN_FILE, #names > 0 and (table.concat(names, "\n") .. "\n") or "")
end

-- Maps players can vote for and nominate, and the only ones picked
-- automatically: never a map without a start and an end, never a hidden one.
-- Admins can still load any installed map with !map (to place zones).
function MV.Playable()
	local known, bad, hidden = SURF.Zones.KnownZoned(), SURF.Zones.KnownBad(), MV.Hidden()
	local zoned = {}
	for _, m in ipairs(MV.MapList()) do
		if not hidden[m] and MV.HasZones(m, known, bad) then zoned[#zoned + 1] = m end
	end
	return zoned
end

-- Map list with tiers, for menus and the portal
function MV.Info(list)
	local known, bad, hidden = SURF.Zones.KnownZoned(), SURF.Zones.KnownBad(), MV.Hidden()
	local out = {}
	for i, m in ipairs(list) do
		out[i] = { name = m, tier = MV.Tier(m), zoned = MV.HasZones(m, known, bad), hidden = hidden[m] or nil }
	end
	return out
end

local function VotePool()
	local maps = table.Copy(MV.Playable())
	table.Shuffle(maps)
	return maps
end

local function ResolveMap(query, list)
	query = string.lower(query or "")
	if query == "" then return nil end
	local partial
	for _, m in ipairs(list or MV.Playable()) do
		if m == query then return m end
		if not partial and string.find(m, query, 1, true) then partial = m end
	end
	return partial
end

MV.ResolveMap = ResolveMap

function MV.Nominate(ply, query)
	if MV.active then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "A vote is already running.") end
	local map = ResolveMap(query)
	if not map then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "No map matches \"" .. tostring(query) .. "\". Type !maps for the list.") end
	if map == game.GetMap() then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "That's the current map.") end
	MV.nominations[ply:SteamID64()] = map
	SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, ply:Nick() .. " nominated ", SURF.Config.Accent, map, color_white, ".")
end

local function RTVNeeded()
	-- AFK players don't count (sv_afk.lua)
	return math.max(1, math.ceil(#SURF.AFK.Active() * SURF.Config.RTVRatio))
end

local function RTVCount()
	local c = 0
	for _, p in ipairs(player.GetHumans()) do
		if p.SurfRTV then c = c + 1 end
	end
	return c
end

function MV.RTV(ply)
	if MV.active then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "A vote is already running.") end
	if CurTime() - mapStart < SURF.Config.RTVMinPlayTime then
		return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "Wait a minute after the map starts before rocking the vote.")
	end
	if ply.SurfRTV then
		return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "You already voted (" .. RTVCount() .. "/" .. RTVNeeded() .. ").")
	end
	ply.SurfRTV = true
	SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, ply:Nick() .. " wants to change the map (" .. RTVCount() .. "/" .. RTVNeeded() .. "). Type !rtv to agree.")
	MV.CheckRTV()
end

function MV.CheckRTV()
	if not MV.active and #player.GetHumans() > 0 and RTVCount() >= RTVNeeded() then
		MV.Start(false)
	end
end

function MV.OnDisconnect(ply)
	ply.SurfRTV = nil
	timer.Simple(0.5, MV.CheckRTV)
end

local function Broadcast()
	local tally = {}
	for _, choice in pairs(MV.votes) do tally[choice] = (tally[choice] or 0) + 1 end
	local choiceTiers = {}
	for i, c in ipairs(MV.choices or {}) do choiceTiers[i] = MV.Tier(c) end
	net.Start("surf.MapVote")
	net.WriteBool(MV.active)
	net.WriteTable(MV.choices or {})
	net.WriteTable(choiceTiers)
	net.WriteTable(tally)
	net.WriteFloat(MV.endTime or 0)
	net.Broadcast()
end

function MV.Start(allowExtend)
	MV.active = true
	MV.votes = {}
	local choices, used = {}, { [game.GetMap()] = true }
	local pool = VotePool()
	local playable = {}
	for _, map in ipairs(pool) do playable[map] = true end
	for _, map in pairs(MV.nominations) do
		-- (a nominated map may have been hidden since)
		if playable[map] and not used[map] and #choices < SURF.Config.MapVoteChoices then
			choices[#choices + 1] = map
			used[map] = true
		end
	end
	for _, map in ipairs(pool) do
		if #choices >= SURF.Config.MapVoteChoices then break end
		if not used[map] then
			choices[#choices + 1] = map
			used[map] = true
		end
	end
	if allowExtend then choices[#choices + 1] = EXTEND end
	if #choices == 0 or (#choices == 1 and choices[1] == EXTEND) then
		MV.active = false
		SetGlobal2Int("surf_mapend", math.floor(CurTime() + SURF.Config.MapExtendTime))
		return
	end
	MV.choices = choices
	MV.endTime = CurTime() + SURF.Config.MapVoteTime
	SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, "Map vote started! Press the number keys to vote.")
	Broadcast()
	timer.Create("surf_mapvote_end", SURF.Config.MapVoteTime, 1, MV.Finish)
end

function MV.Finish()
	local tally = {}
	for _, choice in pairs(MV.votes) do tally[choice] = (tally[choice] or 0) + 1 end
	local best, bestCount = nil, -1
	for _, choice in ipairs(MV.choices) do
		local c = tally[choice] or 0
		if c > bestCount or (c == bestCount and math.random() < 0.5) then best, bestCount = choice, c end
	end
	MV.active = false
	Broadcast()

	for _, p in ipairs(player.GetAll()) do p.SurfRTV = nil end
	if best == EXTEND then
		SetGlobal2Int("surf_mapend", math.floor(CurTime() + SURF.Config.MapExtendTime))
		SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, "The map was extended by " .. math.floor(SURF.Config.MapExtendTime / 60) .. " minutes.")
		return
	end
	SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, "Next map: ", SURF.Config.Accent, best, color_white, ". Changing in 5 seconds.")
	timer.Simple(5, function()
		for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
		RunConsoleCommand("changelevel", best)
	end)
end

net.Receive("surf.MapVoteCast", function(_, ply)
	local idx = net.ReadUInt(4)
	if not MV.active or not MV.choices[idx] then return end
	MV.votes[ply:SteamID64()] = MV.choices[idx]
	Broadcast()
end)

timer.Create("surf_maptime", 5, 0, function()
	if MV.active then return end
	if #player.GetHumans() == 0 then
		-- Empty server: the clock starts when someone joins
		SetGlobal2Int("surf_mapend", math.floor(CurTime() + SURF.Config.MapTimeLimit))
		return
	end
	if CurTime() >= GetGlobal2Int("surf_mapend") then MV.Start(true) end
end)

-- A map that turns out to have no working start and end when it loads
-- (bad_zones.txt then keeps it out of later votes) doesn't stay either: a
-- vote for the next map starts once someone is playing, without an extend
-- option. Not when an admin loaded it on purpose with !map, to place zones.
local ADMIN_MAP_FILE = "surfline/admin_map.txt"
function MV.MarkAdminMap(map) file.Write(ADMIN_MAP_FILE, map) end

hook.Add("InitPostEntity", "surf_nozones_leave", function()
	local map = game.GetMap()
	local byAdmin = string.Trim(file.Read(ADMIN_MAP_FILE, "DATA") or "") == map
	file.Delete(ADMIN_MAP_FILE)
	if byAdmin or not string.StartWith(map, SURF.Config.MapPrefix) then return end
	timer.Create("surf_nozones_leave", 15, 0, function()
		if SURF.Zones.HasTimer(0) then return timer.Remove("surf_nozones_leave") end
		if MV.active or #player.GetHumans() == 0 or CurTime() - mapStart < 30 then return end
		timer.Remove("surf_nozones_leave")
		SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, "This map has no working start and end zones, so let's pick another one.")
		MV.Start(false)
	end)
end)

-- If the server boots on a non-surf map (e.g. the gm_construct fallback while
-- workshop maps mount), hop to a random surf map once one is available.
hook.Add("InitPostEntity", "surf_bootmap", function()
	if string.StartWith(game.GetMap(), SURF.Config.MapPrefix) then return end
	timer.Simple(10, function()
		local maps = VotePool()
		if #maps == 0 then
			print("[Surf] No " .. SURF.Config.MapPrefix .. "* maps with zones found. Check maps.log on the server.")
			return
		end
		local pick = maps[1]
		print("[Surf] Not on a surf map, switching to " .. pick)
		RunConsoleCommand("changelevel", pick)
	end)
end)
