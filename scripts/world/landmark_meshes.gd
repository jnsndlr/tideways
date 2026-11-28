class_name LandmarkMeshes
extends RefCounted
## Landmark meshes shared by initial and newly constructed buildings in one region.

var _landmark_meshes := {}


## Cached baked mesh + foundation plinth for milestone landmark GLBs.
func mesh_for(model_name: String) -> ArrayMesh:
	if _landmark_meshes.has(model_name):
		return _landmark_meshes[model_name]
	var path := ""
	if WorldBuilder.SHOP_SHELLS.has(model_name):
		path = WorldBuilder.shop_path(model_name)
	else:
		path = "res://assets/models/%s.glb" % model_name
	if not ResourceLoader.exists(path):
		return null
	var mb := MeshBuilder.new()
	Models._append_part(mb, ModelParts.baked(path), Transform3D.IDENTITY)
	var temp := mb.commit()
	var aabb := temp.get_aabb()
	var pad_w := clampf(aabb.size.x * 0.92, 3.0, 26.0)
	var pad_d := clampf(aabb.size.z * 0.92, 3.0, 26.0)
	var cx := aabb.position.x + aabb.size.x * 0.5
	var cz := aabb.position.z + aabb.size.z * 0.5
	mb.box(
		Vector3(cx, -WorldBuilder.KIT_MAX_DROP * 0.5 + 0.05, cz),
		Vector3(pad_w, WorldBuilder.KIT_MAX_DROP, pad_d),
		Models.KIT_FOUNDATION
	)
	var mesh := mb.commit()
	_landmark_meshes[model_name] = mesh
	return mesh
