extends SceneTree
## Check the gameplay waterlines against the imported hulls whenever the models change.

const Measurement = preload("res://tests/support/ferry_waterline_measurement.gd")


func _initialize() -> void:
	var hulls := [
		[FerryHullAssets.SMALL_GLB, FerryClass.SMALL_CAR_DECK],
		[FerryHullAssets.HIYU_GLB, FerryClass.HIYU_CAR_DECK],
		[FerryHullAssets.MID_GLB, FerryClass.MID_CAR_DECK],
		[FerryHullAssets.ISQ_GLB, FerryClass.ISQ_CAR_DECK],
		[FerryHullAssets.JUMBO_GLB, FerryClass.ISQ_CAR_DECK],
	]
	for index in hulls.size():
		var path: String = hulls[index][0]
		if not ResourceLoader.exists(path):
			push_error("Missing ferry hull %s for waterline verification" % path)
			quit(1)
			return
		var ferry := FerryClass.of(index + 1)
		var measured := Measurement.measure(path, "fixed", HullWaterline.STATIONS, hulls[index][1])
		var half_length := measured[0] * FerryClass.MID_SCALE
		var expected := PackedFloat32Array([ferry.half_length - half_length, 2.0 * half_length])
		for width in measured.slice(1):
			expected.append(width * FerryClass.MID_SCALE)
		var actual := ferry.waterline()
		if actual.size() != expected.size():
			push_error("%s waterline has %d values, expected %d" % [path, actual.size(), expected.size()])
			quit(1)
			return
		for i in actual.size():
			if absf(actual[i] - expected[i]) > 0.0001:
				push_error("%s waterline value %d is %f, imported mesh measures %f" % [path, i, actual[i], expected[i]])
				quit(1)
				return
	print("TEST PASSED")
	quit()
