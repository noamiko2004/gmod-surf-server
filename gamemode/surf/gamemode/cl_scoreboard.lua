-- Scoreboard (hold Tab). Click or right-click a player for their Steam
-- profile, to watch them, to mute their voice just for you, and for admins
-- the admin actions (cl_admin.lua).
local UI = SURF.UI
local C = UI.Col
local S = UI.S
local board

local HEADER = 56

local function PB(p) return p:GetNW2Float("surf_mainpb", 0) end

local function SortedPlayers()
	local list = player.GetAll()
	table.sort(list, function(a, b)
		local ra, rb = a:GetNW2Bool("surf_replay", false), b:GetNW2Bool("surf_replay", false)
		if ra ~= rb then return ra end
		local pa, pb = PB(a), PB(b)
		if (pa > 0) ~= (pb > 0) then return pa > 0 end
		if pa ~= pb then return pa < pb end
		return a:Nick() < b:Nick()
	end)
	return list
end

local function PlayerMenu(p)
	if not IsValid(p) or p:IsBot() then return end
	local sid, name = p:SteamID64(), p:Nick()
	local m = UI.Menu()
	m:AddOption("Steam profile", function() if IsValid(p) then p:ShowProfile() end end):SetIcon("icon16/user.png")
	m:AddOption("Copy SteamID", function()
		SetClipboardText(sid)
		UI.Toast("Copied " .. sid)
	end):SetIcon("icon16/page_copy.png")
	if p ~= LocalPlayer() then
		if p:Alive() and p:Team() ~= TEAM_SPECTATOR then
			m:AddOption("Watch them", function() RunConsoleCommand("say", "!spec " .. sid) end):SetIcon("icon16/eye.png")
		end
		m:AddOption(p:IsMuted() and "Unmute their voice" or "Mute their voice (only for you)", function()
			if IsValid(p) then p:SetMuted(not p:IsMuted()) end
		end):SetIcon("icon16/sound_mute.png")
	end
	if SURF.AdminPanel then SURF.AdminPanel.AddOptions(m, sid, name) end
	UI.OpenMenu(m)
end

-- A small colored label; returns the x after it
local function Chip(text, col, x, h)
	local tw = UI.TextWidth(text, "SurfUI_Tiny") + S(12)
	draw.RoundedBox(4, x, h / 2 - S(10), tw, S(20), UI.Alpha(col, 40))
	draw.SimpleText(text, "SurfUI_Tiny", x + tw / 2, h / 2, col, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	return x + tw + S(6)
end

-- Column x positions inside a row (the header lines up with them)
local function Cols(w)
	return { rank = S(18), avatar = S(38), name = S(76), title = w - S(430), time = w - S(250), ping = w - S(16) }
end

local function Row(scroll, p, rank)
	local replay = p:GetNW2Bool("surf_replay", false)
	local row = scroll:Add("DButton")
	row:Dock(TOP)
	row:DockMargin(0, 0, 0, S(4))
	row:SetTall(S(40))
	row:SetText("")
	row:SetCursor(replay and "arrow" or "hand")
	row.DoClick = function() if not replay then PlayerMenu(p) end end
	row.DoRightClick = row.DoClick
	if not replay then
		local av = UI.Avatar(row, p, 28)
		av:SetPos(S(38), S(6))
		av:SetMouseInputEnabled(false)
	end
	row.Paint = function(s, w, h)
		if not IsValid(p) then return end
		local x = Cols(w)
		local hv = UI.Hover(s, s:IsHovered() and not replay)
		draw.RoundedBox(6, 0, 0, w, h, replay and UI.Alpha(C.gold, 22) or Color(255, 255, 255, 7 + 12 * hv))
		if p == LocalPlayer() then draw.RoundedBox(2, 0, S(8), S(3), h - S(16), UI.Accent()) end
		draw.SimpleText(rank and tostring(rank) or "-", "SurfUI_Body", x.rank, h / 2, C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		if replay then
			local nx = Chip("REPLAY", C.gold, x.avatar, h)
			draw.SimpleText(UI.Fit(p:GetNW2String("surf_replay_name", "?"), "SurfUI_Body", x.title - nx - S(10)), "SurfUI_Body", nx, h / 2, C.gold, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText("Server record", "SurfUI_Body", x.title, h / 2, C.gold, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		else
			local nx = x.name
			if p:IsSuperAdmin() then
				nx = Chip("OWNER", C.gold, nx, h)
			elseif p:IsAdmin() then
				nx = Chip("ADMIN", C.red, nx, h)
			end
			if SURF.IsVIP(p) and not p:IsAdmin() then nx = Chip("VIP", C.gold, nx, h) end
			local ct = SURF.ChatTagOf(p)
			if ct then nx = Chip(string.upper(ct.name), SURF.ItemColor(ct) or C.dim, nx, h) end
			local style = SURF.StyleOf(p)
			if style.id ~= "n" then nx = Chip(style.short, UI.Accent(), nx, h) end
			if p:Team() == TEAM_SPECTATOR then nx = Chip("SPEC", C.faint, nx, h) end
			if p ~= LocalPlayer() and p:IsMuted() then nx = Chip("MUTED", C.faint, nx, h) end
			local nc = SURF.NameColorOf(p)
			local nameCol = nc and SURF.ItemColor(nc) or (SURF.IsVIP(p) and Color(255, 220, 120) or C.text)
			draw.SimpleText(UI.Fit(p:Nick(), "SurfUI_Body", x.title - nx - S(10)), "SurfUI_Body", nx, h / 2, nameCol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			local title = SURF.Config.Titles[p:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
			draw.SimpleText(title.name, "SurfUI_Body", x.title, h / 2, title.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			draw.SimpleText(string.Comma(p:GetNW2Int("surf_points", 0)), "SurfUI_Small", x.title + UI.TextWidth(title.name, "SurfUI_Body") + S(8), h / 2 + 1, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		end
		local pb = PB(p)
		draw.SimpleText(pb > 0 and SURF.FormatTime(pb) or "-", "SurfUI_Body", x.time, h / 2, pb > 0 and C.text or C.faint, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local ping = replay and "BOT" or tostring(p:Ping())
		draw.SimpleText(ping, "SurfUI_Body", x.ping, h / 2, C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
	end
	return row
end

local function Build()
	local w, h = math.min(S(900), ScrW() - 40), math.min(S(700), ScrH() - 80)
	local frame = vgui.Create("DPanel")
	frame:SetSize(w, h)
	frame:Center()
	local pad = S(12)
	frame:DockPadding(pad, S(HEADER) + S(34), pad, S(30))
	frame.Paint = function(_, pw, ph)
		local hh = S(HEADER)
		draw.RoundedBox(8, 0, 0, pw, ph, C.bg)
		draw.RoundedBoxEx(8, 0, 0, pw, hh, C.header, true, true, false, false)
		surface.SetDrawColor(C.line)
		surface.DrawRect(0, hh - 1, pw, 1)
		draw.RoundedBox(2, S(16), hh / 2 - S(10), S(4), S(20), UI.Accent())
		local right = game.GetMap() .. "    " .. #player.GetHumans() .. " / " .. game.MaxPlayers() .. " players"
		draw.SimpleText(right, "SurfUI_Head", pw - S(18), hh / 2, C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		local room = pw - S(48) - UI.TextWidth(right, "SurfUI_Head") - S(30)
		draw.SimpleText(UI.Fit(GetHostName(), "SurfUI_Title", room), "SurfUI_Title", S(30), hh / 2, C.text, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		local x = Cols(pw - pad * 2 - S(12))
		local y = hh + S(18)
		draw.SimpleText("#", "SurfUI_Tiny", pad + x.rank, y, C.dim, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
		draw.SimpleText("PLAYER", "SurfUI_Tiny", pad + x.name, y, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText("TITLE", "SurfUI_Tiny", pad + x.title, y, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText("BEST TIME", "SurfUI_Tiny", pad + x.time, y, C.dim, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText("PING", "SurfUI_Tiny", pad + x.ping, y, C.dim, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		draw.SimpleText("Click a player for their profile and more", "SurfUI_Small", pw / 2, ph - S(15), C.faint, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
	end

	local scroll = UI.Scroll(frame)
	frame.Refresh = function(self)
		scroll:Clear()
		self.count = #player.GetAll()
		local rank = 0
		for _, p in ipairs(SortedPlayers()) do
			local replay = p:GetNW2Bool("surf_replay", false)
			local ranked = PB(p) > 0 and not replay
			if ranked then rank = rank + 1 end
			Row(scroll, p, ranked and rank or nil)
		end
	end
	-- Someone joined or left while it's open
	frame.Think = function(self)
		if #player.GetAll() ~= self.count then self:Refresh() end
	end
	return frame
end

function GM:ScoreboardShow()
	if not IsValid(board) then board = Build() end
	board:Refresh()
	board:Show()
	board:MakePopup()
	board:SetKeyboardInputEnabled(false)
end

function GM:ScoreboardHide()
	if IsValid(board) then board:Hide() end
	CloseDermaMenus()
end

-- New fonts sizes after a resolution change
hook.Add("OnScreenSizeChanged", "surf_scoreboard", function()
	if IsValid(board) then board:Remove() end
end)
