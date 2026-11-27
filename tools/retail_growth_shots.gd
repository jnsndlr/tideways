extends SceneTree
## A big-box store built by town growth, then town cars driving out of its car park.
##   godot --path . --resolution 1600x1000 --script tools/retail_growth_shots.gd -- --out=DIR [--town=NAME] [--pop=N]

var main: Node
var frames := 0
var out := "user://"
var town_name := ""
var pop := 3100
var town: MapData.Town
var lot: MapData.TownLot
var step := 0
var mark := -1


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--town="):
			town_name = a.substr(7)
		elif a.begins_with("--pop="):
			pop = int(a.substr(6))
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _view(at: Vector3, dist: float, pitch: float, yaw: float) -> void:
	main.rig.focus_on(at, dist)
	main.rig.target_pos = at
	main.rig.position = at
	main.rig.distance = dist
	main.rig.target_dist = dist
	main.rig.target_pitch = pitch
	main.rig.pitch = pitch
	main.rig.target_yaw = yaw
	main.rig.yaw = yaw


func _shot(name: String) -> void:
	root.get_viewport().get_texture().get_image().save_png("%s/grow_%s.png" % [out, name])
	print("SHOT ", name)


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.get("map") == null:
		return false
	if town == null:
		# The named town, else the first with a ferry terminal and a store still to build.
		for t in main.map.towns:
			if town_name != "" and t.name != town_name:
				continue
			if town_name == "" and main.sim.terminals.get(t.id) == null:
				continue
			for l in t.growth_lots:
				if l.kind == MapData.TownLot.Kind.BIG_BOX and not l.occupied:
					town = t
					lot = l
					pop = maxi(pop, l.need_pop + 100)
					break
			if lot != null:
				break
		if lot == null and town_name == "":
			# No terminal town has a store to build: show cars at a built one instead.
			for t in main.map.towns:
				if main.sim.terminals.get(t.id) == null:
					continue
				for l in t.growth_lots:
					if l.kind == MapData.TownLot.Kind.BIG_BOX and l.occupied:
						town = t
						lot = l
						step = 3
						break
				if lot != null:
					break
		if lot == null:
			print("NO UNBUILT BIG BOX in ", town_name)
			return true
		print("TOWN ", town.name, " terminal=", main.sim.terminals.get(town.id) != null)
		print("LOT ", lot.model, " at ", lot.pos, " need ", lot.need_pop, " street stage ", WorldBuilder.street_stages(town)[lot.street])
		mark = frames
		return false
	var fwd := Vector3(sin(lot.yaw), 0, cos(lot.yaw))
	var yaw := atan2(fwd.x, fwd.z) + 0.5
	match step:
		0:
			_view(lot.pos, 260.0, 0.75, yaw)
			if frames - mark > 60:
				_shot("0_before")
				main.sim.town_growth.dev_build_speed = 40.0
				main.sim.town_growth.dev_set_population(town, pop)
				step = 1
				mark = frames
		1:
			_view(lot.pos, 160.0, 0.6, yaw)
			if frames - mark > 30:
				_shot("1_building")
				Engine.time_scale = 8.0
				step = 2
				mark = frames
		2:
			if lot.occupied and _built():
				Engine.time_scale = 1.0
				print("BUILT after ", frames - mark, " frames; street stage ", WorldBuilder.street_stages(town)[lot.street])
				step = 3
				mark = frames
			elif frames - mark > 6000:
				print("NOT BUILT")
				return true
		3:
			_view(lot.pos, 260.0, 0.75, yaw)
			if frames - mark > 40:
				_shot("2_built")
				var path := BigBoxes.drive(town, lot)
				print("DRIVE pts ", path.size(), " from ", path[0] if path.size() else null, " to ", path[-1] if path.size() else null)
				# Only the store's drive for a while: the terminal's own cars pull out of
				# the car park and head for the ferry.
				var term: Terminal = main.sim.terminals.get(town.id)
				if term == null:
					print("NO TERMINAL")
					return true
				var keep: Array[PackedVector3Array] = term._inbound.duplicate()
				term._inbound.clear()
				term.add_drive(path)
				print("INBOUND for store: ", term._inbound.size(), " has_service=", term.has_service())
				for k in 3:
					term._spawn_car()
				term._inbound = keep
				step = 4
				mark = frames
		4:
			_view(lot.pos, 140.0, 0.6, yaw)
			for t: int in [20, 60, 120, 200]:
				if frames - mark == t:
					_shot("3_cars_%d" % t)
			if frames - mark > 230:
				return true
	return false


func _built() -> bool:
	var name := "BigBox_%s_%d_%d" % [lot.model, roundi(lot.pos.x), roundi(lot.pos.z)]
	return not main.find_children(name, "Node3D", true, false).is_empty()
