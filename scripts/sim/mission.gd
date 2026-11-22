class_name Mission
extends RefCounted
## A trial mission: goals a scenario sets the player, read from its "mission"
## block. Nothing fails yet; a day limit only marks the goals still open as late.
##
##   "mission": {
##     "title": "South to Cypress", "brief": "…", "days": 5,
##     "goals": [
##       {"kind": "carried", "target": 250},          vehicles carried since the start
##       {"kind": "cash", "target": 60000},            cash in hand
##       {"kind": "terminal", "island": "island-3"},   a terminal open there
##       {"kind": "serve", "island": "island-3"}       a boat scheduled to call there
## An "island" key names any of its towns, or one town ("island-2/1").
##     ]
##   }
## Each goal may give its own "label".

var title := ""
var brief := ""
var days := 0                  # 0: no limit
var goals: Array[Dictionary] = []
var carried_before := 0
var start_day := -1


static func from_dict(d: Dictionary) -> Mission:
	var m := Mission.new()
	m.title = str(d.get("title", "Mission"))
	m.brief = str(d.get("brief", ""))
	m.days = int(d.get("days", 0))
	for g in d.get("goals", []):
		if g is Dictionary:
			m.goals.append(g)
	return m


## [label, done, progress text] for each goal.
func progress(sim: Simulation) -> Array:
	if start_day < 0:
		start_day = sim.day
	var out := []
	for g in goals:
		var kind := str(g.get("kind", ""))
		var target := float(g.get("target", 0))
		var key := str(g.get("island", ""))
		var label := str(g.get("label", ""))
		var done := false
		var text := ""
		match kind:
			"carried":
				var n := carried(sim)
				done = n >= target
				text = "%d / %d" % [n, int(target)]
				if label == "":
					label = "Carry %d vehicles" % int(target)
			"cash":
				done = sim.available_cash >= target
				text = Hud.fmt_money(sim.available_cash)
				if label == "":
					label = "Have %s in hand" % Hud.fmt_money(target)
			"terminal":
				done = _terminal_at(sim, key)
				if label == "":
					label = "Open a terminal on %s" % _name(sim, key)
			"serve":
				done = _served(sim, key)
				if label == "":
					label = "Run a boat to %s" % _name(sim, key)
			_:
				label = "Unknown goal: %s" % kind
		out.append([label, done, text])
	return out


func complete(sim: Simulation) -> bool:
	for p in progress(sim):
		if not p[1]:
			return false
	return not goals.is_empty()


## Days into the mission (1 on the first), and whether it's past its limit.
func day_of(sim: Simulation) -> int:
	return sim.day - (start_day if start_day >= 0 else sim.day) + 1


func late(sim: Simulation) -> bool:
	return days > 0 and day_of(sim) > days


func carried(sim: Simulation) -> int:
	return carried_before + sim.ledger.cars_total


static func _terminal_at(sim: Simulation, key: String) -> bool:
	for t: Terminal in sim.terminals.values():
		if _is(t.town, key):
			return true
	return false


static func _served(sim: Simulation, key: String) -> bool:
	for f in sim.ferries:
		for id in f.stops + f.next_stops:
			if _is(sim.map.towns[id], key):
				return true
	return false


static func _name(sim: Simulation, key: String) -> String:
	for t in sim.map.towns:
		if t.key == key:
			return t.name
	for isl in sim.map.islands:
		if isl.key == key:
			return isl.name
	return key


## Whether town `t` is the one `key` names, or on the island it names.
static func _is(t: MapData.Town, key: String) -> bool:
	return t.key == key or t.key.begins_with(key + "/")
