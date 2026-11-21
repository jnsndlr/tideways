class_name ModelParts
extends RefCounted
## Reads the named meshes that Jon authors in Blender. Names compare without case,
## spaces or underscores; all coordinates stay in each part's own frame.

static var _libraries := {}


## Groups reused for multiple liveries or assemblies. Treat cached parts as read-only.
static func library(path: String) -> Dictionary:
	if _libraries.has(path):
		return _libraries[path]
	var parts := {}
	var root := (load(path) as PackedScene).instantiate()
	for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var builder := MeshBuilder.new()
		_append_triangles(builder, node.mesh)
		parts[_key(node)] = builder
	root.free()
	_libraries[path] = parts
	return parts


## Fresh triangles for callers that paint or transform selected parts. Preserve source order.
static func merge_named(path: String, names: Array) -> MeshBuilder:
	var builder := MeshBuilder.new()
	var root := (load(path) as PackedScene).instantiate()
	for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if _key(node) in names:
			_append_triangles(builder, node.mesh)
	root.free()
	return builder


## Every mesh in `path` flattened into one builder in the scene root's frame, its
## node transforms applied. Surfaces without vertex colours take their material's
## albedo, for models painted with materials rather than vertex colours. Cached.
static func baked(path: String) -> MeshBuilder:
	var key := "baked:" + path
	if _libraries.has(key):
		return _libraries[key]
	var builder := MeshBuilder.new()
	var root := (load(path) as PackedScene).instantiate()
	for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var xf := Transform3D.IDENTITY
		var n: Node = node
		while n != root and n is Node3D:
			xf = (n as Node3D).transform * xf
			n = n.get_parent()
		var part := MeshBuilder.new()
		for surface in node.mesh.get_surface_count():
			var mat := node.get_active_material(surface)
			var paint := Color(0.94, 0.95, 0.94)
			if mat is BaseMaterial3D:
				paint = (mat as BaseMaterial3D).albedo_color
			var start := part.colors.size()
			_append_surface(part, node.mesh, surface)
			for i in range(start, part.colors.size()):
				if part.colors[i].a < 0.0:
					part.colors[i] = paint
		Models._append_part(builder, part, xf)
	root.free()
	_libraries[key] = builder
	return builder


## The animated wildlife shaders need the original indices, UVs and smooth normals.
static func shader_mesh(path: String, name: String, material: Material) -> ArrayMesh:
	var root := (load(path) as PackedScene).instantiate()
	var mesh := ArrayMesh.new()
	for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if _key(node) != name:
			continue
		var arrays := node.mesh.surface_get_arrays(0)
		var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
		for i in colors.size():
			colors[i] = colors[i].linear_to_srgb()
		arrays[Mesh.ARRAY_COLOR] = colors
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, material)
	root.free()
	return mesh


static func _key(node: Node) -> String:
	return String(node.name).to_lower().replace(" ", "").replace("_", "")


static func _append_triangles(builder: MeshBuilder, mesh: Mesh) -> void:
	for surface in mesh.get_surface_count():
		_append_surface(builder, mesh, surface, Color(0.94, 0.95, 0.94))


## One surface's triangles; vertices without colours take `fallback` (alpha -1 marks
## them for `baked` to paint).
static func _append_surface(builder: MeshBuilder, mesh: Mesh, surface: int, fallback := Color(0, 0, 0, -1)) -> void:
	var arrays := mesh.surface_get_arrays(surface)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR] if arrays[Mesh.ARRAY_COLOR] != null else PackedColorArray()
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
	var count := indices.size() if not indices.is_empty() else vertices.size()
	for k in count:
		var i := indices[k] if not indices.is_empty() else k
		builder.verts.append(vertices[i])
		builder.normals.append(normals[i])
		builder.colors.append(colors[i].linear_to_srgb() if not colors.is_empty() else fallback)
