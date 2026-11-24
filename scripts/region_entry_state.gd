class_name RegionEntryState
extends RefCounted
## Inputs kept between scene instances. Worker and live-world state belongs to WorldSession.

static var sandbox_seed := 0
static var layout: MapLayout
static var unsaved := false
static var scenario_path := ""
static var editor_restore := {}


static func select_authored(path: String) -> void:
	scenario_path = path
	editor_restore.clear()
