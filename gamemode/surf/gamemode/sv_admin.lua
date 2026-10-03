-- In-game admin: the admin panel (cl_admin.lua: !admin, F1 > Admin, or
-- right-click a player on the scoreboard) and admin chat commands.
--
-- Admins moderate: teleport, freeze, slay, mute chat, gag voice, kick, ban,
-- delete times and run the map rotation. Superadmins (OWNER_STEAMIDS in
-- config.env) can also give VIP, coins, items and points, and make players
-- admins (saved in surf_staff). Nobody can punish someone of the same or a
-- higher rank. Every action is logged in surf_admin_log, together with what
-- admins do on the website, and the panel shows that log.
SURF.Admin = {}
local A = SURF.Admin
local Q = SURF.DB.Query
local acc, white, red = SURF.Config.Accent, color_white, Color(255, 90, 90)

util.AddNetworkString("surf.Admin") -- client -> server: { a = action, ... }
util.AddNetworkString("surf.AdminData") -- server -> client: kind, table
util.AddNetworkString("surf.Announce") -- server -> everyone: text, admin name

Q([[CREATE TABLE IF NOT EXISTS surf_admin_log (
	id INTEGER PRIMARY KEY AUTOINCREMENT, date INTEGER, admin TEXT, admin_name TEXT, action TEXT,
	target TEXT, target_name TEXT, detail TEXT, source TEXT)]])
Q([[CREATE TABLE IF NOT EXISTS surf_staff (
	steamid TEXT PRIMARY KEY, name TEXT, rank TEXT NOT NULL, added_by TEXT, date INTEGER)]])
-- Chat mutes and voice gags; expires 0 = until an admin lifts it
Q([[CREATE TABLE IF NOT EXISTS surf_sanctions (
	steamid TEXT NOT NULL, kind TEXT NOT NULL, expires INTEGER NOT NULL, reason TEXT, admin TEXT, date INTEGER,
	PRIMARY KEY (steamid, kind))]])

local function ValidID(sid)
	return isstring(sid) and #sid == 17 and string.match(sid, "^7656%d+$") ~= nil
end
A.ValidID = ValidID

local function Clean(text, n)
	text = string.gsub(tostring(text or ""), "%c", " ")
	return string.sub(string.Trim(text), 1, n or 200)
end

function A.KnownName(sid)
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then return p:Nick() end
	local row = Q("SELECT name FROM surf_players WHERE steamid = %s", sid)
	return row and row[1] and row[1].name or sid
end

-- Ranks -------------------------------------------------------------------------

function A.IsOwnerID(sid)
	for id in string.gmatch(file.Read("surfline/owners.txt", "DATA") or "", "%d+") do
		if id == sid then return true end
	end
	return false
end

function A.StaffRank(sid)
	local r = Q("SELECT rank FROM surf_staff WHERE steamid = %s", sid)
	return r and r[1] and r[1].rank or nil
end

-- 0 player, 1 admin, 2 superadmin; the server console is above everyone
function A.Level(who)
	if who == nil then return 3 end
	if isstring(who) then
		local p = player.GetBySteamID64(who)
		if IsValid(p) then return A.Level(p) end
		if A.IsOwnerID(who) then return 2 end
		return A.StaffRank(who) == "admin" and 1 or 0
	end
	if not IsValid(who) then return 3 end
	if who:IsSuperAdmin() then return 2 end
	if who:IsAdmin() then return 1 end
	return 0
end

hook.Add("PlayerInitialSpawn", "surf_staff", function(ply)
	if ply:IsBot() or ply:IsAdmin() then return end
	if A.StaffRank(ply:SteamID64()) == "admin" then ply:SetUserGroup("admin") end
end)

-- Log ---------------------------------------------------------------------------

function A.Log(adminSid, adminName, action, targetSid, targetName, detail, source)
	Q("INSERT INTO surf_admin_log (date, admin, admin_name, action, target, target_name, detail, source) VALUES (%d, %s, %s, %s, %s, %s, %s, %s)",
		os.time(), adminSid or "", adminName or "", action or "", targetSid or "", targetName or "", detail or "", source or "game")
	-- Keep the newest 5000
	Q("DELETE FROM surf_admin_log WHERE id <= (SELECT MAX(id) FROM surf_admin_log) - 5000")
end

-- Mutes and gags ------------------------------------------------------------------

local KINDS = { mute = "SurfMute", gag = "SurfGag" }

local function LoadSanctions(ply)
	ply.SurfMute, ply.SurfGag = nil, nil
	for _, r in ipairs(Q("SELECT kind, expires FROM surf_sanctions WHERE steamid = %s", ply:SteamID64()) or {}) do
		local exp = tonumber(r.expires) or 0
		if KINDS[r.kind] and (exp == 0 or exp > os.time()) then ply[KINDS[r.kind]] = exp end
	end
	ply:SetNW2Bool("surf_muted", ply.SurfMute ~= nil)
	ply:SetNW2Bool("surf_gagged", ply.SurfGag ~= nil)
end
A.LoadSanctions = LoadSanctions
hook.Add("PlayerInitialSpawn", "surf_sanctions", function(ply) if not ply:IsBot() then LoadSanctions(ply) end end)

-- Returns the expiry (0 = no end) when the player is muted/gagged right now
local function Active(ply, kind)
	local exp = ply[KINDS[kind]]
	if exp == nil then return nil end
	if exp ~= 0 and exp <= os.time() then
		Q("DELETE FROM surf_sanctions WHERE steamid = %s AND kind = %s", ply:SteamID64(), kind)
		LoadSanctions(ply)
		return nil
	end
	return exp
end
function A.Muted(ply) return IsValid(ply) and Active(ply, "mute") or nil end
function A.Gagged(ply) return IsValid(ply) and Active(ply, "gag") or nil end

local function Until(exp)
	if exp == 0 then return "until an admin lifts it" end
	local left = exp - os.time()
	if left < 3600 then return "for " .. math.max(1, math.ceil(left / 60)) .. " more minutes" end
	if left < 86400 * 2 then return "for " .. math.ceil(left / 3600) .. " more hours" end
	return "until " .. os.date("%Y-%m-%d", exp)
end
A.Until = Until

-- Called from GM:PlayerSay (sv_discord_bridge.lua): false blocks the message
function A.MayChat(ply)
	local exp = A.Muted(ply)
	if not exp then return true end
	if (ply.SurfMuteToldAt or 0) < CurTime() - 3 then
		ply.SurfMuteToldAt = CurTime()
		SURF.Chat(ply, red, "[Admin] ", white, "You are muted " .. Until(exp) .. ". Chat commands still work.")
	end
	return false
end

hook.Add("PlayerCanHearPlayersVoice", "surf_gag", function(_, talker)
	if A.Gagged(talker) then return false end
end)

local function SetSanction(sid, kind, minutes, reason, adminSid)
	if minutes == nil then
		Q("DELETE FROM surf_sanctions WHERE steamid = %s AND kind = %s", sid, kind)
	else
		local exp = minutes <= 0 and 0 or (os.time() + minutes * 60)
		Q("REPLACE INTO surf_sanctions (steamid, kind, expires, reason, admin, date) VALUES (%s, %s, %d, %s, %s, %d)",
			sid, kind, exp, reason or "", adminSid or "", os.time())
	end
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then LoadSanctions(p) end
end

-- Staff ---------------------------------------------------------------------------

local function SetRank(sid, rank, by)
	if rank == "admin" then
		Q("REPLACE INTO surf_staff (steamid, name, rank, added_by, date) VALUES (%s, %s, %s, %s, %d)", sid, A.KnownName(sid), rank, by or "", os.time())
	else
		Q("DELETE FROM surf_staff WHERE steamid = %s", sid)
	end
	local p = player.GetBySteamID64(sid)
	if IsValid(p) and not p:IsSuperAdmin() then
		p:SetUserGroup(rank == "admin" and "admin" or "user")
		SURF.VIP.Load(p) -- admins get the VIP looks
		SURF.Commands.SendList(p)
		SURF.Chat(p, acc, "[Admin] ", white, rank == "admin" and "You are an admin now. Type !admin to open the admin panel." or "You are no longer an admin.")
	end
end

-- Actions ---------------------------------------------------------------------------
-- perm: 1 admin, 2 superadmin. target: "online" needs the player on the
-- server, "sid" works for anyone with a SteamID64. punish: only on someone
-- of a lower rank. ingame: the admin has to be on the server (not the
-- console). fn(admin, target, args, sid) returns ok, message.

local ACT = {}
A.Actions = ACT

local function Minutes(v, default)
	return math.Clamp(math.floor(tonumber(v) or default or 0), 0, 60 * 24 * 3650)
end

local function TimeText(minutes)
	if minutes <= 0 then return "permanently" end
	if minutes < 120 then return "for " .. minutes .. " minutes" end
	if minutes < 60 * 48 then return "for " .. math.floor(minutes / 60) .. " hours" end
	return "for " .. math.floor(minutes / 1440) .. " days"
end
A.TimeText = TimeText

local function ToSurf(p)
	if p:Team() == TEAM_SPECTATOR then SURF.Spec.Toggle(p) end
	if not p:Alive() then p:Spawn() end
end

ACT["goto"] = { perm = 1, target = "online", ingame = true, fn = function(adm, t)
	if adm == t then return false, "that's you" end
	if t:Team() == TEAM_SPECTATOR or not t:Alive() then return false, t:Nick() .. " isn't surfing right now" end
	ToSurf(adm)
	SURF.Timer.PracticeTeleport(adm, t:GetPos(), t:EyeAngles())
	return true, "went to " .. t:Nick()
end }

ACT.bring = { perm = 1, target = "online", punish = true, ingame = true, fn = function(adm, t)
	if adm:Team() == TEAM_SPECTATOR or not adm:Alive() then return false, "you need to be surfing to bring someone" end
	ToSurf(t)
	SURF.Timer.PracticeTeleport(t, adm:GetPos(), adm:EyeAngles())
	SURF.Chat(t, acc, "[Admin] ", white, adm:Nick() .. " brought you to them. !r takes you back to the start.")
	return true, "brought " .. t:Nick()
end }

ACT.start = { perm = 1, target = "online", punish = true, fn = function(_, t)
	ToSurf(t)
	SURF.Timer.GoToStart(t, 0)
	return true, "sent " .. t:Nick() .. " to the start"
end }

ACT.respawn = { perm = 1, target = "online", punish = true, fn = function(_, t)
	if t:Team() == TEAM_SPECTATOR then SURF.Spec.Toggle(t) else t:Spawn() end
	return true, "respawned " .. t:Nick()
end }

ACT.slay = { perm = 1, target = "online", punish = true, fn = function(_, t)
	if not t:Alive() then return false, t:Nick() .. " isn't alive" end
	t:Kill()
	return true, "slayed " .. t:Nick()
end }

ACT.freeze = { perm = 1, target = "online", punish = true, fn = function(_, t)
	local on = not t:GetNW2Bool("surf_frozen", false)
	t:SetNW2Bool("surf_frozen", on)
	t:Freeze(on)
	if on then SURF.Timer.Stop(t, "frozen by an admin") end
	SURF.Chat(t, acc, "[Admin] ", white, on and "An admin froze you." or "You can move again.")
	return true, (on and "froze " or "unfroze ") .. t:Nick()
end }

ACT.spectate = { perm = 1, target = "online", ingame = true, nolog = true, fn = function(adm, t)
	if adm == t then return false, "that's you" end
	if t:Team() == TEAM_SPECTATOR or not t:Alive() then return false, t:Nick() .. " isn't surfing right now" end
	SURF.Spec.Watch(adm, t)
	return true, "spectating " .. t:Nick()
end }

ACT.mute = { perm = 1, target = "sid", punish = true, fn = function(adm, _, args, sid)
	local minutes = Minutes(args.minutes, 30)
	SetSanction(sid, "mute", minutes, Clean(args.reason), IsValid(adm) and adm:SteamID64() or "console")
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then SURF.Chat(p, red, "[Admin] ", white, "You were muted " .. TimeText(minutes) .. ". Chat commands still work.") end
	return true, "muted " .. A.KnownName(sid) .. " " .. TimeText(minutes)
end }

ACT.unmute = { perm = 1, target = "sid", fn = function(_, _, _, sid)
	SetSanction(sid, "mute", nil)
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then SURF.Chat(p, acc, "[Admin] ", white, "You can chat again.") end
	return true, "unmuted " .. A.KnownName(sid)
end }

ACT.gag = { perm = 1, target = "sid", punish = true, fn = function(adm, _, args, sid)
	local minutes = Minutes(args.minutes, 30)
	SetSanction(sid, "gag", minutes, Clean(args.reason), IsValid(adm) and adm:SteamID64() or "console")
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then SURF.Chat(p, red, "[Admin] ", white, "Your voice chat was turned off " .. TimeText(minutes) .. ".") end
	return true, "gagged " .. A.KnownName(sid) .. " " .. TimeText(minutes)
end }

ACT.ungag = { perm = 1, target = "sid", fn = function(_, _, _, sid)
	SetSanction(sid, "gag", nil)
	local p = player.GetBySteamID64(sid)
	if IsValid(p) then SURF.Chat(p, acc, "[Admin] ", white, "Your voice chat works again.") end
	return true, "ungagged " .. A.KnownName(sid)
end }

local function Portal(action, c)
	local fn = SURF.Portal and SURF.Portal.Actions and SURF.Portal.Actions[action]
	if not fn then return false, "not available" end
	return fn(c)
end

ACT.kick = { perm = 1, target = "online", punish = true, fn = function(adm, t, args)
	local reason = Clean(args.reason)
	SURF.Chat(nil, acc, "[Admin] ", white, t:Nick() .. " was kicked" .. (reason ~= "" and (": " .. reason) or "."))
	return Portal("kick", { steamid = t:SteamID64(), reason = reason ~= "" and reason or ("Kicked by " .. (IsValid(adm) and adm:Nick() or "an admin")) })
end }

ACT.ban = { perm = 1, target = "sid", punish = true, fn = function(adm, _, args, sid)
	local minutes = Minutes(args.minutes, 0)
	local reason = Clean(args.reason)
	local name = A.KnownName(sid)
	local ok, msg = Portal("ban", { steamid = sid, minutes = minutes, reason = reason, by = IsValid(adm) and adm:SteamID64() or "console" })
	if ok then SURF.Chat(nil, acc, "[Admin] ", white, name .. " was banned " .. TimeText(minutes) .. (reason ~= "" and (": " .. reason) or ".")) end
	return ok, msg
end }

ACT.unban = { perm = 1, target = "sid", fn = function(_, _, _, sid) return Portal("unban", { steamid = sid }) end }

ACT.deltime = { perm = 1, target = "sid", fn = function(_, _, args, sid)
	local style = SURF.StyleByID[tostring(args.style or "n")] and tostring(args.style or "n") or "n"
	local key = SURF.MapKey(0, style)
	if not SURF.DB.GetRecord(key, sid) then return false, A.KnownName(sid) .. " has no time on this map" .. SURF.Timer.StyleSuffix(style) end
	SURF.DB.DeleteTime(key, sid)
	return true, "deleted the time of " .. A.KnownName(sid) .. " on " .. game.GetMap() .. SURF.Timer.StyleSuffix(style)
end }

-- Owner only: VIP, coins, items, points, staff
ACT.givevip = { perm = 2, target = "sid", fn = function(_, _, args, sid)
	local days = math.Clamp(math.floor(tonumber(args.days) or 30), 0, 36500)
	local exp = SURF.VIP.Give(sid, days)
	return true, "VIP for " .. A.KnownName(sid) .. (exp == 0 and " (permanent)" or (" until " .. os.date("%Y-%m-%d", exp)))
end }

ACT.removevip = { perm = 2, target = "sid", fn = function(_, _, _, sid)
	SURF.VIP.Remove(sid)
	return true, "removed VIP from " .. A.KnownName(sid)
end }

ACT.coins = { perm = 2, target = "sid", fn = function(adm, _, args, sid)
	if not (SURF.Shop and SURF.Shop.GiveCoins) then return false, "the shop isn't loaded" end
	local amount = math.Clamp(math.floor(tonumber(args.amount) or 0), -1000000, 1000000)
	if amount == 0 then return false, "the amount is 0" end
	local bal = SURF.Shop.GiveCoins(sid, amount, "from " .. (IsValid(adm) and adm:Nick() or "an admin"))
	return true, string.format("%s%d coins for %s (now %d)", amount > 0 and "+" or "", amount, A.KnownName(sid), bal or 0)
end }

ACT.giveitem = { perm = 2, target = "sid", fn = function(adm, _, args, sid)
	if not (SURF.Shop and SURF.Shop.Grant) then return false, "the shop isn't loaded" end
	local key = tostring(args.item or "")
	if not SURF.ItemByKey[key] or not SURF.Shop.Grant(sid, key, "admin " .. (IsValid(adm) and adm:Nick() or "")) then return false, "unknown item" end
	return true, "gave " .. SURF.ItemByKey[key].name .. " to " .. A.KnownName(sid)
end }

ACT.removeitem = { perm = 2, target = "sid", fn = function(_, _, args, sid)
	if not (SURF.Shop and SURF.Shop.Revoke) then return false, "the shop isn't loaded" end
	local key = tostring(args.item or "")
	if not SURF.ItemByKey[key] then return false, "unknown item" end
	SURF.Shop.Revoke(sid, key)
	return true, "took " .. SURF.ItemByKey[key].name .. " from " .. A.KnownName(sid)
end }

ACT.points = { perm = 2, target = "sid", fn = function(adm, _, args, sid)
	if not SURF.Ranks.AdjustPoints then return false, "point changes need the latest shop update" end
	local delta = math.Clamp(math.floor(tonumber(args.amount) or 0), -1000000, 1000000)
	if delta == 0 then return false, "the amount is 0" end
	local total = SURF.Ranks.AdjustPoints(sid, delta, "from " .. (IsValid(adm) and adm:Nick() or "an admin"))
	return true, string.format("%s%d points for %s (admin changes now %+d)", delta > 0 and "+" or "", delta, A.KnownName(sid), total or 0)
end }

ACT.setadmin = { perm = 2, target = "sid", fn = function(adm, _, args, sid)
	if A.IsOwnerID(sid) then return false, A.KnownName(sid) .. " is an owner (OWNER_STEAMIDS in config.env)" end
	local on = args.on == true
	SetRank(sid, on and "admin" or nil, IsValid(adm) and adm:SteamID64() or "console")
	return true, (on and "made " .. A.KnownName(sid) .. " an admin" or ("removed admin from " .. A.KnownName(sid)))
end }

-- Server: no target
ACT.changelevel = { perm = 1, fn = function(_, _, args)
	local map = tostring(args.map or "")
	if not table.HasValue(SURF.MapVote.MapList(), map) then return false, "that map isn't installed" end
	return Portal("changelevel", { map = map })
end }

ACT.restartmap = { perm = 1, fn = function() return Portal("changelevel", { map = game.GetMap() }) end }

ACT.extend = { perm = 1, fn = function(_, _, args) return Portal("extend", { minutes = args.minutes }) end }

ACT.vote = { perm = 1, fn = function() return Portal("vote", {}) end }

ACT.hidemap = { perm = 1, fn = function(_, _, args)
	local map = tostring(args.map or "")
	if not table.HasValue(SURF.MapVote.MapList(), map) then return false, "that map isn't installed" end
	SURF.MapVote.SetHidden(map, args.hide ~= false)
	return true, (args.hide ~= false and "hid " or "unhid ") .. map
end }

ACT.announce = { perm = 1, fn = function(adm, _, args)
	local text = Clean(args.text, 160)
	if text == "" then return false, "the message is empty" end
	net.Start("surf.Announce")
	net.WriteString(text)
	net.WriteString(IsValid(adm) and adm:Nick() or "Server")
	net.Broadcast()
	SURF.Chat(nil, Color(255, 200, 40), "[Announcement] ", white, text)
	return true, "announced: " .. text
end }

-- Runs an action for an admin (nil = server console). Returns ok, message.
function A.Do(adm, action, args)
	args = istable(args) and args or {}
	local def = ACT[action]
	if not def then return false, "unknown action" end
	local lvl = A.Level(adm)
	if lvl < def.perm then return false, def.perm >= 2 and "only owners can do that" or "only admins can do that" end
	if def.ingame and not IsValid(adm) then return false, "only works from in game" end
	local t, sid
	if def.target then
		sid = tostring(args.sid or "")
		if not ValidID(sid) then return false, "no player picked" end
		t = player.GetBySteamID64(sid)
		if def.target == "online" and not IsValid(t) then return false, A.KnownName(sid) .. " isn't on the server" end
		if def.punish and A.Level(sid) >= lvl and sid ~= (IsValid(adm) and adm:SteamID64() or "") then
			return false, A.KnownName(sid) .. " has the same or a higher rank than you"
		end
	end
	local ok, a, b = pcall(def.fn, adm, IsValid(t) and t or nil, args, sid)
	local success, msg
	if ok then success, msg = a, b else success, msg = false, "error: " .. tostring(a) end
	if success and not def.nolog then
		A.Log(IsValid(adm) and adm:SteamID64() or "console", IsValid(adm) and adm:Nick() or "Console", action, sid,
			sid and A.KnownName(sid) or nil, msg, "game")
	end
	print(string.format("[Surf] Admin %s: %s %s: %s", IsValid(adm) and adm:Nick() or "console", action, sid or "", tostring(msg)))
	return success, msg
end

-- Data for the panel ---------------------------------------------------------------

local function PlayerRow(p)
	local r = SURF.Ranks.bySid[p:SteamID64()]
	return {
		sid = p:SteamID64(), name = p:Nick(), ping = p:Ping(), connected = math.floor(p:TimeConnected()),
		points = r and r.points or 0, rank = r and r.pos or 0, title = p:GetNW2Int("surf_title", 1), coins = p:GetNW2Int("surf_coins", 0),
		vip = SURF.IsVIP(p), level = A.Level(p), muted = A.Muted(p) ~= nil, gagged = A.Gagged(p) ~= nil,
		frozen = p:GetNW2Bool("surf_frozen", false), spec = p:Team() == TEAM_SPECTATOR, style = SURF.StyleOf(p).id,
		afk = SURF.AFK and SURF.AFK.IsAFK(p) or false,
	}
end

local DATA = {}

DATA.players = function()
	local out = {}
	for _, p in ipairs(player.GetHumans()) do out[#out + 1] = PlayerRow(p) end
	return { players = out }
end

DATA.player = function(_, args)
	local sid = tostring(args.sid or "")
	if not ValidID(sid) then return nil end
	local row = Q("SELECT name, playtime, firstseen, lastseen FROM surf_players WHERE steamid = %s", sid)
	row = row and row[1] or {}
	local p = player.GetBySteamID64(sid)
	local r = SURF.Ranks.bySid[sid]
	local vip = Q("SELECT expires FROM surf_vip WHERE steamid = %s", sid)
	local ban = Q("SELECT reason, admin, created, expires FROM surf_bans WHERE steamid = %s", sid)
	local sanctions = {}
	for _, s in ipairs(Q("SELECT kind, expires, reason FROM surf_sanctions WHERE steamid = %s", sid) or {}) do
		local exp = tonumber(s.expires) or 0
		if exp == 0 or exp > os.time() then sanctions[s.kind] = { expires = exp, reason = s.reason } end
	end
	local owned, coins = {}, 0
	if SURF.Shop and SURF.Shop.Inventory then
		local inv = SURF.Shop.Inventory(sid) or {}
		owned, coins = inv.owned or {}, tonumber(inv.coins) or 0
	else
		for _, it in ipairs(Q("SELECT item FROM surf_items WHERE steamid = %s", sid) or {}) do owned[#owned + 1] = it.item end
		if SURF.Shop and SURF.Shop.Balance then coins = SURF.Shop.Balance(sid) end
	end
	local times = Q("SELECT COUNT(*) AS n FROM surf_times WHERE steamid = %s", sid)
	local here = {}
	for _, st in ipairs(SURF.Config.Styles) do
		local t = SURF.DB.GetRecord(SURF.MapKey(0, st.id), sid)
		if t then here[#here + 1] = { style = st.id, time = t } end
	end
	return {
		sid = sid, name = IsValid(p) and p:Nick() or (row.name or sid), online = IsValid(p),
		playtime = (tonumber(row.playtime) or 0) + ((IsValid(p) and p.SurfJoinTime) and (os.time() - p.SurfJoinTime) or 0),
		firstseen = tonumber(row.firstseen), lastseen = tonumber(row.lastseen), known = row.name ~= nil,
		points = r and r.points or 0, rank = r and r.pos or 0, ranked = #SURF.Ranks.list,
		adjust = SURF.Ranks.Adjustment and SURF.Ranks.Adjustment(sid) or nil,
		coins = coins, owned = owned, times = times and tonumber(times[1].n) or 0, here = here,
		vip = (vip and vip[1]) and tonumber(vip[1].expires) or nil, vipNow = IsValid(p) and SURF.IsVIP(p) or nil,
		ban = (ban and ban[1]) and { reason = ban[1].reason, admin = ban[1].admin, created = tonumber(ban[1].created), expires = tonumber(ban[1].expires) } or nil,
		muted = sanctions.mute, gagged = sanctions.gag, frozen = IsValid(p) and p:GetNW2Bool("surf_frozen", false) or nil,
		level = A.Level(sid), staff = A.StaffRank(sid), owner = A.IsOwnerID(sid),
		features = { points = SURF.Ranks.AdjustPoints ~= nil, shop = SURF.Shop ~= nil and SURF.Shop.Grant ~= nil },
	}
end

DATA.find = function(_, args)
	local q = Clean(args.q, 64)
	if q == "" then return { q = q, results = {} } end
	local rows = Q("SELECT steamid, name, lastseen FROM surf_players WHERE steamid = %s OR name LIKE %s ORDER BY lastseen DESC LIMIT 40",
		q, "%" .. q .. "%")
	local out = {}
	for _, r in ipairs(rows or {}) do
		out[#out + 1] = { sid = r.steamid, name = r.name, lastseen = tonumber(r.lastseen), online = IsValid(player.GetBySteamID64(r.steamid)) }
	end
	return { q = q, results = out }
end

DATA.bans = function()
	local out = {}
	for _, r in ipairs(Q("SELECT steamid, name, reason, admin, created, expires FROM surf_bans ORDER BY created DESC LIMIT 150") or {}) do
		local exp = tonumber(r.expires) or 0
		if exp == 0 or exp > os.time() then
			out[#out + 1] = { sid = r.steamid, name = r.name, reason = string.sub(r.reason or "", 1, 120), admin = r.admin ~= "" and A.KnownName(r.admin) or "",
				created = tonumber(r.created), expires = exp }
		end
	end
	return { bans = out }
end

DATA.log = function()
	local out = {}
	-- Kept small: a net message holds 64 KB
	for _, r in ipairs(Q("SELECT * FROM surf_admin_log ORDER BY id DESC LIMIT 150") or {}) do
		out[#out + 1] = { date = tonumber(r.date), admin = r.admin_name ~= "" and r.admin_name or r.admin, action = r.action,
			target = r.target_name, detail = string.sub(r.detail or "", 1, 140), source = r.source }
	end
	return { log = out }
end

DATA.staff = function()
	local out = {}
	for id in string.gmatch(file.Read("surfline/owners.txt", "DATA") or "", "%d+") do
		if ValidID(id) then out[#out + 1] = { sid = id, name = A.KnownName(id), rank = "owner" } end
	end
	for _, r in ipairs(Q("SELECT steamid, rank, added_by, date FROM surf_staff ORDER BY date") or {}) do
		out[#out + 1] = { sid = r.steamid, name = A.KnownName(r.steamid), rank = r.rank,
			by = r.added_by ~= "" and A.KnownName(r.added_by) or "", date = tonumber(r.date) }
	end
	return { staff = out }
end

DATA.server = function()
	local maps = SURF.MapVote.Info(SURF.MapVote.MapList())
	return {
		map = game.GetMap(), tier = SURF.MapVote.Tier(game.GetMap()), zoned = SURF.Zones.HasTimer(0),
		timeleft = math.max(0, math.floor(GetGlobal2Int("surf_mapend") - CurTime())), vote = SURF.MapVote.active,
		players = #player.GetHumans(), max = game.MaxPlayers(), maps = maps,
	}
end

local function Send(ply, kind, data)
	net.Start("surf.AdminData")
	net.WriteString(kind)
	net.WriteTable(data or {})
	net.Send(ply)
end
A.Send = Send

-- Opens the panel for an admin (on a player when sid is given)
function A.Open(ply, sid)
	if A.Level(ply) < 1 then return end
	Send(ply, "open", { sid = sid, level = A.Level(ply) })
end

net.Receive("surf.Admin", function(_, ply)
	local msg = net.ReadTable()
	if not istable(msg) or A.Level(ply) < 1 then return end
	local now = CurTime()
	if msg.a == "data" then
		-- Up to 10 lookups a second (opening a page asks for a few at once)
		if (ply.SurfAdminWin or 0) < now then ply.SurfAdminWin, ply.SurfAdminN = now + 1, 0 end
		ply.SurfAdminN = ply.SurfAdminN + 1
		if ply.SurfAdminN > 10 then return end
		local fn = DATA[tostring(msg.what or "")]
		if not fn then return end
		local ok, data = pcall(fn, ply, msg)
		if ok and data then Send(ply, msg.what, data) end
		return
	end
	if (ply.SurfAdminAt or 0) > now then return end
	ply.SurfAdminAt = now + 0.15
	-- The panel shows the answer as a toast
	local ok, text = A.Do(ply, tostring(msg.a or ""), msg)
	Send(ply, "result", { ok = ok, msg = text, a = msg.a, sid = msg.sid })
end)

-- Chat commands -----------------------------------------------------------------------

-- A player on the server by SteamID or (part of) their name
function A.FindPlayer(query)
	query = string.Trim(tostring(query or ""))
	if query == "" then return nil, "no player given" end
	if string.StartWith(query, "STEAM_") then query = util.SteamIDTo64(query) end
	local p = player.GetBySteamID64(query)
	if IsValid(p) then return p end
	local q, found = string.lower(query), {}
	for _, pl in ipairs(player.GetHumans()) do
		local n = string.lower(pl:Nick())
		if n == q then return pl end
		if string.find(n, q, 1, true) then found[#found + 1] = pl end
	end
	if #found == 1 then return found[1] end
	if #found == 0 then return nil, "no player matches \"" .. query .. "\"" end
	return nil, #found .. " players match \"" .. query .. "\", type more of the name"
end

local Add = SURF.Commands.Add

local function Run(ply, action, args)
	local ok, msg = A.Do(ply, action, args)
	SURF.Chat(ply, ok and acc or red, "[Admin] ", white, ok and ("Done: " .. msg) or ("Couldn't do that: " .. msg))
end

-- !cmd <player> [rest...]: runs action on that player
local function OnPlayer(action, build)
	return function(ply, args)
		local t, err = A.FindPlayer(args[1])
		if not t then return SURF.Chat(ply, red, "[Admin] ", white, err) end
		local rest = {}
		for i = 2, #args do rest[#rest + 1] = args[i] end
		local a = build and build(rest) or {}
		a.sid = t:SteamID64()
		Run(ply, action, a)
	end
end

Add({ "admin", "adminmenu" }, "Open the admin panel (!admin [player])", function(ply, args)
	local t = args[1] and A.FindPlayer(args[1])
	A.Open(ply, IsValid(t) and t:SteamID64() or nil)
end, true)
Add({ "kick" }, "!kick <player> [reason]", OnPlayer("kick", function(r) return { reason = table.concat(r, " ") } end), true)
Add({ "ban" }, "!ban <player> <minutes, 0 = permanent> [reason]", OnPlayer("ban", function(r)
	return { minutes = tonumber(r[1]) or 0, reason = table.concat(r, " ", 2) }
end), true)
Add({ "mute" }, "!mute <player> [minutes, 0 = until unmuted] (chat)", OnPlayer("mute", function(r) return { minutes = tonumber(r[1]) or 30 } end), true)
Add({ "unmute" }, "!unmute <player>", OnPlayer("unmute"), true)
Add({ "gag" }, "!gag <player> [minutes, 0 = until ungagged] (voice)", OnPlayer("gag", function(r) return { minutes = tonumber(r[1]) or 30 } end), true)
Add({ "ungag" }, "!ungag <player>", OnPlayer("ungag"), true)
Add({ "goto" }, "!goto <player> teleports you to them", OnPlayer("goto"), true)
Add({ "bring" }, "!bring <player> teleports them to you", OnPlayer("bring"), true)
Add({ "slay" }, "!slay <player>", OnPlayer("slay"), true)
Add({ "freeze" }, "!freeze <player> (again to unfreeze)", OnPlayer("freeze"), true)
Add({ "announce", "ann" }, "!announce <text> shows a message on everyone's screen", function(ply, args)
	Run(ply, "announce", { text = table.concat(args, " ") })
end, true)
Add({ "extend" }, "!extend [minutes] adds time to this map", function(ply, args)
	Run(ply, "extend", { minutes = tonumber(args[1]) or 15 })
end, true)
