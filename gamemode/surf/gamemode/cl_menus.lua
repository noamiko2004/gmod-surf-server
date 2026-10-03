-- Small Derma menus opened by the server (!wr, !help, !shop, !maps, !style, !graphics, !vip)
local Menus = {}
SURF.Menus = Menus

local function Frame(title, w, h)
	local f = vgui.Create("DFrame")
	f:SetSize(w, h)
	f:Center()
	f:SetTitle("")
	f:MakePopup()
	f.Paint = function(_, pw, ph)
		draw.RoundedBox(10, 0, 0, pw, ph, Color(10, 12, 18, 240))
		draw.SimpleText(title, "SurfLarge", 16, 18, SURF.Config.Accent, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	return f
end

local function List(parent, columns)
	local l = vgui.Create("DListView", parent)
	l:Dock(FILL)
	l:DockMargin(0, 12, 0, 0)
	l:SetMultiSelect(false)
	for _, c in ipairs(columns) do
		local col = l:AddColumn(c[1])
		if c[2] then col:SetFixedWidth(c[2]) end
	end
	return l
end

function Menus.records(data)
	local f = Frame("Top times on " .. data.map .. " (" .. (data.total or 0) .. " finishers)", 560, 520)
	local l = List(f, { { "#", 40 }, { "Player" }, { "Time", 120 }, { "Date", 110 } })
	for i, r in ipairs(data.rows or {}) do
		l:AddLine(i, r.name, SURF.FormatTime(r.time), r.date and os.date("%Y-%m-%d", r.date) or "")
	end
	if #(data.rows or {}) == 0 then l:AddLine("", "No times yet. Be the first!", "", "") end
end

function Menus.players(data)
	local f = Frame("Top players (" .. (data.total or 0) .. " ranked)", 520, 520)
	local l = List(f, { { "#", 40 }, { "Player" }, { "Title", 110 }, { "Points", 80 } })
	for i, r in ipairs(data.rows or {}) do
		local t = SURF.Config.Titles[r.title] or SURF.Config.Titles[1]
		l:AddLine(i, r.name, t.name, r.points)
	end
	if #(data.rows or {}) == 0 then l:AddLine("", "Nobody ranked yet. Finish a map!", "", "") end
end

function Menus.help(data)
	local f = Frame("Commands", 560, 520)
	local l = List(f, { { "Command", 220 }, { "What it does" } })
	for _, c in ipairs(data.cmds or {}) do
		l:AddLine(c.cmd, (c.admin and "[Admin] " or "") .. c.help)
	end
	l:AddLine("F1 / F2 / F3 / F4", "Help / Records / Shop / Spectate")
end

function Menus.maps(data)
	local f = Frame("Maps (" .. #(data.maps or {}) .. ")  -  click to nominate", 460, 540)
	local l = List(f, { { "Map" }, { "Tier", 60 } })
	for _, m in ipairs(data.maps or {}) do
		local line = l:AddLine(m.name, m.tier > 0 and m.tier or "-")
		line.mapName = m.name
	end
	l.OnRowSelected = function(_, _, line)
		RunConsoleCommand("say", "!nominate " .. line.mapName)
		f:Close()
	end
end

-- The shop (!shop, F3, !vip) is in cl_shop.lua

function Menus.styles(data)
	local f = Frame("Styles  -  each has its own records", 460, 360)
	local scroll = vgui.Create("DScrollPanel", f)
	scroll:Dock(FILL)
	scroll:DockMargin(0, 12, 0, 0)
	for _, st in ipairs(data.styles or SURF.Config.Styles) do
		local b = scroll:Add("DButton")
		b:Dock(TOP)
		b:DockMargin(0, 0, 0, 6)
		b:SetTall(44)
		b:SetText("")
		local current = st.id == data.current
		b.Paint = function(self, w, h)
			local acc = SURF.Config.Accent
			local bg = current and Color(acc.r, acc.g, acc.b, 50) or (self:IsHovered() and Color(255, 255, 255, 20) or Color(255, 255, 255, 8))
			draw.RoundedBox(6, 0, 0, w, h, bg)
			draw.SimpleText(st.name, "SurfMedium", 12, 14, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(st.help or "", "SurfSmall", 12, 32, Color(170, 180, 195), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(current and "current" or ("!style " .. st.id), "SurfSmall", w - 12, h / 2, current and acc or Color(170, 180, 195), TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		end
		b.DoClick = function()
			RunConsoleCommand("say", "!style " .. st.id)
			f:Close()
		end
	end
end

function Menus.graphics()
	local V = SURF.Visuals
	local f = Frame("Graphics", 460, 390)
	local scroll = vgui.Create("DScrollPanel", f)
	scroll:Dock(FILL)
	scroll:DockMargin(0, 12, 0, 0)
	local function Row(title, help, right, active, click)
		local b = scroll:Add("DButton")
		b:Dock(TOP)
		b:DockMargin(0, 0, 0, 6)
		b:SetTall(44)
		b:SetText("")
		b.Paint = function(self, w, h)
			local acc = SURF.Config.Accent
			local on = active()
			local bg = on and Color(acc.r, acc.g, acc.b, 50) or (self:IsHovered() and Color(255, 255, 255, 20) or Color(255, 255, 255, 8))
			draw.RoundedBox(6, 0, 0, w, h, bg)
			draw.SimpleText(title, "SurfMedium", 12, 14, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(help, "SurfSmall", 12, 32, Color(170, 180, 195), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(right(), "SurfSmall", w - 12, h / 2, on and acc or Color(170, 180, 195), TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		end
		b.DoClick = click
	end
	for _, p in ipairs(V.Presets) do
		Row(p.name, p.help, function() return V.Current() == p and "on" or "" end, function() return V.Current() == p end,
			function() V.SetPreset(p.id) end)
	end
	Row("Glowing zones", "Start and end zones glow, with labels over them.",
		function() return V.ZonesOn() and "on" or "off" end, V.ZonesOn, V.ToggleZones)
	Row("Map light", "Lights up the whole map for you on dark maps. Same as F.",
		function() return V.MapLightOn() and "on" or "off" end, V.MapLightOn, V.ToggleMapLight)
end

net.Receive("surf.Menu", function()
	local kind = net.ReadString()
	local data = net.ReadTable()
	if Menus[kind] then Menus[kind](data) end
end)
