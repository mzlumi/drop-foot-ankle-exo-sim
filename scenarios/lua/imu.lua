-- ScriptController that only measures: a simulated gyroscope on the right
-- shank (gyro.lua), logged with store_data. Applies no force.
-- Properties (strings, from the ScriptController block):
--   body (default tibia_r), rate_hz (100), noise_dps (0.5), bias_dps (2),
--   delay_s (0.015), seed (1).

local Gyro = require "gyro"
local RAD2DEG = 180.0 / math.pi

function init( model, par, side )
	body = model:find_body( scone.body or "tibia_r" )
	gyro = Gyro.new(
		tonumber( scone.rate_hz ) or 100,
		tonumber( scone.noise_dps ) or 0.5,
		tonumber( scone.bias_dps ) or 2.0,
		tonumber( scone.delay_s ) or 0.015,
		tonumber( scone.seed ) or 1 )
	w_true = 0.0
end

function update( model, t )
	w_true = body:ang_vel().z * RAD2DEG
	gyro:update( t, w_true )
	return false
end

function store_data( frame )
	frame:set_value( "imu.true", w_true )
	frame:set_value( "imu.measured", gyro.output )
	frame:set_value( "imu.output_k", gyro.output_k )
	frame:set_value( "imu.sample_true", gyro.sample_true )
	frame:set_value( "imu.sample_k", gyro.k )
end
