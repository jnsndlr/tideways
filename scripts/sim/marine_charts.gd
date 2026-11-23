class_name MarineCharts
extends RefCounted
## One build of the navigable water, fishing grounds and coves for a region.
## The worker reads region data only. Its results are consumed after it joins.

enum Phase { PENDING, NAVIGATION, FISHING, ANCHORAGES, COMPLETE, CANCELLED }

var map: MapData
var terrain: Terrain
var nav: NavGrid
var grounds: Array[FishingGround] = []
var anchorages: Array[Anchorage] = []
var _mutex := Mutex.new()
var _phase := Phase.PENDING


func _init(region: MapData, heights: Terrain) -> void:
	map = region
	terrain = heights


func phase() -> Phase:
	_mutex.lock()
	var current := _phase
	_mutex.unlock()
	return current


func cancelled() -> bool:
	return phase() == Phase.CANCELLED


func cancel() -> void:
	_mutex.lock()
	_phase = Phase.CANCELLED
	_mutex.unlock()


func _advance_to(next: Phase) -> bool:
	_mutex.lock()
	var active := _phase != Phase.CANCELLED
	if active:
		_phase = next
	_mutex.unlock()
	return active


func build() -> void:
	if not _advance_to(Phase.NAVIGATION):
		return
	nav = NavGrid.new(map, terrain, cancelled)
	if not _advance_to(Phase.FISHING):
		return
	grounds = FishingGround.find_all(self)
	if not _advance_to(Phase.ANCHORAGES):
		return
	var start := Time.get_ticks_msec()
	anchorages = Anchorage.find_all(self)
	if _advance_to(Phase.COMPLETE):
		var spots := 0
		for cove in anchorages:
			spots += cove.spots.size()
		print("Anchorages: %d coves, %d spots (%d ms)" % [anchorages.size(), spots, Time.get_ticks_msec() - start])
