class_name SailboatView
extends Node3D
## The main and jib in the hull's frame, raised under sail and furled under engine.

var _boat: Sailboat
var _hull: VesselHullView
var _main := MeshInstance3D.new()
var _jib := MeshInstance3D.new()


func _init(boat: Sailboat, hull: VesselHullView) -> void:
	_boat = boat
	_hull = hull
	_main.mesh = Models.sailboat_main()
	_main.position = SailboatModel.MAIN_PIVOT
	add_child(_main)
	_jib.mesh = Models.sailboat_jib()
	_jib.position = SailboatModel.jib_tack()
	add_child(_jib)


func _enter_tree() -> void:
	_boat.sails_changed.connect(_set_sails)
	_boat.sheet_changed.connect(_trim)
	_set_sails(not _boat.motoring)
	if not is_nan(_boat.sheet_angle):
		_trim(_boat.sheet_angle)


func _exit_tree() -> void:
	_boat.sails_changed.disconnect(_set_sails)
	_boat.sheet_changed.disconnect(_trim)


func _set_sails(hoisted: bool) -> void:
	_hull.mesh = Models.sailboat() if hoisted else Models.sailboat_furled()
	_main.visible = hoisted
	_jib.visible = hoisted


func _trim(angle: float) -> void:
	# The imported sails are cambered to +x. Mirror their belly to leeward,
	# flattening as they swing across through the wind.
	var belly := Basis.IDENTITY
	if SailboatModel.authored:
		var f := clampf(angle / 0.12, -1.0, 1.0)
		belly = Basis.from_scale(Vector3(f if absf(f) > 0.1 else 0.1 * signf(f + 1e-6), 1, 1))
	_main.basis = Basis(Vector3.UP, -angle) * belly
	var stay := (SailboatModel.jib_head() - SailboatModel.jib_tack()).normalized()
	_jib.basis = Basis(stay, -clampf(angle, -0.8, 0.8)) * belly
