-- World-record replay bot. Records every main-track run tick by tick; when a
-- run sets the server record it's saved to data/surfline/replays/<map>.dat
-- and a bot named "WR Replay" plays it back on a loop. !replay spectates it.
SURF.Replay = { frames = nil, n = 0, idx = 1, info = nil, bot = nil }
local R = SURF.Replay
local DIR = "surfline/replays"
local MAGIC = "SLR1"
local MAX_MINUTES = 20

local function MaxFrames()
	return math.floor(MAX_MINUTES * 60 / engine.TickInterval())
end

local function Path()
	return DIR .. "/" .. game.GetMap() .. ".dat"
end

-- Recording -----------------------------------------------------------------

function R.StartRecording(ply)
	if ply:IsBot() then return end
	ply.SurfRec, ply.SurfRecN = {}, 0
end

function R.StopRecording(ply)
	local frames, n = ply.SurfRec, ply.SurfRecN
	ply.SurfRec, ply.SurfRecN = nil, 0
	return frames, n
end

hook.Add("FinishMove", "surf_replay_record", function(ply, mv)
	local rec = ply.SurfRec
	if not rec then return end
	local n = ply.SurfRecN
	if n >= MaxFrames() then
		ply.SurfRec = nil -- too long to keep; this run just won't have a replay
		return
	end
	local o, a = mv:GetOrigin(), mv:GetAngles()
	local i = n * 5
	rec[i + 1], rec[i + 2], rec[i + 3], rec[i + 4], rec[i + 5] = o.x, o.y, o.z, a.p, a.y
	ply.SurfRecN = n + 1
end)

-- Saving / loading ----------------------------------------------------------

local function Save(info, frames, n)
	file.CreateDir(DIR)
	local f = file.Open(Path(), "wb", "DATA")
	if not f then return end
	f:Write(MAGIC)
	f:WriteFloat(info.time)
	f:WriteFloat(engine.TickInterval())
	f:WriteULong(n)
	local name = string.sub(info.name, 1, 64)
	f:WriteByte(#name)
	f:Write(name)
	for i = 1, n * 5 do f:WriteFloat(frames[i]) end
	f:Close()
end

local function Load()
	local f = file.Open(Path(), "rb", "DATA")
	if not f then return end
	if f:Read(4) ~= MAGIC then f:Close() return end
	local time = f:ReadFloat()
	f:ReadFloat() -- tick interval it was recorded at
	local n = f:ReadULong()
	local name = f:Read(f:ReadByte()) or "?"
	if n <= 0 or n > MaxFrames() * 2 then f:Close() return end
	local frames = {}
	for i = 1, n * 5 do frames[i] = f:ReadFloat() end
	f:Close()
	return { time = time, name = name }, frames, n
end

-- Playback ------------------------------------------------------------------

local function UpdateBot()
	local bot = R.bot
	if not IsValid(bot) or not R.info then return end
	bot:SetNW2Bool("surf_replay", true)
	bot:SetNW2String("surf_replay_name", R.info.name)
	bot:SetNW2Float("surf_pb", R.info.time)
	bot:SetNW2Float("surf_wr", R.info.time)
	bot:SetNW2Float("surf_final", R.info.time)
	bot:SetNW2Float("surf_mainpb", R.info.time)
end

function R.EnsureBot()
	if not R.frames or IsValid(R.bot) then return end
	if #player.GetAll() >= game.MaxPlayers() then return end
	R.bot = player.CreateNextBot("WR Replay")
	UpdateBot()
end

function R.SetRecord(ply, time, frames, n)
	if not frames or n < 2 then return end
	R.info = { time = time, name = ply:Nick() }
	R.frames, R.n, R.idx = frames, n, 1
	Save(R.info, frames, n)
	R.EnsureBot()
	UpdateBot()
end

-- Called from GM:PlayerSpawn for the replay bot
function R.SetupBot(bot)
	bot:SetMoveType(MOVETYPE_NOCLIP)
	bot:SetCollisionGroup(COLLISION_GROUP_IN_VEHICLE)
	bot:GodEnable()
	bot:SetAvoidPlayers(false)
	local ent = util.SpriteTrail(bot, 0, Color(255, 200, 40), false, 16, 0, 1.5, 1 / 16 * 0.5, "trails/plasma.vmt")
	bot:SetNW2Entity("surf_trail", ent)
	UpdateBot()
end

hook.Add("StartCommand", "surf_replay", function(ply, cmd)
	if ply == R.bot then
		cmd:ClearMovement()
		cmd:ClearButtons()
	end
end)

hook.Add("SetupMove", "surf_replay", function(ply, mv)
	if ply ~= R.bot or not R.frames then return end
	local f, i = R.frames, R.idx
	if i == 1 then
		ply:SetNW2Int("surf_state", SURF.STATE_RUNNING)
		ply:SetNW2Float("surf_start", CurTime())
	end
	if i > R.n then
		-- Hold at the end for two seconds, then loop
		if not R.holdUntil then
			R.holdUntil = CurTime() + 2
			ply:SetNW2Int("surf_state", SURF.STATE_FINISHED)
		end
		if CurTime() < R.holdUntil then return end
		R.holdUntil, R.idx, i = nil, 1, 1
		ply:SetNW2Int("surf_state", SURF.STATE_RUNNING)
		ply:SetNW2Float("surf_start", CurTime())
	end
	local b = (i - 1) * 5
	local pos = Vector(f[b + 1], f[b + 2], f[b + 3])
	local ang = Angle(f[b + 4], f[b + 5], 0)
	mv:SetOrigin(pos)
	mv:SetAngles(ang)
	mv:SetMoveAngles(ang)
	ply:SetEyeAngles(ang)
	if i < R.n then
		local nb = i * 5
		mv:SetVelocity(Vector(f[nb + 1] - f[b + 1], f[nb + 2] - f[b + 2], f[nb + 3] - f[b + 3]) / engine.TickInterval())
	end
	R.idx = i + 1
end)

hook.Add("Move", "surf_replay", function(ply)
	if ply == R.bot then return true end
end)

hook.Add("InitPostEntity", "surf_replay_load", function()
	local info, frames, n = Load()
	if not info then return end
	R.info, R.frames, R.n, R.idx = info, frames, n, 1
	timer.Simple(5, R.EnsureBot)
end)

-- Re-add the bot if it was kicked or a slot freed up
timer.Create("surf_replay_bot", 30, 0, function() R.EnsureBot() end)

function R.Spectate(ply)
	if not IsValid(R.bot) then
		SURF.Chat(ply, SURF.Config.Accent, "[Replay] ", color_white, "No record replay on this map yet. Set one!")
		return
	end
	if ply:Team() ~= TEAM_SPECTATOR then SURF.Spec.Toggle(ply) end
	ply:Spectate(OBS_MODE_IN_EYE)
	ply:SpectateEntity(R.bot)
end
