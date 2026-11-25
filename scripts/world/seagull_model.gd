class_name SeagullModel
extends RefCounted
## The gull shader uses folded wing positions from the authored mesh's UV channels.
## The classic mesh folds about the shoulder in the shader instead.

const ASSET := "res://assets/models/seagull_mid.glb"

static var baked_fold := (
	not "--classic-gull" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func wing_material() -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = preload("res://shaders/seagull.gdshader")
	material.set_shader_parameter("baked_fold", baked_fold)
	return material


static func build(material: Material) -> ArrayMesh:
	if baked_fold:
		return ModelParts.shader_mesh(ASSET, "seagull", material)
	var mb := MeshBuilder.new()
	var white := Color(0.95, 0.95, 0.93)
	var mantle := Color(0.66, 0.7, 0.74, 0.5)
	var tip := Color(0.12, 0.12, 0.13, 0.5)
	# Body: an octahedron stretched along the spine, and a smaller one for the head.
	_octa(mb, Vector3(0, 0.01, 0.03), Vector3(0.065, 0.065, 0.0), 0.24, -0.23, white)
	_octa(mb, Vector3(0, 0.075, 0.22), Vector3(0.045, 0.045, 0.0), 0.06, -0.05, white)
	var beak := Color(0.95, 0.74, 0.2)
	var bp := Vector3(0, 0.06, 0.36)
	var b0 := Vector3(0.016, 0.075, 0.275)
	var b1 := Vector3(-0.016, 0.075, 0.275)
	var b2 := Vector3(0, 0.05, 0.275)
	mb.tri(b0, b1, bp, beak, Vector3.UP)
	mb.tri(b1, b2, bp, beak, Vector3(-1, -1, 0))
	mb.tri(b2, b0, bp, beak, Vector3(1, -1, 0))
	mb.quad(
		Vector3(-0.05, 0.03, -0.16),
		Vector3(0.05, 0.03, -0.16),
		Vector3(0.075, 0.02, -0.32),
		Vector3(-0.075, 0.02, -0.32),
		white,
		Vector3.UP
	)
	for side: float in [-1.0, 1.0]:
		var sh_f := Vector3(0.06 * side, 0.04, 0.1)
		var sh_b := Vector3(0.06 * side, 0.04, -0.07)
		var el_f := Vector3(0.4 * side, 0.04, 0.08)
		var el_b := Vector3(0.4 * side, 0.04, -0.09)
		var mid_f := Vector3(0.58 * side, 0.04, 0.03)
		var mid_b := Vector3(0.58 * side, 0.04, -0.1)
		var end := Vector3(0.72 * side, 0.04, -0.12)
		mb.quad(sh_f, el_f, el_b, sh_b, mantle, Vector3.UP)
		mb.quad(el_f, mid_f, mid_b, el_b, mantle, Vector3.UP)
		mb.tri(mid_f, end, mid_b, tip, Vector3.UP)
	return mb.commit(material)


## An octahedron at `c`, `r` wide (x) and tall (y), reaching `front` ahead and `back` behind.
static func _octa(
	mb: MeshBuilder, c: Vector3, r: Vector3, front: float, back: float, col: Color
) -> void:
	var f := c + Vector3(0, 0, front)
	var b := c + Vector3(0, 0, back)
	var ring := [
		c + Vector3(r.x, 0, 0),
		c + Vector3(0, r.y, 0),
		c + Vector3(-r.x, 0, 0),
		c + Vector3(0, -r.y, 0)
	]
	for i in 4:
		var p0: Vector3 = ring[i]
		var p1: Vector3 = ring[(i + 1) % 4]
		var out := (p0 + p1) * 0.5 - c
		mb.tri(p0, p1, f, col, out)
		mb.tri(p1, p0, b, col, out)
