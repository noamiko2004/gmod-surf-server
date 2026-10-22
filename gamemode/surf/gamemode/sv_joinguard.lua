-- Players who connect but never make it into the game (for example "Client's
-- map differs from the server's", or a map download that fails). With nobody
-- in game the map never changes, so one map like that could lock everyone out
-- for days. After two failed joins in a row, or one whose reason names the
-- map, with nobody playing: switch to another map, log an error (the health
-- check counts it) and list the map in join_failed.txt so the next update
-- downloads it again (scripts/maps.py).
local FAILED_FILE = "surfline/join_failed.txt"
local connecting, fails = {}, 0

gameevent.Listen("player_connect")
gameevent.Listen("player_disconnect")

local function InGame()
	for _, p in ipairs(player.GetHumans()) do
		if not connecting[p:UserID()] then return true end
	end
	return false
end

local function Leave(reason)
	local map = game.GetMap()
	local listed = file.Read(FAILED_FILE, "DATA") or ""
	if not string.find("\n" .. listed, "\n" .. map .. "\n", 1, true) then
		file.Write(FAILED_FILE, listed .. map .. "\n")
	end
	local pool = {}
	for _, m in ipairs(SURF.MapVote.Playable()) do
		if m ~= map then pool[#pool + 1] = m end
	end
	ErrorNoHalt("[SURF] error: players could not join " .. map .. " (" .. reason .. "), " ..
		(#pool > 0 and "switching map" or "no other map to switch to") .. "\n")
	if #pool == 0 then return end
	local pick = pool[math.random(#pool)]
	timer.Simple(3, function() RunConsoleCommand("changelevel", pick) end)
end

hook.Add("player_connect", "surf_joinguard", function(d)
	if tonumber(d.bot) ~= 1 then connecting[d.userid] = true end
end)

hook.Add("PlayerInitialSpawn", "surf_joinguard", function(ply)
	connecting[ply:UserID()] = nil
	if not ply:IsBot() then fails = 0 end
end)

hook.Add("player_disconnect", "surf_joinguard", function(d)
	if not connecting[d.userid] then return end
	connecting[d.userid] = nil
	fails = fails + 1
	local reason = tostring(d.reason or "")
	local mapError = string.find(string.lower(reason), "map", 1, true) ~= nil
	if (fails >= 2 or mapError) and not InGame() then
		fails = 0
		Leave(reason ~= "" and reason or "left while loading")
	end
end)
