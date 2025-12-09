-- Simulated shank gyroscope (Part D1). Units: deg/s and s.
-- Sign: positive when the shank rotates forward (distal end forward), the
-- sign of tibia_r:ang_vel().z in Human0914 (docs/conventions.md).
--
-- Model, applied to the true sagittal angular velocity w(t):
--   * sampling at rate_hz: sample k is taken at t_k = k / rate_hz, at the
--     first control step with t >= t_k;
--   * y_k = w(t_k) + bias + noise * n_k, with n_k standard normal;
--   * transport delay: y_k becomes available at t_k + delay and is held
--     (zero-order hold) until y_{k+1} becomes available.
-- The normal deviates come from a Park-Miller generator (x <- 16807 x mod
-- 2^31 - 1, exact in double precision) and the Box-Muller transform, so the
-- Python twin dropfoot.sensor.Gyro produces the same sequence from the same seed.

local Gyro = {}
Gyro.__index = Gyro

local MODULUS = 2147483647
local MULTIPLIER = 16807
local EPS = 1e-9

function Gyro.new( rate_hz, noise_dps, bias_dps, delay_s, seed )
	local g = setmetatable( {}, Gyro )
	g.period = 1.0 / rate_hz
	g.noise = noise_dps
	g.bias = bias_dps
	g.delay = delay_s
	g.state = math.floor( seed ) % MODULUS
	if g.state == 0 then g.state = 1 end
	g.k = -1 -- index of the last sample taken
	g.queue = {} -- samples taken but not yet available
	g.head = 1
	g.tail = 0
	g.output = 0.0 -- measured value, held
	g.output_k = -1 -- index of the sample in the output (-1: none yet)
	g.sample_true = 0.0 -- true value at the last sample taken
	return g
end

function Gyro:uniform()
	self.state = ( MULTIPLIER * self.state ) % MODULUS
	return self.state / MODULUS
end

function Gyro:normal()
	local u1 = self:uniform()
	local u2 = self:uniform()
	return math.sqrt( -2.0 * math.log( u1 ) ) * math.cos( 2.0 * math.pi * u2 )
end

-- Advance to time t with the current true value w (deg/s).
-- Returns true when a new measured sample became available at this step.
function Gyro:update( t, w )
	while ( self.k + 1 ) * self.period <= t + EPS do
		self.k = self.k + 1
		self.sample_true = w
		local y = w + self.bias + self.noise * self:normal()
		self.tail = self.tail + 1
		self.queue[ self.tail ] = { available = self.k * self.period + self.delay, value = y, k = self.k }
	end
	local fresh = false
	while self.head <= self.tail and self.queue[ self.head ].available <= t + EPS do
		local s = self.queue[ self.head ]
		self.queue[ self.head ] = nil
		self.head = self.head + 1
		self.output = s.value
		self.output_k = s.k
		fresh = true
	end
	return fresh
end

return Gyro
