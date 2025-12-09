-- Right ankle exoskeleton as a ScriptController (Parts D and F).
-- Sign: the device torque tau is positive when it dorsiflexes the foot.
-- It is applied as an action-reaction pair, +tau on talus_r and -tau on
-- tibia_r, about z. ankle_angle_r is positive in dorsiflexion (rad).
--
-- External moments persist in SCONE (OpenSim 3 adds each call to the body's
-- applied moment), so the script remembers the moment it has applied and adds
-- only the change at each step. Python twin and tests: dropfoot.device.
--
-- Properties (strings, from the ScriptController block):
--   mode          none | constant | passive   (default none)
--   constant_nm, on_time, off_time    constant mode: tau between the two times
--   k_nm_per_rad, theta0_rad          passive mode: tau = -k (theta - theta0)
--   act_delay_s, act_time_constant_s, limit_nm   actuator response (not used in passive mode)
--   and the gyroscope and detector settings of imu.lua, which always run.

local Gyro = require "gyro"
local Detector = require "detector"
local Actuator = require "actuator"
local RAD2DEG = 180.0 / math.pi

local function num( name, default )
	local v = tonumber( scone[ name ] )
	if v == nil then return default end
	return v
end

function init( model, par, side )
	tibia = model:find_body( "tibia_r" )
	talus = model:find_body( "talus_r" )
	ankle = model:find_dof( "ankle_angle_r" )
	mode = scone.mode or "none"

	gyro = Gyro.new( num( "rate_hz", 100 ), num( "noise_dps", 0.5 ), num( "bias_dps", 2.0 ),
		num( "imu_delay_s", 0.015 ), num( "seed", 1 ) )
	detector = Detector.new( {
		swing_dps = num( "swing_dps" ), hs_feature = scone.hs_feature,
		hs_depth_dps = num( "hs_depth_dps" ), hs_rise_dps = num( "hs_rise_dps" ),
		to_depth_dps = num( "to_depth_dps" ), to_rise_dps = num( "to_rise_dps" ),
		lockout_frac = num( "lockout_frac" ), terminal_timeout = num( "terminal_timeout" ),
		stride0 = num( "stride0" ) } )
	actuator = Actuator.new( num( "act_delay_s", 0.0 ), num( "act_time_constant_s", 0.0 ), num( "limit_nm", 1e9 ) )

	constant_nm = num( "constant_nm", 0.0 )
	on_time = num( "on_time", 0.0 )
	off_time = num( "off_time", 1e9 )
	k_spring = num( "k_nm_per_rad", 0.0 )
	theta0 = num( "theta0_rad", 0.0 )

	applied = 0.0 -- moment currently applied to talus_r (and its negative to tibia_r)
	command = 0.0
	w_true = 0.0
	theta = 0.0
	theta_dot = 0.0
	power = 0.0
end

function apply( tau )
	local change = tau - applied
	if change ~= 0.0 then
		talus:add_external_moment( 0, 0, change )
		tibia:add_external_moment( 0, 0, -change )
		applied = tau
	end
end

function update( model, t )
	w_true = tibia:ang_vel().z * RAD2DEG
	if gyro:update( t, w_true ) then
		detector:update( t, gyro.output )
	end
	theta = ankle:position()
	theta_dot = ankle:velocity()

	local tau
	if mode == "constant" then
		if t >= on_time and t < off_time then command = constant_nm else command = 0.0 end
		tau = actuator:update( t, command )
	elseif mode == "passive" then
		command = -k_spring * ( theta - theta0 )
		tau = command -- a spring has no actuator lag
	else
		command = 0.0
		tau = 0.0
	end
	apply( tau )
	power = applied * theta_dot
	return false
end

function store_data( frame )
	frame:set_value( "imu.true", w_true )
	frame:set_value( "imu.measured", gyro.output )
	frame:set_value( "imu.output_k", gyro.output_k )
	frame:set_value( "det.state", detector.state )
	frame:set_value( "det.n_hs", detector.n_hs )
	frame:set_value( "det.n_to", detector.n_to )
	frame:set_value( "det.hs_time", detector.hs_time )
	frame:set_value( "det.to_time", detector.to_time )
	frame:set_value( "det.phase", detector:phase( frame:time() ) )
	frame:set_value( "dev.command", command )
	frame:set_value( "dev.torque", applied )
	frame:set_value( "dev.power", power )
	frame:set_value( "dev.theta", theta )
end
