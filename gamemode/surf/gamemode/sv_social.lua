-- Chat life: join messages with title and rank, rank-up announcements and a
-- tip every few minutes.
SURF.Social = {}
local Social = SURF.Social
local acc, white, gold = SURF.Config.Accent, color_white, Color(255, 200, 40)

hook.Add("SurfPlayerReady", "surf_join_message", function(ply)
	if ply.SurfFirstVisit then
		SURF.Chat(nil, acc, "[Join] ", white, ply:Nick() .. " joined for the first time. Welcome!")
		return
	end
	local title = SURF.Config.Titles[ply:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
	local pos = ply:GetNW2Int("surf_rankpos", 0)
	local detail = title.name .. (pos > 0 and (", #" .. pos) or "")
	if SURF.IsVIP(ply) then
		SURF.Chat(nil, gold, "[VIP] ", Color(255, 220, 120), ply:Nick(), white, " joined (", title.color, detail, white, ").")
	else
		SURF.Chat(nil, acc, "[Join] ", white, ply:Nick() .. " joined (", title.color, detail, white, ").")
	end
end)

hook.Add("SurfRankUp", "surf_rankup_message", function(ply, idx)
	local title = SURF.Config.Titles[idx]
	if not title then return end
	SURF.Chat(nil, acc, "[Rank] ", white, ply:Nick() .. " ranked up to ", title.color, title.name, white, "!")
	ply:SendLua([[surface.PlaySound("garrysmod/content_downloaded.wav")]])
end)

-- Tips ----------------------------------------------------------------------

local nextTip = 0
function Social.NextTip()
	local tips = SURF.Config.Tips
	for _ = 1, #tips do
		nextTip = nextTip % #tips + 1
		local tip = tips[nextTip]
		if string.find(tip, "{portal}", 1, true) then
			local url = SURF.PortalURL()
			tip = url and string.Replace(tip, "{portal}", url) or nil
		end
		if tip then return tip end
	end
end

timer.Create("surf_tips", SURF.Config.TipInterval, 0, function()
	if #player.GetHumans() == 0 or SURF.MapVote.active then return end
	local tip = Social.NextTip()
	if tip then SURF.Chat(nil, acc, "[Tip] ", white, tip) end
end)
