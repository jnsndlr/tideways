class_name SlipRefitCrew
extends Node3D
## The pusher and crane scow that refit a terminal's slip for bigger boats (Terminal's
## refit). With the slip closed and clear she comes in from offshore straight down the
## slip, scow first, moors between the inner and outer dolphins while the crane drives
## the new ones and the wing walls, then backs out to sea again. The terminal owns the
## work clock and every pose comes from it (Terminal.refit_stage / refit_progress).
## A child of the terminal, so in its frame: x across the slips, z (u) out along them.

const PUSHER_GLB := "res://assets/models/pusher_mid.glb"
const SCOW_GLB := "res://assets/models/barge_construction_mid.glb"
const TOW_GAP := 20.38          # the scow's origin ahead of the pusher's (as scenes/pusher_gravel_tow.tscn)
const OFFSHORE := 420.0         # how far out along the slip she comes from and goes back to
const WORK_U := 90.0            # where the scow lies while the crew works

var terminal: Terminal
var _tow := Node3D.new()
var _bob := 0.0


static func available() -> bool:
	return ResourceLoader.exists(PUSHER_GLB) and ResourceLoader.exists(SCOW_GLB)


func setup(t: Terminal) -> void:
	terminal = t
	name = "SlipRefitCrew"
	add_child(_tow)
	# Both are painted in vertex colours, which the shared material shows as modelled.
	var mb := MeshBuilder.new()
	Models._append_part(mb, ModelParts.baked(PUSHER_GLB), Transform3D.IDENTITY)
	Models._append_part(mb, ModelParts.baked(SCOW_GLB), Transform3D(Basis.IDENTITY, Vector3(0, 0, TOW_GAP)))
	var mesh := MeshInstance3D.new()
	mesh.mesh = mb.commit()
	_tow.add_child(mesh)
	visible = false


func _process(delta: float) -> void:
	var stage := terminal.refit_stage
	var on := stage in [Terminal.RefitStage.ARRIVING, Terminal.RefitStage.WORKING, Terminal.RefitStage.LEAVING]
	visible = on
	if not on:
		return
	var t := terminal.refit_progress()
	var eased := smoothstep(0.0, 1.0, t)
	var work := WORK_U + TOW_GAP   # the pusher's u, the scow ahead of her towards the shore
	var u := work
	match stage:
		Terminal.RefitStage.ARRIVING:
			u = lerpf(OFFSHORE, work, eased)
		Terminal.RefitStage.LEAVING:
			u = lerpf(work, OFFSHORE, eased)
	_bob += delta
	var v := terminal.island.slip_offset(terminal.refit_slip)
	# Heading in towards the shore (-u) the whole time: she backs out to leave.
	_tow.transform = Transform3D(Basis(Vector3.UP, PI), Vector3(v, sin(_bob * 1.1) * 0.12, u))
