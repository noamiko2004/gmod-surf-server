-- Invisible box trigger for start/end zones. Spawned by sv_zones.lua.
AddCSLuaFile()

ENT.Type = "anim"
ENT.Base = "base_anim"
ENT.PrintName = "Surf Zone"
ENT.Spawnable = false

if CLIENT then return end

function ENT:Initialize()
	local half = (self.max - self.min) / 2
	self:SetSolid(SOLID_BBOX)
	self:PhysicsInitBox(-half, half)
	self:SetCollisionBoundsWS(self.min, self.max)
	self:SetTrigger(true)
	self:DrawShadow(false)
	self:SetNotSolid(true)
	self:SetNoDraw(true)
	self:SetMoveType(MOVETYPE_NONE)

	local phys = self:GetPhysicsObject()
	if IsValid(phys) then
		phys:Sleep()
		phys:EnableCollisions(false)
	end
end

function ENT:StartTouch(ent)
	if IsValid(ent) and ent:IsPlayer() then
		SURF.Timer.OnZoneEnter(ent, self.ztype)
	end
end

function ENT:EndTouch(ent)
	if IsValid(ent) and ent:IsPlayer() then
		SURF.Timer.OnZoneLeave(ent, self.ztype)
	end
end

function ENT:UpdateTransmitState()
	return TRANSMIT_NEVER
end
