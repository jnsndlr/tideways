extends "res://tests/rule_test_case.gd"

const ContactSamples := preload("res://tests/traffic/vehicle_contact_samples.gd")


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var samples := ContactSamples.new()
	var a := 1 << 36
	for i in 5:
		samples.begin_sample()
		if i % 2 == 0:
			samples.record(a, 8)
		else:
			samples.record(8, a)
		samples.record(a + i + 1, 8)
	check(samples.observations == 10, "Keep aggregate observations for every vehicle pair")
	check(samples.longest == 5, "Reversing collection order preserves the same pair")
	check(samples.lasting_episodes == 1, "One sustained contact counts as one episode")
	samples.begin_sample()
	for i in 4:
		samples.begin_sample()
		samples.record(a, 8)
	check(samples.lasting_episodes == 2, "A sample without a contact separates episodes")
	var first := Vehicle.new()
	var second := Vehicle.new()
	root.add_child(first)
	root.add_child(second)
	var body := _box(first)
	var trailer := _box(second)
	body.position = Vector3(4, 0, 5)
	trailer.position = Vector3(0, 0, 5)
	check(not ContactSamples.surfaces_intersect(first, second), "Separate mesh surfaces")
	trailer.position = Vector3(4.4, 0.2, 5.3)
	trailer.rotation.y = 0.4
	check(ContactSamples.surfaces_intersect(first, second), "Detect a rotated trailer body")
	trailer.hide()
	check(not ContactSamples.surfaces_intersect(first, second), "Skip hidden geometry")
	first.free()
	second.free()
	finish()


func _box(vehicle: Vehicle) -> MeshInstance3D:
	var part := MeshInstance3D.new()
	part.mesh = BoxMesh.new()
	vehicle.add_child(part)
	return part
