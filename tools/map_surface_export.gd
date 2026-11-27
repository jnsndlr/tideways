extends SceneTree
## Read-only export of built-world geometry for map_surface_audit.py.
## Shared resources are written once. Each placed instance keeps its transform.

var _geometry: FileAccess
var _meshes := {}
var _instances := []
var _skipped := {}


func _initialize() -> void:
	_export.call_deferred()


func _export() -> void:
	if (
		RenderingServer.get_current_rendering_method() == "dummy"
		or DisplayServer.get_name() == "headless"
	):
		push_error(
			"Use a rendering window; the dummy renderer discards MultiMesh placement transforms"
		)
		quit(1)
		return
	var options := Scenes.launch_options.values
	var directory: String = options.get("out", "")
	if directory.is_empty() or DirAccess.make_dir_recursive_absolute(directory) != OK:
		push_error("Pass --out=<audit-directory>")
		quit(1)
		return
	SaveGame._path = directory.path_join("audit-save.json")
	_geometry = FileAccess.open(directory.path_join("triangles.bin"), FileAccess.WRITE)
	if not _geometry:
		quit(1)
		return
	var scene := Scenes.SANDBOX if options.has("seed") else Scenes.MAIN_MAP
	if change_scene_to_file(scene) != OK:
		quit(1)
		return
	await scene_changed
	var session := current_scene as WorldSession
	while not session.built:
		await process_frame
	# Let deferred light and view installation finish before traversing or unloading.
	await process_frame
	await process_frame
	var world := session.builder.root
	for item in world.find_children("*", "GeometryInstance3D", true, false):
		var node := item as GeometryInstance3D
		var path := String(world.get_path_to(node))
		var group := path.get_slice("/", 0)
		if not node.is_visible_in_tree():
			_skip("hidden")
		elif node.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			_skip("shadow only")
		elif group in ["Water", "WaterRing", "SeaFloor", "RouteOverlay", "NightLights"]:
			_skip(group)
		elif group.begins_with("Pines") or group.begins_with("RoundTrees"):
			_skip("trees and LOD")
		elif node is MeshInstance3D and node.mesh:
			_record(node.mesh, node.global_transform, path, group)
		elif node is MultiMeshInstance3D and node.multimesh and node.multimesh.mesh:
			if not options.has("rocks") and (group.begins_with("Shore") or group == "Rocks"):
				_skip("scattered rocks and cliffs")
				continue
			var mm: MultiMesh = node.multimesh
			var n := (
				mm.instance_count if mm.visible_instance_count < 0 else mm.visible_instance_count
			)
			for i in n:
				_record(mm.mesh, node.global_transform * mm.get_instance_transform(i), path, group)
	_geometry.close()
	var manifest := FileAccess.open(directory.path_join("map.json"), FileAccess.WRITE)
	if not manifest:
		quit(1)
		return
	manifest.store_string(
		JSON.stringify(
			{
				"seed": session.sim.map.map_seed,
				"scenario": session.save_scenario,
				"meshes": _meshes.values(),
				"instances": _instances,
				"skipped_nodes": _skipped
			}
		)
	)
	manifest.close()
	print("SURFACE EXPORT: ", _instances.size(), " placed meshes, seed ", session.sim.map.map_seed)
	session.queue_free()
	await process_frame
	await process_frame
	quit()


func _skip(reason: String) -> void:
	_skipped[reason] = int(_skipped.get(reason, 0)) + 1


func _record(mesh: Mesh, xf: Transform3D, path: String, group: String) -> void:
	var key := mesh.get_instance_id()
	if not _meshes.has(key):
		var faces := mesh.get_faces()
		_meshes[key] = {
			"index": _meshes.size(), "offset": _geometry.get_position(), "count": faces.size()
		}
		_geometry.store_buffer(faces.to_byte_array())
	_instances.append(
		{
			"mesh": _meshes[key].index,
			"path": path,
			"group": group,
			"transform":
			[
				xf.basis.x.x,
				xf.basis.x.y,
				xf.basis.x.z,
				xf.basis.y.x,
				xf.basis.y.y,
				xf.basis.y.z,
				xf.basis.z.x,
				xf.basis.z.y,
				xf.basis.z.z,
				xf.origin.x,
				xf.origin.y,
				xf.origin.z
			]
		}
	)
