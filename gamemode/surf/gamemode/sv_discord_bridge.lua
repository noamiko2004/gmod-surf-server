-- Bridge to the Discord bot (discord/surfbot/bridge.py) through files in
-- garrysmod/data/surfline/discord/. The game drops events in to_discord/ and
-- reads (then deletes) what the bot drops in to_game/. Both run as the gmod
-- user. One JSON object per file, written under another name and renamed to
-- .json so the other side never reads half a file.
--
--   to_discord: {t="chat", sid, name, text} {t="join"/"leave", sid, name, count, max}
--               {t="map", map, tier} {t="link", sid, name, code}
--   to_game:    {t="chat", name, text} {t="linked", sid, discord} {t="linkfail", sid, reason}
--
-- !link <code> (sv_commands.lua) connects a Steam account to Discord; the code
-- comes from /link on Discord. The bot then shows the player's rank and VIP as
-- Discord roles.
SURF.DiscordBridge = {}
local B = SURF.DiscordBridge
local DIR = "surfline/discord"
local OUT, IN = DIR .. "/to_discord", DIR .. "/to_game"
local MAX_QUEUED = 500 -- events kept while the bot isn't reading them
local READ_PER_TICK = 20
file.CreateDir(DIR)
file.CreateDir(OUT)
file.CreateDir(IN)

local blurple, light, white = Color(88, 101, 242), Color(200, 205, 255), color_white
local acc = SURF.Config.Accent

-- One line without control characters, at most n bytes, never ending in half
-- a UTF-8 character
local function Clean(s, n)
	s = string.Trim((string.gsub(tostring(s or ""), "%c", " ")))
	n = n or 200
	if #s <= n then return s end
	s = string.sub(s, 1, n)
	for i = #s, math.max(1, #s - 3), -1 do
		local b = string.byte(s, i)
		if b < 128 then break end
		if b >= 192 then
			local len = b >= 240 and 4 or (b >= 224 and 3 or 2)
			if #s - i + 1 < len then s = string.sub(s, 1, i - 1) end
			break
		end
	end
	return s
end
B.Clean = Clean

-- The bot is down or not installed: stop queueing after a while
local backlog, backlogAt = 0, -math.huge
local function Backlogged()
	if CurTime() - backlogAt > 30 then
		backlog, backlogAt = #file.Find(OUT .. "/*.json", "DATA"), CurTime()
	end
	return backlog >= MAX_QUEUED
end

local seq = 0
function B.Send(ev)
	if Backlogged() then return false end
	seq = (seq + 1) % 10000
	ev.at = os.time()
	local name = string.format("%s/%d_%04d", OUT, os.time(), seq)
	local json = util.TableToJSON(ev)
	file.Write(name .. "_tmp.txt", json)
	if not (file.Rename and file.Rename(name .. "_tmp.txt", name .. ".json")) then
		file.Write(name .. ".json", json)
		file.Delete(name .. "_tmp.txt")
	end
	backlog = backlog + 1
	return true
end

-- Public chat goes to Discord: no commands, no team chat, at most 5 lines in
-- 10 seconds per player
function B.Chat(ply, text, teamChat)
	if teamChat or not IsValid(ply) or ply:IsBot() then return end
	local first = string.sub(text or "", 1, 1)
	if first == "!" or first == "/" then return end
	text = Clean(text)
	if text == "" then return end
	local now = CurTime()
	local f = ply.SurfDiscordFlood
	if not f or now - f.start > 10 then
		f = { start = now, n = 0 }
		ply.SurfDiscordFlood = f
	end
	f.n = f.n + 1
	if f.n > 5 then return end
	B.Send({ t = "chat", sid = ply:SteamID64(), name = Clean(ply:Nick(), 64), text = text })
end

-- The gamemode function, not a hook: it only runs when no hook took the
-- message first (chat commands return "" from surf_commands)
function GM:PlayerSay(ply, text, teamChat)
	if SURF.Admin and not SURF.Admin.MayChat(ply) then return "" end
	B.Chat(ply, text, teamChat)
	return text
end

function B.Link(ply, code)
	code = string.sub(string.upper((string.gsub(tostring(code or ""), "[^%w]", ""))), 1, 16)
	if code == "" then
		SURF.Chat(ply, blurple, "[Discord] ", white, "Type /link in our Discord (!discord) to get a code, then type !link <code> here.")
		return
	end
	if CurTime() - (ply.SurfLinkAt or -math.huge) < 5 then
		SURF.Chat(ply, blurple, "[Discord] ", white, "Wait a few seconds before trying again.")
		return
	end
	ply.SurfLinkAt = CurTime()
	if B.Send({ t = "link", sid = ply:SteamID64(), name = Clean(ply:Nick(), 64), code = code }) then
		SURF.Chat(ply, blurple, "[Discord] ", white, "Checking your code...")
	else
		SURF.Chat(ply, blurple, "[Discord] ", white, "The Discord bot isn't answering right now. Try again later.")
	end
end

hook.Add("SurfPlayerReady", "surf_discord_bridge", function(ply)
	B.Send({ t = "join", sid = ply:SteamID64(), name = Clean(ply:Nick(), 64), count = #player.GetHumans(), max = game.MaxPlayers() })
end)

hook.Add("PlayerDisconnected", "surf_discord_bridge", function(ply)
	if ply:IsBot() then return end
	B.Send({ t = "leave", sid = ply:SteamID64(), name = Clean(ply:Nick(), 64), count = math.max(0, #player.GetHumans() - 1), max = game.MaxPlayers() })
end)

hook.Add("InitPostEntity", "surf_discord_bridge", function()
	local map = game.GetMap()
	if not string.StartWith(map, SURF.Config.MapPrefix) then return end -- a fallback start map switches by itself
	timer.Simple(5, function()
		B.Send({ t = "map", map = map, tier = SURF.MapVote.Tier(map) or 0 })
	end)
end)

function B.Handle(ev)
	if ev.t == "chat" then
		local name, text = Clean(ev.name, 32), Clean(ev.text)
		if name == "" or text == "" then return end
		SURF.Chat(nil, blurple, "[Discord] ", light, name, white, ": " .. text)
	elseif ev.t == "linked" or ev.t == "linkfail" then
		local p = player.GetBySteamID64(tostring(ev.sid or ""))
		if not IsValid(p) then return end
		if ev.t == "linked" then
			SURF.Chat(p, blurple, "[Discord] ", white, "Linked to ", acc, Clean(ev.discord, 32), white, ". Your rank shows on Discord now.")
		else
			SURF.Chat(p, blurple, "[Discord] ", Color(255, 120, 120), Clean(ev.reason))
		end
	end
end

function B.Poll()
	local files = file.Find(IN .. "/*.json", "DATA", "nameasc")
	for i, f in ipairs(files or {}) do
		if i > READ_PER_TICK then break end
		local path = IN .. "/" .. f
		local ev = util.JSONToTable(file.Read(path, "DATA") or "")
		file.Delete(path)
		if istable(ev) then B.Handle(ev) end
	end
end
timer.Create("surf_discord_bridge", 2, 0, B.Poll)
