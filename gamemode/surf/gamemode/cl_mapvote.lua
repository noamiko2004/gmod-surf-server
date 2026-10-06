local vote = { active = false, choices = {}, tiers = {}, tally = {}, endTime = 0, mine = nil }

net.Receive("surf.MapVote", function()
	vote.active = net.ReadBool()
	vote.choices = net.ReadTable()
	vote.tiers = net.ReadTable()
	vote.tally = net.ReadTable()
	vote.endTime = net.ReadFloat()
	if not vote.active then vote.mine = nil end
end)

local function Label(v, choice, i)
	if choice == "__extend" then return "Extend current map" end
	local tier = v.tiers[i] or 0
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

-- Shown in the editor so the vote can be placed
local SAMPLE = { active = true, choices = { "surf_mesa", "surf_utopia_njv", "surf_kitsune", "__extend" }, tiers = { 1, 1, 2 },
	tally = { surf_mesa = 2, surf_kitsune = 1 }, mine = 1 }

local function Current(ctx)
	if vote.active then return vote end
	if ctx.preview then
		SAMPLE.endTime = CurTime() + 20
		return SAMPLE
	end
end

-- A part of the HUD (cl_hud.lua), so players can move it with !hud
SURF.HUD.Add("mapvote", {
	name = "Map vote",
	size = function(ctx)
		local v = Current(ctx)
		local S = SURF.UI.S
		return S(380), S(56) + #(v and v.choices or {}) * (S(32) + S(4)) + S(28)
	end,
	pos = { 1, 0.5, -16, 0 },
	show = function() return vote.active end,
	draw = function(w, h, ctx)
		local v = Current(ctx)
		if not v then return end
		local UI = SURF.UI
		local C, S = UI.Col, UI.S
		local acc = UI.Accent()
		local total = 0
		for _, n in pairs(v.tally) do total = total + n end
		local rowH, gap = S(32), S(4)
		draw.RoundedBox(8, 0, 0, w, h, Color(13, 15, 21, 235))
		draw.RoundedBox(2, S(14), S(16), S(4), S(20), acc)
		draw.SimpleText("Map vote", "SurfUI_Title", S(26), S(26), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local left = math.max(0, math.ceil(v.endTime - CurTime()))
		draw.SimpleText(left .. "s", "SurfUI_Head", w - S(16), S(26), left <= 5 and C.red or C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		for i, choice in ipairs(v.choices) do
			local ry = S(50) + (i - 1) * (rowH + gap)
			local n = v.tally[choice] or 0
			local bw = w - S(20)
			local mine = v.mine == i
			draw.RoundedBox(6, S(10), ry, bw, rowH, Color(255, 255, 255, 8))
			if n > 0 and total > 0 then draw.RoundedBox(6, S(10), ry, math.max(S(12), bw * n / total), rowH, UI.Alpha(acc, mine and 90 or 45)) end
			if mine then draw.RoundedBox(2, S(10), ry + S(7), S(3), rowH - S(14), acc) end
			draw.SimpleText(tostring(i), "SurfUI_Small", S(26), ry + rowH / 2, mine and acc or C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			draw.SimpleText(UI.Fit(Label(v, choice, i), "SurfUI_Body", bw - S(80)), "SurfUI_Body", S(42), ry + rowH / 2, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(tostring(n), "SurfUI_Body", w - S(24), ry + rowH / 2, n > 0 and acc or C.faint, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		end
		draw.SimpleText(v.mine and "You can change your vote" or ("Press 1-" .. #v.choices .. " to vote"), "SurfUI_Small", w / 2, h - S(16), C.faint, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end,
})
