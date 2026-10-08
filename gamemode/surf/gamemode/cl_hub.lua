-- The main menu (F1 or !menu): a side menu with pages. !wr, !top, !maps,
-- !style, !graphics and !help open it on their page. Pages that need the
-- server's data ask for it (surf.MenuReq, sv_menus.lua) and show "Loading..."
-- until it arrives. The shop and VIP have their own windows (cl_shop.lua).
local Menus = SURF.Menus
local UI = SURF.UI
local C = UI.Col
local S = UI.S
local Hub = { args = {} }
SURF.Hub = Hub

local ITEMS = {
	{ id = "home", name = "Home", icon = "icon16/house.png", server = true },
	{ id = "records", name = "Records", icon = "icon16/time.png", server = true },
	{ id = "players", name = "Top players", icon = "icon16/award_star_gold_1.png", server = true },
	{ id = "maps", name = "Maps", icon = "icon16/map.png", server = true },
	{ id = "styles", name = "Styles", icon = "icon16/arrow_switch.png" },
	{ id = "settings", name = "Settings", icon = "icon16/cog.png" },
	{ id = "help", name = "Commands", icon = "icon16/book_open.png" },
	{ spacer = true },
	{ id = "challenges", name = "Challenges", icon = "icon16/flag_green.png", window = true },
	{ id = "shop", name = "Shop", icon = "icon16/cart.png", window = true },
	{ id = "vip", name = "VIP", icon = "icon16/star.png", window = true, color = C.gold },
	{ id = "discord", name = "Discord", icon = "icon16/comments.png", window = true },
	{ id = "admin", name = "Admin", icon = "icon16/shield.png", window = true, admin = true, color = C.red },
}
local ITEM = {}
for _, it in ipairs(ITEMS) do
	if it.id then ITEM[it.id] = it end
end

local BUILD = {}
local hub
local reqNo = 0

local function Say(text) RunConsoleCommand("say", text) end

-- Runs a chat command and gets the menu out of the way
local function Do(text)
	if IsValid(hub) then hub:Close() end
	Say(text)
end

local function Request(kind, arg)
	reqNo = reqNo % 60000 + 1
	net.Start("surf.MenuReq")
	net.WriteString(kind)
	net.WriteString(arg or "")
	net.WriteUInt(reqNo, 16)
	net.SendToServer()
	return reqNo
end

local TIER_COLORS = { Color(90, 210, 120), Color(150, 220, 90), Color(240, 210, 70), Color(255, 150, 60), Color(240, 80, 80), Color(200, 100, 255) }
local function TierColor(t)
	if not t or t <= 0 then return C.faint end
	return TIER_COLORS[math.min(t, #TIER_COLORS)]
end

local function Hours(sec)
	sec = math.floor(sec or 0)
	local h, m = math.floor(sec / 3600), math.floor(sec % 3600 / 60)
	if h > 0 then return h .. "h " .. m .. "m" end
	return m .. "m"
end

local function Diff(d)
	if d < 60 then return string.format("+%.3f", d) end
	return "+" .. SURF.FormatTime(d)
end

local function Profile(sid)
	if sid and sid ~= "" then gui.OpenURL("https://steamcommunity.com/profiles/" .. sid) end
end

-- A page's title with a grey line under it
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

-- On/off switch on the right of a row
local function Switch(on)
	return function(_, w, h)
		local sw, sh = S(40), S(22)
		local x, y = w - sw - S(14), h / 2 - sh / 2
		local acc = UI.Accent()
		draw.RoundedBox(sh / 2, x, y, sw, sh, on() and Color(acc.r, acc.g, acc.b, 220) or Color(255, 255, 255, 30))
		local k = sh - S(6)
		draw.RoundedBox(k / 2, on() and (x + sw - k - S(3)) or (x + S(3)), y + S(3), k, k, color_white)
	end
end

local function Toggle(parent, title, sub, on, click)
	return UI.Row(parent, { title = title, sub = sub, onClick = click, paint = Switch(on) })
end

function Hub.IsOpen() return IsValid(hub) end

function Hub.Show(id, data)
	if not IsValid(hub) then return Hub.Open(id, data) end
	if not ITEM[id] or not BUILD[id] then return end
	hub.page, hub.wait = id, nil
	hub.side:SetActive(id)
	hub.body:Clear()
	if ITEM[id].server and not data then
		hub.wait = Request(id, Hub.args[id])
		UI.Loading(hub.body)
		return
	end
	BUILD[id](hub.body, data or {})
end

local function Window(id)
	if id == "admin" then
		if SURF.AdminPanel then SURF.AdminPanel.Open() end
	else
		Say("!" .. id)
	end
end

function Hub.Open(id, data)
	id = BUILD[id] and id or "home"
	if not IsValid(hub) then
		hub = UI.Frame(GetGlobal2String("surf_brand", SURF.Config.Name), 960, 640, { id = "hub", sub = "Main menu",
			right = function() return string.Comma(LocalPlayer():GetNW2Int("surf_coins", 0)) .. " coins", C.gold end })
		local items = {}
		for _, it in ipairs(ITEMS) do
			if not it.admin or LocalPlayer():IsAdmin() then items[#items + 1] = it end
		end
		hub.side = UI.Sidebar(hub, items, id, function(pick)
			if ITEM[pick].window then
				hub:Close()
				Window(pick)
				return false
			end
			Hub.Show(pick)
		end, 200)
		local hint = UI.Label(hub.side, "F1 opens this menu", "SurfUI_Small", C.faint)
		hint:Dock(BOTTOM)
		hint:SetContentAlignment(5)
		hint:SetTall(S(24))
		hub.body = vgui.Create("DPanel", hub)
		hub.body:Dock(FILL)
		hub.body.Paint = nil
	end
	Hub.Show(id, data)
end

-- The server's answer for a page; dropped if the player moved on
function Hub.Answer(kind, data)
	if not IsValid(hub) or hub.page ~= kind or hub.wait ~= data.req then return end
	hub.wait = nil
	hub.body:Clear()
	BUILD[kind](hub.body, data)
end

-- Home ----------------------------------------------------------------------

function BUILD.home(parent, d)
	local me = LocalPlayer()
	local titles = SURF.Config.Titles
	local t = titles[d.title or 1] or titles[1]
	local nextT = titles[(d.title or 1) + 1]
	local points = d.points or 0

	local card = UI.Card(parent)
	card:Dock(TOP)
	card:SetTall(S(96))
	card:DockMargin(0, 0, 0, S(12))
	local av = UI.Avatar(card, me, 64)
	av:Dock(LEFT)
	av:DockMargin(0, S(4), S(14), S(4))
	local info = vgui.Create("DPanel", card)
	info:Dock(FILL)
	info.Paint = function(_, w, h)
		draw.SimpleText(me:Nick(), "SurfUI_Title", 0, S(14), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(t.name, "SurfUI_Body", 0, S(40), t.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		if d.vip then
			local x = UI.TextWidth(t.name, "SurfUI_Body") + S(10)
			draw.RoundedBox(4, x, S(31), S(38), S(18), C.gold)
			draw.SimpleText("VIP", "SurfUI_Tiny", x + S(19), S(40), C.dark, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		local frac = nextT and math.Clamp((points - t.points) / math.max(1, nextT.points - t.points), 0, 1) or 1
		draw.SimpleText(nextT and string.format("%s / %s points to %s", string.Comma(points), string.Comma(nextT.points), nextT.name) or "Highest title reached",
			"SurfUI_Small", w, S(40), C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		draw.RoundedBox(3, 0, h - S(10), w, S(6), Color(255, 255, 255, 15))
		draw.RoundedBox(3, 0, h - S(10), math.max(S(6), w * frac), S(6), t.color)
	end

	local g = UI.Grid(parent, 3, 68)
	UI.Stat(g, "Points", string.Comma(points), t.color)
	UI.Stat(g, "Server rank", (d.rank or 0) > 0 and ("#" .. d.rank .. " of " .. (d.ranked or 0)) or "Finish a map to rank")
	UI.Stat(g, "Coins", function() return string.Comma(me:GetNW2Int("surf_coins", d.coins or 0)) end, C.gold)
	UI.Stat(g, "Maps finished", d.finished or 0)
	UI.Stat(g, "Records held", d.records or 0, (d.records or 0) > 0 and C.gold or nil)
	UI.Stat(g, "Time played", Hours(d.playtime))

	UI.Section(parent, "This map")
	local m = d.map or {}
	local mc = UI.Card(parent)
	mc:Dock(TOP)
	mc:SetTall(S(132))
	mc:DockMargin(0, 0, 0, S(12))
	mc.Paint = function(_, w)
		draw.RoundedBox(8, 0, 0, w, mc:GetTall(), C.card)
		local x = S(14)
		draw.SimpleText(m.name or game.GetMap(), "SurfUI_Head", x, S(20), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local tw = UI.TextWidth(m.name or game.GetMap(), "SurfUI_Head") + S(12)
		local tierText = (m.tier or 0) > 0 and ("Tier " .. m.tier) or "Tier ?"
		local bw = UI.TextWidth(tierText, "SurfUI_Tiny") + S(14)
		draw.RoundedBox(4, x + tw, S(11), bw, S(18), TierColor(m.tier))
		draw.SimpleText(tierText, "SurfUI_Tiny", x + tw + bw / 2, S(20), C.dark, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		local parts = {}
		if m.mapper and m.mapper ~= "" then parts[#parts + 1] = "by " .. m.mapper end
		parts[#parts + 1] = (m.stages or 0) > 0 and (m.stages .. " stages") or "linear"
		parts[#parts + 1] = (m.bonuses or 0) == 1 and "1 bonus" or ((m.bonuses or 0) .. " bonuses")
		parts[#parts + 1] = string.format("%d:%02d left", math.floor((m.timeleft or 0) / 60), math.floor((m.timeleft or 0) % 60))
		if m.zoned == false then parts[#parts + 1] = "no timer zones yet" end
		draw.SimpleText(table.concat(parts, "  ·  "), "SurfUI_Small", x, S(42), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local half = (w - S(28)) / 2
		draw.SimpleText("SERVER RECORD", "SurfUI_Tiny", x, S(64), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(m.wr and (SURF.FormatTime(m.wr.time) .. "  " .. UI.Fit(m.wr.name or "", "SurfUI_Body", half - S(110))) or "No record yet",
			"SurfUI_Body", x, S(84), m.wr and C.gold or C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText("YOUR BEST", "SurfUI_Tiny", x + half, S(64), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(m.pb and (SURF.FormatTime(m.pb) .. "  (#" .. (m.pbRank or "?") .. " of " .. (m.finishers or 0) .. ")") or "Not finished yet",
			"SurfUI_Body", x + half, S(84), m.pb and UI.Accent() or C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	local acts = UI.ButtonBar(mc, BOTTOM)
	acts:SetTall(S(30))
	acts:AddButton("Restart", "primary", function() Do("!r") end)
	acts:AddButton("Watch the record", "ghost", function() Do("!replay") end)
	acts:AddButton("Vote for another map", "ghost", function() Do("!rtv") end)

	local links = UI.ButtonBar(parent, TOP)
	links:DockMargin(0, 0, 0, 0)
	links:AddButton("Shop", "gold", function() Do("!shop") end)
	if d.site then links:AddButton("Website", "ghost", function() gui.OpenURL(d.site) end) end
	if d.discord then links:AddButton("Discord", "ghost", function() gui.OpenURL(d.discord) end) end
	if not d.vip then links:AddButton("Get VIP", "ghost", function() Do("!vip") end) end
end

-- Records ---------------------------------------------------------------------

function BUILD.records(parent, d)
	local me = LocalPlayer()
	local style = d.style or me:GetNW2String("surf_style", "n")
	local track = d.track or 0
	Header(parent, "Records", (d.map or game.GetMap()) .. "  ·  " .. string.Comma(d.total or 0) .. " finishers")
	local styles = {}
	for _, st in ipairs(SURF.Config.Styles) do styles[#styles + 1] = { id = st.id, name = st.name } end
	UI.Tabs(parent, styles, style, function(id)
		Hub.args.records = id .. "|" .. track
		Hub.Show("records")
	end)
	if d.bonuses and #d.bonuses > 0 then
		local tracks = { { id = 0, name = "Main" } }
		for _, b in ipairs(d.bonuses) do tracks[#tracks + 1] = { id = b, name = "Bonus " .. b } end
		UI.Tabs(parent, tracks, track, function(id)
			Hub.args.records = style .. "|" .. id
			Hub.Show("records")
		end)
	end
	local rows = d.rows or {}
	if #rows == 0 then return UI.Empty(parent, "No times yet. Be the first!") end
	local l = UI.List(parent, { { "#", 50 }, { "Player" }, { "Time", 120, align = "right" }, { "Behind", 110, align = "right" }, { "Date", 110, align = "right" } })
	local best = rows[1].time
	for i, r in ipairs(rows) do
		local line = l:AddLine(i, r.name or "?", SURF.FormatTime(r.time), i == 1 and "" or Diff(r.time - best), r.date and os.date("%Y-%m-%d", r.date) or "")
		line:SetSortValue(1, i)
		line:SetSortValue(3, r.time)
		line:SetSortValue(4, r.time)
		line:SetSortValue(5, r.date or 0)
		line.sid = r.steamid
		if i == 1 then
			UI.CellColor(line, 1, C.gold)
			UI.CellColor(line, 3, C.gold)
		end
		if r.steamid and r.steamid == me:SteamID64() then UI.CellColor(line, 2, UI.Accent()) end
		UI.CellColor(line, 4, C.dim)
		UI.CellColor(line, 5, C.dim)
	end
	l.OnRowRightClick = function(_, _, line)
		local m = UI.Menu()
		m:AddOption("Steam profile", function() Profile(line.sid) end):SetIcon("icon16/user.png")
		if me:IsAdmin() and track == 0 and line.sid and d.here then
			m:AddOption("Delete this time", function()
				UI.Confirm("Delete time", "Delete the time of " .. line:GetColumnText(2) .. " on this map? Their points change too.", "Delete", function()
					Say("!deltime " .. line.sid .. " " .. style)
					timer.Simple(0.5, function() if Hub.IsOpen() then Hub.Show("records") end end)
				end, true)
			end):SetIcon("icon16/delete.png")
		end
		UI.OpenMenu(m)
	end
end

-- Top players -------------------------------------------------------------------

function BUILD.players(parent, d)
	local me = LocalPlayer()
	local titles = SURF.Config.Titles
	local sub = string.Comma(d.total or 0) .. " ranked players"
	if d.mine then sub = sub .. "  ·  you are #" .. d.mine.pos .. " with " .. string.Comma(d.mine.points) .. " points" end
	Header(parent, "Top players", sub)
	local rows = d.rows or {}
	if #rows == 0 then return UI.Empty(parent, "Nobody is ranked yet. Finish a map!") end
	local l = UI.List(parent, { { "#", 50 }, { "Player" }, { "Title", 140 }, { "Points", 110, align = "right" } })
	for i, r in ipairs(rows) do
		local t = titles[r.title] or titles[1]
		local line = l:AddLine(i, r.name or "?", t.name, string.Comma(r.points))
		line:SetSortValue(1, i)
		line:SetSortValue(4, r.points)
		line.sid = r.sid
		UI.CellColor(line, 3, t.color)
		if i <= 3 then UI.CellColor(line, 1, C.gold) end
		if r.sid and r.sid == me:SteamID64() then UI.CellColor(line, 2, UI.Accent()) end
	end
	l.OnRowRightClick = function(_, _, line)
		if not line.sid then return end
		local m = UI.Menu()
		m:AddOption("Steam profile", function() Profile(line.sid) end):SetIcon("icon16/user.png")
		UI.OpenMenu(m)
	end
end

-- Maps ------------------------------------------------------------------------

function BUILD.maps(parent, d)
	local me = LocalPlayer()
	local maps = d.maps or {}
	local nominated = d.nominated
	local done = 0
	for _, m in ipairs(maps) do if m.done then done = done + 1 end end
	Header(parent, "Maps", #maps .. " maps, you finished " .. done .. "  ·  click one to nominate it for the next vote")
	local query, tier = "", 0
	local scroll
	local function Fill()
		scroll:Clear()
		local n = 0
		for _, m in ipairs(maps) do
			local t = m.tier or 0
			local tierOk = tier == 0 or (tier == 5 and t >= 5) or t == tier
			if tierOk and (query == "" or string.find(m.name, query, 1, true)) then
				n = n + 1
				local cur = m.name == d.current
				UI.Row(scroll, {
					title = m.name, tall = 46,
					sub = ((t > 0) and ("Tier " .. t) or "Tier unknown") .. "  ·  " .. (m.done and "You finished it" or "Not finished yet"),
					swatch = TierColor(t),
					active = function() return nominated == m.name end,
					right = function() return cur and "Playing now" or (nominated == m.name and "Nominated" or "Nominate") end,
					rightColor = function() return cur and C.green or (nominated == m.name and UI.Accent() or C.dim) end,
					onClick = not cur and function()
						Say("!nominate " .. m.name)
						nominated = m.name
					end or nil,
					onRightClick = me:IsAdmin() and function()
						local menu = UI.Menu()
						menu:AddOption("Change to this map now", function() Do("!map " .. m.name) end):SetIcon("icon16/map_go.png")
						menu:AddOption("Hide this map", function()
							UI.Confirm("Hide map", "Take " .. m.name .. " out of votes and this list? !unhidemap brings it back.", "Hide", function() Say("!hidemap " .. m.name) end, true)
						end):SetIcon("icon16/map_delete.png")
						UI.OpenMenu(menu)
					end or nil,
				})
			end
		end
		if n == 0 then UI.Empty(scroll, "No map matches.") end
	end
	UI.Search(parent, "Search maps...", function(q)
		query = q
		Fill()
	end)
	UI.Tabs(parent, { { id = 0, name = "All" }, { id = 1, name = "Tier 1" }, { id = 2, name = "Tier 2" }, { id = 3, name = "Tier 3" },
		{ id = 4, name = "Tier 4" }, { id = 5, name = "Tier 5+" } }, 0, function(id)
		tier = id
		Fill()
	end)
	scroll = UI.Scroll(parent)
	Fill()
end

-- Styles ----------------------------------------------------------------------

function BUILD.styles(parent)
	local me = LocalPlayer()
	Header(parent, "Styles", "Each style has its own records. Times on styles other than Normal give half the points.")
	local scroll = UI.Scroll(parent)
	for _, st in ipairs(SURF.Config.Styles) do
		local function cur() return me:GetNW2String("surf_style", "n") == st.id end
		UI.Row(scroll, { title = st.name, sub = st.help, active = cur,
			right = function() return cur() and "Current" or ("!style " .. st.id) end,
			onClick = function() if not cur() then Say("!style " .. st.id) end end })
	end
end

-- Settings --------------------------------------------------------------------

local function ConVarOn(name)
	local cv = GetConVar(name)
	return cv ~= nil and cv:GetBool()
end

function BUILD.settings(parent)
	local me = LocalPlayer()
	local V = SURF.Visuals
	Header(parent, "Settings", "These only change the game for you")
	local scroll = UI.Scroll(parent)
	UI.Section(scroll, "Color preset")
	for _, p in ipairs(V.Presets) do
		UI.Row(scroll, { title = p.name, sub = p.help, active = function() return V.Current() == p end,
			right = function() return V.Current() == p and "On" or "" end, onClick = function() V.SetPreset(p.id) end })
	end
	UI.Section(scroll, "Effects")
	Toggle(scroll, "Glowing zones", "Start and end zones glow, with labels over them.", V.ZonesOn, V.ToggleZones)
	Toggle(scroll, "Map light", "Lights up the whole map for you on dark maps. Same as F.", V.MapLightOn, V.ToggleMapLight)
	UI.Section(scroll, "Gameplay")
	Toggle(scroll, "Autohop", "Hold jump to keep bunnyhopping.", function() return me:GetNW2Bool("surf_autohop", SURF.Config.DefaultAutoHop) end,
		function() Say("!auto") end)
	Toggle(scroll, "Hide other players", "Also hides their trails.", function() return ConVarOn("surf_hideplayers") end, function() Say("!hide") end)
	local HUD = SURF.HUD
	UI.Section(scroll, "HUD")
	UI.Row(scroll, { title = "Edit HUD layout", sub = "Move, resize or hide the timer, keys and the rest. Same as !hud.", right = "Edit",
		rightColor = UI.Accent(), onClick = function() HUD.Edit() end })
	local function Part(id, title, sub)
		Toggle(scroll, title, sub, function() return not HUD.Hidden(id) end, function() HUD.Toggle(id) end)
	end
	Part("lookat", "Player info", "Name, title, points and best time of the player you look at.")
	Part("keys", "Key display", "The keys you press and your mouse turning, or those of whoever you spectate.")
	Part("speed", "Speedometer", "Big speed under the crosshair.")
	Part("watchers", "Spectator list", "Who is watching you.")
	Part("split", "Checkpoint splits", "Your time at each checkpoint against your best and the record.")
end

-- Commands ----------------------------------------------------------------------

function BUILD.help(parent, d)
	local cmds = d.cmds
	if not cmds then
		cmds = {}
		for _, c in ipairs(SURF.ChatHints and SURF.ChatHints.cmds or {}) do
			cmds[#cmds + 1] = { cmd = "!" .. table.concat(c.n or {}, " !"), help = c.h, admin = c.a }
		end
	end
	Header(parent, "Commands", "Type them in chat. Typing ! shows hints and Tab completes them.")
	local keys = vgui.Create("DPanel", parent)
	keys:Dock(TOP)
	keys:SetTall(S(34))
	keys:DockMargin(0, 0, 0, S(10))
	local KEYS = { { "F1", "Menu" }, { "F2", "Records" }, { "F3", "Shop" }, { "F4", "Spectate" }, { "F", "Map light" } }
	keys.Paint = function(_, _, h)
		local x = 0
		for _, k in ipairs(KEYS) do
			local kw = UI.TextWidth(k[1], "SurfUI_Tiny") + S(14)
			draw.RoundedBox(4, x, h / 2 - S(11), kw, S(22), Color(255, 255, 255, 22))
			draw.SimpleText(k[1], "SurfUI_Tiny", x + kw / 2, h / 2, C.text, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			x = x + kw + S(6)
			draw.SimpleText(k[2], "SurfUI_Small", x, h / 2, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			x = x + UI.TextWidth(k[2], "SurfUI_Small") + S(18)
		end
	end
	local scroll
	local function Fill(q)
		scroll:Clear()
		for _, c in ipairs(cmds) do
			if q == "" or string.find(string.lower(c.cmd .. " " .. (c.help or "")), q, 1, true) then
				UI.Row(scroll, { title = c.cmd, sub = c.help, titleColor = UI.Accent(), tall = 46,
					right = c.admin and "Admin" or nil, rightColor = C.red })
			end
		end
	end
	UI.Search(parent, "Search commands...", Fill)
	scroll = UI.Scroll(parent)
	Fill("")
end

-- What the server opens ---------------------------------------------------------

for _, id in ipairs({ "home", "records", "players", "maps" }) do
	Menus[id] = function(data)
		if data.req then return Hub.Answer(id, data) end
		Hub.Open(id, data)
	end
end
function Menus.styles(data) Hub.Open("styles", data) end
function Menus.graphics() Hub.Open("settings", {}) end
function Menus.help(data) Hub.Open("help", data) end
-- F1 and !menu: opens the menu, or closes it when it's already open
function Menus.menu(data)
	if IsValid(hub) and not (data and data.page) then return hub:Close() end
	Hub.Open(data and data.page or "home")
end
