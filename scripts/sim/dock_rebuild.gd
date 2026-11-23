extends RefCounted
## Company state needed when a purchased dock forces the story map to regenerate.
## Store stable keys and simulation values so the old scene can be freed.

var _day: int
var _minutes: float
var _ledger: CompanyLedger
var _works: Dictionary[String, Terminal.Works] = {}
var _paces: Dictionary[String, int] = {}
var _captains: Dictionary[String, Captain] = {}


func _init(sim: Simulation) -> void:
	_day = sim.day
	_minutes = sim.minutes
	var sc := sim.scenario
	_ledger = sim.ledger
	for t: Terminal in sim.terminals.values():
		_works[t.island.key] = Terminal.Works.new(t)
		var working: Array[int] = []
		var ties: Array[int] = []
		for slip in t.island.slips:
			if slip.tie_up:
				ties.append(slip.size)
			else:
				working.append(slip.size)
		sc.slips[t.island.key] = working
		sc.tie_ups[t.island.key] = ties
	for f in sim.ferries:
		_paces[f.fleet_key] = f.pace
		_captains[f.fleet_key] = f.next_captain if f.next_captain else f.captain


func resume(sim: Simulation) -> void:
	sim.day = _day
	sim.minutes = _minutes
	sim.ledger = _ledger
	for t: Terminal in sim.terminals.values():
		if _works.has(t.island.key):
			_works[t.island.key].resume(t)
	for f in sim.ferries:
		if _paces.has(f.fleet_key):
			f.set_pace(_paces[f.fleet_key])
			f.assign_captain(_captains[f.fleet_key])
