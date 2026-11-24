extends WorldSession
## A generated region, with its seed retained across direct scene loads.

## Direct-load tools set this before instantiating the scene.
static var map_seed: int:
	get: return RegionEntryState.sandbox_seed
	set(value): RegionEntryState.sandbox_seed = value


func _ready() -> void:
	SessionDiagnostics.attach(self)
	var options := Scenes.launch_options.values
	if RegionEntryState.sandbox_seed == 0:
		RegionEntryState.sandbox_seed = int(options["seed"]) if options.has("seed") else randi_range(1, 99999)
	await start_generated(RegionEntryState.sandbox_seed)


## The HUD's opening toast: [title, body].
func intro(islands: int) -> Array:
	return ["PROCEDURAL ARCHIPELAGO", "Map seed %d · %d islands · %d routes.\nPress G for a new map." % [
		map.map_seed, islands, map.routes.size()]]


func regenerate() -> void:
	Engine.time_scale = 1.0
	RegionEntryState.sandbox_seed = randi_range(1, 99999)
	get_tree().reload_current_scene()
