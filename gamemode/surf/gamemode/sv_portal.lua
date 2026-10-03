-- Bridge to the web portal (portal/server.py) through files in
-- garrysmod/data/surfline/portal/. The game writes status.json every few
-- seconds; the portal drops admin commands into cmd/*.txt, which the game
-- runs and answers in results.txt. Both run as the same Linux user.
SURF.Portal = {}
local P = SURF.Portal
local DIR = "surfline/portal"
local RESULTS = DIR .. "/results.txt"
file.CreateDir(DIR)
file.CreateDir(DIR .. "/cmd")

local mapStarted = os.time()
local STATE = {
	[SURF.STATE_NOZONES] = "nozones", [SURF.STATE_START] = "start", [SURF.STATE_RUNNING] = "running",
	[SURF.STATE_FINISHED] = "finished", [SURF.STATE_IDLE] = "idle",
}

local function PlayerRow(p)
	local state = STATE[p:GetNW2Int("surf_state", SURF.STATE_IDLE)] or "idle"
	if p:Team() == TEAM_SPECTATOR then state = "spec" end
	local t = 0
	if state == "running" then
		t = CurTime() - p:GetNW2Float("surf_start")
	elseif state == "finished" then
		t = p:GetNW2Float("surf_final")
	end
	local title = SURF.Config.Titles[p:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
	return {
		steamid = p:SteamID64(), name = p:Nick(), points = p:GetNW2Int("surf_points", 0), title = title.name,
		rank = p:GetNW2Int("surf_rankpos", 0), state = state, track = p:GetNW2Int("surf_track", 0), style = SURF.StyleOf(p).id,
		time = math.Round(t, 3), pb = math.Round(p:GetNW2Float("surf_pb", 0), 3), vip = SURF.IsVIP(p),
		admin = p:IsAdmin(), ping = p:Ping(), connected = math.floor(p:TimeConnected()),
	}
end

local mapsCache, mapsCacheAt = nil, 0
local function MapsInfo()
	if not mapsCache or CurTime() - mapsCacheAt > 60 then
		mapsCache, mapsCacheAt = SURF.MapVote.Info(SURF.MapVote.MapList()), CurTime()
	end
	return mapsCache
end

function P.WriteStatus()
	local players = {}
	for _, p in ipairs(player.GetHumans()) do players[#players + 1] = PlayerRow(p) end
	local map = game.GetMap()
	local wr = SURF.DB.GetWR(SURF.MapKey(0))
	local R = SURF.Replay
	file.Write(DIR .. "/status.json", util.TableToJSON({
		updated = os.time(), hostname = GetHostName(), brand = GetGlobal2String("surf_brand", SURF.Config.Name),
		map = map, tier = SURF.MapVote.Tier(map), mapper = SURF.MapVote.Mapper(map), maxplayers = game.MaxPlayers(),
		timeleft = math.max(0, math.floor(GetGlobal2Int("surf_mapend") - CurTime())), map_started = mapStarted,
		wr = wr and { time = wr.time, name = wr.name } or false,
		replay = (R.info and IsValid(R.bot)) and { time = R.info.time, name = R.info.name } or false,
		players = players, maps = MapsInfo(),
	}))
end

-- Commands ------------------------------------------------------------------

local function ValidID(sid)
	return isstring(sid) and string.match(sid, "^7656%d+$") ~= nil and #sid == 17
end

local function Clean(text)
	text = string.gsub(tostring(text or ""), "%c", " ")
	return string.sub(string.Trim(text), 1, 200)
end

local function KnownName(sid)
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then return p:Nick() end
	local row = SURF.DB.Query("SELECT name FROM surf_players WHERE steamid = %s", sid)
	return row and row[1] and row[1].name or sid
end

local acc = SURF.Config.Accent
local ACTIONS = {}

ACTIONS.say = function(c)
	local text = Clean(c.text)
	if text == "" then return false, "empty message" end
	SURF.Chat(nil, Color(255, 200, 40), "[Server] ", color_white, text)
	return true, "message sent"
end

ACTIONS.changelevel = function(c)
	local map = tostring(c.map or "")
	if not table.HasValue(SURF.MapVote.MapList(), map) then return false, "map not installed" end
	SURF.Chat(nil, acc, "[Admin] ", color_white, "Changing the map to ", acc, map, color_white, " in 5 seconds.")
	timer.Simple(5, function()
		for _, p in ipairs(player.GetHumans()) do SURF.DB.SavePlayer(p) end
		SURF.MapVote.MarkAdminMap(map)
		RunConsoleCommand("changelevel", map)
	end)
	return true, "changing to " .. map
end

ACTIONS.extend = function(c)
	local minutes = math.Clamp(math.floor(tonumber(c.minutes) or 0), 1, 120)
	SetGlobal2Int("surf_mapend", math.max(GetGlobal2Int("surf_mapend"), math.floor(CurTime())) + minutes * 60)
	SURF.Chat(nil, acc, "[Admin] ", color_white, "The map was extended by " .. minutes .. " minutes.")
	return true, "extended by " .. minutes .. " min"
end

ACTIONS.vote = function()
	if SURF.MapVote.active then return false, "a vote is already running" end
	SURF.MapVote.Start(true)
	return true, "vote started"
end

ACTIONS.kick = function(c)
	local p = ValidID(c.steamid) and player.GetBySteamID64(c.steamid)
	if not IsValid(p) then return false, "player not online" end
	local reason = Clean(c.reason)
	p:Kick(reason ~= "" and reason or "Kicked by an admin")
	return true, "kicked " .. p:Nick()
end

ACTIONS.ban = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local minutes = math.max(0, math.floor(tonumber(c.minutes) or 0))
	local reason = Clean(c.reason)
	if reason == "" then reason = "Banned by an admin" end
	local expires = minutes == 0 and 0 or (os.time() + minutes * 60)
	local name = KnownName(c.steamid)
	SURF.DB.Query("REPLACE INTO surf_bans (steamid, name, reason, admin, created, expires) VALUES (%s, %s, %s, %s, %d, %d)",
		c.steamid, name, reason, tostring(c.by or ""), os.time(), expires)
	local p = player.GetBySteamID64(c.steamid)
	if IsValid(p) then p:Kick("Banned: " .. reason) end
	return true, "banned " .. name .. (minutes == 0 and " permanently" or (" for " .. minutes .. " min"))
end

ACTIONS.unban = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	SURF.DB.Query("DELETE FROM surf_bans WHERE steamid = %s", c.steamid)
	return true, "unbanned " .. KnownName(c.steamid)
end

ACTIONS.givevip = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local days = math.max(0, math.floor(tonumber(c.days) or 0))
	local exp = SURF.VIP.Give(c.steamid, days)
	return true, "VIP for " .. KnownName(c.steamid) .. (exp == 0 and " (permanent)" or (" until " .. os.date("%Y-%m-%d", exp)))
end

ACTIONS.removevip = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	SURF.VIP.Remove(c.steamid)
	return true, "removed VIP from " .. KnownName(c.steamid)
end

ACTIONS.givecoins = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local amount = math.Clamp(math.floor(tonumber(c.amount) or 0), -1000000, 1000000)
	if amount == 0 then return false, "amount is 0" end
	local bal = SURF.Shop.GiveCoins(c.steamid, amount, c.by == "tebex" and "store purchase" or "given on the website")
	return true, string.format("%s%d coins for %s (now %d)", amount > 0 and "+" or "", amount, KnownName(c.steamid), bal)
end

ACTIONS.giveitem = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local key = tostring(c.item or "")
	if not SURF.Shop.Grant(c.steamid, key, c.by == "tebex" and "store" or "website") then return false, "unknown item" end
	return true, "gave " .. SURF.ItemByKey[key].name .. " to " .. KnownName(c.steamid)
end

ACTIONS.removeitem = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local key = tostring(c.item or "")
	if not SURF.ItemByKey[key] then return false, "unknown item" end
	SURF.Shop.Revoke(c.steamid, key)
	return true, "removed " .. SURF.ItemByKey[key].name .. " from " .. KnownName(c.steamid)
end

ACTIONS.adjustpoints = function(c)
	if not ValidID(c.steamid) then return false, "bad steamid" end
	local delta = math.Clamp(math.floor(tonumber(c.points) or 0), -1000000, 1000000)
	if delta == 0 then return false, "points is 0" end
	local total = SURF.Ranks.AdjustPoints(c.steamid, delta, Clean(c.reason))
	local r = SURF.Ranks.bySid[c.steamid]
	return true, string.format("%s%d points for %s (adjustment now %d, total %d)", delta > 0 and "+" or "", delta,
		KnownName(c.steamid), total, r and r.points or 0)
end

-- Shop settings from the portal's shop admin page
ACTIONS.shopitem = function(c)
	local key = tostring(c.item or "")
	local it = SURF.ItemByKey[key]
	if not it then return false, "unknown item" end
	local fields = {}
	if c.price ~= nil then fields.price = tonumber(c.price) or 0 end
	if c.vip ~= nil then fields.vip = c.vip == true end
	if c.hidden ~= nil then fields.hidden = c.hidden == true end
	if not SURF.Shop.SetItem(key, fields) then return false, "can't change " .. key end
	return true, string.format("%s: %s%s%s", it.name, it.price and (it.price .. " coins") or "no coin price",
		it.vip and ", VIP" or "", it.hidden and ", hidden" or "")
end

ACTIONS.coinrate = function(c)
	local name = tostring(c.name or "")
	if not SURF.Shop.SetRate(name, c.value) then return false, "bad rate" end
	return true, "coin rate " .. name .. " is now " .. tostring(SURF.Config.Coins[name])
end

ACTIONS.vipprice = function(c)
	local days, price = tonumber(c.days), tonumber(c.price)
	if not SURF.Shop.SetVIPPrice(days, price) then return false, "bad VIP package" end
	return true, price == 0 and ("removed the " .. days .. " day VIP package") or string.format("%d days of VIP cost %d coins", days, price)
end

-- Record keys: surf_x, surf_x#b2, surf_x@sw, surf_x#b2@sw
local function ValidKey(key)
	local base, style = string.match(key, "^(.-)@(%w+)$")
	if base then
		if not SURF.StyleByID[style] or style == "n" then return false end
		key = base
	end
	return string.match(key, "^surf_[%w_]+$") ~= nil or string.match(key, "^surf_[%w_]+#b%d+$") ~= nil
end

ACTIONS.deltime = function(c)
	local key = tostring(c.key or "")
	if not ValidID(c.steamid) or not ValidKey(key) then
		return false, "bad map or steamid"
	end
	SURF.DB.DeleteTime(key, c.steamid)
	return true, "deleted the time of " .. KnownName(c.steamid) .. " on " .. key
end

local function Result(id, ok, msg)
	if (file.Size(RESULTS, "DATA") or 0) > 200 * 1024 then
		local lines = string.Explode("\n", file.Read(RESULTS, "DATA") or "")
		file.Write(RESULTS, table.concat(lines, "\n", math.max(1, #lines - 100)))
	end
	file.Append(RESULTS, util.TableToJSON({ id = id, ok = ok, msg = msg, time = os.time() }) .. "\n")
end

function P.RunCommands()
	local files = file.Find(DIR .. "/cmd/*.txt", "DATA") or {}
	table.sort(files)
	for _, name in ipairs(files) do
		local path = DIR .. "/cmd/" .. name
		local cmd = util.JSONToTable(file.Read(path, "DATA") or "") or {}
		file.Delete(path)
		local id = string.StripExtension(name)
		local fn = ACTIONS[cmd.action or ""]
		local ok, msg
		if fn then
			local success, a, b = pcall(fn, cmd)
			if success then ok, msg = a, b else ok, msg = false, "error: " .. tostring(a) end
		else
			ok, msg = false, "unknown action"
		end
		print(string.format("[Surf] Portal: %s by %s: %s", tostring(cmd.action), tostring(cmd.by), tostring(msg)))
		Result(id, ok, msg)
	end
end

timer.Create("surf_portal_status", 5, 0, function() P.WriteStatus() end)
timer.Create("surf_portal_cmds", 2, 0, function() P.RunCommands() end)
hook.Add("InitPostEntity", "surf_portal", function() timer.Simple(2, P.WriteStatus) end)

-- Bans (set from the portal) ----------------------------------------------

hook.Add("CheckPassword", "surf_bans", function(sid64)
	local row = SURF.DB.Query("SELECT reason, expires FROM surf_bans WHERE steamid = %s", sid64)
	if not row or not row[1] then return end
	local exp = tonumber(row[1].expires) or 0
	if exp ~= 0 and exp < os.time() then
		SURF.DB.Query("DELETE FROM surf_bans WHERE steamid = %s", sid64)
		return
	end
	return false, "You are banned: " .. tostring(row[1].reason) .. (exp == 0 and "" or (" (until " .. os.date("%Y-%m-%d %H:%M", exp) .. ")"))
end)
