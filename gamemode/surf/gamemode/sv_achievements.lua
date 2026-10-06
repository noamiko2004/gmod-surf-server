-- Achievements: permanent goals with a coin reward each (!achievements).
-- Most are counted from what is already saved (times, records, playtime), so
-- old players get theirs the first time they join after this update. The rest
-- use counters in surf_counters (finishes, top speed, best sync, challenges,
-- races won).
--
--   SURF.Achievements.Bump(ply, key, amount)   add to a counter, then check
--   SURF.Achievements.Max(ply, key, value)     keep the highest value, then check
--   SURF.Achievements.Check(ply)               unlock whatever is reached now
SURF.Achievements = {}
local Ach = SURF.Achievements
local Q = SURF.DB.Query
local acc, white = SURF.Config.Accent, color_white
local GOLD = Color(255, 200, 40)

Q([[CREATE TABLE IF NOT EXISTS surf_achievements (
	steamid TEXT NOT NULL, id TEXT NOT NULL, date INTEGER, PRIMARY KEY (steamid, id))]])
Q([[CREATE TABLE IF NOT EXISTS surf_counters (
	steamid TEXT NOT NULL, key TEXT NOT NULL, value REAL NOT NULL DEFAULT 0, PRIMARY KEY (steamid, key))]])

-- stat: what is measured (see Stats below), goal: the value to reach.
-- The ids are saved, don't rename them.
Ach.List = {
	{ id = "first", name = "First Wave", desc = "Finish any map", stat = "maps", goal = 1, coins = 50 },
	{ id = "maps5", name = "Getting Around", desc = "Finish 5 different maps", stat = "maps", goal = 5, coins = 100 },
	{ id = "maps25", name = "Explorer", desc = "Finish 25 different maps", stat = "maps", goal = 25, coins = 300 },
	{ id = "maps50", name = "Globetrotter", desc = "Finish 50 different maps", stat = "maps", goal = 50, coins = 600 },
	{ id = "maps100", name = "Completionist", desc = "Finish 100 different maps", stat = "maps", goal = 100, coins = 1500 },
	{ id = "tier3", name = "Stepping Up", desc = "Finish a tier 3 map", stat = "tier", goal = 3, coins = 100 },
	{ id = "tier4", name = "Hard Mode", desc = "Finish a tier 4 map", stat = "tier", goal = 4, coins = 250 },
	{ id = "tier5", name = "Unbreakable", desc = "Finish a tier 5 or harder map", stat = "tier", goal = 5, coins = 500 },
	{ id = "bonus1", name = "Bonus Round", desc = "Finish a bonus", stat = "bonuses", goal = 1, coins = 50 },
	{ id = "bonus10", name = "Bonus Hunter", desc = "Finish 10 different bonuses", stat = "bonuses", goal = 10, coins = 300 },
	{ id = "styles", name = "Stylish", desc = "Finish a map on every style", stat = "styles", goal = #SURF.Config.Styles, coins = 300 },
	{ id = "record1", name = "Record Breaker", desc = "Set a server record", stat = "recordsSet", goal = 1, coins = 200 },
	{ id = "record10", name = "Record Holder", desc = "Hold 10 server records at once", stat = "recordsHeld", goal = 10, coins = 700 },
	{ id = "runs100", name = "Grinder", desc = "Finish 100 runs", stat = "finishes", goal = 100, coins = 300 },
	{ id = "runs500", name = "No Life", desc = "Finish 500 runs", stat = "finishes", goal = 500, coins = 900 },
	{ id = "speed2500", name = "Speed Demon", desc = "Reach 2,500 u/s in a finished run", stat = "speed", goal = 2500, coins = 150 },
	{ id = "speed3400", name = "Sound Barrier", desc = "Reach 3,400 u/s in a finished run", stat = "speed", goal = 3400, coins = 350 },
	{ id = "sync90", name = "In Sync", desc = "Finish a run with 90% sync", stat = "sync", goal = 90, coins = 200 },
	{ id = "streak7", name = "Regular", desc = "Play 7 days in a row", stat = "streak", goal = 7, coins = 300 },
	{ id = "streak30", name = "Resident", desc = "Play 30 days in a row", stat = "streak", goal = 30, coins = 1500 },
	{ id = "hours10", name = "Dedicated", desc = "Play for 10 hours", stat = "hours", goal = 10, coins = 300 },
	{ id = "hours50", name = "Veteran", desc = "Play for 50 hours", stat = "hours", goal = 50, coins = 1000 },
	{ id = "chal10", name = "Challenger", desc = "Complete 10 challenges", stat = "challenges", goal = 10, coins = 200 },
	{ id = "chal50", name = "Taskmaster", desc = "Complete 50 challenges", stat = "challenges", goal = 50, coins = 700 },
	{ id = "race1", name = "Rival", desc = "Win a race (!race)", stat = "races", goal = 1, coins = 100 },
	{ id = "race10", name = "Fastest Alive", desc = "Win 10 races", stat = "races", goal = 10, coins = 500 },
}
Ach.ByID = {}
for _, a in ipairs(Ach.List) do Ach.ByID[a.id] = a end

-- Counters -------------------------------------------------------------------

function Ach.Counter(sid, key)
	local r = Q("SELECT value FROM surf_counters WHERE steamid = %s AND key = %s", sid, key)
	return r and r[1] and tonumber(r[1].value) or 0
end

local function SetCounter(sid, key, value)
	Q("REPLACE INTO surf_counters (steamid, key, value) VALUES (%s, %s, %s)", sid, key, string.format("%.2f", value))
end

function Ach.Bump(ply, key, amount)
	local sid = ply:SteamID64()
	SetCounter(sid, key, Ach.Counter(sid, key) + (amount or 1))
	Ach.Check(ply)
end

function Ach.Max(ply, key, value)
	local sid = ply:SteamID64()
	if (value or 0) <= Ach.Counter(sid, key) then return end
	SetCounter(sid, key, value)
	Ach.Check(ply)
end

-- Stats ----------------------------------------------------------------------

local function Count(sql, ...)
	local r = Q(sql, ...)
	return r and r[1] and tonumber(r[1].n) or 0
end

local function MainMaps(sid)
	local out = {}
	for _, r in ipairs(Q("SELECT map FROM surf_times WHERE steamid = %s", sid) or {}) do
		if not string.find(r.map, "[#@]") then out[#out + 1] = r.map end
	end
	return out
end

local Stats = {}
Ach.Stats = Stats
function Stats.maps(sid) return #MainMaps(sid) end
function Stats.tier(sid)
	local best = 0
	for _, m in ipairs(MainMaps(sid)) do best = math.max(best, SURF.MapVote.Tier(m)) end
	return best
end
function Stats.bonuses(sid)
	return Count("SELECT COUNT(*) AS n FROM surf_times WHERE steamid = %s AND map LIKE '%%#b%%' AND map NOT LIKE '%%@%%'", sid)
end
function Stats.styles(sid)
	local seen, n = {}, 0
	for _, r in ipairs(Q("SELECT map FROM surf_times WHERE steamid = %s", sid) or {}) do
		local st = string.match(r.map, "@(%w+)$") or "n"
		if not seen[st] and SURF.StyleByID[st] then seen[st], n = true, n + 1 end
	end
	return n
end
function Stats.recordsSet(sid) return Count("SELECT COUNT(*) AS n FROM surf_records WHERE steamid = %s", sid) end
function Stats.recordsHeld(sid)
	return Count("SELECT COUNT(*) AS n FROM surf_times t WHERE t.steamid = %s AND t.time = (SELECT MIN(time) FROM surf_times WHERE map = t.map)", sid)
end
function Stats.finishes(sid) return Ach.Counter(sid, "finishes") end
function Stats.speed(sid) return Ach.Counter(sid, "speed") end
function Stats.sync(sid) return Ach.Counter(sid, "sync") end
function Stats.challenges(sid) return Ach.Counter(sid, "challenges") end
function Stats.races(sid) return Ach.Counter(sid, "races") end
function Stats.streak(sid)
	local _, best = SURF.Challenges.Streak(sid)
	return best
end
function Stats.hours(sid)
	local r = Q("SELECT playtime FROM surf_players WHERE steamid = %s", sid)
	local sec = r and r[1] and tonumber(r[1].playtime) or 0
	local ply = player.GetBySteamID64(sid)
	if IsValid(ply) and ply.SurfJoinTime then sec = sec + os.time() - ply.SurfJoinTime end
	return math.floor(sec / 360) / 10
end

-- Every stat once (several achievements share one)
local function AllStats(sid)
	local vals = {}
	for _, a in ipairs(Ach.List) do
		if vals[a.stat] == nil then vals[a.stat] = Stats[a.stat](sid) end
	end
	return vals
end

-- Unlocking ---------------------------------------------------------------------

function Ach.Unlocked(sid)
	local out = {}
	for _, r in ipairs(Q("SELECT id, date FROM surf_achievements WHERE steamid = %s", sid) or {}) do
		out[r.id] = tonumber(r.date) or 0
	end
	return out
end

-- quiet: unlocked from what the player did before (on join), summed up in one
-- line instead of an announcement each
function Ach.Check(ply, quiet)
	if not IsValid(ply) or ply:IsBot() then return end
	local sid = ply:SteamID64()
	local have = Ach.Unlocked(sid)
	local vals, got, coins = nil, {}, 0
	for _, a in ipairs(Ach.List) do
		if not have[a.id] then
			vals = vals or AllStats(sid)
			if (vals[a.stat] or 0) >= a.goal then
				Q("INSERT OR IGNORE INTO surf_achievements (steamid, id, date) VALUES (%s, %s, %d)", sid, a.id, os.time())
				local earned = SURF.Shop.Earn(ply, a.coins, "achievement: " .. a.name, true)
				got[#got + 1] = { a = a, coins = earned }
				coins = coins + earned
			end
		end
	end
	if #got == 0 then return end
	ply:SetNW2Int("surf_ach", table.Count(have) + #got)
	if quiet then
		local names = {}
		for _, g in ipairs(got) do names[#names + 1] = g.a.name end
		SURF.Chat(ply, GOLD, "[Achievements] ", white, "Unlocked " .. #got .. " for what you've already done (" .. table.concat(names, ", ") .. "): ",
			GOLD, "+" .. coins .. " coins", white, ". See them all with ", acc, "!achievements", white, ".")
		SURF.Challenges.Toast(ply, #got .. " achievements unlocked: +" .. coins .. " coins", GOLD)
		return
	end
	for _, g in ipairs(got) do
		SURF.Chat(nil, GOLD, "[Achievement] ", team.GetColor(ply:Team()), ply:Nick(), white, " unlocked ", GOLD, g.a.name, white, " (" .. g.a.desc .. ").")
		SURF.Challenges.Toast(ply, "Achievement: " .. g.a.name .. " (+" .. g.coins .. " coins)", GOLD)
	end
	ply:SendLua([[surface.PlaySound("garrysmod/content_downloaded.wav")]])
end

hook.Add("SurfFinish", "surf_achievements", function(ply, time, res, track, style)
	local sid = ply:SteamID64()
	SetCounter(sid, "finishes", Ach.Counter(sid, "finishes") + 1)
	local max, sync = ply:GetNW2Float("surf_fin_max", 0), ply:GetNW2Float("surf_fin_sync", -1)
	if max > Ach.Counter(sid, "speed") then SetCounter(sid, "speed", max) end
	if sync > Ach.Counter(sid, "sync") then SetCounter(sid, "sync", sync) end
	Ach.Check(ply)
end)

hook.Add("SurfPlayerReady", "surf_achievements", function(ply)
	ply:SetNW2Int("surf_ach", table.Count(Ach.Unlocked(ply:SteamID64())))
	-- After the streak is counted and the welcome lines are out
	timer.Simple(6, function() if IsValid(ply) then Ach.Check(ply, true) end end)
end)

-- Playtime achievements are checked now and then
timer.Create("surf_achievements_hours", 600, 0, function()
	for _, p in ipairs(player.GetHumans()) do Ach.Check(p) end
end)

function Ach.MenuData(ply)
	local sid = ply:SteamID64()
	local have, vals, list = Ach.Unlocked(sid), AllStats(sid), {}
	for _, a in ipairs(Ach.List) do
		list[#list + 1] = { id = a.id, name = a.name, desc = a.desc, goal = a.goal, coins = a.coins,
			value = math.min(a.goal, vals[a.stat] or 0), date = have[a.id] }
	end
	return list
end

SURF.Commands.Add({ "achievements", "ach", "badges" }, "Your achievements and what they pay", function(ply)
	SURF.Challenges.Open(ply, "achievements")
end)
