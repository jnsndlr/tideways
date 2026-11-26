class_name TugModel
extends RefCounted
## Escort tug hulls, liveries and lighting in authored and classic modes.

# Tug (+Z is the bow): about 14 m long and 5 m in the beam, heavily fendered, the
# wheelhouse high on its deckhouse forward, the stack behind it and the towing
# winch and staple on the after deck.
const TUG_MAST := Vector3(0, 7.7, 1.4)
const TUG_LANTERN := 1.1
const TUG_SIDELIGHT := Vector3(1.56, 4.7, 2.9)
const TUG_HULLS := [Color(0.1, 0.1, 0.11), Color(0.62, 0.15, 0.12), Color(0.13, 0.22, 0.36)]
const TUG_HOUSES := [Color(0.94, 0.95, 0.94), Color(0.94, 0.95, 0.94), Color(0.9, 0.84, 0.62)]
const TUG_STACKS := [Color(0.86, 0.33, 0.1), Color(0.1, 0.1, 0.11), Color(0.75, 0.15, 0.13)]
const TUG_STERN_LIGHT := Vector3(0, 1.4, -7.08)

const ASSET := "res://assets/models/tug_mid.glb"
const MID_TUG_MAST := Vector3(0, 8.05, 1.25)
# Sidelight lamps (Models.add_sidelight) on the wheelhouse sides, below the windows.
const MID_TUG_SIDELIGHT := Vector3(1.5, 3.95, 2.6)
const MID_TUG_SIDELIGHT_SCALE := 1.2
const MID_TUG_STERN_LIGHT := Vector3(0, 2.02, -7.11)

static var authored := (
	not "--classic-tug" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func _tug_mast() -> Vector3:
	return MID_TUG_MAST if authored else TUG_MAST


## Where the port (+x, red) sidelight's glow sits; the starboard one mirrors it.
static func _tug_sidelight() -> Vector3:
	return (
		Models.sidelight_glow_at(MID_TUG_SIDELIGHT, 1.0, MID_TUG_SIDELIGHT_SCALE)
		if authored
		else TUG_SIDELIGHT
	)


static func _tug_stern_light() -> Vector3:
	return MID_TUG_STERN_LIGHT if authored else TUG_STERN_LIGHT


## The mid-poly tug in `variant`'s livery.
static func _authored_hull(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(ASSET, ["fixed"])
	var paint := {
		"hull": TUG_HULLS[variant % TUG_HULLS.size()],
		"house": TUG_HOUSES[variant % TUG_HOUSES.size()],
		"stack": TUG_STACKS[variant % TUG_STACKS.size()],
		"glass": Models.WINDOW_LIT,
		"window": Models.WINDOW,
		"lens": Models.lamp_glass(GlowBuilder.LED)
	}
	for part: String in paint:
		var p := ModelParts.merge_named(ASSET, [part])
		mb.verts.append_array(p.verts)
		mb.normals.append_array(p.normals)
		for i in p.verts.size():
			mb.colors.append(paint[part])
	Models.add_lantern(mb, MID_TUG_MAST, GlowBuilder.LED, TUG_LANTERN)
	for sx: float in [-1.0, 1.0]:
		Models.add_sidelight(
			mb,
			Vector3(sx * MID_TUG_SIDELIGHT.x, MID_TUG_SIDELIGHT.y, MID_TUG_SIDELIGHT.z),
			sx,
			1.0,
			MID_TUG_SIDELIGHT_SCALE
		)
	return mb


static func _tug_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array(
		[
			Vector2(-2.2, -7),
			Vector2(2.2, -7),
			Vector2(2.5, -5.5),
			Vector2(2.5, 2.0),
			Vector2(2.2, 4.5),
			Vector2(1.4, 6.3),
			Vector2(0, 7),
			Vector2(-1.4, 6.3),
			Vector2(-2.2, 4.5),
			Vector2(-2.5, 2.0),
			Vector2(-2.5, -5.5)
		]
	)
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((2.5 + grow) / 2.5, (7.0 + grow) / 7.0)
	return pts


## A tug; `variant` picks its colours.
static func hull(variant: int) -> ArrayMesh:
	if authored:
		return _authored_hull(variant).commit()
	var mb := MeshBuilder.new()
	var hull: Color = TUG_HULLS[variant % TUG_HULLS.size()]
	var house: Color = TUG_HOUSES[variant % TUG_HOUSES.size()]
	var stack: Color = TUG_STACKS[variant % TUG_STACKS.size()]
	var deck := Color(0.36, 0.37, 0.37)
	var fender := Color(0.06, 0.06, 0.07)
	var steel := Color(0.25, 0.26, 0.28)
	var outline := _tug_outline()
	mb.extrude(outline, -2.2, 0.05, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.65)
	mb.extrude(outline, 0.05, 1.3, hull, deck)
	mb.extrude(_tug_outline(0.04), 0.95, 1.08, Models.WHITE, Color(0, 0, 0, 0))
	# Fendering all round, and the big bow fender for pushing.
	mb.extrude(_tug_outline(0.3), 0.35, 1.0, fender, Color(0, 0, 0, 0))
	mb.box(Vector3(0, 1.1, 6.75), Vector3(2.4, 1.3, 0.9), fender)
	# Bulwarks down the sides, a white cap on them.
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 2.42, 1.6, -1.8), Vector3(0.14, 0.6, 9.4), hull)
		mb.box(Vector3(x * 2.42, 1.92, -1.8), Vector3(0.2, 0.06, 9.4), Models.WHITE)
	# The deckhouse, the wheelhouse high on it with windows all round, and the
	# mast on its roof.
	mb.box(Vector3(0, 2.4, 1.6), Vector3(3.6, 2.2, 5.0), house)
	mb.box(Vector3(0, 2.6, 1.6), Vector3(3.64, 0.5, 4.2), Models.WINDOW)
	mb.box(Vector3(0, 4.4, 2.2), Vector3(3.0, 1.8, 2.6), house)
	mb.box(Vector3(0, 4.62, 2.2), Vector3(3.06, 0.7, 2.66), Models.WINDOW_LIT)
	mb.box(Vector3(0, 5.36, 2.2), Vector3(3.5, 0.12, 3.1), house)
	for x: float in [-1.0, 1.0]:
		var sl := Vector3(x * TUG_SIDELIGHT.x, TUG_SIDELIGHT.y, TUG_SIDELIGHT.z)
		mb.box(sl + Vector3(0, 0, -0.25), Vector3(0.3, 0.34, 0.06), Models.LAMP_DARK)
		mb.box(sl, Vector3(0.12, 0.24, 0.3), Models.LENS_RED if x > 0.0 else Models.LENS_GREEN)
	mb.box(
		Vector3(0, (5.42 + TUG_MAST.y) * 0.5, TUG_MAST.z),
		Vector3(0.16, TUG_MAST.y - 5.42, 0.16),
		house
	)
	mb.box(Vector3(0, 6.3, TUG_MAST.z), Vector3(2.4, 0.1, 0.3), house)
	mb.box(Vector3(0, 6.45, TUG_MAST.z), Vector3(1.2, 0.06, 0.1), Color(0.2, 0.2, 0.22))
	Models.add_lantern(mb, TUG_MAST, GlowBuilder.LED, TUG_LANTERN)
	# The stack, behind the wheelhouse.
	mb.box(Vector3(0, 3.9, -1.5), Vector3(1.3, 2.6, 1.4), stack)
	mb.box(Vector3(0, 5.25, -1.5), Vector3(1.32, 0.3, 1.42), Color(0.08, 0.08, 0.08))
	mb.box(Vector3(0, 4.2, -1.5), Vector3(1.34, 0.3, 1.44), Models.WHITE)
	# Towing winch and the staple over the after deck, bitts either side.
	mb.box(Vector3(0, 1.8, -3.6), Vector3(2.2, 1.0, 1.3), steel)
	mb.cylinder(Vector3(0, 1.55, -3.6), 0.5, 0.5, 0.5, 10, Color(0.75, 0.6, 0.18))
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 1.9, 2.4, -5.8), Vector3(0.3, 2.2, 0.3), stack)
		mb.cylinder(Vector3(x * 1.4, 1.3, -6.3), 0.2, 0.2, 0.5, 8, steel)
	mb.box(Vector3(0, 3.5, -5.8), Vector3(4.1, 0.3, 0.3), stack)
	mb.box(
		TUG_STERN_LIGHT + Vector3(0, 0, 0.06),
		Vector3(0.18, 0.14, 0.04),
		Models.lamp_glass(GlowBuilder.LED)
	)
	return mb.commit()


static func lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var window := Color(1.0, 0.74, 0.42)
	# The wheelhouse windows (the mid-poly one runs further aft, raked out forward).
	var y := 4.65 if authored else 4.62
	var z0 := 1.0 if authored else 1.3
	var front := 3.6 if authored else 3.55
	for x: float in [-1.56, 1.56]:
		for i in 3:
			gb.reflection(Vector3(x, y, z0 + i * 0.9), window, 0.2, 1.6, Vector3(signf(x), 0, 0))
	for i in 3:
		gb.reflection(Vector3(-1.0 + i, y, front), window, 0.2, 1.6, Vector3(0, 0, 1))
	return gb.commit()


## Sidelights and stern light, shown under way.
static func navigation_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var sl := _tug_sidelight()
	if not authored:
		sl.z += 0.1
	gb.glow(
		Vector3(sl.x, sl.y, sl.z), GlowBuilder.RED, 0.18, 6.0, true, 0.0, Vector3(1, 0, 0.8), 0.0
	)
	gb.glow(
		Vector3(-sl.x, sl.y, sl.z),
		GlowBuilder.GREEN,
		0.18,
		6.0,
		true,
		0.0,
		Vector3(-1, 0, 0.8),
		0.0
	)
	gb.glow(_tug_stern_light(), GlowBuilder.LED, 0.12, 4.0, true, 0.0, Vector3(0, 0, -1), 0.0)
	return gb.commit()


## The masthead light, shown under way.
static func mast_light() -> ArrayMesh:
	var gb := GlowBuilder.new()
	gb.glow(
		Models.lantern_glow_at(_tug_mast(), TUG_LANTERN),
		GlowBuilder.LED,
		0.2,
		7.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	return gb.commit()
