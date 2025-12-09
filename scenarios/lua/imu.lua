-- ScriptController that only measures: a simulated gyroscope on the right
-- shank (gyro.lua) and the gait-event detector running on it (detector.lua),
-- logged with store_data. Applies no force.
-- Properties (strings, from the ScriptController block):
--   body (default tibia_r), rate_hz (100), noise_dps (0.5), bias_dps (2),
--   delay_s (0.015), seed (1), and the detector settings of detector.lua
--   (swing_dps, hs_feature, hs_depth_dps, hs_rise_dps, to_depth_dps,
--   to_rise_dps, lockout_frac, terminal_timeout, stride0).

local Gyro = require "gyro"
local Detector = require "detector"
local RAD2DEG = 180.0 / math.pi

function init( model, par, side )
	body = model:find_body( scone.body or "tibia_r" )
	gyro = Gyro.new(
		tonumber( scone.rate_hz ) or 100,
		tonumber( scone.noise_dps ) or 0.5,
		tonumber( scone.bias_dps ) or 2.0,
		tonumber( scone.delay_s ) or 0.015,
		tonumber( scone.seed ) or 1 )
	detector = Detector.new( {
		swing_dps = tonumber( scone.swing_dps ),
		hs_feature = scone.hs_feature,
		hs_depth_dps = tonumber( scone.hs_depth_dps ),
		hs_rise_dps = tonumber( scone.hs_rise_dps ),
		to_depth_dps = tonumber( scone.to_depth_dps ),
		to_rise_dps = tonumber( scone.to_rise_dps ),
		lockout_frac = tonumber( scone.lockout_frac ),
		terminal_timeout = tonumber( scone.terminal_timeout ),
		stride0 = tonumber( scone.stride0 ) } )
	w_true = 0.0
	phase = -1.0
end

function update( model, t )
	w_true = body:ang_vel().z * RAD2DEG
	if gyro:update( t, w_true ) then
		detector:update( t, gyro.output )
	end
	phase = detector:phase( t )
	return false
end

function store_data( frame )
	frame:set_value( "imu.true", w_true )
	frame:set_value( "imu.measured", gyro.output )
	frame:set_value( "imu.output_k", gyro.output_k )
	frame:set_value( "imu.sample_true", gyro.sample_true )
	frame:set_value( "imu.sample_k", gyro.k )
	frame:set_value( "det.state", detector.state )
	frame:set_value( "det.n_hs", detector.n_hs )
	frame:set_value( "det.n_to", detector.n_to )
	frame:set_value( "det.hs_time", detector.hs_time )
	frame:set_value( "det.hs_detect", detector.hs_detect )
	frame:set_value( "det.to_time", detector.to_time )
	frame:set_value( "det.to_detect", detector.to_detect )
	frame:set_value( "det.phase", phase )
end
