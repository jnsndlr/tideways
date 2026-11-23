extends Node3D

const Kit := preload("res://scripts/world/dock_kit.gd")


func _ready() -> void:
	var kit := Kit.new()
	add_child(kit)
	var west := Vector3(-9, Kit.HIGH, 0)
	var hinge := kit.add_deck(Kit.Width.MAIN, west, Vector2.RIGHT, Kit.Support.PILES)
	var landing := kit.add_ramp(Kit.Width.MAIN, hinge, Vector2.RIGHT, Kit.LOW)
	kit.add_deck(Kit.Width.MAIN, landing, Vector2.RIGHT, Kit.Support.FLOATS)

	# Two fingers connect flush at the side edges of the main landings.
	var high_side := west + Vector3(3, 0, Kit.MAIN_WIDTH / 2)
	var tip := kit.add_deck(Kit.Width.FINGER, high_side, Vector2.DOWN, Kit.Support.PILES)
	tip = kit.add_ramp(Kit.Width.FINGER, tip, Vector2.DOWN, Kit.LOW)
	kit.add_deck(Kit.Width.FINGER, tip, Vector2.DOWN, Kit.Support.FLOATS)

	var low_side := landing + Vector3(3, 0, Kit.MAIN_WIDTH / 2)
	tip = kit.add_deck(Kit.Width.FINGER, low_side, Vector2.DOWN, Kit.Support.FLOATS)
	tip = kit.add_ramp(Kit.Width.FINGER, tip, Vector2.DOWN, Kit.HIGH)
	kit.add_deck(Kit.Width.FINGER, tip, Vector2.DOWN, Kit.Support.PILES)

	$Camera3D.look_at(Vector3(0, 0, 8))
