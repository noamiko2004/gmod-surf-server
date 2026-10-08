-- Looks: color presets (!graphics), glowing start/end zones with labels
-- (off by default, !zonefx turns them on) and the map light (F or !light).
-- All of it is client-side drawing; none of it changes movement or times.
SURF.Visuals = {}
local V = SURF.Visuals

local graphics = CreateClientConVar("surf_graphics", "1", true, false, "Color preset: 0 off, 1 vivid, 2 cinematic")
-- A new name for the zone setting, so the old saved "on" doesn't carry over
local zoneGlow = CreateClientConVar("surf_zoneglow", "0", true, false, "Glowing zones with labels (0 draws plain outlines)")

surface.CreateFont("SurfZoneLabel", { font = "Roboto", size = 72, weight = 800, antialias = true })

local function ColorTab(c)
	return {
		["$pp_colour_addr"] = c.addr or 0, ["$pp_colour_addg"] = c.addg or 0, ["$pp_colour_addb"] = c.addb or 0,
		["$pp_colour_brightness"] = c.brightness or 0, ["$pp_colour_contrast"] = c.contrast or 1,
		["$pp_colour_colour"] = c.colour or 1,
		["$pp_colour_mulr"] = c.mulr or 0, ["$pp_colour_mulg"] = c.mulg or 0, ["$pp_colour_mulb"] = c.mulb or 0,
	}
end

-- bloom: darken, multiply, size x, size y, passes, color multiply
-- sharpen: contrast, distance
V.Presets = {
	{ id = "off", name = "Off", help = "The map exactly as made. Best FPS." },
	{ id = "vivid", name = "Vivid", help = "Richer colors, a touch of contrast and a soft glow on bright spots.",
	  color = ColorTab({ contrast = 1.05, colour = 1.18 }), bloom = { 0.78, 0.55, 6, 6, 2, 0.8 }, sharpen = { 0.5, 0.6 } },
	{ id = "cinematic", name = "Cinematic", help = "Deeper contrast, cool shadows and a stronger glow.",
	  color = ColorTab({ contrast = 1.14, colour = 1.08, brightness = -0.02, addb = 0.012, mulb = 0.05 }),
	  bloom = { 0.66, 0.85, 9, 9, 2, 0.7 }, sharpen = { 0.35, 0.8 } },
}
V.ByID = {}
for i, p in ipairs(V.Presets) do
	p.index = i - 1
	V.ByID[p.id] = p
end

function V.Current()
	return V.Presets[math.Clamp(graphics:GetInt(), 0, #V.Presets - 1) + 1]
end

function V.SetPreset(id)
	local p = V.ByID[id]
	if not p then return false end
	RunConsoleCommand("surf_graphics", tostring(p.index))
	chat.AddText(SURF.Config.Accent, "[Graphics] ", color_white, "Preset: " .. p.name .. ". " .. p.help)
	return true
end

function V.ZonesOn() return zoneGlow:GetBool() end

function V.ToggleZones()
	local on = not zoneGlow:GetBool()
	RunConsoleCommand("surf_zoneglow", on and "1" or "0")
	chat.AddText(SURF.Config.Accent, "[Graphics] ", color_white, "Glowing zones " .. (on and "on" or "off") .. ".")
end

-- Color grading: the same shader GMod's own color modify uses
local colorMat = Material("pp/colour")
local function ColorModify(tab)
	render.UpdateScreenEffectTexture()
	colorMat:SetTexture("$fbtexture", render.GetScreenEffectTexture())
	for k, v in pairs(tab) do colorMat:SetFloat(k, v) end
	render.SetMaterial(colorMat)
	render.DrawScreenQuad()
end

hook.Add("RenderScreenspaceEffects", "surf_graphics", function()
	local p = V.Current()
	if p and p.id ~= "off" then
		if p.color then ColorModify(p.color) end
		if p.bloom and DrawBloom then
			local b = p.bloom
			DrawBloom(b[1], b[2], b[3], b[4], b[5], b[6], 1, 1, 1)
		end
		if p.sharpen and DrawSharpen then DrawSharpen(p.sharpen[1], p.sharpen[2]) end
	end
	-- Map light (F) last, so it brightens the graded picture
	V.DrawMapLight()
end)

-- Zones -----------------------------------------------------------------------

local ZONE_COLORS = {
	start = Color(0, 255, 120), ["end"] = Color(255, 60, 60),
	bstart = Color(60, 160, 255), bend = Color(200, 90, 255),
}
local WALL = 80
-- Alpha of the glowing wall from the floor up (smooth between the steps)
local FADE = { 1, 0.42, 0.12, 0 }

-- Wall pieces of a zone, worked out once when the zones arrive
local function Geometry(z)
	local x1, y1, x2, y2 = z.min.x, z.min.y, z.max.x, z.max.y
	local floor = z.min.z + 1
	local height = math.min(WALL, math.max(16, z.max.z - z.min.z))
	local corners = { { x1, y1 }, { x2, y1 }, { x2, y2 }, { x1, y2 } }
	-- Each quad: four corners with their share of the wall's alpha
	local quads = {}
	for i = 1, #FADE - 1 do
		local h0, h1 = floor + height * (i - 1) / (#FADE - 1), floor + height * i / (#FADE - 1)
		local f0, f1 = FADE[i], FADE[i + 1]
		for s = 1, 4 do
			local p, q = corners[s], corners[s % 4 + 1]
			local a, b = { Vector(p[1], p[2], h0), f0 }, { Vector(q[1], q[2], h0), f0 }
			local c, d = { Vector(q[1], q[2], h1), f1 }, { Vector(p[1], p[2], h1), f1 }
			quads[#quads + 1] = { a, b, c, d }
			quads[#quads + 1] = { d, c, b, a } -- seen from both sides
		end
	end
	local f = 0.2
	local fl = { { Vector(x1, y1, floor), f }, { Vector(x2, y1, floor), f }, { Vector(x2, y2, floor), f }, { Vector(x1, y2, floor), f } }
	quads[#quads + 1] = fl
	quads[#quads + 1] = { fl[4], fl[3], fl[2], fl[1] }
	return { quads = quads, label = Vector((x1 + x2) / 2, (y1 + y2) / 2, floor + height + 24) }
end

-- One mesh per zone; vertex colors give the wall its fade
local function DrawGlow(g, col, alpha)
	render.SetColorMaterial()
	mesh.Begin(MATERIAL_QUADS, #g.quads)
	for _, q in ipairs(g.quads) do
		for k = 1, 4 do
			mesh.Position(q[k][1])
			mesh.Color(col.r, col.g, col.b, alpha * q[k][2])
			mesh.AdvanceVertex()
		end
	end
	mesh.End()
end

local function LabelText(z)
	local text = z.ztype == "start" and "START" or "END"
	if z.track > 0 then text = "BONUS " .. z.track .. " " .. text end
	return text
end

local paint = Color(0, 0, 0)
local outline = Color(0, 0, 0)
local function DrawZone(z, base, pulse, eye)
	z.geo = z.geo or Geometry(z)
	local g = z.geo
	DrawGlow(g, base, 120 * pulse)
	render.DrawWireframeBox(vector_origin, angle_zero, z.min, Vector(z.max.x, z.max.y, z.min.z + 2), base, true)

	-- Label over the middle, turned to the viewer, fading with distance
	local dist = eye:Distance(g.label)
	local inside = eye.x > z.min.x and eye.x < z.max.x and eye.y > z.min.y and eye.y < z.max.y
	if dist > 3000 or inside then return end
	local alpha = math.Clamp((3000 - dist) / 1000, 0, 1) * 235
	paint.r, paint.g, paint.b, paint.a = base.r, base.g, base.b, alpha
	outline.a = alpha * 0.7
	cam.Start3D2D(g.label, Angle(0, (g.label - eye):Angle().y - 90, 90), 0.3)
		draw.SimpleTextOutlined(LabelText(z), "SurfZoneLabel", 0, 0, paint, TEXT_ALIGN_CENTER, TEXT_ALIGN_BOTTOM, 3, outline)
	cam.End3D2D()
end

hook.Add("PostDrawTranslucentRenderables", "surf_zones", function(depth, skybox)
	if depth or skybox then return end
	local fancy = zoneGlow:GetBool()
	local pulse = 0.8 + 0.2 * math.sin(CurTime() * 2.5)
	local eye = EyePos()
	for _, z in ipairs(SURF.ClientZones or {}) do
		if z.ztype ~= "cp" then
			local base = ZONE_COLORS[(z.track > 0 and "b" or "") .. z.ztype] or color_white
			if fancy then
				DrawZone(z, base, pulse, eye)
			else
				render.DrawWireframeBox(vector_origin, angle_zero, z.min, Vector(z.max.x, z.max.y, z.min.z + 2), base, true)
			end
		end
	end
end)

-- Map light ---------------------------------------------------------------------
-- F (the flashlight key) or !light brightens the dark parts of a map for this
-- player only. It measures the light on what you look at and raises the
-- exposure only where that is low, so lit areas look the same and nothing
-- ever gets darker. (It used to switch the map to fullbright, which takes away
-- the map's own lighting and made most maps flat and darker.) Remembered.
local mapLight = CreateClientConVar("surf_maplight", "0", true, false, "Brighten the dark parts of maps (F or !light)")
function V.MapLightOn() return mapLight:GetBool() end

function V.ToggleMapLight()
	local on = not mapLight:GetBool()
	RunConsoleCommand("surf_maplight", on and "1" or "0")
	surface.PlaySound("items/flashlight1.wav")
	chat.AddText(SURF.Config.Accent, "[Light] ", color_white, on
		and "Map light on: dark spots are brightened for you, lit ones stay as they are. Press F again to turn it off."
		or "Map light off.")
end

hook.Add("PlayerBindPress", "surf_maplight", function(ply, bind, pressed)
	if pressed and string.find(bind, "impulse 100", 1, true) then
		V.ToggleMapLight()
		return true -- instead of the normal flashlight
	end
end)

-- Light levels at or above TARGET are left alone; darker ones are brought up
-- to it, by at most MAX_GAIN times
local TARGET, MAX_GAIN = 0.15, 3
-- Where to measure: the crosshair and four points around it
local SPREAD = { { 0, 0 }, { 0.35, 0 }, { -0.35, 0 }, { 0, 0.25 }, { 0, -0.25 } }
local gain, goal, nextSample = 1, 1, 0

local function Luminance(c) return 0.299 * c.x + 0.587 * c.y + 0.114 * c.z end

-- Average light at your eyes and on the walls and ramps in view (not the sky)
function V.LightLevel()
	local eye, ang = EyePos(), EyeAngles()
	local fwd, right, up = ang:Forward(), ang:Right(), ang:Up()
	local sum, n = Luminance(render.GetLightColor(eye)), 1
	for _, s in ipairs(SPREAD) do
		local tr = util.TraceLine({ start = eye, endpos = eye + (fwd + right * s[1] + up * s[2]) * 4000, mask = MASK_SOLID_BRUSHONLY })
		if tr.Hit and not tr.HitSky then
			sum, n = sum + Luminance(render.GetLightColor(tr.HitPos + tr.HitNormal * 4)), n + 1
		end
	end
	return sum / n
end

function V.LightGain() return gain end

hook.Add("Think", "surf_maplight", function()
	if not mapLight:GetBool() then gain, goal = 1, 1 return end
	local now = RealTime()
	if now >= nextSample then
		nextSample = now + 0.2
		-- Light is measured linear and the screen is gamma, hence the root
		goal = math.Clamp(math.sqrt(TARGET / math.max(V.LightLevel(), 0.001)), 1, MAX_GAIN)
	end
	-- Ease toward it, like eyes getting used to the dark
	gain = gain + (goal - gain) * math.min(1, FrameTime() * 3)
end)

-- Contrast in this shader multiplies the picture: an exposure boost
local lightTab = ColorTab({})
function V.DrawMapLight()
	if gain <= 1.01 then return end
	lightTab["$pp_colour_contrast"] = gain
	ColorModify(lightTab)
end
