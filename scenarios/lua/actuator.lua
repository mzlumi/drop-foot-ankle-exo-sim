-- Closed-loop torque response of the exoskeleton actuator (from Part E):
-- a pure delay followed by a first-order lag, and a symmetric torque limit.
-- Units: N m and s. Python twin: dropfoot.device.ActuatorLag.
--
--   tau_cmd(t)  ->  clip to +-limit  ->  delay  ->  1 / (time_constant s + 1)  ->  tau(t)
--
-- Discretized per control step dt with the exact first-order response to the
-- delayed command held over the step that just ended (zero-order hold):
--   tau <- tau + (u_held - tau) * (1 - exp(-dt / time_constant)),
-- then the delayed command due at t becomes u_held for the next step.
-- With time_constant = 0 the torque is the delayed command itself.

local Actuator = {}
Actuator.__index = Actuator

local EPS = 1e-9

function Actuator.new( delay_s, time_constant_s, limit_nm )
	local a = setmetatable( {}, Actuator )
	a.delay = delay_s
	a.time_constant = time_constant_s
	a.limit = limit_nm
	a.queue = {}
	a.head = 1
	a.tail = 0
	a.delayed = 0.0
	a.torque = 0.0
	a.t_prev = nil
	return a
end

function Actuator:clip( u )
	if u > self.limit then return self.limit end
	if u < -self.limit then return -self.limit end
	return u
end

-- Advance to time t with command u; returns the delivered torque.
function Actuator:update( t, u )
	if self.time_constant > 0 and self.t_prev ~= nil then
		local dt = t - self.t_prev
		self.torque = self.torque + ( self.delayed - self.torque ) * ( 1.0 - math.exp( -dt / self.time_constant ) )
	end
	self.tail = self.tail + 1
	self.queue[ self.tail ] = { t = t + self.delay, u = self:clip( u ) }
	while self.head <= self.tail and self.queue[ self.head ].t <= t + EPS do
		self.delayed = self.queue[ self.head ].u
		self.queue[ self.head ] = nil
		self.head = self.head + 1
	end
	if self.time_constant <= 0 then
		self.torque = self.delayed
	end
	self.t_prev = t
	return self.torque
end

return Actuator
