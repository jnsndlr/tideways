class_name TieUpPier
extends Node3D

## One timber pier along the shore that every tie-up slip lies against, like a
## ferry system's lay-up dock: a catwalk from the lot, a long main deck at the
## end of the slips, finger catwalks between the hulls and timber mooring
## dolphins out along each side. Built in the terminal frame (x across, z out).

const Kit := preload("res://scripts/world/dock_kit.gd")
const DOLPHIN_LARGE := preload("res://assets/models/timber_dolphin_large.glb")
const DOLPHIN_SMALL := preload("res://assets/models/timber_dolphin_small.glb")
const DOLPHIN_SCALE := 1.8
const PIER_U := Layout.PIER_END - Kit.MAIN_WIDTH * 0.5  # deck centre; seaward edge at PIER_END
const END_REACH := 6.0           # how far the main deck runs past the outer dolphin rows


static func available() -> bool:
	return ResourceLoader.exists("res://assets/models/dock_kit/main_deck.glb") \
		and ResourceLoader.exists("res://assets/models/timber_dolphin_large.glb")


func _init(berths: Array) -> void:
	# Each berth is (centre v, half width); they arrive in shore order.
	var lo: float = berths.front().x - berths.front().y - Layout.TIE_UP_ROW * 0.5
	var top: float = berths.back().x + berths.back().y + Layout.TIE_UP_ROW * 0.5
	var kit := Kit.new()
	kit.name = "Deck"
	add_child(kit)
	var hi := Kit.HIGH

	# The main deck: square to the shore, the hull ends lie up against its seaward edge.
	var span := top - lo + END_REACH * 2.0
	var runs := ceili(span / Kit.RUN)
	var p := Vector3((lo + top) * 0.5 - runs * Kit.RUN * 0.5, hi, PIER_U)
	var deck_lo := p.x
	for k in runs:
		p = kit.add_deck(Kit.Width.MAIN, p, Vector2.RIGHT, Kit.Support.PILES)

	# The catwalk from the lot front comes down a ramp to the deck's landward side.
	var walk := Vector3(deck_lo + Kit.RUN * 0.5, Layout.LOT_Y, PIER_U - Kit.MAIN_WIDTH * 0.5 - Kit.RUN * 5)
	walk = kit.add_ramp(Kit.Width.FINGER, walk, Vector2(0, 1), hi)
	for k in 4:
		walk = kit.add_deck(Kit.Width.FINGER, walk, Vector2(0, 1), Kit.Support.PILES)

	# A row of dolphins either side of each berth, shared between neighbours:
	# a small one near the pier and a large one out towards the hull's far end.
	var rows: Array[float] = [lo]
	for k in berths.size() - 1:
		rows.append(berths[k].x + berths[k].y + Layout.TIE_UP_ROW * 0.5)
	rows.append(top)
	for v in rows:
		_dolphin(DOLPHIN_SMALL, Vector3(v, 0, Layout.PIER_END + 10.0))
		_dolphin(DOLPHIN_LARGE, Vector3(v, 0, Layout.PIER_END + 52.0))


func _dolphin(scene: PackedScene, at: Vector3) -> void:
	var d: Node3D = scene.instantiate()
	add_child(d)
	var turn := fposmod(at.x * 0.37 + at.z * 0.11, TAU)
	d.transform = Transform3D(Basis(Vector3.UP, turn).scaled(Vector3.ONE * DOLPHIN_SCALE), at)
