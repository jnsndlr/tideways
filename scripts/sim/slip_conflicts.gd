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
## A boat holds "most sailings" when it is at least this share of her sailings.
const RECURRING := 0.5
## Clash warnings' colour (amber: a warning, not the red of a sailing she can't make).
const WARN := Color(0.98, 0.76, 0.36)


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
			var isl := sim.map.islands[ids[i]]
			var r := sim.route_between(ids[i], ids[(i + 1) % n])
			var start := prev + o[n] - dwell if i == 0 else t + o[i] - dwell
			var slip := isl.slip_index(r.id)
			var tie := _tie_up_for(f, isl, t - start - f.planned_unload()) if i == 0 else -1
			if tie >= 0:
				# Between sailings she lies at a tie-up (Ferry.GAP_TIE_UP), and the slip
				# is free from when she has moved off it until she is back.
				var move := f.shift_minutes(Ferry.shift_length(absf(isl.slip_offset(tie) - isl.slip_offset(slip))))
				out.append({"island": ids[i], "slip": slip, "start": start, "end": start + f.planned_unload() + move * 0.5, "sailing": k})
				start = t - Ferry.MAX_DWELL - Ferry.GAP_MARGIN - move * 0.5
			out.append({"island": ids[i], "slip": slip, "start": start, "end": t + o[i], "sailing": k})
	return out


## The tie-up slip at `isl` she goes to in a gap of `gap` minutes between
## unloading and her next sailing there (Ferry.GAP_TIE_UP), or -1.
static func _tie_up_for(f: Ferry, isl: MapData.Island, gap: float) -> int:
	if gap < Ferry.GAP_TIE_UP:
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
	var times: Array[int] = f._next_timetable if pending else f.timetable
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
	for other: Ferry in f.sim.ferries:
		if other == f:
			continue
		var plan := plan_of(other)
		if plan.is_empty():
			continue
		if plan.times.is_empty():
			for i in plan.ids.size():
				var r := f.sim.route_between(plan.ids[i], plan.ids[(i + 1) % plan.ids.size()])
				var isl := f.sim.map.islands[plan.ids[i]]
				if r != null and my_slips.has("%d:%d" % [plan.ids[i], isl.slip_index(r.id)]) and other not in out.untimed:
					out.untimed.append(other)
			continue
		var theirs := windows(other, plan.ids, plan.times, plan.pace)
		for a in mine:
			for b in theirs:
				if a.island != b.island or a.slip != b.slip:
					continue
				for shift in [-Timetable.DAY, 0, Timetable.DAY]:
					var bs: float = b.start + shift
					var be: float = b.end + shift
					if a.start < be + CLEAR and bs < a.end + CLEAR:
						var she_holds: bool = a.start > bs
						var at: float = a.start if she_holds else bs
						var hold: float = (be if she_holds else a.end) + CLEAR - at
						out.clashes.append({"other": other, "island": a.island, "sailing": a.sailing,
							"other_sailing": b.sailing, "at": at, "hold": hold, "she_holds": she_holds,
							"other_sailings": plan.times.size()})
	return out


## The clashes on sailing `k` (of `check`'s result).
static func on_sailing(result: Dictionary, k: int) -> Array:
	return result.clashes.filter(func(c): return c.sailing == k)


## Short lines for the whole timetable: a recurring hold (one boat holding for
## the other on most of her sailings, every day), else how many sailings clash.
## `her`: what to call the boat checked ("she", or her name).
static func summary(f: Ferry, result: Dictionary, her := "she") -> Array[String]:
	var lines: Array[String] = []
	var by_other := {}
	for c in result.clashes:
		by_other.get_or_add(c.other, []).append(c)
	for other: Ferry in by_other:
		var cs: Array = by_other[other]
		var where := _slip_names(f.sim, cs)
		var she_held := {}
		var they_held := {}
		for c in cs:
			if c.she_holds:
				she_held[c.sailing] = true
			else:
				they_held[c.other_sailing] = true
		var mine: int = result.sailings
		var theirs: int = cs[0].other_sailings
		var recurring := false
		if she_held.size() > 0 and she_held.size() >= ceili(mine * RECURRING):
			lines.append("Every day %s holds offshore for the %s at %s on %d of %d sailings." % [
				her, other.ferry_name, where, she_held.size(), mine])
			recurring = true
		if they_held.size() > 0 and they_held.size() >= ceili(theirs * RECURRING):
			lines.append("Every day the %s holds offshore for %s at %s on %d of her %d sailings." % [
				other.ferry_name, _object(her), where, they_held.size(), theirs])
			recurring = true
		if not recurring:
			var k := {}
			for c in cs:
				k[c.sailing] = true
			lines.append("%d sailing%s want%s %s's slip while the %s is there: whoever comes in second holds offshore." % [
				k.size(), "" if k.size() == 1 else "s", "s" if k.size() == 1 else "", where, other.ferry_name])
	for other: Ferry in result.untimed:
		lines.append("The %s sails as loading allows, so clashes at a slip you share can't be planned." % other.ferry_name)
	return lines


## A few words for the ferry panel: the worst way her timetable and another
## boat's meet ("" if they don't).
static func short_text(result: Dictionary) -> String:
	var best := ""
	var best_n := 0
	for other in _others(result):
		var cs: Array = result.clashes.filter(func(c): return c.other == other)
		var she := {}
		var they := {}
		for c in cs:
			if c.she_holds:
				she[c.sailing] = true
			else:
				they[c.other_sailing] = true
		if she.size() > best_n:
			best_n = she.size()
			best = "Holds for the %s on %d of %d sailings" % [other.ferry_name, she.size(), result.sailings]
		if they.size() > best_n:
			best_n = they.size()
			best = "The %s holds for her on %d of %d" % [other.ferry_name, they.size(), cs[0].other_sailings]
	return best


static func _others(result: Dictionary) -> Array:
	var out := []
	for c in result.clashes:
		if c.other not in out:
			out.append(c.other)
	return out


## One line for a clash on a sailing.
static func clash_text(sim: Simulation, c: Dictionary) -> String:
	var where := sim.map.islands[c.island].name.trim_suffix(" Island")
	var mins := maxi(1, roundi(c.hold))
	if c.she_holds:
		return "%s %s: the %s is alongside · she holds ~%d min offshore" % [where, Timetable.text(c.at), c.other.ferry_name, mins]
	return "%s %s: she is alongside · the %s holds ~%d min offshore" % [where, Timetable.text(c.at), c.other.ferry_name, mins]


static func _slip_names(sim: Simulation, cs: Array) -> String:
	var names: Array[String] = []
	for c in cs:
		var n := sim.map.islands[c.island].name.trim_suffix(" Island")
		if n not in names:
			names.append(n)
	return " and ".join(names)


static func _object(her: String) -> String:
	return "her" if her == "she" else her
