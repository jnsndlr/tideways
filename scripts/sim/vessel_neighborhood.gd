class_name VesselNeighborhood
extends RefCounted
## Broad phase for helm queries. Membership follows local movement immediately,
## so a later helm sees earlier vessels' moves within the same simulation tick.
const CELL := 420.0

var _cells := {}
var _by_order := {}
var _outside := {}
var _next_order := 0
var _max_reach := 0.0
var _parent: Node3D


func _init(parent: Node3D) -> void:
	_parent = parent


func add(v: Vessel) -> void:
	v.neighborhood_order = _next_order
	_by_order[_next_order] = v
	_next_order += 1
	v.neighborhood = self
	include_reach(v)
	v.set_notify_local_transform(true)
	relocate(v)


func include_reach(v: Vessel) -> void:
	_max_reach = maxf(_max_reach, v.half_seg + v.hull_radius)


func remove(v: Vessel) -> void:
	v.set_notify_local_transform(false)
	v.neighborhood = null
	_unbucket(v)
	_outside.erase(v.neighborhood_order)
	_by_order.erase(v.neighborhood_order)


func _unbucket(v: Vessel) -> void:
	if v.neighborhood_bounds.size == Vector2.ZERO:
		return
	var cell := Vector2i((v.neighborhood_bounds.position / CELL).round())
	var bucket: Array = _cells[cell]
	bucket.erase(v.neighborhood_order)
	if bucket.is_empty():
		_cells.erase(cell)
	v.neighborhood_bounds = Rect2()


func relocate(v: Vessel) -> void:
	if v.get_parent_node_3d() != _parent or v.top_level or not v.is_inside_tree():
		_unbucket(v)
		_outside[v.neighborhood_order] = true
		return
	var pos := v.position
	var p := Vector2(pos.x, pos.z)
	if v.neighborhood_bounds.has_point(p):
		return
	_unbucket(v)
	_outside.erase(v.neighborhood_order)
	var cell := Vector2i((p / CELL).floor())
	if not _cells.has(cell):
		_cells[cell] = []
	_cells[cell].append(v.neighborhood_order)
	v.neighborhood_bounds = Rect2(Vector2(cell) * CELL, Vector2.ONE * CELL)


func candidates(vessels: Array[Vessel], center: Vector2, radius: float) -> Array[Vessel]:
	if (
		_cells.size() <= 1
		or not is_instance_valid(_parent)
		or _parent.global_transform.basis != Basis.IDENTITY
	):
		return vessels
	var origin := _parent.global_position
	var p := center - Vector2(origin.x, origin.z)
	var reach := Vector2.ONE * (radius + _max_reach)
	var lo := Vector2i(((p - reach) / CELL).floor())
	var hi := Vector2i(((p + reach) / CELL).floor())
	var ids := _outside.keys()
	for x in range(lo.x, hi.x + 1):
		for y in range(lo.y, hi.y + 1):
			var bucket: Variant = _cells.get(Vector2i(x, y))
			if bucket != null:
				ids.append_array(bucket)
	if ids.size() * 2 >= vessels.size():
		return vessels
	ids.sort()
	var nearby: Array[Vessel] = []
	for id: int in ids:
		nearby.append(_by_order[id])
	return nearby
