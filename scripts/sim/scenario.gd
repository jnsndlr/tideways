class_name Scenario
extends RefCounted
## How a company starts: its cash, the terminals it owns, its boats and the
## schedules they run. Islands are named by their region key (MapData.Island.key).
## No service exists without a schedule. The map generator plans a route between
## every pair of terminals in reach, but only the scheduled ones (`links()`) are
## in service (and, on a map without hand-placed docks, set where the docks
## face); the stop editor can put a boat on the rest. Each terminal
## has the slips listed for it (one small slip if none are), and the routes
## calling there share them; a slip no route uses is idle.
## A generated map with no scenario plans its own network; `from_network` then
## puts a boat on every route so the simulation still starts from a scenario.

const OPENING := "res://maps/opening.json"

class Boat:
	var key := ""
	var name := ""
	var size := 2

## A boat and the stops it calls at in turn. Two stops shuttle back and forth.
## The stop editor changes them in play (Simulation.reschedule); departure times
## and frequency come next in stage 4.
class Schedule:
	var boat := ""
	var stops: Array[String] = []
	## Starts tied up at the first stop's tie-up slip instead of in service.
	var laid_up := false
	## Minutes after midnight she leaves the first stop (Timetable); empty: as
	## soon as she has loaded. In the file: "departures": ["6:30", "18:05"].
	var departures: Array[int] = []


var name := ""
var cash := CompanyLedger.STARTING_CASH
## Island keys that start with a terminal. Empty: the generator plans the network.
var terminals: Array[String] = []
## Island key -> the sizes of its slips, left to right (MapData.Slip.size).
var slips := {}
## Island key -> the sizes of its tie-up slips (at most 2).
var tie_ups := {}
## Island key -> holding lanes paved at the start (the rest of the lot is bought lane by lane).
var lanes := {}
## Island key -> which of its locked dock sites (MapData.Island.dock_sites) the
## terminal stands at; 0 unless listed ("dock": 1).
var docks := {}
var fleet: Array[Boat] = []
## Goals for a trial mission (the scenario's "mission" block), or null.
var mission: Mission
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
		var key := str(t["key"]) if t is Dictionary else str(t)
		s.terminals.append(key)
		var sizes: Array[int] = []
		for slip in (t.get("slips", []) if t is Dictionary else []):
			sizes.append(MapData.Slip.size_from_name(str(slip.get("size", "small")) if slip is Dictionary else str(slip)))
		s.slips[key] = sizes if not sizes.is_empty() else [1]
		var ties: Array[int] = []
		for slip in (t.get("tie_ups", []) if t is Dictionary else []).slice(0, 2):
			ties.append(MapData.Slip.size_from_name(str(slip.get("size", "small")) if slip is Dictionary else str(slip)))
		s.tie_ups[key] = ties
		s.lanes[key] = int(t.get("lanes", 0)) if t is Dictionary else 0
		if t is Dictionary and t.has("dock"):
			s.docks[key] = int(t["dock"])
	if data.get("mission") is Dictionary:
		s.mission = Mission.from_dict(data["mission"])
	for b in data.get("fleet", []):
		var boat := Boat.new()
		boat.key = str(b["key"])
		boat.name = str(b.get("name", boat.key))
		boat.size = clampi(int(b.get("size", 2)), 1, FerryClass.MAX_SIZE)
		s.fleet.append(boat)
	for sc in data.get("schedules", []):
		var schedule := Schedule.new()
		schedule.boat = str(sc["boat"])
		for stop in sc.get("stops", []):
			schedule.stops.append(str(stop))
		schedule.laid_up = bool(sc.get("laid_up", false))
		for t in sc.get("departures", []):
			var m := Timetable.parse(str(t))
			if m < 0:
				push_warning("Schedule for %s: %s is not a time" % [schedule.boat, t])
			elif m not in schedule.departures:
				schedule.departures.append(m)
		schedule.departures.sort()
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


## Which dock site the terminal at island `key` stands at.
func dock_site(key: String) -> int:
	return int(docks.get(key, 0))


## The slip sizes for the terminal at `key`: one small slip unless listed.
func slip_sizes(key: String) -> Array[int]:
	var sizes: Array[int] = [1]
	sizes.assign(slips.get(key, sizes))
	return sizes


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
