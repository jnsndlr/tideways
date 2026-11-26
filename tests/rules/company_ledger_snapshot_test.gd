extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	var north := MapData.Route.new()
	north.id = 3
	north.key = "north"
	var south := MapData.Route.new()
	south.id = 5
	south.key = "south"
	var routes: Array[MapData.Route] = [north, south]
	var fixture := FileAccess.get_file_as_string("res://tests/fixtures/company_ledger_v1.json")
	var legacy := CompanyLedgerSnapshot.restore(JSON.parse_string(fixture), routes)
	check(legacy != null, "Read the pinned v1 accounting fixture")
	if legacy:
		check(legacy.cash == 49903.5 and legacy.credit_vehicle(1, north.id) == 23.75
				and legacy.cash == 49927.25, "Continue from the fixture's balance and route fare")
	var company := CompanyLedger.new()
	company.set_route_vehicle_fare(north.id, 14.5)
	company.set_route_passenger_fare(south.id, 0.0)
	company.credit_vehicle(3, north.id)
	company.credit_passenger(south.id)
	company.receive("sales", 10.5)
	company.start_day()
	company.refund_fare(7.5)
	company.spend("purchases", 51000)
	company.spend("fuel", 3.75)
	company.spend("crew", 2.5)
	var saved := company.snapshot(routes)
	var record = JSON.parse_string(JSON.stringify(saved, "", true, true))
	north.id = 6
	south.id = 3
	var restored := CompanyLedgerSnapshot.restore(record, [south, north])
	check(restored != null, "Restore the live ledger with renumbered routes")
	if restored:
		check(restored.snapshot(routes) == saved, "Restore balances, both days, counters and stable-key prices")
		var before := restored.cash
		var fares_before := restored.revenue_today
		check(restored.credit_vehicle(2, north.id) == 29.0, "Next truck pays its route's price")
		check(restored.cash == before + 29.0 and restored.revenue_today == fares_before + 29.0
				and restored.cars_total == 2, "Only the new boarding is credited")
		restored.set_vehicle_fare(31)
		restored.set_passenger_fare(7)
		check(restored.vehicle_fare_for(south.id) == 31 and restored.passenger_fare_for(north.id) == 7,
				"Routes without explicit overrides follow future default changes")
		check(restored.passenger_fare_for(south.id) == 0, "Keep the explicit free crossing")
		check(restored.today != record.today and restored.yesterday == record.yesterday,
				"Posting after restore changes only the restored ledger")
	for field in record:
		var missing: Dictionary = record.duplicate(true)
		missing.erase(field)
		check(CompanyLedgerSnapshot.restore(missing, routes) == null, "Reject missing %s" % field)
	for bad in [{"version": 2}, {"version": true}, {"cash": INF}, {"cars_total": 1.5},
			{"today": {}}, {"route_fares": {"unknown": {"vehicle": 18}}},
			{"route_fares": {"north": {"passenger": -1}}}, {"route_fares": {"north": {"typo": 0}}}]:
		check(CompanyLedgerSnapshot.restore(record.merged(bad, true), routes) == null, "Reject %s" % bad)
	check(CompanyLedgerSnapshot.restore(record, [south, south]) == null, "Reject ambiguous region identity")
	check(company.snapshot(routes).is_empty(), "Reject capture if a live override no longer resolves")
	finish()
