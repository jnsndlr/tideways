extends SceneTree
## Run headless with --script tools/helm_neighborhood_bench.gd.
## Times moving every hull and finding nearby hulls. All timings exclude setup.
## A stride of 80 approximates the opening's helm query rate; 8 stresses busy water.
const TICKS := 24


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	for size: int in [128, 512, 2048]:
		for spacing: float in [330.0, 4.0]:
			for stride: int in [80, 8]:
				var expected := measure(size, spacing, stride, false)
				if measure(size, spacing, stride, true) != expected:
					push_error("Neighbor totals differ from the full scan")
					quit(1)
					return
	quit()


func measure(count: int, spacing: float, stride: int, indexed: bool) -> int:
	var sea := Node3D.new()
	root.add_child(sea)
	var fleet: Array[Vessel] = []
	var grid := VesselNeighborhood.new(sea)
	for i in count:
		var boat := Vessel.new()
		sea.add_child(boat)
		boat.position = Vector3((i % 32) * spacing, 0.0, floori(i / 32.0) * spacing)
		fleet.append(boat)
		if indexed:
			grid.add(boat)

	var elapsed: Array[int] = []
	var hits := 0
	for tick in TICKS:
		var start := Time.get_ticks_usec()
		for boat in fleet:
			boat.position.x += 3.0
		for i in range(tick % stride, count, stride):
			var center := fleet[i].pos2()
			var nearby := grid.candidates(fleet, center, Helm.SCAN) if indexed else fleet
			for other in nearby:
				var p := other.global_position
				var reach := Helm.SCAN + other.half_seg + other.hull_radius
				if absf(p.x - center.x) <= reach and absf(p.z - center.y) <= reach:
					hits += 1
		elapsed.append(Time.get_ticks_usec() - start)
	elapsed.sort()
	print(
		(
			"fleet=%d spacing=%.0f stride=%d indexed=%s median_ms=%.3f hits=%d"
			% [count, spacing, stride, indexed, elapsed[TICKS >> 1] / 1000.0, hits]
		)
	)
	sea.free()
	return hits
