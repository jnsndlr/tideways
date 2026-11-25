extends SceneTree
## Stage 4, two boats: maps/two_boats.json, the opening with a size 1 Heron
## on Gullrock–Madrona as well as the size 2 Hiyu. They
## share one terminal's one slip. Both are put on routes that start away from
## it, and the Heron is timed to come in there halfway through the Hiyu's call.
## The stop editor must warn about it on that sailing without disabling Apply,
## the warning must go once the Heron is moved clear, and in play the Heron
## must really hold offshore there for the Hiyu.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/slip_conflict_test.gd -- --scenario=two_boats

var main: Node
var frames := 0
var _heron_in := -1.0   # when (sim.minutes) the plan says the Heron comes in held
var shared: Terminal    # where both call


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _term(sim: Simulation, key: String) -> Terminal:
	for t: Terminal in sim.terminals.values():
		if t.town.key.begins_with(key + "/"):
			return t
	return null


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	if sim.ferries.size() != 2:
		return _fail("The two-boats scenario should run two boats, not %d" % sim.ferries.size())
	var hiyu := sim.ferries[0]
	var heron := sim.ferries[1]
	if frames == 5:
		return _set_up(sim, hiyu, heron)
	var heron_held: bool = heron.state == Ferry.State.SAILING and heron.destination() == shared \
		and heron.speed < 0.2 and heron._waiting_for == hiyu \
		and hiyu.state != Ferry.State.SAILING and hiyu.here() == shared
	if heron_held:
		print("%s: the Heron holds %.0f m off %s while the Hiyu is alongside (planned in %s)" % [
			sim.clock_text(), heron.path_left(), shared.town.name, sim.clock_text(_heron_in)])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 12000:
		return _fail("The Heron never held offshore for the Hiyu at %s" % shared.town.name)
	return false


func _set_up(sim: Simulation, hiyu: Ferry, heron: Ferry) -> bool:
	Engine.time_scale = 6.0
	if heron.fc.size != 1 or hiyu.fc.size != 2:
		return _fail("Expected the size 2 Hiyu and a size 1 Heron, got %d and %d" % [hiyu.fc.size, heron.fc.size])
	# Each starts her round at her other stop, so she calls at the shared one
	# only briefly in mid-round.
	var common := hiyu.stops.filter(func(id): return id in heron.stops)
	if common.size() != 1:
		return _fail("Expected the two boats to share one terminal, got %s" % [common])
	var madrona: int = common[0]
	shared = sim.terminals[madrona]
	var hiyu_ids: Array[int] = [hiyu.stops[1 - hiyu.stops.find(madrona)], madrona]
	var heron_ids: Array[int] = [heron.stops[1 - heron.stops.find(madrona)], madrona]
	var oh := hiyu.plan_offsets(hiyu_ids)
	var orr := heron.plan_offsets(heron_ids)
	var now := int(sim.minutes)
	# The Heron's first timed sailing leaves Gullrock once she can be back there.
	var heron_t := ceili((now + orr[-1] + 20.0) / 5.0) * 5
	var heron_in := heron_t + orr[1] - heron.planned_dwell()
	# The Hiyu is due in at Madrona half her call before that.
	var hiyu_t := roundi(heron_in - oh[1] + hiyu.planned_dwell() * 0.5)
	if hiyu_t < now + 30:
		return _fail("No room to set this up at %s" % sim.clock_text())
	print("Hiyu leaves %s %s (alongside %s %s–%s); Heron leaves %s %s (due in %s)" % [
		sim.map.towns[hiyu_ids[0]].name, Timetable.text(hiyu_t), shared.town.name,
		Timetable.text(hiyu_t + oh[1] - hiyu.planned_dwell()), Timetable.text(hiyu_t + oh[1]),
		sim.map.towns[heron_ids[0]].name, Timetable.text(heron_t), Timetable.text(heron_in)])
	var hiyu_times: Array[int] = [hiyu_t]
	if not sim.reschedule(hiyu, hiyu_ids, hiyu_times):
		return _fail("Couldn't time the Hiyu")
	# The editor, on the Heron with the clashing sailing drafted.
	var hud: Hud = main.hud
	hud.select_ferry(heron)
	var ed := hud._ferry_panel.open_schedule()
	ed._timed = true
	ed._times.assign([heron_t])
	ed._rebuild()
	var result := SlipConflicts.check(heron, heron_ids, ed._times, heron.pace)
	var clashes := SlipConflicts.on_sailing(result, 0)
	if clashes.size() != 1 or not clashes[0].she_holds or clashes[0].other != hiyu or clashes[0].island != madrona:
		return _fail("Expected one clash with the Heron holding for the Hiyu at %s, got %s" % [shared.town.name, result.clashes])
	print("Clash: %s" % SlipConflictText.clash_text(sim, clashes[0]))
	if not ed._clash_note.visible or "holds offshore for the Hiyu" not in ed._clash_note.text:
		return _fail("The editor shows no recurring hold warning: '%s'" % ed._clash_note.text)
	print("Editor: %s" % ed._clash_note.text)
	if not _sailing_warned(ed, 0):
		return _fail("The clashing sailing carries no warning")
	if ed._apply.disabled:
		return _fail("A slip clash disabled Apply")
	# A second working berth can take the later boat. A berth still being
	# built cannot absorb the conflict, nor can a tie-up berth.
	var spare := MapData.Slip.new(1, false)
	shared.town.slips.append(spare)
	ed._rebuild()
	if _sailing_warned(ed, 0):
		return _fail("Timed boats were warned despite a second free working berth")
	spare.building = true
	ed._rebuild()
	if not _sailing_warned(ed, 0):
		return _fail("The timetable relied on a working berth under construction")
	spare.building = false
	spare.tie_up = true
	ed._rebuild()
	if not _sailing_warned(ed, 0):
		return _fail("The timetable treated a lay-up berth as a working slip")
	shared.town.slips.pop_back()
	# Moved a round later the warning goes.
	ed._times.assign([heron_t + 120])
	ed._rebuild()
	if ed._clash_note.visible or _sailing_warned(ed, 0):
		return _fail("Still warned with the Heron clear of the Hiyu: '%s'" % ed._clash_note.text)
	# Back, and applied anyway.
	ed._times.assign([heron_t])
	ed._rebuild()
	ed._on_apply()
	if heron.timetable != [heron_t] and heron.itinerary.pending.times != [heron_t]:
		return _fail("Apply didn't put the Heron on her clashing sailing")
	if hud._slip_clash_text(heron) == "" or hud._slip_clash_text(hiyu) == "":
		return _fail("The ferry panel doesn't mention the clash for both boats")
	print("Panel (Heron): %s" % hud._slip_clash_text(heron))
	print("Panel (Hiyu): %s" % hud._slip_clash_text(hiyu))
	_heron_in = heron_in
	return false


## Whether sailing `k`'s row in the editor has a clash note under it.
func _sailing_warned(ed: ScheduleEditor, k: int) -> bool:
	var boxes := ed._sailings.get_children().filter(func(c): return not c.is_queued_for_deletion())
	if k >= boxes.size():
		return false
	for c in boxes[k].get_children():
		if c is Label and "holds ~" in (c as Label).text:
			return true
	return false
