class_name WhaleModel
extends RefCounted
## Humpback and gray whale variants share a Blender source and launch switch.

const ASSET := "res://assets/models/whales_mid.glb"
static var authored := (
	not "--classic-whales" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


## A humpback: long, knobbly-headed, with a small dorsal fin on a hump, very long
## pale flippers and broad flukes whose undersides are mostly white.
static func humpback(material: Material) -> ArrayMesh:
	if authored:
		return ModelParts.shader_mesh(ASSET, "humpback", material)
	var mb := MeshBuilder.new()
	var dark := Color(0.09, 0.095, 0.11)
	var grey := Color(0.24, 0.25, 0.27)
	var pale := Color(0.82, 0.82, 0.8)
	var st := [
		[0.5, 0.0, 0.0, -0.025],
		[0.46, 0.045, 0.025, -0.012],
		[0.37, 0.085, 0.055, 0.0],
		[0.22, 0.108, 0.085, 0.0],
		[0.05, 0.112, 0.093, 0.0],
		[-0.12, 0.085, 0.08, 0.005],
		[-0.27, 0.048, 0.055, 0.01],
		[-0.38, 0.02, 0.034, 0.012],
		[-0.42, 0.0, 0.0, 0.012]
	]
	MarineMammalMesh.body(
		mb,
		st,
		func(i: int, band: int, k: int) -> Color:
			if band == 3 and i >= 1 and i <= 3:
				return pale.darkened(MarineMammalMesh.spots(i, k, 1.0) * 0.25)
			if band == 2 and i <= 3:
				return grey.lerp(pale, 0.35 * MarineMammalMesh.spots(i, k, 2.0))
			if band == 0 and i <= 1:
				# The knobs on its head.
				return dark.lightened(0.12 * MarineMammalMesh.spots(i, k, 3.0))
			return dark if band < 2 else grey
	)
	MarineMammalMesh.dorsal_fin(mb, -0.06, -0.17, 0.083, dark, dark)
	MarineMammalMesh.flipper(
		mb,
		Vector3(0.09, -0.045, 0.24),
		Vector3(0.36, -0.14, -0.06),
		0.12,
		grey.lerp(pale, 0.5),
		pale
	)
	MarineMammalMesh.flukes(mb, -0.38, 0.19, -0.5, dark, pale)
	var mesh := mb.commit(material)
	mesh.shadow_mesh = null
	return mesh


## A gray whale: slimmer, mottled grey with pale patches of barnacles, no dorsal
## fin but a low hump and a row of knuckles down its tail stock.
static func gray_whale(material: Material) -> ArrayMesh:
	if authored:
		return ModelParts.shader_mesh(ASSET, "graywhale", material)
	var mb := MeshBuilder.new()
	var base := Color(0.4, 0.42, 0.43)
	var light := Color(0.62, 0.63, 0.61)
	var barnacle := Color(0.8, 0.78, 0.72)
	var st := [
		[0.5, 0.0, 0.0, -0.03],
		[0.44, 0.035, 0.035, -0.02],
		[0.34, 0.065, 0.065, 0.0],
		[0.18, 0.09, 0.085, 0.0],
		[0.0, 0.095, 0.09, 0.0],
		[-0.16, 0.075, 0.075, 0.0],
		[-0.3, 0.042, 0.052, 0.006],
		[-0.4, 0.018, 0.035, 0.01],
		[-0.44, 0.0, 0.0, 0.01]
	]
	MarineMammalMesh.body(
		mb,
		st,
		func(i: int, band: int, k: int) -> Color:
			var r := MarineMammalMesh.spots(i, k, 7.0)
			if r > 0.86 and band < 3:
				return barnacle
			return base.lerp(light, r * 0.7).darkened(0.08 * band)
	)
	# A low hump, then knuckles along the ridge of the tail stock.
	MarineMammalMesh.dorsal_fin(mb, -0.08, -0.16, 0.08, base, base)
	var z := -0.19
	while z > -0.38:
		var t := (z + 0.16) / -0.24
		var y := lerpf(0.074, 0.044, t)
		mb.tri(
			Vector3(-0.01, y - 0.004, z + 0.012),
			Vector3(0.01, y - 0.004, z + 0.012),
			Vector3(0, y + 0.012, z),
			base,
			Vector3(0, 1, 1)
		)
		mb.tri(
			Vector3(-0.01, y - 0.004, z - 0.012),
			Vector3(0.01, y - 0.004, z - 0.012),
			Vector3(0, y + 0.012, z),
			base,
			Vector3(0, 1, -1)
		)
		z -= 0.035
	MarineMammalMesh.flipper(
		mb, Vector3(0.07, -0.05, 0.25), Vector3(0.19, -0.11, 0.12), 0.06, base, light
	)
	MarineMammalMesh.flukes(mb, -0.39, 0.15, -0.51, base, light)
	var mesh := mb.commit(material)
	mesh.shadow_mesh = null
	return mesh
