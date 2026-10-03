util.AddNetworkString("surf.Ready")
util.AddNetworkString("surf.Chat")
util.AddNetworkString("surf.Menu")
util.AddNetworkString("surf.Action")
util.AddNetworkString("surf.SetTrail")
util.AddNetworkString("surf.Zones")
util.AddNetworkString("surf.MapVote")
util.AddNetworkString("surf.MapVoteCast")

-- SURF.Chat(target or nil for everyone, Color, "text", Color, "text", ...)
function SURF.Chat(target, ...)
	local args = { ... }
	net.Start("surf.Chat")
	net.WriteUInt(#args, 8)
	for _, v in ipairs(args) do
		if IsColor(v) or (type(v) == "table" and v.r) then
			net.WriteBool(true)
			net.WriteColor(Color(v.r, v.g, v.b, v.a or 255))
		else
			net.WriteBool(false)
			net.WriteString(tostring(v))
		end
	end
	if target then net.Send(target) else net.Broadcast() end
end

SURF.Menu = {}
function SURF.Menu.Open(ply, kind, data)
	net.Start("surf.Menu")
	net.WriteString(kind)
	net.WriteTable(data or {})
	net.Send(ply)
end

-- Client-only toggles (hide players, etc.)
function SURF.ClientAction(ply, action)
	net.Start("surf.Action")
	net.WriteString(action)
	net.Send(ply)
end

function SURF.Humans()
	return player.GetHumans()
end

-- The web portal's address (deploy.sh writes it when the portal is on)
local portalURL
function SURF.PortalURL()
	if portalURL == nil then
		local url = string.Trim(file.Read("surfline/portal_url.txt", "DATA") or "")
		portalURL = string.match(url, "^https://[%w%.%-:]+$") and url or false
	end
	return portalURL or nil
end
