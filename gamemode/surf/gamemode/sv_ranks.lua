-- Points and titles. Every finished map is worth points: more for a better
-- rank, a bonus for holding the record, half for bonus tracks and half for
-- styles other than Normal (both halvings for a bonus on a style).
SURF.Ranks = { list = {}, bySid = {} }
local Ranks = SURF.Ranks

local function Points(pos, bonus, style)
	local p = 10 + math.max(0, 50 - (pos - 1) * 5) + (pos == 1 and 50 or 0)
	if bonus then p = math.floor(p / 2) end
	if style then p = math.floor(p / 2) end
	return p
end

function SURF.TitleFor(points)
	local idx = 1
	for i, t in ipairs(SURF.Config.Titles) do
		if points >= t.points then idx = i end
	end
	return idx
end

local function Apply(ply)
	if ply:IsBot() then return end
	local r = Ranks.bySid[ply:SteamID64()]
	local pts = r and r.points or 0
	ply:SetNW2Int("surf_points", pts)
	ply:SetNW2Int("surf_rankpos", r and r.pos or 0)
	local idx = SURF.TitleFor(pts)
	local old = ply.SurfTitleIdx
	ply.SurfTitleIdx = idx
	ply:SetNW2Int("surf_title", idx)
	if old and idx > old then hook.Run("SurfRankUp", ply, idx) end
end
Ranks.Apply = Apply

function Ranks.Recalc()
	local rows = SURF.DB.Query("SELECT map, steamid, name, time FROM surf_times ORDER BY map, time, date, steamid")
	local pts, names = {}, {}
	local curMap, pos = nil, 0
	for _, r in ipairs(rows or {}) do
		if r.map ~= curMap then curMap, pos = r.map, 0 end
		pos = pos + 1
		pts[r.steamid] = (pts[r.steamid] or 0) + Points(pos, string.find(r.map, "#b", 1, true) ~= nil, string.find(r.map, "@", 1, true) ~= nil)
		names[r.steamid] = r.name
	end
	-- Admin adjustments (the web portal adds them the same way)
	for _, r in ipairs(SURF.DB.Query("SELECT a.steamid, a.points, p.name FROM surf_points_adjust a LEFT JOIN surf_players p ON p.steamid = a.steamid") or {}) do
		local adj = tonumber(r.points) or 0
		if pts[r.steamid] or adj > 0 then
			pts[r.steamid] = math.max(0, (pts[r.steamid] or 0) + adj)
			if not names[r.steamid] then names[r.steamid] = (r.name and r.name ~= "NULL") and r.name or r.steamid end
		end
	end
	local list = {}
	for sid, p in pairs(pts) do list[#list + 1] = { sid = sid, name = names[sid], points = p } end
	table.sort(list, function(a, b)
		if a.points ~= b.points then return a.points > b.points end
		return a.sid < b.sid -- same order as the web portal
	end)
	Ranks.list, Ranks.bySid = list, {}
	for i, e in ipairs(list) do
		e.pos = i
		Ranks.bySid[e.sid] = e
	end
	for _, p in ipairs(player.GetHumans()) do Apply(p) end
end

hook.Add("InitPostEntity", "surf_ranks", Ranks.Recalc)

-- Points given or taken by an admin, on top of the points from times
SURF.DB.Query([[CREATE TABLE IF NOT EXISTS surf_points_adjust (
	steamid TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0, reason TEXT, date INTEGER)]])

function Ranks.Adjustment(sid)
	local r = SURF.DB.Query("SELECT points FROM surf_points_adjust WHERE steamid = %s", sid)
	return r and r[1] and tonumber(r[1].points) or 0
end

-- delta can be negative; returns the player's new total adjustment
function Ranks.AdjustPoints(sid, delta, reason)
	local total = math.Clamp(Ranks.Adjustment(sid) + math.floor(tonumber(delta) or 0), -10000000, 10000000)
	if total == 0 then
		SURF.DB.Query("DELETE FROM surf_points_adjust WHERE steamid = %s", sid)
	else
		SURF.DB.Query("REPLACE INTO surf_points_adjust (steamid, points, reason, date) VALUES (%s, %d, %s, %d)", sid, total, tostring(reason or ""), os.time())
	end
	Ranks.Recalc()
	return total
end

function Ranks.Describe(ply)
	local acc, white = SURF.Config.Accent, color_white
	local r = Ranks.bySid[ply:SteamID64()]
	local pts = r and r.points or 0
	local idx = SURF.TitleFor(pts)
	local title = SURF.Config.Titles[idx]
	local nextT = SURF.Config.Titles[idx + 1]
	local msg = r and string.format("You are #%d of %d with %d points. ", r.pos, #Ranks.list, pts) or "Finish any map to get ranked. "
	SURF.Chat(ply, acc, "[Rank] ", white, msg, title.color, title.name,
		white, nextT and string.format(" (next: %s at %d)", nextT.name, nextT.points) or "")
end

function Ranks.TopMenuData(limit)
	local out = {}
	for i = 1, math.min(limit or 50, #Ranks.list) do
		local e = Ranks.list[i]
		out[i] = { name = e.name, points = e.points, title = SURF.TitleFor(e.points) }
	end
	return out
end
