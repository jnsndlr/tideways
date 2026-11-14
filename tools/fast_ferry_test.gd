extends SceneTree

func _initialize() -> void:
	var demand: Array[float] = [40.0, 10.0, 30.0, 50.0, 20.0]
	var assignments := FerryClass.sizes_by_demand(demand)
	if assignments != [4, 1, 3, 5, 2]:
		push_error("Expected busier routes to receive larger ferries; got %s" % str(assignments))
		quit(1)
		return
	print("Ferry sizes follow route demand.")
	if not _captains_suit_different_crossings():
		quit(1)
		return
	quit(0)


## The same ferry (the mid-size class) on a short hop and on a long crossing: each
## captain should be the quicker on one of them, by a margin a player can see.
func _captains_suit_different_crossings() -> bool:
	var cruise: float = FerryClass.of(3).cruise
	var roster := Captain.roster()
	var open_water := roster[0]
	var docker := roster[1]
	var short_gain := open_water.crossing_minutes(470.0, cruise) - docker.crossing_minutes(470.0, cruise)
	var long_gain := docker.crossing_minutes(2050.0, cruise) - open_water.crossing_minutes(2050.0, cruise)
	if Captain.best_for(470.0, cruise) != docker or short_gain < 2.0:
		push_error("Expected %s to be at least 2 min quicker on a 470 m hop; got %.1f" % [docker.name, short_gain])
		return false
	if Captain.best_for(2050.0, cruise) != open_water or long_gain < 2.0:
		push_error("Expected %s to be at least 2 min quicker on a 2050 m crossing; got %.1f" % [open_water.name, long_gain])
		return false
	print("Captains: %s is %.1f min quicker on a short hop, %s %.1f min quicker on a long crossing." % [
		docker.name, short_gain, open_water.name, long_gain])
	return true
