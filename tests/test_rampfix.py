"""The ramp fix (sh_rampfix.lua) against scripted traces, and the timer
ignoring a bonus start zone surfed through at speed.
Run: python3 tests/test_rampfix.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "mock_gmod.py")
src = open(MOCK).read()
setup = src.split("\nZ = G.SURF.Zones\n")[0]
ns = {"__file__": MOCK, "__name__": "mock_setup"}
exec(compile(setup, MOCK, "exec"), ns)
L, G, check, failures, include = ns["L"], ns["G"], ns["check"], ns["failures"], ns["include"]

L.execute(r'''
local vmeta = getmetatable(Vector(0, 0, 0))
function vmeta:Dot(b) return self.x * b.x + self.y * b.y + self.z * b.z end
function vmeta:GetNormalized() local l = self:Length() return l > 0 and self / l or Vector(0, 0, 0) end
function vmeta:Distance(b) return (self - b):Length() end
MASK_PLAYERSOLID, COLLISION_GROUP_PLAYER_MOVEMENT = 0, 0
-- Each test sets traceHit: the surface any trace finds (nil = nothing)
function util.TraceHull(t)
	if t.start == t.endpos or not traceHit then return { Hit = false, StartSolid = false, HitNormal = Vector(0, 0, 0) } end
	return { Hit = true, StartSolid = false, HitNormal = traceHit }
end
''')
include("sh_rampfix.lua")

L.execute(r'''
ramp = Vector(0.8, 0, 0.6)  -- a surf ramp (normal.z 0.6)
p = MakePlayer("Rampy", "76561190000000077")
function p:Crouching() return false end
function p:GetHull() return Vector(-16, -16, 0), Vector(16, 16, 72) end
function p:GetHullDuck() return Vector(-16, -16, 0), Vector(16, 16, 36) end

-- One tick: velocity and origin in, what the engine made of them out
function Tick(vin, vout, oin, oout)
	local org, vel = oout or oin or Vector(0, 0, 0), vout
	local mv = {}
	function mv:GetVelocity() return vel end
	function mv:SetVelocity(v) vel = v end
	function mv:GetOrigin() return org end
	function mv:SetOrigin(o) org = o end
	local pre = {}
	function pre:GetVelocity() return vin end
	function pre:GetOrigin() return oin or Vector(0, 0, 0) end
	hooks.SetupMove.surf_rampfix(p, pre)
	hooks.FinishMove.surf_rampfix(p, mv)
	return vel, org
end

-- Stopped dead on a ramp: the slide along it comes back
traceHit = ramp
local v = Vector(-1000, 500, -400)
out1 = Tick(v, Vector(0, 0, 0))
want = v - ramp * v:Dot(ramp)

-- The engine slid along fine: left alone
p.SurfRampStreak = 0
out2 = Tick(v, want)

-- Hit a wall: a real stop
traceHit = Vector(1, 0, 0)
out3 = Tick(v, Vector(0, 0, 0))

-- Landing on ground: a real stop
traceHit = ramp
p.ground = true
out4 = Tick(Vector(0, 0, -1500), Vector(0, 0, 0))
p.ground = false

-- A map teleport that zeroes speed far away: left alone
out5 = Tick(v, Vector(0, 0, 0), Vector(0, 0, 0), Vector(5000, 0, 0))

-- Noclip: left alone
p.mt = MOVETYPE_NOCLIP
out6 = Tick(v, Vector(0, 0, 0))
p.mt = MOVETYPE_WALK

-- Really stuck: gives up after a few ticks in a row
p.SurfRampStreak = 0
fixed = 0
for i = 1, 10 do if Tick(v, Vector(0, 0, 0)):Length() > 0 then fixed = fixed + 1 end end
''')
check(abs(G.out1.x - G.want.x) < 1e-6 and abs(G.out1.y - G.want.y) < 1e-6 and abs(G.out1.z - G.want.z) < 1e-6 and G.want.Length(G.want) > 500,
      "speed lost on a ramp comes back as the slide along it")
check(G.out2.Length(G.out2) == G.want.Length(G.want), "a normal slide is left alone")
check(G.out3.Length(G.out3) == 0, "a wall stop is left alone")
check(G.out4.Length(G.out4) == 0, "landing on ground is left alone")
check(G.out5.Length(G.out5) == 0, "a map teleport is left alone")
check(G.out6.Length(G.out6) == 0, "noclip is left alone")
check(G.fixed == 4, f"gives up after 4 ticks in a row ({G.fixed})")

# Timer: surfing fast through a bonus start zone keeps the run
L.execute(r'''
mapname = "surf_lessons"
SURF.Zones.Load()
r = MakePlayer("Runner", "76561190000000078")
SURF.DB.LoadPlayer(r)
SURF.Timer.SetTrack(r, 0, true)
local s0, b1 = SURF.Zones.Find("start", 0), SURF.Zones.Find("start", 1)
SetCurTime(100) SURF.Timer.OnZoneEnter(r, s0) SURF.Timer.OnZoneLeave(r, s0)
r.vel = Vector(1500, 0, 0)
SetCurTime(110) SURF.Timer.OnZoneEnter(r, b1) SURF.Timer.OnZoneLeave(r, b1)
fastState, fastTrack, fastSpeed = r:GetNW2Int("surf_state"), r.SurfTrack, r.vel:Length2D()
-- Walking into it still switches to the bonus
r.vel = Vector(100, 0, 0)
SetCurTime(120) SURF.Timer.OnZoneEnter(r, b1)
slowTrack = r.SurfTrack
''')
check(G.fastState == G.SURF.STATE_RUNNING and G.fastTrack == 0 and G.fastSpeed == 1500,
      f"flying through a bonus start keeps the run and the speed ({G.fastState}, {G.fastTrack}, {G.fastSpeed})")
check(G.slowTrack == 1, "walking into a bonus start switches to it")

print(f"{len(failures)} failure(s)")
raise SystemExit(1 if failures else 0)
