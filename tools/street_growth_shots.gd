extends SceneTree
## A town at several stages of growth, its streets revealing and paving as lots build
## (WorldBuilder.refresh_streets). For checking by eye.
## godot --path . --script tools/street_growth_shots.gd -- --out=DIR [--towns=Tern,Lumber
## Bay] [--dist=M]

const STAGES := [0, 30, 90, 200, 400]  # extra lots built, in rank order

var main: Node
var frames := 0
var out := "user://"
var dist := 330.0
var names: PackedStringArray = ["Tern", "Lumber Bay", "Bramble Bay"]
var _jobs: Array = []  # [town, stage index]
var _wait := 0
var _built := 0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=")
		match kv[0]:
			"--out":
				out = kv[1]
			"--towns":
				names = kv[1].split(",")
			"--dist":
				dist = float(kv[1])
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _find(n: String) -> MapData.Town:
	for t in main.sim.map.towns:
		if (
			(t.name.begins_with(n) or main.sim.map.islands[t.island].name.begins_with(n))
			and t.street_plan != null
		):
			return t
	return null


## Builds the next `n` free house/shop lots of `town` straight away.
func _build_lots(town: MapData.Town, n: int) -> void:
	var tc: TownConstruction = main.find_child("TownConstruction", true, false)
	for lot in town.growth_lots:
		if n <= 0:
			return
		if lot.occupied or lot.kind == MapData.TownLot.Kind.LANDMARK:
			continue
		lot.occupied = true
		var job := TownGrowth.BuildJob.new()
		job.lot = lot
		job.kind = lot.kind
		job.town_id = town.id
		tc._on_construction_completed(job)
		n -= 1


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	if _jobs.is_empty() and _built == 0:
		for n in names:
			var t := _find(n)
			if t == null:
				var all := []
				for x in main.sim.map.towns:
					all.append(
						(
							"%s/%s(%s)"
							% [x.name, main.sim.map.islands[x.island].name, x.street_plan != null]
						)
					)
				push_warning("No town named %s; have %s" % [n, all])
				continue
			var free := 0
			for l in t.growth_lots:
				free += 0 if l.occupied else 1
			print(
				(
					"%s: plan lots %d, edges %d, growth lots %d (free %d), per edge %s, built %s, pop %d"
					% [
						n,
						t.town_lots.lots.size() if t.town_lots else -1,
						t.street_plan.edges.size(),
						t.growth_lots.size(),
						free,
						t.street_lots,
						t.street_built,
						t.population
					]
				)
			)
			for i in STAGES.size():
				_jobs.append([t, i])
		_built = 1
		main.sim.minutes = 13.0 * 60.0
	if _wait > 0:
		_wait -= 1
		return false
	if _jobs.is_empty():
		quit(0)
		return true
	var head: Array = _jobs[0]
	var t: MapData.Town = head[0]
	var i: int = head[1]
	if head.size() == 2:
		var prev: int = STAGES[i - 1] if i > 0 else 0
		_build_lots(t, STAGES[i] - prev)
		main.rig.follow = null
		main.rig.target_pos = t.town_center
		main.rig.target_dist = dist
		main.rig.target_pitch = 0.95
		main.rig.target_yaw = atan2(t.town_axis.x, t.town_axis.z) + 0.6
		main.rig.snap()
		head.append(true)
		_wait = 20
		return false
	var file := "%s/%s_%d.png" % [out, t.name.replace(" ", "_"), STAGES[i]]
	root.get_viewport().get_texture().get_image().save_png(file)
	var stages := []
	for e in t.street_plan.edges.size():
		stages.append(WorldBuilder.street_stages(t)[e])
	print("Saved %s  streets %s" % [file, stages])
	_jobs.pop_front()
	return false
