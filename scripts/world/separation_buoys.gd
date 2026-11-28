class_name SeparationBuoys
extends Node3D
## Traffic separation buoys about every SPACING metres along every route two or
## more boats share, on the centreline between their lanes (at least one, mid-route). Comes and
## goes as boats are put on and
## taken off routes; flashes amber at night.

const GLB := "res://assets/models/buoys/buoy_traffic_separation.glb"
const SPACING := 2000.0
const CHANNEL_SPACING := 700.0  # along the cargo channels
const PAINT := preload("res://shaders/weathered_paint.gdshader")
const AMBER := Color(1.0, 0.65, 0.15)

var sim: Simulation
var night_lights: Node3D
var _buoys := {}  # route id -> [model, glow]
var _codes := {}  # text -> ViewportTexture
var _check := 0.0
var _first_code := {}  # route id -> index of its first buoy's code


## Puget Sound style codes: S, SA..SG, T, TA..TG, U, ... (letters run on after G).
static func code(i: int) -> String:
	var per := 8
	var head := char(83 + i / per)  # "S" onward
	var tail := i % per
	return head if tail == 0 else head + char(64 + tail)


func setup(s: Simulation, lights: Node3D) -> void:
	sim = s
	night_lights = lights
	# Every route's buoys get their codes up front, so a buoy keeps its name
	# whatever other routes come and go.
	var next := 1  # (start at SA)
	for r in sim.map.routes:
		_first_code[r.id] = next
		next += _count(r)
	_place_channels(next)


static func _count(r: MapData.Route) -> int:
	return maxi(1, roundi(r.length / SPACING))


func _process(delta: float) -> void:
	_check -= delta
	if _check > 0.0 or sim == null or not ResourceLoader.exists(GLB):
		return
	_check = 1.0
	var want := {}
	for r in sim.map.routes:
		if r.curve and r.length > 0.0 and sim.marine.shared(r):
			want[r.id] = r
	for id in _buoys.keys():
		if not want.has(id):
			for n: Node in _buoys[id]:
				if is_instance_valid(n):
					n.queue_free()
			_buoys.erase(id)
	for id in want:
		if not _buoys.has(id):
			_buoys[id] = _place(want[id])


func _place(r: MapData.Route) -> Array:
	var n := _count(r)
	var out: Array = []
	for k in n:
		out.append_array(_place_at(r, (k + 0.5) * r.length / n, k))
	return out


func _place_at(r: MapData.Route, s: float, k: int) -> Array:
	var mid := r.curve.sample_baked(s)
	var ahead := r.curve.sample_baked(minf(s + 5.0, r.length))
	return _buoy(
		Vector2(mid.x, mid.z),
		Vector2(ahead.x - mid.x, ahead.z - mid.z),
		"Separation Buoy %d-%d" % [r.id, k],
		code(_first_code.get(r.id, 0) + k)
	)


## Buoys every CHANNEL_SPACING along each cargo channel's centreline
## (ShippingLanes), on the map and a little way past its edge. They stay put.
func _place_channels(first_code: int) -> void:
	if not ResourceLoader.exists(GLB) or sim.marine == null or sim.marine.lanes == null:
		return
	var lanes := sim.marine.lanes
	var lim := sim.map.half_size + 600.0
	var n := first_code
	for i in lanes.centrelines.size():
		var line := lanes.centrelines[i]
		var path := NavPath.new(line)
		var d := CHANNEL_SPACING * 0.5
		var k := 0
		while d < path.length:
			var p := path.sample(d)
			if absf(p.x) < lim and absf(p.y) < lim:
				_buoy(p, path.tangent(d, 20.0), "Channel Buoy %s-%d" % [lanes.names[i], k], code(n))
				n += 1
				k += 1
			d += CHANNEL_SPACING


func _buoy(at: Vector2, dir2: Vector2, nm: String, text: String) -> Array:
	var p := Vector3(at.x, 0.0, at.y)
	var yaw := atan2(dir2.x, dir2.y) if dir2.length() > 0.01 else 0.0
	var aid := (load(GLB) as PackedScene).instantiate() as Node3D
	aid.name = nm
	add_child(aid)
	var b := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * WorldBuilder.BUOY_SCALE)
	aid.transform = Transform3D(b, p)
	_letter(aid, text)
	var out: Array = [aid]
	if night_lights:
		var beacon := aid.find_child("BeaconLight", true, false) as Node3D
		var lamp := beacon.position if beacon else Vector3(0, 3.0, 0)
		var glows := GlowBuilder.new()
		var phase := Models.blink_phase_at(p)
		glows.glow(
			p + b * (lamp + Vector3(0, 0.35, 0)),
			AMBER,
			0.6,
			7.0,
			true,
			Models.blink_of(phase),
			Vector3.ZERO,
			Models.LAMP_ON_AT
		)
		var mi := MeshInstance3D.new()
		mi.name = aid.name + " Light"
		mi.mesh = glows.commit()
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		night_lights.add_child(mi)
		out.append(mi)
	return out


## The code painted on each of the daymark box's four faces (see art/buoys.py),
## in weathered stencil paint: the code is drawn once into a small texture, then
## shaders/weathered_paint chips and fades it on each face.
func _letter(aid: Node3D, text: String) -> void:
	var mat := ShaderMaterial.new()
	mat.shader = PAINT
	mat.set_shader_parameter("texture_albedo", _code_texture(text))
	var quad := QuadMesh.new()
	quad.size = Vector2(1.2, 0.6)
	for i in 4:
		var mi := MeshInstance3D.new()
		mi.mesh = quad
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var yaw := i * PI * 0.5
		mi.transform = Transform3D(
			Basis(Vector3.UP, yaw), Basis(Vector3.UP, yaw) * Vector3(0, 4.28, 0.69)
		)
		aid.add_child(mi)


func _code_texture(text: String) -> Texture2D:
	if _codes.has(text):
		return _codes[text]
	var vp := SubViewport.new()
	vp.size = Vector2i(256, 128)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	var l := Label.new()
	l.text = text
	l.size = Vector2(256, 128)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", 104)
	l.add_theme_color_override("font_color", Color.WHITE)
	vp.add_child(l)
	add_child(vp)
	_codes[text] = vp.get_texture()
	return _codes[text]
