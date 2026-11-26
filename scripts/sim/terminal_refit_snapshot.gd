class_name TerminalRefitSnapshot
extends RefCounted
## The fitted sizes and paid widening job on a rebuilt terminal's existing slips.
## Building new berths and reassigning their routes need the harbour layout snapshot.


static func capture(term: Terminal) -> Dictionary:
	if term._assignments != null and term._assignments.has_moves():
		return {}
	var slips := []
	for i in term.town.slips.size():
		var slip := term.town.slips[i]
		if slip.building and (not term.refit_new or i != term.refit_slip):
			return {}
		(
			slips
			. append(
				{
					"offset": term.town.slip_offset(i),
					"tie_up": slip.tie_up,
					"building": slip.building,
					"routes": _route_keys(term, slip),
					"size": slip.size,
				}
			)
		)
	var job := {}
	if term.refit_stage != TerminalRefit.Stage.NONE and not term.refit_new:
		job = {
			"offset": term.town.slip_offset(term.refit_slip),
			"stage": TerminalRefit.Stage.keys()[term.refit_stage],
			"remaining": term.refit_remaining
		}
	return {
		"version": 2,
		"seed": str(term.sim.map.map_seed),
		"town": term.town.key,
		"slips": slips,
		"job": job
	}


static func _route_keys(term: Terminal, slip: MapData.Slip) -> Array[String]:
	var keys: Array[String] = []
	for rid in slip.routes:
		keys.append(term.sim.map.routes[rid].key)
	keys.sort()
	return keys


## Install into the same harbour topology. Validate every slip and the crane
## phase before fitting any guides or waking the project; restore never buys work.
static func restore(record: Variant, term: Terminal) -> bool:
	if not _matches_header(record, term):
		return false
	if (
		term.refit_stage != TerminalRefit.Stage.NONE
		and not (term.refit_new and record.job.is_empty())
	):
		return false
	var sizes: Array[int] = []
	sizes.resize(term.town.slips.size())
	for row in record.slips:
		if not row is Dictionary:
			return false
		var i := _index(term, row.get("offset"))
		if i < 0 or sizes[i] != 0 or not _matches_slip(row, term, i, int(record.version)):
			return false
		sizes[i] = int(row.size)
	var job: Dictionary = record.job
	var target := -1
	var stage := TerminalRefit.Stage.NONE
	if not job.is_empty():
		target = _index(term, job.get("offset"))
		if target < 0 or not job.get("stage") is String or not TerminalRefit.Stage.has(job.stage):
			return false
		stage = TerminalRefit.Stage[job.stage]
		if not _valid_job(stage, job.get("remaining"), sizes[target], term.town.slips[target].size):
			return false
	for i in sizes.size():
		if sizes[i] != term.town.slips[i].size:
			term.fit_slip(i, sizes[i])
	if target >= 0:
		term._refit.resume_job(target, stage, job.remaining, TerminalRefit.WORK, false)
	else:
		term.refit_changed.emit()
	return true


static func _matches_header(r: Variant, term: Terminal) -> bool:
	return (
		r is Dictionary
		and _number(r.get("version"))
		and (r.version == 1 or r.version == 2)
		and r.get("town") == term.town.key
		and r.get("seed") == str(term.sim.map.map_seed)
		and r.get("job") is Dictionary
		and r.get("slips") is Array
		and r.slips.size() == term.town.slips.size()
		and (term._assignments == null or not term._assignments.has_moves())
	)


static func _index(term: Terminal, offset: Variant) -> int:
	if _number(offset):
		for i in term.town.slips.size():
			if is_equal_approx(term.town.slip_offset(i), offset):
				return i
	return -1


static func _matches_slip(row: Dictionary, term: Terminal, index: int, version: int) -> bool:
	var slip := term.town.slips[index]
	return (
		(
			not slip.building
			if version == 1
			else row.get("building") is bool and row.building == slip.building
		)
		and (not slip.building or row.get("size") == 1)
		and row.get("tie_up") is bool
		and row.tie_up == slip.tie_up
		and row.get("routes") is Array
		and row.routes == _route_keys(term, slip)
		and _number(row.get("size"))
		and floor(row.size) == row.size
		and row.size >= slip.size
		and row.size < MapData.Slip.LARGEST_BOAT.size()
	)


static func _valid_job(
	stage: TerminalRefit.Stage, left: Variant, size: int, initial_size: int
) -> bool:
	if not _number(left) or left <= 0:
		return false
	var total := TerminalRefit.ARRIVAL + TerminalRefit.WORK + TerminalRefit.DEPARTURE
	var work_start := TerminalRefit.WORK + TerminalRefit.DEPARTURE
	if stage == TerminalRefit.Stage.LEAVING:
		return left <= TerminalRefit.DEPARTURE and size > initial_size
	if size + 1 >= MapData.Slip.LARGEST_BOAT.size():
		return false
	match stage:
		TerminalRefit.Stage.CLEARING:
			return left == total
		TerminalRefit.Stage.ARRIVING:
			return left >= work_start and left <= total
		TerminalRefit.Stage.WORKING:
			return left >= TerminalRefit.DEPARTURE and left <= work_start
	return false


static func _number(v: Variant) -> bool:
	return (v is float or v is int) and is_finite(v)
