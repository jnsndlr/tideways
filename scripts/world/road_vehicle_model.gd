class_name RoadVehicleModel
extends RefCounted
## Chooses and builds car, truck and trailer models, paints and road lights.

const CAR_COLORS := [
	Color(0.75, 0.16, 0.14),
	Color(0.16, 0.32, 0.62),
	Color(0.92, 0.92, 0.9),
	Color(0.62, 0.64, 0.66),
	Color(0.12, 0.12, 0.14),
	Color(0.9, 0.72, 0.2),
	Color(0.2, 0.45, 0.3),
	Color(0.85, 0.4, 0.15),
	Color(0.2, 0.55, 0.6)
]

## Blender bodies use VehicleData dimensions and lamp positions in real metres.
## Classic traffic uses the procedural car and truck and a distinct paint palette.
const ASSET := "res://assets/models/vehicles.glb"
# The cars (VehicleData keys) and how common each is on the road: sedans and SUVs
# (100 each), pickups (45, full-size first), minivans (25) and vans (20), work vans first.
const VEHICLES := {
	"sedan_modern": 25,
	"sedan_compact": 18,
	"sedan_nineties": 15,
	"sedan_ev": 10,
	"sedan_boxy": 8,
	"sedan_exec": 8,
	"sedan_luxury": 8,
	"sedan_sport": 8,
	"suv_crossover": 30,
	"suv_threerow": 20,
	"suv_nineties": 10,
	"suv_offroad": 10,
	"suv_luxury": 9,
	"suv_ev": 9,
	"suv_cherokee": 8,
	"suv_coupe": 4,
	"minivan_family": 6,
	"minivan_modern": 5,
	"minivan_bold": 4,
	"minivan_nineties": 3,
	"minivan_suvish": 3,
	"minivan_boxy": 2,
	"minivan_compact": 1,
	"minivan_ev": 1,
	"van_cargo": 6,
	"van_hightop": 3,
	"van_compact": 3,
	"van_passenger": 2,
	"van_shuttle": 2,
	"van_camper": 2,
	"van_retro": 1,
	"van_overland": 1,
	"pickup_fullsize": 14,
	"pickup_midsize": 8,
	"pickup_compact": 5,
	"pickup_trail": 5,
	"pickup_dually": 4,
	"pickup_squarebody": 4,
	"pickup_rock": 3,
	"pickup_sport": 2,
	"pickup_princess": 1
}
# Trucks (Vehicle.is_truck: a share of the traffic, see Simulation) and how common:
# box trucks and step vans on their rounds first; "rig" is a tractor-trailer, its
# tractor and trailer picked from TRACTORS and TRAILERS.
const TRUCKS := {"truck_box": 30, "truck_step": 20, "truck_reefer": 14, "truck_tank": 10, "rig": 26}
const TRACTORS := {
	"tractor_day": 30,
	"tractor_aero": 25,
	"tractor_midroof": 20,
	"tractor_longnose": 15,
	"tractor_classic": 10
}
const TRAILERS := {
	"trailer_van": 25,
	"trailer_reefer": 15,
	"trailer_container": 15,
	"trailer_flatbed": 12,
	"trailer_logs": 10,
	"trailer_dump": 10,
	"trailer_tank": 8,
	"trailer_carhauler": 5
}
# Paint and how common: whites, blacks, greys and silvers first, as in any car park.
const PAINTS := [
	[Color(0.9, 0.9, 0.88), 20],
	[Color(0.86, 0.84, 0.78), 5],
	[Color(0.1, 0.1, 0.11), 16],
	[Color(0.3, 0.31, 0.33), 10],
	[Color(0.66, 0.68, 0.7), 12],
	[Color(0.15, 0.3, 0.6), 7],
	[Color(0.12, 0.16, 0.3), 4],
	[Color(0.72, 0.14, 0.11), 8],
	[Color(0.42, 0.1, 0.12), 3],
	[Color(0.2, 0.4, 0.27), 4],
	[Color(0.72, 0.65, 0.52), 3],
	[Color(0.25, 0.55, 0.6), 3],
	[Color(0.9, 0.72, 0.18), 2],
	[Color(0.88, 0.42, 0.14), 1],
	[Color(0.4, 0.3, 0.22), 2]
]

static var authored := (
	not "--classic-cars" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)


static func classic_car(color_index: int) -> ArrayMesh:
	return Models._cached(
		"car_%d" % color_index,
		func():
			var col: Color = CAR_COLORS[color_index % CAR_COLORS.size()]
			var mb := MeshBuilder.new()
			mb.box(Vector3(0, 0.44, 0), Vector3(1.0, 0.5, 2.0), col)
			mb.box(Vector3(0, 0.86, -0.12), Vector3(0.84, 0.36, 1.05), col.lightened(0.05))
			mb.box(Vector3(0, 0.86, -0.12), Vector3(0.86, 0.24, 0.95), Models.GLASS)
			mb.box(Vector3(0, 0.86, -0.12), Vector3(0.7, 0.24, 1.07), Models.GLASS)
			for x: float in [-0.46, 0.46]:
				for z: float in [-0.62, 0.62]:
					mb.box(Vector3(x, 0.2, z), Vector3(0.16, 0.36, 0.42), Color(0.08, 0.08, 0.08))
			return mb.commit()
	)


## A car picked by how common each is, from `u` in [0, 1).
static func pick_vehicle(u: float) -> String:
	return pick_weighted(VEHICLES, u)


## A key of `table` (key -> weight) picked by weight, from `u` in [0, 1).
static func pick_weighted(table: Dictionary, u: float) -> String:
	var total := 0
	for n: String in table:
		total += table[n]
	var x := u * total
	for n: String in table:
		x -= table[n]
		if x < 0.0:
			return n
	return table.keys()[0]


## A paint (index into PAINTS) picked by how common each is, from `u` in [0, 1).
static func pick_paint(u: float) -> int:
	var total := 0
	for p: Array in PAINTS:
		total += p[1]
	var x := u * total
	for i in PAINTS.size():
		x -= PAINTS[i][1]
		if x < 0.0:
			return i
	return 0


## Vehicle `model` (a VehicleData key) in paint `paint`, at its modelled (real) size.
static func body_mesh(model: String, paint: int) -> ArrayMesh:
	var lib := ModelParts.library(ASSET)
	var key := model.replace("_", "")
	# Only the body and accent take paint. A fixed trailer can share its mesh across liveries.
	if TRAILERS.has(model) and not lib.has(key + "body") and not lib.has(key + "accent"):
		paint = 0
	return Models._cached(
		"%s_%d" % [model, paint],
		func():
			var mb := MeshBuilder.new()
			mb.append_part(lib[key + "fixed"], Transform3D.IDENTITY)
			var col: Color = PAINTS[paint % PAINTS.size()][0]
			if lib.has(key + "body"):  # (some trailers have nothing painted)
				mb.append_part(lib[key + "body"], Transform3D.IDENTITY, Color.WHITE, col)
			if lib.has(key + "accent"):
				# A two-tone band: a darker shade of the paint.
				mb.append_part(
					lib[key + "accent"], Transform3D.IDENTITY, Color.WHITE, col.darkened(0.45)
				)
			if lib.has(key + "head"):  # (trailers have none)
				mb.append_part(
					lib[key + "head"],
					Transform3D.IDENTITY,
					Color.WHITE,
					Models.lamp_glass(GlowBuilder.HEADLIGHT)
				)
			mb.append_part(
				lib[key + "tail"],
				Transform3D.IDENTITY,
				Color.WHITE,
				Models.lamp_glass(GlowBuilder.TAIL)
			)
			return mb.commit()
	)


static func classic_truck(color_index: int) -> ArrayMesh:
	return Models._cached(
		"truck_%d" % color_index,
		func():
			var col: Color = CAR_COLORS[color_index % CAR_COLORS.size()]
			var mb := MeshBuilder.new()
			mb.box(Vector3(0, 0.7, 0.72), Vector3(1.1, 1.0, 0.8), col)
			mb.box(Vector3(0, 0.9, 1.1), Vector3(0.95, 0.4, 0.06), Models.GLASS)
			mb.box(Vector3(0, 0.95, -0.42), Vector3(1.15, 1.3, 1.5), Color(0.9, 0.9, 0.88))
			for x: float in [-0.5, 0.5]:
				for z: float in [-0.8, 0.75]:
					mb.box(Vector3(x, 0.2, z), Vector3(0.16, 0.38, 0.44), Color(0.08, 0.08, 0.08))
			return mb.commit()
	)


## Head and tail lights for every car and truck (+Z is the front), plus the cone
## they throw down the road. Drawn per vehicle by NightLights' multimesh.
static func _classic_lights() -> ArrayMesh:
	return Models._cached(
		"car_lights",
		func():
			var gb := GlowBuilder.new()
			for x: float in [-0.32, 0.32]:
				gb.glow(
					Vector3(x, 0.5, 1.08),
					GlowBuilder.HEADLIGHT,
					0.14,
					7.0,
					false,
					0.0,
					Vector3.BACK,
					0.0
				)
				gb.glow(
					Vector3(x * 1.1, 0.55, -1.14),
					GlowBuilder.TAIL,
					0.11,
					5.0,
					false,
					0.0,
					Vector3.FORWARD,
					0.0
				)
			gb.cone(Vector3(0, 0.1, 1.4), Vector3.BACK, 9.0, 2.2, GlowBuilder.HEADLIGHT, 0.4)
			return gb.commit()
	)


## The same for vehicle `model` (a VehicleData key; "" is the code-built car and truck),
## its lamps where the model has them.
static func lights(model: String) -> ArrayMesh:
	if model == "":
		return _classic_lights()
	return Models._cached(
		"lights_" + model,
		func():
			var d: Dictionary = VehicleData.VARIANTS[model]
			var head: Vector3 = d.head
			var tail: Vector3 = d.tail
			var trailer := d.has("pin")  # (no headlamps)
			var gb := GlowBuilder.new()
			for sx: float in [-1.0, 1.0]:
				if not trailer:
					gb.glow(
						Vector3(head.x * sx, head.y, head.z + 0.03),
						GlowBuilder.HEADLIGHT,
						0.33,
						7.0,
						false,
						0.0,
						Vector3.BACK,
						0.0
					)
				gb.glow(
					Vector3(tail.x * sx, tail.y, tail.z - 0.03),
					GlowBuilder.TAIL,
					0.26,
					5.0,
					false,
					0.0,
					Vector3.FORWARD,
					0.0
				)
			if not trailer:
				gb.cone(
					Vector3(0, 0.25, head.z + 0.3),
					Vector3.BACK,
					21.0,
					5.2,
					GlowBuilder.HEADLIGHT,
					0.4
				)
			return gb.commit()
	)
