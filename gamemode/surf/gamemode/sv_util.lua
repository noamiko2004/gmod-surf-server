util.AddNetworkString("surf.Ready")
util.AddNetworkString("surf.Chat")
util.AddNetworkString("surf.Menu")
util.AddNetworkString("surf.Action")
util.AddNetworkString("surf.SetTrail")
util.AddNetworkString("surf.Zones")
util.AddNetworkString("surf.MapVote")
util.AddNetworkString("surf.MapVoteCast")
util.AddNetworkString("surf.Commands")

-- SURF.Chat(target or nil for everyone, Color, "text", Color, "text", ...)
-- Runs fn(...) and logs any error instead of stopping the caller, so one
-- failing step (or one failing hook, which stops the hooks after it) doesn't
-- take the rest down. The "[SURF] error" line is what the health check counts.
function SURF.Try(fn, ...)
	local ok, err = xpcall(fn, debug.traceback, ...)
	if not ok then ErrorNoHalt("[SURF] error: " .. tostring(err) .. "\n") end
	return ok
end

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

-- Discord invite: DISCORD_URL or the bot's invite (links.json, written by
-- deploy.sh), else the invite the bot drops in data/surfline/discord/invite.txt
function SURF.DiscordURL()
	if SURF.Config.DiscordURL ~= "" then return SURF.Config.DiscordURL end
	local url = string.Trim(file.Read("surfline/discord/invite.txt", "DATA") or "")
	if string.match(url, "^https://discord%.gg/[%w%-]+$") or string.match(url, "^https://discord%.com/invite/[%w%-]+$") then return url end
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
