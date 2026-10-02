local board

local BG = Color(10, 12, 18, 235)
local ROW = Color(255, 255, 255, 8)
local DIM = Color(170, 180, 195)
local GOLD = Color(255, 200, 40)

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

local function Build()
	local w, h = math.min(820, ScrW() - 40), math.min(640, ScrH() - 80)
	local frame = vgui.Create("DPanel")
	frame:SetSize(w, h)
	frame:Center()
	frame.Paint = function(_, pw, ph)
		draw.RoundedBox(10, 0, 0, pw, ph, BG)
		local acc = SURF.Config.Accent
		draw.SimpleText(GetHostName(), "SurfLarge", 20, 26, acc, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
		draw.SimpleText(game.GetMap() .. "  |  " .. #player.GetHumans() .. "/" .. game.MaxPlayers() .. " players", "SurfSmall", pw - 20, 26, DIM, TEXT_ALIGN_RIGHT, TEXT_ALIGN_CENTER)
		local hy = 60
		draw.SimpleText("#", "SurfSmall", 24, hy, DIM)
		draw.SimpleText("Player", "SurfSmall", 60, hy, DIM)
		draw.SimpleText("Title", "SurfSmall", pw - 400, hy, DIM)
		draw.SimpleText("Best time", "SurfSmall", pw - 260, hy, DIM)
		draw.SimpleText("Ping", "SurfSmall", pw - 70, hy, DIM)
	end

	local scroll = vgui.Create("DScrollPanel", frame)
	scroll:SetPos(10, 84)
	scroll:SetSize(w - 20, h - 94)

	frame.Refresh = function()
		scroll:Clear()
		local rank = 0
		for _, p in ipairs(SortedPlayers()) do
			local replay = p:GetNW2Bool("surf_replay", false)
			local pb = PB(p)
			if pb > 0 and not replay then rank = rank + 1 end
			local thisRank = (pb > 0 and not replay) and rank or nil
			local row = scroll:Add("DPanel")
			row:Dock(TOP)
			row:DockMargin(0, 0, 0, 4)
			row:SetTall(34)
			row.Paint = function(_, rw, rh)
				if not IsValid(p) then return end
				draw.RoundedBox(6, 0, 0, rw, rh, replay and Color(255, 200, 40, 20) or ROW)
				draw.SimpleText(thisRank and tostring(thisRank) or "-", "SurfMedium", 14, rh / 2, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				if replay then
					draw.SimpleText("[REPLAY] " .. p:GetNW2String("surf_replay_name", "?"), "SurfMedium", 50, rh / 2, GOLD, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
					draw.SimpleText("Server record", "SurfMedium", rw - 390, rh / 2, GOLD, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				else
					local nameCol = SURF.IsVIP(p) and Color(255, 220, 120) or color_white
					local tag = p:IsAdmin() and "[ADMIN] " or (SURF.IsVIP(p) and "[VIP] " or "")
					if p:Team() == TEAM_SPECTATOR then tag = tag .. "(spec) " end
					draw.SimpleText(tag .. p:Nick(), "SurfMedium", 50, rh / 2, nameCol, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
					local title = SURF.Config.Titles[p:GetNW2Int("surf_title", 1)] or SURF.Config.Titles[1]
					draw.SimpleText(title.name .. "  " .. p:GetNW2Int("surf_points", 0), "SurfMedium", rw - 390, rh / 2, title.color, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				end
				draw.SimpleText(SURF.FormatTime(PB(p)), "SurfMedium", rw - 250, rh / 2, color_white, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
				draw.SimpleText(replay and "BOT" or p:Ping(), "SurfMedium", rw - 60, rh / 2, DIM, TEXT_ALIGN_LEFT, TEXT_ALIGN_CENTER)
			end
		end
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
end
