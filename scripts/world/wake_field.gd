class_name WakeField
extends Node
## Hands every vessel's wake trail (ferries, cargo ships, sailboats) to the water
## shader each frame, which draws the foam, aerated water and Kelvin waves itself.

# Must match WAKE_SLOTS / WAKE_PTS in water.gdshader.
const MAX_SLOTS := 16
const MAX_POINTS := 48
const SEGMENTS_PER_GROUP := 6
const GROUPS_PER_SLOT := 8
# Half-widths along each hull's waterline (WAKE_STATIONS in water.gdshader).
const STATIONS := 24
# Must match the shader's Kelvin wedge, so the bounds cover the whole wake.
const KELVIN_SPREAD := 0.354
const KELVIN_REACH := 540.0
# Furthest the shader's reverse-thrust wash reaches from the bow (with its spread).
const FRONT_WASH_REACH := 72.0
# The water shader's unit (water.gdshader's UNIT): everything goes over in it.
const UNIT := 3.0
# Conservative world-space vertical range around the displaced sea surface.
const WATER_HEIGHT_MARGIN := 50.0

var sim: Simulation
var water_mat: ShaderMaterial
var _setup_frame: int
var _pts := PackedVector4Array()
var _spd := PackedFloat32Array()
var _spd4 := PackedVector4Array()
var _group_box := PackedVector4Array()
var _group_radius := PackedVector4Array()
var _box := PackedVector4Array()
var _info := PackedVector4Array()
var _hull := PackedVector4Array()
var _shape := PackedVector4Array()
var _prof := PackedVector4Array()


func _ready() -> void:
	# After the vessels have moved this frame.
	process_priority = 10
	_setup_frame = Engine.get_frames_drawn()
	_pts.resize(MAX_SLOTS * MAX_POINTS)
	_spd.resize(MAX_SLOTS * MAX_POINTS)
	_spd4.resize(MAX_SLOTS * MAX_POINTS / 4)
	_box.resize(MAX_SLOTS)
	_group_box.resize(MAX_SLOTS * GROUPS_PER_SLOT)
	_group_radius.resize(MAX_SLOTS * GROUPS_PER_SLOT / 4)
	_info.resize(MAX_SLOTS)
	_hull.resize(MAX_SLOTS)
	_shape.resize(MAX_SLOTS)
	_prof.resize(MAX_SLOTS * STATIONS / 4)


func _process(_delta: float) -> void:
	var fleet: Array[Vessel] = []
	for f in sim.ferries:
		if not f.wake.is_empty():
			fleet.append(f)
	for v in sim.marine.vessels:
		if is_instance_valid(v) and v.wake and not v.wake.is_empty():
			fleet.append(v)
	# There are more vessels than the shader has slots (and moored or docked ones
	# keep their trail for a while), so the nearest to the camera get them first.
	var cam := get_viewport().get_camera_3d()
	if cam and fleet.size() > MAX_SLOTS:
		var c := Vector2(cam.global_position.x, cam.global_position.z)
		fleet.sort_custom(func(a: Vessel, b: Vessel):
			return (a.pos2() - c).length_squared() < (b.pos2() - c).length_squared())
	# The one-shot minimap shares the water material on its initial draw.
	var planes: Array[Plane] = []
	if cam and Engine.get_frames_drawn() > _setup_frame:
		planes = cam.get_frustum()
	var eligible := 0
	var count := 0
	for v in fleet:
		if eligible >= MAX_SLOTS:
			break
		var tr := v.wake
		var hull := v.wake_hull()
		var at := count * MAX_POINTS
		var n := tr.pack(v.global_position, _pts, _spd, at, MAX_POINTS)
		if n < 2:
			continue
		var reach := KELVIN_REACH * hull.w
		var lo := Vector2(INF, INF)
		var hi := -lo
		for i in n:
			var p := _pts[at + i]
			var along := tr.odometer - p.z
			var wk := hull.x + clampf(along + hull.y, 0.0, reach) * KELVIN_SPREAD
			var r := wk * 1.1 + 12.0
			lo = lo.min(Vector2(p.x - r, p.y - r))
			hi = hi.max(Vector2(p.x + r, p.y + r))
		var thrust := v.front_thrust()
		if thrust > 0.0:
			# Room for the reverse-thrust wash thrown out ahead of the bow.
			var bow := Vector2(_pts[at].x, _pts[at].y)
			lo = lo.min(bow - Vector2.ONE * FRONT_WASH_REACH)
			hi = hi.max(bow + Vector2.ONE * FRONT_WASH_REACH)
		# Preserve the original nearest-vessel budget even when a slot is culled.
		eligible += 1
		if _outside_view(lo, hi, planes):
			continue
		_box[count] = Vector4(lo.x, lo.y, hi.x, hi.y) / UNIT
		_info[count] = Vector4(tr.odometer / UNIT, n, tr.life, thrust)
		_hull[count] = Vector4(hull.x / UNIT, hull.y / UNIT, hull.z, hull.w)
		# The waterline: where it starts and how long it is, how far back from its stem
		# the bow fills out (to 97% of its widest) and its half-width at the stem.
		var wl := v.wake_waterline()
		var widest := 0.0
		for i in STATIONS:
			widest = maxf(widest, wl[2 + i])
		var run := 0
		while run < STATIONS - 1 and wl[2 + run] < widest * 0.97:
			run += 1
		var ds := wl[1] / (STATIONS - 1)
		_shape[count] = Vector4(wl[0], wl[1], run * ds, wl[2]) / UNIT
		for i in STATIONS / 4:
			var j := 2 + i * 4
			_prof[count * STATIONS / 4 + i] = Vector4(wl[j], wl[j + 1], wl[j + 2], wl[j + 3]) / UNIT
		for i in n:
			var q := _pts[at + i]
			_pts[at + i] = Vector4(q.x / UNIT, q.y / UNIT, q.z / UNIT, q.w)
		_pack_segment_bounds(count, n)
		count += 1
	# Speeds go four to a vec4, which keeps the shader's uniforms compact.
	for i in _spd4.size():
		_spd4[i] = Vector4(_spd[i * 4], _spd[i * 4 + 1], _spd[i * 4 + 2], _spd[i * 4 + 3])
	water_mat.set_shader_parameter("wake_count", count)
	water_mat.set_shader_parameter("wake_pts", _pts)
	water_mat.set_shader_parameter("wake_speed", _spd4)
	water_mat.set_shader_parameter("wake_box", _box)
	water_mat.set_shader_parameter("wake_info", _info)
	water_mat.set_shader_parameter("wake_hull", _hull)
	water_mat.set_shader_parameter("wake_shape", _shape)
	water_mat.set_shader_parameter("wake_prof", _prof)
	water_mat.set_shader_parameter("wake_group_box", _group_box)
	water_mat.set_shader_parameter("wake_group_radius", _group_radius)


## Cull only if the entire wake (including its trailing crumbs) misses one plane.
static func _outside_view(lo: Vector2, hi: Vector2, planes: Array[Plane]) -> bool:
	var center := Vector3((lo.x + hi.x) * 0.5, 0.0, (lo.y + hi.y) * 0.5)
	var extent := Vector3((hi.x - lo.x) * 0.5, WATER_HEIGHT_MARGIN, (hi.y - lo.y) * 0.5)
	for plane in planes:
		if plane.distance_to(center) > plane.normal.abs().dot(extent) + 1.0:
			return true
	return false


## Bound each group of trail segments in shader units. A fragment outside a
## group's wash radius only needs that group when it might contain a nearer
## segment for the Kelvin waves. Keep the exact search for degenerate segments.
func _pack_segment_bounds(slot: int, point_count: int) -> void:
	var offset := slot * MAX_POINTS
	var half_beam := _hull[slot].x
	for first in range(0, point_count - 1, SEGMENTS_PER_GROUP):
		var lo := Vector2(_pts[offset + first].x, _pts[offset + first].y)
		var hi := lo
		var min_distance := INF
		var degenerate := false
		for i in range(first, mini(first + SEGMENTS_PER_GROUP, point_count - 1)):
			var a := _pts[offset + i]
			var b := _pts[offset + i + 1]
			var end := Vector2(b.x, b.y)
			lo = lo.min(end)
			hi = hi.max(end)
			# trail_at extrapolates half a segment beyond either endpoint.
			min_distance = minf(min_distance, minf(a.z, b.z) - 0.5 * absf(b.z - a.z))
			if Vector2(a.x, a.y).distance_squared_to(end) <= 0.00011:
				degenerate = true
		var group := slot * GROUPS_PER_SLOT + first / SEGMENTS_PER_GROUP
		_group_box[group] = Vector4(lo.x, lo.y, hi.x, hi.y)
		# wash_reach limits lateral spread; end_fade allows up to 1.5 + half_beam
		# beyond the ends. Their sum also covers the corners, with rounding slack.
		var behind := maxf(0.0, _info[slot].x - min_distance)
		var radius := 1.85 * half_beam * (0.75 + 0.13 * sqrt(behind)) + 1.6 + half_beam
		_group_radius[group / 4][group % 4] = -1.0 if degenerate else radius
