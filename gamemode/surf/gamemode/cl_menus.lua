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

-- Shop (!shop, !trail, F3): one tab per category, plus VIP. A price click
-- asks once more before buying; clicking what you have on takes it off.
local GOLD = Color(255, 200, 40)
local DIM = Color(170, 180, 195)
local shopFrame

local function VIPText(data)
	local status
	if data.vip then
		status = "You are a VIP" .. ((data.expires and data.expires > 0) and (" until " .. os.date("%Y-%m-%d", data.expires)) or "") .. ". Thank you!"
	else
		status = "VIP is purely cosmetic and never affects your times."
	end
	local bonus = data.rates and data.rates.VIPBonus or 0.5
	return status .. "\n\nPerks: VIP trails, chat tag and name color, a gold [VIP] chat tag and a gold name on the scoreboard, and "
		.. math.floor(bonus * 100) .. "% more coins for the shop.\n\nEvery purchase helps keep the server online."
end

local function VIPPanel(parent, data)
	local txt = vgui.Create("DLabel", parent)
	txt:Dock(FILL)
	txt:DockMargin(4, 12, 4, 4)
	txt:SetFont("SurfMedium")
	txt:SetWrap(true)
	txt:SetContentAlignment(7)
	txt:SetText(VIPText(data))
	if data.url and data.url ~= "" then
		local b = vgui.Create("DButton", parent)
		b:Dock(BOTTOM)
		b:SetTall(36)
		b:SetText("Open the store")
		b.DoClick = function() gui.OpenURL(data.url) end
	end
end

local function ItemRow(scroll, it, data, owned)
	local b = scroll:Add("DButton")
	b:Dock(TOP)
	b:DockMargin(0, 0, 0, 6)
	b:SetTall(46)
	b:SetText("")
	local on = (data.equipped or {})[it.cat] == it.id
	local have = SURF.ItemFree(it) or owned[it.key] or (it.vip and data.vip)
	local textX = 12
	if it.cat == "trail" or it.cat == "color" then textX = 38 end
	if it.cat == "sound" then
		textX = 54
		local play = vgui.Create("DButton", b)
		play:SetPos(8, 9)
		play:SetSize(38, 28)
		play:SetText("Play")
		play:SetFont("SurfSmall")
		play.DoClick = function() surface.PlaySound(it.sound) end
	end
	b.Paint = function(self, w, h)
		local acc = SURF.Config.Accent
		local bg = on and Color(acc.r, acc.g, acc.b, 50) or (self:IsHovered() and Color(255, 255, 255, 20) or Color(255, 255, 255, 8))
		draw.RoundedBox(6, 0, 0, w, h, bg)
		if it.cat == "trail" or it.cat == "color" then draw.RoundedBox(4, 12, 15, 16, 16, SURF.ItemColor(it)) end
		local title, tcol = it.name, color_white
		if it.cat == "tag" then title, tcol = "[" .. it.name .. "]", it.color end
		if it.cat == "color" then tcol = SURF.ItemColor(it) end
		draw.SimpleText(title, "SurfMedium", textX, 14, tcol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local sub
		if on then sub = "On. Click to take it off."
		elseif have then sub = SURF.ItemFree(it) and "Free" or (it.vip and not owned[it.key] and "VIP item" or "Yours")
		elseif it.price then sub = it.vip and "Buy it with coins, or free with VIP" or "Buy it with coins"
		else sub = "VIP only" end
		if it.cat == "color" then sub = sub .. "  |  " .. LocalPlayer():Nick() end
		draw.SimpleText(sub, "SurfSmall", textX, 32, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local right, rcol
		if on then right, rcol = "ON", acc
		elseif have then right, rcol = "Equip", color_white
		elseif it.price and self.armed and self.armed > CurTime() then right, rcol = "Buy for " .. it.price .. "?", GOLD
		elseif it.price then right, rcol = it.price .. " coins", (data.coins or 0) >= it.price and GOLD or Color(140, 140, 140)
		else right, rcol = "VIP", GOLD end
		draw.SimpleText(right, "SurfMedium", w - 14, h / 2, rcol, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
	b.DoClick = function(self)
		if on or have then
			net.Start("surf.ShopEquip")
			net.WriteString(it.cat)
			net.WriteString(on and "none" or it.id)
			net.SendToServer()
		elseif it.price then
			if (data.coins or 0) < it.price then
				chat.AddText(GOLD, "[Shop] ", color_white, it.name .. " costs " .. it.price .. " coins and you have " .. (data.coins or 0) .. ". Finish maps to earn more.")
			elseif self.armed and self.armed > CurTime() then
				self.armed = nil
				net.Start("surf.ShopBuy")
				net.WriteString(it.key)
				net.SendToServer()
			else
				self.armed = CurTime() + 3
			end
		else
			RunConsoleCommand("say", "!vip")
		end
	end
end

local function BuildShop(f, data)
	f:Clear()
	f.data = data
	local owned = {}
	for _, k in ipairs(data.owned or {}) do owned[k] = true end

	local tabs = vgui.Create("DPanel", f)
	tabs:Dock(TOP)
	tabs:DockMargin(0, 12, 0, 8)
	tabs:SetTall(32)
	tabs.Paint = nil
	local list = {}
	for _, c in ipairs(SURF.ShopCategories) do list[#list + 1] = { id = c.id, name = c.name } end
	list[#list + 1] = { id = "vip", name = "VIP" }
	for _, t in ipairs(list) do
		local tb = vgui.Create("DButton", tabs)
		tb:Dock(LEFT)
		tb:DockMargin(0, 0, 6, 0)
		tb:SetText("")
		surface.SetFont("SurfMedium")
		tb:SetWide(surface.GetTextSize(t.name) + 24)
		tb.Paint = function(self, w, h)
			local acc = SURF.Config.Accent
			local cur = f.tab == t.id
			draw.RoundedBox(6, 0, 0, w, h, cur and Color(acc.r, acc.g, acc.b, 70) or (self:IsHovered() and Color(255, 255, 255, 20) or Color(255, 255, 255, 8)))
			draw.SimpleText(t.name, "SurfMedium", w / 2, h / 2, t.id == "vip" and GOLD or color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		tb.DoClick = function()
			f.tab = t.id
			BuildShop(f, f.data)
		end
	end

	local foot = vgui.Create("DLabel", f)
	foot:Dock(BOTTOM)
	foot:DockMargin(2, 6, 2, 0)
	foot:SetFont("SurfSmall")
	foot:SetTextColor(DIM)
	foot:SetText("Earn coins by finishing maps, beating your best and playing. Type !coins for details.")

	local body = vgui.Create("DPanel", f)
	body:Dock(FILL)
	body.Paint = nil
	if f.tab == "vip" then return VIPPanel(body, data) end
	local scroll = vgui.Create("DScrollPanel", body)
	scroll:Dock(FILL)
	for _, c in ipairs(SURF.ShopCategories) do
		if c.id == f.tab then
			for _, it in ipairs(c.list) do
				if it.id ~= "none" then ItemRow(scroll, it, data, owned) end
			end
		end
	end
end

function Menus.shop(data)
	if data.refresh and not IsValid(shopFrame) then return end
	if not IsValid(shopFrame) then
		shopFrame = Frame("Shop", 640, 560)
		local paint = shopFrame.Paint
		shopFrame.Paint = function(self, pw, ph)
			paint(self, pw, ph)
			draw.SimpleText(string.Comma(self.data and self.data.coins or 0) .. " coins", "SurfLarge", pw - 44, 18, GOLD, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		end
		shopFrame.tab = data.tab or "trail"
	elseif not data.refresh then
		shopFrame.tab = data.tab or shopFrame.tab
	end
	-- Rebuild the frame's own content but keep its close button
	local close = shopFrame.btnClose
	for _, child in ipairs(shopFrame:GetChildren()) do
		if child ~= close and child ~= shopFrame.btnMaxim and child ~= shopFrame.btnMinim and child ~= shopFrame.lblTitle then child:Remove() end
	end
	local holder = vgui.Create("DPanel", shopFrame)
	holder:Dock(FILL)
	holder.Paint = nil
	holder.tab = shopFrame.tab
	BuildShop(holder, data)
	shopFrame.data = data
	-- remember the tab when it changes inside the holder
	holder.Think = function(self) shopFrame.tab = self.tab end
end

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

function Menus.vip(data)
	VIPPanel(Frame("VIP", 460, 300), data)
end

net.Receive("surf.Menu", function()
	local kind = net.ReadString()
	local data = net.ReadTable()
	if Menus[kind] then Menus[kind](data) end
end)
