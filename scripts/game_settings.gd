class_name GameSettings
## Player settings, saved to user://settings.cfg. Static so any script (and the
## command-line tools, which compile before autoloads exist) can reach them.
##
## Volumes are linear 0..1 per audio bus. The buses below Master are made here on
## first use, all feeding Master.

const PATH := "user://settings.cfg"
## Bus name -> default volume.
const VOLUMES := {"Master": 0.8, "Music": 0.7, "Radio": 0.8, "Effects": 0.7}

static var _cfg: ConfigFile


## Loads the saved settings and applies them, once.
static func ensure() -> void:
	if _cfg:
		return
	_cfg = ConfigFile.new()
	_cfg.load(PATH)  # A missing file just leaves the defaults.
	for bus: String in VOLUMES:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			var i := AudioServer.bus_count - 1
			AudioServer.set_bus_name(i, bus)
			AudioServer.set_bus_send(i, "Master")
	for bus: String in VOLUMES:
		_apply(bus)


static func volume(bus: String) -> float:
	ensure()
	var stored: Variant = _cfg.get_value("audio", bus.to_lower(), VOLUMES[bus])
	if (stored is float or stored is int) and is_finite(float(stored)):
		return clampf(float(stored), 0.0, 1.0)
	return VOLUMES[bus]


static func set_volume(bus: String, v: float) -> void:
	ensure()
	_cfg.set_value("audio", bus.to_lower(), clampf(v, 0.0, 1.0))
	_apply(bus)
	_cfg.save(PATH)


## On/off options under [display].
const FLAGS := {"floating_costs": false}


static func flag(key: String) -> bool:
	ensure()
	var stored: Variant = _cfg.get_value("display", key, FLAGS[key])
	return stored if stored is bool else FLAGS[key]


static func set_flag(key: String, on: bool) -> void:
	ensure()
	_cfg.set_value("display", key, on)
	_cfg.save(PATH)


static func _apply(bus: String) -> void:
	var i := AudioServer.get_bus_index(bus)
	var v := volume(bus)
	AudioServer.set_bus_volume_linear(i, v)
	AudioServer.set_bus_mute(i, v <= 0.001)
