class_name PinnipedModel
extends RefCounted
## Harbor seals and sea lions share an authored asset and a classic model switch.

const ASSET := "res://assets/models/pinnipeds_mid.glb"
static var authored := (
	not "--classic-seals" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


## A harbor seal: rotund, no neck to speak of, short flippers, a dog-like face
## with big dark eyes. Pale grey and heavily spotted (the instance colour tints
## it silver, tawny or dark).
static func harbor_seal(material: Material) -> ArrayMesh:
	if authored:
		return ModelParts.shader_mesh(ASSET, "harborseal", material)
	var mb := MeshBuilder.new()
	var coat := Color(0.86, 0.85, 0.82)
	var spot := Color(0.42, 0.41, 0.4)
	var belly := Color(0.95, 0.94, 0.9)
	var st := [
		[0.5, 0.0, 0.0, 0.07],
		[0.47, 0.033, 0.028, 0.07],
		[0.43, 0.052, 0.046, 0.076],
		[0.37, 0.066, 0.058, 0.08],
		[0.3, 0.08, 0.07, 0.08],
		[0.18, 0.11, 0.098, 0.098],
		[0.03, 0.124, 0.108, 0.108],
		[-0.14, 0.1, 0.088, 0.088],
		[-0.28, 0.058, 0.056, 0.06],
		[-0.37, 0.028, 0.03, 0.046]
	]
	_pinniped_body(
		mb,
		st,
		func(i: int, band: int, k: int) -> Color:
			if band == 3 and i >= 4:
				return belly
			# Dappled: every facet a little darker or lighter.
			return coat.lerp(spot, MarineMammalMesh.spots(i, k, 11.0) * 0.45) if i >= 2 else coat
	)
	_face(mb, Vector3(0.042, 0.095, 0.43), 0.011, Vector3(0, 0.072, 0.498))
	_hind_flippers(mb, -0.36, 0.045, -0.52, 0.075, spot)
	# Short fore flippers, tucked along the chest.
	for side: float in [-1.0, 1.0]:
		mb.tri(
			Vector3(0.1 * side, 0.035, 0.22),
			Vector3(0.105 * side, 0.03, 0.14),
			Vector3(0.15 * side, 0.004, 0.13),
			spot,
			Vector3(side, 1, 0)
		)
	var mesh := mb.commit()
	mesh.shadow_mesh = null
	return mesh


## A California sea lion: sleeker, a real neck, a narrow pointed snout with
## little ear flaps, and long fore flippers it props itself up on. Brown, darker
## along the back (the instance colour tints bulls dark, females golden).
static func sea_lion(material: Material) -> ArrayMesh:
	if authored:
		return ModelParts.shader_mesh(ASSET, "sealion", material)
	var mb := MeshBuilder.new()
	var coat := Color(0.86, 0.84, 0.8)
	var back := Color(0.72, 0.7, 0.67)
	var muzzle := Color(0.95, 0.93, 0.88)
	var flipper := Color(0.45, 0.43, 0.42)
	var st := [
		[0.5, 0.0, 0.0, 0.125],
		[0.465, 0.022, 0.022, 0.125],
		[0.41, 0.043, 0.043, 0.132],
		[0.34, 0.05, 0.05, 0.128],
		[0.26, 0.066, 0.068, 0.11],
		[0.13, 0.108, 0.1, 0.1],
		[-0.02, 0.112, 0.098, 0.098],
		[-0.17, 0.082, 0.078, 0.078],
		[-0.29, 0.044, 0.048, 0.05],
		[-0.35, 0.024, 0.028, 0.034]
	]
	_pinniped_body(
		mb,
		st,
		func(i: int, band: int, _k: int) -> Color:
			if i <= 1:
				return muzzle
			return back if band == 0 else coat
	)
	_face(mb, Vector3(0.038, 0.148, 0.415), 0.009, Vector3(0, 0.128, 0.497))
	# Ear flaps.
	for side: float in [-1.0, 1.0]:
		mb.tri(
			Vector3(0.045 * side, 0.16, 0.36),
			Vector3(0.05 * side, 0.165, 0.345),
			Vector3(0.055 * side, 0.15, 0.335),
			flipper,
			Vector3(side, 0, -1)
		)
	_hind_flippers(mb, -0.34, 0.03, -0.5, 0.07, flipper)
	# Long fore flippers, out to the side and down to the ground.
	for side: float in [-1.0, 1.0]:
		var r0 := Vector3(0.095 * side, 0.05, 0.17)
		var r1 := Vector3(0.1 * side, 0.045, 0.07)
		var tip := Vector3(0.25 * side, 0.0, -0.02)
		var mid := Vector3(0.18 * side, 0.015, 0.1)
		mb.tri(r0, mid, r1, flipper, Vector3.UP)
		mb.tri(mid, tip, r1, flipper, Vector3.UP)
	var mesh := mb.commit()
	mesh.shadow_mesh = null
	return mesh


## A seal or sea lion one unit long (+Z forward, nose at z = 0.5) lying on its
## belly, the bottom of its belly at y = 0; drawn per animal by Pinnipeds and
## posed by pinniped.gdshader (head up, hind flippers up, swimming sway or the
## arch of a seal humping along on land). Rings of 8 facets through the stations
## `st` ([z, half-width, half-height, centre height]), coloured by
## `paint`(station, band, facet), band 0 the back and 3 the belly.
static func _pinniped_body(mb: MeshBuilder, st: Array, paint: Callable) -> void:
	MarineMammalMesh.body(mb, st, paint)
	# Close off the tail end (the flippers fan out from it).
	var last: Array = st[st.size() - 1]
	if last[1] > 0.0:
		var c := Vector3(0, last[3], last[0] - 0.01)
		for k in 8:
			var a0 := TAU * k / 8.0
			var a1 := TAU * (k + 1) / 8.0
			mb.tri(
				Vector3(last[1] * sin(a0), last[3] + last[2] * cos(a0), last[0]),
				Vector3(last[1] * sin(a1), last[3] + last[2] * cos(a1), last[0]),
				c,
				paint.call(st.size() - 2, mini(k, 7 - k), k),
				Vector3.FORWARD
			)


## Hind flippers: two webbed fans off the tail, toes spread.
static func _hind_flippers(
	mb: MeshBuilder, root_z: float, y: float, tip_z: float, spread: float, col: Color
) -> void:
	for side: float in [-1.0, 1.0]:
		var r := Vector3(0.012 * side, y, root_z)
		var outer := Vector3(spread * side, y - 0.004, tip_z)
		var inner := Vector3(spread * 0.25 * side, y - 0.004, tip_z + 0.02)
		var mid := Vector3(spread * 0.6 * side, y - 0.002, tip_z + 0.035)
		mb.tri(r, outer, mid, col, Vector3.UP)
		mb.tri(r, mid, inner, col, Vector3.UP)


## An eye on each side of the head, and the nose.
static func _face(mb: MeshBuilder, eye: Vector3, r: float, nose: Vector3) -> void:
	var black := Color(0.03, 0.03, 0.035)
	for side: float in [-1.0, 1.0]:
		var c := Vector3(eye.x * side, eye.y, eye.z)
		var o := Vector3(side * 0.004, 0, 0)
		mb.quad(
			c + o + Vector3(0, -r, r),
			c + o + Vector3(0, -r, -r),
			c + o + Vector3(0, r, -r),
			c + o + Vector3(0, r, r),
			black,
			Vector3(side, 0.2, 0.3)
		)
	mb.tri(
		nose + Vector3(-0.012, 0.004, 0),
		nose + Vector3(0.012, 0.004, 0),
		nose + Vector3(0, -0.012, 0.004),
		black,
		Vector3(0, 0.3, 1)
	)
