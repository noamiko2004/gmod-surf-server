-- New server records go to a Discord channel through a webhook. Set
-- DISCORD_WEBHOOK in config.env (Discord: channel settings > Integrations >
-- Webhooks > New Webhook > Copy Webhook URL); deploy.sh hands it to the game
-- in data/surfline/webhook.txt.
SURF.Discord = {}
local D = SURF.Discord

local webhook
function D.URL()
	if webhook == nil then
		local url = string.Trim(file.Read("surfline/webhook.txt", "DATA") or "")
		local ok = string.match(url, "^https://discord%.com/api/webhooks/%d+/[%w_%-]+$")
			or string.match(url, "^https://discordapp%.com/api/webhooks/%d+/[%w_%-]+$")
			or string.match(url, "^https://ptb%.discord%.com/api/webhooks/%d+/[%w_%-]+$")
			or string.match(url, "^https://canary%.discord%.com/api/webhooks/%d+/[%w_%-]+$")
		webhook = ok and url or false
	end
	return webhook or nil
end

-- Player names are shown as typed, not as Discord formatting
local function Escape(s)
	return (string.gsub(tostring(s or ""), "([%*_~`|>\\%[%]])", "\\%1"))
end
D.Escape = Escape

function D.RecordMessage(info)
	local where = "**" .. Escape(info.map) .. "**"
	if info.track > 0 then where = where .. " (Bonus " .. info.track .. ")" end
	local style = SURF.StyleByID[info.style or "n"]
	if style and style.id ~= "n" then where = where .. " on **" .. style.name .. "**" end
	local desc = "**" .. Escape(info.name) .. "** set the server record on " .. where .. " with **" .. SURF.FormatTime(info.time) .. "**"
	if info.oldWR and info.oldWR > 0 then
		desc = desc .. string.format(" (-%.3f", info.oldWR - info.time)
			.. ((info.oldName and info.oldName ~= "" and info.oldName ~= info.name) and (", beating " .. Escape(info.oldName)) or "") .. ")"
	end
	local embed = {
		title = "New server record",
		description = desc .. ".",
		color = 16762920, -- gold
	}
	if info.server and info.server ~= "" then embed.footer = { text = info.server } end
	local portal = SURF.PortalURL()
	if portal then embed.url = portal .. "/maps/" .. info.map end
	if info.tier and info.tier > 0 then
		embed.fields = { { name = "Tier", value = tostring(info.tier), inline = true } }
	end
	return {
		username = info.brand,
		allowed_mentions = { parse = {} }, -- never ping anyone
		embeds = { embed },
	}
end

function D.Post(msg)
	local url = D.URL()
	if not url or not HTTP then return false end
	HTTP({
		method = "POST", url = url, type = "application/json", body = util.TableToJSON(msg),
		success = function(code, body)
			if code >= 300 then print("[Surf] Discord webhook answered " .. code .. ": " .. string.sub(body or "", 1, 200)) end
		end,
		failed = function(err) print("[Surf] Discord webhook failed: " .. tostring(err)) end,
	})
	return true
end

hook.Add("SurfNewRecord", "surf_discord", function(ply, time, res, track, style)
	if not D.URL() then return end
	D.Post(D.RecordMessage({
		map = game.GetMap(), track = track or 0, style = style, name = ply:Nick(), time = time,
		oldWR = res.oldWR, oldName = res.oldName, tier = SURF.MapVote.Tier(game.GetMap()),
		brand = SURF.Config.Name, server = GetHostName(),
	}))
end)
