class_name TieUpPier
extends Node3D

## Adjacent lay-up berths share a timber deck, access ramp and mooring dolphins.
## Working slips separate decks. Coordinates are in the terminal frame (x across, z out).

const Kit := preload("res://scripts/world/dock_kit.gd")
const DOLPHIN_LARGE := "res://assets/models/timber_dolphin_large.glb"
const DOLPHIN_SMALL := "res://assets/models/timber_dolphin_small.glb"
const DOLPHIN_SCALE := 1.8
# Tops measured on the authored models, relative to their waterline origins.
const SMALL_CAP := Vector3(0, 2.67 * DOLPHIN_SCALE, Layout.PIER_END + 10.0)
const LARGE_CAP := Vector3(0, 3.74 * DOLPHIN_SCALE, Layout.PIER_END + 52.0)
const PIER_U := Layout.PIER_END - Kit.MAIN_WIDTH * 0.5  # deck centre; seaward edge at PIER_END
const END_REACH := 6.0           # how far the main deck runs past the outer dolphin rows


## Deck groups separated by a working slip keep its apron and approach open.
var rows: Array[float] = []
var port_rows: Array[float] = []


static func available() -> bool:
	return Kit.available() and ResourceLoader.exists(DOLPHIN_LARGE, "PackedScene") and ResourceLoader.exists(DOLPHIN_SMALL, "PackedScene")


func _init(centres: Array[float], town: MapData.Town) -> void:
	var small: PackedScene = load(DOLPHIN_SMALL)
	var large: PackedScene = load(DOLPHIN_LARGE)
	var first := 0
	for i in centres.size():
		if i + 1 < centres.size() and centres[i + 1] - centres[i] <= Layout.TIE_UP_SPACING + 0.01:
			continue
		_build_group(centres, first, i, town)
		first = i + 1
	for v in rows:
		_dolphin(small, Vector3(v, 0, SMALL_CAP.z))
		_dolphin(large, Vector3(v, 0, LARGE_CAP.z))


func _build_group(centres: Array[float], first: int, last: int, town: MapData.Town) -> void:
	var lo := centres[first] - Layout.TIE_UP_SPACING * 0.5
	var top := centres[last] + Layout.TIE_UP_SPACING * 0.5
	var kit := Kit.new()
	kit.name = "Deck"
	add_child(kit, true)
	var hi := Kit.HIGH

	# The main deck: square to the shore, the hull ends lie up against its seaward edge.
	var span := top - lo + END_REACH * 2.0
	var runs := ceili(span / Kit.RUN)
	var p := Vector3((lo + top) * 0.5 - runs * Kit.RUN * 0.5, hi, PIER_U)
	var deck_lo := p.x
	for k in runs:
		p = kit.add_deck(Kit.Width.MAIN, p, Vector2.RIGHT, Kit.Support.PILES)

	# The catwalk from the lot front comes down a ramp to the deck's landward side.
	var shore_edge := PIER_U - Kit.MAIN_WIDTH * 0.5
	var walk_runs := ceili((shore_edge - town.lot_front_u()) / Kit.RUN)
	var nearest := clampi(floori(-deck_lo / Kit.RUN), 0, runs - 1)
	var walk := Vector3(deck_lo + (nearest + 0.5) * Kit.RUN, town.lot_y, shore_edge - walk_runs * Kit.RUN)
	var ramps := clampi(ceili(absf(town.lot_y - hi) * 5.0 / Kit.RUN), 1, walk_runs)
	for k in ramps:
		var y := lerpf(town.lot_y, hi, float(k + 1) / ramps)
		walk = kit.add_ramp(Kit.Width.FINGER, walk, Vector2(0, 1), y)
	for k in walk_runs - ramps:
		walk = kit.add_deck(Kit.Width.FINGER, walk, Vector2(0, 1), Kit.Support.PILES)

	# A row of dolphins either side of each berth, shared between neighbours:
	# a small one near the pier and a large one out towards the hull's far end.
	rows.append(lo)
	port_rows.append(lo)
	for i in range(first, last + 1):
		rows.append(centres[i] + Layout.TIE_UP_SPACING * 0.5)


func _dolphin(scene: PackedScene, at: Vector3) -> void:
	var d: Node3D = scene.instantiate()
	add_child(d)
	var turn := fposmod(at.x * 0.37 + at.z * 0.11, TAU)
	d.transform = Transform3D(Basis(Vector3.UP, turn).scaled(Vector3.ONE * DOLPHIN_SCALE), at)
