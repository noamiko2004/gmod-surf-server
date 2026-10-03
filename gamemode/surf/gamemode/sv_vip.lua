-- VIP is cosmetic only (VIP trails, chat tags and name color, a gold name,
-- and 50% more coins for the cosmetic shop). Facepunch's server guidelines
-- allow selling cosmetics and access; nothing here affects runs.
--
-- Grant from the server console, RCON, or a store like Tebex:
--   surf_givevip <steamid64 or STEAM_0:x:y> <days, 0 = permanent>
--   surf_removevip <steamid64 or STEAM_0:x:y>
SURF.VIP = {}

local function NormalizeID(id)
	id = string.Trim(tostring(id or ""))
	if string.StartWith(id, "STEAM_") then return util.SteamIDTo64(id) end
	if id:match("^7656%d+$") then return id end
	return nil
end

function SURF.VIP.Load(ply)
	local vip = ply:IsUserGroup("vip") or ply:IsAdmin()
	local row = SURF.DB.Query("SELECT expires FROM surf_vip WHERE steamid = %s", ply:SteamID64())
	if row and row[1] then
		local exp = tonumber(row[1].expires)
		if exp == 0 or exp > os.time() then
			vip = true
			ply.SurfVIPExpires = exp
		end
	end
	ply:SetNW2Bool("surf_vip", vip)
end

function SURF.VIP.Give(sid64, days)
	local row = SURF.DB.Query("SELECT expires FROM surf_vip WHERE steamid = %s", sid64)
	local now = os.time()
	local expires
	if days <= 0 then
		expires = 0
	else
		local cur = (row and row[1]) and tonumber(row[1].expires) or now
		if cur == 0 then return 0 end -- already permanent
		expires = math.max(cur, now) + days * 86400
	end
	SURF.DB.Query("REPLACE INTO surf_vip (steamid, expires) VALUES (%s, %d)", sid64, expires)
	local ply = player.GetBySteamID64(sid64)
	if IsValid(ply) then
		SURF.VIP.Load(ply)
		SURF.Trails.Apply(ply)
		SURF.Shop.ApplyLooks(ply)
		SURF.Chat(nil, Color(255, 200, 40), "[VIP] ", color_white, ply:Nick() .. " just became a VIP. Thank you for supporting the server!")
	end
	return expires
end

function SURF.VIP.Remove(sid64)
	SURF.DB.Query("DELETE FROM surf_vip WHERE steamid = %s", sid64)
	local ply = player.GetBySteamID64(sid64)
	if IsValid(ply) then
		SURF.VIP.Load(ply)
		SURF.Trails.Apply(ply)
		SURF.Shop.ApplyLooks(ply)
	end
end

local function ConsoleOnly(ply)
	return not IsValid(ply) or ply:IsSuperAdmin()
end

concommand.Add("surf_givevip", function(ply, _, args)
	if not ConsoleOnly(ply) then return end
	local sid = NormalizeID(args[1])
	local days = tonumber(args[2] or "30") or 30
	if not sid then
		print("[Surf] usage: surf_givevip <steamid64|STEAM_0:x:y> <days, 0 = permanent>")
		return
	end
	local exp = SURF.VIP.Give(sid, days)
	print("[Surf] VIP granted to " .. sid .. (exp == 0 and " permanently" or (" until " .. os.date("%Y-%m-%d", exp))))
end)

concommand.Add("surf_removevip", function(ply, _, args)
	if not ConsoleOnly(ply) then return end
	local sid = NormalizeID(args[1])
	if not sid then print("[Surf] usage: surf_removevip <steamid64|STEAM_0:x:y>") return end
	SURF.VIP.Remove(sid)
	print("[Surf] VIP removed from " .. sid)
end)

-- Expire VIPs that run out mid-session
timer.Create("surf_vip_check", 600, 0, function()
	for _, p in ipairs(player.GetHumans()) do
		if p.SurfVIPExpires and p.SurfVIPExpires > 0 and p.SurfVIPExpires < os.time() then
			p.SurfVIPExpires = nil
			SURF.VIP.Load(p)
			SURF.Trails.Apply(p)
			SURF.Shop.ApplyLooks(p)
		end
	end
end)
