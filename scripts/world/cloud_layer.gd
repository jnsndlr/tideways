class_name CloudLayer
extends Node3D
## Drifting cloud deck (hidden from the minimap). Coverage and drift come from the
## simulation's weather and wind and are published as shader globals, which the
## land and water shaders sample to draw matching cloud shadows.

const ALTITUDE := 510.0 # keep in sync with CLOUD_ALTITUDE in clouds.gdshaderinc
const SIZE := 21000.0
const VISUAL_LAYER := 2
const COVERAGE := {"Sunny": 0.18, "Light Breeze": 0.32, "Partly Cloudy": 0.48, "Overcast": 0.8}

var visual_mat: ShaderMaterial
var coverage := 0.45


## Hides the deck and its shadows on the ground and water (the island editor's clear view).
func set_shown(on: bool) -> void:
	visible = on
	RenderingServer.global_shader_parameter_set("cloud_coverage", coverage if on else 0.0)


func setup(weather: String, wind_from: Vector2, wind_speed: float) -> void:
	name = "Clouds"
	visual_mat = ShaderMaterial.new()
	visual_mat.shader = load("res://shaders/clouds.gdshader")

	# Wind is named for where it blows from; clouds drift the other way (-Z is north).
	var drift := -wind_from * wind_speed * 1.2
	coverage = COVERAGE.get(weather, 0.45)
	RenderingServer.global_shader_parameter_set("cloud_coverage", coverage)
	RenderingServer.global_shader_parameter_set("cloud_wind", drift)
	# Overcast skies diffuse the light, so their shadows are broad but soft.
	RenderingServer.global_shader_parameter_set("cloud_shadow_strength", 0.4 if weather == "Overcast" else 0.65)
	if weather == "Overcast":
		visual_mat.set_shader_parameter("opacity", 0.7)

	var plane := PlaneMesh.new()
	plane.size = Vector2(SIZE, SIZE)
	var visual := MeshInstance3D.new()
	visual.mesh = plane
	visual.material_override = visual_mat
	visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visual.layers = 1 << (VISUAL_LAYER - 1)
	visual.position.y = ALTITUDE
	add_child(visual)

