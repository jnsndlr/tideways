extends SceneTree
## Buying a second working slip at Madrona (stage 5), where Hiyu and Rhododendron
## share one small slip (maps/shared_slip.json), and a tie-up at Port Rosario. Passes
## once the new slip is built in place beside the first, one route has moved to it
## without the map being rebuilt, a boat has docked there, and the tie-up is built.
##
##   godot --headless --path . --fixed-fps 30 --script tools/slip_purchase_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var madrona: Terminal
var rosario: Terminal
var new_slip := -1
var new_tie := -1
var built := {}
var moved := -1
var used_by := ""
var world_children := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(why: String) -> bool:
	push_error("Slip purchase: " + why)
	quit(1)
	return true


func _offer(kind: TerminalUpgrade.Kind) -> TerminalUpgrade:
	return madrona.find_upgrade(kind)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	if frames == 5:
		for t: Terminal in sim.terminals.values():
			print("%s upgrades:" % t.town.name)
			for u in t.upgrades():
				print("  %s · $%d · %s%s" % [u.title, u.price, u.detail(), "" if is_nan(u.v) else " · at v %.0f" % u.v])
			if t.town.key.begins_with("island-2/"):
				madrona = t
			if t.town.key.begins_with("island-1/"):
				rosario = t
		if madrona == null or rosario == null:
			return _fail("no Madrona or Port Rosario terminal")
		madrona.slip_built.connect(func(i): built[i] = true)
		rosario.slip_built.connect(func(i): built["rosario %d" % i] = true)
		var slip := _offer(TerminalUpgrade.Kind.SLIP)
		if slip == null or slip.blocked != "":
			return _fail("Madrona can't take a second slip: %s" % (slip.blocked if slip else "not offered"))
		var cash := sim.available_cash
		if not madrona.buy(slip):
			return _fail("could not buy the slip")
		if not is_equal_approx(cash - sim.available_cash, slip.price):
			return _fail("paid %.0f, not %d" % [cash - sim.available_cash, slip.price])
		new_slip = madrona.town.slips.size() - 1
		var tie := _offer(TerminalUpgrade.Kind.TIE_UP)
		if tie == null or tie.blocked == "" or madrona.buy(tie):
			return _fail("a tie-up could be bought while the slip is being built")
		if madrona.town.working_slips() != 1:
			return _fail("the slip was in use before it was built")
		world_children = main.builder.root.get_child_count()
		var tie_rosario := rosario.find_upgrade(TerminalUpgrade.Kind.TIE_UP)
		if tie_rosario == null or not rosario.buy(tie_rosario):
			return _fail("could not buy a tie-up at Port Rosario: %s" % (tie_rosario.blocked if tie_rosario else "not offered"))
		new_tie = rosario.town.slips.size() - 1
		print("Bought a tie-up at Port Rosario at v %.0f" % rosario.town.slip_offset(new_tie))
		print("Bought %s at v %.0f (first slip at %.0f)" % [slip.title, madrona.town.slip_offset(new_slip), madrona.town.slip_offset(0)])
		Engine.time_scale = 8.0
		return false
	if new_slip >= 0 and built.has(new_slip) and madrona.refit_stage == Terminal.RefitStage.NONE and world_children > 0:
		if madrona.town.working_slips() != 2:
			return _fail("Madrona has %d working slips after the build" % madrona.town.working_slips())
		var guide := madrona.slip_guides[new_slip]
		if Models.mid_slip_guides:
			if guide == null or guide.get_children().filter(func(node: Node): return node is SlipGuidesView).size() != 1:
				return _fail("the new working slip should have one fitted guide view")
		elif guide != null:
			return _fail("classic working slips should have no guide contacts")
		var ramp := madrona.slip_ramps[new_slip]
		if Models.mid_slip:
			if ramp == null or ramp.get_children().filter(func(node: Node): return node is SlipRampView).size() != 1:
				return _fail("the newly built working slip should have one fitted ramp view")
		elif ramp != null:
			return _fail("the classic slip should open without a transfer span")
		if main.builder.root.get_child_count() <= world_children:
			return _fail("the new slip wasn't built into the world")
		world_children = 0
		print("Slip built on day %d at %s" % [sim.day, sim.clock_text()])
	if new_slip >= 0 and moved < 0 and not madrona.town.slips[new_slip].routes.is_empty():
		moved = madrona.town.slips[new_slip].routes[0]
		if madrona.town.slips[0].routes.has(moved):
			return _fail("route %d is on both slips" % moved)
		var r := sim.map.routes[moved]
		var end := r.curve.sample_baked(0.0 if r.a == madrona.town.id else r.length)
		if end.distance_to(madrona.town.dock_center(moved)) > 1.0:
			return _fail("route %d still ends %.0f m from its new slip" % [moved, end.distance_to(madrona.town.dock_center(moved))])
		print("Route %d moved to the new slip at %s" % [moved, sim.clock_text()])
	if moved >= 0 and used_by == "":
		for f in sim.ferries:
			if f.route.id == moved and f.state != Ferry.State.SAILING and f.here() == madrona and f.berth == Ferry.Berth.WORKING:
				var off := Vector2(f.global_position.x, f.global_position.z).distance_to(
					Vector2(madrona.town.berth_center(new_slip).x, madrona.town.berth_center(new_slip).z))
				if off > 30.0:
					return _fail("%s lies %.0f m off the new slip" % [f.ferry_name, off])
				used_by = f.ferry_name
				print("%s alongside at the new slip (%.0f m off its berth)" % [f.ferry_name, off])
	if used_by != "" and built.has("rosario %d" % new_tie):
		if rosario.slip_ramps[new_tie] != null:
			return _fail("the tie-up berth should open without a transfer span")
		if rosario.town.tie_ups() != [new_tie]:
			return _fail("Port Rosario's tie-ups are %s" % [rosario.town.tie_ups()])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 24000:
		return _fail("timed out at %s (slip built %s, route moved %d, used by '%s', tie-up built %s)" % [sim.clock_text(), built.has(new_slip), moved, used_by, built.has("rosario %d" % new_tie)])
	return false
