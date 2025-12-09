-- Runs scenarios/lua/detector.lua outside SCONE, for tests/test_detector.py.
-- Usage: lua detector_driver.lua <scenarios/lua folder> <hs_feature> < samples
-- Reads "t y" lines from stdin and prints "event t estimate detect phase" for every event.
package.path = arg[ 1 ] .. "/?.lua;" .. package.path
local Detector = require "detector"
local d = Detector.new( { hs_feature = arg[ 2 ] } )
for line in io.lines() do
	local t, y = line:match( "(%S+)%s+(%S+)" )
	t = tonumber( t )
	y = tonumber( y )
	local e = d:update( t, y )
	if e == 1 then
		print( string.format( "1 %.17g %.17g %.17g %.17g", t, d.hs_time, d.hs_detect, d:phase( t ) ) )
	elseif e == 2 then
		print( string.format( "2 %.17g %.17g %.17g %.17g", t, d.to_time, d.to_detect, d:phase( t ) ) )
	end
end
