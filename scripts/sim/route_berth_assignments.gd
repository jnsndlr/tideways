class_name RouteBerthAssignments
extends RefCounted
## Balances a town's routes between working slips and moves them when boats are clear.

var terminal: Terminal
var town: MapData.Town
var sim: Simulation
var _pending := {}
var _groups := []


func _init(owner: Terminal) -> void:
	terminal = owner
	town = owner.town
	sim = owner.sim


func has_moves() -> bool:
	return not _pending.is_empty()


## Gives routes that share a working slip with another a slip of their own where
## one is free and big enough for their boats. A route only moves if a boat sails
## it; a boat that calls here on two legs keeps both on one slip. The move waits
## until no boat on it is under way or alongside here (apply_when_clear).
func plan() -> void:
	_pending.clear()
	_groups.clear()
	var working: Array[int] = []
	for i in town.slips.size():
		if not town.slips[i].tie_up and not town.slips[i].building:
			working.append(i)
	if working.size() < 2:
		return
	var calls := {}
	for i in working:
		calls[i] = 0
	_groups = _route_groups()
	var busy := []
	for g in _groups:
		if g.any(func(rid): return sim.map.routes[rid].in_service):
			busy.append(g)
			calls[_slip_of(g[0])] = calls.get(_slip_of(g[0]), 0) + 1
	while true:
		var best_g: Array = []
		var best_i := -1
		var best_score := INF
		for g in busy:
			var at := _slip_of(g[0])
			if calls.get(at, 0) <= 1:
				continue
			var side := _departure_side(g)
			for i in working:
				if i == at or calls[i] + 1 >= calls[at] or not _group_fits(g, i) or terminal.slip_shut(i):
					continue
				# The emptiest slip, on the side the route heads off to.
				var score: float = calls[i] * 10.0 - side * signf(town.slip_offset(i) - town.slip_offset(at))
				if score < best_score:
					best_score = score
					best_g = g
					best_i = i
		if best_i < 0:
			break
		calls[_slip_of(best_g[0])] -= 1
		calls[best_i] += 1
		for rid in best_g:
			if town.slip_index(rid) == best_i:
				_pending.erase(rid)
			else:
				_pending[rid] = best_i


## Which slip route `rid` calls at here, or will once it has moved.
func _slip_of(rid: int) -> int:
	return _pending.get(rid, town.slip_index(rid))


## The routes calling here in groups that must share a slip: a boat that comes in
## on one and leaves on another (a multi-stop schedule) joins them.
func _route_groups() -> Array:
	var parent := {}
	for rid in town.route_ids():
		parent[rid] = rid
	var find := func(rid: int) -> int:
		while parent[rid] != rid:
			rid = parent[rid]
		return rid
	for f in sim.ferries:
		for plan in [[f.stops, f.legs], [f.next_stops, f.itinerary.pending.legs]]:
			var stops: Array = plan[0]
			var legs: Array = plan[1]
			if legs.size() != stops.size():
				continue
			for i in stops.size():
				if stops[i] != town.id:
					continue
				var a: int = legs[(i - 1 + legs.size()) % legs.size()].id
				var b: int = legs[i].id
				if parent.has(a) and parent.has(b):
					parent[find.call(a)] = find.call(b)
	var groups := {}
	for rid in parent:
		var r: int = find.call(rid)
		if not groups.has(r):
			groups[r] = []
		groups[r].append(rid)
	return groups.values()


## Whether every boat sailing a route in `g` fits slip `i`.
func _group_fits(g: Array, i: int) -> bool:
	for f in sim.ferries:
		for r in f.legs + f.itinerary.pending.legs:
			if r.id in g and not town.slips[i].fits(f.fc.size):
				return false
	return true


## Which way (+1 / -1 across the slips, about 0 straight out) the routes of `g` head.
func _departure_side(g: Array) -> float:
	var total := 0.0
	for rid in g:
		var r := sim.map.routes[rid]
		var s := minf(400.0, r.length * 0.4)
		var p := r.curve.sample_baked(s if r.a == town.id else r.length - s)
		total += (p - town.dock_center(rid)).normalized().dot(town.lateral())
	return total / maxf(g.size(), 1)


## Moves each group of routes waiting for another slip once no boat on them is
## under way or at this terminal. A route whose new end would run over land stays.
func apply_when_clear() -> void:
	for g in _groups:
		var moving: Array = g.filter(func(rid): return _pending.has(rid))
		if moving.is_empty():
			continue
		var clear := true
		for f in sim.ferries:
			if f.route.id in g and (f.state == Ferry.State.SAILING or f.here() == terminal):
				clear = false
		if not clear:
			continue
		var curves := {}
		for rid in moving:
			var to: int = _pending[rid]
			var c := _reaimed_curve(sim.map.routes[rid], town.slip_offset(to) - town.slip_offset(town.slip_index(rid)))
			if c == null:
				push_warning("%s: route %d can't move to slip %d (land in the way)" % [town.name, rid, to])
				curves.clear()
				break
			curves[rid] = c
		if curves.is_empty():
			for rid in moving:
				_pending.erase(rid)
			continue
		for rid in moving:
			var to: int = _pending[rid]
			_apply(rid, to, curves[rid])
		if sim.marine:
			sim.marine.refresh_corridors()
		sim.routes_changed.emit()


## Route `r`'s curve with its end here moved `dv` across the slips: straight out of
## the new slip for Terminal.REAIM_HOLD, then easing back onto the old line. Null if that
## would take it over land or the route is too short to ease back.
func _reaimed_curve(r: MapData.Route, dv: float) -> Curve3D:
	var blend := minf(Terminal.REAIM_BLEND, r.length - Terminal.REAIM_HOLD - 200.0)
	if blend < 120.0:
		return null
	var pts := r.curve.get_baked_points()
	var from_here := r.a == town.id
	if not from_here:
		pts.reverse()
	var shift := town.lateral() * dv
	var out := PackedVector3Array()
	var d := 0.0
	for k in pts.size():
		if k > 0:
			d += pts[k].distance_to(pts[k - 1])
		var w := 1.0 - smoothstep(Terminal.REAIM_HOLD, Terminal.REAIM_HOLD + blend, d)
		var p := pts[k] + shift * w
		if w > 0.0 and d > 36.0 and k + 1 < pts.size():
			var side := Vector3.UP.cross((pts[k + 1] - pts[k]).normalized()) * 18.0
			for o: Vector3 in [Vector3.ZERO, side, -side]:
				if sim.terrain.height_v(p + o) > -3.6:
					return null
		out.append(p)
	if not from_here:
		out.reverse()
	var c := Curve3D.new()
	c.bake_interval = r.curve.bake_interval
	for p in out:
		c.add_point(p)
	return c


## Moves route `rid` to slip `to` here at once (a boat too big for its slip was
## given it). False if its new end would run over land.
func move_now(rid: int, to: int) -> bool:
	var from := town.slip_index(rid)
	if from == to:
		return true
	var c := _reaimed_curve(sim.map.routes[rid], town.slip_offset(to) - town.slip_offset(from))
	if c == null:
		return false
	_apply(rid, to, c)
	return true


func _apply(rid: int, to: int, curve: Curve3D) -> void:
	var from := town.slip_index(rid)
	_pending.erase(rid)
	town.slips[from].routes.erase(rid)
	town.slips[to].routes.append(rid)
	terminal.slip_v[rid] = town.slip_offset(to)
	if terminal.slip_ramps[to]:
		terminal.ramps[rid] = terminal.slip_ramps[to]
	else:
		terminal.ramps.erase(rid)
	var route := sim.map.routes[rid]
	route.curve = curve
	route.length = curve.get_baked_length()
	sim.working_slips.moved(town, route, from, to)
	for ferry in sim.ferries:
		ferry.route_reshaped(route)
