-- Daily and weekly challenges, the map of the day and visit streaks (!challenges).
--
--   Daily:   three challenges, the same for everyone, new every day (UTC), plus
--            "finish the map of the day". Doing all three pays a sweep bonus.
--   Weekly:  two bigger ones, new every Monday.
--   Streak:  coming back on consecutive days pays a growing bonus on top of
--            the shop's daily visit coins.
--   Map of the day: one playable map a day, always offered in the map vote.
--
-- Rewards are coins (SURF.Shop.Earn, so VIPs get their bonus). Nothing random
-- is sold or won: everyone gets the same challenges and the same rewards.
SURF.Challenges = {}
local Ch = SURF.Challenges
local Q = SURF.DB.Query
local acc, white = SURF.Config.Accent, color_white
local GOLD = Color(255, 200, 40)
local GREEN = Color(70, 210, 120)

util.AddNetworkString("surf.Challenge")

Q([[CREATE TABLE IF NOT EXISTS surf_challenges (
	steamid TEXT NOT NULL, period TEXT NOT NULL, cid TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
	done INTEGER NOT NULL DEFAULT 0, extra TEXT, PRIMARY KEY (steamid, period, cid))]])
Q([[CREATE TABLE IF NOT EXISTS surf_streak (
	steamid TEXT PRIMARY KEY, last_day INTEGER NOT NULL, streak INTEGER NOT NULL, best INTEGER NOT NULL)]])

-- kind: what counts. finish = any finished run, maps = different main maps,
-- pb = personal bests (a first finish counts), tier = main map of at least
-- that tier, bonus = a bonus run, style = a run on a style other than Normal,
-- play = minutes surfing (not AFK or spectating), speed = top speed in a
-- finished run, sync = sync in a finished run, record = a server record,
-- motd = the map of the day.
Ch.Daily = {
	{ id = "finish3", kind = "finish", goal = 3, coins = 60, text = "Finish 3 runs" },
	{ id = "finish6", kind = "finish", goal = 6, coins = 100, text = "Finish 6 runs" },
	{ id = "maps2", kind = "maps", goal = 2, coins = 90, text = "Finish 2 different maps" },
	{ id = "pb2", kind = "pb", goal = 2, coins = 80, text = "Set 2 personal bests" },
	{ id = "tier3", kind = "tier", tier = 3, goal = 1, coins = 120, text = "Finish a tier 3 or harder map" },
	{ id = "bonus1", kind = "bonus", goal = 1, coins = 70, text = "Finish a bonus (!b)" },
	{ id = "style1", kind = "style", goal = 1, coins = 80, text = "Finish a run on another style (!style)" },
	{ id = "play20", kind = "play", goal = 20, coins = 60, text = "Surf for 20 minutes" },
	{ id = "speed2000", kind = "speed", min = 2000, goal = 1, coins = 80, text = "Reach 2,000 u/s in a finished run" },
	{ id = "sync75", kind = "sync", min = 75, goal = 1, coins = 80, text = "Finish a run with 75% sync or better" },
}
Ch.Weekly = {
	{ id = "wmaps10", kind = "maps", goal = 10, coins = 500, text = "Finish 10 different maps" },
	{ id = "wpb10", kind = "pb", goal = 10, coins = 400, text = "Set 10 personal bests" },
	{ id = "wtier4", kind = "tier", tier = 4, goal = 2, coins = 600, text = "Finish a tier 4 or harder map twice" },
	{ id = "wplay180", kind = "play", goal = 180, coins = 500, text = "Surf for 3 hours" },
	{ id = "wrecord", kind = "record", goal = 1, coins = 500, text = "Set a server record (bonuses and styles count)" },
	{ id = "wfinish30", kind = "finish", goal = 30, coins = 400, text = "Finish 30 runs" },
}
Ch.MOTD = { id = "motd", kind = "motd", goal = 1, coins = 150 }
Ch.SweepCoins = 100 -- all three daily challenges done
Ch.DailyCount, Ch.WeeklyCount = 3, 2

-- Streak bonus: StreakPerDay per day in a row (from day 2), up to StreakMax
Ch.StreakPerDay, Ch.StreakMax = 10, 100

-- Days and weeks count in UTC; weeks start on Monday (day 0 was a Thursday)
function Ch.Day() return math.floor(os.time() / 86400) end
function Ch.Week() return math.floor((Ch.Day() + 3) / 7) end
function Ch.SecondsLeft(weekly)
	local now = os.time()
	if weekly then return (Ch.Week() + 1) * 7 * 86400 - 3 * 86400 - now end
	return (Ch.Day() + 1) * 86400 - now
end

-- Same picks for everyone: a small seeded generator (Park-Miller)
local function Seeded(seed)
	local s = seed % 2147483646 + 1
	return function(n)
		s = (s * 16807) % 2147483647
		return s % n + 1
	end
end

-- n challenges from a pool, no two of the same kind
local function Pick(pool, n, seed)
	local rnd, left, out, kinds = Seeded(seed), {}, {}, {}
	for i, c in ipairs(pool) do left[i] = c end
	while #out < n and #left > 0 do
		local c = table.remove(left, rnd(#left))
		if not kinds[c.kind] then
			kinds[c.kind] = true
			out[#out + 1] = c
		end
	end
	return out
end

local cache = {}
function Ch.Today()
	local day = Ch.Day()
	if cache.day ~= day then cache.day, cache.daily = day, Pick(Ch.Daily, Ch.DailyCount, day * 7919) end
	return cache.daily
end
function Ch.ThisWeek()
	local week = Ch.Week()
	if cache.week ~= week then cache.week, cache.weekly = week, Pick(Ch.Weekly, Ch.WeeklyCount, week * 104729 + 17) end
	return cache.weekly
end

-- Map of the day ---------------------------------------------------------------

local MOTD_FILE = "surfline/motd.txt"

-- Today's map (saved, so it stays put when maps are installed or hidden)
function Ch.MapOfTheDay()
	local day = Ch.Day()
	if cache.motdDay == day then return cache.motd end
	cache.motdDay, cache.motd = day, Ch.PickMapOfTheDay(day)
	return cache.motd
end

function Ch.PickMapOfTheDay(day)
	local playable = SURF.MapVote.Playable()
	local ok = {}
	for _, m in ipairs(playable) do ok[m] = true end
	local d, saved = string.match(file.Read(MOTD_FILE, "DATA") or "", "^(%d+)%s+(%S+)")
	if tonumber(d) == day and ok[saved] then return saved end
	-- Prefer maps most players can finish (tiers 1 to 4), then any
	local pool = {}
	for _, m in ipairs(playable) do
		local t = SURF.MapVote.Tier(m)
		if t >= 1 and t <= 4 then pool[#pool + 1] = m end
	end
	if #pool == 0 then pool = playable end
	if #pool == 0 then return nil end
	table.sort(pool)
	local pick = pool[Seeded(day * 31 + 7)(#pool)]
	file.CreateDir("surfline")
	file.Write(MOTD_FILE, day .. " " .. pick .. "\n")
	return pick
end

-- The map of the day is always one of the map vote's choices
local MV = SURF.MapVote
local origStart = MV.Start
function MV.Start(...)
	local motd = Ch.MapOfTheDay()
	local listed = false
	for _, m in pairs(MV.nominations) do
		if m == motd then listed = true end
	end
	if motd and motd ~= game.GetMap() and not listed then MV.nominations["motd"] = motd end
	local r = origStart(...)
	if MV.nominations["motd"] == motd then MV.nominations["motd"] = nil end
	return r
end

-- Progress ---------------------------------------------------------------------

-- Every challenge running right now: { def, period, weekly, motd }
function Ch.Active()
	local out, dayP, weekP = {}, "d" .. Ch.Day(), "w" .. Ch.Week()
	for _, c in ipairs(Ch.Today()) do out[#out + 1] = { def = c, period = dayP } end
	local motd = Ch.MapOfTheDay()
	if motd then out[#out + 1] = { def = Ch.MOTD, period = dayP, motd = motd } end
	for _, c in ipairs(Ch.ThisWeek()) do out[#out + 1] = { def = c, period = weekP, weekly = true } end
	return out
end

function Ch.Text(a)
	if a.motd then return "Finish the map of the day: " .. a.motd end
	return a.def.text
end

local function State(ply, period, cid)
	ply.SurfCh = ply.SurfCh or {}
	local k = period .. ":" .. cid
	local st = ply.SurfCh[k]
	if not st then
		local r = Q("SELECT progress, done, extra FROM surf_challenges WHERE steamid = %s AND period = %s AND cid = %s", ply:SteamID64(), period, cid)
		r = r and r[1]
		st = { progress = r and tonumber(r.progress) or 0, done = r and tonumber(r.done) == 1 or false, extra = {} }
		for m in string.gmatch(r and r.extra ~= "NULL" and r.extra or "", "[^,]+") do st.extra[m] = true end
		ply.SurfCh[k] = st
	end
	return st
end
Ch.State = State

local function Save(ply, period, cid, st)
	local extra = {}
	for m in pairs(st.extra) do extra[#extra + 1] = m end
	table.sort(extra)
	Q("REPLACE INTO surf_challenges (steamid, period, cid, progress, done, extra) VALUES (%s, %s, %s, %d, %d, %s)",
		ply:SteamID64(), period, cid, st.progress, st.done and 1 or 0, table.concat(extra, ","))
end

local function Toast(ply, text, col)
	net.Start("surf.Challenge")
	net.WriteString("toast")
	net.WriteTable({ text = text, col = col })
	net.Send(ply)
end
Ch.Toast = Toast

local function Complete(ply, a, st)
	st.done = true
	local coins = SURF.Shop.Earn(ply, a.def.coins, "challenge", true)
	local what = a.weekly and "Weekly challenge" or "Daily challenge"
	SURF.Chat(ply, GOLD, "[Challenges] ", white, what .. " done: ", acc, Ch.Text(a), white, ". ", GOLD, "+" .. coins .. " coins", white, ".")
	Toast(ply, what .. " done: +" .. coins .. " coins", GOLD)
	ply:SendLua([[surface.PlaySound("garrysmod/save_load1.wav")]])
	SURF.Achievements.Bump(ply, "challenges", 1)
	-- All the random dailies done: the sweep bonus, once a day
	if not a.weekly and not a.motd then
		for _, c in ipairs(Ch.Today()) do
			if not State(ply, a.period, c.id).done then return end
		end
		local sweep = State(ply, a.period, "sweep")
		if sweep.done then return end
		sweep.done, sweep.progress = true, 1
		Save(ply, a.period, "sweep", sweep)
		local bonus = SURF.Shop.Earn(ply, Ch.SweepCoins, "all daily challenges", true)
		SURF.Chat(nil, GOLD, "[Challenges] ", white, ply:Nick() .. " finished all of today's challenges! (", acc, "!challenges", white, ")")
		SURF.Chat(ply, GOLD, "[Challenges] ", white, "Daily sweep bonus: ", GOLD, "+" .. bonus .. " coins", white, ". New challenges tomorrow.")
	end
end

-- Something happened: kind as in the lists above. amount defaults to 1.
-- info: map (maps, motd), tier (tier), value (speed, sync)
function Ch.Progress(ply, kind, amount, info)
	if not IsValid(ply) or ply:IsBot() then return end
	info = info or {}
	for _, a in ipairs(Ch.Active()) do
		local d = a.def
		if d.kind == kind then
			local st = State(ply, a.period, d.id)
			local counts = not st.done
			if counts and kind == "tier" then counts = (info.tier or 0) >= d.tier end
			if counts and (kind == "speed" or kind == "sync") then counts = (info.value or 0) >= d.min end
			if counts and kind == "motd" then counts = info.map == a.motd end
			if counts and kind == "maps" then
				counts = info.map ~= nil and not st.extra[info.map]
				if counts then st.extra[info.map] = true end
			end
			if counts then
				st.progress = math.min(d.goal, st.progress + (amount or 1))
				if st.progress >= d.goal then
					Complete(ply, a, st)
				elseif kind ~= "play" then
					Toast(ply, Ch.Text(a) .. ": " .. st.progress .. "/" .. d.goal)
				end
				Save(ply, a.period, d.id, st)
			end
		end
	end
end

hook.Add("SurfFinish", "surf_challenges", function(ply, time, res, track, style)
	local map = game.GetMap()
	local P = Ch.Progress
	P(ply, "finish")
	if res.improved then P(ply, "pb") end
	if res.wr then P(ply, "record") end
	if track > 0 then P(ply, "bonus") end
	if style ~= "n" then P(ply, "style") end
	if track == 0 then
		P(ply, "maps", 1, { map = map })
		P(ply, "tier", 1, { tier = SURF.MapVote.Tier(map) })
		P(ply, "motd", 1, { map = map })
	end
	P(ply, "speed", 1, { value = ply:GetNW2Float("surf_fin_max", 0) })
	local sync = ply:GetNW2Float("surf_fin_sync", -1)
	if sync >= 0 then P(ply, "sync", 1, { value = sync }) end
end)

-- A minute of surfing (not spectating, not away)
timer.Create("surf_challenges_play", 60, 0, function()
	for _, p in ipairs(player.GetHumans()) do
		if p:Team() ~= TEAM_SPECTATOR and p:Alive() and SURF.AFK.IdleTime(p) < 60 then Ch.Progress(p, "play", 1) end
	end
end)

-- Streaks ------------------------------------------------------------------------

function Ch.Streak(sid)
	local r = Q("SELECT last_day, streak, best FROM surf_streak WHERE steamid = %s", sid)
	r = r and r[1]
	if not r then return 0, 0 end
	local streak = tonumber(r.streak) or 0
	-- A streak is alive until a whole day is missed
	if (tonumber(r.last_day) or 0) < Ch.Day() - 1 then streak = 0 end
	return streak, tonumber(r.best) or 0
end

-- First visit of the day continues (or starts) the streak and pays for it
function Ch.Visit(ply)
	local sid, today = ply:SteamID64(), Ch.Day()
	local r = Q("SELECT last_day, streak, best FROM surf_streak WHERE steamid = %s", sid)
	r = r and r[1]
	local last, streak, best = r and tonumber(r.last_day) or -1, r and tonumber(r.streak) or 0, r and tonumber(r.best) or 0
	if last == today then return streak, false end
	streak = (last == today - 1) and streak + 1 or 1
	best = math.max(best, streak)
	Q("REPLACE INTO surf_streak (steamid, last_day, streak, best) VALUES (%s, %d, %d, %d)", sid, today, streak, best)
	if streak >= 2 then
		local coins = SURF.Shop.Earn(ply, math.min(Ch.StreakMax, Ch.StreakPerDay * streak), "streak", true)
		local nextBonus = math.min(Ch.StreakMax, Ch.StreakPerDay * (streak + 1))
		SURF.Chat(ply, GOLD, "[Streak] ", white, streak .. " days in a row! ", GOLD, "+" .. coins .. " coins", white,
			". Come back tomorrow for " .. nextBonus .. ".")
	elseif last >= 0 and last < today - 1 then
		SURF.Chat(ply, GOLD, "[Streak] ", white, "Welcome back! Play on consecutive days for a growing coin bonus.")
	end
	return streak, true
end

-- Joining ------------------------------------------------------------------------

local function Countdown(sec)
	sec = math.max(0, sec)
	local h = math.floor(sec / 3600)
	if h >= 24 then return math.floor(h / 24) .. "d " .. (h % 24) .. "h" end
	return h .. "h " .. math.floor(sec % 3600 / 60) .. "m"
end
Ch.Countdown = Countdown

hook.Add("SurfPlayerReady", "surf_challenges", function(ply)
	ply.SurfCh = nil
	Ch.Visit(ply)
	local motd = Ch.MapOfTheDay()
	timer.Simple(4, function()
		if not IsValid(ply) then return end
		if motd == game.GetMap() then
			SURF.Chat(ply, GOLD, "[Daily] ", white, "This is the ", GOLD, "map of the day", white, "! Finish it today for " .. Ch.MOTD.coins .. " coins.")
		elseif motd then
			SURF.Chat(ply, GOLD, "[Daily] ", white, "Map of the day: ", acc, motd, white, " (" .. Ch.MOTD.coins .. " coins). It is always in the map vote.")
		end
		local left = 0
		for _, a in ipairs(Ch.Active()) do
			if not a.weekly and not a.motd and not State(ply, a.period, a.def.id).done then left = left + 1 end
		end
		if left > 0 then
			SURF.Chat(ply, GOLD, "[Daily] ", white, left .. " daily challenge" .. (left > 1 and "s" or "") .. " left today. Type ", acc, "!challenges", white, " to see them.")
		end
	end)
end)

-- Menu ----------------------------------------------------------------------------

function Ch.MenuData(ply)
	local list = {}
	for _, a in ipairs(Ch.Active()) do
		local st = State(ply, a.period, a.def.id)
		list[#list + 1] = {
			id = a.def.id, text = Ch.Text(a), goal = a.def.goal, progress = st.progress, done = st.done or nil,
			coins = a.def.coins, weekly = a.weekly or nil, motd = a.motd,
			unit = a.def.kind == "play" and "min" or nil,
		}
	end
	local streak, best = Ch.Streak(ply:SteamID64())
	local motd = Ch.MapOfTheDay()
	return {
		list = list, sweep = Ch.SweepCoins, swept = State(ply, "d" .. Ch.Day(), "sweep").done or nil,
		dayLeft = Ch.SecondsLeft(false), weekLeft = Ch.SecondsLeft(true),
		streak = streak, bestStreak = best, streakNext = math.min(Ch.StreakMax, Ch.StreakPerDay * (streak + 1)),
		motd = motd and { name = motd, tier = SURF.MapVote.Tier(motd), here = motd == game.GetMap() or nil } or nil,
	}
end

function Ch.Open(ply, tab)
	local data = Ch.MenuData(ply)
	data.ach = SURF.Achievements.MenuData(ply)
	data.tab = tab
	SURF.Menu.Open(ply, "challenges", data)
end

SURF.Commands.Add({ "challenges", "daily", "quests", "weekly" }, "Daily and weekly challenges, map of the day and your streak", function(ply)
	Ch.Open(ply, "today")
end)
SURF.Commands.Add({ "motd", "mapoftheday" }, "Show the map of the day", function(ply)
	local motd = Ch.MapOfTheDay()
	if not motd then
		SURF.Chat(ply, GOLD, "[Daily] ", white, "No map of the day yet.")
	elseif motd == game.GetMap() then
		SURF.Chat(ply, GOLD, "[Daily] ", white, "You're on it! Finish ", acc, motd, white, " today for " .. Ch.MOTD.coins .. " coins.")
	else
		SURF.Chat(ply, GOLD, "[Daily] ", white, "Map of the day: ", acc, motd, white, " (tier " .. SURF.MapVote.Tier(motd) .. "). Type ",
			acc, "!nominate " .. motd, white, " or wait for the vote, it is always a choice.")
	end
end)
SURF.Commands.Add({ "streak" }, "How many days in a row you've played", function(ply)
	local streak, best = Ch.Streak(ply:SteamID64())
	SURF.Chat(ply, GOLD, "[Streak] ", white, "Current streak: " .. streak .. " day" .. (streak == 1 and "" or "s") .. " (best " .. best .. "). Tomorrow's bonus: "
		.. math.min(Ch.StreakMax, Ch.StreakPerDay * (streak + 1)) .. " coins.")
end)
