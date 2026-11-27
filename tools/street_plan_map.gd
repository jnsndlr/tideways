extends SceneTree
## Top-down maps of each town's StreetPlan over its ground, 1 px per metre.
##   godot --headless --path . --script tools/street_plan_map.gd -- <seed> <out_dir>
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_value := int(args[0]) if args.size() > 0 else 123
	var out := args[1] if args.size() > 1 else "user://"
	var gen := MapGenerator.new()
	var map := gen.generate(seed_value)
	var zc := [Color(1, 0.2, 0.2), Color(1, 0.85, 0.1), Color(0.75, 0.3, 1), Color(1, 1, 1)]
	const S := 700
	for isl in map.towns:
		var plan := isl.street_plan
		if plan == null:
			continue
		var c := isl.road_main_a[-1]
		var img := Image.create(S, S, false, Image.FORMAT_RGB8)
		for y in S:
			for x in S:
				var h := gen.terrain.height_at(c.x + x - S / 2, c.z + y - S / 2)
				var col := Color(0.15, 0.3, 0.55) if h < 0.0 else (Color(0.8, 0.75, 0.55) if h < 3.2 else Color(0.25, 0.45, 0.2).lightened(clampf(h / 60.0, 0, 0.7)))
				if h >= 3.2 and int(h) % 5 == 0 and fposmod(h, 5.0) < 0.35:
					col = col.darkened(0.3)
				img.set_pixel(x, y, col)
		var px := func(p: Vector3) -> Vector2i: return Vector2i(roundi(p.x - c.x + S / 2), roundi(p.z - c.z + S / 2))
		for line in [isl.road_main_a]:
			for p in line:
				_dot(img, px.call(p), 2, Color(0.3, 0.3, 0.3))
		for e in plan.edges:
			var pts: PackedVector3Array = e.pts
			for i in pts.size() - 1:
				for s in 13:
					_dot(img, px.call(pts[i].lerp(pts[i + 1], s / 12.0)), 1, zc[e.zone])
		for n in plan.nodes:
			_dot(img, px.call(n), 2, Color.WHITE)
		img.save_png("%s/%s.png" % [out, isl.name.replace(" ", "_")])
		print("%s: %d nodes, %d streets" % [isl.name, plan.nodes.size(), plan.edges.size()])
	quit(0)


func _dot(img: Image, at: Vector2i, r: int, col: Color) -> void:
	for dy in range(-r, r + 1):
		for dx in range(-r, r + 1):
			var q := at + Vector2i(dx, dy)
			if q.x >= 0 and q.y >= 0 and q.x < img.get_width() and q.y < img.get_height():
				img.set_pixel(q.x, q.y, col)
