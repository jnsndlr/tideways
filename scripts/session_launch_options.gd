class_name SessionLaunchOptions
extends RefCounted
## The process command line selects the initial scene and supplies session options.

enum Entry { MENU, MAIN_MAP, SANDBOX }

var entry := Entry.MENU
var values: Dictionary[String, String] = {}


func _init(arguments: PackedStringArray) -> void:
	if not arguments.is_empty():
		entry = Entry.MAIN_MAP if "--main" in arguments else Entry.SANDBOX
	for argument in arguments:
		if argument.begins_with("--"):
			var pair := argument.substr(2).split("=", true, 1)
			values[pair[0]] = pair[1] if pair.size() > 1 else "1"
	values.make_read_only()
