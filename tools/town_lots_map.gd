extends SceneTree


## Top-down maps of each town's blocks and frontage lots, 1 px per metre.
## Lots shaded by reveal rank (bright = early), corners outlined white, streets dark.
##   godot --headless --path . --script tools/town_lots_map.gd -- <seed> <out_dir> [town filter]
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var seed_value := int(args[0]) if args.size() > 0 else 123
	var out := args[1] if args.size() > 1 else "user://"
	var only := args[2] if args.size() > 2 else ""
	var gen := MapGenerator.new()
	var map := gen.generate(seed_value)
	const S := 800
	for isl in map.towns:
		var plan := isl.street_plan
		if plan == null or (only != "" and not isl.name.contains(only)):
			continue
		var t0 := Time.get_ticks_msec()
		var tl := TownLots.build(plan, gen.terrain, plan._sq)
		var ms := Time.get_ticks_msec() - t0
		var c := plan._sq
		var img := Image.create(S, S, false, Image.FORMAT_RGB8)
		var bcol := {}
		for y in S:
			for x in S:
				var wx := c.x + x - S / 2
				var wz := c.z + y - S / 2
				var hh := gen.terrain.height_at(wx, wz)
				var col := (
					Color(0.15, 0.3, 0.55)
					if hh < 0.0
					else (Color(0.8, 0.75, 0.55) if hh < 3.2 else Color(0.3, 0.45, 0.25))
				)
				var k := tl._idx(tl.cell_of(Vector2(wx, wz)))
				if k >= 0:
					if tl.owner[k] == TownLots.ROAD:
						col = Color(0.2, 0.2, 0.22)
					elif tl.block_of[k] >= 0:
						var b := tl.block_of[k]
						if not bcol.has(b):
							bcol[b] = Color.from_hsv(fmod(b * 0.618, 1.0), 0.25, 0.55)
						col = bcol[b]
				img.set_pixel(x, y, col)
		var n := maxf(1.0, tl.lots.size() - 1)
		var px := func(p: Vector2) -> Vector2: return Vector2(p.x - c.x + S / 2, p.y - c.z + S / 2)
		for lot in tl.lots:
			var q: PackedVector2Array = lot.quad
			var poly := PackedVector2Array()
			for p in q:
				poly.append(px.call(p))
			var f: float = float(lot.rank) / n
			var fill := Color.from_hsv(0.08 + 0.55 * f, 0.75, 1.0 - 0.45 * f)
			_fill(img, poly, fill)
			var edge_col := Color.WHITE if lot.corner else fill.darkened(0.55)
			for i in 4:
				_line(img, poly[i], poly[(i + 1) % 4], edge_col)
			_line(img, poly[0], poly[1], Color(0.1, 0.1, 0.1))  # street face
		img.save_png("%s/lots_%s.png" % [out, isl.name.replace(" ", "_")])
		var corners := tl.lots.filter(func(l: Dictionary) -> bool: return l.corner).size()
		print(
			(
				"%s: %d blocks, %d lots (%d corner), %d ms"
				% [isl.name, tl.block_count, tl.lots.size(), corners, ms]
			)
		)
	quit(0)


func _fill(img: Image, poly: PackedVector2Array, col: Color) -> void:
	var lo := poly[0].min(poly[1]).min(poly[2]).min(poly[3])
	var hi := poly[0].max(poly[1]).max(poly[2]).max(poly[3])
	for y in range(maxi(0, floori(lo.y)), mini(img.get_height(), ceili(hi.y) + 1)):
		for x in range(maxi(0, floori(lo.x)), mini(img.get_width(), ceili(hi.x) + 1)):
			if Geometry2D.is_point_in_polygon(Vector2(x + 0.5, y + 0.5), poly):
				img.set_pixel(x, y, col)


func _line(img: Image, a: Vector2, b: Vector2, col: Color) -> void:
	var steps := maxi(1, ceili(a.distance_to(b)))
	for s in steps + 1:
		var p := a.lerp(b, float(s) / steps)
		if p.x >= 0 and p.y >= 0 and p.x < img.get_width() and p.y < img.get_height():
			img.set_pixel(int(p.x), int(p.y), col)
