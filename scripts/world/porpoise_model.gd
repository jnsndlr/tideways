class_name PorpoiseModel
extends RefCounted
## Procedural meshes used by the two porpoise species.


## A Dall's porpoise: stocky and black with a big white patch on each flank,
## a triangular fin frosted at the tip.
static func dalls_porpoise(material: Material) -> ArrayMesh:
	var mb := MeshBuilder.new()
	var black := Color(0.04, 0.045, 0.05)
	var white := Color(0.92, 0.93, 0.92)
	var st := [
		[0.5, 0.0, 0.0, -0.01],
		[0.45, 0.04, 0.04, 0.0],
		[0.36, 0.085, 0.085, 0.0],
		[0.18, 0.115, 0.108, 0.0],
		[0.0, 0.115, 0.11, 0.0],
		[-0.15, 0.085, 0.09, 0.005],
		[-0.3, 0.035, 0.065, 0.01],
		[-0.4, 0.015, 0.035, 0.01],
		[-0.44, 0.0, 0.0, 0.01]
	]
	MarineMammalMesh.body(
		mb,
		st,
		func(i: int, band: int, _k: int) -> Color:
			if band >= 2 and i >= 3 and i <= 4:
				return white
			return black
	)
	MarineMammalMesh.dorsal_fin(mb, 0.04, -0.12, 0.105, black, Color(0.75, 0.77, 0.78))
	MarineMammalMesh.flipper(
		mb, Vector3(0.08, -0.06, 0.25), Vector3(0.17, -0.12, 0.15), 0.06, black, black
	)
	MarineMammalMesh.flukes(mb, -0.38, 0.13, -0.49, black, black)
	var mesh := mb.commit(material)
	mesh.shadow_mesh = null
	return mesh


## A harbor porpoise: small and round-headed, dark grey above, paler below, with
## a little triangular fin.
static func harbor_porpoise(material: Material) -> ArrayMesh:
	var mb := MeshBuilder.new()
	var dark := Color(0.17, 0.18, 0.2)
	var side := Color(0.42, 0.43, 0.44)
	var belly := Color(0.85, 0.85, 0.83)
	var st := [
		[0.5, 0.0, 0.0, -0.01],
		[0.45, 0.045, 0.045, 0.0],
		[0.35, 0.08, 0.08, 0.0],
		[0.18, 0.1, 0.1, 0.0],
		[0.0, 0.1, 0.1, 0.0],
		[-0.16, 0.075, 0.08, 0.0],
		[-0.3, 0.035, 0.05, 0.005],
		[-0.4, 0.015, 0.03, 0.01],
		[-0.44, 0.0, 0.0, 0.01]
	]
	MarineMammalMesh.body(
		mb, st, func(_i: int, band: int, _k: int) -> Color: return [dark, dark, side, belly][band]
	)
	MarineMammalMesh.dorsal_fin(mb, 0.02, -0.11, 0.095, dark, dark)
	MarineMammalMesh.flipper(
		mb, Vector3(0.07, -0.06, 0.25), Vector3(0.16, -0.11, 0.16), 0.05, dark, dark
	)
	MarineMammalMesh.flukes(mb, -0.38, 0.12, -0.48, dark, dark)
	var mesh := mb.commit(material)
	mesh.shadow_mesh = null
	return mesh
