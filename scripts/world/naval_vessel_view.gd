class_name NavalVesselView
extends RefCounted
## Installs the authored hull and samples its visible waterline once per model.

const TUG_GLB := "res://assets/models/navy_tug_mid.glb"
const SUB_GLB := "res://assets/models/nuclear_sub_mid.glb"
const NAUTILUS_GLB := "res://assets/models/fantasy_sub_mid.glb"

static var _waterlines := {}  # glb -> its waterline, measured from the mesh (model metres)


static func fit(vessel: NavalVessel) -> void:
	var glb: String = {"tug": TUG_GLB, "nautilus": NAUTILUS_GLB}.get(vessel.spec.id, SUB_GLB)
	var scene := load(glb) as PackedScene
	if scene:
		var art: Node3D = scene.instantiate()
		art.scale = Vector3.ONE * NavalVessel.ART_SCALE
		_use_vertex_colours(art)
		vessel.add_child(art)
		_fit_waterline(vessel, glb, art)


## The foam hugs the hull where it meets the water: its outline there, measured
## from the model's vertices near y = 0, in STATIONS half-widths stem to stern.
## The trail and hull fit it too.
static func _fit_waterline(vessel: NavalVessel, glb: String, art: Node3D) -> void:
	if not _waterlines.has(glb):
		_waterlines[glb] = _measure(art)
	var m: Dictionary = _waterlines[glb]
	if m.is_empty():
		return
	var bow: float = m.bow * NavalVessel.ART_SCALE
	var length: float = m.length * NavalVessel.ART_SCALE
	var profile := PackedFloat32Array([vessel.spec.half_length - bow, length])
	for w: float in m.widths:
		profile.append(w * NavalVessel.ART_SCALE)
	vessel.set_waterline(profile)


static func _measure(art: Node3D) -> Dictionary:
	const BAND := 0.9
	var pts := PackedVector3Array()
	var stack: Array[Node] = [art]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		stack.append_array(n.get_children())
		if not (n is MeshInstance3D and n.mesh):
			continue
		var xf: Transform3D = Transform3D.IDENTITY
		var up: Node = n
		while up != art and up is Node3D:
			xf = (up as Node3D).transform * xf
			up = up.get_parent()
		for i in n.mesh.get_surface_count():
			for v: Vector3 in n.mesh.surface_get_arrays(i)[Mesh.ARRAY_VERTEX]:
				var q := xf * v
				if absf(q.y) < BAND:
					pts.append(q)
	if pts.size() < 8:
		return {}
	var zmin := INF
	var zmax := -INF
	for q in pts:
		zmin = minf(zmin, q.z)
		zmax = maxf(zmax, q.z)
	var n := HullWaterline.STATIONS
	var length := zmax - zmin
	if is_zero_approx(length):
		return {}
	var widths := PackedFloat32Array()
	widths.resize(n)
	widths.fill(-1.0)
	for q in pts:
		var k := clampi(roundi((zmax - q.z) / length * (n - 1)), 0, n - 1)
		widths[k] = maxf(widths[k], absf(q.x))
	# Stations no vertex fell near: between their neighbours.
	for k in n:
		if widths[k] < 0.0:
			var a := k - 1
			while a >= 0 and widths[a] < 0.0:
				a -= 1
			var b := k + 1
			while b < n and widths[b] < 0.0:
				b += 1
			var wa := widths[a] if a >= 0 else 0.0
			var wb := widths[b] if b < n else 0.0
			widths[k] = (
				lerpf(wa, wb, float(k - a) / float(b - a))
				if a >= 0 and b < n
				else maxf(wa, wb) * 0.5
			)
	return {"bow": zmax, "length": length, "widths": widths}


static func _use_vertex_colours(n: Node) -> void:
	if n is MeshInstance3D and n.mesh:
		var m: Mesh = n.mesh
		for i in m.get_surface_count():
			var mat := m.surface_get_material(i) as BaseMaterial3D
			if mat and m.surface_get_format(i) & Mesh.ARRAY_FORMAT_COLOR:
				mat = mat.duplicate()
				mat.vertex_color_use_as_albedo = true
				mat.vertex_color_is_srgb = true
				n.set_surface_override_material(i, mat)
	for c in n.get_children():
		_use_vertex_colours(c)
