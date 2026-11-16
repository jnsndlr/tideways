class_name MapLayout
extends RefCounted
## An authored map: where each island sits and how it is shaped, saved as JSON.
## MapGenerator builds everything else (mainland, islets, routes, towns) from it.
## The editor on the main map rolls and dials these, then saves or copies them.

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
	# Ferry dock placed by hand (else the generator picks one facing its neighbours):
	# a spot by the shore and the way the pier points out to sea.
	var dock := false
	var dock_x := 0.0
	var dock_z := 0.0
	var dock_angle := 0.0   # degrees, the heading out to sea (0 = +x, 90 = +z)

	const KEYS := ["name", "x", "z", "radius", "height", "hills", "peak", "lakes", "shape_seed", "stretch",
		"angle", "roughness", "forest", "fields", "pinned", "mainland", "dock", "dock_x", "dock_z", "dock_angle"]

	func to_dict() -> Dictionary:
		var d := {}
		for k in KEYS:
			var v = get(k)
			d[k] = snappedf(v, 0.001) if v is float else v
		return d

	static func from_dict(d: Dictionary) -> IslandSpec:
		var s := IslandSpec.new()
		for k in KEYS:
			if d.has(k):
				var v = d[k]
				match typeof(s.get(k)):
					TYPE_INT:
						v = int(v)
					TYPE_BOOL:
						v = bool(v)
					TYPE_FLOAT:
						v = float(v)
					TYPE_STRING:
						v = str(v)
				s.set(k, v)
		return s

	func duplicate() -> IslandSpec:
		return from_dict(to_dict())


## Seeds the mainland, islets, towns and everything else not in `islands`.
var world_seed := 1
var islands: Array[IslandSpec] = []


func to_dict() -> Dictionary:
	var list := []
	for s in islands:
		list.append(s.to_dict())
	return {"version": 1, "world_seed": world_seed, "islands": list}


func to_json() -> String:
	return JSON.stringify(to_dict(), "\t", false)


static func from_dict(d: Dictionary) -> MapLayout:
	var lay := MapLayout.new()
	lay.world_seed = int(d.get("world_seed", 1))
	for e in d.get("islands", []):
		lay.islands.append(IslandSpec.from_dict(e))
	return lay


## null when the text isn't a layout.
static func from_json(text: String) -> MapLayout:
	var d = JSON.parse_string(text)
	if not (d is Dictionary and d.has("islands")):
		return null
	return from_dict(d)


static func load_file(path: String) -> MapLayout:
	if not FileAccess.file_exists(path):
		return null
	return from_json(FileAccess.get_file_as_string(path))


func save_file(path: String) -> Error:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(to_json() + "\n")
	return OK


func duplicate() -> MapLayout:
	return from_dict(to_dict())
