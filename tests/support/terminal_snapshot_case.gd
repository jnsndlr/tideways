extends "res://tests/rule_test_case.gd"
## Start matching production terminals and cross the JSON boundary for restore tests.


func _world(renumber := false, uses_staging := false) -> Simulation:
	var region := TinyRegion.build()
	if renumber:
		region.map.towns.reverse()
		for i in region.map.towns.size():
			region.map.towns[i].id = i
		for route in region.map.routes:
			route.a = 1 - route.a
			route.b = 1 - route.b
	for town in region.map.towns:
		town.open_lanes = 0 if uses_staging else 2
		town.construction_staging_lanes = 1 if uses_staging else 0
		town.lane_extension_price = 150
	return region.start(root)


func _record(port: Terminal) -> Dictionary:
	var holding := TerminalHoldingSnapshot.capture(port)
	check(not holding.is_empty(), "Capture the terminal holding lot")
	return JSON.parse_string(
		JSON.stringify(
			{"holding": holding, "ledger": port.sim.ledger.snapshot(port.sim.map.routes)},
			"",
			true,
			true
		)
	)
