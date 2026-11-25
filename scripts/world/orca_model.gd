class_name OrcaModel
extends RefCounted
## Authored orcas use UV coordinates for individual markings. The classic mesh
## paints its own white patches and saddle. Both encode dorsal-fin height in vertex alpha.

const ASSET := "res://assets/models/orca_mid.glb"

static var uv_markings := (
	not "--classic-orca" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func build(material: Material) -> ArrayMesh:
	if uv_markings:
		return ModelParts.shader_mesh(ASSET, "orca", material)
	var mb := MeshBuilder.new()
	var black := Color(0.05, 0.055, 0.065)
	var white := Color(0.92, 0.93, 0.92)
	var saddle := Color(0.5, 0.52, 0.55)
	# Cross-sections nose to tail: z, half-width, half-height, centre height.
	var st := [
		[0.5, 0.0, 0.0, -0.01],
		[0.44, 0.045, 0.04, -0.005],
		[0.34, 0.075, 0.07, 0.0],
		[0.18, 0.095, 0.09, 0.0],
		[0.0, 0.095, 0.092, 0.0],
		[-0.16, 0.075, 0.075, 0.0],
		[-0.3, 0.045, 0.05, 0.005],
		[-0.4, 0.018, 0.035, 0.01],
		[-0.44, 0.0, 0.0, 0.01]
	]
	var rings: Array[PackedVector3Array] = []
	for s: Array in st:
		var ring := PackedVector3Array()
		for k in 8:
			var a := TAU * k / 8.0
			ring.append(Vector3(s[1] * sin(a), s[3] + s[2] * cos(a), s[0]))
		rings.append(ring)
	for i in st.size() - 1:
		var axis := Vector3(0, (st[i][3] + st[i + 1][3]) * 0.5, (st[i][0] + st[i + 1][0]) * 0.5)
		for k in 8:
			# Facet k runs from k * 45° (0 = the back) round to (k + 1) * 45°.
			var band := mini(k, 7 - k)  # 0 top, 1 upper side, 2 lower side, 3 belly
			var col := black
			if band == 3 and i <= 4:
				col = white
			elif band == 2 and (i <= 1 or i == 4 or i == 5):
				col = white
			elif band == 1 and i == 2:
				col = white
			elif band == 0 and i == 4:
				col = saddle
			var a := rings[i][k]
			var b := rings[i][(k + 1) % 8]
			var c := rings[i + 1][(k + 1) % 8]
			var d := rings[i + 1][k]
			mb.quad(a, b, c, d, col, (a + b + c + d) * 0.25 - axis)
	# Dorsal fin: base on the back, a waist and a tip; height and sweep come from the shader.
	var base_y := 0.085
	var bf := Vector3(0, base_y, 0.07)
	var bb := Vector3(0, base_y, -0.1)
	var mf := Vector3(0, base_y, 0.03)
	var mback := Vector3(0, base_y, -0.06)
	var tip := Vector3(0, base_y, -0.03)
	var fin_base := Color(black, 1.0)
	var fin_mid := Color(black, 0.75)
	var fin_tip := Color(black, 0.5)
	for side: float in [-1.0, 1.0]:
		var w := Vector3(0.014 * side, 0, 0)
		var wm := Vector3(0.007 * side, 0, 0)
		var out := Vector3(side, 0, 0)
		mb.tri3(bf + w, bb + w, mback + wm, fin_base, fin_base, fin_mid, out)
		mb.tri3(bf + w, mback + wm, mf + wm, fin_base, fin_mid, fin_mid, out)
		mb.tri3(mf + wm, mback + wm, tip, fin_mid, fin_mid, fin_tip, out)
		# Leading and trailing edges.
		mb.tri3(bf, bf + w, mf + wm, fin_base, fin_base, fin_mid, Vector3(side, 0, 1))
		mb.tri3(bf, mf + wm, mf, fin_base, fin_mid, fin_mid, Vector3(side, 0, 1))
		mb.tri3(mf, mf + wm, tip, fin_mid, fin_mid, fin_tip, Vector3(side, 0, 1))
		mb.tri3(bb, bb + w, mback + wm, fin_base, fin_base, fin_mid, Vector3(side, 0, -1))
		mb.tri3(bb, mback + wm, mback, fin_base, fin_mid, fin_mid, Vector3(side, 0, -1))
		mb.tri3(mback, mback + wm, tip, fin_mid, fin_mid, fin_tip, Vector3(side, 0, -1))
		# Paddle-shaped flippers, angled down and back.
		mb.tri(
			Vector3(0.07 * side, -0.065, 0.24),
			Vector3(0.21 * side, -0.12, 0.09),
			Vector3(0.07 * side, -0.07, 0.13),
			black,
			Vector3(0, -1, 0)
		)
		# Flukes: swept-back wings off the tail stock with a notch in the middle.
		var root_f := Vector3(0, 0.01, -0.38)
		var notch := Vector3(0, 0.01, -0.46)
		var fluke_tip := Vector3(0.15 * side, 0.005, -0.52)
		mb.tri(root_f, fluke_tip, Vector3(0.05 * side, 0.01, -0.48), black, Vector3.UP)
		mb.tri(root_f, Vector3(0.05 * side, 0.01, -0.48), notch, black, Vector3.UP)
	var mesh := mb.commit()
	# The shader moves the fin and tail, which a baked shadow mesh can't follow.
	mesh.shadow_mesh = null
	return mesh
