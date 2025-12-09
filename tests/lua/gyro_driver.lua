-- Runs scenarios/lua/gyro.lua on a known signal outside SCONE, for tests/test_sensor.py.
-- Usage: lua gyro_driver.lua <scenarios/lua folder> <rate_hz> <noise> <bias> <delay> <seed>
package.path = arg[ 1 ] .. "/?.lua;" .. package.path
local Gyro = require "gyro"
local g = Gyro.new( tonumber( arg[ 2 ] ), tonumber( arg[ 3 ] ), tonumber( arg[ 4 ] ), tonumber( arg[ 5 ] ), tonumber( arg[ 6 ] ) )
for i = 0, 1999 do
	local t = i * 0.001
	local w = 300.0 * math.sin( 2.0 * math.pi * t ) + 40.0 * math.cos( 7.0 * t )
	g:update( t, w )
	print( string.format( "%.17g %.17g %d", t, g.output, g.output_k ) )
end
