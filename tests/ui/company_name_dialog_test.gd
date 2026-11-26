extends "res://tests/rule_test_case.gd"
## Return and Start must both require an explicitly entered company name.

const TICKET := preload("res://scenes/company_name_dialog.tscn")
var chosen: Array[String] = []


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var ticket := TICKET.instantiate()
	root.add_child(ticket)
	ticket.name_chosen.connect(func(value: String): chosen.append(value))
	var field: LineEdit = ticket.get_node("%NameField")
	var start: Button = ticket.get_node("%Start")
	field.edit()
	for blank in ["", "   "]:
		root.push_text_input(blank)
		await process_frame
		await process_frame
		check(start.disabled, "Start should be disabled for an empty or spaces-only name")
		press_key(KEY_ENTER)
		if ticket.is_queued_for_deletion():
			check(false, "Return accepted a blank name")
			await process_frame
			finish()
			return
		check(chosen.is_empty() and field.is_editing(), "Blank Return should keep the editor open")
	root.push_text_input("North Shore  ")
	await process_frame
	await process_frame
	check(not start.disabled, "A typed name should enable Start")
	field.select_all()
	press_key(KEY_BACKSPACE)
	await process_frame
	await process_frame
	check(start.disabled, "Clearing a valid name should disable Start again")
	root.push_text_input("  North Shore  ")
	press_key(KEY_ENTER)
	check(chosen == ["North Shore"], "Return should submit one trimmed name")
	await process_frame
	finish()


func press_key(code: Key) -> void:
	for down in [true, false]:
		var key := InputEventKey.new()
		key.keycode = code
		key.pressed = down
		root.push_input(key, true)
