class_name MapLayout
extends RefCounted
## An authored map: where each island sits and how it is shaped, saved as JSON.
## MapGenerator builds everything else (mainland, islets, routes, towns) from it.
## The editor on the main map rolls and dials these, then saves or copies them.

const VERSION := 1
const MAIN_STORY := "res://maps/main_story.json"


class IslandSpec:
	var name := ""
	var x := 0.0
	var z := 0.0
	var radius := 560.0
	var height := 1.0       # times the usual height for its size
	var hills := 1.0        # height variance inland
	var peak := 0.0         # a mountain rising from the middle
	var lakes := 1.0        # how far the valleys may dip under the sea (0: never)
	var shape_seed := 1
	var stretch := 1.0
	var angle := 0.0        # degrees
	var roughness := 1.0
	var forest := 1.0
	var fields := 0.4
	var pinned := false
	var mainland := false   # sits on the mainland's coast, its land joined to it
	# Ferry docks placed and locked by hand: the only places a terminal can go on
	# an authored map (an island with none never gets one). Saved relative to the
	# island, so moving or turning it carries them along. A generated map's
	# islands have none, and the generator picks a spot facing the neighbours.
	var ferry := true  # with no scenario (--full-network): build its first dock
	var community_type := "residential"  # "rural", "residential", or "industrial"
	var docks: Array[DockSpec] = []

	const COMMUNITY_TYPES := ["rural", "residential", "industrial"]
	const KEYS := [
		"name",
		"x",
		"z",
		"radius",
		"height",
		"hills",
		"peak",
		"lakes",
		"shape_seed",
		"stretch",
		"angle",
		"roughness",
		"forest",
		"fields",
		"pinned",
		"mainland",
		"ferry",
		"community_type"
	]

	## Where dock `d` meets the shore in the world, and the heading out to sea.
	func dock_at(d: DockSpec) -> Vector2:
		return Vector2(x, z) + Vector2(d.u, d.v).rotated(deg_to_rad(angle))

	func dock_heading(d: DockSpec) -> Vector2:
		return Vector2.from_angle(deg_to_rad(d.facing + angle))

	## A dock at world point `at` heading out along world angle `deg` degrees.
	func dock_from_world(at: Vector2, deg: float, tier := "standard") -> DockSpec:
		var d := DockSpec.new()
		var local := (at - Vector2(x, z)).rotated(-deg_to_rad(angle))
		d.u = local.x
		d.v = local.y
		d.facing = fposmod(deg - angle, 360.0)
		d.tier = tier
		return d

	func to_dict() -> Dictionary:
		var d := {}
		for k in KEYS:
			var v = get(k)
			d[k] = snappedf(v, 0.001) if v is float else v
		if not docks.is_empty():
			d["docks"] = docks.map(func(dk: DockSpec): return dk.to_dict())
		return d

	static func from_dict(d: Dictionary) -> IslandSpec:
		var s := IslandSpec.new()
		for k in KEYS:
			if d.has(k):
				if not MapLayout._matches(d[k], s.get(k)):
					return null
				s.set(k, d[k])
		if not (s.community_type in COMMUNITY_TYPES):
			s.community_type = "residential"
		if not d.get("docks", []) is Array:
			return null
		for e in d.get("docks", []):
			if not e is Dictionary:
				return null
			var site := DockSpec.from_dict(e)
			if site == null:
				return null
			s.docks.append(site)
		for key in ["dock_x", "dock_z", "dock_angle"]:
			if not MapLayout._matches(d.get(key, 0.0), 0.0):
				return null
		if not d.get("dock", false) is bool:
			return null
		# The old single hand-placed dock, in world coordinates.
		if bool(d.get("dock", false)) and s.docks.is_empty():
			s.docks.append(s.dock_from_world(Vector2(float(d.get("dock_x", 0.0)), float(d.get("dock_z", 0.0))), float(d.get("dock_angle", 0.0))))
		return s

	func duplicate() -> IslandSpec:
		return from_dict(to_dict())


## A ferry dock site: where the pier meets the shore and the way it points out to
## sea, in its island's own frame (u along the island's angle, v across it), and
## its build tier (DOCK_TIERS: what it costs to build in play).
class DockSpec:
	var u := 0.0
	var v := 0.0
	var facing := 0.0      # degrees, relative to the island's angle
	var tier := "standard"
	## The town this dock serves; its terminal takes the town's name (TID-319).
	var town := ""
	var community_type := ""

	func to_dict() -> Dictionary:
		var d := {"u": snappedf(u, 0.001), "v": snappedf(v, 0.001), "facing": snappedf(facing, 0.0001), "tier": tier}
		if not town.is_empty():
			d["town"] = town
		if not community_type.is_empty():
			d["community_type"] = community_type
		return d

	static func from_dict(d: Dictionary) -> DockSpec:
		var s := DockSpec.new()
		for key in ["u", "v", "facing", "tier", "town", "community_type"]:
			if d.has(key):
				if not MapLayout._matches(d[key], s.get(key)):
					return null
				s.set(key, d[key])
		if not s.community_type.is_empty() and not (s.community_type in IslandSpec.COMMUNITY_TYPES):
			s.community_type = ""
		if not DOCK_TIERS.has(s.tier):
			s.tier = "standard"
		return s


## What a dock site costs to build in play, by tier. Rebalance them all here.
const DOCK_TIERS := {
	"small": {"name": "Small site", "price": 12000},
	"standard": {"name": "Standard site", "price": 20000},
	"hard": {"name": "Hard site", "price": 32000},
}
const DOCK_TIER_ORDER := ["small", "standard", "hard"]


static func dock_price(tier: String) -> int:
	return int(DOCK_TIERS.get(tier, DOCK_TIERS["standard"])["price"])


## Seeds the mainland, islets, towns and everything else not in `islands`.
var world_seed := 1
var islands: Array[IslandSpec] = []


func to_dict() -> Dictionary:
	var list := []
	for s in islands:
		list.append(s.to_dict())
	return {"version": VERSION, "world_seed": world_seed, "islands": list}


## True when docks are placed by hand: a terminal can then only go in one.
func locked_docks() -> bool:
	for s in islands:
		if not s.docks.is_empty():
			return true
	return false


func to_json() -> String:
	return JSON.stringify(to_dict(), "\t", false)


## JSON represents integers as floats. Reject fractional seeds and non-finite coordinates.
static func _matches(value: Variant, default_value: Variant) -> bool:
	if default_value is float or default_value is int:
		if not (value is float or value is int) or not is_finite(value):
			return false
		return default_value is float or value == int(value)
	return typeof(value) == typeof(default_value)


static func from_dict(d: Dictionary) -> MapLayout:
	# Versionless layouts use the original island format, including the single world-space dock.
	var version: Variant = d.get("version", VERSION)
	if not _matches(version, VERSION) or version != VERSION or not d.get("islands") is Array:
		return null
	if not _matches(d.get("world_seed", 1), 1):
		return null
	var lay := MapLayout.new()
	lay.world_seed = int(d.get("world_seed", 1))
	for e in d.islands:
		if not e is Dictionary:
			return null
		var spec := IslandSpec.from_dict(e)
		if spec == null:
			return null
		lay.islands.append(spec)
	return lay


## null when the text isn't a supported layout.
static func from_json(text: String) -> MapLayout:
	var json := JSON.new()
	if json.parse(text) != OK or not json.data is Dictionary:
		return null
	return from_dict(json.data)


static func load_file(path: String) -> MapLayout:
	if not FileAccess.file_exists(path):
		return null
	return from_json(FileAccess.get_file_as_string(path))


func save_file(path: String) -> Error:
	if FileAccess.file_exists(path) and load_file(path) == null:
		return ERR_FILE_UNRECOGNIZED
	var data := to_dict()
	if from_dict(data) == null:
		return ERR_INVALID_DATA
	return SavedText.replace(path, JSON.stringify(data, "\t", false) + "\n")


func duplicate() -> MapLayout:
	return from_dict(to_dict())
