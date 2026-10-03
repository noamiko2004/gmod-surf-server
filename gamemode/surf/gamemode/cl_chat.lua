-- Chat command hints: typing ! (or /) lists the matching commands with what
-- they do, above the chat box. Tab completes the first match, and pressing it
-- again moves on to the next one. The list comes from the server
-- (sv_commands.lua), so it holds only commands this player may use.
SURF.ChatHints = { cmds = {} }
local H = SURF.ChatHints
local MAX_ROWS = 7

net.Receive("surf.Commands", function()
	H.cmds = net.ReadTable() or {}
end)

local open, text = false, ""
local tabState -- { lead, matches, i, shown } while Tab cycles

hook.Add("StartChat", "surf_chat_hints", function() open, text, tabState = true, "", nil end)
hook.Add("FinishChat", "surf_chat_hints", function() open, text, tabState = false, "", nil end)
hook.Add("ChatTextChanged", "surf_chat_hints", function(t)
	text = t or ""
	if tabState and text ~= tabState.shown then tabState = nil end
end)

-- "!sty" -> "!", "sty"; nil when the text isn't a command
local function Parse(t)
	local lead, rest = string.match(t, "^([!/])(.*)$")
	if not lead then return nil end
	local word, args = string.match(rest, "^(%S*)(.*)$")
	return lead, string.lower(word or ""), args or ""
end

-- Commands with a name starting with word: { cmd, name } in the server's order
function H.Matches(word)
	local out = {}
	for _, c in ipairs(H.cmds) do
		for _, n in ipairs(c.n or {}) do
			if string.sub(n, 1, #word) == word then
				out[#out + 1] = { cmd = c, name = n }
				break
			end
		end
	end
	return out
end

local function Exact(word)
	for _, c in ipairs(H.cmds) do
		for _, n in ipairs(c.n or {}) do
			if n == word then return c end
		end
	end
end

hook.Add("OnChatTab", "surf_chat_hints", function(t)
	local lead, word, args = Parse(t)
	if not lead or args ~= "" then return end
	if not tabState then
		local matches = H.Matches(word)
		if #matches == 0 then return end
		tabState = { lead = lead, matches = matches, i = 0 }
	end
	tabState.i = tabState.i % #tabState.matches + 1
	tabState.shown = tabState.lead .. tabState.matches[tabState.i].name
	text = tabState.shown
	return tabState.shown
end)

local bg, rowHi = Color(10, 12, 18, 225), Color(255, 255, 255, 14)
local dim, adminCol = Color(160, 170, 185), Color(255, 110, 110)

-- "!style !styles" with the name being typed first
local function Names(cmd, name, lead)
	local others = {}
	for _, n in ipairs(cmd.n) do
		if n ~= name then others[#others + 1] = lead .. n end
	end
	return lead .. name, table.concat(others, " ")
end

local function Fit(str, room)
	if surface.GetTextSize(str) <= room then return str end
	while #str > 4 and surface.GetTextSize(str .. "...") > room do str = string.sub(str, 1, -2) end
	return str .. "..."
end

hook.Add("HUDPaint", "surf_chat_hints", function()
	if not open or #H.cmds == 0 then return end
	local lead, word, args = Parse(text)
	if not lead then return end
	local rows, footer
	if tabState then
		rows, footer = tabState.matches, "Tab: next match."
	elseif args ~= "" and Exact(word) then
		-- Typing the arguments: keep showing what the command does
		rows = { { cmd = Exact(word), name = word } }
	else
		rows = H.Matches(word)
		if #rows == 0 then
			footer = "No command starts with " .. lead .. word .. ". Type !help for the list."
		elseif #rows > MAX_ROWS then
			footer = (#rows - MAX_ROWS) .. " more. Keep typing, or press Tab to go through them."
		else
			footer = "Tab completes the command."
		end
	end
	-- While Tab cycles, keep the current match in view
	local first = 1
	local current = tabState and tabState.i or (word ~= "" and #rows > 0 and 1 or 0)
	if current > MAX_ROWS then first = current - MAX_ROWS + 1 end
	local last = math.min(#rows, first + MAX_ROWS - 1)

	surface.SetFont("SurfSmall")
	local cx, cy = chat.GetChatBoxPos()
	local w = math.max(chat.GetChatBoxSize(), 560)
	local nameW = 0
	for i = first, last do
		local main, others = Names(rows[i].cmd, rows[i].name, lead)
		nameW = math.max(nameW, surface.GetTextSize(main .. " " .. others))
	end
	nameW = math.min(nameW, w * 0.45)
	local h = 10 + (last - first + 1) * 24 + (footer and 22 or 0)
	local x, y = cx, cy - h - 6
	draw.RoundedBox(6, x, y, w, h, bg)
	for i = first, last do
		local r, ry = rows[i], y + 6 + (i - first) * 24
		if i == current then draw.RoundedBox(4, x + 4, ry, w - 8, 22, rowHi) end
		local main, others = Names(r.cmd, r.name, lead)
		draw.SimpleText(main, "SurfSmall", x + 12, ry + 11, SURF.Config.Accent, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local mw = surface.GetTextSize(main .. " ")
		if others ~= "" then
			draw.SimpleText(Fit(others, nameW - mw), "SurfSmall", x + 12 + mw, ry + 11, dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		local hx = x + 28 + nameW
		local help = (r.cmd.a and "[admin] " or "") .. (r.cmd.h or "")
		draw.SimpleText(Fit(help, x + w - 12 - hx), "SurfSmall", hx, ry + 11, r.cmd.a and adminCol or color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	if footer then
		draw.SimpleText(footer, "SurfSmall", x + 12, y + h - 14, dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
end)
