-- The shop menu (!shop, F3, !vip), hats on players, and admin price changes.
-- Left: categories and VIP. Middle: the items. Right: a live preview of the
-- selected item (3D for hats and skins) with its Buy / Equip button.
local Menus = SURF.Menus
local GOLD = Color(255, 200, 40)
local DIM = Color(170, 180, 195)
local MUTED = Color(120, 128, 140)
local PANEL = Color(255, 255, 255, 8)
local HOVER = Color(255, 255, 255, 18)
local shopFrame

local function Acc(a) local c = SURF.Config.Accent return Color(c.r, c.g, c.b, a or 255) end

-- Admin changes (price, VIP, hidden, coin rates, VIP prices) ---------------

local defaults = {}
for key, it in pairs(SURF.ItemByKey) do defaults[key] = { price = it.price, vip = it.vip, hidden = it.hidden } end

net.Receive("surf.ShopOverrides", function()
	local o = net.ReadTable() or {}
	local items = istable(o.items) and o.items or {}
	for key, it in pairs(SURF.ItemByKey) do
		local d, x = defaults[key], items[key] or {}
		it.price, it.vip, it.hidden = d.price, d.vip, d.hidden
		if x.price ~= nil then it.price = (x.price > 0) and x.price or nil end
		if x.vip ~= nil then it.vip = x.vip or nil end
		if x.hidden ~= nil then it.hidden = x.hidden or nil end
	end
	if istable(o.coins) then for k, v in pairs(o.coins) do SURF.Config.Coins[k] = v end end
	if istable(o.vip) then SURF.Config.VIPPackages = o.vip end
end)

-- Hats ----------------------------------------------------------------------

local hatEnts = {}
local function HatEnt(mdl)
	local ent = hatEnts[mdl]
	if not IsValid(ent) then
		ent = ClientsideModel(mdl, RENDERGROUP_OPAQUE)
		if not IsValid(ent) then return end
		ent:SetNoDraw(true)
		hatEnts[mdl] = ent
	end
	return ent
end

-- Draws hat item `it` on the head of `ent` (a player or a preview model)
function SURF.DrawHat(ent, it)
	if not it or not it.model then return end
	local att = ent:LookupAttachment("eyes")
	if not att or att <= 0 then return end
	local a = ent:GetAttachment(att)
	if not a then return end
	local hat = HatEnt(it.model)
	if not hat then return end
	local pos, ang = a.Pos, a.Ang
	pos = pos + ang:Forward() * (it.fwd or 0) + ang:Up() * (it.up or 0) + ang:Right() * (it.right or 0)
	ang:RotateAroundAxis(ang:Right(), it.pitch or 0)
	ang:RotateAroundAxis(ang:Up(), it.yaw or 0)
	ang:RotateAroundAxis(ang:Forward(), it.roll or 0)
	local m = Matrix()
	m:Scale(Vector(1, 1, 1) * (it.scale or 1))
	hat:EnableMatrix("RenderMultiply", m)
	hat:SetRenderOrigin(pos)
	hat:SetRenderAngles(ang)
	hat:SetupBones()
	local c = it.color
	if c then render.SetColorModulation(c.r / 255, c.g / 255, c.b / 255) end
	hat:DrawModel()
	if c then render.SetColorModulation(1, 1, 1) end
	hat:SetRenderOrigin()
	hat:SetRenderAngles()
end

hook.Add("PostPlayerDraw", "surf_hats", function(ply)
	if not ply:Alive() then return end
	local id = ply:GetNW2String("surf_hat", "")
	if id == "" then return end
	if ply == LocalPlayer() and not ply:ShouldDrawLocalPlayer() then return end
	SURF.DrawHat(ply, SURF.ItemByKey["hat:" .. id])
end)

-- Small drawing helpers -----------------------------------------------------

local trailMats = {}
local function TrailMat(it)
	local m = trailMats[it.mat]
	if not m then m = Material(it.mat) trailMats[it.mat] = m end
	return m
end

-- A trail swooshing across a box
local function DrawTrail(it, x, y, w, h, speed)
	if not it.mat then return end
	surface.SetMaterial(TrailMat(it))
	local c = it.color or color_white
	local n, t = 24, CurTime() * (speed or 3)
	local px, py
	for i = 0, n do
		local f = i / n
		local cx = x + w * 0.08 + w * 0.84 * f
		local cy = y + h / 2 + math.sin(t + f * 5) * h * 0.22
		if px then
			local dx, dy = cx - px, cy - py
			local len = math.sqrt(dx * dx + dy * dy) + 2
			surface.SetDrawColor(c.r, c.g, c.b, 40 + 215 * f)
			surface.DrawTexturedRectRotated((cx + px) / 2, (cy + py) / 2, len, 4 + h * 0.18 * f, -math.deg(math.atan2(dy, dx)))
		end
		px, py = cx, cy
	end
end

-- A name in an item's color, letter by letter when it is rainbow
local function DrawName(it, text, font, x, y, alignCenter)
	surface.SetFont(font)
	local w = surface.GetTextSize(text)
	if alignCenter then x = x - w / 2 end
	if not it.rainbow then
		draw.SimpleText(text, font, x, y, it.color or color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		return
	end
	local i = 0
	for _, code in utf8.codes(text) do
		local ch = utf8.char(code)
		draw.SimpleText(ch, font, x, y, SURF.ItemColor(it, i * 25), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		x = x + surface.GetTextSize(ch)
		i = i + 1
	end
end

-- A chat line: [tag] [Title] Name: gg
local function DrawChatLine(x, y, tag, nameIt)
	local ply = LocalPlayer()
	local title = SURF.Config.Titles[ply:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
	local parts = {}
	if tag then parts[#parts + 1] = { "[" .. tag.name .. "] ", tag.color } end
	parts[#parts + 1] = { "[" .. title.name .. "] ", title.color or DIM }
	surface.SetFont("SurfMedium")
	for _, p in ipairs(parts) do
		draw.SimpleText(p[1], "SurfMedium", x, y, p[2], TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		x = x + surface.GetTextSize(p[1])
	end
	local name = ply:Nick()
	if nameIt then DrawName(nameIt, name, "SurfMedium", x, y)
	else draw.SimpleText(name, "SurfMedium", x, y, Color(160, 210, 255), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER) end
	surface.SetFont("SurfMedium")
	x = x + surface.GetTextSize(name)
	draw.SimpleText(": gg, nice run", "SurfMedium", x, y, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
end

-- Item state ----------------------------------------------------------------

local function State(it, data, owned)
	local on = (data.equipped or {})[it.cat] == it.id
	local free = SURF.ItemFree(it)
	local have = free or owned[it.key] or (it.vip and data.vip)
	return on, have, free
end

local function PriceText(it, data, owned)
	local on, have, free = State(it, data, owned)
	if on then return "ON", Acc() end
	if have then return free and "Free" or (owned[it.key] and "Owned" or "VIP"), DIM end
	if it.price then return string.Comma(it.price), (data.coins or 0) >= it.price and GOLD or MUTED end
	return "VIP only", GOLD
end

local function Visible(it, owned)
	return it.id ~= "none" and (not it.hidden or owned[it.key])
end

-- Menu ----------------------------------------------------------------------

local function Button(parent, text, col, click)
	local b = vgui.Create("DButton", parent)
	b:SetText("")
	b.label = text
	b.Paint = function(self, w, h)
		local c = isfunction(col) and col() or col
		local t = isfunction(self.label) and self.label() or self.label
		draw.RoundedBox(6, 0, 0, w, h, self:IsHovered() and Color(c.r, c.g, c.b, 255) or Color(c.r, c.g, c.b, 210))
		draw.SimpleText(t, "SurfMedium", w / 2, h / 2, Color(10, 12, 18), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end
	b.DoClick = click
	return b
end

local BuildBody

local function Sidebar(f, data, owned)
	local side = vgui.Create("DPanel", f)
	side:Dock(LEFT)
	side:SetWide(170)
	side:DockMargin(0, 0, 10, 0)
	side.Paint = nil
	local tabs = {}
	for _, c in ipairs(SURF.ShopCategories) do tabs[#tabs + 1] = { id = c.id, name = c.name, list = c.list } end
	tabs[#tabs + 1] = { id = "vip", name = "VIP" }
	for _, t in ipairs(tabs) do
		local have, total = 0, 0
		for _, it in ipairs(t.list or {}) do
			if Visible(it, owned) then
				total = total + 1
				local _, h = State(it, data, owned)
				if h then have = have + 1 end
			end
		end
		local b = vgui.Create("DButton", side)
		b:Dock(TOP)
		b:DockMargin(0, 0, 0, 6)
		b:SetTall(44)
		b:SetText("")
		b.Paint = function(self, w, h)
			local cur = f.tab == t.id
			draw.RoundedBox(6, 0, 0, w, h, cur and Acc(70) or (self:IsHovered() and HOVER or PANEL))
			if cur then draw.RoundedBox(2, 0, 8, 3, h - 16, Acc()) end
			draw.SimpleText(t.name, "SurfMedium", 14, t.list and 15 or h / 2, t.id == "vip" and GOLD or color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			if t.list then
				draw.SimpleText(have .. " / " .. total .. " yours", "SurfSmall", 14, 32, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			elseif data.vip then
				draw.SimpleText("active", "SurfSmall", w - 12, h / 2, GOLD, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
			end
		end
		b.DoClick = function()
			if f.tab == t.id then return end
			f.tab, f.sel = t.id, nil
			surface.PlaySound("ui/buttonclick.wav")
			BuildBody(f)
		end
	end
	local how = vgui.Create("DLabel", side)
	how:Dock(BOTTOM)
	how:SetTall(84)
	how:SetWrap(true)
	how:SetContentAlignment(1)
	how:SetFont("SurfSmall")
	how:SetTextColor(DIM)
	how:SetText("Earn coins by finishing maps, beating your best, daily visits and playing. Type !coins for the rates.")
	return side
end

-- Preview of the selected item, with its action button
local function Preview(parent, it, data, owned)
	local p = vgui.Create("DPanel", parent)
	p:Dock(RIGHT)
	p:SetWide(280)
	p:DockMargin(10, 0, 0, 0)
	p.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, PANEL) end
	if not it then
		local l = vgui.Create("DLabel", p)
		l:Dock(FILL)
		l:SetContentAlignment(5)
		l:SetFont("SurfMedium")
		l:SetTextColor(DIM)
		l:SetText("Pick an item to see it")
		return
	end
	local info = vgui.Create("DPanel", p)
	info:Dock(BOTTOM)
	info:SetTall(132)
	info:DockPadding(14, 0, 14, 14)
	local on, have, free = State(it, data, owned)
	info.Paint = function(_, w)
		draw.SimpleText(it.cat == "tag" and ("[" .. it.name .. "]") or it.name, "SurfLarge", 14, 18, it.cat == "tag" and it.color or color_white)
		local sub
		if on then sub = "You have it on."
		elseif have then sub = free and "Free for everyone." or (owned[it.key] and "Yours." or "Free with your VIP.")
		elseif it.price then sub = string.Comma(it.price) .. " coins" .. (it.vip and ", or free with VIP" or "")
		else sub = "Only for VIPs." end
		draw.SimpleText(sub, "SurfMedium", 14, 52, (it.price and not have) and GOLD or DIM)
		if it.cat == "hat" or it.cat == "skin" then
			draw.SimpleText("Drag to turn it around", "SurfSmall", w - 14, 22, MUTED, TEXT_ALIGN_RIGHT)
		end
	end
	local act
	if on then
		act = Button(info, "Take it off", DIM, function()
			net.Start("surf.ShopEquip") net.WriteString(it.cat) net.WriteString("none") net.SendToServer()
		end)
	elseif have then
		act = Button(info, "Put it on", Acc(), function()
			net.Start("surf.ShopEquip") net.WriteString(it.cat) net.WriteString(it.id) net.SendToServer()
		end)
	elseif it.price then
		local armed = 0
		act = Button(info, function()
			if (data.coins or 0) < it.price then return "Need " .. string.Comma(it.price - (data.coins or 0)) .. " more coins" end
			return armed > CurTime() and "Click again to buy" or ("Buy for " .. string.Comma(it.price))
		end, function() return (data.coins or 0) >= it.price and GOLD or MUTED end, function()
			if (data.coins or 0) < it.price then return surface.PlaySound("buttons/button10.wav") end
			if armed > CurTime() then
				armed = 0
				net.Start("surf.ShopBuy") net.WriteString(it.key) net.SendToServer()
			else
				armed = CurTime() + 3
				surface.PlaySound("ui/buttonclick.wav")
			end
		end)
	else
		act = Button(info, "See VIP", GOLD, function() parent:GetParent().tab = "vip" BuildBody(parent:GetParent()) end)
	end
	act:Dock(BOTTOM)
	act:SetTall(42)

	local stage
	if it.cat == "skin" or it.cat == "hat" then
		stage = vgui.Create("DModelPanel", p)
		stage:SetModel(it.cat == "skin" and it.model or LocalPlayer():GetModel())
		local ent = stage:GetEntity()
		if IsValid(ent) then
			local seq = ent:LookupSequence("idle_all_01")
			if seq and seq > 0 then ent:ResetSequence(seq) end
		end
		if it.cat == "hat" then
			stage:SetFOV(32)
			stage:SetCamPos(Vector(70, 0, 66))
			stage:SetLookAt(Vector(0, 0, 63))
			stage.PostDrawModel = function(_, e) SURF.DrawHat(e, it) end
		else
			stage:SetFOV(38)
			stage:SetCamPos(Vector(110, 0, 48))
			stage:SetLookAt(Vector(0, 0, 36))
		end
		stage.yaw = 25
		stage.LayoutEntity = function(self, e)
			if self:IsDown() then
				local x = gui.MouseX()
				self.yaw = self.yaw + (x - (self.lastX or x)) * 0.6
				self.lastX = x
			else
				self.lastX = nil
				self.yaw = self.yaw + FrameTime() * 20
			end
			e:SetAngles(Angle(0, self.yaw, 0))
			self:RunAnimation()
		end
		stage.IsDown = function(self) return self.Depressed or input.IsMouseDown(MOUSE_LEFT) and self:IsHovered() end
	else
		stage = vgui.Create("DPanel", p)
		stage.Paint = function(_, w, h)
			draw.RoundedBox(8, 8, 8, w - 16, h - 16, Color(0, 0, 0, 90))
			if it.cat == "trail" then
				DrawTrail(it, 8, 8, w - 16, h - 16)
			elseif it.cat == "tag" then
				draw.SimpleText("In chat", "SurfSmall", 20, 26, DIM)
				DrawChatLine(20, h / 2, it, SURF.NameColorOf(LocalPlayer()))
			elseif it.cat == "color" then
				DrawName(it, LocalPlayer():Nick(), "SurfLarge", w / 2, h / 2 - 12, true)
				DrawChatLine(20, h / 2 + 30, SURF.ChatTagOf(LocalPlayer()), it)
			elseif it.cat == "sound" then
				draw.SimpleText("Plays where you are", "SurfSmall", w / 2, h / 2 - 40, DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
				draw.SimpleText("when you finish a run", "SurfSmall", w / 2, h / 2 - 22, DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			end
		end
		if it.cat == "sound" then
			local play = Button(stage, "Play", Acc(), function() surface.PlaySound(it.sound) end)
			play:SetSize(110, 38)
			stage.PerformLayout = function(self, w, h) play:SetPos(w / 2 - 55, h / 2 + 4) end
		end
	end
	stage:Dock(FILL)
end

local function Tile(grid, it, data, owned, f)
	local t = grid:Add("DButton")
	t:SetSize(128, 116)
	t:SetText("")
	local on = State(it, data, owned)
	if it.cat == "skin" or it.cat == "hat" then
		local icon = vgui.Create("SpawnIcon", t)
		icon:SetSize(64, 64)
		icon:SetPos(32, 8)
		icon:SetModel(it.model)
		icon:SetMouseInputEnabled(false)
		icon:SetTooltip(false)
	end
	t.Paint = function(self, w, h)
		local sel = f.sel == it.key
		draw.RoundedBox(8, 0, 0, w, h, sel and Acc(60) or (self:IsHovered() and HOVER or PANEL))
		if sel or on then
			surface.SetDrawColor(on and Acc() or Acc(150))
			surface.DrawOutlinedRect(0, 0, w, h, 2)
		end
		if it.cat == "trail" then
			DrawTrail(it, 6, 10, w - 12, 60, self:IsHovered() and 6 or 2)
		elseif it.cat == "tag" then
			draw.SimpleText("[" .. it.name .. "]", "SurfMedium", w / 2, 40, it.color, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		elseif it.cat == "color" then
			DrawName(it, "Name", "SurfLarge", w / 2, 40, true)
		elseif it.cat == "sound" then
			local c = self:IsHovered() and Acc() or DIM
			surface.SetDrawColor(c.r, c.g, c.b, 255)
			draw.NoTexture()
			surface.DrawPoly({ { x = w / 2 - 9, y = 28 }, { x = w / 2 + 13, y = 40 }, { x = w / 2 - 9, y = 52 } })
		end
		if it.cat ~= "tag" then
			draw.SimpleText(it.name, "SurfSmall", w / 2, 82, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		local txt, col = PriceText(it, data, owned)
		draw.SimpleText(txt, "SurfSmall", w / 2, 100, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		if it.hidden then draw.SimpleText("retired", "SurfSmall", w - 6, 4, MUTED, TEXT_ALIGN_RIGHT) end
	end
	t.DoClick = function()
		f.sel = it.key
		if it.cat == "sound" then surface.PlaySound(it.sound) end
		BuildBody(f)
	end
	t.DoDoubleClick = function()
		local _, have = State(it, data, owned)
		if have then
			net.Start("surf.ShopEquip") net.WriteString(it.cat) net.WriteString(on and "none" or it.id) net.SendToServer()
		end
	end
end

local function VIPBody(body, data)
	local wrap = vgui.Create("DPanel", body)
	wrap:Dock(FILL)
	wrap:DockPadding(18, 16, 18, 16)
	local exp = data.expires
	local permanent = data.vip and not (exp and exp > 0)
	local bonus = math.floor(((data.rates or SURF.Config.Coins).VIPBonus or 0.5) * 100)
	wrap.Paint = function(_, w, h)
		draw.RoundedBox(8, 0, 0, w, h, PANEL)
		draw.SimpleText("VIP", "SurfTimer", 18, 34, GOLD, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local status
		if permanent then status = "You have VIP for good. Thank you!"
		elseif data.vip then status = "You are a VIP until " .. os.date("%Y-%m-%d", exp) .. ". Buying more adds days."
		else status = "Purely cosmetic: it never changes your times." end
		draw.SimpleText(status, "SurfMedium", 100, 34, data.vip and GOLD or DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local perks = {
			"Every VIP trail, hat, skin, chat tag and name color",
			"A gold [VIP] tag in chat and a gold name on the scoreboard",
			bonus .. "% more coins from everything you do",
			"Keeps the server online for everyone",
		}
		for i, line in ipairs(perks) do
			draw.RoundedBox(4, 24, 66 + i * 26, 8, 8, GOLD)
			draw.SimpleText(line, "SurfMedium", 46, 70 + i * 26, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		draw.SimpleText("Buy VIP with coins", "SurfLarge", 18, 226, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	local row = vgui.Create("DPanel", wrap)
	row:Dock(TOP)
	row:DockMargin(0, 228, 0, 0)
	row:SetTall(96)
	row.Paint = nil
	local packs = data.vipPackages or SURF.Config.VIPPackages or {}
	for _, pack in ipairs(packs) do
		local armed = 0
		local b = vgui.Create("DButton", row)
		b:Dock(LEFT)
		b:SetWide(180)
		b:DockMargin(0, 0, 12, 0)
		b:SetText("")
		local can = (data.coins or 0) >= pack.price and not permanent
		b.Paint = function(self, w, h)
			draw.RoundedBox(8, 0, 0, w, h, (self:IsHovered() and can) and Color(255, 200, 40, 50) or Color(255, 200, 40, 22))
			surface.SetDrawColor(255, 200, 40, can and 200 or 60)
			surface.DrawOutlinedRect(0, 0, w, h, 2)
			draw.SimpleText(pack.days .. " days", "SurfLarge", w / 2, 26, color_white, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			draw.SimpleText(string.Comma(pack.price) .. " coins", "SurfMedium", w / 2, 52, can and GOLD or MUTED, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			local sub = permanent and "You have VIP" or (not can and ("Need " .. string.Comma(pack.price - (data.coins or 0)) .. " more"))
				or (armed > CurTime() and "Click again to buy" or "Click to buy")
			draw.SimpleText(sub, "SurfSmall", w / 2, 76, armed > CurTime() and GOLD or DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		b.DoClick = function()
			if not can then return surface.PlaySound("buttons/button10.wav") end
			if armed > CurTime() then
				armed = 0
				net.Start("surf.ShopBuyVIP") net.WriteUInt(pack.days, 16) net.SendToServer()
			else
				armed = CurTime() + 3
				surface.PlaySound("ui/buttonclick.wav")
			end
		end
	end
	if #packs == 0 then
		local l = vgui.Create("DLabel", row)
		l:Dock(FILL)
		l:SetFont("SurfMedium")
		l:SetTextColor(DIM)
		l:SetText("VIP isn't sold for coins right now.")
	end
	if data.url and data.url ~= "" then
		local store = Button(wrap, "Get VIP in the store (supports the server)", GOLD, function() gui.OpenURL(data.url) end)
		store:Dock(BOTTOM)
		store:SetTall(42)
	end
end

BuildBody = function(f)
	local data = f.data
	if IsValid(f.body) then f.body:Remove() end
	local body = vgui.Create("DPanel", f)
	body:Dock(FILL)
	body.Paint = nil
	f.body = body
	if f.tab == "vip" then return VIPBody(body, data) end
	local owned = f.owned
	local cat
	for _, c in ipairs(SURF.ShopCategories) do if c.id == f.tab then cat = c end end
	if not cat then return end
	local items = {}
	for _, it in ipairs(cat.list) do if Visible(it, owned) then items[#items + 1] = it end end
	if not f.sel or not SURF.ItemByKey[f.sel] or SURF.ItemByKey[f.sel].cat ~= cat.id then
		-- start on what they wear, else the first item
		local eq = (data.equipped or {})[cat.id]
		f.sel = (eq and eq ~= "none" and SURF.ItemByKey[cat.id .. ":" .. eq]) and (cat.id .. ":" .. eq) or (items[1] and items[1].key)
	end
	Preview(body, SURF.ItemByKey[f.sel or ""], data, owned)
	local scroll = vgui.Create("DScrollPanel", body)
	scroll:Dock(FILL)
	local grid = vgui.Create("DIconLayout", scroll)
	grid:Dock(FILL)
	grid:SetSpaceX(8)
	grid:SetSpaceY(8)
	for _, it in ipairs(items) do Tile(grid, it, data, owned, f) end
end

function Menus.shop(data)
	if data.refresh and not IsValid(shopFrame) then return end
	if not IsValid(shopFrame) then
		local f = vgui.Create("DFrame")
		f:SetSize(math.min(ScrW() - 40, 1000), math.min(ScrH() - 40, 640))
		f:Center()
		f:SetTitle("")
		f:MakePopup()
		f:DockPadding(14, 52, 14, 14)
		f.Paint = function(self, pw, ph)
			draw.RoundedBox(10, 0, 0, pw, ph, Color(10, 12, 18, 245))
			draw.RoundedBoxEx(10, 0, 0, pw, 40, Color(255, 255, 255, 6), true, true, false, false)
			draw.SimpleText("SHOP", "SurfLarge", 16, 20, Acc(), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText("Cosmetics only. Nothing here changes how you surf.", "SurfSmall", 86, 21, MUTED, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			local d = self.data or {}
			surface.SetFont("SurfLarge")
			local coins = string.Comma(d.coins or 0)
			draw.SimpleText(coins, "SurfLarge", pw - 44, 20, GOLD, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
			local cw = surface.GetTextSize(coins)
			draw.SimpleText("coins", "SurfSmall", pw - 50 - cw, 21, DIM, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
			if d.vip then
				draw.RoundedBox(4, pw - 150 - cw, 9, 44, 22, GOLD)
				draw.SimpleText("VIP", "SurfSmall", pw - 128 - cw, 20, Color(10, 12, 18), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			end
		end
		f.tab = data.tab or "trail"
		shopFrame = f
	elseif not data.refresh then
		shopFrame.tab = data.tab or shopFrame.tab
		shopFrame.sel = nil
	end
	local f = shopFrame
	f.data = data
	f.owned = {}
	for _, k in ipairs(data.owned or {}) do f.owned[k] = true end
	if IsValid(f.side) then f.side:Remove() end
	if IsValid(f.body) then f.body:Remove() end
	f.side = Sidebar(f, data, f.owned)
	BuildBody(f)
end

-- Old servers or other code may still open "vip" directly
function Menus.vip(data)
	data.tab = "vip"
	data.coins = data.coins or LocalPlayer():GetNW2Int("surf_coins", 0)
	Menus.shop(data)
end
