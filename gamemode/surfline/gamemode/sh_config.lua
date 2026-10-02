-- Everything a server owner is likely to tweak lives here.
SURF = SURF or {}

SURF.Config = {
	Name = "Surfline",
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

	-- Where players can support the server. Shown by !vip / !store.
	StoreURL = "",
	DiscordURL = "",
}

SURF.TrailByID = {}
for _, t in ipairs(SURF.Config.Trails) do
	SURF.TrailByID[t.id] = t
end
