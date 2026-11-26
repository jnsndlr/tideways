class_name FerryHullModel
extends RefCounted
## Fits the selected hull, its shadow geometry and lamps to the simulated ferry class.

const RIB_GLB := "res://assets/models/rib_mid.glb"
const DROP := [
	0.0,
	FerryClass.SMALL_DROP,
	FerryClass.HIYU_DROP,
	FerryClass.MID_DROP,
	FerryClass.ISQ_DROP,
	FerryClass.MID_DROP
]
# The Evergreen State's car deck lights: the lenses' glow, and the light they throw
# on the deck (an oval pool under each, its half width and half length in her
# metres, and its energy).
const CAR_DECK_LIGHT := Color(1.0, 0.82, 0.55)
const CAR_DECK_POOL := Vector2(2.6, 5.2)
const CAR_DECK_POOL_ENERGY := 0.2


static func build(fc: FerryClass) -> ArrayMesh:
	var mb: MeshBuilder
	if fc.authored_hull:
		var parts := ["fixed", "thin", "glass", "window"]
		if fc.size >= 3:
			parts.append("lamp")
		mb = _mid_ferry(fc, FerryHullAssets.BY_SIZE[fc.size], DROP[fc.size], parts)
	else:
		mb = ClassicFerryHull.build(fc)
	for p in fc.lanterns:
		Models.add_lantern(mb, p, GlowBuilder.LED, fc.lantern_scale)
	for sl: Array in fc.sidelights:
		Models.add_sidelight(mb, sl[0], sl[1], sl[2], fc.sidelight_scale)
	for lp: Array in fc.lamps:
		Models.add_bulkhead_lamp(mb, lp[0], lp[1], GlowBuilder.WARM, fc.lamp_scale)
	return mb.commit()


static func shadow(fc: FerryClass) -> ArrayMesh:
	var p := ModelParts.merge_named(FerryHullAssets.BY_SIZE[fc.size], ["thinshadow"])
	var mb := MeshBuilder.new()
	for i in p.verts.size():
		mb.verts.append(p.verts[i] * FerryClass.MID_SCALE - Vector3(0, DROP[fc.size], 0))
		mb.normals.append(p.normals[i])
	mb.colors = p.colors
	return mb.commit()


static func _mid_ferry(fc: FerryClass, glb: String, drop_y: float, parts: Array) -> MeshBuilder:
	var mb := MeshBuilder.new()
	var k := FerryClass.MID_SCALE
	var drop := Vector3(0, drop_y, 0)
	var lens := Models.lamp_glass(CAR_DECK_LIGHT)
	for part: String in parts:
		var p := ModelParts.merge_named(glb, [part])
		if part == "thin":
			mb.no_shadow.append(Vector2i(mb.verts.size(), mb.verts.size() + p.verts.size()))
		for i in p.verts.size():
			mb.verts.append(p.verts[i] * k - drop)
			mb.normals.append(p.normals[i])
		if part == "fixed" or part == "thin":
			mb.colors.append_array(p.colors)
		else:
			var c: Color = {"glass": Models.WINDOW_LIT, "window": Models.WINDOW, "lamp": lens}[part]
			for i in p.verts.size():
				mb.colors.append(c)
	if not fc.ribs.is_empty() and ResourceLoader.exists(RIB_GLB):
		var rib := ModelParts.merge_named(RIB_GLB, ["fixed", "sling"])
		for r: Array in fc.ribs:
			var b := Basis(Vector3.UP, r[1])
			var at: Vector3 = r[0]
			for i in rib.verts.size():
				mb.verts.append((b * rib.verts[i] + at) * k - drop)
				mb.normals.append(b * rib.normals[i])
			mb.colors.append_array(rib.colors)
	return mb


## Lights of ferry class `fc` in the hull's frame: masthead lights, red / green
## sidelights, the deck lamps, and the lit windows' reflections on the water.
static func lights(fc: FerryClass) -> ArrayMesh:
	var gb := GlowBuilder.new()
	for p in fc.lanterns:
		gb.glow(
			Models.lantern_glow_at(p, fc.lantern_scale),
			GlowBuilder.LED,
			0.3 * fc.lantern_scale / Models.FERRY_LANTERN,
			9.0,
			true,
			0.0,
			Vector3.ZERO,
			0.0
		)
	for sl: Array in fc.sidelights:
		gb.nav(
			Models.sidelight_glow_at(sl[0], sl[1], fc.sidelight_scale),
			0.22 * fc.sidelight_scale / Models.FERRY_SIDELIGHT_SCALE,
			7.0,
			Vector3(sl[1], 0, sl[2] * 0.8)
		)
	for lp: Array in fc.lamps:
		gb.glow(
			Models.bulkhead_glow_at(lp[0], lp[1], fc.lamp_scale),
			GlowBuilder.WARM,
			Models.bulkhead_glow_size(fc.lamp_scale),
			4.0,
			true,
			0.0,
			lp[1],
			0.0
		)
	var window := Color(1.0, 0.74, 0.42)
	for w: Array in fc.windows:
		gb.reflection(w[0], window, w[1], w[2], w[3])
	if fc.issaquah:
		for c in _mid_car_deck_lights(FerryHullAssets.ISQ_GLB):
			# Each pool on the deck under its lens: the tween deck's, a ramp's or the main deck.
			var floor := FerryClass.ISQ_CAR_DECK
			var ax := absf(c.x)
			var az := absf(c.z)
			if c.y > 6.0 and ax > 5.05:
				if az < FerryClass.ISQ_MEZ_Z:
					floor = FerryClass.ISQ_MEZ_TOP
				elif ax > FerryClass._isq_ramp_edge(az) and FerryClass._isq_ramp_edge(az) > 0.0:
					floor = lerpf(
						FerryClass.ISQ_MEZ_TOP,
						FerryClass.ISQ_CAR_DECK,
						(az - FerryClass.ISQ_MEZ_Z) / (FerryClass.ISQ_RAMP_Z - FerryClass.ISQ_MEZ_Z)
					)
			var w := clampf(FerryClass._isq_beam(c.z) - 0.6 - ax, 1.0, CAR_DECK_POOL.x)
			gb.pool(
				FerryClass._isq(c.x, floor + 0.03, c.z),
				CAR_DECK_LIGHT,
				w * FerryClass.MID_SCALE,
				CAR_DECK_POOL_ENERGY,
				Models.LAMP_ON_AT,
				CAR_DECK_POOL.y * FerryClass.MID_SCALE
			)
	if fc.evergreen:
		for c in _mid_car_deck_lights():
			# Kept inside the hull sides, or the wings' pools spill out over the water.
			var w := clampf(FerryClass._mid_beam(c.z) - 0.6 - absf(c.x), 1.0, CAR_DECK_POOL.x)
			gb.pool(
				FerryClass._mid(c.x, FerryClass.MID_CAR_DECK + 0.03, c.z),
				CAR_DECK_LIGHT,
				w * FerryClass.MID_SCALE,
				CAR_DECK_POOL_ENERGY,
				Models.LAMP_ON_AT,
				CAR_DECK_POOL.y * FerryClass.MID_SCALE
			)
	return gb.commit()


## Where the Evergreen State's car deck lights are (her metres, x and z): the centres
## of the model's `lamp` lenses, which lie well apart.
static func _mid_car_deck_lights(glb := FerryHullAssets.MID_GLB) -> PackedVector3Array:
	var p := ModelParts.merge_named(glb, ["lamp"])
	var sums := PackedVector3Array()
	var counts := PackedInt32Array()
	for v in p.verts:
		var j := 0
		while j < sums.size() and (v - sums[j] / counts[j]).length() > 1.5:
			j += 1
		if j == sums.size():
			sums.append(Vector3.ZERO)
			counts.append(0)
		sums[j] += v
		counts[j] += 1
	var out := PackedVector3Array()
	for j in sums.size():
		out.append(sums[j] / counts[j])
	return out
