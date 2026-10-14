-- The shop menu (!shop, F3, !vip), hats on players, and admin price changes.
-- Left: categories and VIP. Middle: the items. Right: your look in 3D with
-- everything you have on and the selected item tried on, and its Buy / Equip
-- button.
-- Built with the shared theme in cl_ui.lua.
local Menus = SURF.Menus
local UI = SURF.UI
local C, S = UI.Col, UI.S
local GOLD, DIM, MUTED, PANEL = C.gold, C.dim, C.faint, C.card
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
	surface.SetFont("SurfUI_Body")
	for _, p in ipairs(parts) do
		draw.SimpleText(p[1], "SurfUI_Body", x, y, p[2], TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		x = x + surface.GetTextSize(p[1])
	end
	local name = ply:Nick()
	if nameIt then DrawName(nameIt, name, "SurfUI_Body", x, y)
	else draw.SimpleText(name, "SurfUI_Body", x, y, Color(160, 210, 255), TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER) end
	surface.SetFont("SurfUI_Body")
	x = x + surface.GetTextSize(name)
	draw.SimpleText(": gg wp", "SurfUI_Body", x, y, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
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

local BuildBody, ShowPreview

-- How many items of each category you have, for the sidebar
local function Counts(data, owned)
	local out = {}
	for _, c in ipairs(SURF.ShopCategories) do
		local have, total = 0, 0
		for _, it in ipairs(c.list) do
			if Visible(it, owned) then
				total = total + 1
				local _, h = State(it, data, owned)
				if h then have = have + 1 end
			end
		end
		out[c.id] = { have = have, total = total }
	end
	return out
end

-- Categories down the left, with how many items of each you have. It reads
-- f.data and f.counts while painting, so a refresh doesn't rebuild it.
local function Sidebar(f)
	local side = vgui.Create("DPanel", f)
	side:Dock(LEFT)
	side:SetWide(S(190))
	side:DockMargin(0, 0, S(14), 0)
	side:DockPadding(S(6), S(6), S(6), S(6))
	side.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, C.panel) end
	local tabs = {}
	for _, c in ipairs(SURF.ShopCategories) do tabs[#tabs + 1] = { id = c.id, name = c.name, list = c.list } end
	tabs[#tabs + 1] = { id = "vip", name = "VIP" }
	for _, t in ipairs(tabs) do
		local b = vgui.Create("DButton", side)
		b:Dock(TOP)
		b:DockMargin(0, 0, 0, S(2))
		b:SetTall(S(46))
		b:SetText("")
		b.Paint = function(self, w, h)
			local cur = f.tab == t.id
			local hv = UI.Hover(self, self:IsHovered())
			local acc = UI.Accent()
			if cur then
				draw.RoundedBox(6, 0, 0, w, h, UI.Alpha(acc, 45))
				draw.RoundedBox(2, 0, S(9), S(3), h - S(18), acc)
			elseif hv > 0.01 then
				draw.RoundedBox(6, 0, 0, w, h, Color(255, 255, 255, 12 * hv))
			end
			local tcol = t.id == "vip" and GOLD or ((cur or hv > 0.5) and C.text or DIM)
			if t.list then
				local n = (f.counts or {})[t.id] or { have = 0, total = 0 }
				draw.SimpleText(t.name, "SurfUI_Body", S(14), h / 2 - S(8), tcol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				draw.SimpleText(n.have .. " / " .. n.total .. " yours", "SurfUI_Small", S(14), h / 2 + S(10), MUTED, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			else
				draw.SimpleText(t.name, "SurfUI_Body", S(14), h / 2, tcol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				if (f.data or {}).vip then draw.SimpleText("active", "SurfUI_Small", w - S(12), h / 2, GOLD, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER) end
			end
		end
		b.DoClick = function()
			if f.tab == t.id then return end
			UI.Click()
			f.tab, f.sel = t.id, nil
			f.lookZoom = t.id == "hat" and 1 or 0
			BuildBody(f)
		end
	end
	local how = vgui.Create("DLabel", side)
	how:Dock(BOTTOM)
	how:DockMargin(S(8), 0, S(8), S(6))
	how:SetTall(S(90))
	how:SetWrap(true)
	how:SetContentAlignment(1)
	how:SetFont("SurfUI_Small")
	how:SetTextColor(MUTED)
	how:SetText("Earn coins by finishing maps, beating your best, daily visits and playing. Type !coins for the rates.")
	return side
end

local function Equip(cat, id)
	net.Start("surf.ShopEquip") net.WriteString(cat) net.WriteString(id) net.SendToServer()
end

-- What the preview player wears: everything you have on, with the selected
-- item tried on in its slot
local LOOK_SLOTS = { "skin", "hat", "trail", "tag", "color" }
local FALLBACK_MODEL = "models/player/group01/male_07.mdl"

local function Look(f, it)
	local data, owned = f.data or {}, f.owned or {}
	local eq = data.equipped or {}
	local look = {}
	for _, cat in ipairs(LOOK_SLOTS) do
		if it and it.cat == cat then
			look[cat] = it
		else
			local id = eq[cat]
			local cur = id and id ~= "none" and SURF.ItemByKey[cat .. ":" .. id]
			if cur and select(2, State(cur, data, owned)) then look[cat] = cur end
		end
	end
	local mdl = LocalPlayer():GetModel()
	if not mdl or mdl == "" or mdl == "models/player.mdl" then mdl = FALLBACK_MODEL end
	look.model = look.skin and look.skin.model or mdl
	look.trying = it ~= nil and not State(it, data, owned)
	return look
end

-- The trail behind the preview player, like util.SpriteTrail draws it in game
-- (16 wide at the feet, thinning out)
local function DrawTrail3D(ent, it)
	if not it or not it.mat then return end
	local pos, fwd, right = ent:GetPos(), ent:GetForward(), ent:GetRight()
	local c = it.color or color_white
	local n, t = 16, RealTime()
	render.SetMaterial(TrailMat(it))
	render.StartBeam(n + 1)
	for i = 0, n do
		local k = i / n
		local p = pos - fwd * (6 + 40 * k) + right * (math.sin(t * 2 - k * 3) * 6 * k)
		p.z = p.z + 5 + math.sin(t * 3 - k * 4) * 3 * k
		render.AddBeam(p, 16 * (1 - k) + 0.5, k, Color(c.r, c.g, c.b, 255 * (1 - k * 0.8)))
	end
	render.EndBeam()
end

-- [Tag] Name over the preview player, in the name color
local function DrawNameplate(look, w, y)
	local name = LocalPlayer():Nick()
	local tagText = look.tag and ("[" .. look.tag.name .. "] ") or ""
	local font = "SurfUI_Head"
	if UI.TextWidth(tagText .. name, font) > w - S(24) then font = "SurfUI_Body" end
	local tw = tagText ~= "" and UI.TextWidth(tagText, font) or 0
	local x = w / 2 - (tw + UI.TextWidth(name, font)) / 2
	if look.tag then draw.SimpleText(tagText, font, x, y, look.tag.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER) end
	if look.color then DrawName(look.color, name, font, x + tw, y)
	else draw.SimpleText(name, font, x + tw, y, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER) end
end

-- The player in everything they have on, turning slowly; drag to turn it,
-- scroll to zoom between the whole body and the head
local function LookStage(parent, f, it, look)
	local stage = vgui.Create("DModelPanel", parent)
	stage.look = look
	stage:SetModel(look.model)
	local ent = stage:GetEntity()
	if IsValid(ent) then
		local seq = ent:LookupSequence("idle_all_01")
		if seq and seq > 0 then ent:ResetSequence(seq) end
		local me = LocalPlayer()
		local pc = me.GetPlayerColor and me:GetPlayerColor()
		if pc then ent.GetPlayerColor = function() return pc end end
	end
	f.lookYaw = f.lookYaw or 25
	f.lookZoom = f.lookZoom or 0
	stage.zoom = f.lookZoom
	local function Camera(self)
		local k = self.zoom
		self:SetFOV(Lerp(k, 40, 32))
		self:SetCamPos(Vector(Lerp(k, 120, 70), 0, Lerp(k, 44, 66)))
		self:SetLookAt(Vector(0, 0, Lerp(k, 36, 63)))
	end
	Camera(stage)
	stage.LayoutEntity = function(self, e)
		if self.Depressed then
			local x = gui.MouseX()
			f.lookYaw = f.lookYaw + (x - (self.lastX or x)) * 0.6
			self.lastX = x
		else
			self.lastX = nil
			f.lookYaw = f.lookYaw + FrameTime() * 20
		end
		self.zoom = Lerp(math.min(FrameTime() * 10, 1), self.zoom, f.lookZoom)
		Camera(self)
		e:SetAngles(Angle(0, f.lookYaw, 0))
		self:RunAnimation()
	end
	stage.OnMouseWheeled = function(_, delta)
		f.lookZoom = math.Clamp(f.lookZoom + delta * 0.25, 0, 1)
		return true
	end
	stage.PostDrawModel = function(_, e)
		DrawTrail3D(e, look.trail)
		SURF.DrawHat(e, look.hat)
	end
	local paint = stage.Paint
	stage.Paint = function(self, w, h)
		draw.RoundedBoxEx(8, 0, 0, w, h, Color(0, 0, 0, 70), true, true, false, false)
		paint(self, w, h)
		local label = look.trying and ("Trying on " .. it.name) or "Your look"
		draw.SimpleText(UI.Fit(label, "SurfUI_Small", w - S(24)), "SurfUI_Small", S(12), S(16), look.trying and GOLD or DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		DrawNameplate(look, w, S(44))
		if it and (it.cat == "tag" or it.cat == "color") then
			draw.RoundedBox(6, S(8), h - S(66), w - S(16), S(32), Color(0, 0, 0, 110))
			DrawChatLine(S(16), h - S(50), look.tag, look.color)
		end
		draw.SimpleText("Drag to turn, scroll to zoom", "SurfUI_Tiny", w / 2, h - S(14), MUTED, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end
	if it and it.cat == "sound" then
		local play = UI.Button(stage, "Play sound", "primary", function() surface.PlaySound(it.sound) end)
		play:SetSize(S(130), S(36))
		local layout = stage.PerformLayout
		stage.PerformLayout = function(self, w, h)
			if layout then layout(self, w, h) end
			play:SetPos(w / 2 - S(65), h - S(72))
		end
	end
	return stage
end

-- The right column: your look with the selected item on, its name and price,
-- and its Buy / Equip button. Rebuilt on its own when you pick an item, so
-- the item list keeps its scroll position.
ShowPreview = function(f)
	local p = f.look
	if not IsValid(p) then return end
	p:Clear()
	local data, owned = f.data, f.owned
	local it = SURF.ItemByKey[f.sel or ""]
	-- name, price and button along the bottom (docked before the stage)
	if it then
		local info = vgui.Create("DPanel", p)
		info:Dock(BOTTOM)
		info:SetTall(S(132))
		info:DockPadding(S(14), 0, S(14), S(14))
		local on, have, free = State(it, data, owned)
		info.Paint = function(_, w)
			surface.SetDrawColor(C.line)
			surface.DrawRect(S(14), 0, w - S(28), 1)
			local name = it.cat == "tag" and ("[" .. it.name .. "]") or it.name
			draw.SimpleText(UI.Fit(name, "SurfUI_Title", w - S(28)), "SurfUI_Title", S(14), S(26), it.cat == "tag" and it.color or C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			local sub
			if on then sub = "You have it on."
			elseif have then sub = free and "Free for everyone." or (owned[it.key] and "Yours." or "Free with your VIP.")
			elseif it.price then sub = string.Comma(it.price) .. " coins" .. (it.vip and ", or free with VIP" or "")
			else sub = "Only for VIPs." end
			draw.SimpleText(sub, "SurfUI_Body", S(14), S(56), (it.price and not have) and GOLD or DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		local act
		if on then
			act = UI.Button(info, "Take it off", "ghost", function() Equip(it.cat, "none") end)
		elseif have then
			act = UI.Button(info, "Put it on", "primary", function() Equip(it.cat, it.id) end)
		elseif it.price then
			local armed = 0
			local short = (data.coins or 0) < it.price
			act = UI.Button(info, function()
				if short then return "Need " .. string.Comma(it.price - (data.coins or 0)) .. " more coins" end
				return armed > CurTime() and "Click again to buy" or ("Buy for " .. string.Comma(it.price))
			end, "gold", function()
				if armed > CurTime() then
					armed = 0
					net.Start("surf.ShopBuy") net.WriteString(it.key) net.SendToServer()
				else
					armed = CurTime() + 3
				end
			end)
			if short then act:SetEnabled(false) end
		else
			act = UI.Button(info, "See VIP", "gold", function()
				f.tab, f.sel = "vip", nil
				BuildBody(f)
			end)
		end
		act:Dock(BOTTOM)
		act:SetTall(S(42))
	end
	f.stage = LookStage(p, f, it, Look(f, it))
	f.stage:Dock(FILL)
end

local function Tile(grid, it, f)
	local t = grid:Add("DButton")
	t:SetSize(S(128), S(118))
	t:SetText("")
	if it.cat == "skin" or it.cat == "hat" then
		local icon = vgui.Create("SpawnIcon", t)
		icon:SetSize(S(64), S(64))
		icon:SetPos(S(32), S(8))
		icon:SetModel(it.model)
		icon:SetMouseInputEnabled(false)
		icon:SetTooltip(false)
	end
	-- state comes from f.data each frame, so a buy or equip shows without a rebuild
	t.Paint = function(self, w, h)
		local on = State(it, f.data, f.owned)
		local sel = f.sel == it.key
		local hv = UI.Hover(self, self:IsHovered())
		local acc = UI.Accent()
		draw.RoundedBox(8, 0, 0, w, h, sel and UI.Alpha(acc, 50) or Color(255, 255, 255, 7 + 12 * hv))
		if sel or on then
			surface.SetDrawColor(UI.Alpha(acc, on and 255 or 150))
			surface.DrawOutlinedRect(0, 0, w, h, 2)
		end
		if it.cat == "trail" then
			DrawTrail(it, S(6), S(10), w - S(12), S(60), self:IsHovered() and 6 or 2)
		elseif it.cat == "tag" then
			draw.SimpleText(UI.Fit("[" .. it.name .. "]", "SurfUI_Body", w - S(8)), "SurfUI_Body", w / 2, S(40), it.color, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		elseif it.cat == "color" then
			DrawName(it, "Name", "SurfUI_Head", w / 2, S(40), true)
		elseif it.cat == "sound" then
			local c = self:IsHovered() and acc or DIM
			surface.SetDrawColor(c.r, c.g, c.b, 255)
			draw.NoTexture()
			surface.DrawPoly({ { x = w / 2 - S(9), y = S(28) }, { x = w / 2 + S(13), y = S(40) }, { x = w / 2 - S(9), y = S(52) } })
		end
		if it.cat ~= "tag" then
			draw.SimpleText(UI.Fit(it.name, "SurfUI_Small", w - S(8)), "SurfUI_Small", w / 2, S(84), C.text, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		local txt, col = PriceText(it, f.data, f.owned)
		draw.SimpleText(txt, "SurfUI_Small", w / 2, S(102), col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		if it.hidden then draw.SimpleText("retired", "SurfUI_Tiny", w - S(6), S(4), MUTED, TEXT_ALIGN_RIGHT) end
	end
	t.DoClick = function()
		if it.cat == "sound" then surface.PlaySound(it.sound) end
		if f.sel == it.key then return end
		UI.Click()
		f.sel = it.key
		ShowPreview(f)
	end
	t.DoDoubleClick = function()
		local on, have = State(it, f.data, f.owned)
		if have then Equip(it.cat, on and "none" or it.id) end
	end
end

local function VIPBody(body, data)
	local wrap = vgui.Create("DPanel", body)
	wrap:Dock(FILL)
	wrap:DockPadding(S(20), S(18), S(20), S(18))
	local exp = data.expires
	local permanent = data.vip and not (exp and exp > 0)
	local bonus = math.floor(((data.rates or SURF.Config.Coins).VIPBonus or 0.5) * 100)
	local perks = {
		"Every VIP trail, hat, skin, chat tag and name color",
		"A gold [VIP] tag in chat and a gold name on the scoreboard",
		bonus .. "% more coins from everything you do",
		"Keeps the server online for everyone",
	}
	wrap.Paint = function(_, w, h)
		draw.RoundedBox(8, 0, 0, w, h, C.panel)
		draw.SimpleText("VIP", "SurfUI_Big", S(20), S(36), GOLD, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local status
		if permanent then status = "You have VIP for good. Thank you!"
		elseif data.vip then status = "You are a VIP until " .. os.date("%Y-%m-%d", exp) .. ". Buying more adds days."
		else status = "Purely cosmetic: it never changes your times." end
		local x = S(32) + UI.TextWidth("VIP", "SurfUI_Big")
		draw.SimpleText(UI.Fit(status, "SurfUI_Body", w - x - S(20)), "SurfUI_Body", x, S(37), data.vip and GOLD or DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		for i, line in ipairs(perks) do
			local y = S(58) + i * S(28)
			draw.RoundedBox(4, S(24), y - S(4), S(8), S(8), GOLD)
			draw.SimpleText(line, "SurfUI_Body", S(44), y, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		draw.SimpleText("Buy VIP with coins", "SurfUI_Head", S(20), S(232), C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
	end
	local row = vgui.Create("DPanel", wrap)
	row:Dock(TOP)
	row:DockMargin(0, S(236), 0, 0)
	row:SetTall(S(96))
	row.Paint = nil
	local packs = data.vipPackages or SURF.Config.VIPPackages or {}
	for _, pack in ipairs(packs) do
		local armed = 0
		local b = vgui.Create("DButton", row)
		b:Dock(LEFT)
		b:SetWide(S(190))
		b:DockMargin(0, 0, S(12), 0)
		b:SetText("")
		local can = (data.coins or 0) >= pack.price and not permanent
		b.Paint = function(self, w, h)
			local hv = UI.Hover(self, self:IsHovered() and can)
			draw.RoundedBox(8, 0, 0, w, h, UI.Alpha(GOLD, 20 + 30 * hv))
			surface.SetDrawColor(UI.Alpha(GOLD, can and 200 or 60))
			surface.DrawOutlinedRect(0, 0, w, h, 2)
			draw.SimpleText(pack.days .. " days", "SurfUI_Title", w / 2, S(26), C.text, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			draw.SimpleText(string.Comma(pack.price) .. " coins", "SurfUI_Body", w / 2, S(52), can and GOLD or MUTED, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
			local sub = permanent and "You have VIP" or (not can and ("Need " .. string.Comma(pack.price - (data.coins or 0)) .. " more"))
				or (armed > CurTime() and "Click again to buy" or "Click to buy")
			draw.SimpleText(sub, "SurfUI_Small", w / 2, S(76), armed > CurTime() and GOLD or DIM, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		end
		b.DoClick = function()
			if not can then return surface.PlaySound("buttons/button10.wav") end
			UI.Click()
			if armed > CurTime() then
				armed = 0
				net.Start("surf.ShopBuyVIP") net.WriteUInt(pack.days, 16) net.SendToServer()
			else
				armed = CurTime() + 3
			end
		end
	end
	if #packs == 0 then
		UI.Label(row, "VIP isn't sold for coins right now.", "SurfUI_Body", DIM):Dock(FILL)
	end
	if data.url and data.url ~= "" then
		local store = UI.Button(wrap, "Get VIP in the store (supports the server)", "gold", function() gui.OpenURL(data.url) end)
		store:Dock(BOTTOM)
		store:SetTall(S(42))
	end
end

-- Rebuilds everything right of the sidebar: on opening, and on a new tab
BuildBody = function(f)
	local data = f.data
	if IsValid(f.body) then f.body:Remove() end
	f.look, f.grid, f.stage = nil, nil, nil
	local body = vgui.Create("DPanel", f)
	body:Dock(FILL)
	body.Paint = nil
	f.body, f.bodyTab = body, f.tab
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
	-- the preview column first, so the item list fills what is left
	local look = vgui.Create("DPanel", body)
	look:Dock(RIGHT)
	look:SetWide(S(290))
	look:DockMargin(S(14), 0, 0, 0)
	look.Paint = function(_, w, h) draw.RoundedBox(8, 0, 0, w, h, C.panel) end
	f.look = look
	ShowPreview(f)
	local scroll = UI.Scroll(body)
	local grid = vgui.Create("DIconLayout", scroll)
	grid:Dock(FILL)
	grid:SetSpaceX(S(8))
	grid:SetSpaceY(S(8))
	for _, it in ipairs(items) do Tile(grid, it, f) end
	f.grid = grid
end

function Menus.shop(data)
	if data.refresh and not IsValid(shopFrame) then return end
	if not IsValid(shopFrame) then
		shopFrame = UI.Frame("Shop", 1040, 660, {
			id = "shop",
			sub = "Cosmetics only. Nothing here changes how you surf.",
			right = function(self)
				local d = self.data or {}
				return string.Comma(d.coins or 0) .. " coins" .. (d.vip and "  ·  VIP" or ""), GOLD
			end,
		})
		shopFrame.tab = data.tab or "trail"
		shopFrame.lookZoom = shopFrame.tab == "hat" and 1 or 0
	elseif not data.refresh then
		local tab = data.tab or shopFrame.tab
		if tab ~= shopFrame.tab then shopFrame.lookZoom = tab == "hat" and 1 or 0 end
		shopFrame.tab = tab
		shopFrame.sel = nil
	end
	local f = shopFrame
	f.data = data
	f.owned = {}
	for _, k in ipairs(data.owned or {}) do f.owned[k] = true end
	f.counts = Counts(data, f.owned)
	if not IsValid(f.side) then f.side = Sidebar(f) end
	-- After buying or equipping, the server sends the new state. Keep the
	-- item list where it is scrolled to and only redraw the preview.
	if data.refresh and IsValid(f.grid) and IsValid(f.look) and f.bodyTab == f.tab then
		ShowPreview(f)
		return
	end
	BuildBody(f)
end

-- !vip and the main menu's VIP entry open the shop on its VIP tab
function Menus.vip(data)
	data.tab = "vip"
	data.coins = data.coins or LocalPlayer():GetNW2Int("surf_coins", 0)
	Menus.shop(data)
end
