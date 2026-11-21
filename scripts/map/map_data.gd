class_name MapData
extends RefCounted
## Pure data describing a map: islands, terminals, towns and routes.
## Produced by MapGenerator today (and by a map editor later); WorldBuilder and
## Simulation only read from it, so hand-authored maps can plug straight in.


class Island:
	var key := ""                   # durable within this region; shared by its terminal
	var id := 0
	var name := ""
	var center := Vector2.ZERO      # x, z
	var radius := 120.0
	var strength := 1.0             # elevation multiplier
	var inhabited := true
	var is_mainland := false
	var mainland_port := false      # set against the mainland's shore (the layout's `mainland`)
	var population := 0
	var growth := 0.0               # base % per year
	var wildlife_appeal := 1.0      # how strongly it pulls marine wildlife visits

	# Shape (see Terrain.Stamp): 0 shape_seed samples the noise where the island stands.
	var shape_seed := 0
	var stretch := 1.0
	var angle := 0.0                # radians
	var roughness := 1.0
	var hills := 1.0
	var peak := 0.0
	var lakes := 1.0
	# Cover: how thick the woods are, and how much is open fields instead.
	var forest := 1.0
	var fields := 0.4

	# Ferry terminal (valid when has_terminal)
	var has_terminal := false
	var shore := Vector3.ZERO       # where the pier meets land, y = 0
	var dock_dir := Vector3.FORWARD # horizontal unit vector pointing out to sea
	var slips: Array[Slip] = []     # left → right along lateral()
	var lot_half_width := 36.0
	var open_lanes := 0             # lanes paved at the start (more are bought); 0: the whole lot
	# Placed by hand in the layout: used as given instead of searching the coast.
	var ferry := true               # may get a terminal at all
	var manual_dock := false
	var manual_at := Vector2.ZERO
	var manual_dir := Vector2.RIGHT
	## A positive quote reserves one expansion site on the left of this lot.
	var lane_extension_price := 0
	## Contiguous holding lanes needed alongside the extension for materials and machines.
	var construction_staging_lanes := 1

	# Town
	var town_center := Vector3.ZERO
	var town_axis := Vector3.RIGHT
	var road_main_a := PackedVector3Array()   # lot entrance → town centre
	var road_main_b := PackedVector3Array()   # town centre → inland end
	var road_cross: Array[PackedVector3Array] = []
	var label_pos := Vector3.ZERO

	func lateral() -> Vector3:
		return Vector3.UP.cross(dock_dir)

	func terminal_xform() -> Transform3D:
		return Transform3D(Basis(lateral(), Vector3.UP, dock_dir), shore)

	## Lateral offset of slip `i`. The working slips sit centred on the lot; tie-up
	## slips come after them in `slips` and carry on along the shore to the right.
	func slip_offset(i: int) -> float:
		return (i - (working_slips() - 1) * 0.5) * Layout.SLIP_SPACING

	func working_slips() -> int:
		var n := 0
		for slip in slips:
			if not slip.tie_up:
				n += 1
		return n

	## Indices into `slips` of the tie-up slips.
	func tie_ups() -> Array[int]:
		var out: Array[int] = []
		for i in slips.size():
			if slips[i].tie_up:
				out.append(i)
		return out

	## Where a hull lies centred at slip `i`, in the world (y = 0).
	func berth_center(i: int) -> Vector3:
		return shore + dock_dir * Layout.DOCK_U + lateral() * slip_offset(i)

	## Which slip `route_id` calls at (-1 if it doesn't call here).
	func slip_index(route_id: int) -> int:
		for i in slips.size():
			if route_id in slips[i].routes:
				return i
		return -1

	## Adds a slip of its own for `route_id` (a planned network's way).
	func add_route_slip(route_id: int, size := 3) -> void:
		var slip := Slip.new(size)
		slip.routes.append(route_id)
		slips.append(slip)

	## The routes calling here, slip by slip from left to right.
	func route_ids() -> Array[int]:
		var out: Array[int] = []
		for slip in slips:
			out.append_array(slip.routes)
		return out

	func dock_center(route_id: int) -> Vector3:
		return shore + dock_dir * Layout.DOCK_U + lateral() * slip_offset(slip_index(route_id))


## Somewhere boats tie up along a shore. Its frame is like a terminal's: origin
## where the pier meets the shore, +Z ("u") out to sea, +X ("v") lateral.
class Harbour:
	var id := 0
	var island := 0                 # island id
	var shore := Vector3.ZERO       # where the pier meets land, y = 0
	var dir := Vector3.FORWARD      # horizontal unit vector pointing out to sea

	func lateral() -> Vector3:
		return Vector3.UP.cross(dir)

	func xform() -> Transform3D:
		return Transform3D(Basis(lateral(), Vector3.UP, dir), shore)

	func at(u: float, v: float) -> Vector3:
		return shore + dir * u + lateral() * v

	func berths() -> int:
		return 0

	## Berth `i`'s place along v.
	func berth_v(_i: int) -> float:
		return 0.0

	## Where a boat lines up to come in (u, v).
	func approach() -> Vector2:
		return Vector2.ZERO

	## Where boats waiting to come in may hold: no nearer the shore than `x`, and
	## no nearer the centre line than `y` (to keep out of the approach).
	func wait_bounds() -> Vector2:
		return Vector2.ZERO

	## How far apart boats waiting here hold station.
	func wait_spacing() -> float:
		return 21.0

	## Whether a boat may wait its turn at (u, v) (out of the way in).
	func wait_ok(_u: float, _v: float) -> bool:
		return true


## A small-boat pier with a T-head (see Layout's marina frame).
class Marina extends Harbour:
	func berth_v(i: int) -> float:
		return (i - (Layout.MARINA_BERTHS - 1) * 0.5) * Layout.MARINA_BERTH_SPACING

	func berths() -> int:
		return Layout.MARINA_BERTHS

	func approach() -> Vector2:
		return Vector2(Layout.MARINA_APPROACH_U, 0.0)

	func wait_bounds() -> Vector2:
		return Vector2(120.0, Layout.MARINA_HEAD_HALF + 36.0)


## A wharf boats lie alongside (see Layout's quay frame): a jetty out to a wharf
## whose seaward face the boats lie against, bow to stern, all pointing `side`
## along v. They come in along the lane off the face from astern and crab in
## sideways, and leave the same way round: crab out, then ahead along the lane.
class Wharf extends Harbour:
	var side := 1.0

	func approach() -> Vector2:
		return Vector2(Layout.QUAY_LANE_U, -side * Layout.QUAY_RUN)

	func wait_bounds() -> Vector2:
		return Vector2(Layout.QUAY_LANE_U + 60.0, 0.0)

	func wait_spacing() -> float:
		return 96.0

	## Not off the end of the lane where boats run in.
	func wait_ok(_u: float, v: float) -> bool:
		return absf(v + side * Layout.QUAY_RUN) > 90.0

	## Its name, as the HUD shows it.
	func title(map: MapData) -> String:
		return map.islands[island].name


## The fishing boats' wharf.
class FishQuay extends Wharf:
	func berth_v(i: int) -> float:
		return (i - (Layout.QUAY_BERTHS - 1) * 0.5) * Layout.QUAY_BERTH_SPACING

	func berths() -> int:
		return Layout.QUAY_BERTHS

	func title(map: MapData) -> String:
		return map.islands[island].name + " fish quay"


## Where the pilot boats and tugs that work with the ships are based.
class PilotStation extends Wharf:
	func berth_v(i: int) -> float:
		return (i - (Layout.STATION_BERTHS - 1) * 0.5) * Layout.STATION_BERTH_SPACING

	func berths() -> int:
		return Layout.STATION_BERTHS

	func title(map: MapData) -> String:
		return map.islands[island].name + " pilot station"


## Where seals and sea lions come out of the water to rest: a stretch of gentle
## beach, a low rock ledge just off a rocky shore, or a marina's float.
class HaulOut:
	enum Kind { BEACH, ROCK, DOCK }
	var id := 0
	var kind := Kind.BEACH
	var island := 0                 # island id it's on (may be an islet)
	var near := 0                   # nearest inhabited island: its appeal, its name
	var marina := -1                # a DOCK's marina id
	var water := Vector3.ZERO       # where the group waits offshore, y = 0
	var out := Vector3.FORWARD      # horizontal unit vector out to sea
	var top := 0.0                  # a ROCK's or DOCK's flat top (beaches follow the ground)
	var ledge := Transform3D()      # a ROCK's slab (+Z out to sea), drawn by WorldBuilder
	var ledge_size := Vector3.ONE
	var spots: Array[HaulSpot] = []

	func kind_name() -> String:
		return ["beach", "rocks", "dock"][kind]


## One animal's place at a haul-out. It swims to `entry`, comes out at `edge`
## (the waterline, or the edge of the rock or float) and lies at `at`, head to
## the water so it can be off quickly.
class HaulSpot:
	var at := Vector3.ZERO
	var edge := Vector3.ZERO
	var entry := Vector3.ZERO
	var yaw := 0.0
	var big := true                 # room for a sea lion, not just a seal


## A berth at a terminal. It belongs to the terminal, not to a route: every
## route in `routes` docks here, one boat at a time. A slip with no routes is idle.
## A tie-up slip loads no cars and serves no route: boats out of service park there
## so they never block a working slip.
class Slip:
	const SIZE_NAMES := ["", "small", "medium", "large"]
	## Each size takes boats up to this FerryClass size (small 1–2, medium 3–4, large 5).
	const LARGEST_BOAT := [0, 2, 4, 5]

	var size := 1                   # 1 small, 2 medium, 3 large
	var routes: Array[int] = []
	var tie_up := false

	func _init(slip_size := 1, is_tie_up := false) -> void:
		size = clampi(slip_size, 1, 3)
		tie_up = is_tie_up

	func fits(boat_size: int) -> bool:
		return boat_size <= LARGEST_BOAT[size]

	func size_name() -> String:
		return SIZE_NAMES[size]

	static func size_from_name(text: String) -> int:
		return maxi(SIZE_NAMES.find(text.to_lower()), 1)


class Route:
	var key := ""                   # independent of the runtime array position
	var id := 0
	var a := 0      # island id
	var b := 0
	var curve: Curve3D
	var length := 0.0
	## Whether a schedule sails it. A scenario map also plans a route between every
	## other pair of its terminals so a schedule can be edited onto it in play.
	var in_service := true


var map_seed := 0
var half_size := 3300.0
var islands: Array[Island] = []
var routes: Array[Route] = []

## Lane groups are keyed by route id; an idle terminal's one group by this.
const NO_ROUTE := -1


static func is_route(key: int) -> bool:
	return key >= 0
var marinas: Array[Marina] = []
var quays: Array[FishQuay] = []
var stations: Array[PilotStation] = []
var haul_outs: Array[HaulOut] = []
## Sandy beaches cut into the shore (MapGenerator._place_beaches).
var beaches: Array[Beach] = []


class Beach:
	var shore := Vector3.ZERO       # the middle of its waterline, y = 0
	var dir := Vector3.FORWARD      # out to sea
	var half_width := 40.0
	var beside := false             # next to a ferry lot or marina


## Every wharf on the map: fish quays and pilot stations.
func wharves() -> Array[Wharf]:
	var out: Array[Wharf] = []
	out.append_array(quays)
	out.append_array(stations)
	return out
