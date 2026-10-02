SURF.Trails = {}

function SURF.Trails.CanUse(ply, trail)
	return trail ~= nil and (not trail.vip or SURF.IsVIP(ply))
end

function SURF.Trails.Apply(ply)
	if IsValid(ply.SurfTrailEnt) then ply.SurfTrailEnt:Remove() end
	ply.SurfTrailEnt = nil
	ply:SetNW2Entity("surf_trail", NULL)
	if not ply:Alive() or ply:Team() == TEAM_SPECTATOR then return end

	local trail = SURF.TrailByID[ply.SurfTrail or "none"]
	if not SURF.Trails.CanUse(ply, trail) or not trail.mat then return end

	local ent = util.SpriteTrail(ply, 0, trail.color, false, 16, 0, 1.5, 1 / 16 * 0.5, trail.mat .. ".vmt")
	if IsValid(ent) then
		ply.SurfTrailEnt = ent
		ply:SetNW2Entity("surf_trail", ent)
	end
end

net.Receive("surf.SetTrail", function(_, ply)
	local id = net.ReadString()
	local trail = SURF.TrailByID[id]
	if not trail then return end
	if not SURF.Trails.CanUse(ply, trail) then
		SURF.Chat(ply, Color(255, 200, 40), "[VIP] ", color_white, trail.name .. " is a VIP trail. Type !vip to find out more.")
		return
	end
	ply.SurfTrail = id
	SURF.Trails.Apply(ply)
	SURF.Chat(ply, SURF.Config.Accent, "[Trails] ", color_white, "Trail set to " .. trail.name .. ".")
end)
