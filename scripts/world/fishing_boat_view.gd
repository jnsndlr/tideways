class_name FishingBoatView
extends Node3D
## The trawler's running and deck lights, and the warps running out to its net.

var _boat: FishingBoat
var _navigation: MeshInstance3D
var _steaming: MeshInstance3D
var _working: MeshInstance3D
var _warps := MeshInstance3D.new()


func _init(boat: FishingBoat) -> void:
	_boat = boat
	scale = Vector3.ONE * boat.spec.scale
	var lamps := VesselLightGroup.new(boat.lights)
	add_child(lamps)
	_navigation = lamps.add_lamp(Models.trawler_nav_lights())
	_steaming = lamps.add_lamp(Models.trawler_steaming_lights())
	_working = lamps.add_lamp(Models.trawler_working_lights())
	_warps.mesh = Models.trawler_warps()
	_warps.hide()
	add_child(_warps)


func _process(_delta: float) -> void:
	refresh()


func refresh() -> void:
	var alongside := _boat.state == FishingBoat.State.ALONGSIDE
	_navigation.visible = not alongside
	_steaming.visible = not alongside and not _boat.fishing()
	_working.visible = _boat.fishing() or (alongside and _boat.minutes_since_landing() < FishingBoat.LANDING.y)
	_warps.visible = _boat.net_out()
