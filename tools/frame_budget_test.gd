extends SceneTree
## Fails when the game's own per-frame work on seed 123 grows past a budget.
##
## Headless, so nothing is drawn: this watches scripts and scene updates only,
## which is the part a code change can slow down without anyone seeing it on a
## fast desk machine. Rendering cost is measured on a device (tools/perf_probe.gd).
##
## Machines differ, so the frame time is divided by how long this machine takes
## to run a fixed piece of script (the yardstick). The budget is that ratio with
## headroom over the measured baseline; raise it on purpose, in the PR that adds
## the work, rather than to quieten a failure. tools/frame_cost.gd shows which
## system the time went to.
##
##   godot --headless --path . --fixed-fps 30 --script tools/frame_budget_test.gd -- --seed=123

# Median frame time over the yardstick. On main at b0e4c9e the ratio is about
# 1.65 on the hosted CI runner and about 1.9 on a cloud Xeon (the yardstick
# evens machines out to within about 15%). The budget leaves the hosted runner
# about 40% of headroom.
const BUDGET := 2.3
const WARM_FRAMES := 300
const MEASURED_FRAMES := 900
const YARDSTICK_EVERY := 90

var main: Node
var frame := 0
var t_last := 0
var frames_us: Array[float] = []
var yardstick_us := INF


func _initialize() -> void:
	main = load(Scenes.SANDBOX).instantiate()
	root.add_child(main)


## A fixed amount of plain script work: vector maths, a dictionary and a call.
func _yardstick() -> float:
	var t0 := Time.get_ticks_usec()
	var acc := Vector2.ZERO
	var seen := {}
	for i in 20000:
		acc += Vector2(sin(i * 0.1), cos(i * 0.1)).rotated(0.3) * 0.5
		seen[i & 255] = acc.length()
	return float(Time.get_ticks_usec() - t0)


func _process(_delta: float) -> bool:
	frame += 1
	if frame <= WARM_FRAMES:
		t_last = Time.get_ticks_usec()
		return false
	var measured := frame - WARM_FRAMES
	if measured % YARDSTICK_EVERY == 0:
		# Timed between frames, and kept out of the next frame's reading.
		yardstick_us = minf(yardstick_us, _yardstick())
		t_last = Time.get_ticks_usec()
		return false
	var now := Time.get_ticks_usec()
	frames_us.append(float(now - t_last))
	t_last = now
	if measured < MEASURED_FRAMES:
		return false
	frames_us.sort()
	var median := frames_us[frames_us.size() / 2]
	var p95 := frames_us[int(frames_us.size() * 0.95)]
	var ratio := median / yardstick_us
	print("Game code per frame: median %.2f ms, p95 %.2f ms; yardstick %.2f ms; ratio %.2f (budget %.2f)" % [
		median / 1000.0, p95 / 1000.0, yardstick_us / 1000.0, ratio, BUDGET])
	if ratio > BUDGET:
		push_error("Game code per frame is %.2f times the yardstick, over the budget of %.2f. Run tools/frame_cost.gd to see which system grew." % [ratio, BUDGET])
		quit(1)
		return true
	print("TEST PASSED")
	quit(0)
	return true
