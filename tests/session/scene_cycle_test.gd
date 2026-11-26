extends SceneTree
## Opens Sandbox from the menu and returns to the menu several times in one
## process, counting live objects each time the menu is back. Anything a Sandbox
## visit leaves behind shows as the counts climbing from one visit to the next
## (the first visit also fills caches that are meant to stay, so growth is
## measured from the second return on). Fails if objects, resources or orphan
## nodes keep growing. Each return also checks that the region releases its
## slip-guide parts and the scene tree returns to its original menu size.
##
##   godot --headless --path . --fixed-fps 30 --script tests/session/scene_cycle_test.gd
##
## CYCLES (default 4) and SEED (default 123) can be set in the environment; the
## menu skips itself when there are command-line arguments, so none are used.

const SETTLE_FRAMES := 12
const PLAY_FRAMES := 90

var cycles := 4
var _visit := 0
var _wait := 0
var _in_sandbox := false
var _samples: Array[Dictionary] = []
var _regional_guide_cache: WeakRef
var _initial_menu_nodes: int
var _initial_orphans: int


func _initialize() -> void:
	if OS.get_environment("CYCLES") != "":
		cycles = maxi(int(OS.get_environment("CYCLES")), 3)
	var map_seed := int(OS.get_environment("SEED")) if OS.get_environment("SEED") != "" else 123
	RegionEntryState.sandbox_seed = map_seed
	change_scene_to_file(Scenes.MENU)
	_wait = SETTLE_FRAMES


func _process(_delta: float) -> bool:
	_wait -= 1
	if _wait > 0:
		return false
	if _in_sandbox:
		var world := current_scene as WorldSession
		if world == null or world.scene_file_path != Scenes.SANDBOX or not world.built:
			return _fail("Sandbox did not open on visit %d." % _visit)
		_regional_guide_cache = weakref(world._slip_guide_parts)
		_in_sandbox = false
		Scenes.go(self, Scenes.MENU)
		_wait = SETTLE_FRAMES
		return false
	if current_scene == null or current_scene.scene_file_path != Scenes.MENU:
		return _fail("The menu did not come back after visit %d." % _visit)
	var menu_nodes := get_node_count()
	var orphans := int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))
	if _visit == 0:
		_initial_menu_nodes = menu_nodes
		_initial_orphans = orphans
	else:
		if _regional_guide_cache.get_ref() != null:
			return _fail("Visit %d retained its regional slip-guide mesh cache." % _visit)
		if menu_nodes != _initial_menu_nodes or orphans > _initial_orphans:
			return _fail("Menu after visit %d has %d nodes and %d orphans (initially %d and %d)." % [
				_visit, menu_nodes, orphans, _initial_menu_nodes, _initial_orphans])
		var s := {
			"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
			"resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
			"nodes": menu_nodes,
			"orphans": orphans,
		}
		_samples.append(s)
		print("Back at the menu after visit %d: %d objects, %d resources, %d nodes, %d orphan nodes" % [
			_visit, s.objects, s.resources, s.nodes, s.orphans])
	if _visit == cycles:
		return _report()
	_visit += 1
	_in_sandbox = true
	Scenes.go(self, Scenes.SANDBOX)
	_wait = PLAY_FRAMES
	return false


func _report() -> bool:
	var grew := false
	for key: String in ["objects", "resources", "orphans"]:
		var per_visit: int = roundi((_samples[-1][key] - _samples[1][key]) / float(_samples.size() - 2))
		if per_visit > 0:
			grew = true
			push_error("Each Sandbox visit leaves about %d more %s behind." % [per_visit, key])
	if not grew:
		print("TEST PASSED")
		print("Leaving Sandbox leaves nothing behind (%d visits)." % cycles)
	quit(1 if grew else 0)
	return true


func _fail(why: String) -> bool:
	push_error(why)
	quit(1)
	return true
