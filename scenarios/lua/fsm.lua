-- Phase-based finite-state controller of the active AFO (Part F2).
-- Python twin: dropfoot.fsm.PhaseController (same states, same arithmetic).
-- Sign: torque positive when it dorsiflexes; ankle angle positive in
-- dorsiflexion (rad), velocity in rad/s.
--
-- Driven only by the shank-gyroscope detector (its HS and TO events and its
-- phase estimate) and the device's own ankle angle and velocity:
--   OFF          before the first event: no torque;
--   EARLY        from a detected HS until the phase reaches early_frac:
--                viscous braking of plantarflexion, tau = max(0, -b theta_dot);
--   TRANSPARENT  mid and late stance: no torque, so push-off is not resisted;
--   SWING        from a detected TO: PD toward a dorsiflexed target,
--                tau = max(0, kp (target - theta) - kd theta_dot), back to
--                TRANSPARENT after swing_timeout s without a HS (missed event).
-- The device can only lift the foot or brake its fall, as tibialis anterior
-- does, hence the max(0, .). The command then goes through the actuator model.

local FSM = {}
FSM.__index = FSM

FSM.OFF, FSM.EARLY, FSM.TRANSPARENT, FSM.SWING = 0, 1, 2, 3

function FSM.new( cfg )
	local c = setmetatable( {}, FSM )
	c.early_frac = cfg.early_frac or 0.15
	c.b = cfg.brake_nms_per_rad or 1.0
	c.kp = cfg.kp_nm_per_rad or 30.0
	c.kd = cfg.kd_nms_per_rad or 0.6
	c.target = cfg.target_rad or math.rad( 5.0 )
	c.swing_timeout = cfg.swing_timeout_s or 0.8
	c.state = FSM.OFF
	c.t_enter = 0.0
	return c
end

-- event: 0 none, 1 heel strike, 2 toe-off (the detector's return value);
-- phase: the detector's phase estimate at t.
function FSM:update( t, event, phase, theta, theta_dot )
	if event == 1 then
		self.state = FSM.EARLY
		self.t_enter = t
	elseif event == 2 then
		self.state = FSM.SWING
		self.t_enter = t
	end
	if self.state == FSM.EARLY and phase >= self.early_frac then
		self.state = FSM.TRANSPARENT
		self.t_enter = t
	elseif self.state == FSM.SWING and t - self.t_enter > self.swing_timeout then
		self.state = FSM.TRANSPARENT
		self.t_enter = t
	end
	local tau = 0.0
	if self.state == FSM.EARLY then
		tau = -self.b * theta_dot
	elseif self.state == FSM.SWING then
		tau = self.kp * ( self.target - theta ) - self.kd * theta_dot
	end
	if tau < 0.0 then tau = 0.0 end
	return tau
end

return FSM
