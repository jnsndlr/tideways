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
	_car = EconomyConfig.nonnegative_rate(settings, "car", _car)
	_truck = EconomyConfig.nonnegative_rate(settings, "truck", _truck)
	_included_metres = EconomyConfig.nonnegative_rate(settings, "included_metres", _included_metres)
	_extra_fraction_per_metre = EconomyConfig.nonnegative_rate(settings, "extra_fraction_per_metre", _extra_fraction_per_metre)


func measured(metres: float) -> float:
	return _car * (1.0 + _extra_fraction_per_metre * maxf(metres - _included_metres, 0.0))


func flat(is_truck: bool) -> float:
	return _truck if is_truck else _car
