extends SceneTree
## Stage 6, the fleet, on the opening: buys a size 1 boat for delivery to
## Gullrock (its slip is the only one no schedule calls at, and the opening has no
## tie-up slips), watches the tug bring her in, gives her Gullrock – Madrona, waits
## for her to sail, lays her up and sells her for 80% of her price.
##
##   godot --headless --path . --fixed-fps 30 --script tools/fleet_purchase_test.gd

var main: Node
var frames := 0
var phase := 0
var boat: Ferry
var gullrock: Terminal
var madrona: Terminal
var _cash := 0.0
var _sailed := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _log(sim: Simulation, msg: String) -> void:
	print("Day %d %s: %s" % [sim.day, sim.clock_text(), msg])


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.get("sim") == null or not main.built:
		return false
	var sim: Simulation = main.sim
	match phase:
		0:
			Engine.time_scale = 8.0
			for term: Terminal in sim.terminals.values():
				if term.town.key.begins_with("island-7"):
					gullrock = term
				elif term.town.key.begins_with("island-2"):
					madrona = term
			if gullrock == null or madrona == null:
				return _fail("No Gullrock or Madrona terminal in the opening")
			var big := sim.purchase_problem(3, gullrock)
			if big == "":
				return _fail("A size 3 boat could be delivered to Gullrock's small slip")
			_log(sim, "Size 3 at Gullrock: %s" % big)
			for term: Terminal in sim.terminals.values():
				if term != gullrock and sim.purchase_problem(1, term) == "":
					return _fail("%s has no free slip, but a boat could be delivered there" % term.town.name)
			_cash = sim.available_cash
			var lanes_before := sim._lane_destinations(gullrock)
			boat = sim.buy_ferry(1, gullrock)
			if boat == null:
				return _fail("Couldn't buy a size 1 boat for Gullrock: %s" % sim.purchase_problem(1, gullrock))
			var price := FerryClass.of(1).price()
			if not is_equal_approx(sim.available_cash, _cash - price) or not is_equal_approx(sim.ledger.today["purchases"], price):
				return _fail("Buying her didn't charge %d to purchases" % price)
			if boat.berth != Ferry.Berth.DELIVERING or boat.tow == null or boat.in_service():
				return _fail("She isn't under tow: %s" % boat.status_text())
			if boat.route.in_service:
				return _fail("Her delivery route is in service before she has stops")
			if lanes_before != (sim._lane_destinations(gullrock)):
				return _fail("Gullrock's lanes changed for a boat with no stops")
			_log(sim, "Bought %s (%s) for $%d, %.0f min out: %s" % [boat.ferry_name, boat.fc.label, price, boat.tow.minutes_left(), boat.status_text()])
			phase = 1
		1:
			if boat.berth == Ferry.Berth.DELIVERING:
				if boat.crew_today > 0.0:
					return _fail("Paid crew under tow")
				return _timeout(sim)
			if boat.berth != Ferry.Berth.TIED_UP:
				return _fail("Delivered into the wrong state: %s" % boat.status_text())
			var isl := gullrock.town
			var off := boat.global_position.distance_to(isl.berth_center(boat.tie_up))
			_log(sim, "%s delivered, %.1f m off the slip's centre: %s" % [boat.ferry_name, off, boat.status_text()])
			if boat.here() != gullrock or off > boat.fc.half_length:
				return _fail("Not lying in Gullrock's slip")
			# Another boat can't be given Gullrock while she lies in its only slip.
			var hiyu := sim.ferries[0]
			var ids: Array[int] = [hiyu.next_dock().town.id, gullrock.town.id]
			if sim.stops_problem(hiyu, ids) == "":
				return _fail("Hiyu could be scheduled into the slip she lies in")
			var stops: Array[int] = [gullrock.town.id, madrona.town.id]
			var why := sim.stops_problem(boat, stops)
			if why != "" or not sim.reschedule(boat, stops):
				return _fail("Couldn't give her Gullrock – Madrona: " + why)
			if not boat.assigned or not boat.return_requested:
				return _fail("Her first stops didn't send her back into service")
			if madrona.town.id not in sim._lane_destinations(gullrock):
				return _fail("Gullrock's lanes don't serve Madrona")
			_log(sim, "Given Gullrock – Madrona: %s" % boat.status_text())
			phase = 2
		2:
			if boat.berth == Ferry.Berth.WORKING and boat.state == Ferry.State.SAILING:
				_sailed += 1
				_log(sim, "%s sailing: %s" % [boat.ferry_name, boat.status_text()])
				if not boat.route.in_service:
					return _fail("Her route isn't in service while she sails it")
				boat.request_lay_up()
				phase = 3
			return _timeout(sim)
		3:
			if boat.berth == Ferry.Berth.TIED_UP:
				_log(sim, "Laid up at %s: %s" % [boat.here().town.name, boat.status_text()])
				boat.post_costs(false)   # (her running costs to date, which the sale posts first)
				_cash = sim.available_cash
				var value := boat.resale_value()
				if value != roundi(FerryClass.of(1).price() * 0.8):
					return _fail("Resale value %d isn't 80%% of her price" % value)
				var n := sim.ferries.size()
				if not sim.sell_ferry(boat):
					return _fail("Couldn't sell her laid up")
				if sim.ferries.size() != n - 1 or boat in sim.ferries:
					return _fail("Still in the fleet after the sale")
				if sim.available_cash < _cash + value - 0.01 or sim.ledger.today["sales"] < value:
					return _fail("The sale didn't credit $%d to sales" % value)
				_log(sim, "Sold for $%d" % value)
				phase = 4
				_cash = frames
			elif boat.berth == Ferry.Berth.WORKING and boat.in_service() == false and boat.can_sell():
				return _fail("Sellable while working")
			return _timeout(sim)
		4:
			# A while on, with her gone, to catch anything still holding on to her.
			if frames > _cash + 300:
				if sim.ferries[0].state == Ferry.State.SAILING or sim.ferries[0].trips > 0:
					print("TEST PASSED")
					quit(0)
					return true
	return false


func _timeout(sim: Simulation) -> bool:
	if frames > 60000:
		return _fail("Gave up in phase %d: %s" % [phase, boat.status_text() if is_instance_valid(boat) else "sold"])
	return false
