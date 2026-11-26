extends SceneTree
## A trailer needs a separate mesh per paint only when the artwork takes paint.

func _initialize() -> void:
	var library := ModelParts.library(RoadVehicleModel.ASSET)
	for model: String in RoadVehicleModel.TRAILERS:
		var key := model.replace("_", "")
		var takes_paint := library.has(key + "body") or library.has(key + "accent")
		var first := RoadVehicleModel.body_mesh(model, 0)
		var first_colors: PackedColorArray = first.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
		for paint in range(1, RoadVehicleModel.PAINTS.size()):
			var mesh := RoadVehicleModel.body_mesh(model, paint)
			if takes_paint:
				if mesh == first or mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR] == first_colors:
					push_error("%s lost its livery for paint %d" % [model, paint])
					quit(1)
					return
			elif mesh != first:
				push_error("%s allocated a second fixed mesh for paint %d" % [model, paint])
				quit(1)
				return
	print("TEST PASSED")
	quit(0)
