class_name SlipGuides
extends Node3D
## Contact geometry in the slip frame (x across, z out to sea), and the compression
## of each fender and wing wall. Ferries press the contacts independently.

signal fitted
signal compression_changed

const LIE_SWING := deg_to_rad(2.0)
const INNER_REACH := 0.55
# Each wing wall stands this far clear of the landed end of the widest hull the slip
# takes, so a landing off the centre of the slip rides it.
const WALL_CLEAR := 0.3
const WALL_ANGLES := Vector2i(14, 60)   # the splays (degrees off the centreline) a wall may take
# Its corner stands just off the apron's side (6.55 m out), so the bow nestles in.
const WALL_V_MIN := 6.9
# How quickly the parts ease to their targets (per second).
const EASE := 2.5
# From the fender face to the dolphin centre, and the height of its deck.
const DOLPHIN_FACE := 3.5
const DOLPHIN_DECK := 4.17
# Longitudinal fender centres, in order from one end of each dolphin to the other.
const INNER_FENDERS: Array[float] = [-1.1, 1.1]
const OUTER_FENDERS: Array[float] = [-3.3, -1.1, 1.1, 3.3]


class Fender:
	var side := 1.0
	var u := 0.0          # along the slip, at the fender's middle
	var face := 0.0       # lateral offset of its face from the slip's centreline (|v|)
	var target := 0.0
	var squish := 0.0


class Wall:
	var side := 1.0
	var a := Vector3.ZERO   # ends of its fendered face (slip frame, y = 0)
	var b := Vector3.ZERO
	var target := 0.0
	var squish := 0.0


var v := 0.0
var size := 0
var fenders: Array[Fender] = []
var walls: Array[Wall] = []
# Deck tops of the inner and outer dolphins, in the slip frame.
var inner_caps: Array[Vector3] = []
var outer_caps: Array[Vector3] = []
var slip_to_world := Transform3D.IDENTITY


func _init(slip_v: float, terminal_xform: Transform3D) -> void:
	name = "SlipGuides"
	v = slip_v
	position.x = slip_v
	slip_to_world = terminal_xform * Transform3D(Basis.IDENTITY, position)


## Fits the contacts to the widest ferry this slip receives.
func fit(s: int) -> void:
	if s == size:
		return
	size = s
	fenders.clear()
	walls.clear()
	inner_caps.clear()
	outer_caps.clear()
	var inner_u := _slip_inner_u(s)
	var inner := _slip_face_v(s, inner_u)
	var outer := _slip_face_v(s, Layout.DOLPHIN_OUTER.x)
	var line := _wall_line(FerryClass.of(s))
	for side: float in [-1.0, 1.0]:
		var wall := Wall.new()
		wall.side = side
		wall.a = Vector3(side * line[0].y, 0, line[0].x)
		wall.b = Vector3(side * line[1].y, 0, line[1].x)
		walls.append(wall)
		inner_caps.append(_add_dolphin(side, inner_u, inner, INNER_FENDERS))
		outer_caps.append(_add_dolphin(side, Layout.DOLPHIN_OUTER.x, outer, OUTER_FENDERS))
	fitted.emit()


func _add_dolphin(side: float, u: float, face: float, offsets: Array[float]) -> Vector3:
	var cap := Vector3(side * (face + DOLPHIN_FACE), DOLPHIN_DECK, u)
	for offset in offsets:
		var fender := Fender.new()
		fender.side = side
		fender.u = (cap + Vector3.BACK * (side * offset)).z
		fender.face = face
		fenders.append(fender)
	return cap


func _process(delta: float) -> void:
	var k := minf(1.0, delta * EASE)
	var moved := false
	for f in fenders:
		if absf(f.target - f.squish) > 0.001:
			f.squish = lerpf(f.squish, f.target, k)
			moved = true
	for w in walls:
		if absf(w.target - w.squish) > 0.001:
			w.squish = lerpf(w.squish, w.target, k)
			moved = true
	if moved:
		compression_changed.emit()


## Where along the slip (u) a slip of `size`'s inner dolphins stand: INNER_REACH of the
## way down its widest hull from her landed end, where her sides run full, but never
## further out than DOLPHIN_INNER (the big boats' slips).
static func _slip_inner_u(size: int) -> float:
	var fc := FerryClass.of(size)
	var end_u := SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	return minf(Layout.DOLPHIN_INNER.x, end_u + INNER_REACH * 2.0 * fc.half_length)


## Lateral offset of the fender face of a slip of `size`'s dolphin at `u` along it: on
## the side of its widest hull, landed and swung LIE_SWING about her landed end (past
## her far end, on the line her side makes). A slip takes every boat from the one
## after the next slip size down's largest up to `size`, so the face clears the
## widest of them there (the medium slip's Issaquah stands wider than its Evergreen).
static func _slip_face_v(size: int, u: float) -> float:
	var smallest := 1
	for largest: int in MapData.Slip.LARGEST_BOAT:
		if largest < size:
			smallest = maxi(smallest, largest + 1)
	var v := -INF
	for s in range(smallest, size + 1):
		v = maxf(v, _hull_face_v(s, u))
	return v


static func _hull_face_v(size: int, u: float) -> float:
	var fc := FerryClass.of(size)
	var arm := u - SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	var hw := fc.half_width_at(-fc.half_length + arm)
	if hw <= 0.0:
		hw = fc.half_beam
	return hw * cos(LIE_SWING) + arm * sin(LIE_SWING)


## The starboard wing wall's face (its ends, u and v off the centreline) fitted to the
## landed end of a `fc` hull lying straight in the slip, the way slips' wing walls hug
## their ferries' bows: from Layout.WING_WALL's first u, splayed whichever of
## WALL_ANGLES follows her outline most closely, WALL_CLEAR off her where it comes
## nearest, its corner in by the apron (WALL_V_MIN) unless her bow is too bluff for it.
static func _wall_line(fc: FerryClass) -> Array[Vector2]:
	var u0: float = (Layout.WING_WALL[0] as Vector2).x
	var length := Layout.WING_LENGTH
	var end_u := SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	var hull: Array[Vector2] = []
	var k := 0.2
	while k < 30.0:
		var hw := fc.half_width_at(-fc.half_length + k)
		if hw > 0.0:
			hull.append(Vector2(end_u + k, hw))
		k += 0.5
	var best: Array[Vector2] = [Vector2(u0, (Layout.WING_WALL[0] as Vector2).y), Layout.WING_WALL[1]]
	var snuggest := INF
	var nearest_v0 := INF
	for deg in range(WALL_ANGLES.x, WALL_ANGLES.y + 1):
		var a := deg_to_rad(deg)
		var dir := Vector2(cos(a), sin(a))
		var n := Vector2(sin(a), -cos(a))     # towards the centreline
		var span: Array[Vector2] = []
		for q in hull:
			if q.x >= u0 and q.x <= u0 + length * dir.x:
				span.append(q)
		if span.is_empty():
			continue
		# Clearance of a point is (q - w0).n: its own part plus v0 * cos(a).
		var nearest := INF
		for q in span:
			nearest = minf(nearest, (q - Vector2(u0, 0.0)).dot(n))
		var v0 := maxf(WALL_V_MIN, (WALL_CLEAR - nearest) / cos(a))
		var mean := 0.0
		for q in span:
			mean += (q - Vector2(u0, v0)).dot(n)
		mean /= span.size()
		# The corner in nearest the apron first, then the splay that follows her closest.
		if v0 < nearest_v0 - 0.01 or (v0 < nearest_v0 + 0.01 and mean < snuggest):
			nearest_v0 = v0
			snuggest = mean
			best = [Vector2(u0, v0), Vector2(u0, v0) + dir * length]
	return best
