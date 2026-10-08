"""Offline test of scripts/health.py log parsing and the public summary.
Run: python3 tests/test_health.py"""
import json, os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import health as H

fails = 0


def check(cond, what):
    global fails
    print(("ok   " if cond else "FAIL ") + what)
    fails += 0 if cond else 1


# Lua errors: same file:line with other numbers counts as one error
r = H.Report()
game = [
    "[ERROR] gamemodes/surf/gamemode/sv_timer.lua:120: attempt to index a nil value (field '?')",
    "  1. Finish - gamemodes/surf/gamemode/sv_timer.lua:120",
    "[ERROR] gamemodes/surf/gamemode/sv_timer.lua:120: attempt to index a nil value (field '?')",
    "[ERROR] gamemodes/surf/gamemode/sv_shop.lua:7: bad argument #1 to 'pairs' (table expected, got nil)",
    "Client \"Bob\" connected (85.1.2.3:27005).",
]
errs = H.check_game_log(r, game)
check(sum(errs.values()) == 3 and len(errs) == 2, "Lua errors counted and grouped")
check(r.items[0][0] == H.WARN and "3 Lua errors" in r.items[0][2], "Lua errors are a warning line")
r = H.Report()
errs = H.check_game_log(r, ["[ERROR] gamemodes/base/entities/entities/gmod_hands.lua:31: Tried to use a NULL entity!",
                            "  1. DeleteOnRemove - [C]:-1",
                            "   2. DoSetup - gamemodes/base/entities/entities/gmod_hands.lua:31",
                            "    3. SetupHands - lua/includes/extensions/player.lua:350",
                            "     4. unknown - gamemodes/surf/gamemode/init.lua:126",
                            "Map is surf_x"])
check(list(errs) == ["gamemodes/base/entities/entities/gmod_hands.lua:31: Tried to use a NULL entity! <- unknown gamemodes/surf/gamemode/init.lua:126"],
      "base-game errors name the gamemode line that called them: " + str(list(errs)))
r = H.Report()
H.check_game_log(r, ["Segmentation fault (core dumped)", "normal line"])
check(r.items[0][0] == H.BAD, "a crash is a problem")
r = H.Report()
H.check_game_log(r, ["fine"] * 60)
check(r.items[0][0] == H.OK, "clean game log is OK")
r = H.Report()
H.check_game_log(r, ["fine", "also fine"])
check(r.items[0][0] == H.WARN, "a nearly empty game log is a warning, not proof of no errors")

# Python logs: tracebacks name their exception once
r = H.Report()
bot = [
    "INFO surfbot: ready",
    "ERROR surfbot: bridge read failed",
    "Traceback (most recent call last):",
    '  File "bridge.py", line 40, in poll',
    "PermissionError: [Errno 13] Permission denied: 'to_discord/1.json'",
    "WARNING discord.http: rate limited",
]
errs = H.check_py_log(r, "Discord bot log", bot)
check(sum(errs.values()) == 2, "ERROR line and traceback both counted")
check(any(k.startswith("PermissionError") for k in errs), "traceback exception found")

r = H.Report()
H.check_py_log(r, "Discord bot log", ["WARNING surfbot: Game chat from Bob not posted: 50035 Invalid Form Body",
                                      "WARNING surfbot: Game chat from Ann not posted: 50035 Invalid Form Body",
                                      "INFO surfbot: New invite link: https://discord.gg/abc"])
refused = [i for i in r.items if i[1] == "Discord bridge"]
check(len(refused) == 1 and "refused 2 game lines" in refused[0][2] and "chat: N Invalid Form Body" in refused[0][2], "refused game chat grouped by reason")
check(any("new Discord invite 1 time in" in i[2] for i in r.items), "new invite links counted")

r = H.Report()
errs = H.check_py_log(r, "Website log", ['[portal] 85.1.2.3 "GET /maps/x?y=1 HTTP/1.1" 500 -',
                                         '[portal] 85.1.2.3 "GET / HTTP/1.1" 200 -',
                                         '[portal] tebex poll failed: timed out'])
check(errs.get("HTTP 500 on /maps/x") == 1 and sum(errs.values()) == 2, "website 500s and failures counted")

# services: the bot's clean exit to reload its code is no crash; a real one is
r = H.Report()
H.unit_state = lambda u: {"LoadState": "loaded", "ActiveState": "active", "ActiveEnterTimestamp": "today"}
bot_j = ["INFO surfbot: Code changed on disk, restarting to load it",
         "surf-discord.service: Main process exited, code=exited, status=0/SUCCESS",
         "surf-discord.service: Scheduled restart job, restart counter is at 6."]
game_j = ["Segfault in sv_timer", "gmod-surf.service: Main process exited, code=dumped, status=11/SEGV",
          "gmod-surf.service: Main process exited, code=killed, status=15/TERM"]
H.check_services(r, {"surf-discord": bot_j, "gmod-surf": game_j}, [("surf-discord", "Discord bot"), ("gmod-surf", "Game server")])
check(r.items[0][0] == H.OK, "bot reloading its code is not a crash: " + r.items[0][2])
check(r.items[1][0] == H.WARN and "crashed 1 times" in r.items[1][2] and "Segfault in sv_timer" in r.items[1][2], "a real crash is reported with the line before it")

# links: the bot's invite in the bridge folder is enough for !discord
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "discord"))
    open(os.path.join(d, "discord", "invite.txt"), "w").write("https://discord.gg/abc123\n")
    r = H.Report()
    H.check_links(r, d, d, {})
    check(r.items[0][0] == H.OK, "bridge invite.txt counts as a !discord link")

# voice warnings from discord.py are noise
r = H.Report()
H.check_py_log(r, "Discord bot log", ["WARNING discord.client: PyNaCl is not installed, voice will NOT be supported"])
check(r.items[0][2] == "Discord bot log: no errors in 24 h", "voice warnings ignored")

# update.log: last run and its problems
with tempfile.TemporaryDirectory() as home:
    with open(os.path.join(home, "update.log"), "w") as f:
        f.write("[2026-10-05 05:00:01] Pulling latest server files (now at x)\n"
                "[2026-10-05 05:00:02] WARNING: could not get the new version from GitHub\n"
                "[2026-10-05 05:09:00] Update complete. Version x\n")
    now = time.mktime(time.strptime("2026-10-05 12:00:00", "%Y-%m-%d %H:%M:%S"))
    r = H.Report()
    H.check_updates(r, home, now)
    check(r.items[0][0] == H.WARN and "1 problem" in r.items[0][2], "update problems reported")

    # bridge: old files waiting are a stuck reader
    data = os.path.join(home, "data")
    for sub in ("to_discord", "to_game"):
        os.makedirs(os.path.join(data, "discord", sub))
    p = os.path.join(data, "discord", "to_discord", "1.json")
    open(p, "w").write("{}")
    os.utime(p, (time.time() - 600, time.time() - 600))
    r = H.Report()
    H.check_bridge(r, data, time.time())
    check(r.items[0][0] == H.WARN and "to_discord" in r.items[0][2], "stuck bridge messages found")

# public summary hides links, IPs and keys
s = H.redact("Webhook https://discord.com/api/webhooks/1/abc failed for 85.1.2.3:27005 token=abcd "
             + ".".join(["MTIzNDU2Nzg5MDEyMzQ1Njc4OTA", "Gabcde", "abcdefghijklmnopqrstuvwxyz012345"]))  # fake bot token, built so scanners don't flag it
check("discord.com" not in s and "85.1.2.3" not in s and "abcd" not in s and "abcdefghijklmnop" not in s, "redact: " + s)
r = H.Report()
r.add(H.WARN, "x", "see http://secret.example/a", ["1.2.3.4 said hi"])
j = json.dumps(H.render_json(r, "abc", time.time()))
check("secret.example" not in j and "1.2.3.4" not in j and '"status": "warn"' in j, "health.json is redacted")

print("\nAll health checks passed" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
