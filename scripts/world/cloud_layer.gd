class_name CloudLayer
extends Node3D
## Drifting cloud deck (hidden from the minimap). Coverage and drift come from the
## simulation's weather and wind and are published as shader globals, which the
## land and water shaders sample to draw matching cloud shadows.

const ALTITUDE := 510.0 # keep in sync with CLOUD_ALTITUDE in clouds.gdshaderinc
## Near the map, puffs wrap round a square this wide, centred on the map. It's wider
## than the ring's fade, so the wrap is never seen.
const TILE := 10400.0
const PUFF_SPACING := 130.0
## Out over the mainland, a sparser ring of puffs twice the size carries the cover
## on to the horizon (the backdrop's cumulus start at about 16.5 km).
const FAR_TILE := 28000.0
const FAR_SPACING := 260.0
const RING_FADE := Vector2(3800.0, 4800.0)
const FAR_FADE := Vector2(10500.0, 13500.0) # keep in sync with backdrop.gdshader, tree_card.gdshader
const VISUAL_LAYER := 2
## Base coverage per weather. Weather fronts in clouds.gdshaderinc swing it by about
## +/-0.15 across the map, so each kind of day still has both clear patches and banks.
const COVERAGE := {"Sunny": 0.24, "Light Breeze": 0.34, "Partly Cloudy": 0.44, "Overcast": 0.58}

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
		visual_mat.set_shader_parameter("opacity", 0.8)

	var noise := FastNoiseLite.new()
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 0.02
	noise.fractal_octaves = 4
	var tex := NoiseTexture2D.new()
	tex.width = 256
	tex.height = 256
	tex.seamless = true
	tex.noise = noise
	visual_mat.set_shader_parameter("puff_noise", tex)
	var far_mat: ShaderMaterial = visual_mat.duplicate()
	visual_mat.set_shader_parameter("fade_out", RING_FADE)
	far_mat.set_shader_parameter("size_scale", 2.0)
	far_mat.set_shader_parameter("fade_in", RING_FADE)
	far_mat.set_shader_parameter("fade_out", FAR_FADE)
	_build_puffs("Puffs", visual_mat, TILE, PUFF_SPACING, 7151)
	_build_puffs("FarPuffs", far_mat, FAR_TILE, FAR_SPACING, 9277)


## Thousands of soft, camera-facing puffs on a jittered grid. They drift with the wind
## (wrapping round a tile larger than the visible deck) and each sizes itself from the
## shared cloud field where it is, so heaps form, grow and dissolve where the field
## (and so the ground shadows) say they should. One MultiMesh, one draw per ring.
func _build_puffs(label: String, mat: ShaderMaterial, tile: float, spacing: float, seed: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var half := tile * 0.5
	var cells := int(tile / spacing)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	mm.mesh = quad
	mm.instance_count = cells * cells
	var i := 0
	for gz in cells:
		for gx in cells:
			var x := -half + (gx + rng.randf()) * spacing
			var z := -half + (gz + rng.randf()) * spacing
			mm.set_instance_transform(i, Transform3D(Basis(), Vector3(x, ALTITUDE, z)))
			# r: size, g: height jitter, b: texture offset, a: spare
			mm.set_instance_custom_data(i, Color(rng.randf(), rng.randf(), rng.randf(), rng.randf()))
			i += 1
	mm.custom_aabb = AABB(Vector3(-half - 1000.0, ALTITUDE - 500.0, -half - 1000.0), Vector3(tile + 2000.0, 1500.0, tile + 2000.0))

	mat.set_shader_parameter("tile", tile)

	var visual := MultiMeshInstance3D.new()
	visual.name = label
	visual.multimesh = mm
	visual.material_override = mat
	visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visual.layers = 1 << (VISUAL_LAYER - 1)
	add_child(visual)
