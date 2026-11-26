class_name TerminalBerthPurchaseSnapshot
extends RefCounted
## Rebuild the first purchased slip from the same region before applying fitted
## sizes. The ledger owns its receipt. The terminal catalogue owns siting and dredging.


static func capture(term: Terminal) -> Dictionary:
	if term.town.slips.size() != term.original_slip_count + 1:
		return {}
	var index := term.original_slip_count
	var slip := term.town.slips[index]
	var building := term.refit_new
	if building and term.refit_slip != index:
		return {}
	return {
		"version": 1,
		"seed": str(term.sim.map.map_seed),
		"town": term.town.key,
		"original_count": index,
		"offset": term.town.slip_offset(index),
		"tie_up": slip.tie_up,
		"stage": TerminalRefit.Stage.keys()[term.refit_stage] if building else "NONE",
		"remaining": term.refit_remaining if building else 0.0,
	}


static func restore(record: Variant, term: Terminal) -> bool:
	if not _matches(record, term):
		return false
	var kind := TerminalUpgrade.Kind.TIE_UP if record.tie_up else TerminalUpgrade.Kind.SLIP
	var offer := term.find_upgrade(kind, -1, record.offset)
	if offer == null or not is_finite(offer.v) or not offer.blocked.is_empty():
		return false
	var stage: TerminalRefit.Stage = TerminalRefit.Stage[record.stage]
	var work := offer.build_minutes - TerminalRefit.ARRIVAL - TerminalRefit.DEPARTURE
	if not _remaining_matches(stage, record.remaining, work):
		return false
	var index := term.place_purchased_slip(offer)
	if stage != TerminalRefit.Stage.NONE:
		term._refit.resume_job(index, stage, record.remaining, work, true)
	if stage in [TerminalRefit.Stage.LEAVING, TerminalRefit.Stage.NONE]:
		term._open_slip(index)
	return true


static func _matches(record: Variant, term: Terminal) -> bool:
	return (
		record is Dictionary
		and _number(record.get("version"))
		and record.version == 1
		and record.get("seed") == str(term.sim.map.map_seed)
		and record.get("town") == term.town.key
		and _number(record.get("original_count"))
		and record.original_count == term.original_slip_count
		and term.town.slips.size() == term.original_slip_count
		and term.refit_stage == TerminalRefit.Stage.NONE
		and _number(record.get("offset"))
		and record.get("tie_up") is bool
		and record.get("stage") is String
		and TerminalRefit.Stage.has(record.stage)
		and _number(record.get("remaining"))
	)


static func _remaining_matches(stage: TerminalRefit.Stage, left: float, work: float) -> bool:
	var full := TerminalRefit.ARRIVAL + work + TerminalRefit.DEPARTURE
	match stage:
		TerminalRefit.Stage.NONE:
			return left == 0
		TerminalRefit.Stage.CLEARING:
			return left == full
		TerminalRefit.Stage.ARRIVING:
			return left >= work + TerminalRefit.DEPARTURE and left <= full
		TerminalRefit.Stage.WORKING:
			return left >= TerminalRefit.DEPARTURE and left <= work + TerminalRefit.DEPARTURE
		TerminalRefit.Stage.LEAVING:
			return left > 0 and left <= TerminalRefit.DEPARTURE
	return false


static func _number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)
