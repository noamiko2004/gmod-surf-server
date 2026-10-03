-- SQLite storage (garrysmod/sv.db). Back it up with scripts/backup.sh.
-- Times are keyed by "map" for the main track and "map#bN" for bonus N, plus
-- "@style" for styles other than Normal ("map@sw", "map#b1@lg").
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
		ErrorNoHalt("[Surf] SQL error: " .. tostring(sql.LastError()) .. "\n  in: " .. query .. "\n")
	end
	return res
end
SURF.DB.Query = q

local function HasColumn(tbl, col)
	for _, r in ipairs(sql.Query("PRAGMA table_info(" .. tbl .. ")") or {}) do
		if r.name == col then return true end
	end
	return false
end

local function Setup()
	q([[CREATE TABLE IF NOT EXISTS surf_times (
		map TEXT NOT NULL, steamid TEXT NOT NULL, name TEXT, time REAL NOT NULL,
		date INTEGER, completions INTEGER DEFAULT 1, PRIMARY KEY (map, steamid))]])
	q([[CREATE INDEX IF NOT EXISTS surf_times_map_time ON surf_times (map, time)]])
	if not HasColumn("surf_times", "splits") then
		q("ALTER TABLE surf_times ADD COLUMN splits TEXT")
	end
	-- Strafe stats of the run that set the time (NULL for older times)
	for _, col in ipairs({ "jumps INTEGER", "strafes INTEGER", "sync REAL", "avgspeed REAL", "maxspeed REAL" }) do
		if not HasColumn("surf_times", string.match(col, "^%S+")) then
			q("ALTER TABLE surf_times ADD COLUMN " .. col)
		end
	end
	q([[CREATE TABLE IF NOT EXISTS surf_zones (
		map TEXT NOT NULL, ztype TEXT NOT NULL,
		x1 REAL, y1 REAL, z1 REAL, x2 REAL, y2 REAL, z2 REAL, PRIMARY KEY (map, ztype))]])
	q([[CREATE TABLE IF NOT EXISTS surf_vip (steamid TEXT PRIMARY KEY, expires INTEGER NOT NULL)]])
	-- Every new server record, for the portal's "recent records"
	q([[CREATE TABLE IF NOT EXISTS surf_records (
		id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL, steamid TEXT NOT NULL, name TEXT,
		time REAL NOT NULL, prev_time REAL, prev_name TEXT, date INTEGER)]])
	q([[CREATE TABLE IF NOT EXISTS surf_bans (
		steamid TEXT PRIMARY KEY, name TEXT, reason TEXT, admin TEXT, created INTEGER, expires INTEGER)]])
	q([[CREATE TABLE IF NOT EXISTS surf_players (
		steamid TEXT PRIMARY KEY, name TEXT, trail TEXT, autohop INTEGER,
		playtime INTEGER DEFAULT 0, firstseen INTEGER, lastseen INTEGER)]])
	if not HasColumn("surf_players", "style") then
		q("ALTER TABLE surf_players ADD COLUMN style TEXT")
	end
end
Setup()

function SURF.MapKey(track, style)
	track = track or 0
	local key = game.GetMap() .. (track > 0 and ("#b" .. track) or "")
	if style and style ~= "n" then key = key .. "@" .. style end
	return key
end

-- Splits are stored as [[cp, seconds], ...] so JSON keeps the numbers intact
local function EncodeSplits(splits)
	local arr = {}
	for idx, t in pairs(splits or {}) do arr[#arr + 1] = { idx, t } end
	table.sort(arr, function(a, b) return a[1] < b[1] end)
	return util.TableToJSON(arr)
end

local function DecodeSplits(str)
	local out = {}
	if not str or str == "" or str == "NULL" then return out end
	for _, pair in ipairs(util.JSONToTable(str) or {}) do
		if pair[1] and pair[2] then out[tonumber(pair[1])] = tonumber(pair[2]) end
	end
	return out
end

-- Players ------------------------------------------------------------------

function SURF.DB.LoadPlayer(ply)
	local sid = ply:SteamID64()
	ply.SurfJoinTime = os.time()
	local row = q("SELECT * FROM surf_players WHERE steamid = %s", sid)
	ply.SurfFirstVisit = nil
	if row and row[1] then
		row = row[1]
		ply.SurfTrail = row.trail
		if row.autohop and row.autohop ~= "NULL" then
			ply:SetNW2Bool("surf_autohop", tonumber(row.autohop) == 1)
		end
		if SURF.StyleByID[row.style or ""] then
			ply.SurfStyle = row.style
			ply:SetNW2String("surf_style", row.style)
		end
		q("UPDATE surf_players SET name = %s, lastseen = %d WHERE steamid = %s", ply:Nick(), os.time(), sid)
	else
		ply:SetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop)
		q("INSERT INTO surf_players (steamid, name, firstseen, lastseen) VALUES (%s, %s, %d, %d)", sid, ply:Nick(), os.time(), os.time())
		ply.SurfFirstVisit = true
	end
	SURF.VIP.Load(ply)
	SURF.DB.RefreshPB(ply)
end

function SURF.DB.SavePlayer(ply)
	if not ply.SurfJoinTime or ply:IsBot() then return end
	local played = os.time() - ply.SurfJoinTime
	ply.SurfJoinTime = os.time()
	q("UPDATE surf_players SET name = %s, trail = %s, autohop = %d, style = %s, playtime = playtime + %d, lastseen = %d WHERE steamid = %s",
		ply:Nick(), ply.SurfTrail or "none", ply:GetNW2Bool("surf_autohop", true) and 1 or 0, ply.SurfStyle or "n", played, os.time(), ply:SteamID64())
end

-- Times --------------------------------------------------------------------

local wrCache = {}

function SURF.DB.GetWR(key)
	if wrCache[key] == nil then
		local row = q("SELECT name, time, splits FROM surf_times WHERE map = %s ORDER BY time ASC LIMIT 1", key)
		if row and row[1] then
			wrCache[key] = { time = tonumber(row[1].time), name = row[1].name or "?", splits = DecodeSplits(row[1].splits) }
		else
			wrCache[key] = false
		end
	end
	return wrCache[key] or nil
end

function SURF.DB.GetRecord(key, sid)
	local row = q("SELECT time, splits FROM surf_times WHERE map = %s AND steamid = %s", key, sid)
	if row and row[1] then
		return tonumber(row[1].time), DecodeSplits(row[1].splits)
	end
end

local function RefreshWR()
	wrCache = {}
	local wr = SURF.DB.GetWR(SURF.MapKey(0))
	SetGlobal2Float("surf_wr", wr and wr.time or 0)
	SetGlobal2String("surf_wr_name", wr and wr.name or "")
end
hook.Add("InitPostEntity", "surf_db_wr", RefreshWR)

-- Main-track PB, shown on the scoreboard
function SURF.DB.RefreshPB(ply)
	ply:SetNW2Float("surf_mainpb", SURF.DB.GetRecord(SURF.MapKey(0), ply:SteamID64()) or 0)
end

function SURF.DB.Count(key)
	local row = q("SELECT COUNT(*) AS c FROM surf_times WHERE map = %s", key)
	return row and tonumber(row[1].c) or 0
end

function SURF.DB.RankOf(key, time)
	local row = q("SELECT COUNT(*) AS c FROM surf_times WHERE map = %s AND time < %.6f", key, time)
	return (row and tonumber(row[1].c) or 0) + 1
end

-- SQL values for the strafe stats (numbers we format ourselves, or NULL)
local function StatsSQL(st)
	st = st or {}
	local function num(v, fmt) return v and string.format(fmt, v) or "NULL" end
	return num(st.jumps, "%d"), num(st.strafes, "%d"), num(st.sync, "%.2f"), num(st.avg, "%.1f"), num(st.max, "%.1f")
end

-- Returns { improved, oldPB, rank, total, wr, oldWR }
function SURF.DB.SubmitTime(ply, key, time, splits, stats)
	local sid = ply:SteamID64()
	local wr = SURF.DB.GetWR(key)
	local oldWR = wr and wr.time or 0
	local oldPB = SURF.DB.GetRecord(key, sid)
	local improved = false
	local j, s, sy, avg, mx = StatsSQL(stats)

	if not oldPB then
		q("INSERT INTO surf_times (map, steamid, name, time, date, splits, jumps, strafes, sync, avgspeed, maxspeed) VALUES (%s, %s, %s, %.6f, %d, %s, "
			.. j .. ", " .. s .. ", " .. sy .. ", " .. avg .. ", " .. mx .. ")",
			key, sid, ply:Nick(), time, os.time(), EncodeSplits(splits))
		improved = true
	elseif time < oldPB then
		q("UPDATE surf_times SET time = %.6f, name = %s, date = %d, splits = %s, completions = completions + 1, jumps = "
			.. j .. ", strafes = " .. s .. ", sync = " .. sy .. ", avgspeed = " .. avg .. ", maxspeed = " .. mx .. " WHERE map = %s AND steamid = %s",
			time, ply:Nick(), os.time(), EncodeSplits(splits), key, sid)
		improved = true
	else
		q("UPDATE surf_times SET completions = completions + 1, name = %s WHERE map = %s AND steamid = %s", ply:Nick(), key, sid)
	end

	local best = improved and time or oldPB
	local isWR = improved and (oldWR == 0 or time < oldWR)
	if isWR then
		q("INSERT INTO surf_records (map, steamid, name, time, prev_time, prev_name, date) VALUES (%s, %s, %s, %.6f, %.6f, %s, %d)",
			key, sid, ply:Nick(), time, oldWR, wr and wr.name or "", os.time())
		RefreshWR()
	end
	SURF.DB.RefreshPB(ply)
	return {
		improved = improved, oldPB = oldPB, rank = SURF.DB.RankOf(key, best),
		total = SURF.DB.Count(key), wr = isWR, oldWR = oldWR, oldName = wr and wr.name or nil,
	}
end

function SURF.DB.Top(key, limit)
	local rows = q("SELECT name, steamid, time, date, completions FROM surf_times WHERE map = %s ORDER BY time ASC LIMIT %d", key, limit or 10)
	local out = {}
	for i, r in ipairs(rows or {}) do
		out[i] = { name = r.name, steamid = r.steamid, time = tonumber(r.time), date = tonumber(r.date), completions = tonumber(r.completions) }
	end
	return out
end

function SURF.DB.DeleteTime(key, steamid)
	q("DELETE FROM surf_times WHERE map = %s AND steamid = %s", key, steamid)
	RefreshWR()
	for _, p in ipairs(player.GetHumans()) do
		SURF.DB.RefreshPB(p)
		SURF.Timer.SetTrack(p, p.SurfTrack or 0, true)
	end
	SURF.Ranks.Recalc()
end

-- Save playtime/settings periodically so a crash loses little
timer.Create("surf_db_autosave", 300, 0, function()
	for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
end)
hook.Add("ShutDown", "surf_db_save", function()
	for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
end)
