-- Small Derma menus opened by the server (!wr, !help, !trail, !maps, !vip)
local Menus = {}

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
	l:AddLine("F1 / F2 / F3 / F4", "Help / Records / Trails / Spectate")
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

function Menus.trails()
	local f = Frame("Trails", 420, 480)
	local scroll = vgui.Create("DScrollPanel", f)
	scroll:Dock(FILL)
	scroll:DockMargin(0, 12, 0, 0)
	local isVIP = SURF.IsVIP(LocalPlayer())
	for _, t in ipairs(SURF.Config.Trails) do
		local b = scroll:Add("DButton")
		b:Dock(TOP)
		b:DockMargin(0, 0, 0, 6)
		b:SetTall(36)
		b:SetText("")
		local locked = t.vip and not isVIP
		b.Paint = function(self, w, h)
			local bg = self:IsHovered() and Color(255, 255, 255, 20) or Color(255, 255, 255, 8)
			draw.RoundedBox(6, 0, 0, w, h, bg)
			if t.color then draw.RoundedBox(4, 10, 10, 16, 16, t.color) end
			draw.SimpleText(t.name, "SurfMedium", 36, h / 2, locked and Color(140, 140, 140) or color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			if t.vip then
				draw.SimpleText(locked and "VIP (locked)" or "VIP", "SurfSmall", w - 12, h / 2, Color(255, 200, 40), TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
			end
		end
		b.DoClick = function()
			net.Start("surf.SetTrail")
			net.WriteString(t.id)
			net.SendToServer()
			f:Close()
		end
	end
end

function Menus.vip(data)
	local f = Frame("VIP", 460, 300)
	local txt = vgui.Create("DLabel", f)
	txt:Dock(FILL)
	txt:DockMargin(4, 12, 4, 4)
	txt:SetFont("SurfMedium")
	txt:SetWrap(true)
	txt:SetContentAlignment(7)
	local status
	if data.vip then
		status = "You are a VIP" .. ((data.expires and data.expires > 0) and (" until " .. os.date("%Y-%m-%d", data.expires)) or "") .. ". Thank you!"
	else
		status = "VIP is purely cosmetic and never affects your times."
	end
	txt:SetText(status .. "\n\nPerks: exclusive trails, a gold [VIP] chat tag and a gold name on the scoreboard.\n\nEvery purchase helps keep the server online.")
	if data.url and data.url ~= "" then
		local b = vgui.Create("DButton", f)
		b:Dock(BOTTOM)
		b:SetTall(36)
		b:SetText("Open the store")
		b.DoClick = function() gui.OpenURL(data.url) end
	end
end

net.Receive("surf.Menu", function()
	local kind = net.ReadString()
	local data = net.ReadTable()
	if Menus[kind] then Menus[kind](data) end
end)
