class_name FareSchedule
extends RefCounted
## A company reads its fare schedule once when its ledger is created.
## Each extra metre costs a fraction of the base car fare.

const SETTING := "tideways/economy/fares"

var _car := 18.5
var _truck := 42.0
var _included_metres := 6.7
var _extra_fraction_per_metre := 0.3


func _init(settings: Variant = {}) -> void:
	if settings is Dictionary:
		_car = _read_rate(settings, "car", _car)
		_truck = _read_rate(settings, "truck", _truck)
		_included_metres = _read_rate(settings, "included_metres", _included_metres)
		_extra_fraction_per_metre = _read_rate(settings, "extra_fraction_per_metre", _extra_fraction_per_metre)


static func _read_rate(settings: Dictionary, key: String, fallback: float) -> float:
	var value: Variant = settings.get(key)
	if (value is float or value is int) and is_finite(value) and value >= 0:
		return float(value)
	return fallback


func measured(metres: float) -> float:
	return _car * (1.0 + _extra_fraction_per_metre * maxf(metres - _included_metres, 0.0))


func flat(is_truck: bool) -> float:
	return _truck if is_truck else _car
