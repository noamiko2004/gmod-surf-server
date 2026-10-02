-- Start/end zones per map. Admins place them in game with !zone.
SURF.Zones = { data = {}, ents = {} }
local Zones = SURF.Zones
local TYPES = { start = true, ["end"] = true }

function Zones.Load()
	Zones.data = {}
	local rows = SURF.DB.Query("SELECT * FROM surf_zones WHERE map = %s", game.GetMap())
	for _, r in ipairs(rows or {}) do
		Zones.data[r.ztype] = {
			min = Vector(tonumber(r.x1), tonumber(r.y1), tonumber(r.z1)),
			max = Vector(tonumber(r.x2), tonumber(r.y2), tonumber(r.z2)),
		}
	end
end

function Zones.Spawn()
	for _, e in pairs(Zones.ents) do
		if IsValid(e) then e:Remove() end
	end
	Zones.ents = {}
	for ztype, z in pairs(Zones.data) do
		local e = ents.Create("surf_zone")
		e.min, e.max, e.ztype = z.min, z.max, ztype
		e:SetPos((z.min + z.max) / 2)
		e:Spawn()
		Zones.ents[ztype] = e
	end
end

function Zones.HasTimer()
	return Zones.data.start ~= nil and Zones.data["end"] ~= nil
end

function Zones.SendTo(target)
	net.Start("surf.Zones")
	net.WriteTable(Zones.data)
	if target then net.Send(target) else net.Broadcast() end
end

function Zones.Save(ztype, a, b)
	local mins = Vector(math.min(a.x, b.x), math.min(a.y, b.y), math.min(a.z, b.z))
	local maxs = Vector(math.max(a.x, b.x), math.max(a.y, b.y), math.max(a.z, b.z) + SURF.Config.ZoneHeight)
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

function Zones.Reload()
	Zones.Load()
	Zones.Spawn()
	Zones.SendTo(nil)
	for _, p in ipairs(player.GetAll()) do
		if p:Alive() and p:Team() ~= TEAM_SPECTATOR then SURF.Timer.Reset(p) end
	end
end

-- Where !r puts you: the floor of the start zone, or a map spawn
function Zones.StartPos()
	local z = Zones.data.start
	if not z then return nil end
	local center = (z.min + z.max) / 2
	return Vector(center.x, center.y, z.min.z + 4)
end

hook.Add("InitPostEntity", "surf_zones_init", function()
	Zones.Load()
	Zones.Spawn()
end)
hook.Add("PostCleanupMap", "surf_zones_cleanup", Zones.Spawn)

-- Two-step placement: run "!zone start" at one corner, then again at the opposite corner
function Zones.EditCommand(ply, args)
	local ztype = args[1]
	if ztype == "delete" and TYPES[args[2] or ""] then
		Zones.Delete(args[2])
		SURF.Chat(ply, SURF.Config.Accent, "[Zones] ", color_white, "Deleted the " .. args[2] .. " zone.")
		return
	end
	if not TYPES[ztype or ""] then
		SURF.Chat(ply, SURF.Config.Accent, "[Zones] ", color_white,
			"Stand in one corner and type !zone start (or !zone end), then walk to the opposite corner and type it again. !zone delete start|end removes one.")
		return
	end
	local pos = ply:GetPos()
	local edit = ply.SurfZoneEdit
	if edit and edit.ztype == ztype then
		Zones.Save(ztype, edit.p1, pos)
		ply.SurfZoneEdit = nil
		SURF.Chat(ply, SURF.Config.Accent, "[Zones] ", color_white, "Saved the " .. ztype .. " zone for " .. game.GetMap() .. ".")
	else
		ply.SurfZoneEdit = { ztype = ztype, p1 = pos }
		SURF.Chat(ply, SURF.Config.Accent, "[Zones] ", color_white, "First corner set. Go to the opposite corner and type !zone " .. ztype .. " again.")
	end
end
