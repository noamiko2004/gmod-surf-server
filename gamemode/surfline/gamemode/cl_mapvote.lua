local vote = { active = false, choices = {}, tally = {}, endTime = 0, mine = nil }

net.Receive("surf.MapVote", function()
	vote.active = net.ReadBool()
	vote.choices = net.ReadTable()
	vote.tally = net.ReadTable()
	vote.endTime = net.ReadFloat()
	if not vote.active then vote.mine = nil end
end)

local function Label(choice)
	if choice == "__extend" then return "Extend current map" end
	return choice
end

-- Number keys (slot1..slot9) cast votes while a vote is open
hook.Add("PlayerBindPress", "surf_mapvote", function(_, bind, pressed)
	if not vote.active or not pressed then return end
	local n = tonumber(string.match(bind, "^slot(%d)$") or "")
	if n and vote.choices[n] then
		vote.mine = n
		net.Start("surf.MapVoteCast")
		net.WriteUInt(n, 4)
		net.SendToServer()
		surface.PlaySound("buttons/button14.wav")
		return true
	end
end)

function GM:DrawMapVote()
	if not vote.active then return end
	local acc = SURF.Config.Accent
	local w = 320
	local rowH = 28
	local h = 50 + #vote.choices * rowH + 10
	local x, y = ScrW() - w - 16, ScrH() / 2 - h / 2
	draw.RoundedBox(8, x, y, w, h, Color(10, 12, 18, 220))
	local left = math.max(0, math.ceil(vote.endTime - CurTime()))
	draw.SimpleText("Map vote (" .. left .. "s)", "SurfLarge", x + 14, y + 22, acc, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	for i, choice in ipairs(vote.choices) do
		local ry = y + 50 + (i - 1) * rowH
		if vote.mine == i then draw.RoundedBox(4, x + 6, ry, w - 12, rowH - 2, Color(acc.r, acc.g, acc.b, 60)) end
		draw.SimpleText(i .. ". " .. Label(choice), "SurfMedium", x + 14, ry + rowH / 2, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(tostring(vote.tally[choice] or 0), "SurfMedium", x + w - 14, ry + rowH / 2, acc, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
end
