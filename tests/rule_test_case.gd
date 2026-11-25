extends SceneTree
## Collect all failed checks so one run reports every broken expectation.

var _failures := 0


func check(condition: bool, message: String) -> void:
	if not condition:
		_failures += 1
		push_error(message)


func finish() -> void:
	if _failures == 0:
		print("TEST PASSED")
	quit(int(_failures > 0))
