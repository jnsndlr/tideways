class_name RegionEntryState
extends RefCounted
## Inputs kept between scene instances. Worker and live-world state belongs to WorldSession.

static var sandbox_seed := 0
static var layout: MapLayout
static var unsaved := false
static var scenario_path := ""
static var editor_restore := {}
static var unlimited_cash := false
static var company_name := ""
static var pending_save: Dictionary = {}
static var load_error := ""
