local vote = { active = false, choices = {}, tiers = {}, tally = {}, endTime = 0, mine = nil }

net.Receive("surf.MapVote", function()
	vote.active = net.ReadBool()
	vote.choices = net.ReadTable()
	vote.tiers = net.ReadTable()
	vote.tally = net.ReadTable()
	vote.endTime = net.ReadFloat()
	if not vote.active then vote.mine = nil end
end)

local function Label(choice, i)
	if choice == "__extend" then return "Extend current map" end
	local tier = vote.tiers[i] or 0
	return tier > 0 and (choice .. "  (T" .. tier .. ")") or choice
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
	local UI = SURF.UI
	local C, S = UI.Col, UI.S
	local acc = UI.Accent()
	local total = 0
	for _, n in pairs(vote.tally) do total = total + n end
	local w, rowH, gap = S(380), S(32), S(4)
	local h = S(56) + #vote.choices * (rowH + gap) + S(28)
	local x, y = ScrW() - w - S(16), ScrH() / 2 - h / 2
	draw.RoundedBox(8, x, y, w, h, Color(13, 15, 21, 235))
	draw.RoundedBox(2, x + S(14), y + S(16), S(4), S(20), acc)
	draw.SimpleText("Map vote", "SurfUI_Title", x + S(26), y + S(26), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	local left = math.max(0, math.ceil(vote.endTime - CurTime()))
	draw.SimpleText(left .. "s", "SurfUI_Head", x + w - S(16), y + S(26), left <= 5 and C.red or C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	for i, choice in ipairs(vote.choices) do
		local ry = y + S(50) + (i - 1) * (rowH + gap)
		local n = vote.tally[choice] or 0
		local bw = w - S(20)
		local mine = vote.mine == i
		draw.RoundedBox(6, x + S(10), ry, bw, rowH, Color(255, 255, 255, 8))
		if n > 0 and total > 0 then draw.RoundedBox(6, x + S(10), ry, math.max(S(12), bw * n / total), rowH, UI.Alpha(acc, mine and 90 or 45)) end
		if mine then draw.RoundedBox(2, x + S(10), ry + S(7), S(3), rowH - S(14), acc) end
		draw.SimpleText(tostring(i), "SurfUI_Small", x + S(26), ry + rowH / 2, mine and acc or C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		draw.SimpleText(UI.Fit(Label(choice, i), "SurfUI_Body", bw - S(80)), "SurfUI_Body", x + S(42), ry + rowH / 2, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(tostring(n), "SurfUI_Body", x + w - S(24), ry + rowH / 2, n > 0 and acc or C.faint, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
	draw.SimpleText(vote.mine and "You can change your vote" or ("Press 1-" .. #vote.choices .. " to vote"), "SurfUI_Small", x + w / 2, y + h - S(16), C.faint, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
end
