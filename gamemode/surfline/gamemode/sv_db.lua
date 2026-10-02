-- SQLite storage (garrysmod/sv.db). Back it up with scripts/backup.sh.
SURF.DB = {}

local function q(str, ...)
	local args = { ... }
	for i, v in ipairs(args) do
		if type(v) ~= "number" then
			args[i] = sql.SQLStr(tostring(v))
		end
	end
	local query = string.format(str, unpack(args))
	local res = sql.Query(query)
	if res == false then
		ErrorNoHalt("[Surfline] SQL error: " .. tostring(sql.LastError()) .. "\n  in: " .. query .. "\n")
	end
	return res
end
SURF.DB.Query = q

local function Setup()
	q([[CREATE TABLE IF NOT EXISTS surf_times (
		map TEXT NOT NULL, steamid TEXT NOT NULL, name TEXT, time REAL NOT NULL,
		date INTEGER, completions INTEGER DEFAULT 1, PRIMARY KEY (map, steamid))]])
	q([[CREATE INDEX IF NOT EXISTS surf_times_map_time ON surf_times (map, time)]])
	q([[CREATE TABLE IF NOT EXISTS surf_zones (
		map TEXT NOT NULL, ztype TEXT NOT NULL,
		x1 REAL, y1 REAL, z1 REAL, x2 REAL, y2 REAL, z2 REAL, PRIMARY KEY (map, ztype))]])
	q([[CREATE TABLE IF NOT EXISTS surf_vip (steamid TEXT PRIMARY KEY, expires INTEGER NOT NULL)]])
	q([[CREATE TABLE IF NOT EXISTS surf_players (
		steamid TEXT PRIMARY KEY, name TEXT, trail TEXT, autohop INTEGER,
		playtime INTEGER DEFAULT 0, firstseen INTEGER, lastseen INTEGER)]])
end
Setup()

-- Players ------------------------------------------------------------------

function SURF.DB.LoadPlayer(ply)
	local sid = ply:SteamID64()
	ply.SurfJoinTime = os.time()
	local row = q("SELECT * FROM surf_players WHERE steamid = %s", sid)
	if row and row[1] then
		row = row[1]
		ply.SurfTrail = row.trail
		if row.autohop and row.autohop ~= "NULL" then
			ply:SetNW2Bool("surf_autohop", tonumber(row.autohop) == 1)
		end
		q("UPDATE surf_players SET name = %s, lastseen = %d WHERE steamid = %s", ply:Nick(), os.time(), sid)
	else
		ply:SetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop)
		q("INSERT INTO surf_players (steamid, name, firstseen, lastseen) VALUES (%s, %s, %d, %d)", sid, ply:Nick(), os.time(), os.time())
	end
	SURF.VIP.Load(ply)
	SURF.DB.RefreshPB(ply)
end

function SURF.DB.SavePlayer(ply)
	if not ply.SurfJoinTime then return end
	local played = os.time() - ply.SurfJoinTime
	ply.SurfJoinTime = os.time()
	q("UPDATE surf_players SET name = %s, trail = %s, autohop = %d, playtime = playtime + %d, lastseen = %d WHERE steamid = %s",
		ply:Nick(), ply.SurfTrail or "none", ply:GetNW2Bool("surf_autohop", true) and 1 or 0, played, os.time(), ply:SteamID64())
end

-- Times --------------------------------------------------------------------

local function RefreshWR()
	local row = q("SELECT name, time FROM surf_times WHERE map = %s ORDER BY time ASC LIMIT 1", game.GetMap())
	if row and row[1] then
		SetGlobal2Float("surf_wr", tonumber(row[1].time))
		SetGlobal2String("surf_wr_name", row[1].name or "?")
	else
		SetGlobal2Float("surf_wr", 0)
		SetGlobal2String("surf_wr_name", "")
	end
end
hook.Add("InitPostEntity", "surf_db_wr", RefreshWR)

function SURF.DB.RefreshPB(ply)
	local row = q("SELECT time FROM surf_times WHERE map = %s AND steamid = %s", game.GetMap(), ply:SteamID64())
	ply:SetNW2Float("surf_pb", (row and row[1]) and tonumber(row[1].time) or 0)
end

function SURF.DB.Count(map)
	local row = q("SELECT COUNT(*) AS c FROM surf_times WHERE map = %s", map)
	return row and tonumber(row[1].c) or 0
end

function SURF.DB.RankOf(map, time)
	local row = q("SELECT COUNT(*) AS c FROM surf_times WHERE map = %s AND time < %.6f", map, time)
	return (row and tonumber(row[1].c) or 0) + 1
end

-- Returns { improved, oldPB, rank, total, wr, oldWR }
function SURF.DB.SubmitTime(ply, time)
	local map, sid = game.GetMap(), ply:SteamID64()
	local oldWR = GetGlobal2Float("surf_wr", 0)
	local row = q("SELECT time FROM surf_times WHERE map = %s AND steamid = %s", map, sid)
	local oldPB = (row and row[1]) and tonumber(row[1].time) or nil
	local improved = false

	if not oldPB then
		q("INSERT INTO surf_times (map, steamid, name, time, date) VALUES (%s, %s, %s, %.6f, %d)", map, sid, ply:Nick(), time, os.time())
		improved = true
	elseif time < oldPB then
		q("UPDATE surf_times SET time = %.6f, name = %s, date = %d, completions = completions + 1 WHERE map = %s AND steamid = %s",
			time, ply:Nick(), os.time(), map, sid)
		improved = true
	else
		q("UPDATE surf_times SET completions = completions + 1, name = %s WHERE map = %s AND steamid = %s", ply:Nick(), map, sid)
	end

	SURF.DB.RefreshPB(ply)
	local best = improved and time or oldPB
	local isWR = improved and (oldWR == 0 or time < oldWR)
	if isWR then RefreshWR() end
	return {
		improved = improved, oldPB = oldPB, rank = SURF.DB.RankOf(map, best),
		total = SURF.DB.Count(map), wr = isWR, oldWR = oldWR,
	}
end

function SURF.DB.Top(map, limit)
	local rows = q("SELECT name, steamid, time, date, completions FROM surf_times WHERE map = %s ORDER BY time ASC LIMIT %d", map, limit or 10)
	local out = {}
	for i, r in ipairs(rows or {}) do
		out[i] = { name = r.name, steamid = r.steamid, time = tonumber(r.time), date = tonumber(r.date), completions = tonumber(r.completions) }
	end
	return out
end

function SURF.DB.DeleteTime(map, steamid)
	q("DELETE FROM surf_times WHERE map = %s AND steamid = %s", map, steamid)
	RefreshWR()
	for _, p in ipairs(player.GetAll()) do SURF.DB.RefreshPB(p) end
end

-- Save playtime/settings periodically so a crash loses little
timer.Create("surf_db_autosave", 300, 0, function()
	for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
end)
hook.Add("ShutDown", "surf_db_save", function()
	for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
end)
