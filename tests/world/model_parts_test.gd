extends SceneTree
## Compare the game-facing mesh to the authored GLB, so the artwork may evolve.

func _initialize() -> void:
	var asset := (load(SeagullModel.ASSET) as PackedScene).instantiate()
	var source: Mesh
	for node: MeshInstance3D in asset.find_children("*", "MeshInstance3D", true, false):
		if String(node.name).to_lower() == "seagull":
			source = node.mesh
			break
	asset.free()
	if not source:
		push_error("The authored gull part is missing")
		quit(1)
		return

	var input := source.surface_get_arrays(0)
	var indices: PackedInt32Array = input[Mesh.ARRAY_INDEX]
	var vertices: PackedVector3Array = input[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = input[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = input[Mesh.ARRAY_COLOR]
	var merged := ModelParts.merge_named(SeagullModel.ASSET, ["seagull"])
	if indices.is_empty() or merged.verts.size() != indices.size() or merged.normals.size() != indices.size() or merged.colors.size() != indices.size():
		push_error("Flattened gull geometry must have one vertex, normal and color per triangle index")
		quit(1)
		return
	for i in indices.size():
		var j := indices[i]
		if merged.verts[i] != vertices[j] or merged.normals[i] != normals[j] or not merged.colors[i].is_equal_approx(colors[j].linear_to_srgb()):
			push_error("Flattened gull geometry lost its indexed position, normal or sRGB color at index %d" % i)
			quit(1)
			return

	var library := ModelParts.library(SeagullModel.ASSET)
	var cached: MeshBuilder = library["seagull"]
	var first_vertex := vertices[indices[0]]
	merged.verts[0] += Vector3.ONE
	var fresh := ModelParts.merge_named(SeagullModel.ASSET, ["seagull"])
	if cached.verts[0] != first_vertex or fresh.verts[0] != first_vertex:
		push_error("Editing a merged part changed the cached or freshly loaded geometry")
		quit(1)
		return

	var mesh := ModelParts.shader_mesh(SeagullModel.ASSET, "seagull", Models.vc_material())
	if mesh.get_surface_count() != 1 or mesh.surface_get_material(0) != Models.vc_material():
		push_error("Indexed gull mesh lost its shader surface")
		quit(1)
		return
	var output := mesh.surface_get_arrays(0)
	for channel in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_INDEX, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_TEX_UV2]:
		if input[channel] == null or input[channel].is_empty() or output[channel] != input[channel]:
			push_error("Indexed gull mesh must retain authored shader channel %d" % channel)
			quit(1)
			return
	print("TEST PASSED")
	quit(0)
