-- 1v1 races (!race <player>): both go to the start, a 3 second countdown
-- holds them there, and the first to finish the map wins. The winner gets a
-- few coins (a handful of paid wins a day, so friends can't farm it) and a
-- step towards the race achievements. Nothing is bet.
SURF.Race = { invites = {}, list = {} }
local Race = SURF.Race
local acc, white = SURF.Config.Accent, color_white
local GOLD = Color(255, 200, 40)
local TAG = Color(255, 120, 60)

Race.InviteTime = 30 -- seconds to !accept
Race.Countdown = 3
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

function Race.Start(a, b)
	local r = { a = a, b = b, created = CurTime() }
	Race.list[#Race.list + 1] = r
	a.SurfRace, b.SurfRace = r, r
	for _, p in ipairs({ a, b }) do
		SURF.Timer.GoToStart(p, 0)
		if p.Freeze then p:Freeze(true) end
		Send(p, { count = Race.Countdown, vs = Other(r, p):Nick() })
	end
	SURF.Chat(nil, TAG, "[Race] ", white, a:Nick() .. " and " .. b:Nick() .. " are racing on this map! Watch with ", acc, "!spec " .. a:Nick(), white, ".")
	timer.Simple(Race.Countdown, function()
		if r.over then return end
		if not IsValid(r.a) or not IsValid(r.b) then return Race.End(r, "The race was called off (a racer left).") end
		r.go = CurTime()
		for _, p in ipairs({ r.a, r.b }) do
			-- They're still in the start zone, so the timer starts as they leave it
			if p.Freeze then p:Freeze(false) end
			SURF.Timer.GoToStart(p, 0)
			Send(p, { go = true, vs = Other(r, p):Nick() })
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

SURF.Commands.Add({ "race" }, "!race <player> challenges someone to a race to the end", function(ply, args)
	if #args == 0 then
		return Say(ply, "Type ", acc, "!race <name>", white, " to race someone to the end of this map. First to finish wins.")
	end
	if not SURF.Zones.HasTimer(0) then return Say(ply, "This map has no start and end to race on.") end
	local t, err = SURF.Admin.FindPlayer(table.concat(args, " "))
	if not t then return Say(ply, "Couldn't find that player: " .. err .. ".") end
	if t == ply then return Say(ply, "You can't race yourself. Try beating your best with !r.") end
	local ok, why = CanRace(ply)
	if ok then ok, why = CanRace(t) end
	if not ok then return Say(ply, "Can't race now: " .. why .. ".") end
	if (ply.SurfRaceAsked or 0) > CurTime() then return Say(ply, "Wait a few seconds before asking again.") end
	ply.SurfRaceAsked = CurTime() + 10
	Race.invites[t:SteamID64()] = { from = ply, at = CurTime() }
	local st = SURF.StyleOf(ply)
	Say(t, ply:Nick() .. " challenges you to a race to the end of " .. game.GetMap() .. (st.id ~= "n" and (" (they're on " .. st.name .. ")") or "") .. "! Type ",
		acc, "!accept", white, " within " .. Race.InviteTime .. " seconds, or ", acc, "!decline", white, ".")
	SURF.Challenges.Toast(t, ply:Nick() .. " wants to race! Type !accept", TAG)
	t:SendLua([[surface.PlaySound("buttons/button17.wav")]])
	Say(ply, "Race request sent to " .. t:Nick() .. ".")
end)

SURF.Commands.Add({ "accept" }, "Accept a race", function(ply)
	local inv = Race.invites[ply:SteamID64()]
	Race.invites[ply:SteamID64()] = nil
	if not inv or CurTime() - inv.at > Race.InviteTime then return Say(ply, "Nobody has asked you to race right now.") end
	local ok, why = CanRace(inv.from)
	if ok then ok, why = CanRace(ply) end
	if not ok then return Say(ply, "Can't start the race: " .. why .. ".") end
	Race.Start(inv.from, ply)
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
