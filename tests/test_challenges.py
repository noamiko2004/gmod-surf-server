"""Challenges, map of the day, streaks, achievements and races against the
mock Garry's Mod API of mock_gmod.py (its setup only, so the other tests'
players and coins don't get in the way).
Run: python3 tests/test_challenges.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "mock_gmod.py")
src = open(MOCK).read()
setup = src.split("\nZ = G.SURF.Zones\n")[0]
ns = {"__file__": MOCK, "__name__": "mock_setup"}
exec(compile(setup, MOCK, "exec"), ns)
L, G, db, check, failures, include = ns["L"], ns["G"], ns["db"], ns["check"], ns["failures"], ns["include"]

for f in ["sv_achievements.lua", "sv_challenges.lua", "sv_race.lua"]:
    include(f)

L.execute(r'''
Ch, Ach, Race, MV = SURF.Challenges, SURF.Achievements, SURF.Race, SURF.MapVote
startz = SURF.Zones.Find("start", 0)
endz = SURF.Zones.Find("end", 0)
function Run(p, t0, finish)
	SetCurTime(t0)
	SURF.Timer.OnZoneEnter(p, startz)
	SURF.Timer.OnZoneLeave(p, startz)
	SetCurTime(t0 + finish)
	SURF.Timer.OnZoneEnter(p, endz)
end
function Join(p)
	humans[#humans + 1] = p
	SURF.DB.LoadPlayer(p)
	SURF.Shop.Load(p)
	SURF.Timer.SetTrack(p, 0, true)
	for _, fn in pairs(hooks.SurfPlayerReady) do fn(p) end
end
function Said()
	local all = table.concat(chats, "\n")
	chats = {}
	return all
end
function Coins(p) return SURF.Shop.Balance(p.sid) end
''')

# Picks are the same for everyone and stable within a day
L.execute('d1 = Ch.Today() d2 = Ch.Today() w1 = Ch.ThisWeek()')
d1 = list(G.d1.values())
kinds = {c.kind for c in d1}
check(len(d1) == 3 and len(kinds) == 3, f"three daily challenges of different kinds ({[c.id for c in d1]})")
check([c.id for c in d1] == [c.id for c in G.d2.values()], "the same challenges all day")
check(len(list(G.w1.values())) == 2, "two weekly challenges")

# Map of the day: a playable map, saved for the day, offered in every vote
L.execute('motd = Ch.MapOfTheDay() playable = MV.Playable()')
playable = list(G.playable.values())
check(G.motd in playable, f"map of the day is a playable map ({G.motd} of {playable})")
check(ns["vfs"].get("surfline/motd.txt", "").split()[1] == G.motd, "map of the day is saved")
other = next(m for m in playable if m != "surf_kitsune")
L.execute(f'''
Ch.MapOfTheDay = function() return "{other}" end
MV.nominations = {{}}
MV.Start(true)
choices = MV.choices
MV.active = false
''')
check(other in list(G.choices.values()), f"the map of the day is one of the vote's choices ({list(G.choices.values())})")
check(not any(True for _ in G.MV.nominations.keys()), "the map of the day isn't left behind as a nomination")

# Today's challenges for the test: finish 3, 2 different maps, 2,000 u/s
L.execute('''
Ch.MapOfTheDay = function() return "surf_kitsune" end
Ch.Today = function() return { Ch.Daily[1], Ch.Daily[3], Ch.Daily[9] } end
Ch.ThisWeek = function() return { Ch.Weekly[1], Ch.Weekly[6] } end
z = MakePlayer("Zed", "76561190000000201")
chats = {}
Join(z)
joinSaid = Said()
c0 = Coins(z)
''')
check("This is the map of the day" in G.joinSaid, "joining on the map of the day says so")
check("3 daily challenges left" in G.joinSaid, f"joining lists the challenges left ({G.joinSaid!r})")
row = db.execute("select streak, best from surf_streak where steamid='76561190000000201'").fetchone()
check(row == (1, 1), f"first visit starts a streak ({row})")

L.execute('Run(z, 1000, 60) said1 = Said() c1 = Coins(z)')
check("Daily challenge done: Finish the map of the day: surf_kitsune" in G.said1, "finishing the map of the day completes its challenge")
check("unlocked First Wave" in G.said1, "first finish unlocks an achievement for everyone to see")
# first finish 50 + 25 x tier 1, first wave 50, map of the day 150 (+ the map record)
check(G.c1 - G.c0 >= 75 + 50 + 150, f"coins for the finish, the achievement and the map of the day ({G.c1 - G.c0})")
L.execute('''
st = Ch.State(z, "d" .. Ch.Day(), "finish3")
mp = Ch.State(z, "d" .. Ch.Day(), "maps2")
''')
check(G.st.progress == 1 and not G.st.done and G.mp.progress == 1, "finishes and maps count up")

L.execute('Run(z, 2000, 59) Run(z, 3000, 58) said2 = Said()')
check(G.st.progress == 3 and G.st.done and "Finish 3 runs" in G.said2, "three finishes complete \"Finish 3 runs\"")
check(G.mp.progress == 1, "the same map twice is still one map")
L.execute('mapname = "surf_mesa" Run(z, 4000, 61) mapname = "surf_kitsune" said3 = Said()')
check(G.mp.progress == 2 and G.mp.done, "a second map completes \"Finish 2 different maps\"")
check("map of the day" not in G.said3.split("Daily challenge done")[-1], "another map isn't the map of the day")

L.execute('c2 = Coins(z) Ch.Progress(z, "speed", 1, { value = 1500 }) sp = Ch.State(z, "d" .. Ch.Day(), "speed2000")')
check(G.sp.progress == 0, "too slow doesn't count")
L.execute('Ch.Progress(z, "speed", 1, { value = 2100 }) said4 = Said() c3 = Coins(z)')
check(G.sp.done, "2,100 u/s completes the speed challenge")
check("finished all of today's challenges" in G.said4 and "Daily sweep bonus" in G.said4, "all three pay the sweep bonus, announced")
check(G.c3 - G.c2 == 80 + 100, f"speed challenge 80 + sweep 100 ({G.c3 - G.c2})")
L.execute('Ch.Progress(z, "speed", 1, { value = 3000 }) c4 = Coins(z)')
check(G.c4 == G.c3, "a done challenge doesn't pay twice")

# Saved: a fresh load sees the same progress
L.execute('z.SurfCh = nil again = Ch.State(z, "d" .. Ch.Day(), "finish3")')
check(G.again.done and G.again.progress == 3, "progress is saved in the database")
L.execute('Ch.Progress(z, "maps", 1, { map = "surf_x" }) wk = Ch.State(z, "w" .. Ch.Week(), "wmaps10")')
check(G.wk.progress == 3 and "surf_kitsune" in list(G.wk.extra.keys()), f"weekly maps remember which maps ({G.wk.progress})")

# Minutes of surfing count for play challenges
L.execute('''
Ch.Today = function() return { Ch.Daily[8] } end
SURF.AFK.Touch(z)
timers.surf_challenges_play()
pl = Ch.State(z, "d" .. Ch.Day(), "play20")
z.team = TEAM_SPECTATOR timers.surf_challenges_play() z.team = 1
''')
check(G.pl.progress == 1, f"a minute surfing counts, spectating doesn't ({G.pl.progress})")

# Streaks
L.execute('''
today = Ch.Day()
SURF.DB.Query("UPDATE surf_streak SET last_day = %d, streak = 3 WHERE steamid = %s", today - 1, z.sid)
s0 = Coins(z) chats = {}
streak1, paid1 = Ch.Visit(z)
s1 = Coins(z) said5 = Said()
streak2, paid2 = Ch.Visit(z)
SURF.DB.Query("UPDATE surf_streak SET last_day = %d WHERE steamid = %s", today - 3, z.sid)
streak3 = Ch.Visit(z)
cur, best = Ch.Streak(z.sid)
''')
check(G.streak1 == 4 and G.paid1 and G.s1 - G.s0 == 40 and "4 days in a row" in G.said5, f"a 4 day streak pays 40 ({G.s1 - G.s0})")
check(G.streak2 == 4 and not G.paid2, "only the first visit of a day counts")
check(G.streak3 == 1 and G.best == 4, f"missing a day starts over, the best stays ({G.streak3}, {G.best})")

# Achievements from what was done before this update, in one quiet line
L.execute('''
old = MakePlayer("Oldie", "76561190000000202")
for i, m in ipairs({ "surf_a", "surf_b", "surf_c", "surf_d", "surf_e" }) do
	SURF.DB.Query("INSERT INTO surf_times (map, steamid, name, time, date) VALUES (%s, %s, 'Oldie', %f, 1)", m, old.sid, 50 + i)
end
SURF.DB.Query("INSERT INTO surf_times (map, steamid, name, time, date) VALUES ('surf_a#b1', %s, 'Oldie', 9, 1)", old.sid)
chats = {}
Join(old)
said6 = Said()
have = Ach.Unlocked(old.sid)
data = Ach.MenuData(old)
''')
have = set(G.have.keys())
check({"first", "maps5", "bonus1"} <= have, f"old times unlock achievements ({sorted(have)})")
check("Unlocked" in G.said6 and "for what you've already done" in G.said6 and "[Achievement]" not in G.said6,
      "old achievements are summed up for the player, not announced")
data = list(G.data.values())
check(len(data) == len(list(G.Ach.List.values())) and all(d.value <= d.goal for d in data), "the menu lists every achievement with progress")
m5 = next(d for d in data if d.id == "maps25")
check(m5.value == 5 and m5.goal == 25 and m5.date is None, "progress towards a locked one")

# The challenges window
L.execute('menus = {} Ch.Today = function() return { Ch.Daily[1], Ch.Daily[3], Ch.Daily[9] } end SURF.Commands.Run(z, "challenges", {}) m = menus[#menus]')
check(G.m.kind == "challenges" and len(list(G.m.data.list.values())) == 6 and G.m.data.motd.here and G.m.data.swept,
      "!challenges opens the window with 3 daily + map of the day + 2 weekly")
L.execute('menus = {} SURF.Commands.Run(z, "achievements", {}) m = menus[#menus]')
check(G.m.data.tab == "achievements" and len(list(G.m.data.ach.values())) == 26, "!achievements opens on its tab")

# Races
L.execute('''
r1 = MakePlayer("Rae", "76561190000000301")
r2 = MakePlayer("Ray", "76561190000000302")
for _, p in ipairs({ r1, r2 }) do function p:Freeze(on) self.frozen = on self.froze = self.froze or on end Join(p) end
chats = {}
SURF.Commands.Run(r1, "race", { "ray" })
said7 = Said()
invited = Race.invites[r2.sid] ~= nil
SURF.Commands.Run(r1, "race", { "ray" })
said8 = Said()
SURF.Commands.Run(r2, "accept", {})
said9 = Said()
race = r1.SurfRace
sameRace = race ~= nil and race == r2.SurfRace
''')
check(G.invited and "challenges you to a race" in G.said7, "!race sends an invite")
check("Wait a few seconds" in G.said8, "asking again right away is refused")
check(G.sameRace and G.race.go is not None and "are racing" in G.said9, "!accept starts the race")
check(G.r1.froze and G.r1.frozen is False, "racers are held for the countdown, then let go")
L.execute('''
rc0 = Coins(r2)
Run(r1, 100, 30)  -- started before the "go": doesn't win
stillOn = r1.SurfRace ~= nil
Run(r2, race.go + 10, 40)
said10 = Said()
rc1 = Coins(r2)
''')
check(G.stillOn, "a run started before the go doesn't count")
check("Ray beat Rae" in G.said10 and G.r1.SurfRace is None and G.r2.SurfRace is None, "first to finish wins and the race ends")
check("unlocked Rival" in G.said10, "the first win unlocks Rival")
won = db.execute("select value from surf_counters where steamid='76561190000000302' and key='races'").fetchone()
check(won and won[0] == 1, "wins are counted")
L.execute('''
r1.SurfRaceAsked = 0
SURF.DB.Query("REPLACE INTO surf_counters (steamid, key, value) VALUES (%s, 'race_day', %d)", r2.sid, Ch.Day())
SURF.DB.Query("REPLACE INTO surf_counters (steamid, key, value) VALUES (%s, 'race_paid', 5)", r2.sid)
SURF.Commands.Run(r1, "race", { "ray" }) SURF.Commands.Run(r2, "accept", {})
race2 = r1.SurfRace
cc0 = Coins(r2)
Run(r2, race2.go + 10, 40)
cc1 = Coins(r2)
r1.SurfRaceAsked = 0 chats = {}
SURF.Commands.Run(r1, "race", { "ray" }) SURF.Commands.Run(r2, "accept", {})
SURF.Commands.Run(r1, "forfeit", {})
said11 = Said()
r1.SurfRaceAsked = 0
SURF.Commands.Run(r1, "race", { "ray" }) SURF.Commands.Run(r2, "accept", {})
r2.team = TEAM_SPECTATOR timers.surf_race_watch() r2.team = 1
said12 = Said()
''')
check(G.cc1 - G.cc0 < 30, f"wins past the daily limit pay only the normal finish coins ({G.cc1 - G.cc0})")
check("Rae gave up, Ray wins" in G.said11 and G.r1.SurfRace is None, "!forfeit ends the race")
check("Ray gave up, Rae wins" in G.said12 and G.r1.SurfRace is None, "going to spectators ends the race")
L.execute('chats = {} SURF.Commands.Run(r1, "race", { "rae" }) said13 = Said() SURF.Commands.Run(r2, "accept", {}) said14 = Said()')
check("can't race yourself" in G.said13, "no racing yourself")
check("Nobody has asked you" in G.said14, "!accept without an invite")

# Race menu, countdown choice and the record ghost
L.execute(r"""
util.Compress = function(s) return s end
net.WriteData = function(d, n) sent[#sent + 1] = { "WriteData", d, n } end
r1.SurfRaceAsked = 0
r1.info = { surf_race_countdown = "10" }
function r1:GetInfo(k) return (self.info or {})[k] or "" end
menus = {}
SURF.Commands.Run(r1, "race", {})
rm = menus[#menus]
SURF.Replay.frames, SURF.Replay.info, SURF.Replay.n = nil, nil, 0
chats = {}
SURF.Commands.Run(r1, "race", { "wr" })
noGhost = Said()
noGhostOn = r1.SurfGhost
local f = {}
for i = 1, 9 do for _, v in ipairs({ i * 10, 0, 5, 0, 90 }) do f[#f + 1] = v end end
SURF.Replay.frames, SURF.Replay.info, SURF.Replay.n = f, { time = 0.09, name = "Bob" }, 9
sent = {}
SURF.Commands.Run(r1, "race", { "wr" })
ghostSaid = Said()
ghostOn = r1.SurfGhost
for _, e in ipairs(sent) do if e[1] == "WriteData" then ghostData = e[2] end end
SURF.Commands.Run(r1, "race", { "ray" })
SURF.Commands.Run(r2, "accept", {})
cd = r1.SurfRace and r1.SurfRace.countdown
racingNW = r1.nw.surf_racing
SURF.Commands.Run(r1, "forfeit", {})
racingAfter = r1.nw.surf_racing
chats = {}
SURF.Commands.Run(r1, "ghost", { "off" })
ghostOff = r1.SurfGhost == nil
""")
rm = G.rm
check(rm.kind == "race" and any(p.name == "Ray" for p in rm.data.players.values()) and rm.data.countdown == 10, "!race opens the race menu with the players and your countdown")
check(not G.noGhostOn and "no record replay" in G.noGhost, "no ghost without a record replay")
pts = (G.ghostData or "").split(";")
check(G.ghostOn and len(pts) == 3 and pts[0] == "10.0,0.0,5.0,90", f"!race wr sends every 4th replay tick as the ghost ({pts})")
check("Racing the record" in G.ghostSaid, "turning the ghost on says how it works")
check(G.cd == 10 and G.racingNW is True and G.racingAfter is False, f"the challenger's countdown is used ({G.cd}) and racers are marked")
check(G.ghostOff, "!ghost off turns it off")

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
