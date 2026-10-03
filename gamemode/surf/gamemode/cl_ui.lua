-- The look of every menu: colors, fonts and ready-made pieces (window, buttons,
-- rows, tabs, side menu, lists, text boxes, dialogs, right-click menus,
-- toasts). Build menus from these so the whole server looks the same.
--
--   local UI = SURF.UI
--   local f = UI.Frame("Shop", 640, 560, { id = "shop", sub = "Trails and more",
--       right = function() return "1,200 coins", UI.Col.gold end })
--   UI.Tabs(f, { { id = "trail", name = "Trails" }, { id = "tag", name = "Tags" } }, "trail", function(id) end)
--   local scroll = UI.Scroll(f)
--   UI.Row(scroll, { title = "Gold Plasma", sub = "800 coins", swatch = color, right = "Buy", onClick = fn })
--   UI.Button(f, "Open the store", "primary", fn):Dock(BOTTOM)
--
-- Sizes are written for 1080p; UI.S(px) scales them up on bigger screens.
-- Fonts: SurfUI_Title, SurfUI_Head, SurfUI_Body, SurfUI_Small, SurfUI_Tiny,
-- SurfUI_Big. Escape closes the newest window instead of opening the game menu.
SURF.UI = SURF.UI or {}
local UI = SURF.UI

UI.Col = {
	bg = Color(13, 15, 21, 250),
	header = Color(19, 22, 30, 255),
	panel = Color(19, 22, 30, 255), -- side menus and lists
	card = Color(255, 255, 255, 7),
	line = Color(255, 255, 255, 12),
	text = Color(236, 239, 245),
	dim = Color(150, 160, 178),
	faint = Color(100, 108, 124),
	gold = Color(255, 200, 40),
	red = Color(240, 80, 80),
	green = Color(70, 210, 120),
	discord = Color(88, 101, 242),
	dark = Color(8, 11, 16),
}
local C = UI.Col

function UI.Accent() return SURF.Config.Accent end
function UI.Alpha(c, a) return Color(c.r, c.g, c.b, a) end

-- Scale ---------------------------------------------------------------------

UI.Scale = 1
function UI.S(px) return math.Round(px * UI.Scale) end
local S = UI.S

local FONTS = {
	{ "SurfUI_Title", 23, 700 }, { "SurfUI_Head", 19, 600 }, { "SurfUI_Body", 17, 500 },
	{ "SurfUI_Small", 14, 500 }, { "SurfUI_Tiny", 12, 700 }, { "SurfUI_Big", 30, 800 },
}
function UI.CreateFonts()
	UI.Scale = math.Clamp(ScrH() / 1080, 1, 1.6)
	for _, f in ipairs(FONTS) do
		surface.CreateFont(f[1], { font = "Roboto", size = S(f[2]), weight = f[3], antialias = true, extended = true })
	end
end
UI.CreateFonts()
hook.Add("OnScreenSizeChanged", "surf_ui", UI.CreateFonts)

function UI.TextWidth(text, font)
	surface.SetFont(font or "SurfUI_Body")
	return (surface.GetTextSize(text or ""))
end

-- Shortens text with "..." to fit a width
function UI.Fit(text, font, room)
	text = tostring(text or "")
	surface.SetFont(font)
	if surface.GetTextSize(text) <= room then return text end
	while #text > 1 and surface.GetTextSize(text .. "...") > room do text = string.sub(text, 1, -2) end
	return text .. "..."
end

-- 0..1 that follows the hover state smoothly, for fades
function UI.Hover(pnl, on)
	pnl.uiHover = Lerp(math.min(FrameTime() * 14, 1), pnl.uiHover or 0, on and 1 or 0)
	return pnl.uiHover
end
local Hover = UI.Hover

local function Click() surface.PlaySound("garrysmod/ui_click.wav") end
UI.Click = Click

-- A value or a function that gives it
local function V(x, ...)
	if isfunction(x) then return x(...) end
	return x
end

local function DrawX(w, h, col)
	draw.NoTexture()
	surface.SetDrawColor(col)
	local len = math.floor(math.min(w, h) * 0.4)
	surface.DrawTexturedRectRotated(w / 2, h / 2, len, 2, 45)
	surface.DrawTexturedRectRotated(w / 2, h / 2, len, 2, -45)
end

-- Windows ---------------------------------------------------------------------

UI.Open = {} -- windows by id
local stack = {} -- open windows, newest last
local HEADER = 52

function UI.HeaderHeight() return S(HEADER) end

-- A window with a title bar and a close button. Children dock inside it.
-- opts: id (opening a window with the same id replaces it, in the same
-- spot), sub (smaller text after the title), right (function returning text
-- and color, drawn on the right of the title bar), noPopup.
function UI.Frame(title, w, h, opts)
	opts = opts or {}
	local old = opts.id and UI.Open[opts.id]
	local ox, oy
	if IsValid(old) then
		ox, oy = old:GetPos()
		old:Remove()
	end
	w, h = math.min(S(w), ScrW() - 20), math.min(S(h), ScrH() - 20)
	local f = vgui.Create("DFrame")
	f:SetSize(w, h)
	if ox then f:SetPos(math.min(ox, ScrW() - w), math.min(oy, ScrH() - h)) else f:Center() end
	f:SetTitle("")
	f:SetScreenLock(true)
	f.lblTitle:SetVisible(false)
	f.btnMaxim:SetVisible(false)
	f.btnMinim:SetVisible(false)
	f:DockPadding(S(16), S(HEADER) + S(14), S(16), S(16))
	f.uiTitle, f.uiSub, f.uiRight, f.uiId = title, opts.sub, opts.right, opts.id

	f.Paint = function(self, pw, ph)
		local hh = S(HEADER)
		draw.RoundedBox(8, 0, 0, pw, ph, C.bg)
		draw.RoundedBoxEx(8, 0, 0, pw, hh, C.header, true, true, false, false)
		surface.SetDrawColor(C.line)
		surface.DrawRect(0, hh - 1, pw, 1)
		local acc = UI.Accent()
		draw.RoundedBox(2, S(16), hh / 2 - S(10), S(4), S(20), acc)
		local x = S(30)
		draw.SimpleText(self.uiTitle or "", "SurfUI_Title", x, hh / 2, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local rightEdge = pw - S(HEADER) - S(4)
		if self.uiRight then
			local text, col = self.uiRight(self)
			if text and text ~= "" then
				draw.SimpleText(text, "SurfUI_Head", rightEdge, hh / 2, col or C.text, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
				rightEdge = rightEdge - UI.TextWidth(text, "SurfUI_Head") - S(16)
			end
		end
		if self.uiSub and self.uiSub ~= "" then
			local sx = x + UI.TextWidth(self.uiTitle or "", "SurfUI_Title") + S(12)
			draw.SimpleText(UI.Fit(self.uiSub, "SurfUI_Small", rightEdge - sx), "SurfUI_Small", sx, hh / 2 + 1, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
	end

	-- The frame's own close button, restyled (code that clears a frame's
	-- children can keep skipping btnClose)
	local close = f.btnClose
	close:SetText("")
	close.Paint = function(s, bw, bh)
		local hv = Hover(s, s:IsHovered())
		if hv > 0.01 then draw.RoundedBox(6, 0, 0, bw, bh, Color(C.red.r, C.red.g, C.red.b, 210 * hv)) end
		local c = 150 + 105 * hv
		DrawX(bw, bh, Color(c, c, c))
	end
	local layout = f.PerformLayout
	f.PerformLayout = function(self, pw, ph)
		layout(self, pw, ph)
		local hh, bs = S(HEADER), S(32)
		self.btnClose:SetSize(bs, bs)
		self.btnClose:SetPos(self:GetWide() - bs - (hh - bs) / 2, (hh - bs) / 2)
	end

	-- Drag by the whole title bar
	f.OnMousePressed = function(self, code)
		local _, my = self:CursorPos()
		if code == MOUSE_LEFT and my < S(HEADER) then
			self.Dragging = { gui.MouseX() - self.x, gui.MouseY() - self.y }
			self:MouseCapture(true)
		end
	end

	-- Fade in and out
	f:SetAlpha(0)
	f:AlphaTo(255, 0.12, 0)
	f.Close = function(self)
		if self.uiClosing then return end
		self.uiClosing = true
		self:SetMouseInputEnabled(false)
		self:SetKeyboardInputEnabled(false)
		self:AlphaTo(0, 0.1, 0, function() if IsValid(self) then self:Remove() end end)
		self:OnClose()
	end

	if opts.id then UI.Open[opts.id] = f end
	stack[#stack + 1] = f
	f.OnRemove = function(self)
		if self.uiId and UI.Open[self.uiId] == self then UI.Open[self.uiId] = nil end
		table.RemoveByValue(stack, self)
	end
	if not opts.noPopup then f:MakePopup() end
	return f
end

-- Closes the window with this id, if it's open
function UI.Close(id)
	local f = UI.Open[id]
	if IsValid(f) then f:Close() end
end

-- Escape closes the newest window instead of opening the game menu
hook.Add("OnPauseMenuShow", "surf_ui", function()
	for i = #stack, 1, -1 do
		local f = stack[i]
		if IsValid(f) and f:IsVisible() and not f.uiClosing then
			f:Close()
			return false
		end
	end
end)

-- Buttons ---------------------------------------------------------------------

-- kind: "primary" (accent), "ghost" (plain), "danger" (red), "gold"
function UI.Button(parent, text, kind, onClick)
	local b = vgui.Create("DButton", parent)
	b:SetText("")
	b:SetTall(S(36))
	b.uiText, b.uiKind = text, kind or "ghost"
	b.Paint = function(s, w, h)
		local hv = Hover(s, s:IsHovered() and s:IsEnabled())
		local k = s.uiKind
		local bg, fg
		if not s:IsEnabled() then
			bg, fg = Color(255, 255, 255, 6), C.faint
		elseif k == "primary" then
			local a = UI.Accent()
			bg, fg = Color(a.r, a.g, a.b, 205 + 50 * hv), C.dark
		elseif k == "gold" then
			bg, fg = Color(C.gold.r, C.gold.g, C.gold.b, 205 + 50 * hv), C.dark
		elseif k == "danger" then
			bg, fg = Color(C.red.r, C.red.g, C.red.b, 40 + 170 * hv), hv > 0.5 and color_white or Color(255, 140, 140)
		else
			bg, fg = Color(255, 255, 255, 12 + 14 * hv), C.text
		end
		draw.RoundedBox(6, 0, s:IsDown() and 1 or 0, w, h - (s:IsDown() and 1 or 0), bg)
		draw.SimpleText(V(s.uiText, s), "SurfUI_Body", w / 2, h / 2, fg, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end
	b.DoClick = function(s)
		Click()
		if onClick then onClick(s) end
	end
	function b:SetLabel(t) self.uiText = t end
	-- Width for the label plus padding
	function b:Fit(pad)
		self:SetWide(UI.TextWidth(V(self.uiText, self), "SurfUI_Body") + S(pad or 32))
		return self
	end
	return b
end

-- A row of buttons along the bottom (or top) of a panel: UI.ButtonBar(f, BOTTOM)
function UI.ButtonBar(parent, dock)
	local bar = vgui.Create("DPanel", parent)
	bar:Dock(dock or BOTTOM)
	bar:SetTall(S(36))
	bar:DockMargin(0, dock == TOP and 0 or S(10), 0, dock == TOP and S(10) or 0)
	bar.Paint = nil
	-- bar:AddButton(text, kind, fn, side) adds a button on the LEFT or RIGHT
	function bar:AddButton(text, kind, fn, side)
		local b = UI.Button(self, text, kind, fn)
		b:Dock(side or LEFT)
		b:DockMargin(side == RIGHT and S(8) or 0, 0, side == RIGHT and 0 or S(8), 0)
		b:Fit()
		return b
	end
	return bar
end

-- A clickable card row.
-- o: title, sub, right (text), rightColor, titleColor, swatch (color), active
-- (bool), icon (material path), onClick, onRightClick, tall, paint(s, w, h).
-- Any of title/sub/right/rightColor/titleColor/swatch/active may be a function.
function UI.Row(parent, o)
	local b = parent:Add("DButton")
	b:Dock(TOP)
	b:DockMargin(0, 0, 0, S(6))
	b:SetTall(S(o.tall or 50))
	b:SetText("")
	b:SetCursor(o.onClick and "hand" or "arrow")
	b.uiRow = o
	local mat = o.icon and Material(o.icon)
	b.Paint = function(s, w, h)
		local active = V(o.active, s)
		local hv = Hover(s, s:IsHovered() and o.onClick ~= nil)
		local acc = UI.Accent()
		local bg = active and Color(acc.r, acc.g, acc.b, 40 + 20 * hv) or Color(255, 255, 255, 7 + 12 * hv)
		draw.RoundedBox(6, 0, 0, w, h, bg)
		if active then draw.RoundedBox(2, 0, S(8), S(3), h - S(16), acc) end
		local x = S(14)
		local sw = V(o.swatch, s)
		if sw then
			draw.RoundedBox(4, x, h / 2 - S(9), S(18), S(18), sw)
			x = x + S(30)
		elseif mat then
			surface.SetMaterial(mat)
			surface.SetDrawColor(255, 255, 255)
			surface.DrawTexturedRect(x, h / 2 - S(8), S(16), S(16))
			x = x + S(28)
		end
		local right, rw = V(o.right, s), 0
		if right and right ~= "" then
			draw.SimpleText(right, "SurfUI_Body", w - S(14), h / 2, V(o.rightColor, s) or (active and acc or C.dim), TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
			rw = UI.TextWidth(right, "SurfUI_Body") + S(20)
		end
		local room = w - x - rw - S(14)
		local title, sub = V(o.title, s) or "", V(o.sub, s)
		local tcol = V(o.titleColor, s) or C.text
		if sub and sub ~= "" then
			draw.SimpleText(UI.Fit(title, "SurfUI_Body", room), "SurfUI_Body", x, h / 2 - S(9), tcol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(UI.Fit(sub, "SurfUI_Small", room), "SurfUI_Small", x, h / 2 + S(10), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		else
			draw.SimpleText(UI.Fit(title, "SurfUI_Body", room), "SurfUI_Body", x, h / 2, tcol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		if o.paint then o.paint(s, w, h) end
	end
	b.DoClick = function(s)
		if not o.onClick then return end
		Click()
		o.onClick(s)
	end
	b.DoRightClick = function(s) if o.onRightClick then o.onRightClick(s) end end
	return b
end

-- Tabs across the top of a panel. tabs: { { id, name, color } }
-- Returns the bar; bar:SetActive(id) changes the highlighted one.
function UI.Tabs(parent, tabs, active, onSelect)
	local bar = vgui.Create("DPanel", parent)
	bar:Dock(TOP)
	bar:SetTall(S(34))
	bar:DockMargin(0, 0, 0, S(12))
	bar.Paint = nil
	bar.active = active
	for _, t in ipairs(tabs) do
		local b = vgui.Create("DButton", bar)
		b:Dock(LEFT)
		b:DockMargin(0, 0, S(6), 0)
		b:SetText("")
		b:SetWide(UI.TextWidth(t.name, "SurfUI_Body") + S(28))
		b.Paint = function(s, w, h)
			local cur = bar.active == t.id
			local hv = Hover(s, s:IsHovered())
			local acc = UI.Accent()
			draw.RoundedBox(6, 0, 0, w, h, cur and Color(acc.r, acc.g, acc.b, 60) or Color(255, 255, 255, 7 + 12 * hv))
			draw.SimpleText(t.name, "SurfUI_Body", w / 2, h / 2, t.color or (cur and C.text or C.dim), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		b.DoClick = function()
			if bar.active == t.id then return end
			Click()
			bar.active = t.id
			onSelect(t.id)
		end
	end
	function bar:SetActive(id) self.active = id end
	return bar
end

-- A menu down the left side. items: { { id, name, icon, color } or { spacer = true } }
-- onSelect(id) returns false to keep the old item highlighted (for items that
-- open another window).
function UI.Sidebar(parent, items, active, onSelect, width)
	local side = vgui.Create("DPanel", parent)
	side:Dock(LEFT)
	side:SetWide(S(width or 190))
	side:DockMargin(0, 0, S(14), 0)
	side:DockPadding(S(6), S(6), S(6), S(6))
	side.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, C.panel) end
	side.active = active
	for _, it in ipairs(items) do
		if it.spacer then
			local sp = vgui.Create("DPanel", side)
			sp:Dock(TOP)
			sp:SetTall(S(13))
			sp.Paint = function(_, w, h)
				surface.SetDrawColor(C.line)
				surface.DrawRect(S(8), math.floor(h / 2), w - S(16), 1)
			end
		else
			local b = vgui.Create("DButton", side)
			b:Dock(TOP)
			b:SetTall(S(38))
			b:DockMargin(0, 0, 0, S(2))
			b:SetText("")
			local mat = it.icon and Material(it.icon)
			b.Paint = function(s, w, h)
				local cur = side.active == it.id
				local hv = Hover(s, s:IsHovered())
				local acc = UI.Accent()
				if cur then
					draw.RoundedBox(6, 0, 0, w, h, Color(acc.r, acc.g, acc.b, 45))
					draw.RoundedBox(2, 0, S(9), S(3), h - S(18), acc)
				elseif hv > 0.01 then
					draw.RoundedBox(6, 0, 0, w, h, Color(255, 255, 255, 12 * hv))
				end
				local x = S(14)
				if mat then
					surface.SetMaterial(mat)
					surface.SetDrawColor(255, 255, 255, (cur or hv > 0.5) and 255 or 190)
					surface.DrawTexturedRect(x, h / 2 - S(8), S(16), S(16))
					x = x + S(28)
				end
				draw.SimpleText(it.name, "SurfUI_Body", x, h / 2, it.color or ((cur or hv > 0.5) and C.text or C.dim), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			end
			b.DoClick = function()
				Click()
				if onSelect(it.id) ~= false then side.active = it.id end
			end
		end
	end
	function side:SetActive(id) self.active = id end
	return side
end

-- Lists and scrolling -----------------------------------------------------------

function UI.StyleBar(bar)
	if not IsValid(bar) then return end
	if bar.SetHideButtons then bar:SetHideButtons(true) end
	bar.Paint = function(_, w, h) draw.RoundedBox(3, w / 2 - S(3), 0, S(6), h, Color(255, 255, 255, 6)) end
	if IsValid(bar.btnGrip) then
		bar.btnGrip.Paint = function(s, w, h)
			local hv = Hover(s, s:IsHovered() or s.Depressed)
			draw.RoundedBox(3, w / 2 - S(3), 0, S(6), h, Color(255, 255, 255, 45 + 55 * hv))
		end
	end
	if IsValid(bar.btnUp) then bar.btnUp.Paint = function() end end
	if IsValid(bar.btnDown) then bar.btnDown.Paint = function() end end
end

function UI.Scroll(parent)
	local s = vgui.Create("DScrollPanel", parent)
	s:Dock(FILL)
	local bar = s:GetVBar()
	bar:SetWide(S(12))
	UI.StyleBar(bar)
	return s
end

-- A sortable table. columns: { { "Name", width (or nil to fill), align = "right" } }
function UI.List(parent, columns)
	local l = vgui.Create("DListView", parent)
	l:Dock(FILL)
	l:SetMultiSelect(false)
	l:SetHeaderHeight(S(30))
	l:SetDataHeight(S(30))
	l.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, C.panel) end
	UI.StyleBar(l.VBar)
	for i, c in ipairs(columns) do
		local col = l:AddColumn(c[1])
		if c[2] then col:SetFixedWidth(S(c[2])) end
		col.Header:SetFont("SurfUI_Tiny")
		col.Header:SetTextColor(C.dim)
		col.Header.Paint = function(_, w, h)
			surface.SetDrawColor(C.line)
			surface.DrawRect(0, h - 1, w, 1)
		end
		if c.align == "right" then col.Header:SetContentAlignment(6) end
		col.Header:SetTextInset(S(10), 0)
	end
	local add = l.AddLine
	l.AddLine = function(self, ...)
		local line = add(self, ...)
		for i, lab in pairs(line.Columns) do
			lab:SetFont("SurfUI_Body")
			lab:SetTextColor(C.text)
			lab:SetTextInset(S(10), 0)
			if columns[i] and columns[i].align == "right" then lab:SetContentAlignment(6) end
		end
		line.Paint = function(s, w, h)
			local hv = Hover(s, s:IsHovered())
			if s:IsLineSelected() then
				local a = UI.Accent()
				draw.RoundedBox(4, S(4), 0, w - S(8), h, Color(a.r, a.g, a.b, 55))
			elseif hv > 0.01 then
				draw.RoundedBox(4, S(4), 0, w - S(8), h, Color(255, 255, 255, 12 * hv))
			end
		end
		return line
	end
	-- Colors one cell of a line: UI.CellColor(line, 2, color)
	return l
end

function UI.CellColor(line, i, col)
	if line.Columns and IsValid(line.Columns[i]) then line.Columns[i]:SetTextColor(col) end
end

-- Text ------------------------------------------------------------------------

function UI.Label(parent, text, font, color, wrap)
	local l = vgui.Create("DLabel", parent)
	l:SetFont(font or "SurfUI_Body")
	l:SetTextColor(color or C.text)
	l:SetText(text or "")
	if wrap then
		l:SetWrap(true)
		l:SetAutoStretchVertical(true)
	else
		l:SizeToContents()
	end
	return l
end

-- Small grey capitals above a group of rows
function UI.Section(parent, text)
	local l = parent:Add("DLabel")
	l:SetFont("SurfUI_Tiny")
	l:SetTextColor(C.dim)
	l:SetText(string.upper(text))
	l:Dock(TOP)
	l:DockMargin(S(2), S(6), 0, S(6))
	l:SizeToContentsY()
	return l
end

-- A grey line of text where a list has nothing in it
function UI.Empty(parent, text)
	local p = parent:Add("DPanel")
	p:Dock(TOP)
	p:SetTall(S(80))
	p.Paint = function(_, w, h)
		draw.SimpleText(text, "SurfUI_Body", w / 2, h / 2, C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end
	return p
end

-- "Loading..." with a spinning arc, until the panel is cleared
function UI.Loading(parent)
	local p = vgui.Create("DPanel", parent)
	p:Dock(FILL)
	p.Paint = function(_, w, h)
		local t = RealTime() * 6
		local acc = UI.Accent()
		for i = 0, 7 do
			local a = t + i * math.pi / 4
			local alpha = 40 + 215 * ((i / 7) ^ 2)
			draw.RoundedBox(S(3), w / 2 + math.cos(a) * S(16) - S(3), h / 2 - S(14) + math.sin(a) * S(16) - S(3), S(6), S(6), Color(acc.r, acc.g, acc.b, alpha))
		end
		draw.SimpleText("Loading...", "SurfUI_Small", w / 2, h / 2 + S(22), C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end
	return p
end

-- Text boxes ------------------------------------------------------------------

function UI.Entry(parent, placeholder)
	local e = vgui.Create("DTextEntry", parent)
	e:SetFont("SurfUI_Body")
	e:SetTall(S(36))
	e:SetDrawLanguageID(false)
	e:SetTextInset(S(10), 0)
	e.uiPlaceholder = placeholder
	e.Paint = function(s, w, h)
		local focus = s:HasFocus()
		draw.RoundedBox(6, 0, 0, w, h, Color(255, 255, 255, focus and 18 or 10))
		if focus then
			local a = UI.Accent()
			draw.RoundedBox(2, S(6), h - S(2), w - S(12), S(2), a)
		end
		if s:GetValue() == "" and s.uiPlaceholder then
			draw.SimpleText(s.uiPlaceholder, "SurfUI_Body", S(10), h / 2, C.faint, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		s:DrawTextEntryText(C.text, UI.Accent(), C.text)
	end
	return e
end

-- A search box docked at the top; onChange(text) runs as you type
function UI.Search(parent, placeholder, onChange)
	local e = UI.Entry(parent, placeholder or "Search...")
	e:Dock(TOP)
	e:DockMargin(0, 0, 0, S(10))
	e:SetUpdateOnType(true)
	e.OnValueChange = function(_, v) onChange(string.lower(string.Trim(v or ""))) end
	return e
end

-- Cards and stats -----------------------------------------------------------------

function UI.Card(parent)
	local c = vgui.Create("DPanel", parent)
	c.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, C.card) end
	c:DockPadding(S(14), S(12), S(14), S(12))
	return c
end

-- Children of a grid get equal widths: UI.Grid(parent, 3, 74) then add panels
function UI.Grid(parent, cols, cellTall, gap)
	local g = vgui.Create("DPanel", parent)
	g:Dock(TOP)
	g:DockMargin(0, 0, 0, S(12))
	g.Paint = nil
	gap = S(gap or 10)
	g.PerformLayout = function(self, w)
		local kids = self:GetChildren()
		local cw = math.floor((w - gap * (cols - 1)) / cols)
		local ch = S(cellTall)
		for i, k in ipairs(kids) do
			local c, r = (i - 1) % cols, math.floor((i - 1) / cols)
			k:SetPos(c * (cw + gap), r * (ch + gap))
			k:SetSize(cw, ch)
		end
		local rows = math.max(1, math.ceil(#kids / cols))
		self:SetTall(rows * ch + (rows - 1) * gap)
	end
	return g
end

-- A number with a label above it. value and color may be functions.
function UI.Stat(parent, label, value, color)
	local c = vgui.Create("DPanel", parent)
	c.Paint = function(_, w, h)
		draw.RoundedBox(8, 0, 0, w, h, C.card)
		draw.SimpleText(string.upper(label), "SurfUI_Tiny", S(14), S(18), C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(UI.Fit(tostring(V(value) or ""), "SurfUI_Head", w - S(28)), "SurfUI_Head", S(14), h - S(22), V(color) or C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	return c
end

-- A player's Steam picture: who is a player or a SteamID64
function UI.Avatar(parent, who, size)
	local a = vgui.Create("AvatarImage", parent)
	a:SetSize(S(size or 32), S(size or 32))
	if isstring(who) then
		a:SetSteamID(who, 64)
	elseif IsValid(who) then
		a:SetPlayer(who, 64)
	end
	return a
end

-- Dialogs ---------------------------------------------------------------------

local function Dialog(title, w, h)
	local f = UI.Frame(title, w, h, { id = "surf_dialog" })
	f:DoModal()
	return f
end

-- Asks before doing something. danger = true makes the button red.
function UI.Confirm(title, text, yesText, onYes, danger)
	local f = Dialog(title, 440, 210)
	local msg = UI.Label(f, text, "SurfUI_Body", C.text, true)
	msg:Dock(TOP)
	local bar = UI.ButtonBar(f, BOTTOM)
	bar:AddButton(yesText or "Yes", danger and "danger" or "primary", function()
		f:Close()
		onYes()
	end, RIGHT)
	bar:AddButton("Cancel", "ghost", function() f:Close() end, RIGHT)
	return f
end

-- Asks for some text (or a number). opts: numeric, placeholder, okText,
-- choices = { { label, value } } quick picks that fill the box, danger.
function UI.Prompt(title, text, default, onOk, opts)
	opts = opts or {}
	local f = Dialog(title, 460, opts.choices and 270 or 230)
	local msg = UI.Label(f, text, "SurfUI_Body", C.text, true)
	msg:Dock(TOP)
	local e = UI.Entry(f, opts.placeholder)
	e:Dock(TOP)
	e:DockMargin(0, S(10), 0, 0)
	if opts.numeric then e:SetNumeric(true) end
	e:SetValue(default or "")
	if opts.choices then
		local quick = UI.ButtonBar(f, TOP)
		quick:DockMargin(0, S(10), 0, 0)
		quick:SetTall(S(30))
		for _, ch in ipairs(opts.choices) do
			local b = quick:AddButton(ch[1], "ghost", function()
				e:SetValue(tostring(ch[2]))
				e:RequestFocus()
				e:SetCaretPos(#tostring(ch[2]))
			end)
			b:SetTall(S(30))
		end
	end
	local function Submit()
		local v = string.Trim(e:GetValue() or "")
		if v == "" and not opts.allowEmpty then return end
		f:Close()
		onOk(v)
	end
	e.OnEnter = Submit
	local bar = UI.ButtonBar(f, BOTTOM)
	bar:AddButton(opts.okText or "OK", opts.danger and "danger" or "primary", Submit, RIGHT)
	bar:AddButton("Cancel", "ghost", function() f:Close() end, RIGHT)
	e:RequestFocus()
	return f
end

-- Pick one from a long list, with a search box.
-- options: { { label, value, sub, color } }, onPick(value, option)
function UI.Pick(title, options, onPick)
	local f = Dialog(title, 460, 540)
	local scroll
	local function Fill(q)
		scroll:Clear()
		local n = 0
		for _, o in ipairs(options) do
			if q == "" or string.find(string.lower(o[1]), q, 1, true) then
				n = n + 1
				UI.Row(scroll, { title = o[1], sub = o.sub, swatch = o.color, tall = o.sub and 50 or 40, onClick = function()
					f:Close()
					onPick(o[2], o)
				end })
			end
		end
		if n == 0 then UI.Empty(scroll, "Nothing matches.") end
	end
	local search = UI.Search(f, "Search...", Fill)
	scroll = UI.Scroll(f)
	Fill("")
	search:RequestFocus()
	return f
end

-- Right-click menus -----------------------------------------------------------
-- local m = UI.Menu() m:AddOption("Kick", fn):SetIcon("icon16/door_out.png") UI.OpenMenu(m)

function UI.Menu() return DermaMenu() end

local function StyleMenu(m)
	m.Paint = function(_, w, h)
		draw.RoundedBox(6, 0, 0, w, h, Color(24, 27, 36, 252))
	end
	for _, opt in ipairs(m:GetCanvas():GetChildren()) do
		if opt.SetIcon then
			opt:SetFont("SurfUI_Small")
			opt:SetTextColor(opt.uiColor or C.text)
			opt.Paint = function(s, w, h)
				local hv = Hover(s, s:IsHovered())
				if hv > 0.01 then draw.RoundedBox(4, S(3), 1, w - S(6), h - 2, Color(255, 255, 255, 20 * hv)) end
			end
			if opt.SubMenu then StyleMenu(opt.SubMenu) end
		else
			opt.Paint = function(_, w, h)
				surface.SetDrawColor(C.line)
				surface.DrawRect(S(6), 0, w - S(12), h)
			end
		end
	end
end

function UI.OpenMenu(m)
	StyleMenu(m)
	m:Open()
	return m
end

-- Toasts ------------------------------------------------------------------------
-- A short message at the top of the screen: UI.Toast("Saved", UI.Col.green)

local toasts = {}
function UI.Toast(text, col)
	toasts[#toasts + 1] = { text = tostring(text), col = col or UI.Accent(), at = RealTime() }
	if #toasts > 4 then table.remove(toasts, 1) end
end

hook.Add("DrawOverlay", "surf_ui_toasts", function()
	if #toasts == 0 then return end
	local now, y = RealTime(), S(70)
	for i = #toasts, 1, -1 do
		local t = toasts[i]
		local age = now - t.at
		if age > 4 then
			table.remove(toasts, i)
		else
			local alpha = math.min(1, age * 8, (4 - age) * 3)
			local w = UI.TextWidth(t.text, "SurfUI_Body") + S(40)
			local x = ScrW() / 2 - w / 2
			draw.RoundedBox(8, x, y, w, S(38), Color(19, 22, 30, 245 * alpha))
			draw.RoundedBox(2, x + S(10), y + S(11), S(4), S(16), Color(t.col.r, t.col.g, t.col.b, 255 * alpha))
			draw.SimpleText(t.text, "SurfUI_Body", x + S(24), y + S(19), Color(C.text.r, C.text.g, C.text.b, 255 * alpha), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			y = y + S(44)
		end
	end
end)
