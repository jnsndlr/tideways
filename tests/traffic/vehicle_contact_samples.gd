extends RefCounted
## Consecutive proximity or mesh observations for individual vehicles.
## Retain IDs for two samples so the diagnostic never keeps retired vehicles alive.

const LASTING := 4

var observations := 0
var lasting_episodes := 0
var longest := 0
var _previous := {}
var _current := {}


func begin_sample() -> void:
	_previous = _current
	_current = {}


func record(a: int, b: int) -> int:
	var key := "%d/%d" % [mini(a, b), maxi(a, b)]
	var count := int(_previous.get(key, 0)) + 1
	_current[key] = count
	observations += 1
	longest = maxi(longest, count)
	if count == LASTING:
		lasting_episodes += 1
	return count


## Probe both directions so an edge from either model can cut the other's surface.
## A tractor and its articulated trailer are tested in their own current transforms.
static func surfaces_intersect(a: Vehicle, b: Vehicle) -> bool:
	for source: MeshInstance3D in a.find_children("*", "MeshInstance3D", true, false):
		if source.mesh == null or not source.is_visible_in_tree():
			continue
		for target: MeshInstance3D in b.find_children("*", "MeshInstance3D", true, false):
			if target.mesh == null or not target.is_visible_in_tree():
				continue
			var relative := target.global_transform.affine_inverse() * source.global_transform
			if not (relative * source.get_aabb()).intersects(target.get_aabb()):
				continue
			if _cuts_surface(source.mesh, relative, target.mesh):
				return true
			if _cuts_surface(target.mesh, relative.affine_inverse(), source.mesh):
				return true
	return false


static func _cuts_surface(source: Mesh, relative: Transform3D, target: Mesh) -> bool:
	var surface := target.generate_triangle_mesh()
	if surface == null:
		return false
	var faces := source.get_faces()
	for i in range(0, faces.size(), 3):
		var a := relative * faces[i]
		var b := relative * faces[i + 1]
		var c := relative * faces[i + 2]
		if (
			not surface.intersect_segment(a, b).is_empty()
			or not surface.intersect_segment(b, c).is_empty()
			or not surface.intersect_segment(c, a).is_empty()
		):
			return true
	return false
