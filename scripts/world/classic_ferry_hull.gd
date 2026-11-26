class_name ClassicFerryHull
extends RefCounted
## Builds the procedural hull, deck and superstructure for each ferry class.


static func build(fc: FerryClass) -> MeshBuilder:
	var mb := MeshBuilder.new()
	var b := fc.half_beam
	var l := fc.half_length
	var hull := PackedVector2Array(
		[
			Vector2(-b, -(l - fc.chamfer)),
			Vector2(-(b - fc.end_in), -l),
			Vector2(b - fc.end_in, -l),
			Vector2(b, -(l - fc.chamfer)),
			Vector2(b, l - fc.chamfer),
			Vector2(b - fc.end_in, l),
			Vector2(-(b - fc.end_in), l),
			Vector2(-b, l - fc.chamfer)
		]
	)
	if fc.portal:
		# Dark to the deck, the green running up the bulwarks.
		mb.extrude(hull, -4.2, 1.65, Models.HULL_DARK, Color(0, 0, 0, 0), 0.8)
		mb.extrude(hull, 1.65, 2.85, Models.WSF_GREEN, Color(0.42, 0.44, 0.47))
	else:
		mb.extrude(hull, -4.2, 0.45, Models.HULL_DARK, Color(0, 0, 0, 0), 0.8)
		mb.extrude(hull, 0.45, 1.65, Models.WSF_GREEN, Color(0, 0, 0, 0))
		mb.extrude(hull, 1.65, 2.85, Models.WHITE, Color(0.42, 0.44, 0.47))
	if fc.open_deck:
		_open_ferry(mb, fc)
	elif fc.portal:
		_portal_ferry(mb, fc)
	else:
		_full_ferry(mb, fc)
	return mb


## Sizes 3-5: an enclosed car deck with open galleries above, a passenger deck over
## it all, a sun-deck cabin, wheelhouses at both ends and the funnel(s) amidships.
static func _full_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	var b := fc.half_beam
	var l := fc.half_length
	mb.box(Vector3(0, 3.0, 0), Vector3(2.0 * b - 1.8, 0.3, 2.0 * (l - 9.0)), Color(0.45, 0.47, 0.5))
	# Car deck side walls with an open gallery above.
	for x: float in [-(b - 0.45), b - 0.45]:
		mb.box(Vector3(x, 5.1, 0), Vector3(0.9, 3.9, 2.0 * (l - 13.5)), Models.WHITE)
		for z in fc.gallery:
			mb.box(Vector3(x, 8.4, z), Vector3(0.9, 3.0, 1.2), Models.WHITE)
	# Passenger deck
	mb.box(Vector3(0, 10.05, 0), Vector3(2.0 * b + 1.05, 0.9, 2.0 * (l - 14.7)), Models.WSF_GREEN)
	mb.box(Vector3(0, 12.9, 0), Vector3(2.0 * b + 0.6, 4.8, 2.0 * (l - 15.0)), Models.WHITE)
	mb.box(Vector3(0, 13.2, 0), Vector3(2.0 * b + 0.9, 1.8, 2.0 * (l - 17.4)), Models.WINDOW_LIT)
	# Sun deck and upper cabin
	mb.box(Vector3(0, 17.1, 0), Vector3(2.0 * b - 6.0, 3.6, 2.0 * fc.sun_half), Models.WHITE)
	mb.box(
		Vector3(0, 17.4, 0),
		Vector3(2.0 * b - 5.7, 1.35, 2.0 * fc.sun_half - 4.2),
		Models.WINDOW_LIT
	)
	# Wheelhouses at both ends
	var ww := 2.0 * fc.wheel_half_w
	for z: float in [-fc.wheel_z, fc.wheel_z]:
		mb.box(Vector3(0, 20.55, z), Vector3(ww, 3.3, 7.2), Models.WHITE)
		mb.box(Vector3(0, 20.85, z), Vector3(ww + 0.3, 1.35, 7.5), Models.WINDOW_LIT)
		mb.box(Vector3(0, 24.9, z), Vector3(0.45, 5.4, 0.45), Models.WHITE)
	# Funnels
	for z in fc.funnels:
		mb.box(Vector3(0, 22.2, z), Vector3(4.8, 6.6, 7.8), Models.WHITE)
		mb.box(Vector3(0, 25.05, z), Vector3(4.95, 1.05, 7.95), Models.WSF_GREEN)
		mb.box(Vector3(0, 26.4, z), Vector3(5.1, 1.5, 8.1), Color(0.1, 0.1, 0.1))
	# Lifeboats
	for x: float in [-(b - 2.1), b - 2.1]:
		for z in fc.lifeboats:
			mb.box(Vector3(x, 19.5, z), Vector3(2.4, 1.5, 6.6), Color(0.95, 0.45, 0.12))


## The car deck of sizes 1 and 2, open to the sky at the ends: between bulwarks,
## with lane stripes down it.
static func _open_car_deck(mb: MeshBuilder, fc: FerryClass, bulwark := Models.WHITE) -> void:
	var b := fc.half_beam
	var l := fc.half_length
	var deck_col := Color(0.45, 0.47, 0.5)
	var deck_l := l - 7.2
	mb.box(Vector3(0, 3.0, 0), Vector3(2.0 * b - 1.2, 0.3, 2.0 * deck_l), deck_col)
	for z: float in [-1.0, 1.0]:
		mb.box(
			Vector3(0, 2.97, z * (deck_l + 3.3)),
			Vector3(2.0 * (b - fc.end_in) - 0.6, 0.24, 6.6),
			deck_col
		)
	# Lane stripes, stopping short of the ends.
	for c in range(fc.cols.size() - 1):
		var x := (fc.cols[c] + fc.cols[c + 1]) * 0.5
		mb.box(Vector3(x, 3.18, 0), Vector3(0.18, 0.06, 2.0 * deck_l - 3.0), Color(0.9, 0.9, 0.85))
	# Bulwarks along both sides, open at the ends for the cars, with a life ring.
	var bl := l - fc.chamfer + 0.9
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * (b - 0.36), 4.35, 0), Vector3(0.72, 2.7, 2.0 * bl), bulwark)
		mb.box(
			Vector3(x * (b - 0.36), 5.76, 0), Vector3(0.9, 0.18, 2.0 * bl), bulwark.lightened(0.15)
		)
		for z: float in [-1.0, 1.0]:
			mb.box(
				Vector3(x * (b + 0.03), 4.2, z * (bl - 3.6)),
				Vector3(0.18, 1.5, 1.5),
				Color(0.95, 0.45, 0.12)
			)


## Size 1: the open car deck, the wheelhouse up on a stair column on the +X side
## and the exhaust stack standing against the -X bulwark.
static func _open_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	_open_car_deck(mb, fc)
	# Posts for the deck lamps on the -X side.
	for lp: Array in fc.lamps:
		var p: Vector3 = lp[0]
		if p.x < 0.0:
			mb.box(Vector3(p.x - 0.09, 6.0, p.z), Vector3(0.48, 6.0, 0.48), Models.WHITE)
	# The house.
	var hx := fc.house_x
	var hw := fc.house_half_w
	var wy := fc.wheel_y
	var whw := fc.wheel_half_w_open()
	# Stair column, with a door at deck level and a railed landing halfway.
	mb.box(
		Vector3(hx, (3.0 + wy) * 0.5, 0),
		Vector3(2.0 * hw, wy - 3.0, 2.0 * fc.house_half_len),
		Models.WHITE
	)
	mb.box(Vector3(hx - hw - 0.03, 5.55, 0), Vector3(0.12, 4.5, 2.1), Color(0.55, 0.57, 0.6))
	mb.box(
		Vector3(hx, 7.8, 0),
		Vector3(2.0 * hw + 1.5, 0.24, 2.0 * fc.house_half_len + 1.5),
		Models.WSF_GREEN
	)
	# Wheelhouse, with windows all round, and its mast.
	var top := wy + fc.wheel_h
	mb.box(
		Vector3(hx, wy + 0.12, 0),
		Vector3(2.0 * whw + 0.9, 0.24, 2.0 * fc.wheel_half_len + 0.9),
		Models.WSF_GREEN
	)
	mb.box(
		Vector3(hx, wy + fc.wheel_h * 0.5, 0),
		Vector3(2.0 * whw, fc.wheel_h, 2.0 * fc.wheel_half_len),
		Models.WHITE
	)
	mb.box(
		Vector3(hx, wy + 2.25, 0),
		Vector3(2.0 * whw + 0.3, 1.26, 2.0 * fc.wheel_half_len + 0.3),
		Models.WINDOW_LIT
	)
	mb.box(
		Vector3(hx, top + 0.09, 0),
		Vector3(2.0 * whw + 0.6, 0.18, 2.0 * fc.wheel_half_len + 0.6),
		Models.WHITE
	)
	mb.box(Vector3(hx, top + 2.25, 0), Vector3(0.36, 4.5, 0.36), Models.WHITE)
	mb.box(Vector3(hx, top + 3.0, 0), Vector3(2.7, 0.18, 0.18), Models.WHITE)
	# Exhaust stack against the far bulwark.
	var sx := fc.stack_x
	mb.box(Vector3(sx, 4.8, 0), Vector3(1.8, 3.6, 3.0), Models.WHITE)
	mb.cylinder(Vector3(sx, 6.6, 0), 0.6, 0.6, fc.stack_top - 7.8, 6, Color(0.3, 0.3, 0.32))
	mb.cylinder(Vector3(sx, fc.stack_top - 1.2, 0), 0.66, 0.66, 1.2, 6, Color(0.1, 0.1, 0.1))


## Size 2, after the M/V Hiyu: the open car deck runs through a portal amidships.
## Passenger cabins sit over the two outer lanes on slim pillars, a bridge spans
## the tall centre lane between them, and the upper deck on top, railed all round,
## carries the double-ended pilothouse, the stacks, a rescue boat and life rafts.
static func _portal_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	_open_car_deck(mb, fc, Models.WSF_GREEN)
	var b := fc.half_beam
	var hl := fc.house_half_len
	var si := fc.side_in
	var lo := fc.low_y
	var ct := fc.cabin_top
	var dark := Color(0.2, 0.21, 0.23)
	var sign_y := Color(0.95, 0.78, 0.15)
	for x: float in [-1.0, 1.0]:
		# The outer wall down to the bulwark, shorter than the cabin and curving up
		# into its ends, with the car deck's openings in it.
		var ll := fc.low_half_len
		mb.box(
			Vector3(x * (b - 0.45), (5.7 + lo) * 0.5, 0),
			Vector3(0.9, lo - 5.7, 2.0 * ll),
			Models.WHITE
		)
		for zs: float in [-1.0, 1.0]:
			_fillet(mb, x * (b - 0.9), x * b, zs * ll, zs * hl, 5.7, lo, Models.WHITE)
		var z := -(ll - 2.4)
		while z <= ll - 2.4 + 0.03:
			mb.box(Vector3(x * (b - 0.3), 6.75, z), Vector3(0.9, 1.35, 2.7), dark)
			z += 2.0 * (ll - 2.4) / 3.0
		# The cabin over the outer lane, a green line at its foot, windows down the
		# side, on the inboard face and at the ends.
		var cx := x * (si + b) * 0.5
		mb.box(Vector3(cx, (lo + ct) * 0.5, 0), Vector3(b - si, ct - lo, 2.0 * hl), Models.WHITE)
		mb.box(
			Vector3(cx, lo + 0.18, 0),
			Vector3(b - si + 0.12, 0.36, 2.0 * hl + 0.12),
			Models.WSF_GREEN
		)
		z = -(hl - 2.7)
		while z <= hl - 2.7 + 0.03:
			mb.box(Vector3(x * b, 10.35, z), Vector3(0.3, 1.65, 3.0), Models.WINDOW)
			z += fc.cabin_window_step()
		for zs: float in [-1.0, 1.0]:
			mb.box(
				Vector3(x * si, 10.35, zs * (fc.span_half_len + 0.5 * (hl - fc.span_half_len))),
				Vector3(0.3, 1.5, hl - fc.span_half_len - 2.4),
				Models.WINDOW
			)
			mb.box(Vector3(x * (b - 2.7), 10.35, zs * hl), Vector3(3.0, 1.65, 0.3), Models.WINDOW)
			# A clearance board on the overhang's end, yellow with black stripes.
			mb.box(
				Vector3(x * (si + 1.35), lo + 0.45, zs * (hl + 0.03)),
				Vector3(2.1, 0.6, 0.12),
				sign_y
			)
			for k in 3:
				mb.box(
					Vector3(x * (si + 0.6 + 0.75 * k), lo + 0.45, zs * (hl + 0.06)),
					Vector3(0.21, 0.6, 0.12),
					dark
				)
		# Pillars along the overhang's edge.
		for pz in fc.pillars:
			mb.box(
				Vector3(x * (si + 0.3), (3.0 + lo) * 0.5, pz),
				Vector3(0.48, lo - 3.0, 0.48),
				Models.WHITE
			)
	# The bridge over the centre lane, with its own clearance board.
	mb.box(
		Vector3(0, (fc.span_y + ct) * 0.5, 0),
		Vector3(2.0 * si + 0.06, ct - fc.span_y, 2.0 * fc.span_half_len),
		Models.WHITE
	)
	for zs: float in [-1.0, 1.0]:
		mb.box(
			Vector3(0, fc.span_y + 0.96, zs * (fc.span_half_len + 0.03)),
			Vector3(4.2, 0.54, 0.12),
			sign_y
		)
	# The upper deck over the cabins and the bridge (open over the lane either side
	# of it), edged green and railed all round.
	var floor_col := Color(0.5, 0.52, 0.54)
	for x: float in [-1.0, 1.0]:
		mb.box(
			Vector3(x * (si + b) * 0.5, ct + 0.12, 0),
			Vector3(b - si + 0.3, 0.24, 2.0 * hl + 0.3),
			floor_col
		)
		mb.box(
			Vector3(x * (si + b) * 0.5, ct - 0.24, 0),
			Vector3(b - si + 0.36, 0.48, 2.0 * hl + 0.36),
			Models.WSF_GREEN
		)
	mb.box(
		Vector3(0, ct + 0.12, 0), Vector3(2.0 * si, 0.24, 2.0 * fc.span_half_len + 0.3), floor_col
	)
	mb.box(
		Vector3(0, ct - 0.24, 0),
		Vector3(2.0 * si, 0.48, 2.0 * fc.span_half_len + 0.36),
		Models.WSF_GREEN
	)
	var rail := Color(0.12, 0.42, 0.3)
	for x: float in [-1.0, 1.0]:
		_rail(mb, Vector3(x * (b - 0.15), ct, -hl), Vector3(x * (b - 0.15), ct, hl), rail)
		for zs: float in [-1.0, 1.0]:
			_rail(
				mb,
				Vector3(x * (b - 0.15), ct, zs * (hl - 0.15)),
				Vector3(x * si, ct, zs * (hl - 0.15)),
				rail
			)
			_rail(
				mb,
				Vector3(x * si, ct, zs * (hl - 0.15)),
				Vector3(x * si, ct, zs * fc.span_half_len),
				rail
			)
	for zs: float in [-1.0, 1.0]:
		_rail(
			mb,
			Vector3(-si, ct, zs * fc.span_half_len),
			Vector3(si, ct, zs * fc.span_half_len),
			rail
		)
	# The pilothouse, windows all round so it cons either way, and its two masts.
	var wy := fc.wheel_y
	var whw := fc.wheel_half_w
	var wl := fc.wheel_half_len
	var top := wy + fc.wheel_h
	mb.box(
		Vector3(0, wy + fc.wheel_h * 0.5, 0), Vector3(2.0 * whw, fc.wheel_h, 2.0 * wl), Models.WHITE
	)
	mb.box(
		Vector3(0, wy + 2.55, 0), Vector3(2.0 * whw + 0.3, 1.8, 2.0 * wl + 0.3), Models.WINDOW_LIT
	)
	mb.box(
		Vector3(0, top - 0.3, 0), Vector3(2.0 * whw + 0.72, 0.6, 2.0 * wl + 0.72), Models.WSF_GREEN
	)
	mb.box(Vector3(0, top + 0.06, 0), Vector3(2.0 * whw + 0.3, 0.15, 2.0 * wl + 0.3), Models.WHITE)
	for zs: float in [-1.0, 1.0]:
		var mz := zs * fc.mast_z
		mb.box(
			Vector3(0, (top + fc.mast_top) * 0.5, mz),
			Vector3(0.36, fc.mast_top - top, 0.36),
			Color(0.3, 0.3, 0.32)
		)
		mb.box(Vector3(0, top + 2.7, mz), Vector3(4.2, 0.18, 0.18), Color(0.3, 0.3, 0.32))
		mb.box(Vector3(0, top + 4.35, mz), Vector3(2.7, 0.15, 0.24), Models.WHITE)
	mb.box(Vector3(whw - 0.9, top + 2.7, 0), Vector3(0.15, 5.4, 0.15), Color(0.3, 0.3, 0.32))
	# Stacks either side of the pilothouse.
	for x: float in [-1.0, 1.0]:
		var sx := x * fc.stack_dx()
		mb.box(Vector3(sx, ct + 1.05, 0), Vector3(1.8, 2.1, 2.4), Models.WHITE)
		mb.cylinder(
			Vector3(sx, ct + 2.1, 0), 0.48, 0.48, fc.stack_top - ct - 3.0, 6, Color(0.3, 0.3, 0.32)
		)
		mb.cylinder(Vector3(sx, fc.stack_top - 0.9, 0), 0.54, 0.54, 0.9, 6, Color(0.1, 0.1, 0.1))
	# The rescue boat in its cradle at one end, life-raft canisters at the others.
	var rx := b - 3.0
	mb.box(Vector3(rx, ct + 0.45, -(hl - 4.8)), Vector3(1.8, 0.9, 5.4), Color(0.55, 0.57, 0.6))
	mb.box(Vector3(rx, ct + 1.35, -(hl - 4.8)), Vector3(2.25, 0.9, 6.0), Color(0.95, 0.45, 0.12))
	mb.box(Vector3(rx, ct + 1.74, -(hl - 5.1)), Vector3(1.2, 0.36, 3.0), Color(0.2, 0.2, 0.22))
	for p: Vector3 in [
		Vector3(rx, 0, hl - 4.2), Vector3(-rx, 0, hl - 4.2), Vector3(-rx, 0, -(hl - 4.2))
	]:
		mb.cylinder(Vector3(p.x, ct + 0.24, p.z), 0.78, 0.78, 1.5, 6, Models.WHITE)


## A concave fillet between x0 and x1: fills the corner of the (z, y) rectangle from
## (z0, y0) to (z1, y1) that lies off the quarter ellipse centred on (z1, y0), so a
## wall ending at z0 sweeps out under an overhang reaching to z1.
static func _fillet(
	mb: MeshBuilder, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float, col: Color
) -> void:
	const STEPS := 5
	var corner := Vector2(z0, y1)
	var centre := Vector2(z1, y0)
	var arc: Array[Vector2] = []
	for i in STEPS + 1:
		var t := PI * 0.5 * i / STEPS
		arc.append(Vector2(z1 - (z1 - z0) * cos(t), y0 + (y1 - y0) * sin(t)))
	var out_x := Vector3(signf(x1 - x0), 0, 0)
	for i in STEPS:
		var a := arc[i]
		var c := arc[i + 1]
		for side: Array in [[x0, -out_x], [x1, out_x]]:
			var x: float = side[0]
			mb.tri(
				Vector3(x, corner.y, corner.x),
				Vector3(x, a.y, a.x),
				Vector3(x, c.y, c.x),
				col,
				side[1]
			)
		var m := (a + c) * 0.5
		var out := Vector3(0, centre.y - m.y, centre.x - m.x)
		mb.quad(
			Vector3(x0, a.y, a.x),
			Vector3(x1, a.y, a.x),
			Vector3(x1, c.y, c.x),
			Vector3(x0, c.y, c.x),
			col,
			out
		)


## A railing along the deck from `a` to `b` (level, square to an axis): top and
## middle rails on posts about three metres apart.
static func _rail(mb: MeshBuilder, a: Vector3, b: Vector3, col: Color) -> void:
	var d := b - a
	var len := d.length()
	if len < 0.15:
		return
	var along_x := absf(d.x) > absf(d.z)
	var mid := (a + b) * 0.5
	for h: float in [2.7, 1.5]:
		mb.box(
			Vector3(mid.x, a.y + h, mid.z),
			Vector3(len if along_x else 0.15, 0.15, 0.15 if along_x else len),
			col
		)
	var n := maxi(1, ceili(len / 3.3))
	for i in n + 1:
		var p := a + d * (float(i) / n)
		mb.box(Vector3(p.x, a.y + 1.35, p.z), Vector3(0.15, 2.7, 0.15), col)
