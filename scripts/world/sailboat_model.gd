class_name SailboatModel
extends RefCounted
## Sloop hull, sail pivots and anchor light in authored and classic modes.

const ASSET := "res://assets/models/sailboat_mid.glb"
const HULL_PARTS := ["hull", "deckfittings", "keel", "mast", "rigging"]
const MAST_TOP := Vector3(0, 4.3, 0.3)
const LANTERN := 0.8
const MAIN_PIVOT := Vector3(0, 0, 0.2)
const CLASSIC_TACK := Vector3(0, 0.8, 1.7)
const CLASSIC_HEAD := Vector3(0, 3.6, 0.35)
const AUTHORED_TACK := Vector3(0, 0.62, 1.976)
const AUTHORED_HEAD := Vector3(0, 3.55, 0.391)

static var authored := (
	not "--classic-sailboat" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func jib_tack() -> Vector3:
	return AUTHORED_TACK if authored else CLASSIC_TACK


static func jib_head() -> Vector3:
	return AUTHORED_HEAD if authored else CLASSIC_HEAD


static func hull(furled := false) -> ArrayMesh:
	var mb: MeshBuilder
	if authored:
		var parts := HULL_PARTS + ["furled"] if furled else HULL_PARTS
		mb = ModelParts.merge_named(ASSET, parts)
	else:
		mb = MeshBuilder.new()
		var hull := PackedVector2Array(
			[
				Vector2(-0.6, -1.6),
				Vector2(0.6, -1.6),
				Vector2(0.65, 0.6),
				Vector2(0.0, 2.0),
				Vector2(-0.65, 0.6)
			]
		)
		mb.extrude(hull, -0.3, 0.35, Models.WHITE, Color(0.75, 0.62, 0.45), 0.7)
		mb.box(Vector3(0, 2.3, 0.3), Vector3(0.08, 4.0, 0.08), Color(0.8, 0.8, 0.8))
		if furled:
			mb.box(Vector3(0, 0.78, -0.55), Vector3(0.07, 0.07, 1.8), Color(0.8, 0.8, 0.8))
			mb.box(Vector3(0, 0.9, -0.5), Vector3(0.2, 0.18, 1.6), Color(0.2, 0.32, 0.5))
	Models.add_lantern(mb, MAST_TOP, GlowBuilder.LED, LANTERN)
	return mb.commit()


static func mainsail() -> ArrayMesh:
	if authored:
		return ModelParts.merge_named(ASSET, ["mainsail"]).commit()
	var mb := MeshBuilder.new()
	var a := Vector3(0, 0.7, 0)
	var b := Vector3(0, 4.2, 0)
	var c := Vector3(0, 0.7, -1.6)
	mb.tri(a, b, c, Color(0.98, 0.98, 0.96), Vector3.RIGHT)
	mb.tri(a, b, c, Color(0.98, 0.98, 0.96), Vector3.LEFT)
	mb.box(Vector3(0, 0.66, -0.8), Vector3(0.07, 0.07, 1.7), Color(0.8, 0.8, 0.8))
	return mb.commit()


static func jib() -> ArrayMesh:
	if authored:
		return ModelParts.merge_named(ASSET, ["jib"]).commit()
	var mb := MeshBuilder.new()
	var head := CLASSIC_HEAD - CLASSIC_TACK
	var clew := Vector3(0, 0.8, 0.4) - CLASSIC_TACK
	mb.tri(head, clew, Vector3.ZERO, Color(0.95, 0.95, 0.9), Vector3.RIGHT)
	mb.tri(head, clew, Vector3.ZERO, Color(0.95, 0.95, 0.9), Vector3.LEFT)
	return mb.commit()


static func anchor_light() -> ArrayMesh:
	var gb := GlowBuilder.new()
	gb.glow(
		Models.lantern_glow_at(MAST_TOP, LANTERN),
		GlowBuilder.LED,
		0.13,
		4.0,
		true,
		0.0,
		Vector3.ZERO,
		Models.LAMP_ON_AT
	)
	return gb.commit()
