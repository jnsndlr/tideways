class_name DirectionalShadowGrid
extends RefCounted
## Godot snaps directional cascades in world space. Rotating the sun can move a
## distant terminal through several texels even with a stationary camera. Align
## the focus cascade to a fixed local landmark without moving the sunlight ray.

var atlas_size := int(
	ProjectSettings.get_setting_with_override(
		"rendering/lights_and_shadows/directional_shadow/size"
	)
)
var _anchor := Vector3.ZERO
var _texel := 0.0
var _reach := 0.0
var _near := 0.0


func focus(sun: DirectionalLight3D, rig: CameraRig, terminals: Dictionary) -> void:
	_texel = 0
	var camera := rig.camera
	if (
		camera == null
		or camera.projection != Camera3D.PROJECTION_PERSPECTIVE
		or sun.directional_shadow_mode != DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
		or sun.directional_shadow_blend_splits
		or sun.light_angular_distance != 0.0
	):
		return
	# A fixed landmark keeps a pan from scrolling the sampling grid with the
	# camera. Leave open water and views without a nearby terminal alone.
	var nearest: Terminal
	var limit := rig.distance * rig.distance
	for terminal: Terminal in terminals.values():
		var squared := terminal.global_position.distance_squared_to(rig.global_position)
		if squared < limit:
			nearest = terminal
			limit = squared
	if nearest == null:
		return
	_anchor = nearest.global_position
	_reach = minf(sun.directional_shadow_max_distance, camera.far)
	_near = camera.near
	var depth := (rig.global_position - camera.global_position).dot(-camera.global_basis.z)
	if depth <= _near or depth >= _reach or atlas_size <= 4:
		return
	var start := _near
	var end := _reach
	for split: float in [
		sun.directional_shadow_split_1,
		sun.directional_shadow_split_2,
		sun.directional_shadow_split_3,
		1.0
	]:
		end = lerpf(_near, _reach, split)
		if depth <= end:
			break
		start = end
	var projection := camera.get_camera_projection()
	# Radius of this frustum slice's bounding sphere. Four cascades occupy
	# quarter tiles, with a one-texel guard on either side in the renderer.
	var radius := Vector3(end / projection.x.x, end / projection.y.y, (end - start) * 0.5).length()
	_texel = 2.0 * radius / (atlas_size * 0.5 - 2.0)


func apply(sun: DirectionalLight3D) -> void:
	if _texel <= 0:
		return
	var in_light := sun.global_basis.transposed() * _anchor
	var projected := Vector2(in_light.x, in_light.y)
	var grid := projected.snapped(Vector2.ONE * _texel)
	if grid.length_squared() <= _texel * _texel:
		return
	# Use the closest whole texel. Slightly rotate the grid around the sunlight
	# ray and scale its footprint. Both sides of a rounding boundary still put
	# the terminal on a whole texel. Near the light axis keep the unmodified grid.
	var scale := projected.length() / grid.length()
	var roll := grid.angle_to(projected)
	if absf(scale - 1.0) > 0.001 or absf(roll) > deg_to_rad(0.05):
		return
	sun.global_basis = sun.global_basis * Basis(Vector3.BACK, roll)
	sun.directional_shadow_max_distance = _near + (_reach - _near) * scale
