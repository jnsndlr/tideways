extends SceneTree

const Memo := preload("res://scripts/map/route_memo.gd")

class InterruptedSearch extends MapGenerator:
	func _direct_curve(_pa: Vector3, _na: Vector3, _pb: Vector3, _nb: Vector3, _id: int, _fraction: float) -> Curve3D:
		cancel()
		return null


var failures := 0
var rows := 0


func _initialize() -> void:
	var path := "user://route-memo-test-%d.json" % OS.get_process_id()
	var memo := Memo.new()
	var key := "fixture"
	for invalid in ["{", "[]", '{"key":"fixture","routes":[]}']:
		_write(path, invalid)
		memo.load_for(path, key)
		_check(memo.routes.is_empty(), "Invalid cache must fall back to planning.")
	_write(path, JSON.stringify({"key": key, "routes": {
		"valid": [0, 0, 10, 20], "unreachable": [], "odd": [1, 2, 3],
		"one point": [0, 0], "wrong type": {}, "bad coordinate": [0, 1, 2, "3"]
	}}))
	memo.load_for(path, key)
	_check(memo.routes.size() == 2 and memo.routes.has("valid") and memo.routes.has("unreachable"),
		"Only complete, numeric curves and known unreachable links should survive.")
	memo.remember("new", [1, 2, 3, 4])
	memo.save()
	memo.load_for(path, key)
	_check(memo.routes.has("new") and memo.routes.has("valid"), "A saved cache must retain prior routes.")
	memo.load_for(path, "another layout")
	_check(memo.routes.is_empty(), "Different inputs must invalidate the cache.")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

	var layout := MapLayout.new()
	var scenario := Scenario.new()
	var first_site := MapGenerator._route_cache_key(layout, scenario)
	scenario.docks["island-2"] = 2
	_check(MapGenerator._route_cache_key(layout, scenario) != first_site, "Moving a terminal to another dock must invalidate the route plan.")
	var generator := InterruptedSearch.new()
	generator._scenario = Scenario.new()
	generator._route_curve(Vector3.ZERO, Vector3.RIGHT, Vector3(400, 0, 0), Vector3.LEFT)
	_check(generator._memo.routes.is_empty(), "An interrupted search must never record an unreachable route.")
	var planner := RoutePlanner.new(Terrain.new(12, 120.0), 120.0, _cancel_grid)
	_check(rows == 3 and planner.dist.is_empty(), "Cold planning should stop during terrain sampling.")
	if failures == 0:
		print("TEST PASSED")
	quit(int(failures > 0))


func _cancel_grid() -> bool:
	rows += 1
	return rows >= 3


func _write(path: String, contents: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(contents)


func _check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
