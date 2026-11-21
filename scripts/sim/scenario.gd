class_name Scenario
extends RefCounted
## How a company starts: its cash, the terminals it owns, its boats and the
## schedules they run. Islands are named by their region key (MapData.Island.key).
## No link between terminals exists without a schedule: the map generator builds
## a route only for each pair of consecutive stops (`links()`), and a terminal
## with no scheduled stop gets one idle slip.
## A generated map with no scenario plans its own network; `from_network` then
## puts a boat on every route so the simulation still starts from a scenario.

const OPENING := "res://maps/opening.json"

class Boat:
	var key := ""
	var name := ""
	var size := 2

## A boat and the stops it calls at in turn. Two stops shuttle back and forth.
## Departure times and frequency arrive with the timetable editor (stage 4).
class Schedule:
	var boat := ""
	var stops: Array[String] = []


var name := ""
var cash := CompanyLedger.STARTING_CASH
## Island keys that start with a terminal. Empty: the generator plans the network.
var terminals: Array[String] = []
var fleet: Array[Boat] = []
var schedules: Array[Schedule] = []


static func load_file(path: String) -> Scenario:
	var text := FileAccess.get_file_as_string(path)
	var data = JSON.parse_string(text)
	if not data is Dictionary:
		push_error("Scenario %s is missing or not JSON" % path)
		return null
	var s := Scenario.new()
	s.name = str(data.get("name", ""))
	s.cash = float(data.get("cash", CompanyLedger.STARTING_CASH))
	for t in data.get("terminals", []):
		s.terminals.append(str(t["key"]) if t is Dictionary else str(t))
	for b in data.get("fleet", []):
		var boat := Boat.new()
		boat.key = str(b["key"])
		boat.name = str(b.get("name", boat.key))
		boat.size = clampi(int(b.get("size", 2)), 1, 5)
		s.fleet.append(boat)
	for sc in data.get("schedules", []):
		var schedule := Schedule.new()
		schedule.boat = str(sc["boat"])
		for stop in sc.get("stops", []):
			schedule.stops.append(str(stop))
		s.schedules.append(schedule)
	return s


## Every route of a planned network with a boat shuttling on it (the sandbox).
static func from_network(map: MapData, names: Array, sizes: Array[int]) -> Scenario:
	var s := Scenario.new()
	s.name = "Network"
	for isl in map.islands:
		if isl.has_terminal:
			s.terminals.append(isl.key)
	for i in map.routes.size():
		var r := map.routes[i]
		var boat := Boat.new()
		boat.key = "hull-%d" % i
		boat.name = names[r.id % names.size()]
		boat.size = sizes[i]
		s.fleet.append(boat)
		var schedule := Schedule.new()
		schedule.boat = boat.key
		schedule.stops = [map.islands[r.a].key, map.islands[r.b].key]
		s.schedules.append(schedule)
	return s


## The pairs of island keys the schedules sail between, each once.
func links() -> Array[PackedStringArray]:
	var out: Array[PackedStringArray] = []
	var seen := {}
	for schedule in schedules:
		var n := schedule.stops.size()
		for i in (n if n > 2 else n - 1):
			var a := schedule.stops[i]
			var b := schedule.stops[(i + 1) % n]
			var id := "%s|%s" % ([a, b] if a < b else [b, a])
			if a != b and not seen.has(id):
				seen[id] = true
				out.append(PackedStringArray([a, b]))
	return out


func boat(key: String) -> Boat:
	for b in fleet:
		if b.key == key:
			return b
	return null
