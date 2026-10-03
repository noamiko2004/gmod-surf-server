-- Coins and the cosmetic shop (!shop). Coins are earned by playing and only
-- buy cosmetics (trails, chat tags, name colors, finish sounds). They are
-- separate from rank points and never affect runs. No random rewards.
--
-- Grant from the server console, RCON, the web portal or a store like Tebex:
--   surf_givecoins <steamid64 or STEAM_0:x:y> <amount, negative takes away>
--   surf_giveitem <steamid64 or STEAM_0:x:y> <item, e.g. trail:gold>
--   surf_removeitem <steamid64 or STEAM_0:x:y> <item>
SURF.Shop = {}
local S = SURF.Shop
local Q = SURF.DB.Query
local acc, white = SURF.Config.Accent, color_white
local GOLD = Color(255, 200, 40)

util.AddNetworkString("surf.ShopBuy")
util.AddNetworkString("surf.ShopEquip")

Q([[CREATE TABLE IF NOT EXISTS surf_coins (
	steamid TEXT PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0, earned INTEGER NOT NULL DEFAULT 0,
	daily INTEGER NOT NULL DEFAULT 0, rep_day INTEGER NOT NULL DEFAULT 0, repeats INTEGER NOT NULL DEFAULT 0)]])
Q([[CREATE TABLE IF NOT EXISTS surf_items (
	steamid TEXT NOT NULL, item TEXT NOT NULL, source TEXT, date INTEGER, PRIMARY KEY (steamid, item))]])
Q([[CREATE TABLE IF NOT EXISTS surf_equipped (
	steamid TEXT NOT NULL, slot TEXT NOT NULL, item TEXT NOT NULL, PRIMARY KEY (steamid, slot))]])
-- Every coin change, newest last (the portal shows a player's recent ones)
Q([[CREATE TABLE IF NOT EXISTS surf_coin_log (
	id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL, amount INTEGER NOT NULL, reason TEXT, date INTEGER)]])
Q([[CREATE INDEX IF NOT EXISTS surf_coin_log_sid ON surf_coin_log (steamid, id)]])

local function Day() return math.floor(os.time() / 86400) end

local function NormalizeID(id)
	id = string.Trim(tostring(id or ""))
	if string.StartWith(id, "STEAM_") then return util.SteamIDTo64(id) end
	if id:match("^7656%d+$") and #id == 17 then return id end
	return nil
end
S.NormalizeID = NormalizeID

local function Row(sid)
	local r = Q("SELECT * FROM surf_coins WHERE steamid = %s", sid)
	if r and r[1] then return r[1] end
	Q("INSERT OR IGNORE INTO surf_coins (steamid) VALUES (%s)", sid)
	return { coins = "0", earned = "0", daily = "0", rep_day = "0", repeats = "0" }
end

function S.Balance(sid)
	return tonumber(Row(sid).coins) or 0
end

-- Change a balance (never below 0). Returns the new balance.
function S.Add(sid, amount, reason)
	amount = math.floor(tonumber(amount) or 0)
	local cur = S.Balance(sid)
	if amount < 0 then amount = -math.min(cur, -amount) end
	if amount == 0 then return cur end
	Q("UPDATE surf_coins SET coins = coins + %d, earned = earned + %d WHERE steamid = %s", amount, math.max(0, amount), sid)
	Q("INSERT INTO surf_coin_log (steamid, amount, reason, date) VALUES (%s, %d, %s, %d)", sid, amount, reason or "", os.time())
	local ply = player.GetBySteamID64(sid)
	if IsValid(ply) then ply:SetNW2Int("surf_coins", cur + amount) end
	return cur + amount
end

-- Coins for playing: VIPs get the bonus. Says so in chat unless silent.
function S.Earn(ply, base, reason, silent)
	local mult = SURF.IsVIP(ply) and (1 + SURF.Config.Coins.VIPBonus) or 1
	local amount = math.floor(base * mult + 0.5)
	if amount <= 0 then return 0 end
	S.Add(ply:SteamID64(), amount, reason)
	if not silent then
		SURF.Chat(ply, GOLD, "[Coins] ", white, "+" .. amount .. " ", GOLD, "coins", white, " (" .. reason .. ")" .. (mult > 1 and ", VIP bonus included." or "."))
	end
	return amount
end

-- Items -------------------------------------------------------------------

function S.Owns(ply, key)
	return ply.SurfOwned ~= nil and ply.SurfOwned[key] == true
end

function S.CanUse(ply, it)
	if not it then return false end
	if SURF.ItemFree(it) then return true end
	if S.Owns(ply, it.key) then return true end
	return it.vip == true and SURF.IsVIP(ply)
end

-- Chat tag and name color are networked; the trail is sv_trails.lua's job
function S.ApplyLooks(ply)
	local eq = ply.SurfEquip or {}
	for _, slot in ipairs({ "tag", "color" }) do
		local it = eq[slot] and SURF.ItemByKey[slot .. ":" .. eq[slot]]
		ply:SetNW2String("surf_" .. slot, (it and S.CanUse(ply, it)) and it.id or "")
	end
end

function S.Load(ply)
	local sid = ply:SteamID64()
	ply:SetNW2Int("surf_coins", S.Balance(sid))
	ply.SurfOwned = {}
	for _, r in ipairs(Q("SELECT item FROM surf_items WHERE steamid = %s", sid) or {}) do ply.SurfOwned[r.item] = true end
	ply.SurfEquip = {}
	for _, r in ipairs(Q("SELECT slot, item FROM surf_equipped WHERE steamid = %s", sid) or {}) do ply.SurfEquip[r.slot] = r.item end
	S.ApplyLooks(ply)
end

function S.Grant(sid, key, source)
	if not SURF.ItemByKey[key] then return false end
	Q("INSERT OR IGNORE INTO surf_items (steamid, item, source, date) VALUES (%s, %s, %s, %d)", sid, key, source or "", os.time())
	local ply = player.GetBySteamID64(sid)
	if IsValid(ply) then
		ply.SurfOwned = ply.SurfOwned or {}
		ply.SurfOwned[key] = true
		S.ApplyLooks(ply)
	end
	return true
end

function S.Revoke(sid, key)
	Q("DELETE FROM surf_items WHERE steamid = %s AND item = %s", sid, key)
	local ply = player.GetBySteamID64(sid)
	if IsValid(ply) and ply.SurfOwned then
		ply.SurfOwned[key] = nil
		S.ApplyLooks(ply)
		SURF.Trails.Apply(ply)
	end
end

-- id "none" takes the item of that category off
function S.Equip(ply, cat, id)
	local it = SURF.ItemByKey[cat .. ":" .. tostring(id)]
	if id ~= "none" and not S.CanUse(ply, it) then return false end
	if cat == "trail" then
		ply.SurfTrail = id
		SURF.Trails.Apply(ply)
		SURF.DB.SavePlayer(ply)
		return true
	end
	if cat ~= "tag" and cat ~= "color" and cat ~= "sound" then return false end
	ply.SurfEquip = ply.SurfEquip or {}
	local sid = ply:SteamID64()
	if id == "none" then
		ply.SurfEquip[cat] = nil
		Q("DELETE FROM surf_equipped WHERE steamid = %s AND slot = %s", sid, cat)
	else
		ply.SurfEquip[cat] = id
		Q("REPLACE INTO surf_equipped (steamid, slot, item) VALUES (%s, %s, %s)", sid, cat, id)
	end
	S.ApplyLooks(ply)
	return true
end

function S.Equipped(ply)
	local eq = table.Copy(ply.SurfEquip or {})
	eq.trail = ply.SurfTrail or "none"
	return eq
end

-- Returns ok, message
function S.Buy(ply, key)
	local it = SURF.ItemByKey[key or ""]
	if not it then return false, "That item doesn't exist." end
	if S.CanUse(ply, it) then return false, "You already have " .. it.name .. "." end
	if not it.price then return false, it.name .. " is a VIP item. Type !vip to find out more." end
	local sid = ply:SteamID64()
	local have = S.Balance(sid)
	if have < it.price then
		return false, string.format("%s costs %d coins and you have %d. Finish maps to earn more.", it.name, it.price, have)
	end
	S.Add(sid, -it.price, "bought " .. key)
	S.Grant(sid, key, "coins")
	S.Equip(ply, it.cat, it.id)
	return true, string.format("You bought %s for %d coins. It's on now.", it.name, it.price)
end

-- Menu ----------------------------------------------------------------------

function S.MenuData(ply, tab, refresh)
	local owned = {}
	for key in pairs(ply.SurfOwned or {}) do owned[#owned + 1] = key end
	return {
		coins = S.Balance(ply:SteamID64()), owned = owned, equipped = S.Equipped(ply), vip = SURF.IsVIP(ply),
		tab = tab or "trail", refresh = refresh or nil, url = SURF.Config.StoreURL, rates = SURF.Config.Coins,
	}
end

function S.OpenMenu(ply, tab, refresh)
	SURF.Menu.Open(ply, "shop", S.MenuData(ply, tab, refresh))
end

local function Busy(ply)
	if (ply.SurfShopAt or 0) > CurTime() then return true end
	ply.SurfShopAt = CurTime() + 0.3
	return false
end

net.Receive("surf.ShopBuy", function(_, ply)
	local key = net.ReadString()
	if Busy(ply) then return end
	local ok, msg = S.Buy(ply, key)
	SURF.Chat(ply, GOLD, "[Shop] ", white, msg)
	if ok then ply:SendLua([[surface.PlaySound("garrysmod/content_downloaded.wav")]]) end
	local it = SURF.ItemByKey[key]
	S.OpenMenu(ply, it and it.cat, true)
end)

net.Receive("surf.ShopEquip", function(_, ply)
	local cat, id = net.ReadString(), net.ReadString()
	if Busy(ply) then return end
	if not S.Equip(ply, cat, id) then
		local it = SURF.ItemByKey[cat .. ":" .. id]
		local msg = "That item doesn't exist."
		if it and it.price then
			msg = "Buy " .. it.name .. " first (" .. it.price .. " coins)."
		elseif it then
			msg = it.name .. " is a VIP item. Type !vip to find out more."
		end
		SURF.Chat(ply, GOLD, "[Shop] ", white, msg)
	end
	S.OpenMenu(ply, cat, true)
end)

-- The trail menu (F3) is the shop's trail tab now
local oldOpen = SURF.Menu.Open
function SURF.Menu.Open(ply, kind, data)
	if kind == "trails" then return oldOpen(ply, "shop", S.MenuData(ply, "trail")) end
	oldOpen(ply, kind, data)
end

-- Earning -------------------------------------------------------------------

local function Halve(n, track, style)
	if track > 0 then n = n / 2 end
	if style ~= "n" then n = n / 2 end
	return n
end

hook.Add("SurfFinish", "surf_shop", function(ply, time, res, track, style)
	local C = SURF.Config.Coins
	local base, why = 0, {}
	local where = (track > 0 and ("bonus " .. track) or game.GetMap()) .. SURF.Timer.StyleSuffix(style)
	if res.improved and not res.oldPB then
		base = Halve(C.FirstFinish + C.PerTier * math.max(1, SURF.MapVote.Tier(game.GetMap())), track, style)
		why[#why + 1] = "first finish on " .. where
	elseif res.improved then
		base = C.Improved
		why[#why + 1] = "new personal best"
	else
		local r, today = Row(ply:SteamID64()), Day()
		local n = tonumber(r.rep_day) == today and tonumber(r.repeats) or 0
		if n < C.RepeatPerDay then
			Q("UPDATE surf_coins SET rep_day = %d, repeats = %d WHERE steamid = %s", today, n + 1, ply:SteamID64())
			base = C.Repeat
			why[#why + 1] = "finished " .. where
		end
	end
	if res.wr then
		base = base + Halve(C.Record, track, style)
		why[#why + 1] = "server record"
	end
	if base > 0 then S.Earn(ply, base, table.concat(why, " + ")) end

	local snd = ply.SurfEquip and ply.SurfEquip.sound and SURF.ItemByKey["sound:" .. ply.SurfEquip.sound]
	if snd and S.CanUse(ply, snd) then ply:EmitSound(snd.sound, 80, 100, 0.9) end
end)

-- Daily bonus when the player is in and can read chat
hook.Add("SurfPlayerReady", "surf_shop", function(ply)
	local sid, today = ply:SteamID64(), Day()
	Row(sid)
	local r = Q("SELECT daily FROM surf_coins WHERE steamid = %s", sid)
	if r and r[1] and tonumber(r[1].daily) ~= today then
		Q("UPDATE surf_coins SET daily = %d WHERE steamid = %s", today, sid)
		S.Earn(ply, SURF.Config.Coins.Daily, "daily visit, spend coins in !shop")
	end
end)

-- Coins for time spent surfing (not spectating, not away)
local PLAY_EVERY = 300
function S.PayPlaytime()
	for _, p in ipairs(player.GetHumans()) do
		if p:Team() ~= TEAM_SPECTATOR and SURF.AFK.IdleTime(p) < PLAY_EVERY then
			S.Earn(p, SURF.Config.Coins.Playtime, "playtime", true)
		end
	end
end
timer.Create("surf_shop_playtime", PLAY_EVERY, 0, S.PayPlaytime)

-- Catalog for the web portal (garrysmod/data/surfline/portal/shop.json) -------

local function Hex(c) return c and string.format("#%02x%02x%02x", c.r, c.g, c.b) or nil end

function S.WriteCatalog()
	local cats = {}
	for _, cat in ipairs(SURF.ShopCategories) do
		local items = {}
		for _, it in ipairs(cat.list) do
			if it.id ~= "none" then
				items[#items + 1] = { key = it.key, id = it.id, name = it.name, price = it.price or 0, vip = it.vip == true,
					color = Hex(it.color), rainbow = it.rainbow == true }
			end
		end
		cats[#cats + 1] = { id = cat.id, name = cat.name, items = items }
	end
	file.CreateDir("surfline/portal")
	file.Write("surfline/portal/shop.json", util.TableToJSON({ updated = os.time(), coins = SURF.Config.Coins, categories = cats }))
end
hook.Add("InitPostEntity", "surf_shop", S.WriteCatalog)

-- Commands ------------------------------------------------------------------

local Add = SURF.Commands.Add

local TABS = { trail = "trail", trails = "trail", tag = "tag", tags = "tag", color = "color", colors = "color",
	sound = "sound", sounds = "sound", vip = "vip" }

Add({ "shop", "items", "inventory", "inv" }, "Spend coins on trails, chat tags, name colors and finish sounds", function(ply, args)
	S.OpenMenu(ply, TABS[string.lower(args[1] or "")] or "trail")
end)

Add({ "coins", "balance", "money", "credits" }, "How many coins you have and how to earn more", function(ply)
	local C = SURF.Config.Coins
	SURF.Chat(ply, GOLD, "[Coins] ", white, "You have ", GOLD, S.Balance(ply:SteamID64()) .. " coins", white, ". Type !shop to spend them.")
	SURF.Chat(ply, GOLD, "[Coins] ", white, string.format("Earn them by finishing maps (%d+ for a first finish, more on harder tiers), personal bests (%d), records (%d), playing (%d every 5 min) and a daily visit (%d).",
		C.FirstFinish + C.PerTier, C.Improved, C.Record, C.Playtime, C.Daily) .. ((C.VIPBonus > 0) and string.format(" VIPs earn %d%% more.", C.VIPBonus * 100) or ""))
end)

-- Console / RCON / portal / store --------------------------------------------

local function ConsoleOnly(ply)
	return not IsValid(ply) or ply:IsSuperAdmin()
end

function S.GiveCoins(sid, amount, reason)
	local bal = S.Add(sid, amount, reason or "granted")
	local ply = player.GetBySteamID64(sid)
	if IsValid(ply) and amount > 0 then
		SURF.Chat(ply, GOLD, "[Coins] ", white, "You received ", GOLD, amount .. " coins", white, ". Type !shop to spend them.")
	end
	return bal
end

concommand.Add("surf_givecoins", function(ply, _, args)
	if not ConsoleOnly(ply) then return end
	local sid, amount = NormalizeID(args[1]), math.floor(tonumber(args[2] or "") or 0)
	if not sid or amount == 0 then
		print("[Surf] usage: surf_givecoins <steamid64|STEAM_0:x:y> <amount, negative takes away>")
		return
	end
	print("[Surf] " .. sid .. " now has " .. S.GiveCoins(sid, amount, "console") .. " coins")
end)

concommand.Add("surf_giveitem", function(ply, _, args)
	if not ConsoleOnly(ply) then return end
	local sid, key = NormalizeID(args[1]), string.lower(args[2] or "")
	if not sid or not S.Grant(sid, key, "console") then
		print("[Surf] usage: surf_giveitem <steamid64|STEAM_0:x:y> <item, e.g. trail:gold>")
		return
	end
	print("[Surf] gave " .. key .. " to " .. sid)
end)

concommand.Add("surf_removeitem", function(ply, _, args)
	if not ConsoleOnly(ply) then return end
	local sid, key = NormalizeID(args[1]), string.lower(args[2] or "")
	if not sid or key == "" then print("[Surf] usage: surf_removeitem <steamid64|STEAM_0:x:y> <item>") return end
	S.Revoke(sid, key)
	print("[Surf] removed " .. key .. " from " .. sid)
end)
