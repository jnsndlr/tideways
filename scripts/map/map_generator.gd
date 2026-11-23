class_name MapGenerator
extends RefCounted
## Procedurally lays out an archipelago: a mainland rim, inhabited islands, ferry
## terminals and routes between them, small islets, and town roads.

const NAMES := ["Pinehurst", "Northpoint", "Driftwood", "Harborview", "Seaglass Isle", "Lumber Bay",
	"Cedar Island", "Westcove", "Southgate", "Sunset Point", "Orca Point", "Madrona", "Kelp Harbor",
	"Heron Key", "Fox Island", "Bramble Bay", "Stillwater", "Gull Rock", "Alder Cove", "Tern Island"]

var rng := RandomNumberGenerator.new()
var terrain: Terrain
var map: MapData
var _route_samples := PackedVector3Array()
var _slip_zones: Array = []   # [shore, dock_dir, lateral, slip offset, route ids, lateral min, lateral max]
## When set, terminals and links come from it instead of being planned.
var _scenario: Scenario
## The layout's docks are locked by hand (MapLayout.locked_docks): terminals go
## only at those, never at a spot picked to face the links.
var _locked := false
## Where routes planned for this layout and scenario are kept (empty: plan every
## time). Planning round islands is slow, and the authored map never changes
## unless its islands are moved, so Play loads its routes from here; a stale or
## missing file is planned afresh and rewritten on a desktop run.
var route_cache_path := ""
var _planner: RoutePlanner
var _memo := preload("res://scripts/map/route_memo.gd").new()
var _cancel_mutex := Mutex.new()
var _cancelled := false

const DOCK_MIN_ANGLE := deg_to_rad(35.0)   # no two docks face within this of each other
const ISLAND_GAP := 360.0
const RELIEF_RADIUS := 175.0  # islands rise this many metres per RELIEF_RADIUS of stamp, whatever their size
const QUAY_DEPTH := -8.7      # the shallowest water a fish quay's boats come and go through
const MAX_SPREAD := deg_to_rad(160.0)  # widest arc of neighbours one terminal serves
const MIN_CROSSING := 270.0    # dock to dock, so a ferry has room to line up both ends
const MAX_DETOUR := 1.6       # route length over the dock-to-dock distance
const MAX_TURN := deg_to_rad(200.0)    # total heading change along a route
## How far a route keeps off land in open water (150 m; 0.3 mi was wider than
## the authored map's channels). Near a terminal it
## tapers in: none extra out to CLEARANCE_TAPER_FROM from the dock, then
## CLEARANCE_SLOPE metres more per metre further out, up to this.
const LAND_CLEARANCE := 150.0
const CLEARANCE_TAPER_FROM := 150.0
const CLEARANCE_SLOPE := 1.0
## Where no route keeps the full clearance, these fractions of it are tried in
## turn before the old rule (just afloat, 18 m either side).
const CLEARANCE_STEPS := [1.0, 0.6, 0.3]
## Bump when the planner changes, so saved routes are planned again.
const ROUTE_PLANNER_VERSION := 4


## Called by the scene before joining its worker. A cancelled generator is discarded.
func cancel() -> void:
	_cancel_mutex.lock()
	_cancelled = true
	_cancel_mutex.unlock()


func _should_stop() -> bool:
	_cancel_mutex.lock()
	var stopped := _cancelled
	_cancel_mutex.unlock()
	return stopped


## A random map: rolls a layout from `map_seed`, then builds it.
func generate(map_seed: int) -> MapData:
	return generate_from(roll_layout(map_seed, NAMES))


## Builds the map an authored layout describes: its islands as given, and the
## mainland, islets, routes, towns and the rest from its world seed. With a
## `scenario`, only its terminals are built and only its scheduled stops linked.
func generate_from(layout: MapLayout, scenario: Scenario = null) -> MapData:
	_build(layout, scenario)
	if _should_stop():
		map = null
		terrain = null
	return map


func _build(layout: MapLayout, scenario: Scenario) -> void:
	if _should_stop():
		return
	_scenario = scenario
	_locked = layout.locked_docks()
	_planner = null
	_route_samples.clear()
	_memo.load_for(route_cache_path, "" if route_cache_path.is_empty() else _route_cache_key(layout, scenario))
	var map_seed := layout.world_seed
	rng.seed = map_seed
	map = MapData.new()
	map.map_seed = map_seed
	terrain = Terrain.new(map_seed, map.half_size)
	var ports: Array[Vector2] = []
	for spec in layout.islands:
		if spec.mainland:
			ports.append(Vector2(spec.x, spec.z))
	terrain.set_mainland_ports(ports, _should_stop)
	if _should_stop():
		return
	_place_mainland()
	for spec in layout.islands:
		_island_from_spec(spec)
	for isl in map.islands:
		if _should_stop():
			return
		terrain.stamp(stamp_of(isl), _should_stop)
	terrain.finalize(_should_stop)
	if _should_stop():
		return
	_make_towns()
	_plan_routes()
	if _should_stop():
		return
	_memo.save()
	_place_islets()
	terrain.finalize(_should_stop)
	if _should_stop():
		return
	_place_marinas(map_seed)
	_place_quays(map_seed)
	_place_station(map_seed)
	if _should_stop():
		return
	_flatten_terminals()
	_place_beaches(map_seed)
	_name_islands()
	_layout_towns()
	_roll_wildlife_appeal(map_seed)
	_place_haul_outs(map_seed)


func _new_island(center: Vector2, radius: float, strength: float, inhabited: bool) -> MapData.Island:
	var isl := MapData.Island.new()
	isl.id = map.islands.size()
	isl.key = "island-%d" % isl.id
	isl.center = center
	isl.radius = radius
	isl.strength = strength
	isl.inhabited = inhabited
	map.islands.append(isl)
	return isl


func _island_from_spec(spec: MapLayout.IslandSpec) -> MapData.Island:
	var isl := _new_island(Vector2.ZERO, 0.0, 0.0, true)
	apply_spec(isl, spec)
	return isl


## Copies a layout entry onto its island. An island's `radius` is how far it can
## reach (its long axis); its stamp's own radius is that over the stretch.
static func apply_spec(isl: MapData.Island, spec: MapLayout.IslandSpec) -> void:
	var st := maxf(spec.stretch, 1.0)
	isl.name = spec.name
	isl.center = Vector2(spec.x, spec.z)
	isl.radius = spec.radius * st
	isl.strength = spec.height * spec.radius / RELIEF_RADIUS
	isl.shape_seed = spec.shape_seed
	isl.stretch = st
	isl.angle = deg_to_rad(spec.angle)
	isl.roughness = spec.roughness
	isl.hills = spec.hills
	isl.peak = spec.peak
	isl.lakes = spec.lakes
	isl.forest = spec.forest
	isl.fields = spec.fields
	isl.mainland_port = spec.mainland
	isl.ferry = spec.ferry
	isl.dock_sites.clear()
	for d in spec.docks:
		var site := MapData.DockSite.new()
		site.key = "%s/%d" % [isl.key, isl.dock_sites.size()]
		var at := spec.dock_at(d)
		var dir := spec.dock_heading(d)
		site.shore = Vector3(at.x, 0.0, at.y)
		site.dir = Vector3(dir.x, 0.0, dir.y)
		site.tier = d.tier
		site.town = d.town
		isl.dock_sites.append(site)


static func stamp_of(isl: MapData.Island) -> Terrain.Stamp:
	var s := Terrain.Stamp.new()
	s.island_id = isl.id
	s.center = isl.center
	s.radius = isl.radius / isl.stretch
	s.strength = isl.strength
	s.stretch = isl.stretch
	s.angle = isl.angle
	s.roughness = isl.roughness
	s.hills = isl.hills
	s.peak = isl.peak
	s.lakes = isl.lakes
	s.offset = Terrain.shape_offset(isl.shape_seed) if isl.shape_seed != 0 else isl.center
	return s


## The mainland's masses round the map's edge (x, z, radius), from the world seed
## alone, so they stay put whatever the islands do.
static func mainland_masses(world_seed: int, half_size: float) -> Array[Vector3]:
	var r := RandomNumberGenerator.new()
	r.seed = world_seed * 7 + 3
	var out: Array[Vector3] = []
	var count := r.randi_range(4, 6)
	var start := r.randf() * TAU
	var axis := Mainland.new(world_seed, half_size).axis
	for k in count:
		var ang := start + TAU * k / count + r.randf_range(-0.25, 0.25)
		var dist := r.randf_range(half_size + 400.0, half_size + 890.0)
		var m := Vector3(cos(ang) * dist, sin(ang) * dist, r.randf_range(1190.0, 1580.0))
		# Only on the mainland's shores: the channel's open ends stay open water.
		var across := absf(m.y) if axis == 0 else absf(m.x)
		var along := absf(m.x) if axis == 0 else absf(m.y)
		if across >= along:
			out.append(m)
	return out


func _place_mainland() -> void:
	for m in mainland_masses(map.map_seed, map.half_size):
		# Only where the shore comes into the map: a side with no port is all Backdrop.
		if not terrain.mainland.has_port(m.x, m.y):
			continue
		var isl := _new_island(Vector2(m.x, m.y), m.z, 1.3, false)
		isl.is_mainland = true


# --- Rolling layouts --------------------------------------------------------------------

## A whole random layout: 8-11 islands (-1), one per name (-2) or `count`, named
## from `names` shuffled.
static func roll_layout(world_seed: int, names: Array, count := -1) -> MapLayout:
	var r := RandomNumberGenerator.new()
	r.seed = world_seed
	var lay := MapLayout.new()
	lay.world_seed = world_seed
	var pool := names.duplicate()
	for i in range(pool.size() - 1, 0, -1):
		var j := r.randi_range(0, i)
		var t = pool[i]
		pool[i] = pool[j]
		pool[j] = t
	if count == -1:
		count = r.randi_range(8, 11)
	elif count == -2:
		count = pool.size()
	for k in count:
		var spec := MapLayout.IslandSpec.new()
		spec.name = str(pool[k % pool.size()]) if not pool.is_empty() else "Island %d" % (k + 1)
		roll_shape(spec, r)
		# No room: try it a little smaller, and leave it out after that.
		for shrink in 6:
			if roll_position(lay, spec, r):
				lay.islands.append(spec)
				break
			spec.radius *= 0.88
	return lay


## New size, coastline, hills and cover for `spec`, leaving where it is.
static func roll_shape(spec: MapLayout.IslandSpec, r: RandomNumberGenerator) -> void:
	spec.radius = r.randf_range(450.0, 690.0)
	spec.height = r.randf_range(0.9, 1.15)
	spec.shape_seed = r.randi_range(1, 99999)
	spec.stretch = r.randf_range(1.0, 1.45)
	spec.angle = r.randf_range(0.0, 180.0)
	spec.roughness = r.randf_range(0.8, 1.2)
	spec.hills = r.randf_range(0.7, 1.3)
	spec.forest = r.randf_range(0.7, 1.2)
	spec.fields = r.randf_range(0.25, 0.6)


## Somewhere for `spec` clear of the mainland and every island in `lay` but itself
## (and any in `ignore`). False, leaving it where it was, if there's no room.
static func roll_position(lay: MapLayout, spec: MapLayout.IslandSpec, r: RandomNumberGenerator,
		ignore: Array = []) -> bool:
	var half := MapData.new().half_size
	var limit := half - 1090.0
	var masses := mainland_masses(lay.world_seed, half)
	var reach := spec.radius * maxf(spec.stretch, 1.0)
	if spec.mainland:
		return _roll_coast(lay, spec, r, ignore, masses, reach)
	for attempt in 5000:
		var c := Vector2(r.randf_range(-limit, limit), r.randf_range(-limit, limit))
		if _fits(lay, spec, c, reach, masses, ignore):
			spec.x = c.x
			spec.z = c.y
			return true
	return false


## A place against the map's edge on one of the mainland's shores, reaching past
## the edge, where it runs into the mainland's shore, clear of
## every island.
static func _roll_coast(lay: MapLayout, spec: MapLayout.IslandSpec, r: RandomNumberGenerator,
		ignore: Array, masses: Array[Vector3], reach: float) -> bool:
	var half := MapData.new().half_size
	var ml := Mainland.new(lay.world_seed, half)
	var v := half - reach * 0.3
	for attempt in 2000:
		var u := r.randf_range(-(half - reach - 300.0), half - reach - 300.0)
		var sgn := 1.0 if r.randf() < 0.5 else -1.0
		var c := Vector2(u, sgn * v) if ml.axis == 0 else Vector2(sgn * v, u)
		if _fits(lay, spec, c, reach, masses, ignore):
			spec.x = c.x
			spec.z = c.y
			return true
	return false


## Whether `spec` sits clear of everything where it is now.
static func fits(lay: MapLayout, spec: MapLayout.IslandSpec) -> bool:
	var half := MapData.new().half_size
	return _fits(lay, spec, Vector2(spec.x, spec.z), spec.radius * maxf(spec.stretch, 1.0),
		mainland_masses(lay.world_seed, half), [])


static func _fits(lay: MapLayout, spec: MapLayout.IslandSpec, c: Vector2, reach: float,
		masses: Array[Vector3], ignore: Array) -> bool:
	for m in masses:
		if spec.mainland:
			break
		if c.distance_to(Vector2(m.x, m.y)) < reach + m.z * 0.72 + 255.0:
			return false
	for o in lay.islands:
		if o == spec or ignore.has(o):
			continue
		if c.distance_to(Vector2(o.x, o.z)) < reach + o.radius * maxf(o.stretch, 1.0) + ISLAND_GAP:
			return false
	return true


## Where `o`'s terminal stands and every dock site locked on it, built or not,
## as [shore, dir, built]: islets, marinas, quays and beaches keep clear of them
## all, so buying a site in play finds it as it was left.
## Where `o`'s docks meet the shore: [shore, dir, a terminal's lot, its half width].
## On an authored map every dock site is a town's, built or not, so all count.
func _dock_spots(o: MapData.Island) -> Array:
	var out := []
	var sites := {}
	for id in o.towns:
		var t := map.towns[id]
		if t.has_dock:
			out.append([t.shore, t.dock_dir, true, t.lot_half_width])
			sites[t.site] = true
	for i in o.dock_sites.size():
		if not sites.has(i):
			out.append([o.dock_sites[i].shore, o.dock_sites[i].dir, false, 0.0])
	return out


## One town per locked dock site (an island with none gets one town with no
## dock); a generated map's islands one town each, docked where planning finds.
func _make_towns() -> void:
	map.towns.clear()
	for isl in _main_islands():
		isl.towns.clear()
		var n := isl.dock_sites.size() if _locked else 0
		for i in maxi(n, 1):
			var t := MapData.Town.new()
			t.id = map.towns.size()
			t.key = "%s/%d" % [isl.key, i]
			t.island = isl.id
			t.name = isl.name
			t.center = isl.center
			if i < n:
				var site := isl.dock_sites[i]
				t.site = i
				t.has_dock = true
				t.shore = site.shore
				t.dock_dir = site.dir
				t.center = Vector2(site.shore.x, site.shore.z)
				if not site.town.is_empty():
					t.name = site.town
				elif n > 1 and i > 0:
					t.name = "%s %d" % [isl.name, i + 1]
			map.towns.append(t)
			isl.towns.append(t.id)


## Whether town `t`'s terminal is the company's from the start.
func _owned(t: MapData.Town) -> bool:
	if _scenario:
		return _scenario.terminals.has(t.key)
	return map.islands[t.island].ferry and t.site <= 0


func _main_islands() -> Array[MapData.Island]:
	var out: Array[MapData.Island] = []
	for isl in map.islands:
		if isl.inhabited and not isl.is_mainland:
			out.append(isl)
	return out


static func _find(parent: Array, i: int) -> int:
	while parent[i] != i:
		i = parent[i]
	return i


## Picks island pairs (a spanning tree plus a few extra links), finds a dock site on
## each connected island, then keeps only routes a ferry can sail sensibly. A link
## whose route would loop round, double back or cut through another slip is
## banned and the network planned again without it, so the docks face the links
## that remain.
func _plan_routes() -> void:
	var mains: Array[MapData.Town] = []
	for t in map.towns:
		if _locked and _scenario:
			# Every dock site is planned for, owned or not, so buying one in play
			# needs nothing built (TID-319). (--full-network keeps the old
			# spanning tree over the islands' first sites.)
			if t.has_dock:
				mains.append(t)
			elif _scenario and _scenario.terminals.has(t.key):
				push_warning("%s (%s) has no dock placed in the layout, so no terminal" % [t.name, t.key])
		elif _owned(t) and (t.has_dock or not _locked):
			mains.append(t)
	var banned := {}
	while true:
		if _should_stop():
			return
		var bad := _try_routes(mains, banned)
		if _should_stop():
			return
		if bad.is_empty():
			break
		for key in bad:
			banned[key] = true
	for r in map.routes:
		_route_samples.append_array(r.curve.get_baked_points())
	for t in mains:
		t.built = t.has_dock and _owned(t)


## One planning pass with the `banned` links left out. Returns the links (as
## Vector2i of indices into `mains`) whose routes turned out not to make sense.
func _try_routes(mains: Array[MapData.Town], banned: Dictionary) -> Array:
	map.routes.clear()
	_slip_zones.clear()
	for isl in mains:
		isl.has_dock = _locked
		isl.slips.clear()
	var edges: Array = []
	for i in mains.size():
		for j in range(i + 1, mains.size()):
			var d := mains[i].center.distance_to(mains[j].center)
			# A generated network links islands in reach of each other; a scenario's
			# links are its own (_scenario_links), however far apart.
			if d < 3100.0 and not banned.has(Vector2i(i, j)):
				edges.append([d, i, j])
	edges.sort_custom(func(a, b): return a[0] < b[0])

	var parent: Array = range(mains.size())
	var degree := PackedInt32Array()
	degree.resize(mains.size())
	var bearings: Array = []
	for i in mains.size():
		bearings.append(PackedFloat32Array())
	var chosen: Array = []
	if _scenario:
		_scenario_links(mains, banned, chosen)
	for e in (edges if _scenario == null else []):
		var a: int = e[1]
		var b: int = e[2]
		if degree[a] >= 3 or degree[b] >= 3 or not _fits_terminal(mains, bearings, a, b):
			continue
		var ra := _find(parent, a)
		var rb := _find(parent, b)
		if ra != rb:
			parent[ra] = rb
			_link(mains, bearings, degree, chosen, e)
	for e in (edges if _scenario == null else []):
		var a: int = e[1]
		var b: int = e[2]
		if chosen.has(e) or e[0] > 1900.0 or degree[a] >= 2 or degree[b] >= 2 or not _fits_terminal(mains, bearings, a, b):
			continue
		if rng.randf() < 0.6:
			_link(mains, bearings, degree, chosen, e)

	# Dock sites face the average direction of each island's neighbours.
	var desired := {}
	for e in chosen:
		if e.size() > 3:
			continue   # a candidate route for the schedule editor: docks don't face it
		for pair in [[e[1], e[2]], [e[2], e[1]]]:
			var me: MapData.Town = mains[pair[0]]
			var other: MapData.Town = mains[pair[1]]
			var v: Vector2 = desired.get(me.id, Vector2.ZERO)
			desired[me.id] = v + (other.center - me.center).normalized()
	# A scenario terminal with no scheduled stop faces its nearest fellow terminal.
	if _scenario:
		for isl in mains:
			if not desired.has(isl.id):
				var near: MapData.Town = null
				for o in mains:
					if o != isl and (near == null or o.center.distance_to(isl.center) < near.center.distance_to(isl.center)):
						near = o
				desired[isl.id] = (near.center - isl.center).normalized() if near else Vector2.ZERO
	# Locked by hand (has_dock already): exactly where placed, whatever the links.
	var taken: Array[Vector3] = []
	for isl in mains:
		if desired.has(isl.id) and not _locked:
			var dir: Vector2 = desired[isl.id]
			if dir.length() < 0.1:
				dir = -isl.center if isl.center.length() > 3.0 else Vector2.RIGHT
			isl.has_dock = _find_dock(isl, dir, taken)
			if isl.has_dock:
				taken.append(isl.dock_dir)

	var bad: Array = []
	var link := {}
	var calls := {}    # island id -> the routes calling there
	for isl in mains:
		var none: Array[int] = []
		calls[isl.id] = none
	for e in chosen:
		if _should_stop():
			return []
		var a: MapData.Town = mains[e[1]]
		var b: MapData.Town = mains[e[2]]
		# No dock for it: plan again without this link, so the network goes another way.
		if not (a.has_dock and b.has_dock):
			bad.append(Vector2i(e[1], e[2]))
			continue
		# Locked docks don't turn to face their links, so the final pass below
		# is the only test their routes need (and the only one worth saving).
		var test: Curve3D = null if _locked else _route_curve(a.shore + a.dock_dir * Layout.DOCK_U, a.dock_dir, b.shore + b.dock_dir * Layout.DOCK_U, b.dock_dir)
		if not _locked and (test == null or not _route_sensible(test)):
			bad.append(Vector2i(e[1], e[2]))
			continue
		var r := MapData.Route.new()
		r.id = map.routes.size()
		r.key = "link-%s-%s" % [a.key, b.key]
		r.a = a.id
		r.b = b.id
		r.curve = test
		r.in_service = e.size() <= 3
		map.routes.append(r)
		link[r.id] = Vector2i(e[1], e[2])
		calls[a.id].append(r.id)
		calls[b.id].append(r.id)
	if not bad.is_empty():
		return bad

	for isl in mains:
		var here: Array[int] = calls[isl.id]
		if here.is_empty() and not (isl.has_dock and (_scenario or _locked)):
			isl.has_dock = false
			continue
		var lat := isl.lateral()
		here.sort_custom(func(ra, rb): return _departure_lateral(isl, ra, lat) < _departure_lateral(isl, rb, lat))
		_assign_slips(isl, here)
		isl.lane_extension_price = 150 if not here.is_empty() else 0
		isl.construction_staging_lanes = 2 if isl.working_slips() > 1 else 1
		isl.lot_half_width = maxf(36.0, (isl.working_slips() - 1) * Layout.SLIP_SPACING * 0.5 + 15.0)
		_add_slip_zones(isl)

	for r in map.routes:
		if _should_stop():
			return []
		var a := map.towns[r.a]
		var b := map.towns[r.b]
		var pa := a.dock_center(r.id)
		var pb := b.dock_center(r.id)
		# Every route keeps clear of every other slip and of land.
		r.curve = _route_curve(pa, a.dock_dir, pb, b.dock_dir, r.id)
		if r.curve == null or not (_locked or _route_sensible(r.curve)):
			bad.append(link[r.id])
			continue
		r.length = r.curve.get_baked_length()
	return bad


## Gives `isl` its slips and the routes calling there (sorted left to right by
## where they head) to them. A scenario terminal has the slips it lists, shared in
## turn by neighbouring routes; a planned network gives every route a large slip.
func _assign_slips(isl: MapData.Town, routes: Array[int]) -> void:
	isl.slips.clear()
	if _scenario == null:
		for rid in routes:
			isl.add_route_slip(rid)
		return
	for size in _scenario.slip_sizes(isl.key):
		isl.slips.append(MapData.Slip.new(size))
	for i in routes.size():
		isl.slips[floori(i * isl.slips.size() / float(routes.size()))].routes.append(routes[i])
	for size in _scenario.tie_ups.get(isl.key, []):
		isl.slips.append(MapData.Slip.new(size, true))
	# A site bought in play opens with one small slip and two paved lanes.
	isl.open_lanes = _scenario.lanes.get(isl.key, 0 if _scenario.terminals.has(isl.key) else 2)


## The scenario's scheduled links as edges ([distance, i, j] into `mains`), then
## every other pair of its terminals as a candidate ([distance, i, j, true])
## the schedule editor can put a boat on. A candidate with no sensible route is
## banned like any other link.
func _scenario_links(mains: Array[MapData.Town], banned: Dictionary, chosen: Array) -> void:
	var index := {}
	for i in mains.size():
		index[mains[i].key] = i
	var linked := {}
	for pair in _scenario.links():
		if index.has(pair[0]) and index.has(pair[1]):
			linked[Vector2i(mini(index[pair[0]], index[pair[1]]), maxi(index[pair[0]], index[pair[1]]))] = true
	for pair in _scenario.links():
		if not (index.has(pair[0]) and index.has(pair[1])):
			push_warning("Scenario links %s and %s, which are not both its terminals" % [pair[0], pair[1]])
			continue
		var i: int = mini(index[pair[0]], index[pair[1]])
		var j: int = maxi(index[pair[0]], index[pair[1]])
		if banned.has(Vector2i(i, j)):
			push_warning("No sensible route between %s and %s" % [mains[i].name, mains[j].name])
			continue
		chosen.append([mains[i].center.distance_to(mains[j].center), i, j])
	for i in mains.size():
		for j in range(i + 1, mains.size()):
			if not linked.has(Vector2i(i, j)) and not banned.has(Vector2i(i, j)):
				chosen.append([mains[i].center.distance_to(mains[j].center), i, j, true])


func _link(mains: Array[MapData.Town], bearings: Array, degree: PackedInt32Array, chosen: Array, e: Array) -> void:
	var a: int = e[1]
	var b: int = e[2]
	var ab := mains[b].center - mains[a].center
	bearings[a].append(ab.angle())
	bearings[b].append((-ab).angle())
	degree[a] += 1
	degree[b] += 1
	chosen.append(e)


## True if a single terminal on each of `a` and `b` could serve one more link
## between them: every neighbour of an island must lie within MAX_SPREAD of the
## others, so the dock faces them all rather than splitting the difference
## between opposite shores and sending ferries off the wrong way.
func _fits_terminal(mains: Array[MapData.Town], bearings: Array, a: int, b: int) -> bool:
	var ab := mains[b].center - mains[a].center
	return _spread(bearings[a], ab.angle()) <= MAX_SPREAD and _spread(bearings[b], (-ab).angle()) <= MAX_SPREAD


## The narrowest arc holding all of `angles` plus `extra`.
static func _spread(angles: PackedFloat32Array, extra: float) -> float:
	var all := angles.duplicate()
	all.append(extra)
	for i in all.size():
		all[i] = fposmod(all[i], TAU)
	all.sort()
	var widest_gap := TAU - all[all.size() - 1] + all[0]
	for i in range(1, all.size()):
		widest_gap = maxf(widest_gap, all[i] - all[i - 1])
	return TAU - widest_gap


## A route a real ferry would run: a proper crossing rather than a hop, no more
## than a little longer than the straight line, and never swinging further round
## than a U-turn and back a bit.
func _route_sensible(c: Curve3D) -> bool:
	var pts := c.get_baked_points()
	var chord := pts[0].distance_to(pts[pts.size() - 1])
	if chord < MIN_CROSSING or c.get_baked_length() > chord * MAX_DETOUR:
		return false
	var turn := 0.0
	var prev := Vector3.ZERO
	for i in range(4, pts.size(), 4):
		var h := (pts[i] - pts[i - 4]).normalized()
		if prev != Vector3.ZERO:
			turn += absf(prev.signed_angle_to(h, Vector3.UP))
		prev = h
	return turn <= MAX_TURN


## Which side the route heads off to once clear of the terminal, from its planning
## curve, so neighbouring slips' routes peel away from each other instead of crossing.
func _departure_lateral(isl: MapData.Town, route_id: int, lat: Vector3) -> float:
	if not MapData.is_route(route_id):
		return 0.0
	var r := map.routes[route_id]
	if r.curve == null:
		# Not planned yet (locked docks): which way the far dock lies will do.
		var other := map.towns[r.b if r.a == isl.id else r.a]
		return (other.shore - isl.shore).dot(lat)
	var length := r.curve.get_baked_length()
	var s := minf(RUN_IN + 180.0, length * 0.5)
	var p := r.curve.sample_baked(s if r.a == isl.id else length - s)
	return (p - isl.shore).dot(lat)


## Searches around the desired heading for a shoreline with land behind (for the
## holding lot) and open water ahead (for the slip and approach), never facing
## within DOCK_MIN_ANGLE of a dock already placed. The coast is rarely square to a
## line from the island's middle, so each landfall tries facing a little either way.
func _find_dock(town: MapData.Town, desired: Vector2, taken: Array[Vector3]) -> bool:
	var isl := map.islands[town.island]
	var base := atan2(desired.y, desired.x)
	for k in 33:
		if _should_stop():
			return false
		var ang := base + ceili(k / 2.0) * 0.1 * (1.0 if k % 2 == 1 else -1.0)
		var dir := Vector2(cos(ang), sin(ang))
		var shore := -1.0
		var r := 0.0
		while r < isl.radius * 1.8:
			var p := isl.center + dir * r
			if terrain.height_at(p.x, p.y) < 0.9:
				shore = r
				break
			r += 1.5
		if shore < 24.0:
			continue
		var s3 := Vector3(isl.center.x + dir.x * shore, 0.0, isl.center.y + dir.y * shore)
		for face: float in [0.0, 0.3, -0.3, 0.6, -0.6]:
			var n3 := Vector3(cos(ang + face), 0.0, sin(ang + face))
			var clash := false
			for t in taken:
				if n3.angle_to(t) < DOCK_MIN_ANGLE:
					clash = true
					break
			if clash or not _dock_fits(s3, n3):
				continue
			town.shore = s3
			town.dock_dir = n3
			return true
	return false


## Where a pier heading `dir` out to sea meets the shore nearest `at`: walks
## seaward from land, or back landward from the water, to the waterline.
static func snap_shore(t: Terrain, at: Vector2, dir: Vector2) -> Vector3:
	var step := dir.normalized() * 1.5
	var p := at
	if t.height_at(p.x, p.y) >= 0.9:
		for i in 400:
			if t.height_at(p.x, p.y) < 0.9:
				break
			p += step
	else:
		for i in 400:
			if t.height_at(p.x - step.x, p.y - step.y) >= 0.9:
				break
			p -= step
	return Vector3(p.x, 0.0, p.y)


## The way out to sea at `at`: straight downhill, from the ground's slope.
static func seaward(t: Terrain, at: Vector2) -> Vector2:
	var e := 30.0
	var g := Vector2(t.height_at(at.x + e, at.y) - t.height_at(at.x - e, at.y),
		t.height_at(at.x, at.y + e) - t.height_at(at.x, at.y - e))
	return -g.normalized() if g.length() > 0.001 else Vector2.RIGHT


func _dock_fits(s3: Vector3, n3: Vector3) -> bool:
	var lat := Vector3.UP.cross(n3)
	var land := 0
	for u: float in [-18.0, -36.0, -54.0, -72.0, -90.0]:
		if terrain.height_v(s3 + n3 * u) > 1.5:
			land += 1
	if land < 4:
		return false
	for u in range(18, 156, 9):
		for v: float in [-36.0, 0.0, 36.0]:
			if terrain.height_v(s3 + n3 * float(u) + lat * v) > -3.0:
				return false
	return true


# Ferries leave and enter each slip on a straight run along its centreline, long
# enough (long_run_in) that the longest hull is wholly out past the channel buoys
# before she starts to turn, so her far end can't swing into the dolphins, and turn
# no tighter than TURN_RADIUS in between. Where the coast or other slips leave no
# room, the old run-in for a 90 m hull, then a shorter one and a tighter turn are
# tried, and a wide sweep only as a last resort.
const RUN_IN := 90.0
const SHORT_RUN_IN := 66.0
const TURN_RADIUS := 96.0
const TIGHT_RADIUS := 66.0
const WIDE_RADIUS := 135.0
# Each slip's pier, guide walls and dolphins are off limits to other routes' hulls.
const ZONE_U := Layout.DOLPHIN_OUTER.x + 4.0
const HULL_HALF_BEAM := 13.5
# Half the Issaquah's hull. (The Jumbo's berth, out to ~238 m, is not kept clear:
# sizing these for her cost about a third of the links on generated maps.)
const HULL_HALF_LENGTH := 57.0
# Lateral reach of a terminal's outermost dolphins from its end slips, plus a
# little sea room.
const OUTER_DOLPHIN_CLEAR := Layout.DOLPHIN_OUTER.y + Layout.DOLPHIN_OUTER.z + 6.0


## The straight run out of a slip before the turn: the longest hull's centre runs out
## from the route's end (a 90 m hull's docked centre) until her far end clears the
## channel buoys, plus the ferry's eased helm (Ferry.YAW_EASE) starting the turn early.
static func long_run_in() -> float:
	var fc := FerryClass.of(FerryClass.MAX_SIZE)
	return Layout.CHANNEL_BUOY_U + fc.half_length + Ferry.YAW_EASE - Layout.DOCK_U


## Route from dock centre `pa` (facing out along `na`) to dock centre `pb`, or null
## if there is none. With `route_id` set it must also keep out of every slip but
## that route's own. The most direct route keeping LAND_CLEARANCE off land wins:
## a turn–straight–turn path, or failing that one round the land in the fewest
## straight legs. Where neither can, less clearance is tried (CLEARANCE_STEPS),
## then the old rule. Results are remembered (route_cache_path). A generated
## network with no scenario takes only the direct route, with no clearance.
func _route_curve(pa: Vector3, na: Vector3, pb: Vector3, nb: Vector3, route_id := -1) -> Curve3D:
	var key := "%.1f,%.1f,%.3f,%.3f|%.1f,%.1f,%.3f,%.3f|%d" % [pa.x, pa.z, na.x, na.z, pb.x, pb.z, nb.x, nb.z, route_id]
	if _memo.routes.has(key):
		return _curve_of(_memo.routes[key])
	if _scenario == null and not _locked:
		# A generated network (Sandbox) keeps to direct routes, as before.
		return _direct_curve(pa, na, pb, nb, route_id, 0.0)
	var c: Curve3D = null
	for f: float in CLEARANCE_STEPS:
		if _should_stop():
			return null
		c = _direct_curve(pa, na, pb, nb, route_id, f)
		if _should_stop():
			return null
		if c == null:
			c = _round_land_curve(pa, na, pb, nb, route_id, f)
		if c != null:
			break
	if c == null:
		c = _direct_curve(pa, na, pb, nb, route_id, 0.0)
	if _should_stop():
		return null
	# Its own points (not the baked ones), thinned to within 10 cm and rounded to
	# 1 cm so the saved routes stay small; the curve is rebuilt from them either
	# way, so a planned and a loaded route are the same.
	var flat: Array = []
	if c != null:
		var pts := PackedVector2Array()
		for i in c.point_count:
			var p := c.get_point_position(i)
			pts.append(Vector2(p.x, p.z))
		for p in _thin(pts, 0.1):
			flat.append(snappedf(p.x, 0.01))
			flat.append(snappedf(p.y, 0.01))
	_memo.remember(key, flat)
	return _curve_of(flat) if c != null else null


## `pts` with the points dropped that lie within `tolerance` of the line through
## their neighbours (Ramer–Douglas–Peucker). The ends are kept.
static func _thin(pts: PackedVector2Array, tolerance: float) -> PackedVector2Array:
	if pts.size() < 3:
		return pts
	var keep := PackedByteArray()
	keep.resize(pts.size())
	keep[0] = 1
	keep[pts.size() - 1] = 1
	var stack: Array[Vector2i] = [Vector2i(0, pts.size() - 1)]
	while not stack.is_empty():
		var span: Vector2i = stack.pop_back()
		var worst := -1
		var worst_d := tolerance
		for i in range(span.x + 1, span.y):
			var d := pts[i].distance_to(Geometry2D.get_closest_point_to_segment(pts[i], pts[span.x], pts[span.y]))
			if d > worst_d:
				worst_d = d
				worst = i
		if worst >= 0:
			keep[worst] = 1
			stack.append(Vector2i(span.x, worst))
			stack.append(Vector2i(worst, span.y))
	var out := PackedVector2Array()
	for i in pts.size():
		if keep[i]:
			out.append(pts[i])
	return out


func _curve_of(flat: Array) -> Curve3D:
	if flat.is_empty():
		return null
	var c := Curve3D.new()
	c.bake_interval = 3.0
	for i in range(0, flat.size(), 2):
		c.add_point(Vector3(flat[i], 0.0, flat[i + 1]))
	return c


## True if `c` keeps `fraction` of LAND_CLEARANCE off land (tapering in at its ends).
func _keeps_clear(c: Curve3D, fraction: float) -> bool:
	if fraction <= 0.0:
		return true
	if _planner == null:
		_planner = RoutePlanner.new(terrain, map.half_size, _should_stop)
	if _should_stop():
		return false
	var pts := c.get_baked_points()
	var a := Vector2(pts[0].x, pts[0].z)
	var b := Vector2(pts[pts.size() - 1].x, pts[pts.size() - 1].z)
	for i in range(0, pts.size(), 4):
		var p := Vector2(pts[i].x, pts[i].z)
		var need := RoutePlanner.need_at(p, a, b, LAND_CLEARANCE * fraction, CLEARANCE_TAPER_FROM, CLEARANCE_SLOPE)
		if _planner.clearance_at(p) + RoutePlanner.CELL * 0.75 < need:
			return false
	return true


## Round the land: straight out of each slip, then through the planner's fewest
## straight legs keeping `fraction` of the clearance. Each corner is passed on the
## heading halfway between its legs, and each leg is the shortest
## turn–straight–turn path at TURN_RADIUS from one corner to the next.
func _round_land_curve(pa: Vector3, na: Vector3, pb: Vector3, nb: Vector3, route_id: int, fraction: float) -> Curve3D:
	if _planner == null:
		_planner = RoutePlanner.new(terrain, map.half_size, _should_stop)
	if _should_stop():
		return null
	var h0 := Vector2(na.x, na.z).normalized()
	var h1 := -Vector2(nb.x, nb.z).normalized()
	for run: float in [long_run_in(), RUN_IN]:
		var s := Vector2(pa.x, pa.z) + h0 * run
		var g := Vector2(pb.x, pb.z) - h1 * run
		var corners := _planner.waypoints(s, g, LAND_CLEARANCE * fraction, CLEARANCE_TAPER_FROM, CLEARANCE_SLOPE, _should_stop)
		if corners.size() < 3:
			continue   # no land in the way: the direct route already had its chance
		var headings: Array[Vector2] = [h0]
		for i in range(1, corners.size() - 1):
			var mid := (corners[i] - corners[i - 1]).normalized() + (corners[i + 1] - corners[i]).normalized()
			headings.append(mid.normalized() if mid.length() > 0.01 else (corners[i + 1] - corners[i]).normalized())
		headings.append(h1)
		var pts := PackedVector2Array()
		for i in corners.size() - 1:
			var paths := _turn_paths(corners[i], headings[i], corners[i + 1], headings[i + 1], TURN_RADIUS)
			if paths.is_empty():
				pts.clear()
				break
			paths.sort_custom(func(x, y): return x[0] < y[0])
			pts.append_array(paths[0][1])
		if pts.is_empty():
			continue
		var c := _curve_from(pa, pts, pb, run)
		if _route_clear(c) and (_locked or _route_sensible(c)) and _keeps_clear(c, fraction) and (route_id < 0 or _clear_of_slips(c, route_id)):
			return c
	return null


## The shortest turn–straight–turn route (straight out of `pa`, a turn, a straight,
## a turn, straight into `pb`) clear of land and keeping `fraction` of the
## clearance; with none of that, longer runs and wider turns that at least keep
## out of other slips (only when `fraction` is 0).
func _direct_curve(pa: Vector3, na: Vector3, pb: Vector3, nb: Vector3, route_id: int, fraction: float) -> Curve3D:
	var h0 := Vector2(na.x, na.z).normalized()
	var h1 := -Vector2(nb.x, nb.z).normalized()
	# Every path for every option, scored by length plus a penalty for each
	# compromise, so a short run-in or tight turn wins over looping round.
	var candidates := []
	# The long run-in wins unless it costs more than about a loop round (2 pi
	# TURN_RADIUS, ~600 m) less 200: then the 90 m one is taken, as on short hops.
	var long := long_run_in()
	for option: Vector3 in [Vector3(long, TURN_RADIUS, 0.0), Vector3(RUN_IN, TURN_RADIUS, 400.0),
			Vector3(SHORT_RUN_IN, TURN_RADIUS, 475.0),
			Vector3(RUN_IN, TIGHT_RADIUS, 520.0), Vector3(SHORT_RUN_IN, TIGHT_RADIUS, 610.0),
			Vector3(RUN_IN, WIDE_RADIUS, 760.0)]:
		var p0 := Vector2(pa.x, pa.z) + h0 * option.x
		var p1 := Vector2(pb.x, pb.z) - h1 * option.x
		for path in _turn_paths(p0, h0, p1, h1, option.y):
			candidates.append([path[0] + option.z, path[1], option.x])
	candidates.sort_custom(func(x, y): return x[0] < y[0])
	for cand in candidates:
		if _should_stop():
			return null
		var c := _curve_from(pa, cand[1], pb, cand[2])
		# Not one that strays too far or turns too much (a long run-in can, where
		# the slips face away from each other): a shorter run-in will do instead.
		if _route_clear(c) and (_locked or _route_sensible(c)) and _keeps_clear(c, fraction) and (route_id < 0 or _clear_of_slips(c, route_id)):
			return c
	# Nothing standard keeps out of every other slip: try longer straight runs out
	# of either end and wider turns before giving up on the link.
	if route_id >= 0 and fraction <= 0.0:
		var more := []
		for ra: float in [SHORT_RUN_IN, RUN_IN, 135.0, 180.0, long, 240.0]:
			if _should_stop():
				return null
			for rb: float in [SHORT_RUN_IN, RUN_IN, 135.0, 180.0, long, 240.0]:
				for radius: float in [TIGHT_RADIUS, TURN_RADIUS, WIDE_RADIUS, 180.0]:
					var p0 := Vector2(pa.x, pa.z) + h0 * ra
					var p1 := Vector2(pb.x, pb.z) - h1 * rb
					for path in _turn_paths(p0, h0, p1, h1, radius):
						more.append([path[0] + ra + rb, path[1], ra, rb])
		more.sort_custom(func(x, y): return x[0] < y[0])
		for cand in more:
			if _should_stop():
				return null
			var c := _curve_from(pa, cand[1], pb, cand[2], cand[3])
			if _route_clear(c) and _clear_of_slips(c, route_id):
				return c
	return null


static func _left(v: Vector2) -> Vector2:
	return Vector2(-v.y, v.x)


## The four turn–straight–turn paths from pose (p0, h0) to (p1, h1) at the given
## turn radius, as [length, PackedVector2Array of points every ~6 m].
static func _turn_paths(p0: Vector2, h0: Vector2, p1: Vector2, h1: Vector2, radius: float) -> Array:
	var out := []
	for s0: float in [1.0, -1.0]:
		for s1: float in [1.0, -1.0]:
			# A point turning with sign s about centre c has position c - s·R·left(h).
			var c0 := p0 + _left(h0) * s0 * radius
			var c1 := p1 + _left(h1) * s1 * radius
			var d := c1 - c0
			var k := (s1 - s0) * radius
			var dl2 := d.length_squared() - k * k
			if dl2 < 1e-4:
				continue
			var straight := sqrt(dl2)
			var t := d.rotated(-atan2(k, straight)).normalized()
			var a0 := fposmod(s0 * (t.angle() - h0.angle()), TAU)
			var a1 := fposmod(s1 * (h1.angle() - t.angle()), TAU)
			var pts := PackedVector2Array()
			_arc(pts, c0, h0, s0, radius, a0)
			var q0 := c0 - _left(t) * s0 * radius
			var q1 := c1 - _left(t) * s1 * radius
			var steps := maxi(1, ceili(straight / 6.0))
			for i in steps:
				pts.append(q0.lerp(q1, float(i) / steps))
			_arc(pts, c1, t, s1, radius, a1)
			pts.append(p1)
			out.append([radius * (a0 + a1) + straight, pts])
	return out


static func _arc(pts: PackedVector2Array, c: Vector2, h: Vector2, sgn: float, radius: float, angle: float) -> void:
	var steps := ceili(radius * angle / 6.0)
	for i in steps:
		var hh := h.rotated(sgn * angle * i / steps)
		pts.append(c - _left(hh) * sgn * radius)


## Straight out of `pa` for `run_in`, along `mid`, and straight into `pb` for
## `run_out` (the same as `run_in` if not given).
func _curve_from(pa: Vector3, mid: PackedVector2Array, pb: Vector3, run_in: float, run_out := -1.0) -> Curve3D:
	var c := Curve3D.new()
	c.bake_interval = 3.0
	var a2 := Vector2(pa.x, pa.z)
	var b2 := Vector2(pb.x, pb.z)
	var steps := ceili(run_in / 6.0)
	for i in steps:
		var q := a2.lerp(mid[0], float(i) / steps)
		c.add_point(Vector3(q.x, 0.0, q.y))
	for q in mid:
		c.add_point(Vector3(q.x, 0.0, q.y))
	steps = ceili((run_in if run_out < 0.0 else run_out) / 6.0)
	for i in range(1, steps + 1):
		var q := mid[mid.size() - 1].lerp(b2, float(i) / steps)
		c.add_point(Vector3(q.x, 0.0, q.y))
	return c


func _route_clear(c: Curve3D) -> bool:
	var length := c.get_baked_length()
	var s := 36.0
	while s < length - 36.0:
		var p := c.sample_baked(s)
		var q := c.sample_baked(minf(s + 3.0, length))
		var lat := Vector3.UP.cross((q - p).normalized()) * 18.0
		for o: Vector3 in [Vector3.ZERO, lat, -lat]:
			if terrain.height_v(p + o) > -3.6:
				return false
		s += 9.0
	return true


## Marks `isl`'s slips off limits to other routes (_clear_of_slips).
func _add_slip_zones(isl: MapData.Town) -> void:
	var lat := isl.lateral()
	var last := isl.slips.size() - 1
	for i in isl.slips.size():
		# Slips butt up against each other; the end ones reach out past their
		# outer dolphins.
		var lo := -(OUTER_DOLPHIN_CLEAR if i == 0 else Layout.SLIP_SPACING * 0.5)
		var hi := OUTER_DOLPHIN_CLEAR if i == last else Layout.SLIP_SPACING * 0.5
		_slip_zones.append([isl.shore, isl.dock_dir, lat, isl.slip_offset(i), isl.slips[i].routes, lo, hi])


## True if the hull, swept along `c`, never enters another route's slip.
func _clear_of_slips(c: Curve3D, route_id: int) -> bool:
	var length := c.get_baked_length()
	var s := 0.0
	while s <= length:
		var p := c.sample_baked(s)
		var t := c.sample_baked(minf(s + 3.0, length)) - c.sample_baked(maxf(s - 3.0, 0.0))
		t.y = 0.0
		t = t.normalized()
		var side := Vector3.UP.cross(t)
		for z in _slip_zones:
			if route_id in z[4]:
				continue
			var rel: Vector3 = p - z[0]
			# Cheap reject: nowhere near this terminal.
			var u: float = rel.dot(z[1])
			var reach := HULL_HALF_LENGTH + 6.0
			if u > ZONE_U + reach or u < Layout.LOT_FRONT - reach or absf(rel.dot(z[2]) - z[3]) > Layout.SLIP_SPACING + reach:
				continue
			for along: float in [-HULL_HALF_LENGTH, -HULL_HALF_LENGTH * 0.5, 0.0, HULL_HALF_LENGTH * 0.5, HULL_HALF_LENGTH]:
				for across: float in [-HULL_HALF_BEAM, 0.0, HULL_HALF_BEAM]:
					var q := rel + t * along + side * across
					var qu: float = q.dot(z[1])
					var qv: float = q.dot(z[2]) - z[3]
					if qu < ZONE_U and qu > Layout.LOT_FRONT and qv > z[5] and qv < z[6]:
						return false
		s += 6.0
	return true


## Small rocky islets for scenery, kept away from shipping lanes and docks.
func _place_islets() -> void:
	var target := rng.randi_range(24, 40)
	var placed := 0
	var limit := map.half_size - 120.0
	for attempt in 3000:
		if _should_stop():
			return
		if placed >= target:
			break
		var r := rng.randf_range(30.0, 78.0)
		var c := Vector2(rng.randf_range(-limit, limit), rng.randf_range(-limit, limit))
		var ok := true
		for o in map.islands:
			var reach := o.radius * (0.72 if o.is_mainland else 1.0)
			if c.distance_to(o.center) < r + reach + 30.0:
				ok = false
				break
			for sp in _dock_spots(o):
				if c.distance_to(Vector2(sp[0].x, sp[0].z)) < r + 150.0:
					ok = false
			if not ok:
				break
		if ok:
			for p in _route_samples:
				if Vector2(p.x, p.z).distance_to(c) < r * 1.25 + 42.0:
					ok = false
					break
		if ok:
			var isl := _new_island(c, r, rng.randf_range(0.85, 1.0), false)
			terrain.stamp_island(isl.center, isl.radius, isl.strength, isl.id)
			placed += 1


## A small-boat marina on most inhabited islands: a stretch of shore with land
## behind, deep water out past the T-head and its approach, and well clear of the
## ferry terminals, their lanes and each other. Its own RNG, so the rest of the
## map stays the same for a given seed.
func _place_marinas(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 17 + 3
	for isl in _main_islands():
		if _should_stop():
			return
		if r.randf() > 0.85:
			continue
		var sites: Array = []
		var start := r.randf() * TAU
		for k in 32:
			var ang := start + TAU * k / 32.0
			var site: Variant = _marina_site(isl, Vector3(cos(ang), 0.0, sin(ang)))
			if site != null:
				sites.append(site)
		if sites.is_empty():
			continue
		var pick: Array = sites[r.randi_range(0, sites.size() - 1)]
		var m := MapData.Marina.new()
		m.id = map.marinas.size()
		m.island = isl.id
		m.shore = pick[0]
		m.dir = pick[1]
		map.marinas.append(m)


## [shore, dir] if a marina fits where the ray from the island's centre along `dir`
## meets the sea, else null.
func _marina_site(isl: MapData.Island, n3: Vector3) -> Variant:
	var c := Vector3(isl.center.x, 0.0, isl.center.y)
	var shore := -1.0
	var rr := 0.0
	while rr < isl.radius * 1.8:
		if terrain.height_v(c + n3 * rr) < 0.9:
			shore = rr
			break
		rr += 1.5
	if shore < 24.0:
		return null
	var s3 := c + n3 * shore
	if _h(s3 - n3 * 12.0) < 0.9 or _h(s3 - n3 * 24.0) < 1.5:
		return null
	var lat := Vector3.UP.cross(n3)
	if _h(s3 + n3 * 18.0) > -0.9:
		return null
	for u in range(36, 150, 12):
		for v: float in [-33.0, -15.0, 0.0, 15.0, 33.0]:
			if _h(s3 + n3 * float(u) + lat * v) > -6.0:
				return null
	var reach := s3 + n3 * Layout.MARINA_APPROACH_U
	for o in map.islands:
		for sp in _dock_spots(o):
			if s3.distance_to(sp[0]) < 240.0 or reach.distance_to(sp[0] + sp[1] * 120.0) < 240.0:
				return null
	for m in map.marinas:
		if s3.distance_to(m.shore) < 180.0:
			return null
	for u: float in [0.0, 45.0, 90.0, 135.0]:
		var q := s3 + n3 * u
		# Baked about 3 m apart; every few is plenty at this distance.
		for i in range(0, _route_samples.size(), 4):
			var p := _route_samples[i]
			if Vector2(p.x - q.x, p.z - q.z).length_squared() < 102.0 * 102.0:
				return null
	return [s3, n3]


## A fish quay on a few islands, for the fishing boats to work from: a stretch of
## shore with land behind and deep water along its face and the lane off it, well
## clear of terminals, marinas, ferry routes and each other. Its own RNG, so the
## rest of the map stays the same for a given seed.
func _place_quays(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 23 + 9
	var islands := _main_islands()
	for i in range(islands.size() - 1, 0, -1):
		var j := r.randi_range(0, i)
		var t := islands[i]
		islands[i] = islands[j]
		islands[j] = t
	# Most maps get one; now and then a second.
	var want := 2 if r.randf() < 0.35 else 1
	for isl in islands:
		if _should_stop():
			return
		if map.quays.size() >= want:
			break
		var sites: Array = []
		var start := r.randf() * TAU
		for k in 36:
			var ang := start + TAU * k / 36.0
			var site: Variant = _quay_site(isl, Vector3(cos(ang), 0.0, sin(ang)))
			if site != null:
				sites.append(site)
		if sites.is_empty():
			continue
		var pick: Array = sites[r.randi_range(0, sites.size() - 1)]
		var q := MapData.FishQuay.new()
		q.id = map.quays.size()
		q.island = isl.id
		q.shore = pick[0]
		q.dir = pick[1]
		q.side = 1.0 if r.randf() < 0.5 else -1.0
		map.quays.append(q)


## [shore, dir] if a fish quay fits where the ray from the island's centre along
## `dir` meets the sea, else null.
func _quay_site(isl: MapData.Island, n3: Vector3, marina_gap := 180.0) -> Variant:
	var c := Vector3(isl.center.x, 0.0, isl.center.y)
	var shore := -1.0
	var rr := 0.0
	while rr < isl.radius * 1.8:
		if terrain.height_v(c + n3 * rr) < 0.9:
			shore = rr
			break
		rr += 1.5
	if shore < 24.0:
		return null
	var s3 := c + n3 * shore
	var lat := Vector3.UP.cross(n3)
	for v: float in [-18.0, 0.0, 18.0]:
		if _h(s3 - n3 * 15.0 + lat * v) < 1.2:
			return null
	# The wharf stands over the water (or the foreshore), not dug into the hill.
	var wv := -Layout.QUAY_HALF
	while wv <= Layout.QUAY_HALF:
		if _h(s3 + n3 * (Layout.QUAY_JETTY_END - 6.0) + lat * wv) > 1.8:
			return null
		wv += 12.0
	# Deep enough for a trawler along the face, the lane and the runs either side.
	for u in range(int(Layout.QUAY_FACE_U) + 6, int(Layout.QUAY_LANE_U) + 42, 12):
		var v := -Layout.QUAY_RUN - 24.0
		while v <= Layout.QUAY_RUN + 24.0:
			if _h(s3 + n3 * float(u) + lat * v) > QUAY_DEPTH:
				return null
			v += 18.0
	var reach := s3 + n3 * Layout.QUAY_LANE_U
	for o in map.islands:
		for sp in _dock_spots(o):
			if s3.distance_to(sp[0]) < 180.0 or reach.distance_to(sp[0] + sp[1] * 120.0) < 195.0:
				return null
	for m in map.marinas:
		if s3.distance_to(m.shore) < marina_gap or reach.distance_to(m.at(Layout.MARINA_APPROACH_U, 0.0)) < marina_gap - 15.0:
			return null
	for q in map.wharves():
		if s3.distance_to(q.shore) < 480.0:
			return null
	for u: float in [0.0, Layout.QUAY_LANE_U]:
		for v: float in [-Layout.QUAY_RUN, 0.0, Layout.QUAY_RUN]:
			var p := s3 + n3 * u + lat * v
			for i in range(0, _route_samples.size(), 4):
				var rp := _route_samples[i]
				if Vector2(rp.x - p.x, rp.z - p.z).length_squared() < 102.0 * 102.0:
					return null
	return [s3, n3]


## The pilot station, where the pilot boats and tugs that meet the ships are
## based: a wharf like a fish quay, on the island whose shore faces furthest out
## towards the edges of the map (where the ships come in), if one has room. Its
## own RNG, so the rest of the map stays the same for a given seed.
func _place_station(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 29 + 5
	var best: Array = []
	var best_score := -INF
	# (Its boats come and go a lot: well away from the marinas, if it can be.)
	for gap: float in [390.0, 270.0, 180.0]:
		if not best.is_empty():
			break
		for isl in _main_islands():
			if _should_stop():
				return
			var start := r.randf() * TAU
			for k in 36:
				var ang := start + TAU * k / 36.0
				var site: Variant = _quay_site(isl, Vector3(cos(ang), 0.0, sin(ang)), gap)
				if site == null:
					continue
				var reach: Vector3 = site[0] + site[1] * Layout.QUAY_LANE_U
				# Out towards an edge, looking out to sea.
				var out := maxf(absf(reach.x), absf(reach.z))
				var score := out + 360.0 * Vector2(site[1].x, site[1].z).dot(Vector2(reach.x, reach.z).normalized()) \
						+ r.randf() * 120.0
				if score > best_score:
					best_score = score
					best = [isl, site]
	if best.is_empty():
		return
	var st := MapData.PilotStation.new()
	st.id = map.stations.size()
	st.island = best[0].id
	st.shore = best[1][0]
	st.dir = best[1][1]
	st.side = 1.0 if r.randf() < 0.5 else -1.0
	map.stations.append(st)


func _flatten_terminals() -> void:
	for isl in map.towns:
		if not isl.has_dock:
			continue
		var hw := isl.lot_half_width
		terrain.add_flat(isl.shore, isl.dock_dir, Layout.LOT_BACK - 6.0, Layout.LOT_FRONT + 3.0,
			-hw - Layout.LANE_WIDTH - 4.5, hw + 33.0, Layout.LOT_Y - 0.15, 21.0)
	terrain.apply_flats()


## Sandy beaches cut into the shore: one beside each town's ferry lot (two where the
## lot has no expansion site reserved on its left), one beside some of the marinas,
## and a few more along each island's gentler shores. Before the towns are laid out,
## so their roads stop at the sand. Its own RNG, so the rest of the map stays the
## same for a given seed.
func _place_beaches(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 31 + 17
	var cut: Array[Vector3] = []
	for isl in map.towns:
		if not isl.has_dock:
			continue
		var hw := isl.lot_half_width
		var sides: Array[float] = [1.0]
		if isl.lane_extension_price <= 0:
			sides.append(-1.0)
		for side in sides:
			var half_w := r.randf_range(48.0, 66.0)
			# Past the lot's flat and its blend (Layout: +33 / -11.7, 21 m blend).
			var edge := hw + 33.0 if side > 0.0 else hw + Layout.LANE_WIDTH + 4.5
			# Stepping further along if the shore just past the lot won't take one.
			for step in 4:
				var v := side * (edge + 15.0 + half_w + step * 30.0)
				if _try_beach(isl.shore + isl.lateral() * v, isl.dock_dir, half_w, r, cut, true):
					break
	for m in map.marinas:
		if r.randf() < 0.35:
			continue
		var side := 1.0 if r.randf() < 0.5 else -1.0
		var half_w := r.randf_range(33.0, 45.0)
		_try_beach(m.at(0.0, side * (Layout.MARINA_HEAD_HALF + 36.0 + half_w)), m.dir, half_w, r, cut, true)
	for isl in _main_islands():
		var want := r.randi_range(1, 3)
		var a0 := r.randf() * TAU
		for k in 16:
			if want <= 0:
				break
			var a := a0 + k * TAU / 16.0 + r.randf_range(-0.15, 0.15)
			var d := Vector3(cos(a), 0.0, sin(a))
			var c := Vector3(isl.center.x, 0.0, isl.center.y)
			if _try_beach(c + d * isl.radius, d, r.randf_range(36.0, 66.0), r, cut, false):
				want -= 1


## Cuts a beach near `at` facing about `out` if the shore there will take one: land
## behind it that isn't a tall cliff, and clear of the harbours and the other
## beaches. `beside`: placed on purpose next to a lot or marina, so it may be closer.
func _try_beach(at: Vector3, out: Vector3, half_w: float, r: RandomNumberGenerator,
		cut: Array[Vector3], beside: bool) -> bool:
	var s3 := snap_shore(terrain, Vector2(at.x, at.z), Vector2(out.x, out.z))
	var sw := seaward(terrain, Vector2(s3.x, s3.z))
	var n3 := Vector3(sw.x, 0.0, sw.y)
	# Facing out to sea, not running along a headland.
	if n3.dot(out) < (0.2 if beside else 0.4):
		return false
	if _h(s3 - n3 * 30.0) < 2.5 or _h(s3 - n3 * 30.0) > 16.0 or _h(s3 + n3 * 30.0) > -1.0:
		return false
	var gap := half_w + 30.0
	var bound := map.half_size - 120.0
	if absf(s3.x) > bound or absf(s3.z) > bound:
		return false
	for o in map.islands:
		for sp in _dock_spots(o):
			if s3.distance_to(sp[0]) < (sp[3] + 24.0 + half_w if beside and sp[2] else 260.0):
				return false
	for m in map.marinas:
		if s3.distance_to(m.shore) < (Layout.MARINA_HEAD_HALF + 30.0 + half_w if beside else 170.0):
			return false
	for q in map.wharves():
		if s3.distance_to(q.shore) < Layout.QUAY_HALF + 40.0 + half_w:
			return false
	for p in cut:
		if s3.distance_to(p) < gap + 90.0:
			return false
	terrain.carve_beach(s3, n3, half_w, r.randf_range(33.0, 45.0), r.randf_range(30.0, 38.0))
	cut.append(s3)
	var b := MapData.Beach.new()
	b.shore = s3
	b.dir = n3
	b.half_width = half_w
	b.beside = beside
	map.beaches.append(b)
	return true


## Names come from the layout; population and growth are rolled.
func _name_islands() -> void:
	for isl in _main_islands():
		isl.population = int(rng.randf_range(900.0, 6500.0) / 10.0) * 10
		isl.growth = rng.randf_range(-0.5, 4.5)
		# Split evenly across its towns (service growth will grow the one served).
		for id in isl.towns:
			map.towns[id].population = int(isl.population / float(isl.towns.size()) / 10.0) * 10


## Some islands are wildlife hotspots, most are middling, a few rarely see any.
## Its own RNG, so the rest of the map stays the same for a given seed.
func _roll_wildlife_appeal(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 31 + 7
	for isl in _main_islands():
		var tier := r.randf()
		if tier < 0.25:
			isl.wildlife_appeal = r.randf_range(2.0, 3.2)
		elif tier < 0.75:
			isl.wildlife_appeal = r.randf_range(0.7, 1.4)
		else:
			isl.wildlife_appeal = r.randf_range(0.2, 0.5)


## Where seals and sea lions haul out: a few pocket beaches cut into quiet
## shores, a few low rock ledges off rocky ones (islets first), and the marinas'
## floats. All well away from the ferries' docks and lanes, the wharves and each
## other. Its own RNG, so the rest of the map stays the same for a given seed.
func _place_haul_outs(map_seed: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = map_seed * 37 + 13
	var beaches: Array = []
	var rocks: Array = []
	for isl in map.islands:
		if _should_stop():
			return
		if isl.is_mainland:
			continue
		var c := Vector3(isl.center.x, 0.0, isl.center.y)
		var start := r.randf() * TAU
		for k in 40:
			var ang := start + TAU * k / 40.0
			var n3 := Vector3(cos(ang), 0.0, sin(ang))
			var rr := 0.0
			var shore := -1.0
			while rr < isl.radius * 1.8:
				if _h(c + n3 * rr) < 0.0:
					shore = rr
					break
				rr += 0.5
			if shore < 9.0:
				continue
			var s3 := c + n3 * shore
			var g := Vector3(_h(s3 + Vector3.RIGHT) - _h(s3 - Vector3.RIGHT), 0.0,
				_h(s3 + Vector3.BACK) - _h(s3 - Vector3.BACK))
			var out := -g.normalized() if g.length_squared() > 1e-4 else n3
			if out.dot(n3) < 0.5 or not _haul_clear(s3, 210.0):
				continue
			var lat := Vector3.UP.cross(out)
			# Deep water off it to swim in from, and no other shore just across.
			var open := true
			for u: float in [24.0, 42.0, 66.0]:
				for v: float in [-18.0, 0.0, 18.0]:
					if _h(s3 + out * u + lat * v) > -6.0:
						open = false
			if not open:
				continue
			var islet := not isl.inhabited
			if not islet and _h(s3 - out * 30.0) > 3.0:
				# A beach wants a bit of a bay: land running on out either side.
				var bay := 0.0
				for side: float in [-1.0, 1.0]:
					var q := s3 + lat * side * 48.0
					var rq := -18.0
					while rq < 30.0 and _h(q + out * rq) > 0.0:
						rq += 3.0
					bay += rq
				beaches.append([bay + r.randf() * 18.0, isl, s3, out])
			if _h(s3 - out * 9.0) > 3.6:
				rocks.append([(90.0 if islet else 0.0) + r.randf() * 30.0, isl, s3, out])
	beaches.sort_custom(func(a, b): return a[0] > b[0])
	rocks.sort_custom(func(a, b): return a[0] > b[0])
	var want_beaches := r.randi_range(2, 4)
	for b: Array in beaches:
		if want_beaches <= 0:
			break
		if _haul_clear(b[2], 210.0) and _beach_site(b[1], b[2], b[3], r):
			want_beaches -= 1
	var want_rocks := r.randi_range(3, 5)
	for b: Array in rocks:
		if want_rocks <= 0:
			break
		if _haul_clear(b[2], 210.0):
			_rock_site(b[1], b[2], b[3], r)
			want_rocks -= 1
	for m in map.marinas:
		_dock_site(m)


## Clear of the ferries, their lanes, the wharves, marinas and other haul-outs.
func _haul_clear(p: Vector3, gap: float) -> bool:
	var bound := map.half_size - 90.0
	if absf(p.x) > bound or absf(p.z) > bound:
		return false
	for o in map.islands:
		for sp in _dock_spots(o):
			if p.distance_to(sp[0]) < 270.0:
				return false
	for m in map.marinas:
		if p.distance_to(m.shore) < 135.0 or p.distance_to(m.at(Layout.MARINA_APPROACH_U, 0.0)) < 120.0:
			return false
	for q in map.wharves():
		if p.distance_to(q.shore) < 180.0 or p.distance_to(q.at(Layout.QUAY_LANE_U, 0.0)) < 210.0:
			return false
	for h in map.haul_outs:
		if p.distance_to(h.water) < gap + 60.0:
			return false
	for i in range(0, _route_samples.size(), 4):
		var rp := _route_samples[i]
		if Vector2(rp.x - p.x, rp.z - p.z).length_squared() < 120.0 * 120.0:
			return false
	return true


func _new_haul_out(kind: MapData.HaulOut.Kind, isl: MapData.Island, at: Vector3, out: Vector3) -> MapData.HaulOut:
	var h := MapData.HaulOut.new()
	h.id = map.haul_outs.size()
	h.kind = kind
	h.island = isl.id
	h.out = out
	h.water = Vector3(at.x, 0.0, at.z) + out * 48.0
	var best := INF
	for o in _main_islands():
		var d := Vector2(at.x, at.z).distance_to(o.center) - o.radius
		if d < best:
			best = d
			h.near = o.id
	return h


## Cuts a pocket beach at `s3` and lays out spots up it in rows; false if the
## slope didn't come out gentle enough to lie on.
func _beach_site(isl: MapData.Island, s3: Vector3, out: Vector3, r: RandomNumberGenerator) -> bool:
	var half_w := r.randf_range(27.0, 39.0)
	terrain.carve_beach(s3, out, half_w, r.randf_range(21.0, 27.0), r.randf_range(27.0, 33.0))
	var h := _new_haul_out(MapData.HaulOut.Kind.BEACH, isl, s3, out)
	var lat := Vector3.UP.cross(out)
	var v := -half_w * 0.5
	while v <= half_w * 0.5:
		# Where the water's edge is along this line, now.
		var line := s3 + lat * v
		var e := -30.0
		while e < 36.0 and _h(line + out * e) > 0.0:
			e += 0.25
		var edge := line + out * e
		for row in 3:
			# Rows staggered, so those going further up pass between the ones below.
			var at := edge - out * (1.6 + row * 2.1) + lat * ((row % 2) * 1.15 + r.randf_range(-0.3, 0.3))
			var y := _h(at)
			if y < 0.1 or y > 1.3:
				continue
			var sp := MapData.HaulSpot.new()
			sp.at = Vector3(at.x, y, at.z)
			sp.edge = Vector3(edge.x, 0.0, edge.z)
			sp.entry = sp.edge + out * 5.0
			sp.yaw = atan2(out.x, out.z) + r.randf_range(-0.5, 0.5)
			h.spots.append(sp)
		v += 2.3
	if h.spots.size() < 5:
		return false
	map.haul_outs.append(h)
	return true


## A low flat slab of rock on the waterline off a rocky shore, its back into the bank.
func _rock_site(isl: MapData.Island, s3: Vector3, out: Vector3, r: RandomNumberGenerator) -> void:
	var lat := Vector3.UP.cross(out)
	var size := Vector3(r.randf_range(6.5, 9.5), 2.6, r.randf_range(4.0, 5.0))
	var h := _new_haul_out(MapData.HaulOut.Kind.ROCK, isl, s3, out)
	h.top = r.randf_range(0.35, 0.55)
	var c := s3 + out * (size.z * 0.5 - 1.2)
	h.ledge = Transform3D(Basis(lat, Vector3.UP, out), Vector3(c.x, h.top, c.z))
	h.ledge_size = size
	var x := -size.x * 0.5 + 1.1
	while x <= size.x * 0.5 - 1.0:
		for z: float in [size.z * 0.5 - 1.3, size.z * 0.5 - 3.0]:
			var at := c + lat * (x + (0.0 if z > size.z * 0.5 - 2.0 else 0.95) + r.randf_range(-0.2, 0.2)) + out * z
			if _h(at) > h.top - 0.1:
				continue
			var sp := MapData.HaulSpot.new()
			sp.at = Vector3(at.x, h.top, at.z)
			sp.edge = Vector3(at.x, h.top, at.z) + out * (size.z * 0.5 - 0.3 - z)
			sp.entry = Vector3(sp.edge.x, 0.0, sp.edge.z) + out * 3.0
			sp.yaw = atan2(out.x, out.z) + r.randf_range(-0.7, 0.7)
			sp.big = z > size.z * 0.5 - 2.0
			h.spots.append(sp)
		x += 1.9
	map.haul_outs.append(h)


## The ends of a marina's T-head float: sea lions climb out over the end, past
## the berths, and lie along it.
func _dock_site(m: MapData.Marina) -> void:
	var hu := Layout.MARINA_HEAD_U
	var hh := Layout.MARINA_HEAD_HALF
	var isl := map.islands[m.island]
	var h := _new_haul_out(MapData.HaulOut.Kind.DOCK, isl, m.at(hu, 0.0), m.dir)
	h.marina = m.id
	h.top = 0.65
	h.water = m.at(hu - 3.0, 0.0)
	h.water.y = 0.0
	for side: float in [-1.0, 1.0]:
		var entry := m.at(hu, side * (hh + 7.5))
		if _h(entry) > -3.6:
			continue
		h.water = m.at(hu + 3.0, side * (hh + 18.0))
		h.water.y = 0.0
		# Innermost first, so those coming after needn't climb over the ones lying there.
		for uv: Vector2 in [Vector2(-0.45, hh - 4.3), Vector2(0.45, hh - 2.9), Vector2(-0.45, hh - 1.5)]:
			var sp := MapData.HaulSpot.new()
			sp.at = m.at(hu + uv.x, side * uv.y)
			sp.at.y = h.top
			var edge := m.at(hu + uv.x, side * (hh - 0.4))
			sp.edge = Vector3(edge.x, h.top, edge.z)
			sp.entry = Vector3(entry.x, 0.0, entry.z)
			var along := m.lateral() * side
			sp.yaw = atan2(along.x, along.z)
			h.spots.append(sp)
	if not h.spots.is_empty():
		map.haul_outs.append(h)


func _h(p: Vector3) -> float:
	return terrain.height_v(p)


## Main road from the lot entrance inland to a town centre, plus a cross street.
func _layout_towns() -> void:
	# Where each town sits, then smooth ground around it, then its roads.
	for isl in map.towns:
		if _should_stop():
			return
		if isl.has_dock:
			var nd := isl.dock_dir
			var e := isl.shore + nd * Layout.LOT_BACK
			var dist := 48.0
			while dist > 12.0:
				var p := e - nd * dist
				if _h(p) > 3.9 and _h(p - nd * 24.0) > 3.9:
					break
				dist -= 6.0
			isl.town_center = e - nd * dist
			isl.town_axis = isl.lateral()
		else:
			# A town with no dock: settle on the highest ground near the centre.
			var c := map.islands[isl.island].center
			var best := Vector3(c.x, 0.0, c.y)
			for k in 24:
				var p := Vector3(c.x + rng.randf_range(-150, 150), 0.0, c.y + rng.randf_range(-150, 150))
				if _h(p) > _h(best):
					best = p
			isl.town_center = best
			var a := rng.randf() * TAU
			isl.town_axis = Vector3(cos(a), 0.0, sin(a))
		# Out past where the houses thin out (world_builder's town spread).
		var town_r := sqrt(isl.population / 90.0) * 9.0
		terrain.smooth_town(isl.town_center, town_r * 1.4 + 20.0, 45.0)
	# Cut a shoulder for the ticket lanes after locating the towns. Keep hillside
	# terrain below the outer booth and taper the cut back into the access road.
	for isl in map.towns:
		if isl.has_dock:
			terrain.add_flat(isl.shore, isl.dock_dir, Layout.LOT_BACK - Layout.TICKET_FAN_LENGTH,
				Layout.LOT_BACK, -18.5, 5.5, Layout.LOT_Y - 0.15, 12.0)
	terrain.apply_flats()  # the ferry lots stay exactly level
	for isl in map.towns:
		if isl.has_dock:
			var nd := isl.dock_dir
			var t := isl.lateral()
			var e := isl.shore + nd * Layout.LOT_BACK
			var tc := isl.town_center
			isl.road_main_a = _road_line(e, tc, t)
			var far := 0.0
			while far < 48.0 and _h(tc - nd * (far + 6.0)) > 3.9:
				far += 6.0
			if far >= 12.0:
				isl.road_main_b = _road_line(tc, tc - nd * far, t)
			for side: float in [-1.0, 1.0]:
				var length := 0.0
				while length < 72.0 and _h(tc + t * side * (length + 6.0)) > 3.9:
					length += 6.0
				if length >= 18.0:
					isl.road_cross.append(_road_line(tc, tc + t * side * length, nd))
		isl.town_center.y = _h(isl.town_center)
		isl.label_pos = isl.town_center + Vector3(0, 48, 0)


func _road_line(a: Vector3, b: Vector3, lat: Vector3) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var count := maxi(1, ceili(a.distance_to(b) / 6.0))
	for i in count + 1:
		var p := a.lerp(b, float(i) / count)
		p.y = maxf(_h(p), maxf(_h(p + lat * 5.1), _h(p - lat * 5.1))) + 0.66
		pts.append(p)
	return pts


## All geometry and scenario inputs that affect the saved route curves.
static func _route_cache_key(layout: MapLayout, scenario: Scenario) -> String:
	var scenario_key := [] if scenario == null else [scenario.terminals, scenario.slips, scenario.tie_ups, Array(scenario.links()).map(func(l): return Array(l))]
	var inputs := [ROUTE_PLANNER_VERSION, LAND_CLEARANCE, CLEARANCE_TAPER_FROM, CLEARANCE_SLOPE, CLEARANCE_STEPS, layout.to_json(), scenario_key]
	return str(hash(JSON.stringify(inputs)))
