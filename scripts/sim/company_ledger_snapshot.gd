class_name CompanyLedgerSnapshot
extends RefCounted
## The accounting section of a company snapshot. Store only explicit fare overrides
## so a later change to the company price still reaches routes using the default.
const MAX_JSON_INTEGER := 9007199254740991


static func capture(
	ledger: CompanyLedger, fares: FareSchedule, routes: Array[MapData.Route]
) -> Dictionary:
	var overrides := {}
	var route_keys := _route_keys(routes)
	if route_keys.size() != routes.size():
		return {}
	for route_id in fares.route_vehicle_fares:
		if not route_keys.has(route_id):
			return {}
		overrides[route_keys[route_id]] = {"vehicle": fares.route_vehicle_fares[route_id]}
	for route_id in fares.route_passenger_fares:
		if not route_keys.has(route_id):
			return {}
		var key: String = route_keys[route_id]
		var prices: Dictionary = overrides.get(key, {})
		prices["passenger"] = fares.route_passenger_fares[route_id]
		overrides[key] = prices
	return {
		"version": 1,
		"cash": ledger.cash, "revenue_total": ledger.revenue_total,
		"today": ledger.today.duplicate(), "yesterday": ledger.yesterday.duplicate(),
		"cars_today": ledger.cars_today, "cars_yesterday": ledger.cars_yesterday, "cars_total": ledger.cars_total,
		"passengers_today": ledger.passengers_today, "passengers_yesterday": ledger.passengers_yesterday,
		"passengers_total": ledger.passengers_total, "vehicle_fare": ledger.vehicle_fare,
		"passenger_fare": ledger.passenger_fare, "route_fares": overrides,
	}


## Rebuild before installing the ledger. Loading directly credits no transactions.
static func restore(record: Variant, routes: Array[MapData.Route]) -> CompanyLedger:
	if not record is Dictionary or not _number(record.get("version")) or record.version != 1:
		return null
	if not _number(record.get("cash")) or not _number(record.get("revenue_total")):
		return null
	if not _valid_day(record.get("today")) or not _valid_day(record.get("yesterday")):
		return null
	if not _valid_counts(record, "cars") or not _valid_counts(record, "passengers"):
		return null
	if not _price(record.get("vehicle_fare"), FareSchedule.MAX_VEHICLE_FARE):
		return null
	if not _price(record.get("passenger_fare"), FareSchedule.MAX_PASSENGER_FARE):
		return null
	if not record.get("route_fares") is Dictionary:
		return null
	var keys := _route_keys(routes)
	if keys.size() != routes.size():
		return null
	var ledger := CompanyLedger.new()
	ledger.set_vehicle_fare(record.vehicle_fare)
	ledger.set_passenger_fare(record.passenger_fare)
	for key in record.route_fares:
		var route_id = keys.find_key(key)
		var prices = record.route_fares[key]
		if route_id == null or not prices is Dictionary or prices.is_empty():
			return null
		for kind in prices:
			if kind == "vehicle" and _price(prices[kind], FareSchedule.MAX_VEHICLE_FARE):
				ledger.set_route_vehicle_fare(route_id, prices[kind])
			elif kind == "passenger" and _price(prices[kind], FareSchedule.MAX_PASSENGER_FARE):
				ledger.set_route_passenger_fare(route_id, prices[kind])
			else:
				return null
	ledger.cash = record.cash
	ledger.revenue_total = record.revenue_total
	ledger.today = record.today.duplicate()
	ledger.yesterday = record.yesterday.duplicate()
	ledger.cars_today = int(record.cars_today)
	ledger.cars_yesterday = int(record.cars_yesterday)
	ledger.cars_total = int(record.cars_total)
	ledger.passengers_today = int(record.passengers_today)
	ledger.passengers_yesterday = int(record.passengers_yesterday)
	ledger.passengers_total = int(record.passengers_total)
	return ledger


static func _route_keys(routes: Array[MapData.Route]) -> Dictionary:
	var keys := {}
	var seen := {}
	for route in routes:
		if route == null or route.id < 0 or route.key.is_empty() or keys.has(route.id) or seen.has(route.key):
			return {}
		keys[route.id] = route.key
		seen[route.key] = true
	return keys


static func _valid_day(day: Variant) -> bool:
	var categories := CompanyLedger.INCOME + CompanyLedger.EXPENSES
	if not day is Dictionary or day.size() != categories.size():
		return false
	for category in categories:
		if not _number(day.get(category)):
			return false
	return true


static func _valid_counts(record: Dictionary, prefix: String) -> bool:
	for period in ["today", "yesterday", "total"]:
		var count = record.get(prefix + "_" + period)
		if not _number(count) or count < 0 or floor(count) != count or count > MAX_JSON_INTEGER:
			return false
	return record[prefix + "_total"] >= record[prefix + "_today"] + record[prefix + "_yesterday"]


static func _number(value: Variant) -> bool:
	return (value is float or value is int) and is_finite(value)


static func _price(value: Variant, ceiling: float) -> bool:
	return _number(value) and value >= 0 and value <= ceiling
