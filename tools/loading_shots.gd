extends SceneTree
## Opens the loading screen into the main map and saves frames along the way.
##   godot --path . --resolution 1600x960 --script tools/loading_shots.gd -- --out=DIR

var out := "user://"
var frames := 0
var shot := 0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out)
	LoadingScreen.open(self, Scenes.MAIN_MAP, "Setting out for the islands")


func _process(_delta: float) -> bool:
	frames += 1
	if frames in [5, 30, 60] or (frames > 60 and frames % 40 == 0):
		root.get_viewport().get_texture().get_image().save_png("%s/load_%d.png" % [out, shot])
		shot += 1
	return shot >= 8
