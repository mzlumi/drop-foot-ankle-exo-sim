-- Runs scenarios/lua/device.lua outside SCONE with mock bodies that sum every
-- add_external_moment call, for tests/test_device.py.
-- Usage: lua device_driver.lua <scenarios/lua folder> <mode> [key=value ...]
-- Prints "t applied talus_sum tibia_sum command" per step (1 ms, 3 s).
local folder = arg[ 1 ]
package.path = folder .. "/?.lua;" .. package.path

local function mock_body( name )
	local b = { name = name, mz = 0.0, calls = 0 }
	function b:add_external_moment( x, y, z ) self.mz = self.mz + z; self.calls = self.calls + 1 end
	function b:ang_vel() return { x = 0, y = 0, z = 2.0 * math.sin( 6.0 * clock ) } end
	return b
end
clock = 0.0
local bodies = { tibia_r = mock_body( "tibia_r" ), talus_r = mock_body( "talus_r" ) }
local dof = {}
function dof:position() return 0.2 * math.sin( 5.0 * clock ) end
function dof:velocity() return 1.0 * math.cos( 5.0 * clock ) end
local model = {}
function model:find_body( name ) return bodies[ name ] end
function model:find_dof( name ) return dof end

scone = { mode = arg[ 2 ] }
for i = 3, #arg do
	local k, v = arg[ i ]:match( "([^=]+)=(.+)" )
	scone[ k ] = v
end
dofile( folder .. "/device.lua" )
init( model, nil, 1 )
for i = 0, 2999 do
	clock = i * 0.001
	update( model, clock )
	print( string.format( "%.17g %.17g %.17g %.17g %.17g", clock, applied, bodies.talus_r.mz, bodies.tibia_r.mz, command ) )
end
