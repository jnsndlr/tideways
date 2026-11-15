extends SceneTree
## Shows what each system costs per frame, headless, on a Sandbox seed: switches
## one group of nodes off and on in alternating blocks and compares frame time.
## Use it when tools/frame_budget_test.gd fails, or before and after a change
## that adds per-frame work. Nothing is drawn, so this is script and scene
## update cost only; rendering cost needs a device (tools/perf_probe.gd).
##
##   godot --headless --path . --fixed-fps 30 --script tools/frame_cost.gd -- --seed=123
##
## Takes about two minutes. Costs are comparable between runs on one machine;
## differences under about 0.5 ms are noise. Switching a group off also stops
## what depends on it (no ferries moving means no cars boarding), so read each
## line as "this group and what it drives".

const WARM := 600
const BLOCK := 120
const REPS := 6
const SETTLE := 10      # frames skipped after each switch

var main: Node
var frames := 0
var groups: Array = []
var gi := -1
var phase := 0          # block index within the group (even = on, odd = off)
var in_block := 0
var t_last := 0
var on_us := 0.0
var off_us := 0.0
var on_n := 0
var off_n := 0
var base_us: Array[float] = []
var switched_off: Array = []


func _initialize() -> void:
	main = load(Scenes.SANDBOX).instantiate()
	root.add_child(main)


## Sandbox's direct children running script `type`.
func _children_of(type: String) -> Array:
	var out := []
	for c in main.get_children():
		if c.get_script() and c.get_script().get_global_name() == type:
			out.append(c)
	return out


func _build_groups() -> void:
	var sim: Simulation = main.sim
	groups = [
		["HUD", func(): return [main.hud]],
		["Seagulls", func(): return _children_of("Seagulls")],
		["Eagles", func(): return _children_of("Eagles")],
		["Cetaceans and pinnipeds", func(): return _children_of("Cetaceans") + _children_of("Pinnipeds")],
		["Day cycle, wakes, night lights, clouds, backdrop", _sky_and_water],
		["Camera rig", func(): return [main.rig]],
		["Moving road vehicles", func(): return sim.moving_vehicles.duplicate()],
		["Ferries", func(): return sim.ferries.duplicate()],
		["Other vessels", func(): return sim.marine.vessels.filter(func(v): return not v is Ferry)],
		["Marine traffic arbiter", func(): return [sim.marine]],
		["Wildlife visits", func(): return [sim.wildlife]],
		["Terminals", func(): return sim.terminals.values()],
	]


func _sky_and_water() -> Array:
	var out := []
	for type in ["DayCycle", "WakeField", "NightLights", "CloudLayer", "Backdrop"]:
		out.append_array(_children_of(type))
	return out


func _switch(nodes: Array, on: bool) -> void:
	for n in nodes:
		if is_instance_valid(n):
			n.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED


func _process(_delta: float) -> bool:
	frames += 1
	var now := Time.get_ticks_usec()
	var dt := float(now - t_last)
	t_last = now
	if frames < WARM:
		if frames > WARM - 300:
			base_us.append(dt)
		return false
	var sim: Simulation = main.sim
	if frames == WARM:
		_build_groups()
		base_us.sort()
		var mean := 0.0
		for v in base_us:
			mean += v / base_us.size()
		print("All systems: mean %.2f ms, median %.2f ms, p95 %.2f ms per frame (%d vessels, %d moving vehicles)" % [
			mean / 1000.0, base_us[base_us.size() / 2] / 1000.0, base_us[int(base_us.size() * 0.95)] / 1000.0,
			sim.marine.vessels.size(), sim.moving_vehicles.size()])
		gi = 0
		return false
	if in_block >= SETTLE:
		if phase % 2 == 0:
			on_us += dt
			on_n += 1
		else:
			off_us += dt
			off_n += 1
	in_block += 1
	if in_block < BLOCK:
		return false
	in_block = 0
	phase += 1
	if phase % 2 == 1:
		switched_off = groups[gi][1].call()
		_switch(switched_off, false)
	else:
		_switch(switched_off, true)
	if phase == REPS * 2:
		print("%-50s %5.2f ms  (%d nodes)" % [groups[gi][0], (on_us / on_n - off_us / off_n) / 1000.0, switched_off.size()])
		on_us = 0.0
		off_us = 0.0
		on_n = 0
		off_n = 0
		phase = 0
		gi += 1
		if gi >= groups.size():
			quit(0)
			return true
	return false
