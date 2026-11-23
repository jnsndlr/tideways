class_name SlipConflictText
## Formats shared-slip forecasts for the schedule editor and ferry panel.

## A boat holds "most sailings" when it is at least this share of her sailings.
const RECURRING := 0.5
## Clash warnings' colour (amber: a warning, not the red of a sailing she can't make).
const WARN := Color(0.98, 0.76, 0.36)


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
	var where := sim.map.towns[c.island].name.trim_suffix(" Island")
	var mins := maxi(1, roundi(c.hold))
	if c.she_holds:
		return "%s %s: the %s is alongside · she holds ~%d min offshore" % [where, Timetable.text(c.at), c.other.ferry_name, mins]
	return "%s %s: she is alongside · the %s holds ~%d min offshore" % [where, Timetable.text(c.at), c.other.ferry_name, mins]


static func _slip_names(sim: Simulation, cs: Array) -> String:
	var names: Array[String] = []
	for c in cs:
		var n := sim.map.towns[c.island].name.trim_suffix(" Island")
		if n not in names:
			names.append(n)
	return " and ".join(names)


static func _object(her: String) -> String:
	return "her" if her == "she" else her
