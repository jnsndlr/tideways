extends SceneTree
## Plans every route between the terminals of the authored map for each scenario
## Play can start, and saves them to maps/routes/ (MapGenerator.route_cache_path),
## so the game loads them instead of planning. Run it after moving islands; Play
## also replans and rewrites a stale file on a desktop run.
##
##   godot --headless --path . --script tools/bake_routes.gd [-- --force]

const SCENARIOS := ["opening", "two_boats", "shared_slip", "lane_sharing", "mission_trial", "mission_sandbox", "tie_up_pier", "full-network"]   # full-network: no scenario (--full-network)


func _initialize() -> void:
	var force := "--force" in OS.get_cmdline_user_args()
	var layout := MapLayout.load_file(MapLayout.MAIN_STORY)
	for plan: String in SCENARIOS:
		var gen := MapGenerator.new()
		gen.route_cache_path = "res://maps/routes/%s-%s.json" % [MapLayout.MAIN_STORY.get_file().get_basename(), plan]
		if force and FileAccess.file_exists(gen.route_cache_path):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(gen.route_cache_path))
		var scenario: Scenario = null if plan == "full-network" else Scenario.load_file("res://maps/%s.json" % plan)
		var t0 := Time.get_ticks_msec()
		var map := gen.generate_from(layout.duplicate(), scenario.region_plan() if scenario else null)
		print("%s: %d routes in %d ms" % [plan, map.routes.size(), Time.get_ticks_msec() - t0])
	quit(0)
