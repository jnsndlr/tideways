class_name Grass
extends MultiMeshInstance3D

## Grass blades round the camera's focus, drawn only when zoomed in. One MultiMesh
## of the same clump, all placed, coloured and swayed on the GPU (grass.gdshader)
## from the ground under each one (WorldBuilder.ground_rgba): no per-blade CPU work
## and one draw call.

const SHADER := "res://shaders/grass.gdshader"
## Clumps a side of the patch, and metres between them.
const SIDE := 150
const SPACING := 0.9
## Shown while the camera is nearer its focus than this.
const SHOW_WITHIN := 420.0
const BLADES := 4

var rig: CameraRig
var _mat: ShaderMaterial


func setup(terrain: Terrain, builder: WorldBuilder, camera_rig: CameraRig, sim: Simulation) -> void:
	name = "Grass"
	rig = camera_rig
	_mat = ShaderMaterial.new()
	_mat.shader = load(SHADER)
	_mat.set_shader_parameter("ground", ImageTexture.create_from_image(builder.ground_image()))
	_mat.set_shader_parameter("heights", builder.water_material.get_shader_parameter("seabed_height"))
	_mat.set_shader_parameter("half_size", terrain.half_size)
	if builder.lift_side > 0:
		_mat.set_shader_parameter("lift", ImageTexture.create_from_image(builder.lift_image()))
		_mat.set_shader_parameter("lift_side", builder.lift_side)
		_mat.set_shader_parameter("lift_cell", WorldBuilder.LIFT_CELL)
		_mat.set_shader_parameter("lift_color", Models.ROCK_MOSS)
	_mat.set_shader_parameter("cell", Terrain.CELL)
	_mat.set_shader_parameter("side", SIDE)
	_mat.set_shader_parameter("spacing", SPACING)
	_mat.set_shader_parameter("reach", SIDE * SPACING * 0.5)
	_mat.set_shader_parameter("wind_dir", -sim.wind_from())
	_mat.set_shader_parameter("wind_strength", clampf(sim.wind_speed / 30.0, 0.0, 1.0))

	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = _clump()
	mm.instance_count = SIDE * SIDE
	var identity := PackedFloat32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0])
	var buf := PackedFloat32Array()
	buf.resize(SIDE * SIDE * 12)
	for i in SIDE * SIDE:
		for k in 12:
			buf[i * 12 + k] = identity[k]
	mm.buffer = buf
	multimesh = mm
	material_override = _mat
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Placed in the shader: the whole map, so it is never culled by its mesh's box.
	custom_aabb = AABB(Vector3(-terrain.half_size, -50.0, -terrain.half_size),
		Vector3(terrain.half_size * 2.0, 400.0, terrain.half_size * 2.0))


func _process(_dt: float) -> void:
	visible = rig.distance < SHOW_WITHIN
	if visible:
		_mat.set_shader_parameter("centre", Vector2(rig.target_pos.x, rig.target_pos.z))


## A clump of blades a metre tall at most (the shader scales it): each one a single
## tapered triangle, leaning out a little. UV.y: 0 at the root, 1 at the tip.
static func _clump() -> ArrayMesh:
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var normals := PackedVector3Array()
	for b in BLADES:
		var a := b * TAU / BLADES + 0.4 * b
		var dir := Vector3(cos(a), 0.0, sin(a))
		var across := Vector3(-dir.z, 0.0, dir.x)
		var root := dir * 0.12 * (b % 2 + 1)
		var w := 0.07
		verts.append_array([root - across * w, root + across * w, root + dir * 0.18 + Vector3.UP])
		uvs.append_array([Vector2(0, 0), Vector2(1, 0), Vector2(0.5, 1)])
		normals.append_array([Vector3.UP, Vector3.UP, Vector3.UP])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_NORMAL] = normals
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return mesh
