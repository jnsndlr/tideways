class_name SlipRampView
extends Node3D
## Moving span, apron, counterweights, hoist cables and rams in the slip frame.

const RAISED := 1.5                     # height of the raised span tip above the car deck
const APRON_UP := deg_to_rad(18.0)
const LIFT_Z := 25.0
const LUG := Vector2(9.0, -0.5)        # cable lugs on the lifting beam (x, y in the span's frame)
const LUG_TOP := 0.75                   # the cable's socket above the lug
const TOWER_X := 9.6
const SHEAVE_Y := 14.6
const SHEAVE_R := 0.6
const RAM_X := 5.9
const RAM_A := Vector2(0.5, 23.5)       # ram cylinder's eye on the span (y, z)
const RAM_B := Vector2(0.5, 1.2)        # rod's eye on the apron (y, z)
const CW_TOP_DOWN := 10.6  # height of the counterweights' eyes with the span down

var _ramp: SlipRamp
var _span: Node3D
var _apron: Node3D
var _weights: Array[Node3D] = []
var _span_cables: Array[Node3D] = []
var _weight_cables: Array[Node3D] = []
var _bodies: Array[Node3D] = []
var _rods: Array[Node3D] = []
var _lug_y_down: float


func _init(ramp: SlipRamp) -> void:
	name = "SlipRampView"
	_ramp = ramp
	_span = _part("span", self)
	_span.position = Vector3(0.0, Layout.LOT_Y, Layout.RAMP_HINGE_U)
	_apron = _part("apron", _span)
	_apron.position = Vector3(0.0, 0.0, SlipRamp.SPAN_L)
	for s: float in [-1.0, 1.0]:
		_weights.append(_part("counterweight", self))
		_span_cables.append(_part("cable", self))
		_weight_cables.append(_part("cable", self))
		var body := _part("rambody", _span)
		body.position = Vector3(s * RAM_X, RAM_A.x, RAM_A.y)
		_bodies.append(body)
		var rod := _part("ramrod", _apron)
		rod.position = Vector3(s * RAM_X, RAM_B.x, RAM_B.y)
		_rods.append(rod)
	_lug_y_down = Layout.LOT_Y + SlipRamp.LAND * LIFT_Z / SlipRamp.SPAN_L + LUG.y + LUG_TOP


func _enter_tree() -> void:
	_ramp.pose_changed.connect(_set_pose)
	_set_pose(_ramp.span_fraction, _ramp.apron_fraction)


func _exit_tree() -> void:
	_ramp.pose_changed.disconnect(_set_pose)


func _part(part: String, parent: Node3D) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = Models.slip_mesh(part)
	parent.add_child(mi)
	return mi


func _set_pose(span_fraction: float, apron_fraction: float) -> void:
	var tilt := asin(lerpf(SlipRamp.LAND, RAISED, smoothstep(0.0, 1.0, span_fraction)) / SlipRamp.SPAN_L)
	_span.rotation.x = -tilt
	# The apron's angle is to the horizontal, whatever the span's.
	_apron.rotation.x = tilt + lerpf(SlipRamp.LAND_DIP, -APRON_UP, smoothstep(0.0, 1.0, apron_fraction))
	for i in 2:
		var s := -1.0 if i == 0 else 1.0
		# The hoist cable from the sheave down to the lug, and the counterweight on the
		# other side of the sheave taking up what the span lets out.
		var lug := _span.transform * Vector3(s * LUG.x, LUG.y + LUG_TOP, LIFT_Z)
		_hang(_span_cables[i], Vector3(s * (TOWER_X - SHEAVE_R), SHEAVE_Y, lug.z), lug)
		var cw := Vector3(s * (TOWER_X + SHEAVE_R), CW_TOP_DOWN - (lug.y - _lug_y_down), lug.z)
		_weights[i].position = cw
		_hang(_weight_cables[i], Vector3(cw.x, SHEAVE_Y, cw.z), cw)
		# The ram between the span and the apron: the cylinder aims at the rod's eye,
		# the rod back at the cylinder's.
		var a := _bodies[i].position
		var b := _apron.transform * _rods[i].position
		_bodies[i].basis = Basis.looking_at(b - a, Vector3.UP, true)
		_rods[i].basis = Basis.looking_at(_apron.transform.affine_inverse() * a - _rods[i].position, Vector3.UP, true)


## Stretches a cable (1 m down -Y from its origin) from `top` down to `bottom`.
static func _hang(cable: Node3D, top: Vector3, bottom: Vector3) -> void:
	var d := top - bottom
	var x := Vector3.RIGHT
	var z := x.cross(d).normalized()
	cable.transform = Transform3D(Basis(x, d, z), top)
