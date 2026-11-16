extends SceneTree
## The same woods by day and low sun, to match the colours of the trees' levels of
## detail: force every pine to one level with --mpine (e.g. near only:
## --mpine=1e5,1e5,1e5; card only: --mpine=0.01,0.02,0.03) and compare. Prints each
## shot's mean colour over the woods (the middle of the frame).
##   godot --path . --rendering-driver vulkan --resolution 1600x1000 --script tools/lod_shots.gd -- --out=DIR --tag=X [--mpine=..] [--dist=M] [--hide=Pines?_*,+*_shadow] [--hours=6,9.5] [--yaws=0,90,180,270]

var main: Node
var out := "user://"
var tag := "lod"
var frames := 0
var dist := 260.0
var shot := 0
var hide := ""
var hours := PackedFloat64Array()
var yaws := PackedFloat64Array()
# hour, yaw, pitch
var shots := [[12.0, 0, 28], [7.5, 180, 28], [12.0, 0, 55]]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--tag="):
			tag = a.substr(6)
		elif a.begins_with("--hide="):
			hide = a.substr(7)
		elif a.begins_with("--hours="):
			# Shots at these hours instead, each from every heading in --yaws (0).
			hours = a.substr(8).split_floats(",")
		elif a.begins_with("--yaws="):
			yaws = a.substr(7).split_floats(",")
		elif a.begins_with("--dist="):
			dist = a.substr(7).to_float()
	if not hours.is_empty() or not yaws.is_empty():
		shots = []
		for h in hours if not hours.is_empty() else PackedFloat64Array([12.0]):
			for y in yaws if not yaws.is_empty() else PackedFloat64Array([0.0]):
				shots.append([h, y, 28])
	DirAccess.make_dir_recursive_absolute(out)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames >= 20 and frames % 25 == 0:
		if shot > 0:
			var img := root.get_viewport().get_texture().get_image()
			img.save_png("%s/%s_%d.png" % [out, tag, shot - 1])
			var sum := Vector3.ZERO
			var n := 0
			for y in range(img.get_height() / 4, img.get_height() * 3 / 4, 4):
				for x in range(img.get_width() / 4, img.get_width() * 3 / 4, 4):
					var c := img.get_pixel(x, y)
					sum += Vector3(c.r, c.g, c.b)
					n += 1
			var m := sum / n
			var sun: Vector3 = main.day_cycle.sun.global_transform.basis.z
			print("LODSHOT %s_%d hour %.1f yaw %d mean %.3f %.3f %.3f sun_up %.2f" % [tag, shot - 1, shots[shot - 1][0], shots[shot - 1][1], m.x, m.y, m.z, sun.normalized().y])
		if shot >= shots.size():
			return true
		# A leading + shows what an earlier pattern hid (e.g. the trees' shadow casters).
		for nm in hide.split(",", false):
			for c in main.find_children(nm.trim_prefix("+"), "", true, false):
				c.visible = nm.begins_with("+")
		var s: Array = shots[shot]
		main.day_cycle.set_hour(s[0])
		main.day_cycle.apply(main.day_cycle.hour())
		main.editor._clear_sky(true)
		main.rig.target_pos = Vector3(3000, 0, -50)
		main.rig.target_dist = dist
		main.rig.target_yaw = deg_to_rad(s[1])
		main.rig.target_pitch = deg_to_rad(s[2])
		main.rig.snap()
		shot += 1
	return false
