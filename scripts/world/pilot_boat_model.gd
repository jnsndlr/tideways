class_name PilotBoatModel
extends RefCounted
## Hulls, livery, boarding ladder and lamp positions for the pilot launch.

# Pilot boat (+Z is the bow): about 9 m long and 3 m in the beam, heavily fendered
# to lie against a ship's side, the deckhouse forward and its mast carrying the
# pilot vessel's lights (white over red).
const PILOT_WHITE := Vector3(0, 3.95, 0.7)
const PILOT_RED := Vector3(0, 3.5, 0.7)
const PILOT_LANTERN := 0.9
const PILOT_SIDELIGHT := Vector3(1.13, 1.75, 1.8)
const PILOT_HULLS := [Color(0.08, 0.08, 0.09), Color(0.86, 0.33, 0.1), Color(0.1, 0.15, 0.28)]
const PILOT_TOPS := [Color(0.9, 0.4, 0.1), Color(0.94, 0.95, 0.94), Color(0.9, 0.4, 0.1)]

const ASSET := "res://assets/models/pilot_mid.glb"
const MID_PILOT_HULLS := [Color(0.78, 0.13, 0.1), Color(0.14, 0.15, 0.16), Color(0.1, 0.15, 0.28)]
const MID_PILOT_TRIMS := [Color(0.78, 0.13, 0.1), Color(0.78, 0.13, 0.1), Color(0.9, 0.4, 0.1)]
# The red lantern sits on a bracket forward of the mast, the white one on its top.
const MID_PILOT_RED := Vector3(0, 3.5, 0.93)
# Sidelight lamps (Models.add_sidelight) on the deckhouse sides, just below the windows.
const MID_PILOT_SIDELIGHT := Vector3(1.1, 1.42, 1.15)
const MID_PILOT_SIDELIGHT_SCALE := 0.75
const MID_PILOT_STERN_LIGHT := Vector3(0, 1.45, -4.46)

static var authored := (
	not "--classic-pilot" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func _pilot_red() -> Vector3:
	return MID_PILOT_RED if authored else PILOT_RED


## The authored pilot boat in `variant`'s livery.
static func _mid_pilot(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(ASSET, ["fixed"])
	var paint := {
		"hull": MID_PILOT_HULLS[variant % MID_PILOT_HULLS.size()],
		"trim": MID_PILOT_TRIMS[variant % MID_PILOT_TRIMS.size()],
		"glass": Models.WINDOW_LIT,
		"lens": Models.lamp_glass(GlowBuilder.LED)
	}
	for part: String in paint:
		var p := ModelParts.merge_named(ASSET, [part])
		mb.verts.append_array(p.verts)
		mb.normals.append_array(p.normals)
		for i in p.verts.size():
			mb.colors.append(paint[part])
	Models.add_lantern(mb, MID_PILOT_RED, GlowBuilder.RED, PILOT_LANTERN)
	Models.add_lantern(mb, PILOT_WHITE, GlowBuilder.LED, PILOT_LANTERN)
	for sx: float in [-1.0, 1.0]:
		Models.add_sidelight(
			mb,
			Vector3(sx * MID_PILOT_SIDELIGHT.x, MID_PILOT_SIDELIGHT.y, MID_PILOT_SIDELIGHT.z),
			sx,
			1.0,
			MID_PILOT_SIDELIGHT_SCALE
		)
	return mb


static func _pilot_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array(
		[
			Vector2(-1.4, -4.5),
			Vector2(1.4, -4.5),
			Vector2(1.5, -3.5),
			Vector2(1.5, 1.0),
			Vector2(1.3, 2.6),
			Vector2(0.75, 3.8),
			Vector2(0, 4.5),
			Vector2(-0.75, 3.8),
			Vector2(-1.3, 2.6),
			Vector2(-1.5, 1.0),
			Vector2(-1.5, -3.5)
		]
	)
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((1.5 + grow) / 1.5, (4.5 + grow) / 4.5)
	return pts


## A pilot boat; `variant` picks its colours.
static func hull(variant: int) -> ArrayMesh:
	if authored:
		return _mid_pilot(variant).commit()
	var mb := MeshBuilder.new()
	var hull: Color = PILOT_HULLS[variant % PILOT_HULLS.size()]
	var top: Color = PILOT_TOPS[variant % PILOT_TOPS.size()]
	var deck := Color(0.4, 0.42, 0.42)
	var fender := Color(0.06, 0.06, 0.07)
	var outline := _pilot_outline()
	mb.extrude(outline, -0.8, 0.05, Color(0.5, 0.14, 0.12), Color(0, 0, 0, 0), 0.55)
	mb.extrude(outline, 0.05, 0.95, hull, deck)
	# The heavy rubber fender all round the gunwale.
	mb.extrude(_pilot_outline(0.14), 0.62, 0.95, fender, Color(0, 0, 0, 0))
	mb.extrude(_pilot_outline(0.04), 0.1, 0.18, Models.WHITE, Color(0, 0, 0, 0))
	# Deckhouse, windows all round, and the roof in the station's colour with a
	# rail round it.
	mb.box(Vector3(0, 1.6, 0.4), Vector3(2.2, 1.3, 3.4), Models.WHITE)
	mb.box(Vector3(0, 1.85, 0.4), Vector3(2.24, 0.48, 3.44), Models.WINDOW_LIT)
	mb.box(Vector3(0, 2.3, 0.4), Vector3(2.4, 0.12, 3.6), top)
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 1.1, 2.6, 0.4), Vector3(0.05, 0.05, 3.2), Models.WHITE)
	mb.box(Vector3(0, 2.6, -1.25), Vector3(2.2, 0.05, 0.05), Models.WHITE)
	mb.box(Vector3(0, 2.6, 2.05), Vector3(2.2, 0.05, 0.05), Models.WHITE)
	# A band of the top colour round the hull below the fender.
	mb.extrude(_pilot_outline(0.02), 0.38, 0.55, top, Color(0, 0, 0, 0))
	# Sidelights on the deckhouse's forward corners.
	for x: float in [-1.0, 1.0]:
		mb.box(
			Vector3(x * PILOT_SIDELIGHT.x, PILOT_SIDELIGHT.y, PILOT_SIDELIGHT.z),
			Vector3(0.06, 0.16, 0.24),
			Models.LENS_RED if x > 0.0 else Models.LENS_GREEN
		)
	# The mast: radar, then the pilot's red and white lanterns.
	mb.box(
		Vector3(0, (2.36 + PILOT_WHITE.y) * 0.5, PILOT_WHITE.z),
		Vector3(0.12, PILOT_WHITE.y - 2.36, 0.12),
		Models.WHITE
	)
	mb.box(Vector3(0, 3.05, PILOT_WHITE.z), Vector3(1.4, 0.08, 0.26), Models.WHITE)
	mb.box(Vector3(0, 3.2, PILOT_WHITE.z), Vector3(0.8, 0.06, 0.08), Color(0.2, 0.2, 0.22))
	Models.add_lantern(mb, PILOT_RED, GlowBuilder.RED, PILOT_LANTERN)
	Models.add_lantern(mb, PILOT_WHITE, GlowBuilder.LED, PILOT_LANTERN)
	# Foredeck rails where the pilot steps across, a bitt aft and the stern light.
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 1.05, 1.35, 3.0), Vector3(0.05, 0.05, 1.6), Models.WHITE)
		for z: float in [2.3, 3.0, 3.7]:
			mb.box(
				Vector3(x * 1.05 * (1.0 - (z - 2.3) * 0.3), 1.15, z),
				Vector3(0.05, 0.4, 0.05),
				Models.WHITE
			)
	mb.cylinder(Vector3(0, 0.95, -3.4), 0.14, 0.14, 0.35, 8, Color(0.2, 0.2, 0.22))
	mb.cylinder(Vector3(0.6, 0.95, -2.4), 0.3, 0.3, 0.5, 8, Models.WHITE)
	mb.box(Vector3(0, 0.8, -4.52), Vector3(0.14, 0.1, 0.04), Models.lamp_glass(GlowBuilder.LED))
	return mb.commit()


## The ship's pilot ladder, hung over its side down to just above the pilot
## boat's deck, in the boat's frame with the ship's side `out` metres to
## starboard (+X) and its deck `deck` metres up.
static func ladder(out: float, deck: float) -> ArrayMesh:
	var mb := MeshBuilder.new()
	var rope := Color(0.75, 0.66, 0.48)
	var foot := 1.45
	# Abreast of the foredeck, where the boat's boarding rails are.
	var z := 2.9
	for dz: float in [-0.25, 0.25]:
		mb.box(
			Vector3(out - 0.04, (deck + foot) * 0.5, z + dz), Vector3(0.04, deck - foot, 0.04), rope
		)
	var y := foot + 0.1
	while y < deck - 0.1:
		mb.box(Vector3(out - 0.05, y, z), Vector3(0.06, 0.05, 0.62), Color(0.55, 0.36, 0.2))
		y += 0.33
	# The pilot, stepping across from the foredeck in a hi-vis jacket.
	var px := out - 0.45
	mb.box(Vector3(px, 1.35, z), Vector3(0.24, 0.5, 0.22), Color(0.12, 0.13, 0.18))
	mb.box(Vector3(px, 1.78, z), Vector3(0.3, 0.38, 0.26), Color(0.95, 0.5, 0.1))
	mb.box(Vector3(px, 2.07, z), Vector3(0.18, 0.18, 0.18), Color(0.85, 0.65, 0.5))
	return mb.commit()


static func lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var window := Color(1.0, 0.74, 0.42)
	# (The mid-poly deckhouse's windows run higher and further aft.)
	var y := 1.92 if authored else 1.85
	var z0 := -0.9 if authored else -0.6
	for x: float in [-1.15, 1.15]:
		for i in 3:
			gb.reflection(Vector3(x, y, z0 + i), window, 0.16, 1.4, Vector3(signf(x), 0, 0))
	return gb.commit()


## Sidelights and stern light, shown under way.
static func navigation_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var sl := (
		Models.sidelight_glow_at(MID_PILOT_SIDELIGHT, 1.0, MID_PILOT_SIDELIGHT_SCALE)
		if authored
		else PILOT_SIDELIGHT + Vector3(0.04, 0, 0.1)
	)
	gb.glow(sl, GlowBuilder.RED, 0.15, 5.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
	gb.glow(
		Vector3(-sl.x, sl.y, sl.z),
		GlowBuilder.GREEN,
		0.15,
		5.0,
		true,
		0.0,
		Vector3(-1, 0, 0.8),
		0.0
	)
	gb.glow(
		MID_PILOT_STERN_LIGHT if authored else Vector3(0, 0.8, -4.56),
		GlowBuilder.LED,
		0.1,
		3.5,
		true,
		0.0,
		Vector3(0, 0, -1),
		0.0
	)
	return gb.commit()


## On pilotage duty: white over red, all round.
static func duty_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	gb.glow(
		Models.lantern_glow_at(PILOT_WHITE, PILOT_LANTERN),
		GlowBuilder.LED,
		0.17,
		6.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	gb.glow(
		Models.lantern_glow_at(_pilot_red(), PILOT_LANTERN),
		GlowBuilder.RED,
		0.17,
		6.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	return gb.commit()
