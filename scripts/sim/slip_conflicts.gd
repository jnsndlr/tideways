class_name SlipConflicts
## Stage 4: where two boats' timetables want one slip at once. Each boat's plan
## (Ferry.plan_offsets, a full deck at every call) puts her alongside each stop
## from when she is due in until she leaves: at her first stop from the last
## round's arrival back until the sailing after. When two boats' times there
## overlap, whoever comes in second holds offshore until the slip is clear
## (the sim's shared-slip rules, Ferry._corridor_wait). These only warn: the
## editor never refuses a timetable for them.

## Minutes after she casts off before the next boat can come in (she has to
## back off and clear the water round the slip).
const CLEAR := 3.0


## One boat's planned day: [{island, slip, start, end, sailing}], minutes after
## midnight (start may be negative, end past a day, for calls across midnight).
## Empty with no times or a leg with no route.
static func windows(f: Ferry, ids: Array[int], times: Array[int], p: int) -> Array:
	var out := []
	var o := f.plan_offsets(ids, p)
	if o.is_empty() or times.is_empty():
		return out
	var sim := f.sim
	var n := ids.size()
	var dwell := f.planned_dwell()
	for k in times.size():
		var t := float(times[k])
		var prev := float(times[k - 1] if k > 0 else times[-1] - Timetable.DAY)
		for i in n:
			var isl := sim.map.towns[ids[i]]
			var r := sim.route_between(ids[i], ids[(i + 1) % n])
			var start := prev + o[n] - dwell if i == 0 else t + o[i] - dwell
			var slip := isl.slip_index(r.id)
			var tie := _tie_up_for(f, isl, t - start - f.planned_unload()) if i == 0 else -1
			if tie >= 0:
				# Between sailings she lies at a tie-up (FerryLayUp.GAP_TIE_UP), and the slip
				# is free from when she has moved off it until she is back.
				var move := f.shift_minutes(SlipShiftPath.estimated_length(absf(isl.slip_offset(tie) - isl.slip_offset(slip))))
				out.append({"island": ids[i], "slip": slip, "start": start, "end": start + f.planned_unload() + move * 0.5, "sailing": k})
				start = t - f.dwell.maximum_loading - FerryLayUp.GAP_MARGIN - move * 0.5
			out.append({"island": ids[i], "slip": slip, "start": start, "end": t + o[i], "sailing": k})
	return out


## The tie-up slip at `isl` she goes to in a gap of `gap` minutes between
## unloading and her next sailing there (FerryLayUp.GAP_TIE_UP), or -1.
static func _tie_up_for(f: Ferry, isl: MapData.Town, gap: float) -> int:
	if gap < FerryLayUp.GAP_TIE_UP:
		return -1
	for i in isl.tie_ups():
		if isl.slips[i].fits(f.fc.size):
			return i
	return -1


## The plan another boat is on: the stops and times she runs, or will from her
## next call. Null if she has no timetable or is laid up.
static func plan_of(f: Ferry) -> Dictionary:
	if not f.in_service():
		return {}
	var pending := not f.next_stops.is_empty()
	var ids: Array[int] = f.next_stops if pending else f.stops
	var times: Array[int] = f.itinerary.pending.times if pending else f.timetable
	return {"ferry": f, "ids": ids, "times": times, "pace": f.pace}


## Clashes between boat `f` on (`ids`, `times`, pace `p`) and every other boat
## in service on a timetable. Each: {other, island, sailing (hers),
## other_sailing, at (when the second comes in), hold (minutes the second holds
## offshore), she_holds (she is second)}. `untimed`: the other boats sharing a
## slip with her that sail as loading allows, so can't be planned round.
static func check(f: Ferry, ids: Array[int], times: Array[int], p: int) -> Dictionary:
	var out := {"clashes": [], "untimed": [], "sailings": times.size()}
	var mine := windows(f, ids, times, p)
	if mine.is_empty():
		return out
	var my_slips := {}
	for w in mine:
		my_slips["%d:%d" % [w.island, w.slip]] = true
	var calls := []
	_append_calls(calls, f, mine, times.size())
	for other: Ferry in f.sim.ferries:
		if other == f:
			continue
		var plan := plan_of(other)
		if plan.is_empty():
			continue
		if plan.times.is_empty():
			for i in plan.ids.size():
				var r := f.sim.route_between(plan.ids[i], plan.ids[(i + 1) % plan.ids.size()])
				var isl := f.sim.map.towns[plan.ids[i]]
				if r != null and my_slips.has("%d:%d" % [plan.ids[i], isl.slip_index(r.id)]) and other not in out.untimed:
					out.untimed.append(other)
			continue
		_append_calls(calls, other, windows(other, plan.ids, plan.times, plan.pace), plan.times.size())
	_assign_calls(f, calls, out.clashes)
	return out


## Include adjacent days so a call after midnight sees boats still alongside.
static func _append_calls(calls: Array, ferry: Ferry, scheduled: Array, sailings: int) -> void:
	for w in scheduled:
		for shift: int in [-Timetable.DAY, 0, Timetable.DAY]:
			calls.append({"boat": ferry, "town": w.island, "slip": w.slip, "sailing": w.sailing,
				"sailings": sailings, "start": w.start + shift, "end": w.end + shift, "shift": shift})


static func _assign_calls(f: Ferry, calls: Array, clashes: Array) -> void:
	calls.sort_custom(func(a, b): return a.start < b.start if a.start != b.start else a.boat.fleet_key < b.boat.fleet_key)
	var occupied := {}
	for call in calls:
		var term: Terminal = f.sim.terminals.get(call.town)
		if term == null or call.slip < 0:
			continue
		var berths: Dictionary = occupied.get_or_add(call.town, {})
		var busy := func(i: int):
			return berths.has(i) and berths[i].boat != call.boat and berths[i].end + CLEAR > call.start
		var berth := term.arrival_slip(call.slip, call.boat.fc.size, busy)
		if busy.call(berth):
			var previous: Dictionary = berths[berth]
			var she_holds: bool = call.boat == f
			var mine: Dictionary = call if she_holds else previous
			if mine.boat == f and mine.shift == 0:
				var other: Dictionary = previous if she_holds else call
				clashes.append({"other": other.boat, "island": call.town, "sailing": mine.sailing,
					"other_sailing": other.sailing, "at": call.start, "hold": previous.end + CLEAR - call.start,
					"she_holds": she_holds, "other_sailings": other.sailings})
		if not berths.has(berth) or berths[berth].end <= call.end:
			berths[berth] = call


## The clashes on sailing `k` (of `check`'s result).
static func on_sailing(result: Dictionary, k: int) -> Array:
	return result.clashes.filter(func(c): return c.sailing == k)
