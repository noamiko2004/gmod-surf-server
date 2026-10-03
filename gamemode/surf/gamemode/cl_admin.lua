-- The admin panel: !admin, F1 > Admin, or right-click a player on the
-- scoreboard. Pages: Players (who is on, plus anyone who ever joined),
-- Server, Bans, Staff and Log. The server checks every action again
-- (sv_admin.lua), so this file only decides what to show. Also draws the
-- banner for !announce.
SURF.AdminPanel = {}
local AP = SURF.AdminPanel
local UI = SURF.UI
local C = UI.Col
local S = UI.S

local win
local ui = {} -- panels of the page on screen
local state = { page = "players", q = "", level = 0, data = {} }

-- 0 player, 1 admin, 2 owner
local function Level()
	local me = LocalPlayer()
	if not IsValid(me) then return state.level end
	return math.max(state.level, me:IsSuperAdmin() and 2 or (me:IsAdmin() and 1 or 0))
end
AP.Level = Level

local function Send(msg)
	net.Start("surf.Admin")
	net.WriteTable(msg)
	net.SendToServer()
end

local function Ask(what, extra)
	local m = extra or {}
	m.a, m.what = "data", what
	Send(m)
end

-- Runs an action on the server; the answer comes back as "result"
function AP.Act(action, sid, args)
	local m = args or {}
	m.a, m.sid = action, sid
	Send(m)
end
local Act = AP.Act

-- Text helpers -------------------------------------------------------------------

local function Date(t)
	if not t or t <= 0 then return "" end
	return os.date("%Y-%m-%d %H:%M", t)
end

local function Ago(t)
	if not t or t <= 0 then return "never" end
	local d = os.time() - t
	if d < 120 then return "just now" end
	if d < 7200 then return math.floor(d / 60) .. " minutes ago" end
	if d < 172800 then return math.floor(d / 3600) .. " hours ago" end
	return math.floor(d / 86400) .. " days ago"
end

local function Ends(exp)
	if exp == nil then return "" end
	if exp == 0 then return "never" end
	return Date(exp)
end

local function Hours(sec)
	sec = math.floor(sec or 0)
	local h, m = math.floor(sec / 3600), math.floor(sec % 3600 / 60)
	if h > 0 then return h .. "h " .. m .. "m" end
	return m .. "m"
end

local function Clock(sec)
	sec = math.max(0, math.floor(sec or 0))
	return string.format("%d:%02d", math.floor(sec / 60), sec % 60)
end

local function RankColor(level)
	if level == 2 then return C.gold end
	if level == 1 then return C.red end
	return nil
end

-- Dialogs shared by the panel and the scoreboard menu ----------------------------------

local MUTE_TIMES = { { "10 min", 10 }, { "1 hour", 60 }, { "1 day", 1440 }, { "Until lifted", 0 } }
local BAN_TIMES = { { "1 hour", 60 }, { "1 day", 1440 }, { "1 week", 10080 }, { "Forever", 0 } }

local function AskMinutes(title, text, default, choices, onOk)
	UI.Prompt(title, text, tostring(default), function(v)
		onOk(math.max(0, math.floor(tonumber(v) or default)))
	end, { numeric = true, choices = choices, placeholder = "Minutes" })
end

function AP.Mute(sid, name)
	AskMinutes("Mute " .. name, "Turn off their chat for how many minutes? 0 = until you unmute them. Chat commands still work.", 30, MUTE_TIMES,
		function(m) Act("mute", sid, { minutes = m }) end)
end

function AP.Gag(sid, name)
	AskMinutes("Gag " .. name, "Turn off their voice chat for how many minutes? 0 = until you ungag them.", 30, MUTE_TIMES,
		function(m) Act("gag", sid, { minutes = m }) end)
end

function AP.Kick(sid, name)
	UI.Prompt("Kick " .. name, "Why? (optional) They can join again right away.", "", function(r)
		Act("kick", sid, { reason = r })
	end, { allowEmpty = true, okText = "Kick", danger = true, placeholder = "Reason" })
end

function AP.Ban(sid, name)
	AskMinutes("Ban " .. name, "Ban for how many minutes? 0 = forever.", 1440, BAN_TIMES, function(m)
		UI.Prompt("Ban " .. name, "Why? They see this when they try to join.", "", function(r)
			Act("ban", sid, { minutes = m, reason = r })
		end, { allowEmpty = true, okText = "Ban", danger = true, placeholder = "Reason" })
	end)
end

-- Admin options for a right-click menu (scoreboard, lists)
function AP.AddOptions(m, sid, name)
	if Level() < 1 or not sid then return end
	local online = IsValid(player.GetBySteamID64(sid))
	local sub, opt = m:AddSubMenu("Admin")
	opt:SetIcon("icon16/shield.png")
	sub:AddOption("Open in the admin panel", function() AP.Open("players", sid) end):SetIcon("icon16/application_view_detail.png")
	if online then
		sub:AddOption("Go to", function() Act("goto", sid) end):SetIcon("icon16/arrow_right.png")
		sub:AddOption("Bring", function() Act("bring", sid) end):SetIcon("icon16/arrow_left.png")
		sub:AddOption("Send to the start", function() Act("start", sid) end):SetIcon("icon16/flag_green.png")
		sub:AddOption("Spectate", function() Act("spectate", sid) end):SetIcon("icon16/eye.png")
		sub:AddOption("Freeze or unfreeze", function() Act("freeze", sid) end):SetIcon("icon16/lock.png")
		sub:AddOption("Slay", function() Act("slay", sid) end):SetIcon("icon16/cross.png")
	end
	sub:AddSpacer()
	sub:AddOption("Mute chat...", function() AP.Mute(sid, name) end):SetIcon("icon16/comment_delete.png")
	sub:AddOption("Gag voice...", function() AP.Gag(sid, name) end):SetIcon("icon16/sound_mute.png")
	if online then sub:AddOption("Kick...", function() AP.Kick(sid, name) end):SetIcon("icon16/door_out.png") end
	local ban = sub:AddOption("Ban...", function() AP.Ban(sid, name) end)
	ban:SetIcon("icon16/delete.png")
	ban.uiColor = C.red
end

-- Window -----------------------------------------------------------------------------

local PAGES = {
	{ id = "players", name = "Players", icon = "icon16/group.png" },
	{ id = "server", name = "Server", icon = "icon16/server.png" },
	{ id = "bans", name = "Bans", icon = "icon16/delete.png" },
	{ id = "staff", name = "Staff", icon = "icon16/shield.png" },
	{ id = "log", name = "Log", icon = "icon16/script.png" },
}
local BUILD, DRAW = {}, {}

function AP.IsOpen() return IsValid(win) end

function AP.Show(page)
	if not IsValid(win) then return AP.Open(page) end
	state.page = page
	win.side:SetActive(page)
	win.body:Clear()
	ui = {}
	BUILD[page](win.body)
end

-- page: one of PAGES (default: the last one); sid opens Players on that player
function AP.Open(page, sid)
	if Level() < 1 then return end
	if sid then
		page = "players"
		if state.sid ~= sid then state.sid, state.data.player = sid, nil end
	end
	page = BUILD[page or ""] and page or state.page
	if not IsValid(win) then
		win = UI.Frame("Admin", 1020, 680, { id = "admin", sub = "Players, server, bans and the log",
			right = function() return Level() >= 2 and "Owner" or "Admin", Level() >= 2 and C.gold or C.red end })
		win.side = UI.Sidebar(win, PAGES, page, function(id) AP.Show(id) end, 170)
		local hint = UI.Label(win.side, "!admin opens this", "SurfUI_Small", C.faint)
		hint:Dock(BOTTOM)
		hint:SetContentAlignment(5)
		hint:SetTall(S(24))
		win.body = vgui.Create("DPanel", win)
		win.body:Dock(FILL)
		win.body.Paint = nil
		-- Keep the player list fresh while it's open
		win.body.Think = function()
			if state.page == "players" and RealTime() > (state.nextPoll or 0) then
				state.nextPoll = RealTime() + 5
				Ask("players")
			end
		end
	end
	AP.Show(page)
end

-- Asks again for what the open page shows (after an action)
function AP.Refresh()
	if not IsValid(win) then return end
	local p = state.page
	if p == "players" then
		state.nextPoll = RealTime() + 5
		Ask("players")
		if state.sid then Ask("player", { sid = state.sid }) end
	else
		Ask(p)
	end
end

local function Header(parent, title, sub)
	local p = vgui.Create("DPanel", parent)
	p:Dock(TOP)
	p:SetTall(S(46))
	p:DockMargin(0, 0, 0, S(8))
	p.Paint = function(_, w)
		draw.SimpleText(title, "SurfUI_Title", 0, S(13), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local s = isfunction(sub) and sub() or sub
		if s and s ~= "" then
			draw.SimpleText(UI.Fit(s, "SurfUI_Small", w), "SurfUI_Small", 0, S(36), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
	end
	return p
end

-- A titled group of buttons, three to a line. Entries that are false are skipped.
local function Group(parent, title, buttons)
	local list = {}
	for i = 1, table.maxn(buttons) do
		if buttons[i] then list[#list + 1] = buttons[i] end
	end
	if #list == 0 then return end
	UI.Section(parent, title)
	local g = UI.Grid(parent, 3, 36, 8)
	for _, b in ipairs(list) do UI.Button(g, b[1], b[2], b[3]) end
	return g
end

-- Players ------------------------------------------------------------------------------

local function Flags(p)
	local t = {}
	if p.level == 2 then t[#t + 1] = "owner" elseif p.level == 1 then t[#t + 1] = "admin" end
	if p.vip then t[#t + 1] = "VIP" end
	if p.spec then t[#t + 1] = "spectating" end
	if p.afk then t[#t + 1] = "AFK" end
	if p.muted then t[#t + 1] = "muted" end
	if p.gagged then t[#t + 1] = "gagged" end
	if p.frozen then t[#t + 1] = "frozen" end
	return table.concat(t, ", ")
end

local INVISIBLE = Color(0, 0, 0, 0)

function AP.Select(sid)
	state.sid, state.data.player = sid, nil
	DRAW.player()
	Ask("player", { sid = sid })
end

local function PlayerRow(parent, p, sub, right)
	local row = UI.Row(parent, {
		title = p.name or p.sid, sub = sub, right = right, titleColor = RankColor(p.level) or (p.vip and C.gold or nil),
		swatch = INVISIBLE, -- room for the picture
		active = function() return state.sid == p.sid end,
		onClick = function() AP.Select(p.sid) end,
		onRightClick = function()
			local m = UI.Menu()
			m:AddOption("Copy SteamID", function() SetClipboardText(p.sid) UI.Toast("Copied " .. p.sid) end):SetIcon("icon16/page_copy.png")
			AP.AddOptions(m, p.sid, p.name or p.sid)
			UI.OpenMenu(m)
		end,
	})
	local av = UI.Avatar(row, p.sid, 26)
	av:SetPos(S(10), S(12))
	av:SetMouseInputEnabled(false)
	return row
end

DRAW.players = function()
	local list = ui.list
	if not IsValid(list) then return end
	list:Clear()
	local q = state.q
	local online = state.data.players and state.data.players.players
	if not online then
		UI.Loading(list)
		return
	end
	table.sort(online, function(a, b) return string.lower(a.name) < string.lower(b.name) end)
	UI.Section(list, "On the server (" .. #online .. ")")
	local here, n = {}, 0
	for _, p in ipairs(online) do
		here[p.sid] = true
		if q == "" or p.sid == q or string.find(string.lower(p.name), q, 1, true) then
			n = n + 1
			local sub = string.Comma(p.points or 0) .. " points" .. ((p.rank or 0) > 0 and (", #" .. p.rank) or "")
			local flags = Flags(p)
			PlayerRow(list, p, flags ~= "" and (sub .. "  |  " .. flags) or sub, (p.ping or 0) .. " ms")
		end
	end
	if n == 0 then UI.Empty(list, q == "" and "Nobody is on the server." or "Nobody on the server matches.") end
	if #q < 2 then return end
	UI.Section(list, "Everyone who has played")
	local f = state.data.find
	if not f or f.q ~= string.sub(q, 1, 64) then
		UI.Empty(list, "Searching...")
		return
	end
	local shown = 0
	for _, r in ipairs(f.results or {}) do
		if not here[r.sid] then
			shown = shown + 1
			PlayerRow(list, r, "Last seen " .. Ago(r.lastseen))
		end
	end
	if shown == 0 then UI.Empty(list, "No one else found.") end
end
DRAW.find = DRAW.players

local function Chips(p)
	local out = {}
	if p.owner then out[#out + 1] = { "OWNER", C.gold } elseif p.staff == "admin" or p.level == 1 then out[#out + 1] = { "ADMIN", C.red } end
	if p.vip then out[#out + 1] = { p.vip == 0 and "VIP FOREVER" or ((p.vip > os.time()) and ("VIP UNTIL " .. os.date("%Y-%m-%d", p.vip)) or "VIP ENDED"), C.gold } end
	if p.ban then out[#out + 1] = { "BANNED", C.red } end
	if p.muted then out[#out + 1] = { "MUTED", C.red } end
	if p.gagged then out[#out + 1] = { "GAGGED", C.red } end
	if p.frozen then out[#out + 1] = { "FROZEN", C.dim } end
	if not p.known then out[#out + 1] = { "NEVER JOINED", C.faint } end
	return out
end

local function Notice(parent, title, sub, col)
	return UI.Row(parent, { title = title, sub = sub, titleColor = col or C.red, tall = sub and sub ~= "" and 50 or 40 })
end

local function ItemOptions(filter)
	local out = {}
	for _, cat in ipairs(SURF.ShopCategories or {}) do
		for _, it in ipairs(cat.list or {}) do
			if filter(it) then
				out[#out + 1] = { it.name or it.key, it.key, sub = cat.name .. ((it.price and it.price > 0) and (", " .. it.price .. " coins") or ""),
					color = IsColor(it.color) and it.color or nil }
			end
		end
	end
	return out
end

DRAW.player = function()
	local d = ui.detail
	if not IsValid(d) then return end
	d:Clear()
	if not state.sid then
		UI.Empty(d, "Pick a player on the left, or search for anyone who has played here.")
		return
	end
	local p = state.data.player
	if not p or p.sid ~= state.sid then
		UI.Loading(d)
		return
	end
	local lvl, online, sid, name = Level(), p.online, p.sid, p.name or p.sid
	local feat = p.features or {}
	local scroll = UI.Scroll(d)

	local card = UI.Card(scroll)
	card:Dock(TOP)
	card:SetTall(S(96))
	card:DockMargin(0, 0, S(6), S(12))
	local av = UI.Avatar(card, sid, 64)
	av:Dock(LEFT)
	av:DockMargin(0, S(4), S(14), S(4))
	local info = vgui.Create("DPanel", card)
	info:Dock(FILL)
	local chips = Chips(p)
	info.Paint = function(_, w)
		draw.SimpleText(UI.Fit(name, "SurfUI_Title", w), "SurfUI_Title", 0, S(14), RankColor(p.level) or C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local line = (online and "On the server now" or ("Last seen " .. Ago(p.lastseen))) .. "    " .. sid
		draw.SimpleText(UI.Fit(line, "SurfUI_Small", w), "SurfUI_Small", 0, S(38), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local x = 0
		for _, c in ipairs(chips) do
			local tw = UI.TextWidth(c[1], "SurfUI_Tiny") + S(14)
			draw.RoundedBox(4, x, S(54), tw, S(20), UI.Alpha(c[2], 40))
			draw.SimpleText(c[1], "SurfUI_Tiny", x + tw / 2, S(64), c[2], TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			x = x + tw + S(6)
		end
	end

	local grid = UI.Grid(scroll, 4, 70, 10)
	grid:DockMargin(0, 0, S(6), S(12))
	local pts = string.Comma(p.points or 0) .. ((p.rank or 0) > 0 and ("  #" .. p.rank) or "")
	UI.Stat(grid, (p.adjust and p.adjust ~= 0) and string.format("Points (admin %+d)", p.adjust) or "Points", pts, C.text)
	UI.Stat(grid, "Coins", string.Comma(p.coins or 0), C.gold)
	UI.Stat(grid, "Playtime", Hours(p.playtime), C.text)
	UI.Stat(grid, "Finished maps", string.Comma(p.times or 0), C.text)

	if p.ban then
		Notice(scroll, "Banned, ends " .. Ends(p.ban.expires), (p.ban.reason or "") .. (p.ban.created and ("  (" .. Date(p.ban.created) .. ")") or ""))
	end
	if p.muted then Notice(scroll, "Chat muted, ends " .. Ends(p.muted.expires), p.muted.reason) end
	if p.gagged then Notice(scroll, "Voice gagged, ends " .. Ends(p.gagged.expires), p.gagged.reason) end

	Group(scroll, "Moderation", {
		online and { "Go to", "ghost", function() Act("goto", sid) end },
		online and { "Bring", "ghost", function() Act("bring", sid) end },
		online and { "Send to the start", "ghost", function() Act("start", sid) end },
		online and { "Spectate", "ghost", function() Act("spectate", sid) win:Close() end },
		online and { p.frozen and "Unfreeze" or "Freeze", "ghost", function() Act("freeze", sid) end },
		online and { "Slay", "ghost", function() Act("slay", sid) end },
		{ p.muted and "Unmute chat" or "Mute chat", "ghost", function()
			if p.muted then Act("unmute", sid) else AP.Mute(sid, name) end
		end },
		{ p.gagged and "Ungag voice" or "Gag voice", "ghost", function()
			if p.gagged then Act("ungag", sid) else AP.Gag(sid, name) end
		end },
		online and { "Kick", "danger", function() AP.Kick(sid, name) end },
		{ p.ban and "Unban" or "Ban", "danger", function()
			if p.ban then
				UI.Confirm("Unban " .. name, "Let " .. name .. " join the server again?", "Unban", function() Act("unban", sid) end)
			else
				AP.Ban(sid, name)
			end
		end },
	})

	if p.here and #p.here > 0 then
		Group(scroll, "Records on " .. game.GetMap(), {
			{ "Delete a time", "danger", function()
				local opts = {}
				for _, t in ipairs(p.here) do
					local st = SURF.StyleByID[t.style]
					opts[#opts + 1] = { (st and st.name or t.style) .. "  " .. SURF.FormatTime(t.time), t.style }
				end
				UI.Pick("Delete a time of " .. name, opts, function(style, o)
					UI.Confirm("Delete this time?", name .. ": " .. o[1] .. " on " .. game.GetMap() .. ". This can't be undone.", "Delete", function()
						Act("deltime", sid, { style = style })
					end, true)
				end)
			end },
		})
	end

	if lvl >= 2 then
		Group(scroll, "Owner", {
			{ "Give VIP", "gold", function()
				UI.Prompt("Give VIP to " .. name, "How many days? 0 = forever. Days add to any VIP they already have.", "30", function(v)
					Act("givevip", sid, { days = math.max(0, math.floor(tonumber(v) or 30)) })
				end, { numeric = true, choices = { { "7 days", 7 }, { "30 days", 30 }, { "90 days", 90 }, { "Forever", 0 } }, okText = "Give VIP" })
			end },
			p.vip and { "Remove VIP", "ghost", function()
				UI.Confirm("Remove VIP", "Take VIP away from " .. name .. "?", "Remove", function() Act("removevip", sid) end, true)
			end },
			feat.shop and { "Coins", "ghost", function()
				UI.Prompt("Coins for " .. name, "How many coins to add? Use a minus to take coins away. They have " .. string.Comma(p.coins or 0) .. ".", "100", function(v)
					Act("coins", sid, { amount = math.floor(tonumber(v) or 0) })
				end, { numeric = true, choices = { { "+100", 100 }, { "+1000", 1000 }, { "+5000", 5000 }, { "-100", -100 } } })
			end },
			feat.shop and { "Give an item", "ghost", function()
				local owned = {}
				for _, k in ipairs(p.owned or {}) do owned[k] = true end
				UI.Pick("Give an item to " .. name, ItemOptions(function(it) return not owned[it.key] and not SURF.ItemFree(it) end), function(key)
					Act("giveitem", sid, { item = key })
				end)
			end },
			(feat.shop and #(p.owned or {}) > 0) and { "Take an item", "ghost", function()
				local owned = {}
				for _, k in ipairs(p.owned or {}) do owned[k] = true end
				UI.Pick("Take an item from " .. name, ItemOptions(function(it) return owned[it.key] end), function(key)
					Act("removeitem", sid, { item = key })
				end)
			end },
			feat.points and { "Points", "ghost", function()
				UI.Prompt("Points for " .. name, "How many points to add? Use a minus to take points away. They count on top of the points from times.", "100", function(v)
					Act("points", sid, { amount = math.floor(tonumber(v) or 0) })
				end, { numeric = true, choices = { { "+50", 50 }, { "+100", 100 }, { "+500", 500 }, { "-100", -100 } } })
			end },
			(not p.owner) and { p.staff == "admin" and "Remove admin" or "Make admin", p.staff == "admin" and "danger" or "primary", function()
				local on = p.staff ~= "admin"
				UI.Confirm(on and "Make admin" or "Remove admin",
					on and (name .. " gets the admin panel and can kick, ban, mute and change maps. Only owners can give VIP, coins or items.")
						or ("Take admin away from " .. name .. "?"),
					on and "Make admin" or "Remove", function() Act("setadmin", sid, { on = on }) end, not on)
			end },
		})
		if feat.shop and #(p.owned or {}) > 0 then
			local names = {}
			for _, k in ipairs(p.owned) do
				local it = SURF.ItemByKey[k]
				names[#names + 1] = it and it.name or k
			end
			UI.Section(scroll, "Owns " .. #names .. " items")
			local l = UI.Label(scroll, table.concat(names, ", "), "SurfUI_Small", C.dim, true)
			l:Dock(TOP)
			l:DockMargin(S(2), 0, S(6), S(8))
		end
	end

	Group(scroll, "Other", {
		{ "Copy SteamID", "ghost", function()
			SetClipboardText(sid)
			UI.Toast("Copied " .. sid)
		end },
		{ "Steam profile", "ghost", function() gui.OpenURL("https://steamcommunity.com/profiles/" .. sid) end },
	})
end

function BUILD.players(body)
	local left = vgui.Create("DPanel", body)
	left:Dock(LEFT)
	left:SetWide(S(320))
	left:DockMargin(0, 0, S(14), 0)
	left.Paint = nil
	UI.Search(left, "Find a player (name or SteamID64)", function(q)
		state.q = q
		DRAW.players()
		if #q >= 2 then
			timer.Create("surf_admin_find", 0.35, 1, function() Ask("find", { q = q }) end)
		end
	end)
	state.q = ""
	ui.list = UI.Scroll(left)
	ui.detail = vgui.Create("DPanel", body)
	ui.detail:Dock(FILL)
	ui.detail.Paint = nil
	DRAW.players()
	DRAW.player()
	state.nextPoll = RealTime() + 5
	Ask("players")
	if state.sid then Ask("player", { sid = state.sid }) end
end

-- Server ----------------------------------------------------------------------------------

local function MapMenu(m)
	local menu = UI.Menu()
	if m.name ~= game.GetMap() then
		menu:AddOption("Change to this map", function()
			UI.Confirm("Change the map", "Change to " .. m.name .. " in 5 seconds?", "Change map", function() Act("changelevel", nil, { map = m.name }) end)
		end):SetIcon("icon16/map_go.png")
	end
	if m.hidden then
		menu:AddOption("Put back in votes", function() Act("hidemap", nil, { map = m.name, hide = false }) end):SetIcon("icon16/eye.png")
	else
		local o = menu:AddOption("Hide from votes and !maps", function()
			UI.Confirm("Hide " .. m.name, "Take " .. m.name .. " out of votes and !maps? The next update also deletes it.", "Hide", function()
				Act("hidemap", nil, { map = m.name, hide = true })
			end, true)
		end)
		o:SetIcon("icon16/delete.png")
		o.uiColor = C.red
	end
	UI.OpenMenu(menu)
end

DRAW.server = function()
	local body = ui.server
	if not IsValid(body) then return end
	body:Clear()
	local d = state.data.server
	if not d then
		UI.Loading(body)
		return
	end
	local got = RealTime()
	local grid = UI.Grid(body, 4, 70, 10)
	UI.Stat(grid, "Map", d.map or "", C.text)
	UI.Stat(grid, "Tier", (d.tier or 0) > 0 and tostring(d.tier) or "?", C.text)
	UI.Stat(grid, "Time left", function()
		if d.vote then return "Voting" end
		return Clock((d.timeleft or 0) - (RealTime() - got))
	end, function() return d.vote and UI.Accent() or C.text end)
	UI.Stat(grid, "Players", (d.players or 0) .. " / " .. (d.max or 0), C.text)
	if not d.zoned then
		Notice(body, "This map has no working start and end zones", "Players can't set times here. A vote for another map starts by itself.")
	end

	Group(body, "Map", {
		{ "Start a map vote", "primary", function()
			UI.Confirm("Start a map vote", "Start a vote for the next map now?", "Start vote", function() Act("vote") end)
		end },
		{ "Extend the map", "ghost", function()
			UI.Prompt("Extend the map", "Add how many minutes?", "15", function(v)
				Act("extend", nil, { minutes = math.Clamp(math.floor(tonumber(v) or 15), 1, 120) })
			end, { numeric = true, choices = { { "10 min", 10 }, { "15 min", 15 }, { "30 min", 30 }, { "1 hour", 60 } } })
		end },
		{ "Restart the map", "ghost", function()
			UI.Confirm("Restart the map", "Reload " .. (d.map or "this map") .. " in 5 seconds? Everyone's current run ends.", "Restart", function() Act("restartmap") end)
		end },
		{ "Change the map", "ghost", function()
			local opts = {}
			for _, m in ipairs(d.maps or {}) do
				if m.name ~= d.map then
					opts[#opts + 1] = { m.name, m.name, sub = ((m.tier or 0) > 0 and ("Tier " .. m.tier) or "Tier ?") .. (m.zoned and "" or ", no zones") .. (m.hidden and ", hidden" or "") }
				end
			end
			UI.Pick("Change the map", opts, function(map)
				Act("changelevel", nil, { map = map })
			end)
		end },
		{ "Announcement", "gold", function()
			UI.Prompt("Announcement", "Shows on everyone's screen and in chat.", "", function(text)
				Act("announce", nil, { text = text })
			end, { placeholder = "Message", okText = "Announce" })
		end },
	})

	local maps = d.maps or {}
	UI.Section(body, "Installed maps (" .. #maps .. "), right-click for options")
	local holder = vgui.Create("DPanel", body)
	holder:Dock(FILL)
	holder.Paint = nil
	local scroll
	local function Fill(q)
		scroll:Clear()
		local n = 0
		for _, m in ipairs(maps) do
			if q == "" or string.find(m.name, q, 1, true) then
				n = n + 1
				local sub = ((m.tier or 0) > 0 and ("Tier " .. m.tier) or "Tier ?") .. (m.zoned and "" or ", no zones") .. (m.hidden and ", hidden" or "")
				UI.Row(scroll, { title = m.name, sub = sub, tall = 46, active = m.name == d.map, right = m.name == d.map and "Playing now" or nil,
					titleColor = (m.hidden or not m.zoned) and C.faint or nil,
					onClick = function() MapMenu(m) end, onRightClick = function() MapMenu(m) end })
			end
		end
		if n == 0 then UI.Empty(scroll, "No map matches.") end
	end
	UI.Search(holder, "Search maps", Fill)
	scroll = UI.Scroll(holder)
	Fill("")
end

function BUILD.server(body)
	Header(body, "Server", "The map, the vote and every installed map")
	ui.server = vgui.Create("DPanel", body)
	ui.server:Dock(FILL)
	ui.server.Paint = nil
	DRAW.server()
	Ask("server")
end

-- Bans ---------------------------------------------------------------------------------------

local function BanBySteamID()
	UI.Prompt("Ban a SteamID", "The SteamID64 of the player (17 digits, starts with 7656). They don't need to be online.", "", function(v)
		v = string.Trim(v)
		if not string.match(v, "^7656%d+$") or #v ~= 17 then
			UI.Toast("That isn't a SteamID64", C.red)
			return
		end
		AP.Ban(v, v)
	end, { placeholder = "7656119...", okText = "Next" })
end

DRAW.bans = function()
	local body = ui.bans
	if not IsValid(body) then return end
	body:Clear()
	local d = state.data.bans
	if not d then
		UI.Loading(body)
		return
	end
	local bans = d.bans or {}
	if #bans == 0 then
		UI.Empty(body, "Nobody is banned.")
		return
	end
	local l = UI.List(body, { { "Player" }, { "Reason" }, { "By", 140 }, { "Ends", 150 } })
	for _, b in ipairs(bans) do
		local line = l:AddLine(b.name or b.sid, b.reason or "", b.admin or "", Ends(b.expires))
		line.sid, line.name = b.sid, b.name or b.sid
	end
	l.OnRowRightClick = function(_, _, line)
		local m = UI.Menu()
		local o = m:AddOption("Unban", function()
			UI.Confirm("Unban " .. line.name, "Let " .. line.name .. " join the server again?", "Unban", function() Act("unban", line.sid) end)
		end)
		o:SetIcon("icon16/accept.png")
		m:AddOption("Open in the admin panel", function() AP.Open("players", line.sid) end):SetIcon("icon16/application_view_detail.png")
		m:AddOption("Copy SteamID", function() SetClipboardText(line.sid) UI.Toast("Copied " .. line.sid) end):SetIcon("icon16/page_copy.png")
		UI.OpenMenu(m)
	end
	l.DoDoubleClick = function(_, _, line) AP.Open("players", line.sid) end
end

function BUILD.bans(body)
	Header(body, "Bans", "Right-click a ban to lift it. Players can also be banned from the Players page or with !ban.")
	local bar = UI.ButtonBar(body, TOP)
	bar:AddButton("Ban a SteamID", "danger", BanBySteamID)
	bar:AddButton("Refresh", "ghost", function() Ask("bans") end, RIGHT)
	ui.bans = vgui.Create("DPanel", body)
	ui.bans:Dock(FILL)
	ui.bans.Paint = nil
	DRAW.bans()
	Ask("bans")
end

-- Staff ----------------------------------------------------------------------------------------

local function AddAdmin()
	local opts = {}
	for _, p in ipairs(player.GetHumans()) do
		if not p:IsAdmin() then opts[#opts + 1] = { p:Nick(), p:SteamID64(), sub = "On the server" } end
	end
	table.insert(opts, 1, { "Someone else (type a SteamID64)", "", sub = "They don't need to be online" })
	UI.Pick("Make someone an admin", opts, function(sid, o)
		if sid ~= "" then
			UI.Confirm("Make admin", o[1] .. " gets the admin panel and can kick, ban, mute and change maps.", "Make admin", function()
				Act("setadmin", sid, { on = true })
			end)
			return
		end
		UI.Prompt("Make an admin", "Their SteamID64 (17 digits, starts with 7656).", "", function(v)
			v = string.Trim(v)
			if not string.match(v, "^7656%d+$") or #v ~= 17 then
				UI.Toast("That isn't a SteamID64", C.red)
				return
			end
			Act("setadmin", v, { on = true })
		end, { placeholder = "7656119...", okText = "Make admin" })
	end)
end

DRAW.staff = function()
	local body = ui.staff
	if not IsValid(body) then return end
	body:Clear()
	local d = state.data.staff
	if not d then
		UI.Loading(body)
		return
	end
	local scroll = UI.Scroll(body)
	local owner = Level() >= 2
	for _, s in ipairs(d.staff or {}) do
		local isOwner = s.rank == "owner"
		local sub = isOwner and "Owner (OWNER_STEAMIDS in config.env)"
			or ("Admin" .. ((s.by and s.by ~= "") and (", added by " .. s.by) or "") .. (s.date and (" on " .. os.date("%Y-%m-%d", s.date)) or ""))
		local row = UI.Row(scroll, {
			title = s.name or s.sid, sub = sub, titleColor = isOwner and C.gold or C.red, swatch = INVISIBLE,
			right = (owner and not isOwner) and "Remove" or nil, rightColor = C.red,
			onClick = function()
				if owner and not isOwner then
					UI.Confirm("Remove admin", "Take admin away from " .. (s.name or s.sid) .. "?", "Remove", function() Act("setadmin", s.sid, { on = false }) end, true)
				else
					AP.Open("players", s.sid)
				end
			end,
			onRightClick = function() AP.Open("players", s.sid) end,
		})
		local av = UI.Avatar(row, s.sid, 26)
		av:SetPos(S(10), S(12))
		av:SetMouseInputEnabled(false)
	end
	if #(d.staff or {}) == 0 then UI.Empty(scroll, "No staff yet. Owners come from OWNER_STEAMIDS in config.env.") end
end

function BUILD.staff(body)
	Header(body, "Staff", Level() >= 2 and "Owners can do everything. Admins moderate and run the maps, but can't give VIP, coins or items."
		or "Only owners can add or remove admins.")
	if Level() >= 2 then
		local bar = UI.ButtonBar(body, TOP)
		bar:AddButton("Make someone an admin", "primary", AddAdmin)
	end
	ui.staff = vgui.Create("DPanel", body)
	ui.staff:Dock(FILL)
	ui.staff.Paint = nil
	DRAW.staff()
	Ask("staff")
end

-- Log ------------------------------------------------------------------------------------------

local SOURCE = { game = "In game", web = "Website", store = "Store" }

DRAW.log = function()
	local body = ui.log
	if not IsValid(body) then return end
	body:Clear()
	local d = state.data.log
	if not d then
		UI.Loading(body)
		return
	end
	local q = state.logQ or ""
	local l = UI.List(body, { { "When", 130 }, { "Admin", 140 }, { "Action", 100 }, { "Player", 140 }, { "What happened" }, { "From", 80 } })
	local n = 0
	for _, r in ipairs(d.log or {}) do
		local hay = string.lower(table.concat({ r.admin or "", r.action or "", r.target or "", r.detail or "" }, " "))
		if q == "" or string.find(hay, q, 1, true) then
			n = n + 1
			l:AddLine(Date(r.date), r.admin or "", r.action or "", r.target or "", r.detail or "", SOURCE[r.source] or r.source or "")
		end
	end
	if n == 0 then
		l:Remove()
		UI.Empty(body, q == "" and "Nothing logged yet." or "Nothing matches.")
	end
end

function BUILD.log(body)
	Header(body, "Log", "The last 150 things admins did, in game and on the website")
	state.logQ = ""
	UI.Search(body, "Search the log", function(q)
		state.logQ = q
		DRAW.log()
	end)
	ui.log = vgui.Create("DPanel", body)
	ui.log:Dock(FILL)
	ui.log.Paint = nil
	DRAW.log()
	Ask("log")
end

-- From the server ---------------------------------------------------------------------------------

local RECV = {}

RECV.open = function(d)
	state.level = tonumber(d.level) or state.level
	AP.Open(d.sid and "players" or nil, d.sid)
end

RECV.result = function(d)
	UI.Toast(d.ok and tostring(d.msg) or ("Couldn't do that: " .. tostring(d.msg)), d.ok and C.green or C.red)
	AP.Refresh()
end

net.Receive("surf.AdminData", function()
	local kind, data = net.ReadString(), net.ReadTable()
	if RECV[kind] then return RECV[kind](data) end
	if not DRAW[kind] then return end
	state.data[kind] = data
	DRAW[kind]()
end)

-- Announcements ------------------------------------------------------------------------------------

local banner
net.Receive("surf.Announce", function()
	banner = { text = net.ReadString(), by = net.ReadString(), at = RealTime() }
	surface.PlaySound("buttons/blip1.wav")
end)

hook.Add("HUDPaint", "surf_announce", function()
	if not banner then return end
	local age = RealTime() - banner.at
	if age > 9 then
		banner = nil
		return
	end
	local a = math.min(1, age * 5, (9 - age) * 2)
	local text = UI.Fit(banner.text, "SurfUI_Head", ScrW() - S(160))
	local w = math.max(UI.TextWidth(text, "SurfUI_Head"), S(260)) + S(60)
	local h = S(66)
	local x, y = ScrW() / 2 - w / 2, math.floor(ScrH() * 0.17)
	draw.RoundedBox(8, x, y, w, h, Color(19, 22, 30, 240 * a))
	draw.RoundedBox(2, x, y + S(12), S(4), h - S(24), UI.Alpha(C.gold, 255 * a))
	draw.SimpleText("ANNOUNCEMENT FROM " .. string.upper(banner.by or ""), "SurfUI_Tiny", ScrW() / 2, y + S(18), UI.Alpha(C.gold, 255 * a), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	draw.SimpleText(text, "SurfUI_Head", ScrW() / 2, y + S(43), UI.Alpha(C.text, 255 * a), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
end)
