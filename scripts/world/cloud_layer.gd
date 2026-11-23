class_name CloudLayer
extends Node3D
## Drifting cloud deck (hidden from the minimap). Coverage and drift come from the
## simulation's Weather and wind and are published as shader globals every frame,
## which the land and water shaders sample to draw matching cloud shadows.
##
## The deck sits high, just under the camera at full zoom-out, so the play view
## looks down through clear air and only the widest views look over the cloud tops.

const ALTITUDE := 2700.0 # keep in sync with CLOUD_ALTITUDE in clouds.gdshaderinc
## Near the map, puffs wrap round a square this wide, centred on the map. It's wider
## than the ring's fade, so the wrap is never seen.
const TILE := 10400.0
const PUFF_SPACING := 130.0
## Out over the mainland, a sparser ring of puffs twice the size carries the cover
## on toward the horizon, where the sky shader's distant clouds (sky.gdshader) take over.
const FAR_TILE := 28000.0
const FAR_SPACING := 260.0
## Wide, so the switch to the bigger outer puffs never reads as a line.
const RING_FADE := Vector2(3000.0, 4900.0)
const FAR_FADE := Vector2(10500.0, 13500.0) # keep in sync with backdrop.gdshader, tree_card.gdshader
const VISUAL_LAYER := 2
var visual_mat: ShaderMaterial
var far_mat: ShaderMaterial
var weather: Weather
var shown := true


## Hides the deck and its shadows on the ground and water (the island editor's clear view).
func set_shown(on: bool) -> void:
	shown = on
	visible = on
	_publish()


func setup(w: Weather, wind_from: Vector2, wind_speed: float) -> void:
	name = "Clouds"
	weather = w
	visual_mat = ShaderMaterial.new()
	visual_mat.shader = load("res://shaders/clouds.gdshader")

	# Wind is named for where it blows from; clouds drift the other way (-Z is north).
	var drift := -wind_from * wind_speed * 1.2
	RenderingServer.global_shader_parameter_set("cloud_wind", drift)

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
	far_mat = visual_mat.duplicate()
	visual_mat.set_shader_parameter("fade_out", RING_FADE)
	far_mat.set_shader_parameter("size_scale", 2.0)
	far_mat.set_shader_parameter("fade_in", RING_FADE)
	far_mat.set_shader_parameter("fade_out", FAR_FADE)
	# Both rings share a centre, so the depth sort alone can't order them and they
	# swapped as the camera moved (the outer band flickered). The outer ring always
	# draws first, under the near puffs.
	_build_puffs("FarPuffs", far_mat, FAR_TILE, FAR_SPACING, 9277, 0.0)
	_build_puffs("Puffs", visual_mat, TILE, PUFF_SPACING, 7151, 100.0)
	_publish()


func _process(_delta: float) -> void:
	# Every cloud shader drifts on this clock rather than TIME: the sky can't use
	# TIME without re-rendering its radiance every frame, and the deck, its shadows
	# and the sky's continuation of it have to agree.
	RenderingServer.global_shader_parameter_set("cloud_time", Time.get_ticks_msec() * 0.001)
	_publish()


## Pushes the weather's current sky to the shaders. Weather fronts in
## clouds.gdshaderinc swing coverage by about +/-0.15 across the map, so every kind
## of day still has both clear patches and banks.
func _publish() -> void:
	if weather == null:
		return
	RenderingServer.global_shader_parameter_set("cloud_coverage", weather.coverage if shown else 0.0)
	RenderingServer.global_shader_parameter_set("cloud_shadow_strength", weather.shadow_strength())
	RenderingServer.global_shader_parameter_set("horizon_clouds", weather.horizon)
	RenderingServer.global_shader_parameter_set("cloud_storm", weather.storm)
	# Overcast skies leave the roads damp; storms soak them.
	RenderingServer.global_shader_parameter_set("road_wet", smoothstep(0.05, 0.8, weather.storm) if shown else 0.0)
	visual_mat.set_shader_parameter("opacity", weather.cloud_opacity())
	far_mat.set_shader_parameter("opacity", weather.cloud_opacity())


## Thousands of soft, camera-facing puffs on a jittered grid. They drift with the wind
## (wrapping round a tile larger than the visible deck) and each sizes itself from the
## shared cloud field where it is, so heaps form, grow and dissolve where the field
## (and so the ground shadows) say they should. One MultiMesh, one draw per ring.
func _build_puffs(label: String, mat: ShaderMaterial, tile: float, spacing: float, seed: int, sort_offset: float) -> void:
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
	visual.sorting_offset = sort_offset
	visual.layers = 1 << (VISUAL_LAYER - 1)
	add_child(visual)
