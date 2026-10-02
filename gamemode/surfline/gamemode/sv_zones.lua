-- Zones per map: start, end and checkpoints (cp) for the main track (0) and
-- bonuses (1..n). Ready-made zones come from data/surfline/zones/<map>.json
-- (see zones/README.md); zones an admin places with !zone override them.
SURF.Zones = { list = {}, ents = {}, source = "none", cpCount = {} }
local Zones = SURF.Zones
local TYPES = { start = true, ["end"] = true }
local JSON_TYPES = { start = "start", ["end"] = "end", stage = "cp", checkpoint = "cp" }

local function Box(a, b)
	return Vector(math.min(a.x, b.x), math.min(a.y, b.y), math.min(a.z, b.z)),
		Vector(math.max(a.x, b.x), math.max(a.y, b.y), math.max(a.z, b.z))
end

local function LoadAdminZones(map)
	local rows = SURF.DB.Query("SELECT * FROM surf_zones WHERE map = %s", map)
	local out = {}
	for _, r in ipairs(rows or {}) do
		local mins, maxs = Box(Vector(tonumber(r.x1), tonumber(r.y1), tonumber(r.z1)), Vector(tonumber(r.x2), tonumber(r.y2), tonumber(r.z2)))
		out[#out + 1] = { ztype = r.ztype, track = 0, index = 0, min = mins, max = maxs }
	end
	return out
end

local function LoadMapZones(map)
	local raw = file.Read("surfline/zones/" .. map .. ".json", "DATA")
	if not raw then return {} end
	local data = util.JSONToTable(raw) or {}
	local out = {}
	for _, z in ipairs(data) do
		local ztype = JSON_TYPES[z.type]
		if ztype and z.point_a and z.point_b then
			local mins, maxs = Box(Vector(z.point_a[1], z.point_a[2], z.point_a[3]), Vector(z.point_b[1], z.point_b[2], z.point_b[3]))
			out[#out + 1] = { ztype = ztype, track = tonumber(z.track) or 0, index = tonumber(z.data) or 0, min = mins, max = maxs }
		end
	end
	return out
end

function Zones.Load()
	local map = game.GetMap()
	Zones.list = LoadAdminZones(map)
	Zones.source = "admin"
	if #Zones.list == 0 then
		Zones.list = LoadMapZones(map)
		Zones.source = #Zones.list > 0 and "map" or "none"
	end
	Zones.cpCount = {}
	for _, z in ipairs(Zones.list) do
		if z.ztype == "cp" then
			Zones.cpCount[z.track] = math.max(Zones.cpCount[z.track] or 0, z.index)
		end
	end
	SetGlobal2Int("surf_cpcount", Zones.cpCount[0] or 0)
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
	Zones.Load()
	Zones.Spawn()
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
		SURF.Chat(ply, acc, "[Zones] ", white, "Removed in-game zones. Using " .. (Zones.source == "map" and "the ready-made zones" or "no zones") .. " now.")
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
			.. "In-game zones replace the map's ready-made zones (checkpoints and bonuses too). !zone reset goes back, !zone info shows what's loaded.")
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
