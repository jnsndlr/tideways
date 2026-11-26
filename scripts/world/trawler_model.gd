class_name TrawlerModel
extends RefCounted
## Stern trawler hulls, towing warps and lighting in authored and classic modes.

# Stern trawler (+Z is the bow): about 20 m long and 6.4 m in the beam, the
# wheelhouse forward and the working deck aft under a gantry. The mast carries
# the trawling lights (green over white) and the masthead light.
const TRAWLER_DECK := 1.6
const TRAWLER_MAST := Vector3(0, 8.6, 1.3)  # the white lantern's foot
const TRAWLER_MAST_GREEN := Vector3(0, 9.6, 1.3)
const TRAWLER_LANTERN := 1.2
const TRAWLER_SIDELIGHT := Vector3(2.35, 4.45, 5.4)
const TRAWLER_GANTRY_Z := -9.3
const TRAWLER_GANTRY_TOP := 6.6
const TRAWLER_HULLS := [Color(0.12, 0.2, 0.36), Color(0.13, 0.33, 0.24), Color(0.58, 0.15, 0.12)]
const TRAWLER_GANTRIES := [Color(0.92, 0.52, 0.12), Color(0.9, 0.78, 0.2), Color(0.92, 0.52, 0.12)]
const TRAWLER_NETS := [Color(0.2, 0.55, 0.35), Color(0.85, 0.42, 0.15), Color(0.25, 0.4, 0.62)]

## Blender model from art/trawler_mid.py. The hull, gantry and net take livery colors.
const ASSET := "res://assets/models/trawler_mid.glb"
# Sidelight lamps (Models.add_sidelight) on boards at the wheelhouse roof's front corners.
const MID_TRAWLER_SIDELIGHT := Vector3(2.0, 5.63, 4.3)
const MID_TRAWLER_SIDELIGHT_SCALE := 1.2
# The stern light under the gantry's crossbar; the floods on its forward face and on
# the wheelhouse roof's after edge.
const MID_TRAWLER_STERN_LIGHT := Vector3(0, 6.28, -9.62)
const MID_TRAWLER_GANTRY_FLOOD := Vector3(2.05, 6.5, -8.9)
const MID_TRAWLER_HOUSE_FLOOD := Vector3(0.7, 5.65, 0.35)

static var authored := (
	not "--classic-trawler" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func _trawler_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array(
		[
			Vector2(-2.9, -10),
			Vector2(2.9, -10),
			Vector2(3.2, -8),
			Vector2(3.2, 3),
			Vector2(2.65, 6.5),
			Vector2(1.45, 8.8),
			Vector2(0, 10),
			Vector2(-1.45, 8.8),
			Vector2(-2.65, 6.5),
			Vector2(-3.2, 3),
			Vector2(-3.2, -8)
		]
	)
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((3.2 + grow) / 3.2, (10.0 + grow) / 10.0)
	return pts


static func _authored_hull(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(ASSET, ["fixed"])
	var paint := {
		"hull": TRAWLER_HULLS[variant % TRAWLER_HULLS.size()],
		"gantry": TRAWLER_GANTRIES[variant % TRAWLER_GANTRIES.size()],
		"net": TRAWLER_NETS[variant % TRAWLER_NETS.size()],
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
	Models.add_lantern(mb, TRAWLER_MAST, GlowBuilder.LED, TRAWLER_LANTERN)
	Models.add_lantern(mb, TRAWLER_MAST_GREEN, GlowBuilder.GREEN, TRAWLER_LANTERN)
	for sx: float in [-1.0, 1.0]:
		Models.add_sidelight(
			mb,
			Vector3(sx * MID_TRAWLER_SIDELIGHT.x, MID_TRAWLER_SIDELIGHT.y, MID_TRAWLER_SIDELIGHT.z),
			sx,
			1.0,
			MID_TRAWLER_SIDELIGHT_SCALE
		)
	return mb


static func hull(variant: int) -> ArrayMesh:
	if authored:
		return _authored_hull(variant).commit()
	var mb := MeshBuilder.new()
	var hull_col: Color = TRAWLER_HULLS[variant % TRAWLER_HULLS.size()]
	var gantry: Color = TRAWLER_GANTRIES[variant % TRAWLER_GANTRIES.size()]
	var net: Color = TRAWLER_NETS[variant % TRAWLER_NETS.size()]
	var deck_col := Color(0.42, 0.43, 0.42)
	var steel := Color(0.22, 0.23, 0.25)
	var d := TRAWLER_DECK
	var outline := _trawler_outline()
	mb.extrude(outline, -2.0, 0.05, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.7)
	mb.extrude(outline, 0.05, d, hull_col, deck_col)
	mb.extrude(_trawler_outline(0.06), d - 0.2, d - 0.05, Models.WHITE, Color(0, 0, 0, 0))
	# Bulwarks down either side of the working deck, the transom's open aft.
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 3.12, d + 0.4, -3.0), Vector3(0.14, 0.8, 12.0), hull_col)
		mb.box(Vector3(x * 3.12, d + 0.82, -3.0), Vector3(0.2, 0.06, 12.0), Models.WHITE)
	# The raised foredeck.
	var fore := PackedVector2Array(
		[
			Vector2(-3.2, 3),
			Vector2(3.2, 3),
			Vector2(2.65, 6.5),
			Vector2(1.45, 8.8),
			Vector2(0, 10),
			Vector2(-1.45, 8.8),
			Vector2(-2.65, 6.5)
		]
	)
	mb.extrude(fore, d, d + 1.0, hull_col, deck_col)
	mb.box(Vector3(0, d + 1.15, 6.6), Vector3(0.6, 0.3, 0.8), steel)
	# Deckhouse and the wheelhouse on top of it, windows all round.
	mb.box(Vector3(0, d + 1.0, 2.0), Vector3(4.8, 2.0, 4.6), Models.WHITE)
	mb.box(Vector3(0, d + 2.0 + 0.9, 3.3), Vector3(4.4, 1.8, 3.4), Models.WHITE)
	mb.box(Vector3(0, d + 2.0 + 1.15, 3.3), Vector3(4.46, 0.6, 3.46), Models.WINDOW_LIT)
	mb.box(Vector3(0, d + 2.0 + 1.85, 3.3), Vector3(4.9, 0.12, 3.9), Models.WHITE)
	mb.box(Vector3(0, d + 1.1, 2.0), Vector3(4.86, 0.5, 2.2), Models.WINDOW_LIT)
	# Sidelights in their screens on the wheelhouse sides.
	for x: float in [-1.0, 1.0]:
		var sl := Vector3(x * TRAWLER_SIDELIGHT.x, TRAWLER_SIDELIGHT.y, TRAWLER_SIDELIGHT.z)
		mb.box(sl + Vector3(0, 0, -0.25), Vector3(0.3, 0.32, 0.06), Models.LAMP_DARK)
		mb.box(
			sl,
			Vector3(0.18, 0.24, 0.3),
			Models.lamp_glass(GlowBuilder.RED if x > 0.0 else GlowBuilder.GREEN)
		)
	# Mast with its crosstree and lights, the radar, the exhaust stack.
	var mast_base := d + 2.0 + 1.9
	mb.box(
		Vector3(0, (mast_base + TRAWLER_MAST_GREEN.y) * 0.5, TRAWLER_MAST.z),
		Vector3(0.18, TRAWLER_MAST_GREEN.y - mast_base, 0.18),
		Models.WHITE
	)
	mb.box(Vector3(0, 7.6, TRAWLER_MAST.z), Vector3(2.4, 0.1, 0.1), Models.WHITE)
	Models.add_lantern(mb, TRAWLER_MAST, GlowBuilder.LED, TRAWLER_LANTERN)
	Models.add_lantern(mb, TRAWLER_MAST_GREEN, GlowBuilder.GREEN, TRAWLER_LANTERN)
	mb.box(Vector3(0, mast_base + 0.45, 2.6), Vector3(0.25, 0.5, 0.25), steel)
	mb.box(Vector3(0, mast_base + 0.75, 2.6), Vector3(2.2, 0.12, 0.3), Models.WHITE)
	mb.cylinder(Vector3(1.6, d + 2.0, 0.4), 0.22, 0.2, 3.6, 8, Color(0.85, 0.85, 0.83))
	mb.cylinder(Vector3(1.6, d + 5.6, 0.4), 0.21, 0.21, 0.4, 8, Color(0.08, 0.08, 0.08))
	mb.cylinder(Vector3(-1.5, d + 2.0 + 1.9, 2.2), 0.3, 0.3, 0.7, 8, Models.WHITE)
	# The working deck: fish hatch, net drum, and the gantry over the stern
	# with the trawl doors hung either side.
	mb.box(Vector3(0, d + 0.25, -2.6), Vector3(1.8, 0.5, 1.8), steel)
	var saved := mb.xform
	mb.xform = saved * Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(1.8, d + 1.1, -6.4))
	mb.cylinder(Vector3.ZERO, 0.85, 0.85, 3.6, 10, net, Color(-1, 0, 0), 0.0, true)
	mb.cylinder(Vector3(0, -0.06, 0), 1.05, 1.05, 0.12, 10, steel, Color(-1, 0, 0), 0.0, true)
	mb.cylinder(Vector3(0, 3.54, 0), 1.05, 1.05, 0.12, 10, steel, Color(-1, 0, 0), 0.0, true)
	mb.xform = saved
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * 1.95, d + 0.55, -6.4), Vector3(0.2, 1.1, 0.4), steel)
		mb.box(
			Vector3(x * 2.7, (d + TRAWLER_GANTRY_TOP) * 0.5, TRAWLER_GANTRY_Z),
			Vector3(0.32, TRAWLER_GANTRY_TOP - d, 0.32),
			gantry
		)
		mb.box(Vector3(x * 3.32, d + 0.9, -8.4), Vector3(0.14, 1.1, 1.7), steel)
		mb.box(Vector3(x * 2.95, d + 1.6, -8.4), Vector3(0.6, 0.06, 0.06), steel)
	mb.box(Vector3(0, TRAWLER_GANTRY_TOP, TRAWLER_GANTRY_Z), Vector3(5.8, 0.34, 0.4), gantry)
	for x: float in [-1.4, 1.4]:
		mb.box(
			Vector3(x, TRAWLER_GANTRY_TOP - 0.45, TRAWLER_GANTRY_Z), Vector3(0.3, 0.5, 0.25), steel
		)
	# Tyres slung along the topsides for coming alongside.
	for x: float in [-1.0, 1.0]:
		for z: float in [-6.5, -3.0, 0.5, 4.0]:
			mb.box(Vector3(x * 3.28, d - 0.35, z), Vector3(0.18, 0.6, 0.6), Color(0.08, 0.08, 0.09))
	# The stern light.
	mb.box(
		Vector3(0, d + 0.15, -10.02), Vector3(0.22, 0.2, 0.08), Models.lamp_glass(GlowBuilder.LED)
	)
	return mb.commit()


## The trawl warps, out from the gantry's blocks and down into the water astern
## (shown while the net is out).
static func warps() -> ArrayMesh:
	var mb := MeshBuilder.new()
	for x: float in [-1.4, 1.4]:
		var a := Vector3(x, TRAWLER_GANTRY_TOP - 0.7, TRAWLER_GANTRY_Z)
		var b := Vector3(x * 1.6, -0.6, TRAWLER_GANTRY_Z - 8.5)
		mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
		mb.box(Vector3.ZERO, Vector3(0.07, 0.07, a.distance_to(b)), Color(0.15, 0.15, 0.16))
	return mb.commit()


## The lit wheelhouse's reflection, drawn by NightLights on each trawler.
static func wheelhouse_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var window := Color(1.0, 0.74, 0.42)
	for x: float in [-2.25, 2.25]:
		for i in 3:
			gb.reflection(
				Vector3(x, TRAWLER_DECK + 3.15, 2.4 + i * 0.9),
				window,
				0.26,
				1.8,
				Vector3(signf(x), 0, 0)
			)
	for i in 4:
		gb.reflection(
			Vector3(-1.5 + i, TRAWLER_DECK + 3.15, 5.05), window, 0.26, 1.8, Vector3(0, 0, 1)
		)
	return gb.commit()


## Sidelights and stern light, shown under way.
static func navigation_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	var sl := (
		Models.sidelight_glow_at(MID_TRAWLER_SIDELIGHT, 1.0, MID_TRAWLER_SIDELIGHT_SCALE)
		if authored
		else TRAWLER_SIDELIGHT + Vector3(0, 0, 0.1)
	)
	gb.glow(sl, GlowBuilder.RED, 0.2, 6.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
	gb.glow(
		Vector3(-sl.x, sl.y, sl.z), GlowBuilder.GREEN, 0.2, 6.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0
	)
	gb.glow(
		MID_TRAWLER_STERN_LIGHT if authored else Vector3(0, TRAWLER_DECK + 0.15, -10.1),
		GlowBuilder.LED,
		0.16,
		4.0,
		true,
		0.0,
		Vector3(0, 0, -1),
		0.0
	)
	return gb.commit()


## The masthead light, shown steaming.
static func steaming_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	gb.glow(
		Models.lantern_glow_at(TRAWLER_MAST, TRAWLER_LANTERN),
		GlowBuilder.LED,
		0.22,
		7.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	return gb.commit()


## Trawling: green over white all round, and the working deck floodlit from the
## gantry and the back of the wheelhouse.
static func working_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	gb.glow(
		Models.lantern_glow_at(TRAWLER_MAST_GREEN, TRAWLER_LANTERN),
		GlowBuilder.GREEN,
		0.24,
		7.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	gb.glow(
		Models.lantern_glow_at(TRAWLER_MAST, TRAWLER_LANTERN),
		GlowBuilder.LED,
		0.22,
		7.0,
		true,
		0.0,
		Vector3.ZERO,
		0.0
	)
	if authored:
		for sx: float in [-1.0, 1.0]:
			var g := MID_TRAWLER_GANTRY_FLOOD
			gb.glow(
				Vector3(sx * g.x, g.y, g.z),
				GlowBuilder.LED,
				0.3,
				6.0,
				true,
				0.0,
				Vector3(0, -0.5, 1),
				0.0
			)
			var h := MID_TRAWLER_HOUSE_FLOOD
			gb.glow(
				Vector3(sx * h.x, h.y, h.z),
				GlowBuilder.LED,
				0.24,
				5.0,
				false,
				0.0,
				Vector3(0, -0.4, -1),
				0.0
			)
	else:
		for x: float in [-1.4, 1.4]:
			gb.glow(
				Vector3(x, TRAWLER_GANTRY_TOP - 0.55, TRAWLER_GANTRY_Z + 0.15),
				GlowBuilder.LED,
				0.3,
				6.0,
				true,
				0.0,
				Vector3(0, -0.5, 1),
				0.0
			)
		gb.glow(
			Vector3(0, TRAWLER_DECK + 3.7, 1.55),
			GlowBuilder.LED,
			0.28,
			5.0,
			false,
			0.0,
			Vector3(0, -0.4, -1),
			0.0
		)
	gb.pool(Vector3(0, TRAWLER_DECK + 0.05, -5.0), GlowBuilder.LED, 4.2, 0.5, 0.0)
	gb.pool(Vector3(0, 0.05, -12.0), GlowBuilder.LED, 4.0, 0.1, 0.0)
	return gb.commit()
