-- 1v1 races (!race <player>): both go to the start, a countdown (3, 5 or 10
-- seconds, the challenger's pick) holds them there, and the first to finish
-- the map wins. The winner gets a few coins (a handful of paid wins a day, so
-- friends can't farm it) and a step towards the race achievements. Nothing is
-- bet.
--
-- Racing the record (!race wr): the server record replay is sent to the
-- player and drawn as a gold ghost that starts with each of their runs
-- (cl_challenges.lua), so they race it side by side.
--
-- !race alone opens the race menu: players to challenge, the record ghost and
-- the race settings.
SURF.Race = { invites = {}, list = {} }
local Race = SURF.Race
local acc, white = SURF.Config.Accent, color_white
local GOLD = Color(255, 200, 40)
local TAG = Color(255, 120, 60)

Race.InviteTime = 30 -- seconds to !accept
Race.Countdown = 3
Race.Countdowns = { [3] = true, [5] = true, [10] = true } -- what the challenger may pick
Race.TimeLimit = 15 * 60 -- a race nobody finishes ends as a draw
Race.WinCoins = 30
Race.PaidPerDay = 5 -- wins a day that pay coins

local function Say(ply, ...) SURF.Chat(ply, TAG, "[Race] ", white, ...) end

local function Send(ply, data)
	net.Start("surf.Challenge")
	net.WriteString("race")
	net.WriteTable(data)
	net.Send(ply)
end

util.AddNetworkString("surf.Ghost")

local function Other(r, ply) return r.a == ply and r.b or r.a end

local function CanRace(ply)
	if not IsValid(ply) then return false, "that player left" end
	if ply.SurfRace then return false, ply:Nick() .. " is already in a race" end
	if ply:Team() == TEAM_SPECTATOR then return false, ply:Nick() .. " is spectating" end
	return true
end

function Race.End(r, text)
	if r.over then return end
	r.over = true
	for i, x in ipairs(Race.list) do
		if x == r then table.remove(Race.list, i) break end
	end
	for _, p in ipairs({ r.a, r.b }) do
		if IsValid(p) then
			p.SurfRace = nil
			p:SetNW2Bool("surf_racing", false)
			if p.Freeze then p:Freeze(false) end
			Send(p, { stop = true })
		end
	end
	if text then SURF.Chat(nil, TAG, "[Race] ", white, text) end
end

local function Win(r, winner, time)
	local loser = Other(r, winner)
	local lname = IsValid(loser) and loser:Nick() or "their rival"
	Race.End(r)
	SURF.Chat(nil, TAG, "[Race] ", team.GetColor(winner:Team()), winner:Nick(), white, " beat " .. lname .. " on " .. game.GetMap() .. " in ", acc, SURF.FormatTime(time), white, "!")
	-- Coins for the first few wins of the day
	local Ach = SURF.Achievements
	local sid, day = winner:SteamID64(), SURF.Challenges.Day()
	local paid = Ach.Counter(sid, "race_day") == day and Ach.Counter(sid, "race_paid") or 0
	if paid < Race.PaidPerDay then
		SURF.DB.Query("REPLACE INTO surf_counters (steamid, key, value) VALUES (%s, 'race_day', %d)", sid, day)
		SURF.DB.Query("REPLACE INTO surf_counters (steamid, key, value) VALUES (%s, 'race_paid', %d)", sid, paid + 1)
		local coins = SURF.Shop.Earn(winner, Race.WinCoins, "race win", true)
		Say(winner, "You won! ", GOLD, "+" .. coins .. " coins", white, ".")
	end
	SURF.Challenges.Toast(winner, "You won the race!", GOLD)
	if IsValid(loser) then SURF.Challenges.Toast(loser, winner:Nick() .. " won the race", Color(240, 80, 80)) end
	winner:SendLua([[surface.PlaySound("garrysmod/save_load4.wav")]])
	Ach.Bump(winner, "races", 1)
end

function Race.Start(a, b, countdown)
	countdown = Race.Countdowns[countdown or 0] and countdown or Race.Countdown
	local r = { a = a, b = b, created = CurTime(), countdown = countdown }
	Race.list[#Race.list + 1] = r
	a.SurfRace, b.SurfRace = r, r
	for _, p in ipairs({ a, b }) do
		p:SetNW2Bool("surf_racing", true)
		SURF.Timer.GoToStart(p, 0)
		if p.Freeze then p:Freeze(true) end
		Send(p, { count = countdown, vs = Other(r, p):Nick(), vsSid = Other(r, p):SteamID64() })
	end
	SURF.Chat(nil, TAG, "[Race] ", white, a:Nick() .. " and " .. b:Nick() .. " are racing on this map! Watch with ", acc, "!spec " .. a:Nick(), white, ".")
	timer.Simple(countdown, function()
		if r.over then return end
		if not IsValid(r.a) or not IsValid(r.b) then return Race.End(r, "The race was called off (a racer left).") end
		r.go = CurTime()
		for _, p in ipairs({ r.a, r.b }) do
			-- They're still in the start zone, so the timer starts as they leave it
			if p.Freeze then p:Freeze(false) end
			SURF.Timer.GoToStart(p, 0)
			Send(p, { go = true, vs = Other(r, p):Nick(), vsSid = Other(r, p):SteamID64() })
		end
	end)
	return r
end

hook.Add("SurfFinish", "surf_race", function(ply, time, res, track, style)
	local r = ply.SurfRace
	if not r or r.over or not r.go or track ~= 0 then return end
	-- Only a run started after the "go"
	if ply:GetNW2Float("surf_start", 0) + 0.001 < r.go then return end
	Win(r, ply, time)
end)

hook.Add("PlayerDisconnected", "surf_race", function(ply)
	Race.invites[ply:SteamID64()] = nil
	if ply.SurfRace then Race.End(ply.SurfRace, ply:Nick() .. " left, so the race is off.") end
end)

-- Spectating ends the race; so does running out of time
timer.Create("surf_race_watch", 1, 0, function()
	for i = #Race.list, 1, -1 do
		local r = Race.list[i]
		if r then
			for _, p in ipairs({ r.a, r.b }) do
				if not r.over and (not IsValid(p) or p:Team() == TEAM_SPECTATOR) then
					local name = IsValid(p) and p:Nick() or "A racer"
					local other = Other(r, p)
					Race.End(r, name .. " gave up" .. (IsValid(other) and (", " .. other:Nick() .. " wins") or "") .. ".")
				end
			end
			if not r.over and CurTime() - r.created > Race.TimeLimit then Race.End(r, "Nobody finished in time, the race is a draw.") end
		end
	end
end)

-- The record ghost ---------------------------------------------------------------

Race.GhostStep = 4 -- replay ticks per ghost point (the client blends between them)
local ghost -- { key, chunks, time, name, step }

-- The record replay as compressed "x,y,z,yaw;..." chunks small enough for net
function Race.GhostData()
	local R = SURF.Replay
	if not R.frames or not R.info or (R.n or 0) < 2 then return nil end
	local key = string.format("%s:%.3f:%d", game.GetMap(), R.info.time, R.n)
	if ghost and ghost.key == key then return ghost end
	local pts, f = {}, R.frames
	for i = 1, R.n, Race.GhostStep do
		local b = (i - 1) * 5
		pts[#pts + 1] = string.format("%.1f,%.1f,%.1f,%.0f", f[b + 1], f[b + 2], f[b + 3], f[b + 5])
	end
	local data = util.Compress(table.concat(pts, ";")) or ""
	local chunks = {}
	for i = 1, #data, 60000 do chunks[#chunks + 1] = string.sub(data, i, i + 59999) end
	ghost = { key = key, chunks = chunks, time = R.info.time, name = R.info.name, step = engine.TickInterval() * Race.GhostStep }
	return ghost
end

-- Sends the ghost (or tells the client to drop it when there is none or it's off)
function Race.SendGhost(ply)
	local g = ply.SurfGhost and Race.GhostData()
	if not g then
		net.Start("surf.Ghost")
		net.WriteString("")
		net.WriteUInt(0, 8)
		net.WriteUInt(0, 8)
		net.Send(ply)
		return
	end
	for i, c in ipairs(g.chunks) do
		net.Start("surf.Ghost")
		net.WriteString(g.key)
		net.WriteUInt(i, 8)
		net.WriteUInt(#g.chunks, 8)
		net.WriteFloat(g.time)
		net.WriteString(g.name)
		net.WriteFloat(g.step)
		net.WriteUInt(#c, 32)
		net.WriteData(c, #c)
		net.Send(ply)
	end
end

function Race.SetGhost(ply, on, quiet)
	if on and not Race.GhostData() then
		if not quiet then Say(ply, "There is no record replay on this map yet, so there's no ghost to race. Set the record!") end
		on = false
	end
	ply.SurfGhost = on or nil
	Race.SendGhost(ply)
	Send(ply, { ghostOn = on and true or false })
	if quiet then return end
	if on then
		local R = SURF.Replay
		Say(ply, "Racing the record: a gold ghost of ", GOLD, R.info.name, white, " (" .. SURF.FormatTime(R.info.time) .. ") runs with you every time you start on Normal. ",
			acc, "!race wr", white, " again turns it off.")
	else
		Say(ply, "Record ghost off.")
	end
end

-- A new record means a new ghost for everyone racing it
hook.Add("SurfNewRecord", "surf_race_ghost", function(ply, time, res, track, style)
	if track ~= 0 or style ~= "n" then return end
	for _, p in ipairs(player.GetHumans()) do
		if p.SurfGhost then Race.SendGhost(p) end
	end
end)

-- The ghost setting is kept on the player's computer (surf_race_ghost)
hook.Add("SurfPlayerReady", "surf_race_ghost", function(ply)
	if tonumber(ply:GetInfo("surf_race_ghost")) == 1 then
		timer.Simple(8, function() if IsValid(ply) then Race.SetGhost(ply, true, true) end end)
	end
end)

-- After a run with the ghost on: how it went against the record
hook.Add("SurfFinish", "surf_race_ghost", function(ply, time, res, track, style)
	if not ply.SurfGhost or track ~= 0 or style ~= "n" or res.wr then return end
	local R = SURF.Replay
	if not R.info then return end
	local d = time - R.info.time
	SURF.Challenges.Toast(ply, string.format("The record ghost was %.3f s faster", d), Color(255, 200, 40))
end)

-- The menu ---------------------------------------------------------------------

local function Countdown(ply)
	local n = math.floor(tonumber(ply:GetInfo("surf_race_countdown")) or Race.Countdown)
	return Race.Countdowns[n] and n or Race.Countdown
end

function Race.MenuData(ply)
	local players = {}
	for _, p in ipairs(player.GetHumans()) do
		if p ~= ply then
			players[#players + 1] = { name = p:Nick(), sid = p:SteamID64(),
				state = p.SurfRace and "racing" or (p:Team() == TEAM_SPECTATOR and "spectating" or nil) }
		end
	end
	table.sort(players, function(a, b) return string.lower(a.name) < string.lower(b.name) end)
	local inv = Race.invites[ply:SteamID64()]
	local R = SURF.Replay
	return {
		players = players, ghost = ply.SurfGhost or nil, zoned = SURF.Zones.HasTimer(0) or nil,
		wr = R.info and R.frames and { time = R.info.time, name = R.info.name } or nil,
		invite = inv and IsValid(inv.from) and CurTime() - inv.at <= Race.InviteTime and inv.from:Nick() or nil,
		vs = ply.SurfRace and IsValid(Other(ply.SurfRace, ply)) and Other(ply.SurfRace, ply):Nick() or nil,
		countdown = Countdown(ply), map = game.GetMap(),
	}
end

function Race.OpenMenu(ply) SURF.Menu.Open(ply, "race", Race.MenuData(ply)) end

SURF.Commands.Add({ "race" }, "!race opens the race menu; !race <player> challenges someone, !race wr races the record ghost", function(ply, args)
	if #args == 0 then return Race.OpenMenu(ply) end
	local what = string.lower(args[1])
	if what == "wr" or what == "ghost" or what == "record" then
		local on = not ply.SurfGhost
		if args[2] == "on" then on = true elseif args[2] == "off" then on = false end
		return Race.SetGhost(ply, on)
	end
	if not SURF.Zones.HasTimer(0) then return Say(ply, "This map has no start and end to race on.") end
	local t, err = SURF.Admin.FindPlayer(table.concat(args, " "))
	if not t then return Say(ply, "Couldn't find that player: " .. err .. ".") end
	if t == ply then return Say(ply, "You can't race yourself. Try the record ghost with !race wr.") end
	local ok, why = CanRace(ply)
	if ok then ok, why = CanRace(t) end
	if not ok then return Say(ply, "Can't race now: " .. why .. ".") end
	if (ply.SurfRaceAsked or 0) > CurTime() then return Say(ply, "Wait a few seconds before asking again.") end
	ply.SurfRaceAsked = CurTime() + 10
	local countdown = Countdown(ply)
	Race.invites[t:SteamID64()] = { from = ply, at = CurTime(), countdown = countdown }
	local st = SURF.StyleOf(ply)
	Say(t, ply:Nick() .. " challenges you to a race to the end of " .. game.GetMap() .. (st.id ~= "n" and (" (they're on " .. st.name .. ")") or "") .. "! Type ",
		acc, "!accept", white, " within " .. Race.InviteTime .. " seconds, or ", acc, "!decline", white, ".")
	SURF.Challenges.Toast(t, ply:Nick() .. " wants to race! Type !accept or open !race", TAG)
	Send(t, { invite = ply:Nick() })
	t:SendLua([[surface.PlaySound("buttons/button17.wav")]])
	Say(ply, "Race request sent to " .. t:Nick() .. (countdown ~= Race.Countdown and (" (" .. countdown .. " second countdown)") or "") .. ".")
end)

SURF.Commands.Add({ "ghost" }, "Race the server record's ghost (same as !race wr)", function(ply, args)
	local on = not ply.SurfGhost
	if args[1] == "on" then on = true elseif args[1] == "off" then on = false end
	Race.SetGhost(ply, on)
end)

SURF.Commands.Add({ "accept" }, "Accept a race", function(ply)
	local inv = Race.invites[ply:SteamID64()]
	Race.invites[ply:SteamID64()] = nil
	if not inv or CurTime() - inv.at > Race.InviteTime then return Say(ply, "Nobody has asked you to race right now.") end
	local ok, why = CanRace(inv.from)
	if ok then ok, why = CanRace(ply) end
	if not ok then return Say(ply, "Can't start the race: " .. why .. ".") end
	Race.Start(inv.from, ply, inv.countdown)
end)

SURF.Commands.Add({ "decline" }, "Turn down a race", function(ply)
	local inv = Race.invites[ply:SteamID64()]
	Race.invites[ply:SteamID64()] = nil
	if inv and IsValid(inv.from) then Say(inv.from, ply:Nick() .. " doesn't want to race right now.") end
	Say(ply, "Race declined.")
end)

SURF.Commands.Add({ "forfeit", "giveup" }, "Give up the race you're in", function(ply)
	local r = ply.SurfRace
	if not r then return Say(ply, "You aren't in a race.") end
	local other = Other(r, ply)
	Race.End(r, ply:Nick() .. " gave up" .. (IsValid(other) and (", " .. other:Nick() .. " wins") or "") .. ".")
end)
