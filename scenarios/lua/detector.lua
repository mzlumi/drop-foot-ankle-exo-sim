-- Causal gait-event detector on the measured shank gyroscope (Part D2).
-- Units: deg/s and s. Sign: positive when the shank rotates forward.
-- Python twin: dropfoot.detector.Detector (same states, same arithmetic).
--
-- It runs once per new gyroscope sample (time t = when the sample became
-- available) and uses only that sample and earlier ones. Features of the
-- shank pattern in one stride (docs/conventions.md):
--   swing     the signal rises above swing_dps (mid-swing peak, positive);
--   terminal  after that peak it crosses zero going down;
--   HS        heel strike: with hs_feature = "min", the first negative
--             minimum after the zero crossing, confirmed when the signal has
--             risen hs_rise_dps above it and the minimum is below -hs_depth_dps;
--             with hs_feature = "zero", the zero crossing itself;
--   TO        toe-off: after a lockout of lockout_frac stride times from HS,
--             the negative minimum below -to_depth_dps, confirmed when the
--             signal has risen to_rise_dps above it.
-- An event's time estimate is the time of the sample at the extremum (or
-- the interpolated zero crossing); its detection time is the time at which
-- it was confirmed. Both lag the true event by at least the sensor delay.
-- Gait phase: (t - last HS estimate) / mean of the last 3 stride times,
-- capped at 1; -1 before the first HS.

local Detector = {}
Detector.__index = Detector

local SEARCH, SWING, TERMINAL, STANCE, PRESWING = 0, 1, 2, 3, 4

function Detector.new( cfg )
	local d = setmetatable( {}, Detector )
	d.swing_dps = cfg.swing_dps or 100.0
	d.hs_feature = cfg.hs_feature or "min"
	d.hs_depth_dps = cfg.hs_depth_dps or 50.0
	d.hs_rise_dps = cfg.hs_rise_dps or 20.0
	d.to_depth_dps = cfg.to_depth_dps or 100.0
	d.to_rise_dps = cfg.to_rise_dps or 20.0
	d.lockout_frac = cfg.lockout_frac or 0.35
	d.terminal_timeout = cfg.terminal_timeout or 0.3
	d.stride0 = cfg.stride0 or 1.1
	d.state = SEARCH
	d.t_prev = nil
	d.y_prev = nil
	d.t_enter = 0.0 -- time the current state was entered
	d.ext_y = 0.0 -- running extremum and its time
	d.ext_t = 0.0
	d.hs_time = -1.0
	d.hs_detect = -1.0
	d.to_time = -1.0
	d.to_detect = -1.0
	d.n_hs = 0
	d.n_to = 0
	d.strides = { d.stride0, d.stride0, d.stride0 }
	return d
end

function Detector:mean_stride()
	return ( self.strides[ 1 ] + self.strides[ 2 ] + self.strides[ 3 ] ) / 3.0
end

function Detector:heel_strike( t_event, t )
	if self.n_hs > 0 then
		local T = t_event - self.hs_time
		if T >= 0.6 and T <= 2.0 then
			self.strides[ 1 ] = self.strides[ 2 ]
			self.strides[ 2 ] = self.strides[ 3 ]
			self.strides[ 3 ] = T
		end
	end
	self.hs_time = t_event
	self.hs_detect = t
	self.n_hs = self.n_hs + 1
	self.state = STANCE
	self.t_enter = t
end

-- Feed one sample y that became available at time t. Returns the event
-- detected at this sample: 0 none, 1 heel strike, 2 toe-off.
function Detector:update( t, y )
	local event = 0
	local s = self.state
	if s == SEARCH then
		if y > self.swing_dps then
			self.state = SWING
			self.t_enter = t
		end
	elseif s == SWING then
		if y < 0.0 then
			local tz = t
			if self.y_prev ~= nil and self.y_prev > y then
				tz = self.t_prev + ( t - self.t_prev ) * self.y_prev / ( self.y_prev - y )
			end
			if self.hs_feature == "zero" then
				self:heel_strike( tz, t )
				event = 1
			else
				self.state = TERMINAL
				self.t_enter = t
				self.ext_y = y
				self.ext_t = t
			end
		end
	elseif s == TERMINAL then
		if y < self.ext_y then
			self.ext_y = y
			self.ext_t = t
		end
		if self.ext_y < -self.hs_depth_dps and y > self.ext_y + self.hs_rise_dps then
			self:heel_strike( self.ext_t, t )
			event = 1
		elseif t - self.t_enter > self.terminal_timeout then
			self.state = SEARCH -- lost: wait for the next swing
			self.t_enter = t
		end
	elseif s == STANCE then
		if t - self.hs_time > self.lockout_frac * self:mean_stride() then
			self.state = PRESWING
			self.t_enter = t
			self.ext_y = y
			self.ext_t = t
		end
	elseif s == PRESWING then
		if y < self.ext_y then
			self.ext_y = y
			self.ext_t = t
		end
		if self.ext_y < -self.to_depth_dps and y > self.ext_y + self.to_rise_dps then
			self.to_time = self.ext_t
			self.to_detect = t
			self.n_to = self.n_to + 1
			self.state = SEARCH
			self.t_enter = t
			event = 2
		elseif t - self.hs_time > 2.0 then
			self.state = SEARCH -- no toe-off within 2 s of heel strike
			self.t_enter = t
		end
	end
	self.t_prev = t
	self.y_prev = y
	return event
end

function Detector:phase( t )
	if self.n_hs == 0 then return -1.0 end
	local p = ( t - self.hs_time ) / self:mean_stride()
	if p > 1.0 then p = 1.0 end
	return p
end

return Detector
