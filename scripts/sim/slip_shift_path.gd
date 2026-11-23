class_name SlipShiftPath
## Geometry of one manoeuvre between a working slip and a tie-up.

## Water between her hull end and the channel buoys before she turns.
const SHIFT_MARGIN := 15.0
## How far out from the slips she backs before moving along to the other slip.
const SHIFT_OUT := 70.0
## Points in each leg (astern, ahead) of her way between slips.
const SHIFT_STEPS := 40

var points := PackedVector3Array()
var back_count := 0
var cusp := 0.0
var length := 0.0


## Backs straight out of the slip until the hull clears the outer dolphins,
## then swings her stern out away from the other slip as she slows to a stop, comes
## ahead round in an arc to line up well out, and runs straight in, the way a boat
## handles. Geometry is independent of the ferry's live movement state.
static func build(from: Vector3, to: Vector3, town: MapData.Town, half_length: float) -> SlipShiftPath:
	var result := SlipShiftPath.new()
	var out := town.dock_dir.normalized()
	var side := to - from
	side.y = 0.0
	var gap := side.length()
	side = side.normalized() if gap > 0.01 else town.lateral().normalized()
	# Out until her seaward half is past the channel buoys, so as her stern swings
	# away it swings beyond them, and her inshore end is clear of the outer dolphins.
	var clear_u := maxf(Layout.CHANNEL_BUOY_U - SHIFT_MARGIN, Layout.DOLPHIN_OUTER.x + half_length + 5.0)
	var straight := maxf(clear_u - Layout.DOCK_U, 20.0)
	var p1 := from + out * straight
	var q1 := to + out * straight
	var r := SHIFT_OUT
	var apex := p1 + out * r * 0.9 - side * r * 0.7
	var back := (out * 0.5 - side).normalized()   # her way astern as she stops
	var path := PackedVector3Array()
	_append_line(path, from, p1)
	var c1 := [p1, p1 + out * r * 0.45, apex - back * r * 0.4, apex]
	for k in range(1, SHIFT_STEPS + 1):
		path.append(_bezier(c1, k / float(SHIFT_STEPS)))
	result.back_count = path.size()
	var c2 := [apex, apex - back * (r * 0.5 + gap * 0.35), q1 + out * (r * 0.6 + gap * 0.2), q1]
	for k in range(1, SHIFT_STEPS + 1):
		path.append(_bezier(c2, k / float(SHIFT_STEPS)))
	_append_line(path, q1, to)
	result.points = path
	for k in range(1, path.size()):
		result.length += path[k].distance_to(path[k - 1])
		if k == result.back_count - 1:
			result.cusp = result.length
	return result


static func _append_line(path: PackedVector3Array, a: Vector3, b: Vector3) -> void:
	var n := maxi(2, int(a.distance_to(b) / 6.0))
	for k in n + 1:
		if k == 0 and not path.is_empty():
			continue
		path.append(a.lerp(b, k / float(n)))


static func _bezier(c: Array, t: float) -> Vector3:
	var u := 1.0 - t
	return c[0] * u * u * u + c[1] * 3.0 * u * u * t + c[2] * 3.0 * u * t * t + c[3] * t * t * t


## About how far she goes between two slips `apart` metres apart along the shore
## (build: straight out past the buoys, round, and straight in again).
static func estimated_length(apart: float) -> float:
	var straight := maxf(Layout.CHANNEL_BUOY_U - SHIFT_MARGIN - Layout.DOCK_U, 20.0)
	return 2.0 * straight + 2.6 * SHIFT_OUT + 1.4 * apart
