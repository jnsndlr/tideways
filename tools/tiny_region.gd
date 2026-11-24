class_name TinyRegion
extends RefCounted
## A hand-placed region small enough to build in a fraction of a second: two
## island towns facing each other across a narrow passage with one ferry route
## between them, or three towns in a triangle with three routes (`towns` = 3) for
## checks that need ferries to meet. No marinas, quays, haul-outs or scenery;
## the only other traffic is the passing cargo ship every simulation starts with.
##
## It is laid out with MapGenerator's own dock, route and town helpers, so a
## terminal or route here is shaped by the same rules as a generated one. Rule
## checks start a real Simulation on it without generating a whole map.

const SEED := 7
const HALF_SIZE := 900.0
const ISLAND_RADIUS := 210.0

var map: MapData
var terrain: Terrain


static func build(towns := 2) -> TinyRegion:
	var region := TinyRegion.new()
	var gen := MapGenerator.new()
	gen.rng.seed = SEED
	var map := MapData.new()
	map.map_seed = SEED
	map.half_size = HALF_SIZE
	gen.map = map
	gen.terrain = Terrain.new(SEED, HALF_SIZE)
	var centers := [Vector2(-420.0, 0.0), Vector2(420.0, 0.0)]
	if towns == 3:
		centers = [Vector2(-360.0, 210.0), Vector2(360.0, 210.0), Vector2(0.0, -420.0)]
	var names := ["West Landing", "East Landing", "North Landing"]
	for i in centers.size():
		var isl := gen._new_island(centers[i], ISLAND_RADIUS, 1.0, true)
		isl.name = names[i]
		isl.population = 2600
		gen.terrain.stamp_island(isl.center, isl.radius, isl.strength)
	gen.terrain.finalize()
	# One town per island, each with its terminal open (ids match the islands').
	gen._make_towns()
	for t in map.towns:
		t.population = 2600
		t.has_dock = true
		t.built = true
	var middle := Vector2.ZERO
	for c: Vector2 in centers:
		middle += c / centers.size()
	for isl in map.towns:
		var toward := middle - isl.center if towns == 3 else -isl.center
		if not gen._find_dock(isl, toward.normalized(), []):
			push_error("TinyRegion: no dock site on %s" % isl.name)
			return null
	for a in map.towns.size():
		for b in range(a + 1, map.towns.size()):
			var r := MapData.Route.new()
			r.id = map.routes.size()
			r.key = "link-%s-%s" % [map.towns[a].key, map.towns[b].key]
			r.a = a
			r.b = b
			map.routes.append(r)
			map.towns[a].add_route_slip(r.id)
			map.towns[b].add_route_slip(r.id)
	for isl in map.towns:
		isl.lot_half_width = maxf(36.0, (isl.slips.size() - 1) * Layout.SLIP_SPACING * 0.5 + 15.0)
		gen._add_slip_zones(isl)
	for r in map.routes:
		var a := map.towns[r.a]
		var b := map.towns[r.b]
		# Each route keeps out of the others' slips and berths, as on a generated map.
		r.curve = gen._route_curve(a.dock_center(r.id), a.dock_dir, b.dock_center(r.id), b.dock_dir, r.id)
		if r.curve == null:
			push_error("TinyRegion: no clear route %s to %s" % [a.name, b.name])
			return null
		r.length = r.curve.get_baked_length()
	gen._flatten_terminals()
	gen._layout_towns()
	region.map = map
	region.terrain = gen.terrain
	return region


## A running Simulation on this region, added under `parent`.
func start(parent: Node) -> Simulation:
	var sim := Simulation.new(VehicleFactory.create, Models.mid_slip)
	sim.name = "Simulation"
	parent.add_child(sim)
	sim.setup(map, terrain)
	return sim
