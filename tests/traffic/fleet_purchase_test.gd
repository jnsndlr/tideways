extends SceneTree
## Stage 6, the fleet, on the opening. Buys a size 1 boat: the tug brings her to
## Port Rosario's tie-up. Buys a second (with cash topped up) while that tie-up is
## spoken for: she goes to Gullrock's slip, the one no schedule calls at. Gives
## the first Port Rosario – Madrona, waits for her to sail, lays her up (back in
## the tie-up), sells her for 80% of her price and watches a tug tow her away.
##
##   godot --headless --path . --fixed-fps 30 --script tests/traffic/fleet_purchase_test.gd

var main: Node
var frames := 0
var phase := 0
var boat: Ferry
var second: Ferry
var rosario: Terminal
var gullrock: Terminal
var madrona: Terminal
var _cash := 0.0
var _mark := 0
var _return_position := Vector3.ZERO
var _bought_at := 0.0


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
	if frames > 80000:
		return _fail("Gave up in phase %d" % phase)
	match phase:
		0:
			Engine.time_scale = 8.0
			for term: Terminal in sim.terminals.values():
				if term.town.key.begins_with("island-1"):
					rosario = term
				elif term.town.key.begins_with("island-7"):
					gullrock = term
				elif term.town.key.begins_with("island-2"):
					madrona = term
			if sim.purchase_problem(3) == "":
				return _fail("A size 3 boat ($100,000) could be bought with $50,000")
			_cash = sim.available_cash
			for invalid_size in [0, FerryClass.MAX_SIZE + 1]:
				if sim.buy_ferry(invalid_size) != null or sim.available_cash != _cash:
					return _fail("Invalid ferry size changed the fleet or cash")
			_bought_at = sim.abs_minutes()
			var lanes_before := sim._lane_destinations(rosario)
			boat = sim.buy_ferry(1)
			if boat == null:
				return _fail("Couldn't buy a size 1 boat: %s" % sim.purchase_problem(1))
			var price := FerryClass.of(1).price()
			if not is_equal_approx(sim.available_cash, _cash - price) or not is_equal_approx(sim.ledger.today["purchases"], price):
				return _fail("Buying her didn't charge %d to purchases" % price)
			if boat.here() != rosario or not rosario.town.slips[boat.tie_up].tie_up:
				return _fail("Not bound for Port Rosario's tie-up but %s slip %d" % [boat.here().town.name, boat.tie_up])
			if boat.berth != Ferry.Berth.DELIVERING or boat.tow == null or boat.in_service():
				return _fail("She isn't under tow: %s" % boat.status_text())
			if lanes_before != sim._lane_destinations(rosario):
				return _fail("Port Rosario's lanes changed for a boat with no stops")
			_log(sim, "Bought %s for $%d, %.0f min out: %s" % [boat.ferry_name, price, boat.tow.minutes_left(), boat.status_text()])
			sim.ledger.cash += price
			# A newly built spare berth may have no route assigned to it.
			var spare := rosario.town.slips.size()
			rosario.town.slips.append(MapData.Slip.new(1))
			var offer := sim.delivery_slip(1)
			rosario.town.slips[-1].building = true
			if sim.delivery_slip(1) == [rosario, spare]:
				return _fail("Offered a berth still under construction")
			rosario.town.slips.pop_back()
			if offer != [rosario, spare]:
				return _fail("Delivery skipped the available working slip without an assigned route")
			second = sim.buy_ferry(1)
			if second == null or second.here() != gullrock or gullrock.town.slips[second.tie_up].tie_up:
				return _fail("The second boat isn't bound for Gullrock's idle slip")
			_log(sim, "Bought %s: %s" % [second.ferry_name, second.status_text()])
			phase = 1
		1:
			for f: Ferry in [boat, second]:
				if f.berth == Ferry.Berth.TIED_UP and not f.has_meta("in_at"):
					f.set_meta("in_at", sim.abs_minutes())
					_log(sim, "%s in, %.0f min after she was bought" % [f.ferry_name, sim.abs_minutes() - _bought_at])
					if sim.abs_minutes() - _bought_at > 180.0 or sim.abs_minutes() - _bought_at < 120.0:
						return _fail("Delivery took %.0f min, not 2–3 hours" % (sim.abs_minutes() - _bought_at))
			if boat.berth == Ferry.Berth.DELIVERING or second.berth == Ferry.Berth.DELIVERING:
				if boat.crew_today > 0.0:
					return _fail("Paid crew under tow")
				return false
			for f: Ferry in [boat, second]:
				var off := f.global_position.distance_to(f.here().town.berth_center(f.tie_up))
				_log(sim, "%s delivered, %.1f m off the slip's centre: %s" % [f.ferry_name, off, f.status_text()])
				if f.berth != Ferry.Berth.TIED_UP or off > f.fc.half_length:
					return _fail("%s isn't lying where she was brought" % f.ferry_name)
			if sim.occupant(gullrock, second.tie_up, null) != second:
				return _fail("Gullrock's slip isn't held by the boat lying in it")
			# The arrival planner also sees the laid-up boat. A free second
			# working berth must allow a caller through.
			var alternate := gullrock.town.slips.size()
			gullrock.town.slips.append(MapData.Slip.new(1))
			var selected := gullrock.arrival_slip(second.tie_up, boat.fc.size,
				func(i: int): return gullrock.slip_user(i, boat) != null)
			gullrock.town.slips.pop_back()
			if selected != alternate:
				return _fail("Arriving ferry would use the berth occupied by a delivered boat")
			var stops: Array[int] = [rosario.town.id, madrona.town.id]
			var why := sim.stops_problem(boat, stops)
			if why != "" or not sim.reschedule(boat, stops):
				return _fail("Couldn't give her Port Rosario – Madrona: " + why)
			if not boat.assigned or not boat.return_requested:
				return _fail("Her first stops didn't send her back into service")
			_log(sim, "Given Port Rosario – Madrona: %s" % boat.status_text())
			phase = 2
		2:
			if boat.berth == Ferry.Berth.WORKING and boat.state == Ferry.State.SAILING:
				_log(sim, "%s sailing: %s" % [boat.ferry_name, boat.status_text()])
				if not boat.route.in_service:
					return _fail("Her route isn't in service while she sails it")
				boat.request_lay_up()
				phase = 3
		3:
			if boat.can_sell() != (boat.berth == Ferry.Berth.TIED_UP and not boat.return_requested):
				return _fail("Sellable while not laid up: %s" % boat.status_text())
			if boat.berth == Ferry.Berth.TIED_UP:
				_log(sim, "Laid up at %s: %s" % [boat.here().town.name, boat.status_text()])
				if not boat.here().town.slips[boat.tie_up].tie_up:
					return _fail("Laid up in a working slip with Port Rosario's tie-up free")
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
				if sim.sell_ferry(boat):
					return _fail("A second sale was accepted for a ferry already under tow")
				if not is_equal_approx(sim.available_cash, _cash + value) or sim.ledger.today["sales"] != value:
					return _fail("The sale didn't credit $%d to sales" % value)
				if not sim.fleet_market.berth_reserved(boat.here(), boat.tie_up):
					return _fail("The berth of the departing sold ferry was offered again too soon")
				if sim.tows.is_empty():
					return _fail("No tug came for her")
				_log(sim, "Sold for $%d: %s" % [value, boat.status_text()])
				phase = 4
		4:
			# Towed away and gone, with nothing holding on to her.
			if not is_instance_valid(boat) and sim.tows.is_empty():
				_log(sim, "Towed away; the tug has gone")
				_mark = frames
				phase = 5
		5:
			if frames > _mark + 300:
				# The second delivery is laid up in the same working slip she
				# will use. Returning her to service needs no trip offshore.
				var other_id := second.route.b if second.route.a == gullrock.town.id else second.route.a
				var stops: Array[int] = [gullrock.town.id, other_id]
				_return_position = second.global_position
				if not sim.reschedule(second, stops):
					return _fail("Couldn't start service from the occupied working slip")
				_mark = frames
				phase = 6
		6:
			if second.global_position.distance_to(_return_position) > second.fc.half_length:
				return _fail("The ferry left her berth to return to the same working slip")
			if second.berth == Ferry.Berth.WORKING:
				print("TEST PASSED")
				quit(0)
				return true
			if frames > _mark + 60:
				return _fail("A same-slip return waited for a needless manoeuvre")
	return false
