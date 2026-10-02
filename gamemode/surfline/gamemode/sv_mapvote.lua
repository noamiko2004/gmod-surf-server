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

local function ResolveMap(query)
	query = string.lower(query or "")
	if query == "" then return nil end
	local partial
	for _, m in ipairs(MV.MapList()) do
		if m == query then return m end
		if not partial and string.find(m, query, 1, true) then partial = m end
	end
	return partial
end

function MV.Nominate(ply, query)
	if MV.active then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "A vote is already running.") end
	local map = ResolveMap(query)
	if not map then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "No map matches \"" .. tostring(query) .. "\". Type !maps for the list.") end
	if map == game.GetMap() then return SURF.Chat(ply, SURF.Config.Accent, "[Vote] ", color_white, "That's the current map.") end
	MV.nominations[ply:SteamID64()] = map
	SURF.Chat(nil, SURF.Config.Accent, "[Vote] ", color_white, ply:Nick() .. " nominated ", SURF.Config.Accent, map, color_white, ".")
end

local function RTVNeeded()
	return math.max(1, math.ceil(#player.GetHumans() * SURF.Config.RTVRatio))
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
	net.Start("surf.MapVote")
	net.WriteBool(MV.active)
	net.WriteTable(MV.choices or {})
	net.WriteTable(tally)
	net.WriteFloat(MV.endTime or 0)
	net.Broadcast()
end

function MV.Start(allowExtend)
	MV.active = true
	MV.votes = {}
	local choices, used = {}, { [game.GetMap()] = true }
	for _, map in pairs(MV.nominations) do
		if not used[map] and #choices < SURF.Config.MapVoteChoices then
			choices[#choices + 1] = map
			used[map] = true
		end
	end
	local pool = MV.MapList()
	table.Shuffle(pool)
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

-- If the server boots on a non-surf map (e.g. the gm_construct fallback while
-- workshop maps mount), hop to a random surf map once one is available.
hook.Add("InitPostEntity", "surf_bootmap", function()
	if string.StartWith(game.GetMap(), SURF.Config.MapPrefix) then return end
	timer.Simple(10, function()
		local maps = MV.MapList()
		if #maps == 0 then
			print("[Surfline] No " .. SURF.Config.MapPrefix .. "* maps found. Check WORKSHOP_COLLECTION in config.env.")
			return
		end
		local pick = maps[math.random(#maps)]
		print("[Surfline] Not on a surf map, switching to " .. pick)
		RunConsoleCommand("changelevel", pick)
	end)
end)
