extends RefCounted
## Route plans for one network. Empty point arrays represent an unreachable link.
## A cache miss is recoverable: the generator can always plan the curve afresh.

var routes := {}
var _path := ""
var _key := ""
var _dirty := false


func load_for(path: String, key: String) -> void:
	_path = path
	_key = key
	routes.clear()
	_dirty = false
	if path.is_empty() or not FileAccess.file_exists(path):
		return
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK or not json.data is Dictionary:
		return
	var saved: Dictionary = json.data
	if saved.get("key") != key or not saved.get("routes") is Dictionary:
		return
	for route in saved.routes:
		var points = saved.routes[route]
		if _valid_points(points):
			routes[route] = points


static func _valid_points(points: Variant) -> bool:
	if not points is Array or points.size() % 2 != 0 or points.size() == 2:
		return false
	for value in points:
		if not (value is int or value is float) or not is_finite(value):
			return false
	return true


func remember(route: String, points: Array) -> void:
	routes[route] = points
	_dirty = true


func save() -> void:
	if _path.is_empty() or not _dirty or not (OS.has_feature("editor") or _path.begins_with("user://")):
		return
	var target := ProjectSettings.globalize_path(_path)
	DirAccess.make_dir_recursive_absolute(target.get_base_dir())
	var temporary := "%s.%d.%d.tmp" % [target, OS.get_process_id(), get_instance_id()]
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		push_warning("Couldn't save planned routes to " + _path)
		return
	var written := file.store_string(JSON.stringify({"key": _key, "routes": routes}))
	file.close()
	if not written or DirAccess.rename_absolute(temporary, target) != OK:
		DirAccess.remove_absolute(temporary)
		push_warning("Couldn't replace planned routes at " + _path)
		return
	_dirty = false
