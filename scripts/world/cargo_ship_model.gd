class_name CargoShipModel
extends RefCounted
## Cargo hulls, liveries and matching lights for container ships, tankers and bulkers.

# Container ship (+Z is the bow): masthead lantern heights and the sidelights.
const CARGO_FORE_MAST := Vector3(0, 9.0, 28.5)
const CARGO_AFT_MAST := Vector3(0, 15.6, -24.0)
const CARGO_LANTERN := 1.6
const CARGO_SIDELIGHT := Vector3(6.3, 11.6, -24.0)
const CARGO_FUNNELS := [Color(0.85, 0.55, 0.12), Color(0.15, 0.35, 0.65), Color(0.75, 0.15, 0.13)]
const CONTAINERS := [
	Color(0.62, 0.2, 0.15),
	Color(0.18, 0.33, 0.6),
	Color(0.2, 0.48, 0.32),
	Color(0.88, 0.5, 0.15),
	Color(0.55, 0.57, 0.6),
	Color(0.14, 0.5, 0.55),
	Color(0.9, 0.9, 0.86),
	Color(0.85, 0.7, 0.2),
	Color(0.45, 0.25, 0.4)
]

# Tankers: dark topsides over a deck painted green or oxide red, by variant.
const TANKER_TOPSIDES := [Color(0.1, 0.1, 0.11), Color(0.42, 0.11, 0.1), Color(0.12, 0.2, 0.3)]
const TANKER_DECKS := [Color(0.3, 0.42, 0.3), Color(0.3, 0.42, 0.3), Color(0.5, 0.22, 0.17)]
const TANKER_FUNNELS := [Color(0.85, 0.15, 0.12), Color(0.92, 0.92, 0.9), Color(0.9, 0.72, 0.18)]

## The tanker and bulker share the authored cargo hull frame, lights and lettering.
const TANKER_ASSET := "res://assets/models/tanker_mid.glb"
const BULKER_ASSET := "res://assets/models/bulker_mid.glb"
# The band on the mid-poly ships' white funnels.
const MID_TANKER_FUNNELS := [Color(0.8, 0.14, 0.12), Color(0.12, 0.3, 0.55), Color(0.9, 0.72, 0.18)]

# Bulk carriers: topsides, hatch covers and deck cranes, by variant.
const BULKER_TOPSIDES := [Color(0.14, 0.22, 0.34), Color(0.2, 0.21, 0.22), Color(0.48, 0.15, 0.12)]
const BULKER_HATCHES := [Color(0.55, 0.18, 0.14), Color(0.2, 0.42, 0.3), Color(0.18, 0.3, 0.5)]
const BULKER_CRANES := [Color(0.9, 0.74, 0.2), Color(0.92, 0.92, 0.9), Color(0.9, 0.74, 0.2)]
const BULKER_FUNNELS := [Color(0.15, 0.35, 0.65), Color(0.85, 0.55, 0.12), Color(0.94, 0.95, 0.94)]
# The mid-poly bulkers' deck and coamings, and the band on their white funnels.
const MID_BULKER_DECKS := [Color(0.32, 0.37, 0.34), Color(0.45, 0.2, 0.16), Color(0.36, 0.38, 0.38)]
const MID_BULKER_FUNNELS := [
	Color(0.15, 0.35, 0.65), Color(0.85, 0.55, 0.12), Color(0.1, 0.1, 0.11)
]

## art/cargo_mid.py also generates CargoMidData for hull lettering and container slots.
const CONTAINER_ASSET := "res://assets/models/cargo_mid.glb"

const MID_CARGO_HULLS := [Color(0.12, 0.16, 0.24), Color(0.1, 0.1, 0.11), Color(0.42, 0.12, 0.1)]

const MID_CARGO_SIDELIGHT_SCALE := 1.4

static var authored_container := (
	not "--classic-cargo" in OS.get_cmdline_user_args() and ResourceLoader.exists(CONTAINER_ASSET)
)
static var authored_tanker := authored_container and ResourceLoader.exists(TANKER_ASSET)
static var authored_bulker := authored_container and ResourceLoader.exists(BULKER_ASSET)


## A container ship about 64 m long and 11 m in the beam, its accommodation block
## aft. `variant` picks the funnel colour and how the boxes are stacked.
static func container(variant: int) -> ArrayMesh:
	if authored_container:
		return _mid_cargo(variant).commit()
	var mb := MeshBuilder.new()
	var topsides := Color(0.12, 0.16, 0.24)
	_cargo_hull(mb, topsides, Color(0.4, 0.42, 0.43), CARGO_FUNNELS[variant % CARGO_FUNNELS.size()])
	# Containers: seven bays of four stacks, one to three high.
	var r := RandomNumberGenerator.new()
	r.seed = 4111 + variant * 97
	for bay in 7:
		var z := -18.5 + bay * 6.2
		for col in 4:
			var x := -3.75 + col * 2.5
			var tiers := r.randi_range(1, 3) if variant % 3 != 2 else r.randi_range(2, 3)
			for t in tiers:
				var c: Color = CONTAINERS[r.randi_range(0, CONTAINERS.size() - 1)]
				mb.box(
					Vector3(x, 3.2 + 1.25 + t * 2.5, z),
					Vector3(2.4, 2.45, 6.0),
					c.darkened(r.randf() * 0.12)
				)
	return mb.commit()


## A tanker on the same hull as the container ship: a flat deck with its cargo
## lines and the catwalk running fore and aft, the manifold and its hose crane
## amidships.
static func tanker(variant: int) -> ArrayMesh:
	if authored_tanker:
		var paint := {
			"hull": TANKER_TOPSIDES[variant % TANKER_TOPSIDES.size()],
			"deck": TANKER_DECKS[variant % TANKER_DECKS.size()],
			"funnel": MID_TANKER_FUNNELS[variant % MID_TANKER_FUNNELS.size()]
		}
		return _mid_cargo_ship(TANKER_ASSET, paint).commit()
	var mb := MeshBuilder.new()
	var deck: Color = TANKER_DECKS[variant % TANKER_DECKS.size()]
	_cargo_hull(
		mb,
		TANKER_TOPSIDES[variant % TANKER_TOPSIDES.size()],
		deck,
		TANKER_FUNNELS[variant % TANKER_FUNNELS.size()]
	)
	var pipe := Color(0.62, 0.64, 0.6)
	var steel := Color(0.3, 0.32, 0.33)
	var z0 := -21.6
	var z1 := 22.8
	var zc := (z0 + z1) * 0.5
	var span := z1 - z0
	# Cargo lines along the deck either side of the centreline.
	for x: float in [-2.0, -1.4, 1.4, 2.0]:
		mb.box(Vector3(x, 3.5, zc), Vector3(0.3, 0.3, span), pipe)
	# The catwalk on its posts, high over the lines.
	mb.box(Vector3(0, 5.0, zc), Vector3(1.1, 0.12, span), Models.WHITE)
	for i in 9:
		mb.box(
			Vector3(0, 4.1, z0 + 1.0 + i * (span - 2.0) / 8.0), Vector3(0.2, 1.8, 0.2), Models.WHITE
		)
	# Tank hatches and vent posts down either side.
	for i in 6:
		var z := -17.0 + i * 7.0
		for x: float in [-3.6, 3.6]:
			mb.cylinder(Vector3(x, 3.2, z), 0.55, 0.55, 0.4, 8, steel)
			mb.box(Vector3(x * 0.8, 4.0, z + 2.0), Vector3(0.16, 1.6, 0.16), pipe)
	# The manifold athwartships, with its hose crane.
	for dz: float in [-0.6, 0.6]:
		mb.box(Vector3(0, 3.6, dz), Vector3(10.4, 0.36, 0.36), pipe)
	for x: float in [-5.0, 5.0]:
		mb.box(Vector3(x, 3.9, 0), Vector3(0.6, 1.1, 2.0), steel)
	mb.cylinder(Vector3(0, 3.2, -2.6), 0.4, 0.35, 4.4, 8, Color(0.88, 0.72, 0.2))
	var a := Vector3(0, 7.4, -2.6)
	var b := Vector3(3.6, 4.6, 3.0)
	mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
	mb.box(Vector3.ZERO, Vector3(0.36, 0.36, a.distance_to(b)), Color(0.88, 0.72, 0.2))
	mb.xform = Transform3D.IDENTITY
	# Fire monitors on their platform before the bridge.
	mb.box(Vector3(0, 5.6, -20.2), Vector3(4.0, 0.15, 1.4), Models.WHITE)
	for x: float in [-1.4, 1.4]:
		mb.box(Vector3(x, 5.9, -20.2), Vector3(0.3, 0.5, 0.6), Color(0.75, 0.15, 0.13))
	return mb.commit()


## A geared bulk carrier on the same hull: five big hatches under folding
## covers, and four deck cranes between them with their jibs stowed forward.
static func bulker(variant: int) -> ArrayMesh:
	if authored_bulker:
		var paint := {
			"hull": BULKER_TOPSIDES[variant % BULKER_TOPSIDES.size()],
			"deck": MID_BULKER_DECKS[variant % MID_BULKER_DECKS.size()],
			"hatch": BULKER_HATCHES[variant % BULKER_HATCHES.size()],
			"crane": BULKER_CRANES[variant % BULKER_CRANES.size()],
			"funnel": MID_BULKER_FUNNELS[variant % MID_BULKER_FUNNELS.size()]
		}
		return _mid_cargo_ship(BULKER_ASSET, paint).commit()
	var mb := MeshBuilder.new()
	var topsides: Color = BULKER_TOPSIDES[variant % BULKER_TOPSIDES.size()]
	var hatch: Color = BULKER_HATCHES[variant % BULKER_HATCHES.size()]
	var crane: Color = BULKER_CRANES[variant % BULKER_CRANES.size()]
	_cargo_hull(
		mb, topsides, Color(0.45, 0.2, 0.16), BULKER_FUNNELS[variant % BULKER_FUNNELS.size()]
	)
	var hatch_z := [-17.0, -8.2, 0.6, 9.4, 18.2]
	for z: float in hatch_z:
		# The coaming, and the two cover panels meeting on the centreline in
		# a shallow ridge.
		mb.box(Vector3(0, 3.95, z), Vector3(8.2, 1.5, 7.0), topsides.lightened(0.15))
		for x: float in [-1.0, 1.0]:
			mb.quad(
				Vector3(x * 4.0, 4.7, z - 3.4),
				Vector3(x * 4.0, 4.7, z + 3.4),
				Vector3(0, 5.2, z + 3.4),
				Vector3(0, 5.2, z - 3.4),
				hatch,
				Vector3(x * 0.2, 1, 0)
			)
			for dz: float in [-1.7, 0.0, 1.7]:
				mb.box(
					Vector3(x * 2.0, 4.95, z + dz), Vector3(3.9, 0.12, 0.14), hatch.darkened(0.25)
				)
		mb.tri(
			Vector3(-4.0, 4.7, z + 3.4),
			Vector3(4.0, 4.7, z + 3.4),
			Vector3(0, 5.2, z + 3.4),
			hatch.darkened(0.15),
			Vector3.BACK
		)
		mb.tri(
			Vector3(-4.0, 4.7, z - 3.4),
			Vector3(4.0, 4.7, z - 3.4),
			Vector3(0, 5.2, z - 3.4),
			hatch.darkened(0.15),
			Vector3.FORWARD
		)
	# Cranes between the hatches, jibs stowed forward and a touch outboard,
	# alternately to port and starboard.
	for i in 4:
		var z: float = (hatch_z[i] + hatch_z[i + 1]) * 0.5
		var side := 1.0 if i % 2 == 0 else -1.0
		mb.cylinder(Vector3(0, 3.2, z), 0.75, 0.65, 3.4, 8, crane)
		mb.box(Vector3(0, 7.3, z), Vector3(2.0, 1.6, 2.2), crane)
		mb.box(Vector3(side * 0.6, 7.5, z + 1.12), Vector3(0.7, 0.6, 0.06), Models.GLASS)
		var a := Vector3(side * 0.5, 7.6, z + 0.6)
		var b := Vector3(side * 2.2, 9.8, z + 9.0)
		mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
		mb.box(Vector3.ZERO, Vector3(0.45, 0.5, a.distance_to(b)), crane)
		mb.xform = Transform3D.IDENTITY
		mb.box(Vector3(0, 8.5, z - 0.4), Vector3(0.3, 1.0, 0.3), crane)
	return mb.commit()


## What every cargo ship has in common, 64 m long and 11 m in the beam: the
## hull, forecastle, the accommodation block aft with its bridge and funnel,
## the masts and the sidelights.
static func _cargo_hull(mb: MeshBuilder, topsides: Color, deck: Color, funnel: Color) -> void:
	var hull := PackedVector2Array(
		[
			Vector2(-5.6, -30),
			Vector2(-4.8, -32),
			Vector2(4.8, -32),
			Vector2(5.6, -30),
			Vector2(5.6, 20),
			Vector2(4.2, 27),
			Vector2(1.6, 31),
			Vector2(0, 32),
			Vector2(-1.6, 31),
			Vector2(-4.2, 27),
			Vector2(-5.6, 20)
		]
	)
	mb.extrude(hull, -2.6, 0.25, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.85)
	mb.extrude(hull, 0.25, 3.2, topsides, deck)
	mb.extrude(hull, 0.18, 0.32, Models.WHITE, Color(0, 0, 0, 0))
	# Forecastle and the breakwater behind it.
	mb.box(Vector3(0, 3.6, 26.0), Vector3(8.0, 0.8, 5.0), topsides)
	mb.box(Vector3(0, 4.4, 23.4), Vector3(10.4, 1.6, 0.25), Models.WHITE)
	# Accommodation block, bridge with its wings, and the funnel.
	mb.box(Vector3(0, 7.2, -25.0), Vector3(10.0, 8.0, 6.0), Models.WHITE)
	for y: float in [5.2, 7.4, 9.6]:
		mb.box(Vector3(0, y, -25.0), Vector3(10.1, 0.6, 6.1), Models.WINDOW_LIT)
	mb.box(Vector3(0, 11.6, -24.0), Vector3(12.4, 1.4, 3.2), Models.WHITE)
	mb.box(Vector3(0, 11.7, -24.0), Vector3(12.5, 0.5, 3.3), Models.WINDOW_LIT)
	mb.box(Vector3(0, 12.4, -24.0), Vector3(12.8, 0.2, 3.6), Color(0.3, 0.32, 0.34))
	mb.box(Vector3(0, 14.0, -24.0), Vector3(0.25, 3.0, 0.25), Models.WHITE)
	Models.add_lantern(mb, CARGO_AFT_MAST, GlowBuilder.LED, CARGO_LANTERN)
	mb.box(Vector3(0, 13.4, -28.6), Vector3(2.6, 3.6, 2.8), funnel)
	mb.box(Vector3(0, 15.45, -28.6), Vector3(2.65, 0.5, 2.85), Color(0.1, 0.1, 0.1))
	# Port (+X) red, starboard green, on the bridge wings' ends.
	for x: float in [-1.0, 1.0]:
		mb.box(
			Vector3(x * CARGO_SIDELIGHT.x, CARGO_SIDELIGHT.y, CARGO_SIDELIGHT.z),
			Vector3(0.2, 0.35, 0.45),
			Models.lamp_glass(GlowBuilder.RED if x > 0.0 else GlowBuilder.GREEN)
		)
	# Foremast.
	mb.box(Vector3(0, 6.1, 28.5), Vector3(0.3, 5.8, 0.3), Color(0.85, 0.75, 0.2))
	Models.add_lantern(mb, CARGO_FORE_MAST, GlowBuilder.LED, CARGO_LANTERN)


## The mid-poly container ship in `variant`'s livery, loaded as the variant stows it.
static func _mid_cargo(variant: int) -> MeshBuilder:
	var mb := _mid_cargo_ship(
		CONTAINER_ASSET,
		{
			"hull": MID_CARGO_HULLS[variant % MID_CARGO_HULLS.size()],
			"funnel": CARGO_FUNNELS[variant % CARGO_FUNNELS.size()]
		}
	)
	CargoContainerStowage.append(mb, ModelParts.library(CONTAINER_ASSET), variant)
	return mb


## One of the mid-poly ships on the container ship's hull (the feeder, tanker or bulk
## carrier, from `glb`): its fixed parts, the livery's parts each painted as `paint`
## has them, the glass, and the lanterns and sidelights where CargoMidData has them.
static func _mid_cargo_ship(glb: String, paint: Dictionary) -> MeshBuilder:
	var lib := ModelParts.library(glb)
	var mb := MeshBuilder.new()
	var one := Transform3D.IDENTITY
	mb.append_part(lib["fixed"], one)
	var parts := paint.merged(
		{
			"glass": Models.WINDOW_LIT,
			"window": Models.WINDOW,
			"lens": Models.lamp_glass(GlowBuilder.LED)
		}
	)
	for part: String in parts:
		mb.append_part(lib[part], one, Color.WHITE, parts[part])
	Models.add_lantern(mb, CargoMidData.FORE_MAST, GlowBuilder.LED, CARGO_LANTERN)
	Models.add_lantern(mb, CargoMidData.AFT_MAST, GlowBuilder.LED, CARGO_LANTERN)
	for sx: float in [-1.0, 1.0]:
		var sl := CargoMidData.SIDELIGHT
		Models.add_sidelight(mb, Vector3(sx * sl.x, sl.y, sl.z), sx, 1.0, MID_CARGO_SIDELIGHT_SCALE)
	return mb


## Masthead, stern and sidelights and the lit bridge's reflection, in the ship's frame
## selected to match the actual hull.
static func lights(mid: bool) -> ArrayMesh:
	if mid:
		return _mid_cargo_lights()
	var gb := GlowBuilder.new()
	for top: Vector3 in [CARGO_FORE_MAST, CARGO_AFT_MAST]:
		gb.glow(
			Models.lantern_glow_at(top, CARGO_LANTERN),
			GlowBuilder.LED,
			0.35,
			9.0,
			true,
			0.0,
			Vector3.ZERO,
			0.0
		)
	gb.glow(
		Vector3(-CARGO_SIDELIGHT.x, CARGO_SIDELIGHT.y, CARGO_SIDELIGHT.z),
		GlowBuilder.GREEN,
		0.25,
		7.0,
		true,
		0.0,
		Vector3(-1, 0, 0.8),
		0.0
	)
	gb.glow(CARGO_SIDELIGHT, GlowBuilder.RED, 0.25, 7.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
	gb.glow(Vector3(0, 4.0, -32.2), GlowBuilder.LED, 0.2, 5.0, true, 0.0, Vector3(0, 0, -1), 0.0)
	var window := Color(1.0, 0.74, 0.42)
	for x: float in [-6.25, 6.25]:
		for i in 5:
			gb.reflection(
				Vector3(x, 11.7, -25.4 + i * 0.7), window, 0.3, 2.2, Vector3(signf(x), 0, 0)
			)
	for x in 7:
		gb.reflection(Vector3(-4.5 + x * 1.5, 11.7, -22.3), window, 0.3, 2.2, Vector3(0, 0, 1))
	return gb.commit()


## The mid-poly ship's masthead, stern and sidelights and its lit bridge's reflection.
static func _mid_cargo_lights() -> ArrayMesh:
	var gb := GlowBuilder.new()
	for top: Vector3 in [CargoMidData.FORE_MAST, CargoMidData.AFT_MAST]:
		gb.glow(
			Models.lantern_glow_at(top, CARGO_LANTERN),
			GlowBuilder.LED,
			0.35,
			9.0,
			true,
			0.0,
			Vector3.ZERO,
			0.0
		)
	var sl := CargoMidData.SIDELIGHT
	for sx: float in [-1.0, 1.0]:
		var w := Vector3(sx * sl.x, sl.y, sl.z)
		gb.glow(
			Models.sidelight_glow_at(w, sx, MID_CARGO_SIDELIGHT_SCALE),
			GlowBuilder.RED if sx > 0.0 else GlowBuilder.GREEN,
			0.25,
			7.0,
			true,
			0.0,
			Vector3(sx, 0, 0.8),
			0.0
		)
	gb.glow(
		CargoMidData.STERN_LIGHT - Vector3(0, 0, 0.1),
		GlowBuilder.LED,
		0.2,
		5.0,
		true,
		0.0,
		Vector3(0, 0, -1),
		0.0
	)
	var window := Color(1.0, 0.74, 0.42)
	var y := CargoMidData.BRIDGE_SILL + 0.55
	var bz := CargoMidData.BRIDGE_Z
	for sx: float in [-1.0, 1.0]:
		for i in 5:
			gb.reflection(
				Vector3(
					sx * (CargoMidData.BRIDGE_HW + 0.05), y, lerpf(bz.x + 0.4, bz.y - 0.6, i / 4.0)
				),
				window,
				0.3,
				2.2,
				Vector3(sx, 0, 0)
			)
	for i in 7:
		gb.reflection(Vector3(-3.3 + i * 1.1, y, bz.y + 0.25), window, 0.3, 2.2, Vector3(0, 0, 1))
	return gb.commit()
