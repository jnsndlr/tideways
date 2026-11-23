class_name Timetable
## A boat's timetable (stage 4): the minutes after midnight she leaves her first
## stop, sorted. Each departure is one round of her stops; the times at her other
## stops follow from the leg and dwell times (Ferry.plan_offsets). Empty: she
## sails as fast as loading allows.

const DAY := 1440


## Which departures come too soon after the one before (wrapping from the day
## before) for a round of `round_minutes`: she can't make them.
static func too_soon(times: Array[int], round_minutes: float) -> Array[bool]:
	var out: Array[bool] = []
	for k in times.size():
		var prev := times[k - 1] if k > 0 else times[-1] - DAY
		out.append(times[k] - prev < round_minutes - 0.01)
	return out


static func any_too_soon(times: Array[int], round_minutes: float) -> bool:
	return too_soon(times, round_minutes).has(true)


## "6:30" or "18:05" -> minutes after midnight; -1 if it isn't a time.
static func parse(text: String) -> int:
	var parts := text.strip_edges().split(":")
	if parts.size() != 2 or not parts[0].is_valid_int() or not parts[1].is_valid_int():
		return -1
	var hour := int(parts[0])
	var minute := int(parts[1])
	if hour < 0 or hour >= 24 or minute < 0 or minute >= 60:
		return -1
	return hour * 60 + minute


static func text(m: float) -> String:
	var total := posmod(int(round(m)), DAY)
	var h := total / 60
	var h12 := h % 12
	if h12 == 0:
		h12 = 12
	return "%d:%02d %s" % [h12, total % 60, "AM" if h < 12 else "PM"]
