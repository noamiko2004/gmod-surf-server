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

	-- Trails (!shop or !trail). No price and no vip = free for everyone,
	-- price = bought with coins, vip = true = free for VIPs (VIP only when
	-- there is no price). The ids are saved in the database, so don't rename
	-- them. Materials ship with GMOD.
	Trails = {
		{ id = "none", name = "No trail" },
		{ id = "white", name = "White Laser", mat = "trails/laser", color = Color(255, 255, 255) },
		{ id = "blue", name = "Blue Laser", mat = "trails/laser", color = Color(0, 160, 255) },
		{ id = "red", name = "Red Laser", mat = "trails/laser", color = Color(255, 60, 60), price = 300, vip = true },
		{ id = "green", name = "Green Laser", mat = "trails/laser", color = Color(60, 255, 90), price = 300, vip = true },
		{ id = "pink", name = "Pink Laser", mat = "trails/laser", color = Color(255, 110, 200), price = 300 },
		{ id = "orange", name = "Orange Laser", mat = "trails/laser", color = Color(255, 150, 40), price = 300 },
		{ id = "gold", name = "Gold Plasma", mat = "trails/plasma", color = Color(255, 200, 40), price = 800, vip = true },
		{ id = "purple", name = "Purple Plasma", mat = "trails/plasma", color = Color(180, 80, 255), price = 800, vip = true },
		{ id = "cyan", name = "Cyan Plasma", mat = "trails/plasma", color = Color(40, 230, 255), price = 800 },
		{ id = "beam", name = "Physics Beam", mat = "trails/physbeam", color = Color(255, 255, 255), price = 1200 },
		{ id = "tube", name = "Tube", mat = "trails/tube", color = Color(140, 200, 255), price = 1200 },
		{ id = "electric", name = "Electric", mat = "trails/electric", color = Color(255, 255, 255), vip = true },
		{ id = "love", name = "Love", mat = "trails/love", color = Color(255, 255, 255), vip = true },
		{ id = "smoke", name = "Smoke", mat = "trails/smoke", color = Color(255, 255, 255), vip = true },
	},

	-- Shop items besides trails, same price/vip rules. Chat tags show after
	-- your title, name colors in chat and on the scoreboard, and finish sounds
	-- play where you are when you finish a run. Ids are saved, don't rename.
	ChatTags = {
		{ id = "gg", name = "GG", color = Color(140, 230, 140), price = 300 },
		{ id = "chill", name = "Chill", color = Color(120, 200, 255), price = 300 },
		{ id = "wave", name = "Wave", color = Color(0, 200, 255), price = 400 },
		{ id = "tryhard", name = "Tryhard", color = Color(255, 110, 80), price = 500 },
		{ id = "shark", name = "Shark", color = Color(120, 160, 200), price = 600 },
		{ id = "speedy", name = "Speedy", color = Color(255, 230, 60), price = 600 },
		{ id = "nightowl", name = "Night Owl", color = Color(170, 130, 255), price = 800 },
		{ id = "bigair", name = "Big Air", color = Color(90, 255, 210), price = 1000 },
		{ id = "goat", name = "GOAT", color = Color(255, 200, 40), price = 2500 },
		{ id = "supporter", name = "Supporter", color = Color(255, 200, 40), vip = true },
	},
	NameColors = {
		{ id = "sky", name = "Sky", color = Color(110, 200, 255), price = 500 },
		{ id = "mint", name = "Mint", color = Color(120, 255, 190), price = 500 },
		{ id = "coral", name = "Coral", color = Color(255, 130, 110), price = 500 },
		{ id = "lavender", name = "Lavender", color = Color(190, 160, 255), price = 500 },
		{ id = "sunset", name = "Sunset", color = Color(255, 150, 50), price = 700 },
		{ id = "crimson", name = "Crimson", color = Color(230, 40, 60), price = 700 },
		{ id = "ice", name = "Ice", color = Color(200, 245, 255), price = 700 },
		{ id = "rainbow", name = "Rainbow", color = Color(255, 80, 200), price = 3000, rainbow = true },
		{ id = "royal", name = "Royal Gold", color = Color(255, 200, 40), vip = true },
	},
	FinishSounds = {
		{ id = "pop", name = "Pop", sound = "garrysmod/balloon_pop_cute.wav", price = 300 },
		{ id = "bell", name = "Bell", sound = "buttons/bell1.wav", price = 300 },
		{ id = "charge", name = "Charged", sound = "items/suitchargeok1.wav", price = 500 },
		{ id = "yeah", name = "Yeah!", sound = "vo/npc/male01/yeah02.wav", price = 600 },
		{ id = "boom", name = "Boom", sound = "weapons/physcannon/energy_sing_explosion2.wav", price = 900 },
	},

	-- Hats sit on your head (the "eyes" attachment): fwd/up/right move them
	-- in units, pitch/yaw/roll turn them, scale sizes them, color tints them.
	-- Models ship with GMOD. Nobody sees their own hat in first person.
	Hats = {
		{ id = "cone", name = "Traffic Cone", model = "models/props_junk/trafficcone001a.mdl", scale = 0.8, fwd = -7, up = 11, pitch = 20, price = 600 },
		{ id = "melon", name = "Melon Head", model = "models/props_junk/watermelon01.mdl", fwd = -2, price = 600 },
		{ id = "bucket", name = "Bucket", model = "models/props_junk/metalbucket01a.mdl", scale = 0.7, fwd = -5, up = 5, pitch = 200, price = 800 },
		{ id = "pot", name = "Cooking Pot", model = "models/props_interiors/pot02a.mdl", fwd = -3, up = 8, right = 5.5, pitch = 180, price = 800 },
		{ id = "hula", name = "Hula Doll", model = "models/props_lab/huladoll.mdl", fwd = -3, up = 7, price = 1000 },
		{ id = "headcrab", name = "Headcrab", model = "models/headcrabclassic.mdl", scale = 0.7, fwd = -2, up = 4, pitch = 20, price = 1500 },
		{ id = "skull", name = "Skull Mask", model = "models/gibs/hgibs.mdl", scale = 1.6, fwd = 1, up = -2, price = 1500 },
		{ id = "balloon", name = "Balloon", model = "models/maxofs2d/balloon_classic.mdl", scale = 0.5, fwd = -4, up = 24, color = Color(0, 200, 255), price = 2000 },
		{ id = "halo", name = "Halo", model = "models/maxofs2d/hover_rings.mdl", scale = 0.5, fwd = -3, up = 13, color = Color(255, 220, 90), vip = true },
		{ id = "goldcone", name = "Golden Cone", model = "models/props_junk/trafficcone001a.mdl", scale = 0.8, fwd = -7, up = 11, pitch = 20, color = Color(255, 200, 40), vip = true },
	},

	-- Player models. The citizen models (models/player/group0x) stay free for
	-- everyone through the normal player model picker; these are bought.
	Skins = {
		{ id = "kleiner", name = "Dr. Kleiner", model = "models/player/kleiner.mdl", price = 800 },
		{ id = "eli", name = "Eli", model = "models/player/eli.mdl", price = 1200 },
		{ id = "odessa", name = "Odessa", model = "models/player/odessa.mdl", price = 1200 },
		{ id = "alyx", name = "Alyx", model = "models/player/alyx.mdl", price = 1500 },
		{ id = "barney", name = "Barney", model = "models/player/barney.mdl", price = 1500 },
		{ id = "mossman", name = "Mossman", model = "models/player/mossman.mdl", price = 1500 },
		{ id = "monk", name = "Father Grigori", model = "models/player/monk.mdl", price = 1500 },
		{ id = "police", name = "Metro Police", model = "models/player/police.mdl", price = 1500 },
		{ id = "breen", name = "Dr. Breen", model = "models/player/breen.mdl", price = 2000 },
		{ id = "magnusson", name = "Magnusson", model = "models/player/magnusson.mdl", price = 2000 },
		{ id = "combine", name = "Combine Soldier", model = "models/player/combine_soldier.mdl", price = 2000 },
		{ id = "guard", name = "Prison Guard", model = "models/player/combine_soldier_prisonguard.mdl", price = 2000 },
		{ id = "chell", name = "Chell", model = "models/player/p2_chell.mdl", price = 2500 },
		{ id = "zombie", name = "Zombie", model = "models/player/zombie_classic.mdl", price = 2500 },
		{ id = "charple", name = "Charple", model = "models/player/charple.mdl", price = 2500 },
		{ id = "elite", name = "Combine Elite", model = "models/player/combine_super_soldier.mdl", price = 3000 },
		{ id = "skeleton", name = "Skeleton", model = "models/player/skeleton.mdl", price = 3000 },
		{ id = "gman", name = "G-Man", model = "models/player/gman_high.mdl", price = 3500 },
		{ id = "arctic", name = "Arctic Mossman", model = "models/player/mossman_arctic.mdl", vip = true },
		{ id = "corpse", name = "Corpse", model = "models/player/corpse1.mdl", vip = true },
	},

	-- VIP bought with coins in !shop (real-money VIP goes through Tebex)
	VIPPackages = {
		{ days = 7, price = 4000 },
		{ days = 30, price = 12000 },
	},

	-- Coins: earned by playing, spent in !shop on cosmetics. They are separate
	-- from rank points, so buying never lowers anyone's rank.
	Coins = {
		FirstFinish = 50, -- first time you finish a map, plus PerTier for each tier
		PerTier = 25, -- (bonuses and styles get half, both get a quarter, like points)
		Improved = 15, -- beating your own best time
		Record = 100, -- new server record (also halved for bonuses and styles)
		Repeat = 5, -- finishing again without a new best
		RepeatPerDay = 30, -- how many repeat finishes pay per day
		Daily = 25, -- first visit of the day
		Playtime = 2, -- every 5 minutes surfing (not AFK, not spectating)
		VIPBonus = 0.5, -- VIPs earn 50% more
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
		"Type !hud to move, resize or hide the timer, key display and the rest of your HUD.",
		"Type !graphics for color presets (Vivid, Cinematic or Off) and glowing zones.",
		"Map too dark? Press F (or type !light) to brighten the dark parts just for you.",
		"Join our Discord: {discord} (or type !discord), then !link your account to show your rank there.",
		"Start a chat message with ! to see every command. Tab completes it.",
		"Leaderboards and player profiles: {portal}",
		"Finish maps to earn points and climb the titles. Type !rank to see yours.",
		"Every finish earns coins. Spend them on hats, skins, trails and more in !shop, or save up for VIP.",
		"Want a different map? Type !rtv, or !nominate <map> before the vote.",
		"New daily challenges every day and bigger weekly ones: type !challenges. Each pays coins.",
		"Finish the map of the day for bonus coins. !motd shows which one it is.",
		"Think you're faster? !race <name> challenges someone to a race to the end.",
		"Play on consecutive days to grow your streak bonus. !streak shows yours.",
		"Achievements pay coins too. !achievements shows them all and how close you are.",
	},

	-- Where players can support the server. Shown by !vip / !store.
	StoreURL = "",
	DiscordURL = "",
}

SURF.TrailByID = {}
for _, t in ipairs(SURF.Config.Trails) do
	SURF.TrailByID[t.id] = t
end

-- Shop catalog: every item has a key "<category>:<id>", e.g. "trail:gold".
-- The admin page can change price, vip and hidden per item (sv_shop.lua).
SURF.ShopCategories = {
	{ id = "trail", name = "Trails", list = SURF.Config.Trails },
	{ id = "hat", name = "Hats", list = SURF.Config.Hats },
	{ id = "skin", name = "Skins", list = SURF.Config.Skins },
	{ id = "tag", name = "Chat tags", list = SURF.Config.ChatTags },
	{ id = "color", name = "Name colors", list = SURF.Config.NameColors },
	{ id = "sound", name = "Finish sounds", list = SURF.Config.FinishSounds },
}
SURF.ItemByKey = {}
for _, cat in ipairs(SURF.ShopCategories) do
	for _, it in ipairs(cat.list) do
		it.cat = cat.id
		it.key = cat.id .. ":" .. it.id
		SURF.ItemByKey[it.key] = it
	end
end

SURF.StyleByID = {}
for _, s in ipairs(SURF.Config.Styles) do
	SURF.StyleByID[s.id] = s
end
