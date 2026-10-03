-- Everything a server owner is likely to tweak lives here.
SURF = SURF or {}

SURF.Config = {
	Name = "Surf", -- fallback; BRAND_NAME in config.env wins
	Accent = Color(0, 200, 255),

	-- Movement
	WalkSpeed = 250,
	JumpPower = 290,
	StartSpeedCap = 290, -- horizontal speed allowed when leaving the start zone
	DefaultAutoHop = true,

	-- Zones
	ZoneHeight = 128, -- how far a zone box extends above the higher corner

	-- Map rotation
	MapPrefix = "surf_",
	MapTimeLimit = 40 * 60, -- seconds before an automatic map vote
	MapExtendTime = 15 * 60,
	RTVRatio = 0.6,
	RTVMinPlayTime = 60, -- seconds after map start before rtv is allowed
	MapVoteTime = 20,
	MapVoteChoices = 6,

	RespawnDelay = 1,

	-- Extra workshop addons every client should download (e.g. a CS:S
	-- texture pack). Map addons are added automatically for the current map.
	ClientWorkshop = {},

	-- Trails. vip = true means VIP only. Materials ship with GMOD.
	Trails = {
		{ id = "none", name = "No trail" },
		{ id = "white", name = "White Laser", mat = "trails/laser", color = Color(255, 255, 255) },
		{ id = "blue", name = "Blue Laser", mat = "trails/laser", color = Color(0, 160, 255) },
		{ id = "red", name = "Red Laser", mat = "trails/laser", color = Color(255, 60, 60), vip = true },
		{ id = "green", name = "Green Laser", mat = "trails/laser", color = Color(60, 255, 90), vip = true },
		{ id = "gold", name = "Gold Plasma", mat = "trails/plasma", color = Color(255, 200, 40), vip = true },
		{ id = "purple", name = "Purple Plasma", mat = "trails/plasma", color = Color(180, 80, 255), vip = true },
		{ id = "electric", name = "Electric", mat = "trails/electric", color = Color(255, 255, 255), vip = true },
		{ id = "love", name = "Love", mat = "trails/love", color = Color(255, 255, 255), vip = true },
		{ id = "smoke", name = "Smoke", mat = "trails/smoke", color = Color(255, 255, 255), vip = true },
	},

	-- Titles by points (see sv_ranks.lua). Shown in chat and on the scoreboard.
	Titles = {
		{ points = 0, name = "Newbie", color = Color(170, 170, 170) },
		{ points = 30, name = "Rookie", color = Color(140, 220, 140) },
		{ points = 120, name = "Surfer", color = Color(80, 200, 255) },
		{ points = 300, name = "Skilled", color = Color(120, 140, 255) },
		{ points = 600, name = "Pro", color = Color(200, 120, 255) },
		{ points = 1200, name = "Elite", color = Color(255, 120, 60) },
		{ points = 2500, name = "Legend", color = Color(255, 200, 40) },
	},

	-- Run styles (!style). Each one has its own records. Times on a style other
	-- than Normal are worth half the points. The ids are part of the record keys
	-- in the database ("map@sw"), so don't rename them.
	Styles = {
		{ id = "n", name = "Normal", short = "N", help = "All keys" },
		{ id = "sw", name = "Sideways", short = "SW", help = "Only W and S" },
		{ id = "hsw", name = "Half-Sideways", short = "HSW", help = "Two keys at once: W or S with A or D" },
		{ id = "w", name = "W-Only", short = "W", help = "Only W" },
		{ id = "lg", name = "Low Gravity", short = "LG", help = "60% gravity", gravity = 0.6 },
	},

	-- Players who don't press anything for this long move to spectators,
	-- and don't count towards the !rtv votes needed.
	AFKTime = 5 * 60,

	-- A tip in chat every few minutes ({portal} becomes the website address)
	TipInterval = 4 * 60,
	Tips = {
		"Try another style with !style: Sideways, Half-Sideways, W-Only or Low Gravity. Each has its own records.",
		"Type !replay to watch the server record run.",
		"!saveloc saves your spot and !tele takes you back, for practice.",
		"!mapinfo shows the map's tier, stages, record and your best.",
		"!stage <number> takes you to a stage to practice it.",
		"Hide other players with !hide. Turn the key display on or off with !keys.",
		"Type !graphics for color presets (Vivid, Cinematic or Off) and glowing zones.",
		"Leaderboards and player profiles: {portal}",
		"Finish maps to earn points and climb the titles. Type !rank to see yours.",
		"Want a different map? Type !rtv, or !nominate <map> before the vote.",
	},

	-- Where players can support the server. Shown by !vip / !store.
	StoreURL = "",
	DiscordURL = "",
}

SURF.TrailByID = {}
for _, t in ipairs(SURF.Config.Trails) do
	SURF.TrailByID[t.id] = t
end

SURF.StyleByID = {}
for _, s in ipairs(SURF.Config.Styles) do
	SURF.StyleByID[s.id] = s
end
