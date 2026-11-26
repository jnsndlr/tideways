class_name TreeLod
extends RefCounted
## Selects visible tree detail levels, shadow casters and dithered distance transitions.

# Past this distance (m, to a tile's centre) a forest tile draws the broadleaves'
# stand-ins: as far out as Jon's pines' last step, where a tree is a few pixels, so the
# swap doesn't show as the camera pans (the full ones out to here cost ~0.5 ms).
const TREE_LOD_DIST := 1000.0

# Spruces (the heaviest trees) also have a middle version, drawn from TREE_NEAR_DIST to
# TREE_MID_DIST, and their stand-ins (which keep their stepped tiers) take over sooner.
const TREE_NEAR_DIST := 90.0

const TREE_MID_DIST := 270.0

## How much each of Jon's pines' levels (full, middle, far, card) is brightened to
## read as the full model does (measured with tools/lod_shots.gd).
const MPINE_GAIN := [
	Vector3.ONE, Vector3(1.16, 1.12, 1.03), Vector3(1.72, 1.5, 1.12), Vector3(3.7, 2.7, 2.1)
]

## The same for the broadleaf card.
const BROAD_CARD_GAIN := Vector3(0.62, 0.76, 1.2)

## Where the 300-triangle pine hands over to its impostor (m). `--impostor=M`.
static var impostor_dist: float = (
	(func() -> float:
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--impostor="):
				return a.substr(11).to_float()
		return 500.0)
	. call()
)

# Jon's pines are the full model to mpine_near_dist, a decimated one to mpine_mid_dist and
# a coarser one past it: modelled all over the map (the card sprite, tree_card.gdshader,
# only stands in on the Backdrop's banks). All cards with `--sprite-trees`.
# (and past mpine_far_dist, where it's a few pixels, the stacked cones). Tune with
# `--mpine=near,mid,far`.
static var mpine_near_dist := 150.0

static var mpine_mid_dist := 400.0

static var mpine_far_dist := 1000.0

static var _mpine_args := func():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mpine="):
			var d := a.substr(8).split_floats(",")
			mpine_near_dist = d[0]
			mpine_mid_dist = d[1]
			mpine_far_dist = d[2]
	return true

static var sprite_trees := "--sprite-trees" in OS.get_cmdline_user_args()

# Past this the broadleaves are drawn as the broadleaf card. `--broad-card=M`.
static var broad_card_dist: float = (
	(func() -> float:
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--broad-card="):
				return a.substr(13).to_float()
		return TREE_LOD_DIST)
	. call()
)

## Trees dither from one level of detail into the next over this many metres, centred
## on each swap (lod_dither.gdshaderinc), rather than popping. `--lod-fade=M` (0 = hard swaps).
static var lod_fade: float = (
	(func() -> float:
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--lod-fade="):
				return a.substr(11).to_float()
		return 30.0)
	. call()
)

static var _lod_mats := {}


## The mesh that casts a variant's shadow (its cheapest modelled level).
static func shadow_mesh(variant: Array) -> Mesh:
	return variant[1] if variant[1] != null else variant[0]


## The levels a variant is drawn at, as [mesh, from (m), to (m, 0 = no limit), and
## optionally the colour gain that matches it to the first].
static func lod_levels(variant: Array) -> Array:
	var near: Mesh = variant[0]
	var far: Mesh = variant[1]
	var mid: Mesh = variant[2]
	var card: Mesh = variant[3] if variant.size() > 3 else null
	if card != null and sprite_trees:
		return [[card, 0.0, 0.0]]
	if near.has_meta("impostor_base"):
		# The 300-triangle pine: its impostor lit as the model is, so no colour gain.
		return (
			[[near, 0.0, impostor_dist], [card, impostor_dist, 0.0]]
			if card != null
			else [[near, 0.0, 0.0]]
		)
	if card != null and variant[4] == null:
		# A broadleaf: modelled out to the card.
		if "--cone-trees" in OS.get_cmdline_user_args():
			return [[near, 0.0, TREE_LOD_DIST], [far, TREE_LOD_DIST, 0.0]]
		return [[near, 0.0, broad_card_dist], [card, broad_card_dist, 0.0, BROAD_CARD_GAIN]]
	if card != null:
		_mpine_args.call()
		return [
			[near, 0.0, mpine_near_dist],
			[mid, mpine_near_dist, mpine_mid_dist, MPINE_GAIN[1]],
			[variant[4], mpine_mid_dist, mpine_far_dist, MPINE_GAIN[2]],
			(
				[far, mpine_far_dist, 0.0]
				if "--cone-trees" in OS.get_cmdline_user_args()
				else [card, mpine_far_dist, 0.0, MPINE_GAIN[3]]
			)
		]
	if far == null:
		return [[near, 0.0, 0.0]]
	if mid == null:
		return [[near, 0.0, TREE_LOD_DIST], [far, TREE_LOD_DIST, 0.0]]
	return [
		[near, 0.0, TREE_NEAR_DIST], [mid, TREE_NEAR_DIST, TREE_MID_DIST], [far, TREE_MID_DIST, 0.0]
	]


## Shows `mmi` (a tile of trees drawn with `mesh`, one level of lod_levels) from
## `begin` to `end` (m, 0 = no limit). Each tree is placed by its own distance in the
## shader, while the tile's visibility range is by its middle: the range is widened by
## `slack` (as far as a tree can stand from the middle) and the fade, and the shader
## drops the trees outside.
static func dither_lod(
	mmi: GeometryInstance3D, mesh: Mesh, begin: float, end: float, slack: float, gain := Vector3.ONE
) -> void:
	if begin <= 0.0 and end <= 0.0 and gain == Vector3.ONE:
		mmi.visibility_range_begin = begin
		mmi.visibility_range_end = end
		return
	var mat: ShaderMaterial
	if mesh is QuadMesh:
		# A card: the last level, and the only one its material is drawn at.
		mat = (mesh as QuadMesh).material
	else:
		var key := [begin, end, gain]
		if not _lod_mats.has(key):
			var m := ShaderMaterial.new()
			m.shader = load("res://shaders/tree_lod.gdshader")
			_lod_mats[key] = m
		mat = _lod_mats[key]
		mmi.material_override = mat
	mat.set_shader_parameter("lod_begin", begin)
	mat.set_shader_parameter("lod_end", end)
	mat.set_shader_parameter("lod_fade", maxf(lod_fade, 0.0))
	mat.set_shader_parameter("lod_gain", gain)
	var pad := maxf(lod_fade, 0.0) * 0.5 + slack
	mmi.visibility_range_begin = maxf(begin - pad, 0.0) if begin > 0.0 else 0.0
	mmi.visibility_range_end = end + pad if end > 0.0 else 0.0
