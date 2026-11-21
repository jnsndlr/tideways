extends SceneTree
## Check the crane against its actual scow rig. Each pile leaves its own rack
## position, hangs vertically, swings out, lowers and stays there when released.

func _initialize() -> void:
	var crew := SlipRefitCrew.new()
	crew.setup(null)
	var valid := true
	for k in SlipRefitCrew.PICK_ORDER.size():
		if not _check_cycle(crew, k):
			push_error("Slip refit crane lost pile %d during pickup or placement" % (SlipRefitCrew.PICK_ORDER[k] + 1))
			valid = false
	crew._pose_crane(Terminal.RefitStage.LEAVING, 0.0)
	for pile in crew._piles:
		if pile.visible:
			push_error("A driven pile was still on the departing scow")
			valid = false
	crew._pose_crane(Terminal.RefitStage.ARRIVING, 0.0)
	for pile in crew._piles:
		if not pile.visible:
			push_error("The returning scow did not bring all five piles")
			valid = false
	crew.free()
	if valid:
		print("TEST PASSED")
	quit(0 if valid else 1)


func _pose(crew: SlipRefitCrew, k: int, fraction: float) -> void:
	crew._pose_crane(Terminal.RefitStage.WORKING, SlipRefitCrew.START + (k + fraction) * SlipRefitCrew.CYCLE)


func _check_cycle(crew: SlipRefitCrew, k: int) -> bool:
	var i: int = SlipRefitCrew.PICK_ORDER[k]
	var pile: Node3D = crew._piles[i]
	_pose(crew, k, 0.2)
	if not pile.visible or not pile.transform.is_equal_approx(crew._pile_rest[i]):
		return false
	_pose(crew, k, 0.54)
	if not crew._sling.visible or absf(pile.basis.z.normalized().y) < 0.99:
		return false
	var lifted := pile.position
	_pose(crew, k, 0.72)
	var over_water := pile.position
	if Vector2(lifted.x, lifted.z).distance_to(Vector2(over_water.x, over_water.z)) < 1.0:
		return false
	_pose(crew, k, 0.88)
	var lowered := pile.transform
	if not pile.visible or not crew._sling.visible or lowered.origin.y >= over_water.y - 1.0:
		return false
	_pose(crew, k, 0.94)
	return not crew._sling.visible and pile.visible and pile.transform.is_equal_approx(lowered)
