-- Zones per map: start, end and checkpoints (cp) for the main track (0) and
-- bonuses (1..n). Where they come from, in order:
--   1. zones an admin placed with !zone (start/end of the main track; each
--      one replaces the ready-made zone of the same type)
--   2. ready-made zones in data/surfline/zones/<map>.json (see zones/README.md),
--      checked against the map so a different version of it is caught
--   3. timer triggers built into the map itself (mod_zone_start and friends)
SURF.Zones = { list = {}, ents = {}, source = "none", cpCount = {}, yaw = {}, adminYaw = {} }
local Zones = SURF.Zones
local TYPES = { start = true, ["end"] = true }
local JSON_TYPES = { start = "start", ["end"] = "end", stage = "cp", checkpoint = "cp" }
local ZONED_FILE = "surfline/zoned_maps.txt"
local BAD_FILE = "surfline/bad_zones.txt"

local function Box(a, b)
	return Vector(math.min(a.x, b.x), math.min(a.y, b.y), math.min(a.z, b.z)),
		Vector(math.max(a.x, b.x), math.max(a.y, b.y), math.max(a.z, b.z))
end

local function LoadAdminZones(map)
	local rows = SURF.DB.Query("SELECT * FROM surf_zones WHERE map = %s", map)
	local out = {}
	for _, r in ipairs(rows or {}) do
		local mins, maxs = Box(Vector(tonumber(r.x1), tonumber(r.y1), tonumber(r.z1)), Vector(tonumber(r.x2), tonumber(r.y2), tonumber(r.z2)))
		out[#out + 1] = { ztype = r.ztype, track = 0, index = 0, min = mins, max = maxs, admin = true }
	end
	return out
end

-- Bounds of a trigger brush in the map, found by its targetname
local function TriggerBox(name)
	for _, e in ipairs(ents.FindByName(name)) do
		if IsValid(e) then
			local mins, maxs = e:WorldSpaceAABB()
			if mins and maxs and mins ~= maxs then return mins, maxs end
		end
	end
end

-- A zone fits the map if its middle is inside the world and not in a wall
local function Fits(z)
	local c = (z.min + z.max) / 2
	return util.IsInWorld(c) and bit.band(util.PointContents(c), CONTENTS_SOLID) == 0
end

local function LoadMapZones(map)
	local raw = file.Read("surfline/zones/" .. map .. ".json", "DATA")
	if not raw then return {} end
	local data = util.JSONToTable(raw) or {}
	local out = {}
	for _, z in ipairs(data) do
		local ztype = JSON_TYPES[z.type]
		local mins, maxs
		if ztype and z.hook then
			mins, maxs = TriggerBox(z.hook)
		elseif ztype and z.point_a and z.point_b then
			mins, maxs = Box(Vector(z.point_a[1], z.point_a[2], z.point_a[3]), Vector(z.point_b[1], z.point_b[2], z.point_b[3]))
		end
		if mins then
			out[#out + 1] = { ztype = ztype, track = tonumber(z.track) or 0, index = tonumber(z.data) or 0, min = mins, max = maxs, hooked = z.hook ~= nil }
		end
	end
	-- The zones were made on another server's copy of the map. If its start
	-- or end sits in a wall or outside the world here, this copy is different.
	local fits = {}
	for _, z in ipairs(out) do
		if z.hooked or Fits(z) then
			fits[#fits + 1] = z
		elseif z.track == 0 and z.ztype ~= "cp" then
			print("[Surf] Ready-made " .. z.ztype .. " zone doesn't fit this version of " .. map .. ", ignoring its zones")
			return {}, true
		end
	end
	return fits, false
end

-- Timer triggers some maps ship with (shavit/SurfTimer/KSF naming)
local TRIGGER_PATTERNS = {
	{ "^mod_zone_start$", "start" }, { "^mod_zone_end$", "end" },
	{ "^climb_startzone$", "start" }, { "^climb_endzone$", "end" },
	{ "^start_zone$", "start" }, { "^end_zone$", "end" },
	{ "^zone_start$", "start" }, { "^zone_end$", "end" },
	{ "^map_start$", "start" }, { "^map_end$", "end" },
	{ "^timer_startzone$", "start" }, { "^timer_endzone$", "end" },
	{ "^mod_zone_bonus_(%d+)_start$", "start", "bonus" }, { "^mod_zone_bonus_(%d+)_end$", "end", "bonus" },
	{ "^climb_bonus(%d+)_startzone$", "start", "bonus" }, { "^climb_bonus(%d+)_endzone$", "end", "bonus" },
	{ "^bonus(%d+)_start$", "start", "bonus" }, { "^bonus(%d+)_end$", "end", "bonus" },
	{ "^b(%d+)_start$", "start", "bonus" }, { "^b(%d+)_end$", "end", "bonus" },
	{ "^mod_zone_checkpoint_(%d+)$", "cp", "cp" }, { "^checkpoint_(%d+)$", "cp", "cp" },
	{ "^stage(%d+)_start$", "cp", "stage" }, { "^s(%d+)_start$", "cp", "stage" },
}

local function LoadTriggerZones()
	local out, seen = {}, {}
	for _, e in ipairs(ents.FindByClass("trigger_*")) do
		local name = string.lower(e:GetName() or "")
		if name ~= "" then
			for _, p in ipairs(TRIGGER_PATTERNS) do
				local num = string.match(name, p[1])
				if num then
					local n = tonumber(num) or 0
					local track = p[3] == "bonus" and n or 0
					local index = p[3] == "cp" and n or (p[3] == "stage" and n or 0)
					if p[3] == "stage" and n <= 1 then break end -- stage 1 is the map start
					local key = p[2] .. track .. ":" .. index
					local mins, maxs = e:WorldSpaceAABB()
					if not seen[key] and mins then
						seen[key] = true
						out[#out + 1] = { ztype = p[2], track = track, index = index, min = mins, max = maxs, hooked = true }
					end
					break
				end
			end
		end
	end
	local has = {}
	for _, z in ipairs(out) do has[z.ztype .. z.track] = true end
	if not (has.start0 and has.end0) then return {} end
	return out
end

-- Remembers which maps turned out to have working zones (zoned_maps.txt) and
-- which didn't (bad_zones.txt), so the map vote, the start map pick
-- (start.sh) and the map installer (maps.py) only count maps with a start
-- and an end.
local function ListFile(path)
	local set = {}
	for line in string.gmatch(file.Read(path, "DATA") or "", "[^\n]+") do set[string.Trim(line)] = true end
	return set
end

local function Remember(path, map, on)
	local set = ListFile(path)
	if (set[map] or false) == on then return end
	set[map] = on or nil
	local lines = {}
	for m in pairs(set) do lines[#lines + 1] = m end
	table.sort(lines)
	file.Write(path, table.concat(lines, "\n") .. "\n")
end

function Zones.KnownZoned() return ListFile(ZONED_FILE) end
function Zones.KnownBad() return ListFile(BAD_FILE) end

function Zones.Load()
	local map = game.GetMap()
	local admin = LoadAdminZones(map)
	local ready = LoadMapZones(map)
	local source = #ready > 0 and "map" or "none"
	if #ready == 0 then
		ready = LoadTriggerZones()
		if #ready > 0 then source = "triggers" end
	end
	-- Admin zones replace the ready-made zone of the same type on the main track
	local list, replaced = {}, {}
	for _, z in ipairs(admin) do
		list[#list + 1] = z
		replaced[z.ztype] = true
	end
	for _, z in ipairs(ready) do
		if not (z.track == 0 and replaced[z.ztype]) then list[#list + 1] = z end
	end
	if #admin > 0 then source = source == "none" and "admin" or ("admin+" .. source) end
	Zones.list, Zones.source = list, source

	Zones.cpCount = {}
	for _, z in ipairs(Zones.list) do
		if z.ztype == "cp" then
			Zones.cpCount[z.track] = math.max(Zones.cpCount[z.track] or 0, z.index)
		end
	end
	SetGlobal2Int("surf_cpcount", Zones.cpCount[0] or 0)
	Zones.yaw, Zones.adminYaw = {}, {}
	for _, r in ipairs(SURF.DB.Query("SELECT track, yaw FROM surf_start_angles WHERE map = %s", map) or {}) do
		Zones.adminYaw[tonumber(r.track) or 0] = tonumber(r.yaw)
	end
	-- No working start and end on the main track (ready-made zones that don't
	-- fit this copy of the map, trigger names it doesn't have, or no zones at
	-- all): the map stays out of votes and the start map pick until an admin
	-- places zones with !zone.
	local works = Zones.HasTimer(0)
	Remember(BAD_FILE, map, not works and string.StartWith(map, SURF.Config.MapPrefix))
	Remember(ZONED_FILE, map, works)
end

function Zones.Spawn()
	for _, e in pairs(Zones.ents) do
		if IsValid(e) then e:Remove() end
	end
	Zones.ents = {}
	for _, z in ipairs(Zones.list) do
		local e = ents.Create("surf_zone")
		e.min, e.max, e.zone = z.min, z.max, z
		e:SetPos((z.min + z.max) / 2)
		e:Spawn()
		Zones.ents[#Zones.ents + 1] = e
	end
end

function Zones.Find(ztype, track, index)
	for _, z in ipairs(Zones.list) do
		if z.ztype == ztype and z.track == track and (not index or z.index == index) then return z end
	end
end

function Zones.HasTimer(track)
	track = track or 0
	return Zones.Find("start", track) ~= nil and Zones.Find("end", track) ~= nil
end

-- Bonus tracks that have a start and an end
function Zones.Bonuses()
	local out = {}
	for _, z in ipairs(Zones.list) do
		if z.ztype == "start" and z.track > 0 and Zones.HasTimer(z.track) and not table.HasValue(out, z.track) then
			out[#out + 1] = z.track
		end
	end
	table.sort(out)
	return out
end

local function Floor(z)
	local c = (z.min + z.max) / 2
	return Vector(c.x, c.y, z.min.z + 2)
end

-- Where !r / !b / !stage put you
function Zones.StartPos(track)
	local z = Zones.Find("start", track or 0)
	return z and Floor(z)
end

function Zones.StagePos(index)
	local z = Zones.Find("cp", 0, index)
	return z and Floor(z)
end

-- Which way you face in a start zone. An admin's choice (!zone angle) wins.
-- Otherwise the map's own spawn points near the start decide: surf maps point
-- them at the first ramp, so the way most of them face is used, unless that
-- looks straight into a wall. Failing that, the most open way out.
local SPAWN_CLASSES = { "info_player_counterterrorist", "info_player_terrorist", "info_player_start", "info_player_deathmatch" }
local SPAWN_RANGE = 1024 -- how far outside the start zone a spawn point may be
local MIN_OPEN = 160     -- room a direction needs in front of you

local function DistToBox(p, z)
	local dx = math.max(z.min.x - p.x, 0, p.x - z.max.x)
	local dy = math.max(z.min.y - p.y, 0, p.y - z.max.y)
	local dz = math.max(z.min.z - p.z, 0, p.z - z.max.z)
	return math.sqrt(dx * dx + dy * dy + dz * dz)
end

-- How far you can see at eye height when facing yaw
local function OpenAhead(pos, yaw)
	local r = math.rad(yaw)
	local eye = pos + Vector(0, 0, 48)
	local tr = util.TraceLine({ start = eye, endpos = eye + Vector(math.cos(r), math.sin(r), 0) * 2048, mask = MASK_PLAYERSOLID_BRUSHONLY })
	return tr.Fraction * 2048
end

function Zones.FindStartYaw(track)
	local z = Zones.Find("start", track or 0)
	if not z then return nil end
	local pos = Floor(z)
	-- Spawn points vote in 30 degree groups; the nearest one gives the exact yaw
	local groups = {}
	for _, cls in ipairs(SPAWN_CLASSES) do
		for _, e in ipairs(ents.FindByClass(cls)) do
			if IsValid(e) and DistToBox(e:GetPos(), z) <= SPAWN_RANGE then
				local yaw = math.NormalizeAngle(e:GetAngles().y)
				local key = math.Round(yaw / 30) % 12
				local g = groups[key] or { n = 0, near = math.huge }
				groups[key] = g
				g.n = g.n + 1
				local d = (e:GetPos() - pos):Length()
				if d < g.near then g.near, g.yaw = d, yaw end
			end
		end
	end
	local list = {}
	for _, g in pairs(groups) do list[#list + 1] = g end
	table.sort(list, function(a, b) if a.n ~= b.n then return a.n > b.n end return a.near < b.near end)
	for _, g in ipairs(list) do
		if OpenAhead(pos, g.yaw) >= MIN_OPEN then return g.yaw, "spawn" end
	end
	local best, bestYaw = -1, 0
	for i = 0, 15 do
		local yaw = i * 22.5
		local d = OpenAhead(pos, yaw)
		if d > best + 1 then best, bestYaw = d, yaw end
	end
	return math.NormalizeAngle(bestYaw), "open"
end

function Zones.StartYaw(track)
	track = track or 0
	if Zones.adminYaw[track] then return Zones.adminYaw[track] end
	if Zones.yaw[track] == nil then Zones.yaw[track] = Zones.FindStartYaw(track) or false end
	return Zones.yaw[track] or nil
end

function Zones.SaveYaw(track, yaw)
	SURF.DB.Query("REPLACE INTO surf_start_angles (map, track, yaw) VALUES (%s, %d, %f)", game.GetMap(), track, yaw)
	Zones.adminYaw[track] = yaw
end

function Zones.SendTo(target)
	local out = {}
	for i, z in ipairs(Zones.list) do
		out[i] = { t = z.ztype, k = z.track, i = z.index, a = z.min, b = z.max }
	end
	net.Start("surf.Zones")
	net.WriteTable(out)
	if target then net.Send(target) else net.Broadcast() end
end

function Zones.Save(ztype, a, b)
	local mins, maxs = Box(a, b)
	maxs.z = maxs.z + SURF.Config.ZoneHeight
	-- Avoid paper-thin boxes that players can skip over in one tick
	for _, axis in ipairs({ "x", "y" }) do
		if maxs[axis] - mins[axis] < 32 then
			local mid = (maxs[axis] + mins[axis]) / 2
			mins[axis], maxs[axis] = mid - 16, mid + 16
		end
	end
	SURF.DB.Query("REPLACE INTO surf_zones (map, ztype, x1, y1, z1, x2, y2, z2) VALUES (%s, %s, %f, %f, %f, %f, %f, %f)",
		game.GetMap(), ztype, mins.x, mins.y, mins.z, maxs.x, maxs.y, maxs.z)
	Zones.Reload()
end

function Zones.Delete(ztype)
	SURF.DB.Query("DELETE FROM surf_zones WHERE map = %s AND ztype = %s", game.GetMap(), ztype)
	Zones.Reload()
end

function Zones.ResetToMap()
	SURF.DB.Query("DELETE FROM surf_zones WHERE map = %s", game.GetMap())
	SURF.DB.Query("DELETE FROM surf_start_angles WHERE map = %s", game.GetMap())
	Zones.Reload()
end

function Zones.Reload()
	Zones.Load()
	Zones.Spawn()
	Zones.SendTo(nil)
	for _, p in ipairs(player.GetHumans()) do
		if p:Alive() and p:Team() ~= TEAM_SPECTATOR then SURF.Timer.Reset(p) end
	end
end

hook.Add("InitPostEntity", "surf_zones_init", function()
	-- Protected: an error here would stop the other map-start hooks
	if SURF.Try(Zones.Load) then SURF.Try(Zones.Spawn) end
end)
hook.Add("PostCleanupMap", "surf_zones_cleanup", Zones.Spawn)

-- Two-step placement: run "!zone start" at one corner, then again at the opposite corner
function Zones.EditCommand(ply, args)
	local acc, white = SURF.Config.Accent, color_white
	local ztype = args[1]
	if ztype == "delete" and TYPES[args[2] or ""] then
		Zones.Delete(args[2])
		SURF.Chat(ply, acc, "[Zones] ", white, "Deleted the " .. args[2] .. " zone.")
		return
	end
	if ztype == "reset" then
		Zones.ResetToMap()
		SURF.Chat(ply, acc, "[Zones] ", white, "Removed in-game zones. Using " .. (Zones.source == "none" and "no zones" or "the ready-made zones") .. " now.")
		return
	end
	if ztype == "angle" then
		local track = ply.SurfTrack or 0
		if not Zones.Find("start", track) then
			SURF.Chat(ply, acc, "[Zones] ", white, "This map has no start zone to face from yet.")
			return
		end
		local yaw = math.Round(math.NormalizeAngle(ply:EyeAngles().y), 1)
		Zones.SaveYaw(track, yaw)
		SURF.Chat(ply, acc, "[Zones] ", white, "Players now face this way in the " .. (track > 0 and ("bonus " .. track) or "main") .. " start. !zone reset undoes it.")
		return
	end
	if ztype == "info" then
		SURF.Chat(ply, acc, "[Zones] ", white, string.format("%s: %d zones (%s), %d checkpoints, %d bonuses.",
			game.GetMap(), #Zones.list, Zones.source, Zones.cpCount[0] or 0, #Zones.Bonuses()))
		return
	end
	if not TYPES[ztype or ""] then
		SURF.Chat(ply, acc, "[Zones] ", white,
			"Stand in one corner and type !zone start (or !zone end), then walk to the opposite corner and type it again. "
			.. "Your zone replaces the ready-made one of the same type. !zone angle makes players face the way you look in the start. "
			.. "!zone reset goes back, !zone info shows what's loaded.")
		return
	end
	local pos = ply:GetPos()
	local edit = ply.SurfZoneEdit
	if edit and edit.ztype == ztype then
		Zones.Save(ztype, edit.p1, pos)
		ply.SurfZoneEdit = nil
		SURF.Chat(ply, acc, "[Zones] ", white, "Saved the " .. ztype .. " zone for " .. game.GetMap() .. ".")
	else
		ply.SurfZoneEdit = { ztype = ztype, p1 = pos }
		SURF.Chat(ply, acc, "[Zones] ", white, "First corner set. Go to the opposite corner and type !zone " .. ztype .. " again.")
	end
end
