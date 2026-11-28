class_name CoastGuardLayout
extends RefCounted
## Authored station footprint and vessel berths shared by terrain, traffic and scenery.

const ISLAND := "Port Rosario"
const WEST := -PI * 0.5  # yaw that turns a model's +z front (or a boat's bow) to the sea
## The ramp climbs north up the cliff face from the root to the clifftop.
const RAMP_FOOT := Vector3(2519.0, 0.0, -694.0)
const RAMP_TOP := Vector2(2530.0, -772.0)
## The road: along the clifftop in front of the buildings, then off toward town.
const ROAD := [
	Vector2(2534.0, -772.0),
	Vector2(2548.0, -760.0),
	Vector2(2548.0, -600.0),
	Vector2(2565.0, -545.0)
]
## A level yard east of the road (x0, x1, z0, z1), graded at map generation.
const YARD := Vector4(2552.0, 2605.0, -770.0, -600.0)
const DECK := 1.98  # DockKit.HIGH: the kit's fixed deck height
## [model, berths]: each berth is [x, z, yaw], yaw the way the bow points once in
## (vessels come in bow first and back out). The cutter lies on the west side of the
## pier head, bow north or south (the east side is too tight to the shore); the boats
## lie in the lifeboat houses.
const MOORED := [
	["national_security_cutter", [[2480.6, -790.0, 0.0], [2480.6, -790.0, PI]]],
	["motor_lifeboat_47", [[2506.0, -673.0, -WEST]]],
	["response_boat_small", [[2506.0, -645.0, -WEST]]],
]
