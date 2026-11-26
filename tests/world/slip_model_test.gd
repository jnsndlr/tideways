extends "res://tests/rule_test_case.gd"
## Check the three independent choices at a real terminal, including partial asset installs.


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var authored := not "--classic-slip" in OS.get_cmdline_user_args()
	var span := authored and ResourceLoader.exists("res://assets/models/slip_mid.glb")
	var trestle := span and ResourceLoader.exists("res://assets/models/trestle_mid.glb")
	var guides := authored
	for file in ["ferry_dolphin_lod", "ferry_dolphin_small_lod", "wing_wall_lod"]:
		guides = guides and ResourceLoader.exists("res://assets/models/%s.glb" % file)
	check(SlipModel.authored_trestle == trestle, "The trestle needs the transfer span")
	var region := TinyRegion.build()
	var sim := region.start(root)
	for terminal: Terminal in sim.terminals.values():
		check((terminal.slip_ramps[0] != null) == span, "Ramp state follows span availability")
		check(
			(terminal.slip_guides[0] != null) == guides, "Fitted guides need all three guide models"
		)
	if span:
		var towers := Models.slip_mesh("towers")
		check(towers == Models.slip_mesh("towers"), "Fixed towers share one immutable mesh")
		check(towers != Models.slip_mesh("span"), "The moving span has its own geometry")
	if trestle:
		check(
			not SlipModel.trestle_part("landing").verts.is_empty(), "The landing has deck geometry"
		)
	sim.free()
	finish()
