class_name MarineClearance
extends RefCounted
## Moving-vessel clearance, hull queries and the stationary-vessel index.

# Kept between hulls (their capsules already stand a little proud of the hulls).
const MARGIN := 1.2
# Radar-style give way (path-following vessels): any higher-ranked vessel within
# CPA_RANGE whose closest point of approach comes inside CPA_KEEP (plus both hulls)
# within CPA_HORIZON seconds makes the lower one slow, letting it pass ahead (so
# it passes astern of it), down to a stop if it has to.
const CPA_RANGE := 400.0
const CPA_HORIZON := 90.0
const CPA_KEEP := 40.0
const CPA_FACTORS := [1.0, 0.7, 0.45, 0.25, 0.1, 0.0]
# Held up this long without making way, a vessel stops giving way to paths and
# CPAs (only hulls still count) for STUCK_GO seconds and works its own way out.
const STUCK_AFTER := 8.0
const STUCK_GO := 10.0

# Rebuilt each frame before the vessels move (_update_clearances): the vessels
# under way, and the still ones (at a berth, at anchor) bucketed by where they lie,
# so a check against hulls nearby needn't look at every boat in every marina.
const STILL_CELL := 64.0
var _movers: Array[Vessel] = []
var _still := {}  # Vector2i cell -> Array[Vessel] lying (partly) in it
var _still_reach := 0.0  # the most any still hull reaches from its centre
var _grid_built := false


## The smallest gap between `v`'s hull, were its centre at `p` heading along `h`
## (unit), and any other hull.
func hull_gap(vessels: Array[Vessel], v: Vessel, p: Vector2, h: Vector2) -> float:
	var a := p - h * v.half_seg
	var b := p + h * v.half_seg
	var best := INF
	var look := v.half_seg + v.hull_radius + 6.0
	var near: Array = (
		vessels
		if not _grid_built
		else _movers + _still_in(Rect2(p, Vector2.ZERO).grow(look + _still_reach + 8.0))
	)
	for o: Vessel in near:
		if o == v or not is_instance_valid(o) or Vessel.paired(v, o):
			continue
		var q := o.pos2()
		var r := look + o.half_seg + o.hull_radius
		if absf(q.x - p.x) > r or absf(q.y - p.y) > r:
			continue
		var oh := o.heading2() * o.half_seg
		best = minf(best, segment_distance(a, b, q - oh, q + oh) - v.hull_radius - o.hull_radius)
	return best


## The hull at a run of poses along a vessel's path: its current pose, then every
## `claim_step` ahead up to `look`, each as a capsule segment (a[k] → b[k]) with
## the distance its centre has to go to get there.
class Claim:
	var a := PackedVector2Array()
	var b := PackedVector2Array()
	var ds := PackedFloat32Array()
	var box := Rect2()

	func _init(v: Vessel, look: float) -> void:
		var pts := PackedVector2Array()
		var d := 0.0
		while true:
			pts.append(v.ahead(d))
			ds.append(d)
			if d >= look:
				break
			d = minf(d + v.claim_step, look)
		var h0 := v.heading2()
		for k in pts.size():
			var h := h0
			if k > 0 and not v.crabbing():
				var t := pts[mini(k + 1, pts.size() - 1)] - pts[k - 1]
				if t.length_squared() > 1e-6:
					# Either way along the hull: keep the pose's ends where they were.
					h = t.normalized() * signf(t.normalized().dot(h0) + 1e-3)
			a.append(pts[k] - h * v.half_seg)
			b.append(pts[k] + h * v.half_seg)
		box = Rect2(a[0], Vector2.ZERO)
		for k in a.size():
			box = box.expand(a[k]).expand(b[k])

	func size() -> int:
		return a.size()


func update(vessels: Array[Vessel], dt: float) -> void:
	var hulls := {}
	var own := {}
	var shown := {}
	for v in vessels:
		if v.wants_to_move():
			var left := v.path_left()
			var mine := Claim.new(v, minf(v.self_look(), left))
			own[v] = mine
			hulls[v] = mine
			var sl := minf(v.shown_look(), left)
			if sl > 1.5:
				shown[v] = Claim.new(v, sl)
		else:
			hulls[v] = Claim.new(v, 0.0)
	_bucket(vessels, hulls, own)
	for v in vessels:
		v.clear = INF
		v.cpa_cap = INF
		v.blocker = null
		v.blocked_by_hull = false
		if not own.has(v):
			v.stuck_t = 0.0
			continue
		# Stuck breaker: barely moving while it wants to, for long enough.
		if v.go_t > 0.0:
			v.go_t -= dt
		elif v.speed < 0.4 and not v.resting() and v.path_left() > 20.0 and v.hold > 20.0:
			v.stuck_t += dt
			if v.stuck_t > STUCK_AFTER:
				v.stuck_t = 0.0
				v.go_t = STUCK_GO
		else:
			v.stuck_t = 0.0
		var asserting := v.go_t > 0.0
		var mine: Claim = own[v]
		# Still hulls only count through the hull check, so only those near enough
		# to touch need looking at; every one under way may cross its path.
		var others: Array = (
			_movers + _still_in(mine.box.grow(v.hull_radius + _still_reach + MARGIN))
		)
		for o: Vessel in others:
			if o == v or Vessel.paired(v, o):
				continue
			var thr := v.hull_radius + o.hull_radius + MARGIN
			var reach := mine.box.grow(thr)
			var hull: Claim = hulls[o]
			if reach.intersects(hull.box):
				var k := _first_hit(mine, hull.a[0], hull.b[0], thr)
				if k > 0:
					_limit(v, o, mine.ds[k - 1], true)
			# Never wait on one that is waiting on you: get out of its way instead.
			# (A vessel steering its own way keeps out of others' paths itself.)
			if asserting:
				continue
			if o.rank > v.rank and not v.free_nav and o.wants_to_move() and not o.waits_for(v):
				_cpa_give_way(v, o)
			if o.rank > v.rank and not v.free_nav and shown.has(o) and not o.waits_for(v):
				var theirs: Claim = shown[o]
				if (
					not reach.grow(1.5).intersects(theirs.box)
					or _touches(mine.a[0], mine.b[0], theirs, thr)
				):
					continue
				for j in theirs.size():
					var k2 := _first_hit(mine, theirs.a[j], theirs.b[j], thr + 1.5, false)
					if k2 > 0:
						_limit(v, o, mine.ds[k2 - 1], false)


func _bucket(vessels: Array[Vessel], hulls: Dictionary, own: Dictionary) -> void:
	_movers.clear()
	_still.clear()
	_still_reach = 0.0
	for v in vessels:
		if own.has(v):
			_movers.append(v)
			continue
		_still_reach = maxf(_still_reach, v.half_seg + v.hull_radius)
		var box: Rect2 = (hulls[v] as Claim).box
		var c0 := Vector2i((box.position / STILL_CELL).floor())
		var c1 := Vector2i((box.end / STILL_CELL).floor())
		for x in range(c0.x, c1.x + 1):
			for y in range(c0.y, c1.y + 1):
				var k := Vector2i(x, y)
				if not _still.has(k):
					_still[k] = []
				_still[k].append(v)
	_grid_built = true


## The still vessels lying in the cells `box` touches (one may come up twice).
func _still_in(box: Rect2) -> Array:
	var out := []
	var c0 := Vector2i((box.position / STILL_CELL).floor())
	var c1 := Vector2i((box.end / STILL_CELL).floor())
	for x in range(c0.x, c1.x + 1):
		for y in range(c0.y, c1.y + 1):
			var k := Vector2i(x, y)
			if _still.has(k):
				out.append_array(_still[k])
	return out


## Its velocity as a radar would read it; one wanting to get going is reckoned
## to be about to, along its path.
static func _vel(v: Vessel, sp: float) -> Vector2:
	var d := v.ahead(6.0) - v.pos2()
	var h := d.normalized() if d.length_squared() > 1e-4 else v.heading2()
	return h * sp


## Closest point of approach of two tracks: [time, distance].
static func cpa(p: Vector2, vp: Vector2, q: Vector2, vq: Vector2) -> Vector2:
	var r := q - p
	var w := vq - vp
	var ww := w.length_squared()
	var t := 0.0 if ww < 1e-6 else clampf(-r.dot(w) / ww, 0.0, CPA_HORIZON)
	return Vector2(t, (r + w * t).length())


## `v` gives way to `o`: the fastest of CPA_FACTORS of its speed that keeps the
## CPA open (slowing lets `o` cross ahead), capped on v.cpa_cap.
func _cpa_give_way(v: Vessel, o: Vessel) -> void:
	var p := v.pos2()
	var q := o.pos2()
	var reach := CPA_RANGE + v.half_seg + o.half_seg
	if p.distance_squared_to(q) > reach * reach:
		return
	var need := CPA_KEEP + v.hull_radius + o.hull_radius + v.half_seg + o.half_seg
	var vq := _vel(o, maxf(o.speed, o.cruise * 0.4))
	var base := maxf(v.speed, v.cruise * 0.6)
	var now := cpa(p, _vel(v, base), q, vq)
	if now.y >= need or now.x <= 0.0:
		return
	for f: float in CPA_FACTORS:
		var c := cpa(p, _vel(v, base * f), q, vq)
		if c.y >= need or c.x <= 0.0:
			if base * f < v.cpa_cap:
				v.cpa_cap = base * f
				if f < 1.0 and v.clear > 30.0:
					v.blocker = o
			return
	v.cpa_cap = 0.0
	v.blocker = o


func _limit(v: Vessel, o: Vessel, c: float, by_hull: bool) -> void:
	if c < v.clear:
		v.clear = c
		v.blocker = o
		v.blocked_by_hull = by_hull


## First pose (from 1) in `mine` within `thr` of the segment c → d, or -1. With
## `closing`, a pose only counts if it is also nearer than the current one, so a
## vessel already too close to something can always move away from it.
static func _first_hit(mine: Claim, c: Vector2, d: Vector2, thr: float, closing := true) -> int:
	var sbox := Rect2(c, Vector2.ZERO).expand(d).grow(thr)
	var now := segment_distance(mine.a[0], mine.b[0], c, d) if closing else INF
	for k in range(1, mine.size()):
		if not sbox.intersects(Rect2(mine.a[k], Vector2.ZERO).expand(mine.b[k])):
			continue
		var dk := segment_distance(mine.a[k], mine.b[k], c, d)
		if dk < thr and dk < now - 0.03:
			return k
	return -1


## True if the segment a → b comes within `thr` of any pose in `other`.
static func _touches(a: Vector2, b: Vector2, other: Claim, thr: float) -> bool:
	for j in other.size():
		if segment_distance(a, b, other.a[j], other.b[j]) < thr:
			return true
	return false


static func segment_distance(a: Vector2, b: Vector2, c: Vector2, d: Vector2) -> float:
	if Geometry2D.segment_intersects_segment(a, b, c, d) != null:
		return 0.0
	return minf(minf(_pt_seg(a, c, d), _pt_seg(b, c, d)), minf(_pt_seg(c, a, b), _pt_seg(d, a, b)))


static func _pt_seg(p: Vector2, a: Vector2, b: Vector2) -> float:
	return p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b))
