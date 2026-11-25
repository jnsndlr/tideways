extends SceneTree


func _initialize() -> void:
	var default_launch := SessionLaunchOptions.new([])
	var positional := SessionLaunchOptions.new(["input"])
	var sandbox := SessionLaunchOptions.new([
		"input", "--main=1", "--seed=7", "--seed=123", "--shot=a=b.png", "--time="
	])
	var expected := {"main": "1", "seed": "123", "shot": "a=b.png", "time": ""}
	var authored := SessionLaunchOptions.new(["--scenario=opening", "--main", "--full-network"])
	if default_launch.entry != SessionLaunchOptions.Entry.MENU or not default_launch.values.is_empty():
		push_error("A normal launch should show the menu")
	elif positional.entry != SessionLaunchOptions.Entry.SANDBOX:
		push_error("A positional argument should still skip the menu")
	elif sandbox.entry != SessionLaunchOptions.Entry.SANDBOX or sandbox.values != expected:
		push_error("Sandbox must preserve assigned values and select the last repeated option")
	elif authored.entry != SessionLaunchOptions.Entry.MAIN_MAP or authored.values != {"main": "1", "scenario": "opening", "full-network": "1"}:
		push_error("The exact --main switch should open the authored map with its scenario options")
	elif not authored.values.is_read_only():
		push_error("One session must not be able to change the next session's launch options")
	else:
		print("TEST PASSED")
		quit(0)
		return
	quit(1)
