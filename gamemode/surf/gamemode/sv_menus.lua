-- Data for the main menu's pages (cl_hub.lua, F1 or !menu). The client asks
-- for a page with surf.MenuReq (page, argument, request number) and gets it
-- back through surf.Menu with data.req set to that number, so a late answer
-- for a page the player already left is ignored.
util.AddNetworkString("surf.MenuReq")

local Pages = {}
SURF.Menu.Pages = Pages

local function Count(sql, ...)
	local r = SURF.DB.Query(sql, ...)
	return r and r[1] and tonumber(r[1].n) or 0
end

Pages.home = function(ply)
	local sid = ply:SteamID64()
	local r = SURF.Ranks.bySid[sid]
	local pts = r and r.points or 0
	local style = ply.SurfStyle or "n"
	local key = SURF.MapKey(0, style)
	local wr = SURF.DB.GetWR(key)
	local pb = SURF.DB.GetRecord(key, sid)
	local map = game.GetMap()
	local prow = SURF.DB.Query("SELECT playtime, firstseen FROM surf_players WHERE steamid = %s", sid)
	prow = prow and prow[1] or {}
	local coins = ply:GetNW2Int("surf_coins", 0)
	if SURF.Shop and SURF.Shop.Balance then coins = SURF.Shop.Balance(sid) end
	return {
		points = pts, rank = r and r.pos or 0, ranked = #SURF.Ranks.list, title = SURF.TitleFor(pts), coins = coins,
		vip = SURF.IsVIP(ply), vipExpires = ply.SurfVIPExpires,
		playtime = (tonumber(prow.playtime) or 0) + (ply.SurfJoinTime and (os.time() - ply.SurfJoinTime) or 0),
		firstseen = tonumber(prow.firstseen),
		finished = Count("SELECT COUNT(*) AS n FROM surf_times WHERE steamid = %s AND map NOT LIKE '%%#%%' AND map NOT LIKE '%%@%%'", sid),
		records = Count("SELECT COUNT(*) AS n FROM surf_times t WHERE t.steamid = %s AND t.time = (SELECT MIN(time) FROM surf_times WHERE map = t.map)", sid),
		map = {
			name = map, tier = SURF.MapVote.Tier(map), mapper = SURF.MapVote.Mapper(map), style = style,
			wr = wr and { time = wr.time, name = wr.name } or nil, pb = pb, pbRank = pb and SURF.DB.RankOf(key, pb) or nil,
			finishers = SURF.DB.Count(key), stages = SURF.Zones.cpCount[0] or 0, bonuses = #SURF.Zones.Bonuses(),
			zoned = SURF.Zones.HasTimer(0), timeleft = math.max(0, math.floor(GetGlobal2Int("surf_mapend") - CurTime())),
		},
		site = SURF.PortalURL(), discord = SURF.DiscordURL(),
	}
end

-- arg: "<style>|<track>", e.g. "sw|0" or "n|2"
Pages.records = function(ply, arg)
	local style, track = string.match(arg or "", "^(%w*)|?(%d*)$")
	style = SURF.StyleByID[style or ""] and style or (ply.SurfStyle or "n")
	track = tonumber(track or "") or 0
	if track > 0 and not SURF.Zones.HasTimer(track) then track = 0 end
	local key = SURF.MapKey(track, style)
	return {
		map = game.GetMap() .. (track > 0 and (" bonus " .. track) or "") .. SURF.Timer.StyleSuffix(style),
		rows = SURF.DB.Top(key, 100), total = SURF.DB.Count(key), style = style, track = track,
		bonuses = SURF.Zones.Bonuses(), here = true,
	}
end

Pages.players = function(ply)
	local rows = {}
	for i = 1, math.min(100, #SURF.Ranks.list) do
		local e = SURF.Ranks.list[i]
		rows[i] = { name = e.name, sid = e.sid, points = e.points, title = SURF.TitleFor(e.points) }
	end
	local me = SURF.Ranks.bySid[ply:SteamID64()]
	return { rows = rows, total = #SURF.Ranks.list, mine = me and { pos = me.pos, points = me.points } or nil }
end

Pages.maps = function(ply)
	local done = {}
	for _, r in ipairs(SURF.DB.Query("SELECT map FROM surf_times WHERE steamid = %s", ply:SteamID64()) or {}) do
		if not string.find(r.map, "[#@]") then done[r.map] = true end
	end
	local maps = SURF.MapVote.Info(SURF.MapVote.Playable())
	for _, m in ipairs(maps) do m.done = done[m.name] or nil end
	return { maps = maps, current = game.GetMap(), nominated = SURF.MapVote.nominations[ply:SteamID64()] }
end

-- One answer at a time per player: a burst of clicks gets the latest page
local function Answer(ply)
	local r = ply.SurfMenuPending
	ply.SurfMenuPending = nil
	if not r then return end
	ply.SurfMenuAt = CurTime()
	local ok, data = pcall(Pages[r.kind], ply, r.arg)
	if not ok then
		ErrorNoHalt("[Surf] menu page " .. r.kind .. ": " .. tostring(data) .. "\n")
		data = {}
	end
	data = data or {}
	data.req = r.req
	SURF.Menu.Open(ply, r.kind, data)
end

net.Receive("surf.MenuReq", function(_, ply)
	local kind, arg, req = net.ReadString(), string.sub(net.ReadString(), 1, 64), net.ReadUInt(16)
	if not Pages[kind] then return end
	ply.SurfMenuPending = { kind = kind, arg = arg, req = req }
	local wait = (ply.SurfMenuAt or -math.huge) + 0.2 - CurTime()
	if wait <= 0 then return Answer(ply) end
	if ply.SurfMenuTimer then return end
	ply.SurfMenuTimer = true
	timer.Simple(wait, function()
		if not IsValid(ply) then return end
		ply.SurfMenuTimer = nil
		Answer(ply)
	end)
end)

SURF.Commands.Add({ "menu" }, "Open the main menu (also F1)", function(ply) SURF.Menu.Open(ply, "menu", {}) end)
