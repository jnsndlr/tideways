class_name FerryHullAssets
extends RefCounted
## The installed hull selects both the matching deck layout and its rendered model.

const SMALL_GLB := "res://assets/models/guemes_mid.glb"
const HIYU_GLB := "res://assets/models/hiyu_mid.glb"
const MID_GLB := "res://assets/models/ferry_mid.glb"
const ISQ_GLB := "res://assets/models/issaquah_mid.glb"
const JUMBO_GLB := "res://assets/models/jumbo_mk_ii.glb"
const BY_SIZE := ["", SMALL_GLB, HIYU_GLB, MID_GLB, ISQ_GLB, JUMBO_GLB]

static var _installed := _available_sizes()


static func available(size: int) -> bool:
	return _installed[size]


static func _available_sizes() -> Array[bool]:
	var authored := not "--classic-ferry" in OS.get_cmdline_user_args()
	var result: Array[bool] = [false]
	for size in range(1, BY_SIZE.size()):
		result.append(authored and ResourceLoader.exists(BY_SIZE[size]))
	return result
