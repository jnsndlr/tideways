class_name Models
extends RefCounted
## Procedural low-poly meshes, cached so every instance shares geometry.

# The code-built models (and the Blender ones made to match them) were built for the
# game's first, toy scale; those not yet remade at real size are drawn this many
# times their built size.
const LEGACY_SCALE := 3.0

const GLASS := Color(0.16, 0.22, 0.27)
# Glass that lights up at night (lit_vc.gdshader reads the alpha): WINDOW_LIT always,
# WINDOW for some rooms and not others.
const WINDOW_LIT := Color(0.16, 0.22, 0.27, 0.0)
const WINDOW := Color(0.16, 0.22, 0.27, 0.5)
const WSF_GREEN := Color(0.07, 0.36, 0.25)
const WHITE := Color(0.94, 0.95, 0.94)
const HULL_DARK := Color(0.13, 0.14, 0.16)
const WOOD := Color(0.33, 0.26, 0.2)
const BRASS := Color(0.72, 0.55, 0.24)
const LAMP_DARK := Color(0.12, 0.12, 0.13)
const CAR_COLORS := [Color(0.75, 0.16, 0.14), Color(0.16, 0.32, 0.62), Color(0.92, 0.92, 0.9),
	Color(0.62, 0.64, 0.66), Color(0.12, 0.12, 0.14), Color(0.9, 0.72, 0.2), Color(0.2, 0.45, 0.3),
	Color(0.85, 0.4, 0.15), Color(0.2, 0.55, 0.6)]

# Glass of a lamp fixture (lit_vc.gdshader reads the alpha): glows in its own colour
# at night, with the first lights.
const LAMP_GLASS_ALPHA := 0.15
# night_lights level the fixtures' glass comes on at; their glows match it.
const LAMP_ON_AT := 0.05
# Flashing lamp glass: alpha (BLINK_ALPHA0 + q) / 255 flashes with phase q / BLINK_STEPS,
# every BLINK_PERIOD seconds (lit_vc.gdshader's lamp_blink_period). Its glow gets the
# same phase through GlowBuilder's blink.
const BLINK_ALPHA0 := 180
const BLINK_STEPS := 64
const BLINK_PERIOD := 4.0
# Porch lamps (where on the front wall, and how big), shared with WorldBuilder's glows.
const HOUSE_LAMP := Vector3(1.1, 1.45, 1.7)
const HOUSE_LAMP_SCALE := 0.7
const BLOCK_LAMP := Vector3(0.0, 2.35, 2.5)
const BLOCK_LAMP_SCALE := 0.9
# Ferry fixture scales the glows were tuned at (FerryClass places them).
const FERRY_LANTERN := 1.2
const FERRY_SIDELIGHT_SCALE := 1.3
# Sidelight lenses (lit_vc.gdshader reads the alpha): lit only at the end that's the
# bow on this crossing, set by the hull's nav_flip.
const NAV_GLASS_ALPHA := 0.3
const NAV_RED := Color(0.85, 0.1, 0.07, NAV_GLASS_ALPHA)
const NAV_GREEN := Color(0.1, 0.75, 0.3, NAV_GLASS_ALPHA)
# The sailboat's anchor light, on top of the mast.
const SAIL_MAST_TOP := Vector3(0, 4.3, 0.3)
const SAIL_LANTERN := 0.8
# Channel buoys' lanterns: height above the waterline and scale.
const BUOY_LAMP_Y := 4.95
const BUOY_LANTERN := 3.3

static var _vc_mat: ShaderMaterial
static var _rock_mat: ShaderMaterial
static var _hull_mat: ShaderMaterial
static var _cache := {}


static func rock_material() -> ShaderMaterial:
	if _rock_mat == null:
		_rock_mat = ShaderMaterial.new()
		_rock_mat.shader = load("res://shaders/rock.gdshader")
	return _rock_mat


static var _boulder_mat: ShaderMaterial


## The land boulders' (rock()): painted stone with a lit top edge.
static func boulder_material() -> ShaderMaterial:
	if _boulder_mat == null:
		_boulder_mat = ShaderMaterial.new()
		_boulder_mat.shader = load("res://shaders/boulder.gdshader")
	return _boulder_mat


static func vc_material() -> ShaderMaterial:
	if _vc_mat == null:
		_vc_mat = ShaderMaterial.new()
		_vc_mat.shader = load("res://shaders/lit_vc.gdshader")
	return _vc_mat


## The same for a vessel's or ferry's hull, as its material_override: this one takes
## the per-instance room_seed and nav_flip (which only hulls set; see lit_vc.gdshaderinc).
static func hull_material() -> ShaderMaterial:
	if _hull_mat == null:
		_hull_mat = ShaderMaterial.new()
		_hull_mat.shader = load("res://shaders/lit_vc_hull.gdshader")
	return _hull_mat


static func unshaded_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = true
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


static func _cached(key: String, build: Callable) -> ArrayMesh:
	if not _cache.has(key):
		_cache[key] = build.call()
	return _cache[key]


static func pine_tree() -> ArrayMesh:
	return _cached("pine", func():
		var mb := MeshBuilder.new()
		mb.cylinder(Vector3(0, -0.4, 0), 0.28, 0.2, 1.6, 5, Color(0.36, 0.25, 0.17))
		mb.cylinder(Vector3(0, 0.9, 0), 1.6, 0.0, 2.4, 6, Color(0.16, 0.34, 0.22), Color(-1, 0, 0), 0.3)
		mb.cylinder(Vector3(0, 2.2, 0), 1.25, 0.0, 2.1, 6, Color(0.25, 0.42, 0.2), Color(-1, 0, 0), 0.8)
		mb.cylinder(Vector3(0, 3.4, 0), 0.85, 0.0, 1.8, 6, Color(0.34, 0.5, 0.19), Color(-1, 0, 0), 0.1)
		return mb.commit())


static func round_tree() -> ArrayMesh:
	return _cached("round", func():
		var mb := MeshBuilder.new()
		mb.cylinder(Vector3(0, -0.4, 0), 0.26, 0.2, 1.8, 5, Color(0.38, 0.27, 0.18))
		var c := Color(0.4, 0.53, 0.19)
		mb.cylinder(Vector3(0, 1.2, 0), 0.9, 1.5, 0.9, 7, c)
		mb.cylinder(Vector3(0, 2.1, 0), 1.5, 0.6, 1.2, 7, c.lightened(0.08))
		return mb.commit())


## Trees use the faceted ones modelled in Blender (TREES_GLB, built by art/trees.py into
## art/trees.blend): several pines and broadleaves, each with a cheap stand-in
## ("<name>_lod") for far off. The two above are the fallback: with `--classic-trees`,
## or if the model is missing.
const TREES_GLB := "res://assets/models/trees.glb"
static var mid_trees := not "--classic-trees" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(TREES_GLB)
const SPRUCE_VARIANTS := ["spruce", "spruce_open", "spruce_lean", "spruce_broad", "spruce_tall", "spruce_young"]
## Jon's pine (matching the Backdrop's card sprite), baked by art/pines_meshy.py; the
## spruces above with `--old-pines`.
const MPINES_GLB := "res://assets/models/pines_meshy.glb"
const MPINE_VARIANTS := ["mpine", "mpine_tall", "mpine_broad", "mpine_young"]
## The 300-triangle pine (art/pine_tree.py's stand-in): one model drawn out to
## IMPOSTOR_DIST and as its impostor (tree_impostor.gdshader, baked by
## tools/bake_impostor.gd) past it, its variants that model rescaled as Jon's pines'
## are. Jon's pines above with `--meshy-pines`.
const LPINE_GLB := "res://assets/models/pine_tree_lod.glb"
const LPINE_SCALE := {"lpine": Vector3.ONE, "lpine_tall": Vector3(0.98, 1.16, 0.98),
	"lpine_broad": Vector3(0.93, 0.81, 0.93), "lpine_young": Vector3(0.53, 0.53, 0.53)}
const IMPOSTOR_DIR := "res://assets/textures/impostors/"
static var PINE_VARIANTS: Array = (func() -> Array:
	var args := OS.get_cmdline_user_args()
	if "--old-pines" in args:
		return SPRUCE_VARIANTS
	if ResourceLoader.exists(LPINE_GLB) and not "--meshy-pines" in args:
		return LPINE_SCALE.keys()
	return MPINE_VARIANTS if ResourceLoader.exists(MPINES_GLB) else SPRUCE_VARIANTS).call()
## Where the 300-triangle pine hands over to its impostor (m). `--impostor=M`.
static var IMPOSTOR_DIST: float = (func() -> float:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--impostor="):
			return a.substr(11).to_float()
	return 500.0).call()
const BROAD_VARIANTS := ["oak", "poplar", "spreading", "leaning", "round", "birches"]
# Past this distance (m, to a tile's centre) a forest tile draws the broadleaves'
# stand-ins: as far out as Jon's pines' last step, where a tree is a few pixels, so the
# swap doesn't show as the camera pans (the full ones out to here cost ~0.5 ms).
const TREE_LOD_DIST := 1000.0
# Spruces (the heaviest trees) also have a middle version, drawn from TREE_NEAR_DIST to
# TREE_MID_DIST, and their stand-ins (which keep their stepped tiers) take over sooner.
const TREE_NEAR_DIST := 90.0
const TREE_MID_DIST := 270.0
# Jon's pines are the full model to MPINE_NEAR_DIST, a decimated one to MPINE_MID_DIST and
# a coarser one past it: modelled all over the map (the card sprite, tree_card.gdshader,
# only stands in on the Backdrop's banks). All cards with `--sprite-trees`.
# (and past MPINE_FAR_DIST, where it's a few pixels, the stacked cones). Tune with
# `--mpine=near,mid,far`.
static var MPINE_NEAR_DIST := 150.0
static var MPINE_MID_DIST := 400.0
static var MPINE_FAR_DIST := 1000.0
static var _mpine_args := func():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mpine="):
			var d := a.substr(8).split_floats(",")
			MPINE_NEAR_DIST = d[0]; MPINE_MID_DIST = d[1]; MPINE_FAR_DIST = d[2]
	return true
static var sprite_trees := "--sprite-trees" in OS.get_cmdline_user_args()
const CARD_SHADER := "res://shaders/tree_card.gdshader"
const CARD_SPRITE := "res://assets/textures/pine_card.png"
const BROAD_CARD_SPRITE := "res://assets/textures/broad_card.png"
static var _card_mat: ShaderMaterial
static var _broad_card_mat: ShaderMaterial
# Past this the broadleaves are drawn as the broadleaf card. `--broad-card=M`.
static var BROAD_CARD_DIST: float = (func() -> float:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--broad-card="):
			return a.substr(13).to_float()
	return TREE_LOD_DIST).call()


## The pine (or broadleaf) variants as [near mesh, far mesh or null, middle mesh or null,
## card or null, farthest mesh or null]. Jon's pines' and the broadleaves' "far"
## (stand-ins) only cast their shadows (or with `--cone-trees`, are drawn in place of the
## card); "farthest" is what Jon's pines draw from MPINE_MID_DIST.
static func tree_variants(broadleaf: bool) -> Array:
	if not mid_trees:
		return [[round_tree() if broadleaf else pine_tree(), null, null, null]]
	var out := []
	for n: String in BROAD_VARIANTS if broadleaf else PINE_VARIANTS:
		if n.begins_with("lpine"):
			# One model all the way out, casting its own shadow, then its impostor.
			var m := _tree_part(n)
			out.append([m, m, null, impostor_card(n, m), null])
			continue
		var near := _tree_part(n)
		var lod := _tree_part(n + "_lod")
		if (broadleaf or n.begins_with("mpine")) and not "--raw-stand-ins" in OS.get_cmdline_user_args():
			lod = _fit_stand_in(n, lod, near)
		out.append([near, lod, _tree_part(n + "_mid") if n.begins_with("spruce") or n.begins_with("mpine") else null,
			tree_card(n, near) if n.begins_with("mpine") or broadleaf else null,
			_tree_part(n + "_far") if n.begins_with("mpine") else null])
	return out


## How wide a stand-in is drawn against its full tree's crown: being solid, it reads
## bigger than an airy crown of the same outline (Jon's pines', the broadleaves' clumps).
const STAND_IN_WIDTH := {"mpine": 0.8, "broad": 0.85}


## `lod` moved and scaled so it stands where `near` does, so zooming across the swap
## doesn't grow or shift the trees: its foliage (green vertices) fitted to `near`'s
## crown, STAND_IN_WIDTH as wide, the trunk below stretched to meet it.
static func _fit_stand_in(n: String, lod: ArrayMesh, near: ArrayMesh) -> ArrayMesh:
	return _cached("tree_fit_" + n, func():
		var a := _foliage_box(lod)
		var b := _foliage_box(near)
		var k: float = STAND_IN_WIDTH["mpine" if n.begins_with("mpine") else "broad"]
		var foot := near.get_aabb().position.y
		var sx := b.size.x / a.size.x * k
		var sz := b.size.z / a.size.z * k
		var ca := a.get_center()
		var cb := b.get_center()
		var out := ArrayMesh.new()
		for i in lod.get_surface_count():
			var arr := lod.surface_get_arrays(i)
			var vs: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var cs: PackedColorArray = arr[Mesh.ARRAY_COLOR] if arr[Mesh.ARRAY_COLOR] != null else PackedColorArray()
			for j in vs.size():
				var v := vs[j]
				var y: float
				if v.y >= a.position.y:
					y = b.position.y + (v.y - a.position.y) * b.size.y / a.size.y
				else:
					y = foot + (v.y - foot) * (b.position.y - foot) / maxf(a.position.y - foot, 0.01)
				if cs.is_empty() or _leafy(cs[j]):
					vs[j] = Vector3(cb.x + (v.x - ca.x) * sx, y, cb.z + (v.z - ca.z) * sz)
				else:
					vs[j] = Vector3(v.x, y, v.z)
			arr[Mesh.ARRAY_VERTEX] = vs
			out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
			out.surface_set_material(i, lod.surface_get_material(i))
		return out)


static func _leafy(c: Color) -> bool:
	return c.g > c.r


## The box round a tree's green (foliage) vertices.
static func _foliage_box(m: ArrayMesh) -> AABB:
	var box := AABB()
	var first := true
	for i in m.get_surface_count():
		var arr := m.surface_get_arrays(i)
		var vs: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var cs = arr[Mesh.ARRAY_COLOR]
		for j in vs.size():
			if cs != null and not _leafy(cs[j]):
				continue
			if first:
				box = AABB(vs[j], Vector3.ZERO); first = false
			else:
				box = box.expand(vs[j])
	return box if not first else m.get_aabb()


## The material of every pine card (in the woods and the Backdrop's), or with
## `broadleaf` every broadleaf card; map_half is set once the terrain is known.
static func card_material(broadleaf := false) -> ShaderMaterial:
	if broadleaf:
		if _broad_card_mat == null:
			_broad_card_mat = ShaderMaterial.new()
			_broad_card_mat.shader = load(CARD_SHADER)
			_broad_card_mat.set_shader_parameter("sprite", load(BROAD_CARD_SPRITE))
			# Its greens are the broadleaves' own: no grading towards the pines'.
			_broad_card_mat.set_shader_parameter("grade", Color.WHITE)
			_broad_card_mat.set_shader_parameter("yellow_cap", 1.0)
			_broad_card_mat.set_shader_parameter("low_sun", CARD_LOW_SUN)
			_broad_card_mat.set_shader_parameter("low_sun_direct", CARD_LOW_SUN_DIRECT)
		return _broad_card_mat
	if _card_mat == null:
		_card_mat = ShaderMaterial.new()
		_card_mat.shader = load(CARD_SHADER)
		_card_mat.set_shader_parameter("sprite", load(CARD_SPRITE))
		_card_mat.set_shader_parameter("sprite_mean", _sprite_mean(CARD_SPRITE))
		_card_mat.set_shader_parameter("contrast", CARD_CONTRAST)
		_card_mat.set_shader_parameter("saturation", CARD_SATURATION)
		_card_mat.set_shader_parameter("yellow_cap", CARD_YELLOW_CAP)
		_card_mat.set_shader_parameter("low_sun", CARD_LOW_SUN)
		_card_mat.set_shader_parameter("low_sun_direct", CARD_LOW_SUN_DIRECT)
	return _card_mat


## The average colour of a sprite's opaque texels, linear (as the shader samples it).
static func _sprite_mean(path: String) -> Vector3:
	var img: Image = (load(path) as Texture2D).get_image()
	if img.is_compressed():
		img.decompress()
	var sum := Vector3.ZERO
	var n := 0
	for y in range(0, img.get_height(), 2):
		for x in range(0, img.get_width(), 2):
			var c := img.get_pixel(x, y)
			if c.a > 0.5:
				var l := c.srgb_to_linear()
				sum += Vector3(l.r, l.g, l.b)
				n += 1
	return sum / maxi(n, 1)


## A tree drawn as its card sprite, standing as tall as the modelled `near` one: a pine
## in the sprite's own 250 x 353 proportions, a broadleaf as wide as its crown.
## tree_card.gdshader turns it to the camera.
static var _cards := {}


static func tree_card(n: String, near: Mesh) -> Mesh:
	if not _cards.has(n):
		var box := near.get_aabb()
		var q := QuadMesh.new()
		var broadleaf := not n.begins_with("mpine")
		q.size = Vector2(maxf(box.size.x, box.size.z) if broadleaf else box.size.y * 0.71, box.size.y)
		q.center_offset = Vector3(0.0, box.position.y + box.size.y * 0.5, 0.0)
		# It faces the camera whichever way the tree is turned.
		q.custom_aabb = AABB(Vector3(-q.size.x, box.position.y, -q.size.x), Vector3(q.size.x * 2.0, box.size.y, q.size.x * 2.0))
		q.material = card_material(broadleaf)
		_cards[n] = q
	return _cards[n]


## The impostor's layout (tools/bake_impostor.gd, tree_impostor.gdshader): frames of
## IMPOSTOR_FRAME px, a column per IMPOSTOR_AZIMUTHS headings round the tree, a row per
## IMPOSTOR_ELEVATIONS heights above it, IMPOSTOR_EL_STEP degrees apart from level.
const IMPOSTOR_SHADER := "res://shaders/tree_impostor.gdshader"
const IMPOSTOR_FRAME := 128
const IMPOSTOR_AZIMUTHS := 16
const IMPOSTOR_ELEVATIONS := 4
const IMPOSTOR_EL_STEP := 20.0


## The model the impostor is baked from and the sphere it's framed in: [mesh, centre, radius].
static func impostor_base() -> Array:
	var m := _tree_part("lpine")
	var box := m.get_aabb()
	return [m, box.get_center(), box.size.length() * 0.5]


## Variant `n` of the 300-triangle pine as its impostor card, or null before it's baked.
static func impostor_card(n: String, _near: Mesh) -> Mesh:
	var albedo := IMPOSTOR_DIR + "lpine_albedo.res"
	var normal := IMPOSTOR_DIR + "lpine_normal.res"
	if not ResourceLoader.exists(albedo) or not ResourceLoader.exists(normal):
		return null
	if not _cards.has(n):
		var b := impostor_base()
		var c: Vector3 = b[1]
		var r: float = b[2]
		var k: Vector3 = LPINE_SCALE[n]
		var q := QuadMesh.new()
		q.size = Vector2.ONE
		# It turns to the camera within the sphere round the (rescaled) tree.
		var big := r * maxf(k.x, maxf(k.y, k.z))
		q.custom_aabb = AABB(c * k - Vector3.ONE * big, Vector3.ONE * big * 2.0)
		var mat := ShaderMaterial.new()
		mat.shader = load(IMPOSTOR_SHADER)
		mat.set_shader_parameter("albedo_atlas", load(albedo))
		mat.set_shader_parameter("normal_atlas", load(normal))
		mat.set_shader_parameter("center", c)
		mat.set_shader_parameter("radius", r)
		mat.set_shader_parameter("variant_scale", k)
		mat.set_shader_parameter("azimuths", IMPOSTOR_AZIMUTHS)
		mat.set_shader_parameter("elevations", IMPOSTOR_ELEVATIONS)
		mat.set_shader_parameter("elevation_step", IMPOSTOR_EL_STEP)
		q.material = mat
		_cards[n] = q
	return _cards[n]


## The mesh that casts a variant's shadow (its cheapest modelled level).
static func tree_shadow_mesh(variant: Array) -> Mesh:
	return variant[1] if variant[1] != null else variant[0]


## How much each of Jon's pines' levels (full, middle, far, card) is brightened to
## read as the full model does (measured with tools/lod_shots.gd).
const MPINE_GAIN := [Vector3.ONE, Vector3(1.16, 1.12, 1.03), Vector3(1.72, 1.5, 1.12), Vector3(3.7, 2.7, 2.1)]
## The pine card toned to the far pines' muted olive (tree_card.gdshader). Tune with
## `--card-tone=contrast,saturation[,yellow_cap,low_sun,low_sun_direct]`.
static var CARD_CONTRAST := 0.6
static var CARD_SATURATION := 0.85
static var CARD_YELLOW_CAP := 0.65
static var CARD_LOW_SUN := 0.7
static var CARD_LOW_SUN_DIRECT := 0.3
static var _card_tone: bool = (func() -> bool:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--card-tone="):
			var d := a.substr(12).split_floats(",")
			CARD_CONTRAST = d[0]; CARD_SATURATION = d[1]
			if d.size() > 2:
				CARD_YELLOW_CAP = d[2]
			if d.size() > 3:
				CARD_LOW_SUN = d[3]
			if d.size() > 4:
				CARD_LOW_SUN_DIRECT = d[4]
	return true).call()
## The same for the broadleaf card.
const BROAD_CARD_GAIN := Vector3(0.62, 0.76, 1.2)


## The levels a variant is drawn at, as [mesh, from (m), to (m, 0 = no limit), and
## optionally the colour gain that matches it to the first].
static func tree_lod_levels(variant: Array) -> Array:
	var near: Mesh = variant[0]
	var far: Mesh = variant[1]
	var mid: Mesh = variant[2]
	var card: Mesh = variant[3] if variant.size() > 3 else null
	if card != null and sprite_trees:
		return [[card, 0.0, 0.0]]
	if near.has_meta("impostor_base"):
		# The 300-triangle pine: its impostor lit as the model is, so no colour gain.
		return [[near, 0.0, IMPOSTOR_DIST], [card, IMPOSTOR_DIST, 0.0]] if card != null else [[near, 0.0, 0.0]]
	if card != null and variant[4] == null:
		# A broadleaf: modelled out to the card.
		if "--cone-trees" in OS.get_cmdline_user_args():
			return [[near, 0.0, TREE_LOD_DIST], [far, TREE_LOD_DIST, 0.0]]
		return [[near, 0.0, BROAD_CARD_DIST], [card, BROAD_CARD_DIST, 0.0, BROAD_CARD_GAIN]]
	if card != null:
		_mpine_args.call()
		return [[near, 0.0, MPINE_NEAR_DIST], [mid, MPINE_NEAR_DIST, MPINE_MID_DIST, MPINE_GAIN[1]],
			[variant[4], MPINE_MID_DIST, MPINE_FAR_DIST, MPINE_GAIN[2]],
			[far, MPINE_FAR_DIST, 0.0] if "--cone-trees" in OS.get_cmdline_user_args() else [card, MPINE_FAR_DIST, 0.0, MPINE_GAIN[3]]]
	if far == null:
		return [[near, 0.0, 0.0]]
	if mid == null:
		return [[near, 0.0, TREE_LOD_DIST], [far, TREE_LOD_DIST, 0.0]]
	return [[near, 0.0, TREE_NEAR_DIST], [mid, TREE_NEAR_DIST, TREE_MID_DIST], [far, TREE_MID_DIST, 0.0]]


## Trees dither from one level of detail into the next over this many metres, centred
## on each swap (lod_dither.gdshaderinc), rather than popping. `--lod-fade=M` (0 = hard swaps).
static var LOD_FADE: float = (func() -> float:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--lod-fade="):
			return a.substr(11).to_float()
	return 30.0).call()
static var _lod_mats := {}


## Shows `mmi` (a tile of trees drawn with `mesh`, one level of tree_lod_levels) from
## `begin` to `end` (m, 0 = no limit). Each tree is placed by its own distance in the
## shader, while the tile's visibility range is by its middle: the range is widened by
## `slack` (as far as a tree can stand from the middle) and the fade, and the shader
## drops the trees outside.
static func dither_lod(mmi: GeometryInstance3D, mesh: Mesh, begin: float, end: float, slack: float,
		gain := Vector3.ONE) -> void:
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
	mat.set_shader_parameter("lod_fade", maxf(LOD_FADE, 0.0))
	mat.set_shader_parameter("lod_gain", gain)
	var pad := maxf(LOD_FADE, 0.0) * 0.5 + slack
	mmi.visibility_range_begin = maxf(begin - pad, 0.0) if begin > 0.0 else 0.0
	mmi.visibility_range_end = end + pad if end > 0.0 else 0.0


## Which variant a tree standing at `at` is: from its position, so the choice draws
## no random numbers and the rest of the map comes out the same.
static func tree_variant(at: Vector3, count: int) -> int:
	return absi(hash(Vector2i(roundi(at.x * 10.0), roundi(at.z * 10.0)))) % count


static func _tree_part(n: String) -> ArrayMesh:
	if n.begins_with("lpine"):
		return _cached("tree_" + n, func():
			var mb := ModelParts.merge_named(LPINE_GLB, ["pinetreelod"])
			var k: Vector3 = LPINE_SCALE[n]
			for i in mb.verts.size():
				mb.verts[i] *= k
				mb.normals[i] = (mb.normals[i] / k).normalized()
			var m := mb.commit()
			m.set_meta("impostor_base", "lpine")
			return m)
	var glb := MPINES_GLB if n.begins_with("mpine") else TREES_GLB
	return _cached("tree_" + n, func(): return ModelParts.merge_named(glb, [n.replace("_", "")]).commit())


static func rock() -> ArrayMesh:
	return _cached("rock", func():
		var mb := MeshBuilder.new()
		# [centre of the top, its radius] per piece.
		var tops := [[Vector3(0, 0.8, 0), 0.55], [Vector3(0.6, 0.4, 0.3), 0.25]]
		mb.cylinder(Vector3(0, -0.6, 0), 1.0, 0.55, 1.4, 5, Color(0.56, 0.47, 0.46), Color(0.68, 0.58, 0.52), 0.4)
		var first := mb.verts.size()
		mb.cylinder(Vector3(0.6, -0.5, 0.3), 0.6, 0.25, 0.9, 5, Color(0.5, 0.42, 0.42), Color(-1, 0, 0), 1.1)
		# UV.y: how far in from the top's outline, down the sides or across the top,
		# for the lit edge the boulder shader draws there (lit_vc.gdshaderinc, BOULDER).
		for k in mb.verts.size():
			var t: Array = tops[0 if k < first else 1]
			var c: Vector3 = t[0]
			var p := mb.verts[k]
			var d := 0.0
			if mb.normals[k].y > 0.9:
				d = float(t[1]) * cos(PI / 5.0) if Vector2(p.x - c.x, p.z - c.z).length() < 0.01 else 0.0
			else:
				d = maxf(c.y - p.y, 0.0)
			mb.uvs.append(Vector2(0.0, d))
		return mb.commit(boulder_material()))


const ROCK_STONE := Color(0.64, 0.53, 0.43)
const ROCK_STONE_LIGHT := Color(0.8, 0.68, 0.55)
const ROCK_MOSS := Color(0.5, 0.58, 0.24)

## Shoreline rock kit: chunky, faceted pieces about 1 m across (scale them up) with
## the origin at the ground line. "cliff" pieces are blocky with a grassy cap, for
## stacking along steep shores; "boulder" pieces are bare and rounder, for the
## shallows at a cliff's foot.
static func rock_kit(kind: String) -> Array[ArrayMesh]:
	var out: Array[ArrayMesh] = []
	for v in 4:
		out.append(_cached("rock_%s_%d" % [kind, v], func(): return _rock_piece(kind, v)))
	return out


## A sphere cut down by a handful of random planes: every vertex that lands on the
## same plane shares one flat facet, which reads as split stone.
static func _rock_piece(kind: String, v: int) -> ArrayMesh:
	var r := RandomNumberGenerator.new()
	r.seed = hash(kind) + v * 977
	var cliff := kind == "cliff"
	var planes: Array[Vector4] = []
	var cuts := 7 if cliff else 9
	for i in cuts:
		var n := Vector3(r.randf_range(-1, 1), r.randf_range(-0.55, 0.75), r.randf_range(-1, 1)).normalized()
		planes.append(Vector4(n.x, n.y, n.z, r.randf_range(0.72, 0.95)))
	# A flat-ish top, tipped a little.
	var top := Vector3(r.randf_range(-0.15, 0.15), 1.0, r.randf_range(-0.15, 0.15)).normalized()
	planes.append(Vector4(top.x, top.y, top.z, r.randf_range(0.55, 0.7) if cliff else r.randf_range(0.7, 0.85)))
	var stretch := Vector3(r.randf_range(1.1, 1.5), r.randf_range(0.8, 1.1), r.randf_range(0.8, 1.0)) if cliff \
		else Vector3(r.randf_range(1.0, 1.3), r.randf_range(0.6, 0.85), r.randf_range(0.85, 1.05))
	var seg := 10
	var rings := 7
	var grid: Array[Vector3] = []
	for j in rings + 1:
		var lat := lerpf(-PI * 0.5, PI * 0.5, float(j) / rings)
		for i in seg:
			var lon := TAU * (i + 0.5 * (j % 2)) / seg
			var d := Vector3(cos(lat) * cos(lon), sin(lat), cos(lat) * sin(lon))
			var rad := 1.25
			for p in planes:
				var dn := d.dot(Vector3(p.x, p.y, p.z))
				if dn > 1e-3:
					rad = minf(rad, p.w / dn)
			# Origin at the ground line: the bottom half is buried, so it only needs to exist.
			grid.append(d * rad * stretch + Vector3(0, 0.25, 0))
	var mb := MeshBuilder.new()
	# The grassy cap's triangles (local), for the grass blades to grow on.
	var caps: Array = []
	var add := func(a: Vector3, b: Vector3, c: Vector3) -> void:
		var n := (b - a).cross(c - a)
		if n.length_squared() < 1e-8:
			return
		n = n.normalized()
		var mid := (a + b + c) / 3.0
		if n.dot(mid) < 0.0:
			n = -n
		# One shade per facet: the plane this face lies on, not the triangle.
		var best := -1
		var best_d := 0.9
		for pi in planes.size():
			var pd := n.dot(Vector3(planes[pi].x, planes[pi].y, planes[pi].z))
			if pd > best_d:
				best_d = pd
				best = pi
		var shade := fposmod(sin(float(best) * 12.9898 + v * 78.233) * 43758.5453, 1.0) if best >= 0 else 0.35
		var col := ROCK_STONE.lerp(ROCK_STONE_LIGHT, shade)
		# Undersides and overhangs go dark; the cap goes green on the cliff pieces.
		col = col.darkened(clampf(-n.y, 0.0, 1.0) * 0.3)
		if cliff and n.y > 0.86:
			col = ROCK_MOSS.lerp(ROCK_MOSS.lightened(0.12), shade)
			caps.append_array([a, b, c])
		elif n.y > 0.55:
			col = col.lerp(ROCK_MOSS, 0.25 * (n.y - 0.55) / 0.45)
		mb.tri(a, b, c, col, mid)
	for j in rings:
		for i in seg:
			var a := grid[j * seg + i]
			var b := grid[j * seg + (i + 1) % seg]
			var c := grid[(j + 1) * seg + i]
			var d := grid[(j + 1) * seg + (i + 1) % seg]
			add.call(a, b, d)
			add.call(a, d, c)
	var mesh := mb.commit(rock_material())
	mesh.set_meta("caps", PackedVector3Array(caps))
	return mesh


static func house(wall: Color, roof: Color, stories: int) -> ArrayMesh:
	var key := "house_%s_%s_%d" % [wall.to_html(), roof.to_html(), stories]
	return _cached(key, func():
		var mb := MeshBuilder.new()
		var wh := 2.0 if stories == 1 else 3.4
		# Body extends below ground so houses on slopes never float.
		mb.box(Vector3(0, (wh - 1.2) * 0.5, 0), Vector3(2.8, wh + 1.2, 3.4), wall)
		mb.box(Vector3(0.6, 0.6, 1.71), Vector3(0.6, 1.2, 0.05), Color(0.35, 0.24, 0.18))
		mb.box(Vector3(-0.6, wh * 0.55, 1.71), Vector3(0.8, 0.6, 0.05), WINDOW)
		mb.box(Vector3(1.41, wh * 0.55, 0.0), Vector3(0.05, 0.6, 1.2), WINDOW)
		mb.box(Vector3(-1.41, wh * 0.55, 0.0), Vector3(0.05, 0.6, 1.2), WINDOW)
		var y0 := wh
		var y1 := wh + 1.4
		var hx := 1.65
		var hz := 1.95
		var l0 := Vector3(-hx, y0, -hz)
		var l1 := Vector3(-hx, y0, hz)
		var r0 := Vector3(hx, y0, -hz)
		var r1 := Vector3(hx, y0, hz)
		var t0 := Vector3(0, y1, -hz)
		var t1 := Vector3(0, y1, hz)
		# Each slope is a slab with some thickness, so the roof still reads when
		# seen edge-on from the gable end.
		_roof_slope(mb, l0, t0, hz, roof)
		_roof_slope(mb, r0, t0, hz, roof)
		mb.quad(l0, r0, r1, l1, roof.darkened(0.4), Vector3.DOWN)
		mb.tri(Vector3(-1.4, y0, 1.7), Vector3(1.4, y0, 1.7), Vector3(0, y1 - 0.2, 1.7), wall, Vector3.BACK)
		mb.tri(Vector3(-1.4, y0, -1.7), Vector3(1.4, y0, -1.7), Vector3(0, y1 - 0.2, -1.7), wall, Vector3.FORWARD)
		mb.box(Vector3(0.8, y1 - 0.2, -0.7), Vector3(0.45, 1.2, 0.45), Color(0.55, 0.3, 0.24))
		add_bulkhead_lamp(mb, HOUSE_LAMP, Vector3.BACK, Color(1.0, 0.7, 0.4), HOUSE_LAMP_SCALE, LAMP_DARK)
		return mb.commit())


const KIT_HOUSES_DIR := "res://assets/models/coastal_houses/"
## The coastal house kit (docs/coastal-house-kit.md), at scale 1, origin at ground
## level, +Z to the street.
const KIT_HOUSES := [
	"cottage_braced_stoop", "cottage_rain_porch",
	"craftsman_gable_porch", "craftsman_veranda",
	"craftsman_two_story_gable_porch", "craftsman_two_story_veranda",
	"cabin_lookout_deck", "cabin_mudroom",
	"contemporary_single_shed_view_terrace", "contemporary_single_shed_screened_entry",
	"contemporary_butterfly_view_terrace", "contemporary_butterfly_screened_entry",
	"contemporary_offset_gable_view_terrace", "contemporary_offset_gable_screened_entry",
	"contemporary_raised_clerestory_view_terrace", "contemporary_raised_clerestory_screened_entry",
]
const KIT_FOUNDATION := Color(0.46, 0.45, 0.42)
# How far the foundation runs below the floor, so houses on slopes never float.
const KIT_FOUNDATION_DEPTH := 6.0


## A kit house flattened to one mesh. `wall` / `roof` (when given) repaint the
## Siding and RoofFinish surfaces, keeping each board's shade; the contemporary
## houses keep their authored two-tone cladding. A stone foundation runs down from
## under the shell.
static func kit_house(name: String, wall := Color(-1, 0, 0), roof := Color(-1, 0, 0)) -> ArrayMesh:
	var key := "kit_%s_%s_%s" % [name, wall.to_html(), roof.to_html()]
	return _cached(key, func():
		var mb := MeshBuilder.new()
		var root := (load(KIT_HOUSES_DIR + name + ".tscn") as PackedScene).instantiate()
		var repaint_walls := not name.begins_with("contemporary")
		var shell := AABB()
		var have_shell := false
		for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			var part := ModelParts.painted(node)
			var xf := ModelParts.relative_xform(node, root)
			var n := String(node.name)
			var paint := Color(-1, 0, 0)
			if n.ends_with("Siding") and repaint_walls:
				paint = wall
			elif n.ends_with("RoofFinish"):
				paint = roof
			if paint.r >= 0.0:
				part = _repainted(part, paint)
			_append_part(mb, part, xf)
			if n.ends_with("Siding") and node.get_parent().name == "Shell":
				var box := xf * node.mesh.get_aabb()
				shell = box if not have_shell else shell.merge(box)
				have_shell = true
		root.free()
		if have_shell:
			var c := shell.get_center()
			mb.box(Vector3(c.x, 0.45 - KIT_FOUNDATION_DEPTH * 0.5, c.z),
				Vector3(shell.size.x - 0.1, KIT_FOUNDATION_DEPTH, shell.size.z - 0.1), KIT_FOUNDATION)
		return mb.commit())


## `part` with every colour replaced by `paint`, shaded by how far that vertex sat
## from the part's mean brightness.
static func _repainted(part: MeshBuilder, paint: Color) -> MeshBuilder:
	var out := MeshBuilder.new()
	out.verts = part.verts
	out.normals = part.normals
	var mean := 0.0
	for c in part.colors:
		mean += c.get_luminance()
	mean = maxf(mean / maxf(part.colors.size(), 1.0), 0.01)
	for c in part.colors:
		var k := clampf(c.get_luminance() / mean, 0.8, 1.2)
		out.colors.append(Color(paint.r * k, paint.g * k, paint.b * k))
	return out


## A kit house's marker (`PorchLight`, `Entry`) in its own frame.
static func kit_marker(name: String, marker: String) -> Vector3:
	var key := name + ":" + marker
	if not _kit_markers.has(key):
		var root := (load(KIT_HOUSES_DIR + name + ".tscn") as PackedScene).instantiate()
		var m := root.get_node_or_null(marker) as Node3D
		_kit_markers[key] = m.position if m else Vector3.ZERO
		root.free()
	return _kit_markers[key]

static var _kit_markers := {}


## A kit house's plan in its own frame (x, z), porch, deck and steps included, so
## placement can sit the floor above every bit of ground the house covers.
static func kit_footprint(name: String) -> Rect2:
	if not _kit_footprints.has(name):
		var root := (load(KIT_HOUSES_DIR + name + ".tscn") as PackedScene).instantiate()
		var box := AABB()
		var first := true
		for node: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			var b := ModelParts.relative_xform(node, root) * node.mesh.get_aabb()
			box = b if first else box.merge(b)
			first = false
		root.free()
		_kit_footprints[name] = Rect2(box.position.x, box.position.z, box.size.x, box.size.z)
	return _kit_footprints[name]

static var _kit_footprints := {}


## One slope of a gable roof, eave to ridge (both at -z), running to +z and
## `thick` deep below its top face.
static func _roof_slope(mb: MeshBuilder, eave: Vector3, ridge: Vector3, hz: float, col: Color, thick := 0.15) -> void:
	var n := Vector3(eave.x - ridge.x, 0, 0).normalized() * (ridge.y - eave.y) + Vector3(0, absf(eave.x - ridge.x), 0)
	n = n.normalized()
	var z := Vector3(0, 0, hz * 2.0)
	var e := eave - n * thick
	var r := ridge - n * thick
	var under := col.darkened(0.4)
	mb.quad(eave, ridge, ridge + z, eave + z, col, n)
	mb.quad(e, r, r + z, e + z, under, -n)
	mb.quad(eave, eave + z, e + z, e, col.darkened(0.15), eave - ridge)
	mb.quad(eave, ridge, r, e, col.darkened(0.15), Vector3.FORWARD)
	mb.quad(eave + z, ridge + z, r + z, e + z, col.darkened(0.15), Vector3.BACK)


static func block(wall: Color) -> ArrayMesh:
	return _cached("block_" + wall.to_html(), func():
		var mb := MeshBuilder.new()
		var h := 6.6
		mb.box(Vector3(0, (h - 1.2) * 0.5, 0), Vector3(4.4, h + 1.2, 5.0), wall)
		for level in 3:
			var y := 1.3 + level * 2.1
			mb.box(Vector3(0, y, 0), Vector3(4.5, 0.7, 4.2), WINDOW)
			mb.box(Vector3(0, y, 0), Vector3(3.6, 0.7, 5.1), WINDOW)
		mb.box(Vector3(0, h + 0.15, 0), Vector3(4.6, 0.3, 5.2), Color(0.3, 0.31, 0.33))
		mb.box(Vector3(0.8, h + 0.6, -0.8), Vector3(1.2, 0.7, 1.2), Color(0.6, 0.6, 0.6))
		add_bulkhead_lamp(mb, BLOCK_LAMP, Vector3.BACK, Color(1.0, 0.7, 0.4), BLOCK_LAMP_SCALE, LAMP_DARK)
		return mb.commit())


static func car(color_index: int) -> ArrayMesh:
	return _cached("car_%d" % color_index, func():
		var col: Color = CAR_COLORS[color_index % CAR_COLORS.size()]
		var mb := MeshBuilder.new()
		mb.box(Vector3(0, 0.44, 0), Vector3(1.0, 0.5, 2.0), col)
		mb.box(Vector3(0, 0.86, -0.12), Vector3(0.84, 0.36, 1.05), col.lightened(0.05))
		mb.box(Vector3(0, 0.86, -0.12), Vector3(0.86, 0.24, 0.95), GLASS)
		mb.box(Vector3(0, 0.86, -0.12), Vector3(0.7, 0.24, 1.07), GLASS)
		for x: float in [-0.46, 0.46]:
			for z: float in [-0.62, 0.62]:
				mb.box(Vector3(x, 0.2, z), Vector3(0.16, 0.36, 0.42), Color(0.08, 0.08, 0.08))
		return mb.commit())


## Cars use the ones modelled in Blender (VEHICLES_GLB, built by art/vehicles.py into
## art/vehicles.blend, their sizes and lamps in VehicleData): eight each of sedans,
## SUVs, minivans, vans and pickups, plus trucks, tractors and trailers (TRUCKS), each
## painted from PAINTS. They're modelled at real size and drawn at VEHICLE_SCALE to
## match the ferries until the world is real scale. The code-built car above is the
## fallback: with `--classic-cars`, or if the model is missing.
const VEHICLES_GLB := "res://assets/models/vehicles.glb"
static var mid_cars := not "--classic-cars" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(VEHICLES_GLB)
const VEHICLE_SCALE := Units.VEHICLE_MODEL_SCALE
# The cars (VehicleData keys) and how common each is on the road: sedans and SUVs
# (100 each), pickups (45, full-size first), minivans (25) and vans (20), work vans first.
const VEHICLES := {
	"sedan_modern": 25, "sedan_compact": 18, "sedan_nineties": 15, "sedan_ev": 10,
	"sedan_boxy": 8, "sedan_exec": 8, "sedan_luxury": 8, "sedan_sport": 8,
	"suv_crossover": 30, "suv_threerow": 20, "suv_nineties": 10, "suv_offroad": 10,
	"suv_luxury": 9, "suv_ev": 9, "suv_cherokee": 8, "suv_coupe": 4,
	"minivan_family": 6, "minivan_modern": 5, "minivan_bold": 4, "minivan_nineties": 3,
	"minivan_suvish": 3, "minivan_boxy": 2, "minivan_compact": 1, "minivan_ev": 1,
	"van_cargo": 6, "van_hightop": 3, "van_compact": 3, "van_passenger": 2, "van_shuttle": 2,
	"van_camper": 2, "van_retro": 1, "van_overland": 1,
	"pickup_fullsize": 14, "pickup_midsize": 8, "pickup_compact": 5, "pickup_trail": 5,
	"pickup_dually": 4, "pickup_squarebody": 4, "pickup_rock": 3, "pickup_sport": 2,
	"pickup_princess": 1}
# Trucks (Vehicle.is_truck: a share of the traffic, see Simulation) and how common:
# box trucks and step vans on their rounds first; "rig" is a tractor-trailer, its
# tractor and trailer picked from TRACTORS and TRAILERS.
const TRUCKS := {"truck_box": 30, "truck_step": 20, "truck_reefer": 14, "truck_tank": 10, "rig": 26}
const TRACTORS := {"tractor_day": 30, "tractor_aero": 25, "tractor_midroof": 20, "tractor_longnose": 15,
	"tractor_classic": 10}
const TRAILERS := {"trailer_van": 25, "trailer_reefer": 15, "trailer_container": 15, "trailer_flatbed": 12,
	"trailer_logs": 10, "trailer_dump": 10, "trailer_tank": 8, "trailer_carhauler": 5}
# Paint and how common: whites, blacks, greys and silvers first, as in any car park.
const PAINTS := [
	[Color(0.9, 0.9, 0.88), 20], [Color(0.86, 0.84, 0.78), 5], [Color(0.1, 0.1, 0.11), 16],
	[Color(0.3, 0.31, 0.33), 10], [Color(0.66, 0.68, 0.7), 12], [Color(0.15, 0.3, 0.6), 7],
	[Color(0.12, 0.16, 0.3), 4], [Color(0.72, 0.14, 0.11), 8], [Color(0.42, 0.1, 0.12), 3],
	[Color(0.2, 0.4, 0.27), 4], [Color(0.72, 0.65, 0.52), 3], [Color(0.25, 0.55, 0.6), 3],
	[Color(0.9, 0.72, 0.18), 2], [Color(0.88, 0.42, 0.14), 1], [Color(0.4, 0.3, 0.22), 2]]


## A car picked by how common each is, from `u` in [0, 1).
static func pick_vehicle(u: float) -> String:
	return pick_weighted(VEHICLES, u)


## A key of `table` (key -> weight) picked by weight, from `u` in [0, 1).
static func pick_weighted(table: Dictionary, u: float) -> String:
	var total := 0
	for n: String in table:
		total += table[n]
	var x := u * total
	for n: String in table:
		x -= table[n]
		if x < 0.0:
			return n
	return table.keys()[0]


## A paint (index into PAINTS) picked by how common each is, from `u` in [0, 1).
static func pick_paint(u: float) -> int:
	var total := 0
	for p: Array in PAINTS:
		total += p[1]
	var x := u * total
	for i in PAINTS.size():
		x -= PAINTS[i][1]
		if x < 0.0:
			return i
	return 0


## Vehicle `model` (a VehicleData key) in paint `paint`, at its modelled (real) size.
static func vehicle(model: String, paint: int) -> ArrayMesh:
	var lib := ModelParts.library(VEHICLES_GLB)
	var key := model.replace("_", "")
	# Only the body and accent take paint. A fixed trailer can share its mesh across liveries.
	if TRAILERS.has(model) and not lib.has(key + "body") and not lib.has(key + "accent"):
		paint = 0
	return _cached("%s_%d" % [model, paint], func():
		var mb := MeshBuilder.new()
		_append_part(mb, lib[key + "fixed"], Transform3D.IDENTITY)
		var col: Color = PAINTS[paint % PAINTS.size()][0]
		if lib.has(key + "body"):  # (some trailers have nothing painted)
			_append_part(mb, lib[key + "body"], Transform3D.IDENTITY, Color.WHITE, col)
		if lib.has(key + "accent"):
			# A two-tone band: a darker shade of the paint.
			_append_part(mb, lib[key + "accent"], Transform3D.IDENTITY, Color.WHITE, col.darkened(0.45))
		if lib.has(key + "head"):  # (trailers have none)
			_append_part(mb, lib[key + "head"], Transform3D.IDENTITY, Color.WHITE, lamp_glass(GlowBuilder.HEADLIGHT))
		_append_part(mb, lib[key + "tail"], Transform3D.IDENTITY, Color.WHITE, lamp_glass(GlowBuilder.TAIL))
		return mb.commit())


static func truck(color_index: int) -> ArrayMesh:
	return _cached("truck_%d" % color_index, func():
		var col: Color = CAR_COLORS[color_index % CAR_COLORS.size()]
		var mb := MeshBuilder.new()
		mb.box(Vector3(0, 0.7, 0.72), Vector3(1.1, 1.0, 0.8), col)
		mb.box(Vector3(0, 0.9, 1.1), Vector3(0.95, 0.4, 0.06), GLASS)
		mb.box(Vector3(0, 0.95, -0.42), Vector3(1.15, 1.3, 1.5), Color(0.9, 0.9, 0.88))
		for x: float in [-0.5, 0.5]:
			for z: float in [-0.8, 0.75]:
				mb.box(Vector3(x, 0.2, z), Vector3(0.16, 0.38, 0.44), Color(0.08, 0.08, 0.08))
		return mb.commit())


## Double-ended car ferry of class `fc` (see FerryClass). +Z and -Z ends are
## identical; car deck top at DECK_Y.
static func ferry(fc: FerryClass) -> ArrayMesh:
	if fc.evergreen:
		return _cached("ferry_%d" % fc.size, func():
			return _mid_ferry(fc, FerryClass.MID_GLB, FerryClass.MID_DROP, ["fixed", "thin", "glass", "window", "lamp"]).commit())
	if fc.jumbo:
		return _cached("ferry_%d" % fc.size, func():
			return _mid_ferry(fc, FerryClass.JUMBO_GLB, FerryClass.MID_DROP, ["fixed", "thin", "glass", "window", "lamp"]).commit())
	if fc.issaquah:
		return _cached("ferry_%d" % fc.size, func():
			return _mid_ferry(fc, FerryClass.ISQ_GLB, FerryClass.ISQ_DROP, ["fixed", "thin", "glass", "window", "lamp"]).commit())
	if fc.guemes:
		return _cached("ferry_%d" % fc.size, func():
			return _mid_ferry(fc, FerryClass.SMALL_GLB, FerryClass.SMALL_DROP, ["fixed", "thin", "glass", "window"]).commit())
	if fc.hiyu:
		return _cached("ferry_%d" % fc.size, func():
			return _mid_ferry(fc, FerryClass.HIYU_GLB, FerryClass.HIYU_DROP, ["fixed", "thin", "glass", "window"]).commit())
	return _cached("ferry_%d" % fc.size, func():
		var mb := MeshBuilder.new()
		var b := fc.half_beam
		var l := fc.half_length
		var hull := PackedVector2Array([Vector2(-b, -(l - fc.chamfer)), Vector2(-(b - fc.end_in), -l),
			Vector2(b - fc.end_in, -l), Vector2(b, -(l - fc.chamfer)), Vector2(b, l - fc.chamfer),
			Vector2(b - fc.end_in, l), Vector2(-(b - fc.end_in), l), Vector2(-b, l - fc.chamfer)])
		if fc.portal:
			# Dark to the deck, the green running up the bulwarks.
			mb.extrude(hull, -4.2, 1.65, HULL_DARK, Color(0, 0, 0, 0), 0.8)
			mb.extrude(hull, 1.65, 2.85, WSF_GREEN, Color(0.42, 0.44, 0.47))
		else:
			mb.extrude(hull, -4.2, 0.45, HULL_DARK, Color(0, 0, 0, 0), 0.8)
			mb.extrude(hull, 0.45, 1.65, WSF_GREEN, Color(0, 0, 0, 0))
			mb.extrude(hull, 1.65, 2.85, WHITE, Color(0.42, 0.44, 0.47))
		if fc.open_deck:
			_open_ferry(mb, fc)
		elif fc.portal:
			_portal_ferry(mb, fc)
		else:
			_full_ferry(mb, fc)
		for p in fc.lanterns:
			add_lantern(mb, p, GlowBuilder.LED, fc.lantern_scale)
		for sl: Array in fc.sidelights:
			add_sidelight(mb, sl[0], sl[1], sl[2], fc.sidelight_scale)
		for lp: Array in fc.lamps:
			add_bulkhead_lamp(mb, lp[0], lp[1], GlowBuilder.WARM, fc.lamp_scale)
		return mb.commit())


# Car deck nets: rope on yellow posts.
const NET_ROPE := Color(0.7, 0.58, 0.38)
const NET_POST := Color(0.88, 0.7, 0.12)
const NET_H := 1.6


## The mid-poly net (art/ferry_net_mid.py): yellow stanchions (`post`), wall brackets
## (`eye`) and spans of diamond-mesh rope net (`bay_4`, `bay_5`, `bay_6`, 4 to 6 m
## wide), modelled in metres and shown at FerryClass.MID_SCALE. It billows and
## flutters in the apparent wind (shaders/net.gdshader). The boxes below are the
## fallback: with `--classic-net`, or if the model is missing.
const MID_NET_GLB := "res://assets/models/ferry_net_mid.glb"
static var mid_net := not "--classic-net" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_NET_GLB)
const MID_NET_BAYS := [4, 5, 6]
const MID_NET_H := 1.6
static var _net_mat: ShaderMaterial


## The mid-poly slip (art/slip_mid.py): lattice lift towers with their header, sheaves
## and ladders (`towers`, static scenery in the slip frame) and the moving parts SlipRamp
## works: the transfer span, the apron, counterweights, hoist cables and the apron's
## rams. The old boxes are the fallback: with `--classic-slip`, or if the model is missing.
const MID_SLIP_GLB := "res://assets/models/slip_mid.glb"
static var mid_slip := not "--classic-slip" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_SLIP_GLB)


## The slip's guide structures, modelled in metres with the water at y = 0 and their
## fendered faces looking +Z: a six-pile dolphin for the lit outer pair, a four-pile
## one for the inner pair (art/ferry_dolphin*.blend) and the splayed wing wall
## (art/wing_wall.blend, art/export_wing_wall.py), the wall running along X. Their
## material colours are baked in (ModelParts.baked). The procedural piles and boxes are
## the fallback: with `--classic-slip`, or if a model is missing.
const SLIP_DOLPHIN_OUTER_GLB := "res://assets/models/ferry_dolphin_lod.glb"
const SLIP_DOLPHIN_INNER_GLB := "res://assets/models/ferry_dolphin_small_lod.glb"
const SLIP_WING_WALL_GLB := "res://assets/models/wing_wall_lod.glb"
# How far each dolphin's fender face stands in front of its origin, and its deck top.
const SLIP_DOLPHIN_FACE := 3.5
const SLIP_DOLPHIN_DECK := 4.17
static var mid_slip_guides := not "--classic-slip" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(SLIP_DOLPHIN_OUTER_GLB) and ResourceLoader.exists(SLIP_DOLPHIN_INNER_GLB) \
	and ResourceLoader.exists(SLIP_WING_WALL_GLB)


## One part of the mid-poly slip, about its own pivot (see SlipRamp).
static func slip_part(part: String) -> MeshBuilder:
	return ModelParts.library(MID_SLIP_GLB)[part]


static func slip_mesh(part: String) -> ArrayMesh:
	return _cached("slip_" + part, func(): return slip_part(part).commit())


## The terminal trestle (art/trestle_mid.py): deck `bay`s and the `landing` onto the
## span's hinge, both built level and lifted onto the road's profile vertex by vertex
## (append_on_profile), the pile `bent`s under their joints, the `abutment` at the
## lot's edge and the `lamp` poles on the barrier. Without it the old flat pier stands.
const MID_TRESTLE_GLB := "res://assets/models/trestle_mid.glb"
static var mid_trestle := mid_slip and ResourceLoader.exists(MID_TRESTLE_GLB)


static func trestle_part(part: String) -> MeshBuilder:
	return ModelParts.library(MID_TRESTLE_GLB)[part]


## Appends `part` at (v, 0, u) in the frame `xf` maps to the world, each vertex lifted by
## `height.call(u)` where it stands along u, so level-built deck parts follow a profile
## and neighbours meet exactly (verticals stay vertical; the grades are gentle enough
## to keep the normals).
static func append_on_profile(mb: MeshBuilder, part: MeshBuilder, xf: Transform3D, v: float, u: float,
		height: Callable) -> void:
	var verts := PackedVector3Array()
	verts.resize(part.verts.size())
	for i in part.verts.size():
		var p := part.verts[i] + Vector3(v, 0.0, u)
		p.y += height.call(p.z)
		verts[i] = xf * p
	mb.verts.append_array(verts)
	mb.normals.append_array(Transform3D(xf.basis.orthonormalized(), Vector3.ZERO) * part.normals)
	mb.colors.append_array(part.colors)


## One of a ferry's car deck nets (FerryClass.net_z, net_half_w), centred on z = 0:
## rope strung from wall to wall, held up by two yellow posts a third of the way
## across. Ferry places one at each end and drops the one at the docked end while
## cars cross it.
static func ferry_net(fc: FerryClass) -> ArrayMesh:
	if mid_net:
		return _mid_ferry_net(fc)
	return _cached("ferry_net_%d" % fc.size, func():
		var mb := MeshBuilder.new()
		var w := fc.net_half_w
		var y := Layout.DECK_Y
		for x: float in [-w / 3.0, w / 3.0]:
			mb.box(Vector3(x, y + NET_H * 0.5, 0), Vector3(0.15, NET_H, 0.15), NET_POST)
		for f: float in [0.2, 0.46, 0.73, 0.95]:
			mb.box(Vector3(0, y + f * NET_H, 0), Vector3(2.0 * w, 0.06, 0.06), NET_ROPE)
		var n := ceili(2.0 * w / 0.5)
		for i in range(1, n):
			mb.box(Vector3(lerpf(-w, w, i / float(n)), y + 0.575 * NET_H, 0), Vector3(0.06, 0.75 * NET_H, 0.06), NET_ROPE)
		return mb.commit())


## Three bays across the deck, from a bracket on each wall to the posts at the
## thirds: the modelled width nearest a third of the deck's, stretched to fit. Each
## net vertex's alpha holds how freely it moves (1 - alpha / 2: 0 at the posts and
## walls and along the head rope's ends, most low in the middle of a bay), which
## net.gdshader scales by the wind. Posts and brackets keep alpha 1.
static func _mid_ferry_net(fc: FerryClass) -> ArrayMesh:
	return _cached("ferry_net_mid_%d" % fc.size, func():
		var lib := ModelParts.library(MID_NET_GLB)
		var k := FerryClass.MID_SCALE
		var w := fc.net_half_w
		var span := 2.0 * w / 3.0
		var bay_w: int = MID_NET_BAYS[0]
		for n: int in MID_NET_BAYS:
			if absf(n * k - span) < absf(bay_w * k - span):
				bay_w = n
		var bay: MeshBuilder = lib["bay%d" % bay_w]
		var mb := MeshBuilder.new()
		for b in 3:
			var x0 := -w + b * span
			var xf := Transform3D(Basis.from_scale(Vector3(span / bay_w, k, k)), Vector3(x0, Layout.DECK_Y, 0))
			var start := mb.verts.size()
			_append_part(mb, bay, xf)
			for i in range(start, mb.verts.size()):
				var u := clampf((mb.verts[i].x - x0) / span, 0.0, 1.0)
				var h := clampf((mb.verts[i].y - Layout.DECK_Y) / (MID_NET_H * k), 0.0, 1.0)
				# Pinned at the ends; the head rope is slung taut, the foot slacker, the
				# belly a third of the way up freest.
				var free := sin(PI * u) * (0.35 + 0.65 * sin(PI * 0.75 * (1.0 - h)))
				var c := mb.colors[i]
				c.a = 1.0 - 0.5 * clampf(free, 0.0, 1.0)
				mb.colors[i] = c
		for x: float in [-w / 3.0, w / 3.0]:
			_append_part(mb, lib["post"], Transform3D(Basis.from_scale(Vector3.ONE * k), Vector3(x, Layout.DECK_Y, 0)))
		# The brackets face in from the walls.
		for e: float in [-1.0, 1.0]:
			var basis := Basis(Vector3.UP, 0.0 if e < 0.0 else PI).scaled(Vector3.ONE * k)
			_append_part(mb, lib["eye"], Transform3D(basis, Vector3(e * w, Layout.DECK_Y, 0)))
		if _net_mat == null:
			_net_mat = ShaderMaterial.new()
			_net_mat.shader = load("res://shaders/net.gdshader")
		var mesh := mb.commit(_net_mat)
		# The shadow and depth passes would draw it unmoved.
		mesh.shadow_mesh = null
		return mesh)


# The Evergreen State's car deck lights: the lenses' glow, and the light they throw
# on the deck (an oval pool under each, its half width and half length in her
# metres, and its energy).
const CAR_DECK_LIGHT := Color(1.0, 0.82, 0.55)
const CAR_DECK_POOL := Vector2(2.6, 5.2)
const CAR_DECK_POOL_ENERGY := 0.2


## A mid-poly ferry: the Evergreen State (FerryClass.MID_GLB, source
## art/ferry_mid.py), the Guemes (SMALL_GLB, art/guemes_mid.py) or the Hiyu
## (HIYU_GLB, art/hiyu_mid.py), scaled and dropped
## into the hull's frame; its `glass` (pilothouse, cabin) lit, its `window`s lit room
## by room, the Evergreen State's car deck ceiling `lamp`s glowing. Then her rescue
## boats (FerryClass.ribs) in their cradles, and the class's lanterns, sidelights and
## deck lamps.
## Stout stand-ins that cast the shadows of a mid-poly ferry's rails, stays and other
## thin pipes (those are thinner than a shadow map texel and cast none), or null.
static func ferry_thin_shadow(fc: FerryClass) -> ArrayMesh:
	var src: Array = [FerryClass.MID_GLB, FerryClass.MID_DROP] if fc.evergreen \
		else [FerryClass.SMALL_GLB, FerryClass.SMALL_DROP] if fc.guemes \
		else [FerryClass.HIYU_GLB, FerryClass.HIYU_DROP] if fc.hiyu \
		else [FerryClass.ISQ_GLB, FerryClass.ISQ_DROP] if fc.issaquah \
		else [FerryClass.JUMBO_GLB, FerryClass.MID_DROP] if fc.jumbo else []
	if src.is_empty():
		return null
	return _cached("ferry_thin_shadow_%d" % fc.size, func():
		var p := ModelParts.merge_named(src[0], ["thinshadow"])
		var mb := MeshBuilder.new()
		for i in p.verts.size():
			mb.verts.append(p.verts[i] * FerryClass.MID_SCALE - Vector3(0, src[1], 0))
			mb.normals.append(p.normals[i])
		mb.colors = p.colors
		return mb.commit())


static func _mid_ferry(fc: FerryClass, glb: String, drop_y: float, parts: Array) -> MeshBuilder:
	var mb := MeshBuilder.new()
	var k := FerryClass.MID_SCALE
	var drop := Vector3(0, drop_y, 0)
	var lens := lamp_glass(CAR_DECK_LIGHT)
	for part: String in parts:
		var p := ModelParts.merge_named(glb, [part])
		if part == "thin":
			mb.no_shadow.append(Vector2i(mb.verts.size(), mb.verts.size() + p.verts.size()))
		for i in p.verts.size():
			mb.verts.append(p.verts[i] * k - drop)
			mb.normals.append(p.normals[i])
		if part == "fixed" or part == "thin":
			mb.colors.append_array(p.colors)
		else:
			var c: Color = {"glass": WINDOW_LIT, "window": WINDOW, "lamp": lens}[part]
			for i in p.verts.size():
				mb.colors.append(c)
	if not fc.ribs.is_empty() and ResourceLoader.exists(FerryClass.RIB_GLB):
		var rib := ModelParts.merge_named(FerryClass.RIB_GLB, ["fixed", "sling"])
		for r: Array in fc.ribs:
			var b := Basis(Vector3.UP, r[1])
			var at: Vector3 = r[0]
			for i in rib.verts.size():
				mb.verts.append((b * rib.verts[i] + at) * k - drop)
				mb.normals.append(b * rib.normals[i])
			mb.colors.append_array(rib.colors)
	for p in fc.lanterns:
		add_lantern(mb, p, GlowBuilder.LED, fc.lantern_scale)
	for sl: Array in fc.sidelights:
		add_sidelight(mb, sl[0], sl[1], sl[2], fc.sidelight_scale)
	for lp: Array in fc.lamps:
		add_bulkhead_lamp(mb, lp[0], lp[1], GlowBuilder.WARM, fc.lamp_scale)
	return mb


## Sizes 3-5: an enclosed car deck with open galleries above, a passenger deck over
## it all, a sun-deck cabin, wheelhouses at both ends and the funnel(s) amidships.
static func _full_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	var b := fc.half_beam
	var l := fc.half_length
	mb.box(Vector3(0, 3.0, 0), Vector3(2.0 * b - 1.8, 0.3, 2.0 * (l - 9.0)), Color(0.45, 0.47, 0.5))
	# Car deck side walls with an open gallery above.
	for x: float in [-(b - 0.45), b - 0.45]:
		mb.box(Vector3(x, 5.1, 0), Vector3(0.9, 3.9, 2.0 * (l - 13.5)), WHITE)
		for z in fc.gallery:
			mb.box(Vector3(x, 8.4, z), Vector3(0.9, 3.0, 1.2), WHITE)
	# Passenger deck
	mb.box(Vector3(0, 10.05, 0), Vector3(2.0 * b + 1.05, 0.9, 2.0 * (l - 14.7)), WSF_GREEN)
	mb.box(Vector3(0, 12.9, 0), Vector3(2.0 * b + 0.6, 4.8, 2.0 * (l - 15.0)), WHITE)
	mb.box(Vector3(0, 13.2, 0), Vector3(2.0 * b + 0.9, 1.8, 2.0 * (l - 17.4)), WINDOW_LIT)
	# Sun deck and upper cabin
	mb.box(Vector3(0, 17.1, 0), Vector3(2.0 * b - 6.0, 3.6, 2.0 * fc.sun_half), WHITE)
	mb.box(Vector3(0, 17.4, 0), Vector3(2.0 * b - 5.7, 1.35, 2.0 * fc.sun_half - 4.2), WINDOW_LIT)
	# Wheelhouses at both ends
	var ww := 2.0 * fc.wheel_half_w
	for z: float in [-fc.wheel_z, fc.wheel_z]:
		mb.box(Vector3(0, 20.55, z), Vector3(ww, 3.3, 7.2), WHITE)
		mb.box(Vector3(0, 20.85, z), Vector3(ww + 0.3, 1.35, 7.5), WINDOW_LIT)
		mb.box(Vector3(0, 24.9, z), Vector3(0.45, 5.4, 0.45), WHITE)
	# Funnels
	for z in fc.funnels:
		mb.box(Vector3(0, 22.2, z), Vector3(4.8, 6.6, 7.8), WHITE)
		mb.box(Vector3(0, 25.05, z), Vector3(4.95, 1.05, 7.95), WSF_GREEN)
		mb.box(Vector3(0, 26.4, z), Vector3(5.1, 1.5, 8.1), Color(0.1, 0.1, 0.1))
	# Lifeboats
	for x: float in [-(b - 2.1), b - 2.1]:
		for z in fc.lifeboats:
			mb.box(Vector3(x, 19.5, z), Vector3(2.4, 1.5, 6.6), Color(0.95, 0.45, 0.12))


## The car deck of sizes 1 and 2, open to the sky at the ends: between bulwarks,
## with lane stripes down it.
static func _open_car_deck(mb: MeshBuilder, fc: FerryClass, bulwark := WHITE) -> void:
	var b := fc.half_beam
	var l := fc.half_length
	var deck_col := Color(0.45, 0.47, 0.5)
	var deck_l := l - 7.2
	mb.box(Vector3(0, 3.0, 0), Vector3(2.0 * b - 1.2, 0.3, 2.0 * deck_l), deck_col)
	for z: float in [-1.0, 1.0]:
		mb.box(Vector3(0, 2.97, z * (deck_l + 3.3)), Vector3(2.0 * (b - fc.end_in) - 0.6, 0.24, 6.6), deck_col)
	# Lane stripes, stopping short of the ends.
	for c in range(fc.cols.size() - 1):
		var x := (fc.cols[c] + fc.cols[c + 1]) * 0.5
		mb.box(Vector3(x, 3.18, 0), Vector3(0.18, 0.06, 2.0 * deck_l - 3.0), Color(0.9, 0.9, 0.85))
	# Bulwarks along both sides, open at the ends for the cars, with a life ring.
	var bl := l - fc.chamfer + 0.9
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * (b - 0.36), 4.35, 0), Vector3(0.72, 2.7, 2.0 * bl), bulwark)
		mb.box(Vector3(x * (b - 0.36), 5.76, 0), Vector3(0.9, 0.18, 2.0 * bl), bulwark.lightened(0.15))
		for z: float in [-1.0, 1.0]:
			mb.box(Vector3(x * (b + 0.03), 4.2, z * (bl - 3.6)), Vector3(0.18, 1.5, 1.5), Color(0.95, 0.45, 0.12))


## Size 1: the open car deck, the wheelhouse up on a stair column on the +X side
## and the exhaust stack standing against the -X bulwark.
static func _open_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	_open_car_deck(mb, fc)
	# Posts for the deck lamps on the -X side.
	for lp: Array in fc.lamps:
		var p: Vector3 = lp[0]
		if p.x < 0.0:
			mb.box(Vector3(p.x - 0.09, 6.0, p.z), Vector3(0.48, 6.0, 0.48), WHITE)
	# The house.
	var hx := fc.house_x
	var hw := fc.house_half_w
	var wy := fc.wheel_y
	var whw := fc.wheel_half_w_open()
	# Stair column, with a door at deck level and a railed landing halfway.
	mb.box(Vector3(hx, (3.0 + wy) * 0.5, 0), Vector3(2.0 * hw, wy - 3.0, 2.0 * fc.house_half_len), WHITE)
	mb.box(Vector3(hx - hw - 0.03, 5.55, 0), Vector3(0.12, 4.5, 2.1), Color(0.55, 0.57, 0.6))
	mb.box(Vector3(hx, 7.8, 0), Vector3(2.0 * hw + 1.5, 0.24, 2.0 * fc.house_half_len + 1.5), WSF_GREEN)
	# Wheelhouse, with windows all round, and its mast.
	var top := wy + fc.wheel_h
	mb.box(Vector3(hx, wy + 0.12, 0), Vector3(2.0 * whw + 0.9, 0.24, 2.0 * fc.wheel_half_len + 0.9), WSF_GREEN)
	mb.box(Vector3(hx, wy + fc.wheel_h * 0.5, 0), Vector3(2.0 * whw, fc.wheel_h, 2.0 * fc.wheel_half_len), WHITE)
	mb.box(Vector3(hx, wy + 2.25, 0), Vector3(2.0 * whw + 0.3, 1.26, 2.0 * fc.wheel_half_len + 0.3), WINDOW_LIT)
	mb.box(Vector3(hx, top + 0.09, 0), Vector3(2.0 * whw + 0.6, 0.18, 2.0 * fc.wheel_half_len + 0.6), WHITE)
	mb.box(Vector3(hx, top + 2.25, 0), Vector3(0.36, 4.5, 0.36), WHITE)
	mb.box(Vector3(hx, top + 3.0, 0), Vector3(2.7, 0.18, 0.18), WHITE)
	# Exhaust stack against the far bulwark.
	var sx := fc.stack_x
	mb.box(Vector3(sx, 4.8, 0), Vector3(1.8, 3.6, 3.0), WHITE)
	mb.cylinder(Vector3(sx, 6.6, 0), 0.6, 0.6, fc.stack_top - 7.8, 6, Color(0.3, 0.3, 0.32))
	mb.cylinder(Vector3(sx, fc.stack_top - 1.2, 0), 0.66, 0.66, 1.2, 6, Color(0.1, 0.1, 0.1))


## Size 2, after the M/V Hiyu: the open car deck runs through a portal amidships.
## Passenger cabins sit over the two outer lanes on slim pillars, a bridge spans
## the tall centre lane between them, and the upper deck on top, railed all round,
## carries the double-ended pilothouse, the stacks, a rescue boat and life rafts.
static func _portal_ferry(mb: MeshBuilder, fc: FerryClass) -> void:
	_open_car_deck(mb, fc, WSF_GREEN)
	var b := fc.half_beam
	var hl := fc.house_half_len
	var si := fc.side_in
	var lo := fc.low_y
	var ct := fc.cabin_top
	var dark := Color(0.2, 0.21, 0.23)
	var sign_y := Color(0.95, 0.78, 0.15)
	for x: float in [-1.0, 1.0]:
		# The outer wall down to the bulwark, shorter than the cabin and curving up
		# into its ends, with the car deck's openings in it.
		var ll := fc.low_half_len
		mb.box(Vector3(x * (b - 0.45), (5.7 + lo) * 0.5, 0), Vector3(0.9, lo - 5.7, 2.0 * ll), WHITE)
		for zs: float in [-1.0, 1.0]:
			_fillet(mb, x * (b - 0.9), x * b, zs * ll, zs * hl, 5.7, lo, WHITE)
		var z := -(ll - 2.4)
		while z <= ll - 2.4 + 0.03:
			mb.box(Vector3(x * (b - 0.3), 6.75, z), Vector3(0.9, 1.35, 2.7), dark)
			z += 2.0 * (ll - 2.4) / 3.0
		# The cabin over the outer lane, a green line at its foot, windows down the
		# side, on the inboard face and at the ends.
		var cx := x * (si + b) * 0.5
		mb.box(Vector3(cx, (lo + ct) * 0.5, 0), Vector3(b - si, ct - lo, 2.0 * hl), WHITE)
		mb.box(Vector3(cx, lo + 0.18, 0), Vector3(b - si + 0.12, 0.36, 2.0 * hl + 0.12), WSF_GREEN)
		z = -(hl - 2.7)
		while z <= hl - 2.7 + 0.03:
			mb.box(Vector3(x * b, 10.35, z), Vector3(0.3, 1.65, 3.0), WINDOW)
			z += fc.cabin_window_step()
		for zs: float in [-1.0, 1.0]:
			mb.box(Vector3(x * si, 10.35, zs * (fc.span_half_len + 0.5 * (hl - fc.span_half_len))),
				Vector3(0.3, 1.5, hl - fc.span_half_len - 2.4), WINDOW)
			mb.box(Vector3(x * (b - 2.7), 10.35, zs * hl), Vector3(3.0, 1.65, 0.3), WINDOW)
			# A clearance board on the overhang's end, yellow with black stripes.
			mb.box(Vector3(x * (si + 1.35), lo + 0.45, zs * (hl + 0.03)), Vector3(2.1, 0.6, 0.12), sign_y)
			for k in 3:
				mb.box(Vector3(x * (si + 0.6 + 0.75 * k), lo + 0.45, zs * (hl + 0.06)), Vector3(0.21, 0.6, 0.12), dark)
		# Pillars along the overhang's edge.
		for pz in fc.pillars:
			mb.box(Vector3(x * (si + 0.3), (3.0 + lo) * 0.5, pz), Vector3(0.48, lo - 3.0, 0.48), WHITE)
	# The bridge over the centre lane, with its own clearance board.
	mb.box(Vector3(0, (fc.span_y + ct) * 0.5, 0), Vector3(2.0 * si + 0.06, ct - fc.span_y, 2.0 * fc.span_half_len), WHITE)
	for zs: float in [-1.0, 1.0]:
		mb.box(Vector3(0, fc.span_y + 0.96, zs * (fc.span_half_len + 0.03)), Vector3(4.2, 0.54, 0.12), sign_y)
	# The upper deck over the cabins and the bridge (open over the lane either side
	# of it), edged green and railed all round.
	var floor_col := Color(0.5, 0.52, 0.54)
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * (si + b) * 0.5, ct + 0.12, 0), Vector3(b - si + 0.3, 0.24, 2.0 * hl + 0.3), floor_col)
		mb.box(Vector3(x * (si + b) * 0.5, ct - 0.24, 0), Vector3(b - si + 0.36, 0.48, 2.0 * hl + 0.36), WSF_GREEN)
	mb.box(Vector3(0, ct + 0.12, 0), Vector3(2.0 * si, 0.24, 2.0 * fc.span_half_len + 0.3), floor_col)
	mb.box(Vector3(0, ct - 0.24, 0), Vector3(2.0 * si, 0.48, 2.0 * fc.span_half_len + 0.36), WSF_GREEN)
	var rail := Color(0.12, 0.42, 0.3)
	for x: float in [-1.0, 1.0]:
		_rail(mb, Vector3(x * (b - 0.15), ct, -hl), Vector3(x * (b - 0.15), ct, hl), rail)
		for zs: float in [-1.0, 1.0]:
			_rail(mb, Vector3(x * (b - 0.15), ct, zs * (hl - 0.15)), Vector3(x * si, ct, zs * (hl - 0.15)), rail)
			_rail(mb, Vector3(x * si, ct, zs * (hl - 0.15)), Vector3(x * si, ct, zs * fc.span_half_len), rail)
	for zs: float in [-1.0, 1.0]:
		_rail(mb, Vector3(-si, ct, zs * fc.span_half_len), Vector3(si, ct, zs * fc.span_half_len), rail)
	# The pilothouse, windows all round so it cons either way, and its two masts.
	var wy := fc.wheel_y
	var whw := fc.wheel_half_w
	var wl := fc.wheel_half_len
	var top := wy + fc.wheel_h
	mb.box(Vector3(0, wy + fc.wheel_h * 0.5, 0), Vector3(2.0 * whw, fc.wheel_h, 2.0 * wl), WHITE)
	mb.box(Vector3(0, wy + 2.55, 0), Vector3(2.0 * whw + 0.3, 1.8, 2.0 * wl + 0.3), WINDOW_LIT)
	mb.box(Vector3(0, top - 0.3, 0), Vector3(2.0 * whw + 0.72, 0.6, 2.0 * wl + 0.72), WSF_GREEN)
	mb.box(Vector3(0, top + 0.06, 0), Vector3(2.0 * whw + 0.3, 0.15, 2.0 * wl + 0.3), WHITE)
	for zs: float in [-1.0, 1.0]:
		var mz := zs * fc.mast_z
		mb.box(Vector3(0, (top + fc.mast_top) * 0.5, mz), Vector3(0.36, fc.mast_top - top, 0.36), Color(0.3, 0.3, 0.32))
		mb.box(Vector3(0, top + 2.7, mz), Vector3(4.2, 0.18, 0.18), Color(0.3, 0.3, 0.32))
		mb.box(Vector3(0, top + 4.35, mz), Vector3(2.7, 0.15, 0.24), WHITE)
	mb.box(Vector3(whw - 0.9, top + 2.7, 0), Vector3(0.15, 5.4, 0.15), Color(0.3, 0.3, 0.32))
	# Stacks either side of the pilothouse.
	for x: float in [-1.0, 1.0]:
		var sx := x * fc.stack_dx()
		mb.box(Vector3(sx, ct + 1.05, 0), Vector3(1.8, 2.1, 2.4), WHITE)
		mb.cylinder(Vector3(sx, ct + 2.1, 0), 0.48, 0.48, fc.stack_top - ct - 3.0, 6, Color(0.3, 0.3, 0.32))
		mb.cylinder(Vector3(sx, fc.stack_top - 0.9, 0), 0.54, 0.54, 0.9, 6, Color(0.1, 0.1, 0.1))
	# The rescue boat in its cradle at one end, life-raft canisters at the others.
	var rx := b - 3.0
	mb.box(Vector3(rx, ct + 0.45, -(hl - 4.8)), Vector3(1.8, 0.9, 5.4), Color(0.55, 0.57, 0.6))
	mb.box(Vector3(rx, ct + 1.35, -(hl - 4.8)), Vector3(2.25, 0.9, 6.0), Color(0.95, 0.45, 0.12))
	mb.box(Vector3(rx, ct + 1.74, -(hl - 5.1)), Vector3(1.2, 0.36, 3.0), Color(0.2, 0.2, 0.22))
	for p: Vector3 in [Vector3(rx, 0, hl - 4.2), Vector3(-rx, 0, hl - 4.2), Vector3(-rx, 0, -(hl - 4.2))]:
		mb.cylinder(Vector3(p.x, ct + 0.24, p.z), 0.78, 0.78, 1.5, 6, WHITE)


## A concave fillet between x0 and x1: fills the corner of the (z, y) rectangle from
## (z0, y0) to (z1, y1) that lies off the quarter ellipse centred on (z1, y0), so a
## wall ending at z0 sweeps out under an overhang reaching to z1.
static func _fillet(mb: MeshBuilder, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float, col: Color) -> void:
	const STEPS := 5
	var corner := Vector2(z0, y1)
	var centre := Vector2(z1, y0)
	var arc: Array[Vector2] = []
	for i in STEPS + 1:
		var t := PI * 0.5 * i / STEPS
		arc.append(Vector2(z1 - (z1 - z0) * cos(t), y0 + (y1 - y0) * sin(t)))
	var out_x := Vector3(signf(x1 - x0), 0, 0)
	for i in STEPS:
		var a := arc[i]
		var c := arc[i + 1]
		for side: Array in [[x0, -out_x], [x1, out_x]]:
			var x: float = side[0]
			mb.tri(Vector3(x, corner.y, corner.x), Vector3(x, a.y, a.x), Vector3(x, c.y, c.x), col, side[1])
		var m := (a + c) * 0.5
		var out := Vector3(0, centre.y - m.y, centre.x - m.x)
		mb.quad(Vector3(x0, a.y, a.x), Vector3(x1, a.y, a.x), Vector3(x1, c.y, c.x), Vector3(x0, c.y, c.x), col, out)


## A railing along the deck from `a` to `b` (level, square to an axis): top and
## middle rails on posts about three metres apart.
static func _rail(mb: MeshBuilder, a: Vector3, b: Vector3, col: Color) -> void:
	var d := b - a
	var len := d.length()
	if len < 0.15:
		return
	var along_x := absf(d.x) > absf(d.z)
	var mid := (a + b) * 0.5
	for h: float in [2.7, 1.5]:
		mb.box(Vector3(mid.x, a.y + h, mid.z), Vector3(len if along_x else 0.15, 0.15, 0.15 if along_x else len), col)
	var n := maxi(1, ceili(len / 3.3))
	for i in n + 1:
		var p := a + d * (float(i) / n)
		mb.box(Vector3(p.x, a.y + 1.35, p.z), Vector3(0.15, 2.7, 0.15), col)


## A gull, about 1.4 m across (+Z forward, wings out along X, upper sides facing
## up). Wing vertices carry alpha 0.5, which seagull.gdshader flaps and folds about
## the shoulder (|x| = 0.06); it also lightens their undersides, so they are single panels.
## Gulls use the mid-poly gull modelled in Blender (MID_SEAGULL_GLB, built by
## art/seagull_mid.py), whose wing vertices also carry their folded position in UV and
## UV2.x for seagull.gdshader. The one below is the fallback: with `--classic-gull`, or
## if the model is missing (its wings fold by formula instead).
const MID_SEAGULL_GLB := "res://assets/models/seagull_mid.glb"
static var mid_seagull := not "--classic-gull" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_SEAGULL_GLB)


static func seagull() -> ArrayMesh:
	if mid_seagull:
		return _cached("seagull_mid", func(): return ModelParts.shader_mesh(MID_SEAGULL_GLB, "seagull", vc_material()))
	return _cached("seagull", func():
		var mb := MeshBuilder.new()
		var white := Color(0.95, 0.95, 0.93)
		var mantle := Color(0.66, 0.7, 0.74, 0.5)
		var tip := Color(0.12, 0.12, 0.13, 0.5)
		# Body: an octahedron stretched along the spine, and a smaller one for the head.
		_octa(mb, Vector3(0, 0.01, 0.03), Vector3(0.065, 0.065, 0.0), 0.24, -0.23, white)
		_octa(mb, Vector3(0, 0.075, 0.22), Vector3(0.045, 0.045, 0.0), 0.06, -0.05, white)
		var beak := Color(0.95, 0.74, 0.2)
		var bp := Vector3(0, 0.06, 0.36)
		var b0 := Vector3(0.016, 0.075, 0.275)
		var b1 := Vector3(-0.016, 0.075, 0.275)
		var b2 := Vector3(0, 0.05, 0.275)
		mb.tri(b0, b1, bp, beak, Vector3.UP)
		mb.tri(b1, b2, bp, beak, Vector3(-1, -1, 0))
		mb.tri(b2, b0, bp, beak, Vector3(1, -1, 0))
		mb.quad(Vector3(-0.05, 0.03, -0.16), Vector3(0.05, 0.03, -0.16), Vector3(0.075, 0.02, -0.32),
			Vector3(-0.075, 0.02, -0.32), white, Vector3.UP)
		for side: float in [-1.0, 1.0]:
			var sh_f := Vector3(0.06 * side, 0.04, 0.1)
			var sh_b := Vector3(0.06 * side, 0.04, -0.07)
			var el_f := Vector3(0.4 * side, 0.04, 0.08)
			var el_b := Vector3(0.4 * side, 0.04, -0.09)
			var mid_f := Vector3(0.58 * side, 0.04, 0.03)
			var mid_b := Vector3(0.58 * side, 0.04, -0.1)
			var end := Vector3(0.72 * side, 0.04, -0.12)
			mb.quad(sh_f, el_f, el_b, sh_b, mantle, Vector3.UP)
			mb.quad(el_f, mid_f, mid_b, el_b, mantle, Vector3.UP)
			mb.tri(mid_f, end, mid_b, tip, Vector3.UP)
		return mb.commit())


## A bald eagle at life size, 2.1 m across (+Z forward, wings out along X), modelled
## in Blender (EAGLE_GLB, built by art/eagle_mid.py) to eagle.gdshader's conventions:
## wing vertices alpha 0.5 carrying their folded pose in UV / UV2.x, legs 0.93, tail
## 0.97. Null if the model is missing (then there are no eagles).
const EAGLE_GLB := "res://assets/models/eagle_mid.glb"


static func eagle() -> ArrayMesh:
	if not ResourceLoader.exists(EAGLE_GLB):
		return null
	return _cached("eagle_mid", func(): return ModelParts.shader_mesh(EAGLE_GLB, "eagle", vc_material()))


## Orcas use the mid-poly orca modelled in Blender (MID_ORCA_GLB, built by
## art/orca_mid.py into art/orca_mid.blend) to the same rules as the one below: one
## unit long, fin base at cetacean.gdshader's FIN_BASE, fin vertex alpha = 1 - t/2 for
## height fraction t. Its body is plain black with UV = (distance from the nose,
## angle round from the back / pi), and cetacean.gdshader draws each animal's own
## markings from that (orca_markings). The one below is the fallback: with `--classic-orca`, or if the
## model is missing.
const MID_ORCA_GLB := "res://assets/models/orca_mid.glb"
static var mid_orca := not "--classic-orca" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_ORCA_GLB)


## An orca one unit long (+Z forward, nose at z = 0.5), drawn per animal by Cetaceans'
## multimesh and scaled to its length. The dorsal fin's vertices carry alpha < 1:
## cetacean.gdshader raises them to each animal's fin height and sweeps them back (a
## bull's fin stands tall and straight, a cow's is shorter and curved). It also beats
## the tail. Belly, chin, eye patch and flank are white, the saddle grey.
static func orca() -> ArrayMesh:
	if mid_orca:
		return _cached("orca_mid", func(): return ModelParts.shader_mesh(MID_ORCA_GLB, "orca", vc_material()))
	return _cached("orca", func():
		var mb := MeshBuilder.new()
		var black := Color(0.05, 0.055, 0.065)
		var white := Color(0.92, 0.93, 0.92)
		var saddle := Color(0.5, 0.52, 0.55)
		# Cross-sections nose to tail: z, half-width, half-height, centre height.
		var st := [[0.5, 0.0, 0.0, -0.01], [0.44, 0.045, 0.04, -0.005], [0.34, 0.075, 0.07, 0.0],
			[0.18, 0.095, 0.09, 0.0], [0.0, 0.095, 0.092, 0.0], [-0.16, 0.075, 0.075, 0.0],
			[-0.3, 0.045, 0.05, 0.005], [-0.4, 0.018, 0.035, 0.01], [-0.44, 0.0, 0.0, 0.01]]
		var rings: Array[PackedVector3Array] = []
		for s: Array in st:
			var ring := PackedVector3Array()
			for k in 8:
				var a := TAU * k / 8.0
				ring.append(Vector3(s[1] * sin(a), s[3] + s[2] * cos(a), s[0]))
			rings.append(ring)
		for i in st.size() - 1:
			var axis := Vector3(0, (st[i][3] + st[i + 1][3]) * 0.5, (st[i][0] + st[i + 1][0]) * 0.5)
			for k in 8:
				# Facet k runs from k * 45° (0 = the back) round to (k + 1) * 45°.
				var band := mini(k, 7 - k)   # 0 top, 1 upper side, 2 lower side, 3 belly
				var col := black
				if band == 3 and i <= 4:
					col = white
				elif band == 2 and (i <= 1 or i == 4 or i == 5):
					col = white
				elif band == 1 and i == 2:
					col = white
				elif band == 0 and i == 4:
					col = saddle
				var a := rings[i][k]
				var b := rings[i][(k + 1) % 8]
				var c := rings[i + 1][(k + 1) % 8]
				var d := rings[i + 1][k]
				mb.quad(a, b, c, d, col, (a + b + c + d) * 0.25 - axis)
		# Dorsal fin: base on the back, a waist and a tip; height and sweep come from the shader.
		var base_y := 0.085
		var bf := Vector3(0, base_y, 0.07)
		var bb := Vector3(0, base_y, -0.1)
		var mf := Vector3(0, base_y, 0.03)
		var mback := Vector3(0, base_y, -0.06)
		var tip := Vector3(0, base_y, -0.03)
		var fin_base := Color(black, 1.0)
		var fin_mid := Color(black, 0.75)
		var fin_tip := Color(black, 0.5)
		for side: float in [-1.0, 1.0]:
			var w := Vector3(0.014 * side, 0, 0)
			var wm := Vector3(0.007 * side, 0, 0)
			var out := Vector3(side, 0, 0)
			mb.tri3(bf + w, bb + w, mback + wm, fin_base, fin_base, fin_mid, out)
			mb.tri3(bf + w, mback + wm, mf + wm, fin_base, fin_mid, fin_mid, out)
			mb.tri3(mf + wm, mback + wm, tip, fin_mid, fin_mid, fin_tip, out)
			# Leading and trailing edges.
			mb.tri3(bf, bf + w, mf + wm, fin_base, fin_base, fin_mid, Vector3(side, 0, 1))
			mb.tri3(bf, mf + wm, mf, fin_base, fin_mid, fin_mid, Vector3(side, 0, 1))
			mb.tri3(mf, mf + wm, tip, fin_mid, fin_mid, fin_tip, Vector3(side, 0, 1))
			mb.tri3(bb, bb + w, mback + wm, fin_base, fin_base, fin_mid, Vector3(side, 0, -1))
			mb.tri3(bb, mback + wm, mback, fin_base, fin_mid, fin_mid, Vector3(side, 0, -1))
			mb.tri3(mback, mback + wm, tip, fin_mid, fin_mid, fin_tip, Vector3(side, 0, -1))
			# Paddle-shaped flippers, angled down and back.
			mb.tri(Vector3(0.07 * side, -0.065, 0.24), Vector3(0.21 * side, -0.12, 0.09),
				Vector3(0.07 * side, -0.07, 0.13), black, Vector3(0, -1, 0))
			# Flukes: swept-back wings off the tail stock with a notch in the middle.
			var root_f := Vector3(0, 0.01, -0.38)
			var notch := Vector3(0, 0.01, -0.46)
			var fluke_tip := Vector3(0.15 * side, 0.005, -0.52)
			mb.tri(root_f, fluke_tip, Vector3(0.05 * side, 0.01, -0.48), black, Vector3.UP)
			mb.tri(root_f, Vector3(0.05 * side, 0.01, -0.48), notch, black, Vector3.UP)
		var mesh := mb.commit()
		# The shader moves the fin and tail, which a baked shadow mesh can't follow.
		mesh.shadow_mesh = null
		return mesh)


## A whale or porpoise one unit long (+Z forward, nose at z = 0.5), built like
## the orca for cetacean.gdshader (Cetaceans scales each to its length): rings
## of 8 facets through the stations in `st` ([z, half-width, half-height, centre
## height] nose to tail), each facet coloured by `paint`(station, band, facet)
## where band 0 is the back and 3 the belly.
static func _cetacean_body(mb: MeshBuilder, st: Array, paint: Callable) -> void:
	var rings: Array[PackedVector3Array] = []
	for s: Array in st:
		var ring := PackedVector3Array()
		for k in 8:
			var a := TAU * k / 8.0
			ring.append(Vector3(s[1] * sin(a), s[3] + s[2] * cos(a), s[0]))
		rings.append(ring)
	for i in st.size() - 1:
		var axis := Vector3(0, (st[i][3] + st[i + 1][3]) * 0.5, (st[i][0] + st[i + 1][0]) * 0.5)
		for k in 8:
			var a := rings[i][k]
			var b := rings[i][(k + 1) % 8]
			var c := rings[i + 1][(k + 1) % 8]
			var d := rings[i + 1][k]
			mb.quad(a, b, c, d, paint.call(i, mini(k, 7 - k), k), (a + b + c + d) * 0.25 - axis)


## A dorsal fin for cetacean.gdshader: its base (alpha 1) stays where it's
## modelled, along the back from `front` to `back` at height `y`; the waist and
## tip (alpha < 1) are raised to the animal's fin height and swept back.
static func _cetacean_fin(mb: MeshBuilder, front: float, back: float, y: float, base: Color, tip: Color) -> void:
	var bf := Vector3(0, y, front)
	var bb := Vector3(0, y, back)
	var mf := Vector3(0, y, lerpf(front, back, 0.3))
	var mback := Vector3(0, y, lerpf(front, back, 0.82))
	var t := Vector3(0, y, lerpf(front, back, 0.62))
	var c0 := Color(base, 1.0)
	var c1 := Color(base.lerp(tip, 0.5), 0.75)
	var c2 := Color(tip, 0.5)
	var w0 := (front - back) * 0.09
	for side: float in [-1.0, 1.0]:
		var w := Vector3(w0 * side, 0, 0)
		var wm := w * 0.5
		var out := Vector3(side, 0, 0)
		mb.tri3(bf + w, bb + w, mback + wm, c0, c0, c1, out)
		mb.tri3(bf + w, mback + wm, mf + wm, c0, c1, c1, out)
		mb.tri3(mf + wm, mback + wm, t, c1, c1, c2, out)
		mb.tri3(bf, bf + w, mf + wm, c0, c0, c1, Vector3(side, 0, 1))
		mb.tri3(bf, mf + wm, mf, c0, c1, c1, Vector3(side, 0, 1))
		mb.tri3(mf, mf + wm, t, c1, c1, c2, Vector3(side, 0, 1))
		mb.tri3(bb, bb + w, mback + wm, c0, c0, c1, Vector3(side, 0, -1))
		mb.tri3(bb, mback + wm, mback, c0, c1, c1, Vector3(side, 0, -1))
		mb.tri3(mback, mback + wm, t, c1, c1, c2, Vector3(side, 0, -1))


## Flukes off the tail stock (root at z `root`), `span` either side, the tips
## back at `tip_z`, notched in the middle. Their undersides are a second skin
## just below, so they can be another colour (a humpback's are mostly white).
static func _flukes(mb: MeshBuilder, root: float, span: float, tip_z: float, top: Color, under: Color) -> void:
	var y := 0.01
	for side: float in [-1.0, 1.0]:
		var r := Vector3(0, y, root)
		var notch := Vector3(0, y, tip_z + 0.025)
		var tip := Vector3(span * side, y - 0.005, tip_z)
		var trail := Vector3(span * 0.33 * side, y, tip_z + 0.01)
		var lead := Vector3(span * 0.45 * side, y, root - (root - tip_z) * 0.45)
		for skin: Array in [[top, 0.0, Vector3.UP], [under, -0.006, Vector3.DOWN]]:
			var o := Vector3(0, skin[1], 0)
			mb.tri(r + o, lead + o, trail + o, skin[0], skin[2])
			mb.tri(lead + o, tip + o, trail + o, skin[0], skin[2])
			mb.tri(r + o, trail + o, notch + o, skin[0], skin[2])


## A flipper from `root` out to `tip`, `chord` long at the root, two-faced like
## the flukes (`top` above, `under` below).
static func _flipper(mb: MeshBuilder, root: Vector3, tip: Vector3, chord: float, top: Color, under: Color) -> void:
	for side: float in [-1.0, 1.0]:
		var s := Vector3(side, 1, 1)
		var a := root * s + Vector3(0, 0, chord * 0.5)
		var b := root * s - Vector3(0, 0, chord * 0.5)
		var t := tip * s
		var m := (root * s).lerp(t, 0.55) + Vector3(0, 0, chord * 0.25)
		for skin: Array in [[top, 0.0, Vector3.UP], [under, -0.004, Vector3.DOWN]]:
			var o := Vector3(0, skin[1], 0)
			mb.tri(a + o, m + o, b + o, skin[0], skin[2])
			mb.tri(m + o, t + o, b + o, skin[0], skin[2])


static func _spots(i: int, k: int, salt: float) -> float:
	return fposmod(sin(i * 12.9898 + k * 78.233 + salt) * 43758.5453, 1.0)


## Humpbacks and gray whales use the mid-poly ones modelled in Blender (MID_WHALES_GLB,
## built by art/whales_mid.py into art/whales_mid.blend) to the same frame and fin
## rules as the orca. The code-built ones below are the fallback: with
## `--classic-whales`, or if the model is missing.
const MID_WHALES_GLB := "res://assets/models/whales_mid.glb"
static var mid_whales := not "--classic-whales" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_WHALES_GLB)


## A humpback: long, knobbly-headed, with a small dorsal fin on a hump, very long
## pale flippers and broad flukes whose undersides are mostly white.
static func humpback() -> ArrayMesh:
	if mid_whales:
		return _cached("humpback_mid", func(): return ModelParts.shader_mesh(MID_WHALES_GLB, "humpback", vc_material()))
	return _cached("humpback", func():
		var mb := MeshBuilder.new()
		var dark := Color(0.09, 0.095, 0.11)
		var grey := Color(0.24, 0.25, 0.27)
		var pale := Color(0.82, 0.82, 0.8)
		var st := [[0.5, 0.0, 0.0, -0.025], [0.46, 0.045, 0.025, -0.012], [0.37, 0.085, 0.055, 0.0],
			[0.22, 0.108, 0.085, 0.0], [0.05, 0.112, 0.093, 0.0], [-0.12, 0.085, 0.08, 0.005],
			[-0.27, 0.048, 0.055, 0.01], [-0.38, 0.02, 0.034, 0.012], [-0.42, 0.0, 0.0, 0.012]]
		_cetacean_body(mb, st, func(i: int, band: int, k: int) -> Color:
			if band == 3 and i >= 1 and i <= 3:
				return pale.darkened(_spots(i, k, 1.0) * 0.25)
			if band == 2 and i <= 3:
				return grey.lerp(pale, 0.35 * _spots(i, k, 2.0))
			if band == 0 and i <= 1:
				# The knobs on its head.
				return dark.lightened(0.12 * _spots(i, k, 3.0))
			return dark if band < 2 else grey)
		_cetacean_fin(mb, -0.06, -0.17, 0.083, dark, dark)
		_flipper(mb, Vector3(0.09, -0.045, 0.24), Vector3(0.36, -0.14, -0.06), 0.12, grey.lerp(pale, 0.5), pale)
		_flukes(mb, -0.38, 0.19, -0.5, dark, pale)
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A gray whale: slimmer, mottled grey with pale patches of barnacles, no dorsal
## fin but a low hump and a row of knuckles down its tail stock.
static func gray_whale() -> ArrayMesh:
	if mid_whales:
		return _cached("gray_whale_mid", func(): return ModelParts.shader_mesh(MID_WHALES_GLB, "graywhale", vc_material()))
	return _cached("gray_whale", func():
		var mb := MeshBuilder.new()
		var base := Color(0.4, 0.42, 0.43)
		var light := Color(0.62, 0.63, 0.61)
		var barnacle := Color(0.8, 0.78, 0.72)
		var st := [[0.5, 0.0, 0.0, -0.03], [0.44, 0.035, 0.035, -0.02], [0.34, 0.065, 0.065, 0.0],
			[0.18, 0.09, 0.085, 0.0], [0.0, 0.095, 0.09, 0.0], [-0.16, 0.075, 0.075, 0.0],
			[-0.3, 0.042, 0.052, 0.006], [-0.4, 0.018, 0.035, 0.01], [-0.44, 0.0, 0.0, 0.01]]
		_cetacean_body(mb, st, func(i: int, band: int, k: int) -> Color:
			var r := _spots(i, k, 7.0)
			if r > 0.86 and band < 3:
				return barnacle
			return base.lerp(light, r * 0.7).darkened(0.08 * band))
		# A low hump, then knuckles along the ridge of the tail stock.
		_cetacean_fin(mb, -0.08, -0.16, 0.08, base, base)
		var z := -0.19
		while z > -0.38:
			var t := (z + 0.16) / -0.24
			var y := lerpf(0.074, 0.044, t)
			mb.tri(Vector3(-0.01, y - 0.004, z + 0.012), Vector3(0.01, y - 0.004, z + 0.012), Vector3(0, y + 0.012, z), base, Vector3(0, 1, 1))
			mb.tri(Vector3(-0.01, y - 0.004, z - 0.012), Vector3(0.01, y - 0.004, z - 0.012), Vector3(0, y + 0.012, z), base, Vector3(0, 1, -1))
			z -= 0.035
		_flipper(mb, Vector3(0.07, -0.05, 0.25), Vector3(0.19, -0.11, 0.12), 0.06, base, light)
		_flukes(mb, -0.39, 0.15, -0.51, base, light)
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A Dall's porpoise: stocky and black with a big white patch on each flank,
## a triangular fin frosted at the tip.
static func dalls_porpoise() -> ArrayMesh:
	return _cached("dalls_porpoise", func():
		var mb := MeshBuilder.new()
		var black := Color(0.04, 0.045, 0.05)
		var white := Color(0.92, 0.93, 0.92)
		var st := [[0.5, 0.0, 0.0, -0.01], [0.45, 0.04, 0.04, 0.0], [0.36, 0.085, 0.085, 0.0],
			[0.18, 0.115, 0.108, 0.0], [0.0, 0.115, 0.11, 0.0], [-0.15, 0.085, 0.09, 0.005],
			[-0.3, 0.035, 0.065, 0.01], [-0.4, 0.015, 0.035, 0.01], [-0.44, 0.0, 0.0, 0.01]]
		_cetacean_body(mb, st, func(i: int, band: int, _k: int) -> Color:
			if band >= 2 and i >= 3 and i <= 4:
				return white
			return black)
		_cetacean_fin(mb, 0.04, -0.12, 0.105, black, Color(0.75, 0.77, 0.78))
		_flipper(mb, Vector3(0.08, -0.06, 0.25), Vector3(0.17, -0.12, 0.15), 0.06, black, black)
		_flukes(mb, -0.38, 0.13, -0.49, black, black)
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A harbor porpoise: small and round-headed, dark grey above, paler below, with
## a little triangular fin.
static func harbor_porpoise() -> ArrayMesh:
	return _cached("harbor_porpoise", func():
		var mb := MeshBuilder.new()
		var dark := Color(0.17, 0.18, 0.2)
		var side := Color(0.42, 0.43, 0.44)
		var belly := Color(0.85, 0.85, 0.83)
		var st := [[0.5, 0.0, 0.0, -0.01], [0.45, 0.045, 0.045, 0.0], [0.35, 0.08, 0.08, 0.0],
			[0.18, 0.1, 0.1, 0.0], [0.0, 0.1, 0.1, 0.0], [-0.16, 0.075, 0.08, 0.0],
			[-0.3, 0.035, 0.05, 0.005], [-0.4, 0.015, 0.03, 0.01], [-0.44, 0.0, 0.0, 0.01]]
		_cetacean_body(mb, st, func(_i: int, band: int, _k: int) -> Color:
			return [dark, dark, side, belly][band])
		_cetacean_fin(mb, 0.02, -0.11, 0.095, dark, dark)
		_flipper(mb, Vector3(0.07, -0.06, 0.25), Vector3(0.16, -0.11, 0.16), 0.05, dark, dark)
		_flukes(mb, -0.38, 0.12, -0.48, dark, dark)
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A seal or sea lion one unit long (+Z forward, nose at z = 0.5) lying on its
## belly, the bottom of its belly at y = 0; drawn per animal by Pinnipeds and
## posed by pinniped.gdshader (head up, hind flippers up, swimming sway or the
## arch of a seal humping along on land). Rings of 8 facets through the stations
## `st` ([z, half-width, half-height, centre height]), coloured by
## `paint`(station, band, facet), band 0 the back and 3 the belly.
static func _pinniped_body(mb: MeshBuilder, st: Array, paint: Callable) -> void:
	_cetacean_body(mb, st, paint)
	# Close off the tail end (the flippers fan out from it).
	var last: Array = st[st.size() - 1]
	if last[1] > 0.0:
		var c := Vector3(0, last[3], last[0] - 0.01)
		for k in 8:
			var a0 := TAU * k / 8.0
			var a1 := TAU * (k + 1) / 8.0
			mb.tri(Vector3(last[1] * sin(a0), last[3] + last[2] * cos(a0), last[0]),
				Vector3(last[1] * sin(a1), last[3] + last[2] * cos(a1), last[0]), c, paint.call(st.size() - 2, mini(k, 7 - k), k), Vector3.FORWARD)


## Hind flippers: two webbed fans off the tail, toes spread.
static func _hind_flippers(mb: MeshBuilder, root_z: float, y: float, tip_z: float, spread: float, col: Color) -> void:
	for side: float in [-1.0, 1.0]:
		var r := Vector3(0.012 * side, y, root_z)
		var outer := Vector3(spread * side, y - 0.004, tip_z)
		var inner := Vector3(spread * 0.25 * side, y - 0.004, tip_z + 0.02)
		var mid := Vector3(spread * 0.6 * side, y - 0.002, tip_z + 0.035)
		mb.tri(r, outer, mid, col, Vector3.UP)
		mb.tri(r, mid, inner, col, Vector3.UP)


## An eye on each side of the head, and the nose.
static func _face(mb: MeshBuilder, eye: Vector3, r: float, nose: Vector3) -> void:
	var black := Color(0.03, 0.03, 0.035)
	for side: float in [-1.0, 1.0]:
		var c := Vector3(eye.x * side, eye.y, eye.z)
		var o := Vector3(side * 0.004, 0, 0)
		mb.quad(c + o + Vector3(0, -r, r), c + o + Vector3(0, -r, -r), c + o + Vector3(0, r, -r), c + o + Vector3(0, r, r),
			black, Vector3(side, 0.2, 0.3))
	mb.tri(nose + Vector3(-0.012, 0.004, 0), nose + Vector3(0.012, 0.004, 0), nose + Vector3(0, -0.012, 0.004), black, Vector3(0, 0.3, 1))


## Seals and sea lions use the mid-poly ones modelled in Blender (MID_PINNIPEDS_GLB,
## built by art/pinnipeds_mid.py into art/pinnipeds_mid.blend) to the same frame and
## bend points. The code-built ones below are the fallback: with `--classic-seals`, or if
## the model is missing.
const MID_PINNIPEDS_GLB := "res://assets/models/pinnipeds_mid.glb"
static var mid_pinnipeds := not "--classic-seals" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_PINNIPEDS_GLB)


## A harbor seal: rotund, no neck to speak of, short flippers, a dog-like face
## with big dark eyes. Pale grey and heavily spotted (the instance colour tints
## it silver, tawny or dark).
static func harbor_seal() -> ArrayMesh:
	if mid_pinnipeds:
		return _cached("harbor_seal_mid", func(): return ModelParts.shader_mesh(MID_PINNIPEDS_GLB, "harborseal", vc_material()))
	return _cached("harbor_seal", func():
		var mb := MeshBuilder.new()
		var coat := Color(0.86, 0.85, 0.82)
		var spot := Color(0.42, 0.41, 0.4)
		var belly := Color(0.95, 0.94, 0.9)
		var st := [[0.5, 0.0, 0.0, 0.07], [0.47, 0.033, 0.028, 0.07], [0.43, 0.052, 0.046, 0.076],
			[0.37, 0.066, 0.058, 0.08], [0.3, 0.08, 0.07, 0.08], [0.18, 0.11, 0.098, 0.098],
			[0.03, 0.124, 0.108, 0.108], [-0.14, 0.1, 0.088, 0.088], [-0.28, 0.058, 0.056, 0.06],
			[-0.37, 0.028, 0.03, 0.046]]
		_pinniped_body(mb, st, func(i: int, band: int, k: int) -> Color:
			if band == 3 and i >= 4:
				return belly
			# Dappled: every facet a little darker or lighter.
			return coat.lerp(spot, _spots(i, k, 11.0) * 0.45) if i >= 2 else coat)
		_face(mb, Vector3(0.042, 0.095, 0.43), 0.011, Vector3(0, 0.072, 0.498))
		_hind_flippers(mb, -0.36, 0.045, -0.52, 0.075, spot)
		# Short fore flippers, tucked along the chest.
		for side: float in [-1.0, 1.0]:
			mb.tri(Vector3(0.1 * side, 0.035, 0.22), Vector3(0.105 * side, 0.03, 0.14),
				Vector3(0.15 * side, 0.004, 0.13), spot, Vector3(side, 1, 0))
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A California sea lion: sleeker, a real neck, a narrow pointed snout with
## little ear flaps, and long fore flippers it props itself up on. Brown, darker
## along the back (the instance colour tints bulls dark, females golden).
static func sea_lion() -> ArrayMesh:
	if mid_pinnipeds:
		return _cached("sea_lion_mid", func(): return ModelParts.shader_mesh(MID_PINNIPEDS_GLB, "sealion", vc_material()))
	return _cached("sea_lion", func():
		var mb := MeshBuilder.new()
		var coat := Color(0.86, 0.84, 0.8)
		var back := Color(0.72, 0.7, 0.67)
		var muzzle := Color(0.95, 0.93, 0.88)
		var flipper := Color(0.45, 0.43, 0.42)
		var st := [[0.5, 0.0, 0.0, 0.125], [0.465, 0.022, 0.022, 0.125], [0.41, 0.043, 0.043, 0.132],
			[0.34, 0.05, 0.05, 0.128], [0.26, 0.066, 0.068, 0.11], [0.13, 0.108, 0.1, 0.1],
			[-0.02, 0.112, 0.098, 0.098], [-0.17, 0.082, 0.078, 0.078], [-0.29, 0.044, 0.048, 0.05],
			[-0.35, 0.024, 0.028, 0.034]]
		_pinniped_body(mb, st, func(i: int, band: int, _k: int) -> Color:
			if i <= 1:
				return muzzle
			return back if band == 0 else coat)
		_face(mb, Vector3(0.038, 0.148, 0.415), 0.009, Vector3(0, 0.128, 0.497))
		# Ear flaps.
		for side: float in [-1.0, 1.0]:
			mb.tri(Vector3(0.045 * side, 0.16, 0.36), Vector3(0.05 * side, 0.165, 0.345),
				Vector3(0.055 * side, 0.15, 0.335), flipper, Vector3(side, 0, -1))
		_hind_flippers(mb, -0.34, 0.03, -0.5, 0.07, flipper)
		# Long fore flippers, out to the side and down to the ground.
		for side: float in [-1.0, 1.0]:
			var r0 := Vector3(0.095 * side, 0.05, 0.17)
			var r1 := Vector3(0.1 * side, 0.045, 0.07)
			var tip := Vector3(0.25 * side, 0.0, -0.02)
			var mid := Vector3(0.18 * side, 0.015, 0.1)
			mb.tri(r0, mid, r1, flipper, Vector3.UP)
			mb.tri(mid, tip, r1, flipper, Vector3.UP)
		var mesh := mb.commit()
		mesh.shadow_mesh = null
		return mesh)


## A blow or a splash: a white plume one unit tall, drawn per puff by Cetaceans.
static func spout() -> ArrayMesh:
	return _cached("spout", func():
		var mb := MeshBuilder.new()
		mb.cylinder(Vector3.ZERO, 0.12, 0.45, 0.6, 6, Color(0.95, 0.97, 1.0, 0.85))
		mb.cylinder(Vector3(0, 0.6, 0), 0.45, 0.2, 0.4, 6, Color(0.95, 0.97, 1.0, 0.6))
		return mb.commit(unshaded_material()))


## An octahedron at `c`, `r` wide (x) and tall (y), reaching `front` ahead and `back` behind.
static func _octa(mb: MeshBuilder, c: Vector3, r: Vector3, front: float, back: float, col: Color) -> void:
	var f := c + Vector3(0, 0, front)
	var b := c + Vector3(0, 0, back)
	var ring := [c + Vector3(r.x, 0, 0), c + Vector3(0, r.y, 0), c + Vector3(-r.x, 0, 0), c + Vector3(0, -r.y, 0)]
	for i in 4:
		var p0: Vector3 = ring[i]
		var p1: Vector3 = ring[(i + 1) % 4]
		var out := (p0 + p1) * 0.5 - c
		mb.tri(p0, p1, f, col, out)
		mb.tri(p1, p0, b, col, out)


## Head and tail lights for every car and truck (+Z is the front), plus the cone
## they throw down the road. Drawn per vehicle by NightLights' multimesh.
static func car_lights() -> ArrayMesh:
	return _cached("car_lights", func():
		var gb := GlowBuilder.new()
		for x: float in [-0.32, 0.32]:
			gb.glow(Vector3(x, 0.5, 1.08), GlowBuilder.HEADLIGHT, 0.14, 7.0, false, 0.0, Vector3.BACK, 0.0)
			gb.glow(Vector3(x * 1.1, 0.55, -1.14), GlowBuilder.TAIL, 0.11, 5.0, false, 0.0, Vector3.FORWARD, 0.0)
		gb.cone(Vector3(0, 0.1, 1.4), Vector3.BACK, 9.0, 2.2, GlowBuilder.HEADLIGHT, 0.4)
		return gb.commit())


## The same for vehicle `model` (a VehicleData key; "" is the code-built car and truck),
## its lamps where the model has them.
static func vehicle_lights(model: String) -> ArrayMesh:
	if model == "":
		return car_lights()
	return _cached("lights_" + model, func():
		var d: Dictionary = VehicleData.VARIANTS[model]
		var head: Vector3 = d.head
		var tail: Vector3 = d.tail
		var trailer := d.has("pin")  # (no headlamps)
		var gb := GlowBuilder.new()
		for sx: float in [-1.0, 1.0]:
			if not trailer:
				gb.glow(Vector3(head.x * sx, head.y, head.z + 0.03), GlowBuilder.HEADLIGHT, 0.33, 7.0, false, 0.0,
					Vector3.BACK, 0.0)
			gb.glow(Vector3(tail.x * sx, tail.y, tail.z - 0.03), GlowBuilder.TAIL, 0.26, 5.0, false, 0.0,
				Vector3.FORWARD, 0.0)
		if not trailer:
			gb.cone(Vector3(0, 0.25, head.z + 0.3), Vector3.BACK, 21.0, 5.2, GlowBuilder.HEADLIGHT, 0.4)
		return gb.commit())


## Lights of ferry class `fc` in the hull's frame: masthead lights, red / green
## sidelights, the deck lamps, and the lit windows' reflections on the water.
static func ferry_lights(fc: FerryClass) -> ArrayMesh:
	return _cached("ferry_lights_%d" % fc.size, func():
		var gb := GlowBuilder.new()
		for p in fc.lanterns:
			gb.glow(lantern_glow_at(p, fc.lantern_scale), GlowBuilder.LED, 0.3 * fc.lantern_scale / FERRY_LANTERN, 9.0, true, 0.0, Vector3.ZERO, 0.0)
		for sl: Array in fc.sidelights:
			gb.nav(sidelight_glow_at(sl[0], sl[1], fc.sidelight_scale), 0.22 * fc.sidelight_scale / FERRY_SIDELIGHT_SCALE, 7.0,
				Vector3(sl[1], 0, sl[2] * 0.8))
		for lp: Array in fc.lamps:
			gb.glow(bulkhead_glow_at(lp[0], lp[1], fc.lamp_scale), GlowBuilder.WARM, bulkhead_glow_size(fc.lamp_scale),
				4.0, true, 0.0, lp[1], 0.0)
		var window := Color(1.0, 0.74, 0.42)
		for w: Array in fc.windows:
			gb.reflection(w[0], window, w[1], w[2], w[3])
		if fc.issaquah:
			for c in _mid_car_deck_lights(FerryClass.ISQ_GLB):
				# Each pool on the deck under its lens: the tween deck's, a ramp's or the main deck.
				var floor := FerryClass.ISQ_CAR_DECK
				var ax := absf(c.x)
				var az := absf(c.z)
				if c.y > 6.0 and ax > 5.05:
					if az < FerryClass.ISQ_MEZ_Z:
						floor = FerryClass.ISQ_MEZ_TOP
					elif ax > FerryClass._isq_ramp_edge(az) and FerryClass._isq_ramp_edge(az) > 0.0:
						floor = lerpf(FerryClass.ISQ_MEZ_TOP, FerryClass.ISQ_CAR_DECK,
							(az - FerryClass.ISQ_MEZ_Z) / (FerryClass.ISQ_RAMP_Z - FerryClass.ISQ_MEZ_Z))
				var w := clampf(FerryClass._isq_beam(c.z) - 0.6 - ax, 1.0, CAR_DECK_POOL.x)
				gb.pool(FerryClass._isq(c.x, floor + 0.03, c.z), CAR_DECK_LIGHT,
					w * FerryClass.MID_SCALE, CAR_DECK_POOL_ENERGY, LAMP_ON_AT, CAR_DECK_POOL.y * FerryClass.MID_SCALE)
		if fc.evergreen:
			for c in _mid_car_deck_lights():
				# Kept inside the hull sides, or the wings' pools spill out over the water.
				var w := clampf(FerryClass._mid_beam(c.z) - 0.6 - absf(c.x), 1.0, CAR_DECK_POOL.x)
				gb.pool(FerryClass._mid(c.x, FerryClass.MID_CAR_DECK + 0.03, c.z), CAR_DECK_LIGHT,
					w * FerryClass.MID_SCALE, CAR_DECK_POOL_ENERGY, LAMP_ON_AT, CAR_DECK_POOL.y * FerryClass.MID_SCALE)
		return gb.commit())


## Where the Evergreen State's car deck lights are (her metres, x and z): the centres
## of the model's `lamp` lenses, which lie well apart.
static func _mid_car_deck_lights(glb := FerryClass.MID_GLB) -> PackedVector3Array:
	var p := ModelParts.merge_named(glb, ["lamp"])
	var sums := PackedVector3Array()
	var counts := PackedInt32Array()
	for v in p.verts:
		var j := 0
		while j < sums.size() and (v - sums[j] / counts[j]).length() > 1.5:
			j += 1
		if j == sums.size():
			sums.append(Vector3.ZERO)
			counts.append(0)
		sums[j] += v
		counts[j] += 1
	var out := PackedVector3Array()
	for j in sums.size():
		out.append(sums[j] / counts[j])
	return out


## Sailboats use the mid-poly sloop modelled in Blender (MID_SAILBOAT_GLB, source
## art/sailboat_mid.blend). The original code-built sloop below is the fallback: with
## the `--classic-sailboat` launch flag, or if the model is missing.
const MID_SAILBOAT_GLB := "res://assets/models/sailboat_mid.glb"
static var mid_sailboat := not "--classic-sailboat" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_SAILBOAT_GLB)
const MID_SAILBOAT_HULL := ["hull", "deckfittings", "keel", "mast", "rigging"]
# The mid-poly jib sets on a real forestay, so it hinges on a different line.
const MID_JIB_TACK := Vector3(0, 0.62, 1.976)
const MID_JIB_HEAD := Vector3(0, 3.55, 0.391)


static func jib_tack() -> Vector3:
	return MID_JIB_TACK if mid_sailboat else SAIL_JIB_TACK


static func jib_head() -> Vector3:
	return MID_JIB_HEAD if mid_sailboat else SAIL_JIB_HEAD


## The hull's outline where it meets the water, as seen from above: the glTF part
## `part` (waterline at y = 0, z along its length) from its waterline up to `top`,
## taking in any flare or guard overhanging the water. Its half length, then `n`
## half-widths at stations evenly spaced from tip to tip (all model metres). Both
## ends are taken as the wider of the two, for double-enders.
static var _waterlines := {}


static func waterline(path: String, part: String, n: int, top: float) -> PackedFloat32Array:
	var key := "%s:%s:%d:%f" % [path, part, n, top]
	if _waterlines.has(key):
		return _waterlines[key]
	var mb := ModelParts.merge_named(path, [part])
	# Fine bins over |z|, each holding the widest |x| the hull reaches there. A
	# triangle's widest point within the slab lies on its edges clipped to it, or
	# where the slab's faces cut it.
	const BIN := 0.05
	var bins := PackedFloat32Array()
	var v := mb.verts
	for t in range(0, v.size() - 2, 3):
		var segs: Array[Vector3] = []
		for y: float in [0.0, top]:
			var cut: Array[Vector3] = []
			for e in 3:
				var a := v[t + e]
				var b := v[t + (e + 1) % 3]
				if (a.y < y) != (b.y < y):
					cut.append(a.lerp(b, (a.y - y) / (a.y - b.y)))
			if cut.size() == 2:
				segs.append_array(cut)
		for e in 3:
			var a := v[t + e]
			var b := v[t + (e + 1) % 3]
			if minf(a.y, b.y) > top or maxf(a.y, b.y) < 0.0:
				continue
			var dy := b.y - a.y
			var u0 := 0.0
			var u1 := 1.0
			if absf(dy) > 1e-6:
				u0 = clampf(minf(-a.y / dy, (top - a.y) / dy), 0.0, 1.0)
				u1 = clampf(maxf(-a.y / dy, (top - a.y) / dy), 0.0, 1.0)
			segs.append_array([a.lerp(b, u0), a.lerp(b, u1)])
		for k in range(0, segs.size(), 2):
			var steps := maxi(1, ceili(segs[k].distance_to(segs[k + 1]) / (BIN * 0.5)))
			for s in steps + 1:
				var p := segs[k].lerp(segs[k + 1], float(s) / steps)
				var i := roundi(absf(p.z) / BIN)
				if i >= bins.size():
					bins.resize(i + 1)
				bins[i] = maxf(bins[i], absf(p.x))
	var half := (bins.size() - 1) * BIN
	var out := PackedFloat32Array([half])
	for k in n:
		var i := roundi(absf(k / float(n - 1) * 2.0 - 1.0) * half / BIN)
		# The widest within a bin either side, so no station falls in a gap.
		var w := 0.0
		for j in range(maxi(i - 1, 0), mini(i + 2, bins.size())):
			w = maxf(w, bins[j])
		out.append(w)
	_waterlines[key] = out
	return out


static func sailboat() -> ArrayMesh:
	if mid_sailboat:
		return _cached("sailboat_mid", func():
			var mb := ModelParts.merge_named(MID_SAILBOAT_GLB, MID_SAILBOAT_HULL)
			add_lantern(mb, SAIL_MAST_TOP, GlowBuilder.LED, SAIL_LANTERN)
			return mb.commit())
	return _cached("sailboat", func():
		var mb := MeshBuilder.new()
		var hull := PackedVector2Array([Vector2(-0.6, -1.6), Vector2(0.6, -1.6), Vector2(0.65, 0.6), Vector2(0.0, 2.0), Vector2(-0.65, 0.6)])
		mb.extrude(hull, -0.3, 0.35, WHITE, Color(0.75, 0.62, 0.45), 0.7)
		mb.box(Vector3(0, 2.3, 0.3), Vector3(0.08, 4.0, 0.08), Color(0.8, 0.8, 0.8))
		add_lantern(mb, SAIL_MAST_TOP, GlowBuilder.LED, SAIL_LANTERN)
		return mb.commit())


# The sails, each built round the line it swings on (Sailboat sheets them out
# to leeward): the mainsail and boom round the mast, the jib round its forestay.
const SAIL_MAIN_PIVOT := Vector3(0, 0, 0.2)
const SAIL_JIB_TACK := Vector3(0, 0.8, 1.7)
const SAIL_JIB_HEAD := Vector3(0, 3.6, 0.35)


static func sailboat_main() -> ArrayMesh:
	if mid_sailboat:
		return _cached("sailboat_main_mid", func(): return ModelParts.merge_named(MID_SAILBOAT_GLB, ["mainsail"]).commit())
	return _cached("sailboat_main", func():
		var mb := MeshBuilder.new()
		var a := Vector3(0, 0.7, 0)
		var b := Vector3(0, 4.2, 0)
		var c := Vector3(0, 0.7, -1.6)
		mb.tri(a, b, c, Color(0.98, 0.98, 0.96), Vector3.RIGHT)
		mb.tri(a, b, c, Color(0.98, 0.98, 0.96), Vector3.LEFT)
		mb.box(Vector3(0, 0.66, -0.8), Vector3(0.07, 0.07, 1.7), Color(0.8, 0.8, 0.8))
		return mb.commit())


static func sailboat_jib() -> ArrayMesh:
	if mid_sailboat:
		return _cached("sailboat_jib_mid", func(): return ModelParts.merge_named(MID_SAILBOAT_GLB, ["jib"]).commit())
	return _cached("sailboat_jib", func():
		var mb := MeshBuilder.new()
		var head := SAIL_JIB_HEAD - SAIL_JIB_TACK
		var clew := Vector3(0, 0.8, 0.4) - SAIL_JIB_TACK
		mb.tri(head, clew, Vector3.ZERO, Color(0.95, 0.95, 0.9), Vector3.RIGHT)
		mb.tri(head, clew, Vector3.ZERO, Color(0.95, 0.95, 0.9), Vector3.LEFT)
		return mb.commit())


## The sailboat at its berth: sails stowed along the boom.
static func sailboat_furled() -> ArrayMesh:
	if mid_sailboat:
		return _cached("sailboat_furled_mid", func():
			var mb := ModelParts.merge_named(MID_SAILBOAT_GLB, MID_SAILBOAT_HULL + ["furled"])
			add_lantern(mb, SAIL_MAST_TOP, GlowBuilder.LED, SAIL_LANTERN)
			return mb.commit())
	return _cached("sailboat_furled", func():
		var mb := MeshBuilder.new()
		var hull := PackedVector2Array([Vector2(-0.6, -1.6), Vector2(0.6, -1.6), Vector2(0.65, 0.6), Vector2(0.0, 2.0), Vector2(-0.65, 0.6)])
		mb.extrude(hull, -0.3, 0.35, WHITE, Color(0.75, 0.62, 0.45), 0.7)
		mb.box(Vector3(0, 2.3, 0.3), Vector3(0.08, 4.0, 0.08), Color(0.8, 0.8, 0.8))
		mb.box(Vector3(0, 0.78, -0.55), Vector3(0.07, 0.07, 1.8), Color(0.8, 0.8, 0.8))
		mb.box(Vector3(0, 0.9, -0.5), Vector3(0.2, 0.18, 1.6), Color(0.2, 0.32, 0.5))
		add_lantern(mb, SAIL_MAST_TOP, GlowBuilder.LED, SAIL_LANTERN)
		return mb.commit())


## The sailboat's anchor light, drawn by NightLights on each boat.
static func sailboat_lights() -> ArrayMesh:
	return _cached("sailboat_lights", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(SAIL_MAST_TOP, SAIL_LANTERN), GlowBuilder.LED, 0.13, 4.0, true, 0.0, Vector3.ZERO, LAMP_ON_AT)
		return gb.commit())


# Container ship (+Z is the bow): masthead lantern heights and the sidelights.
const CARGO_FORE_MAST := Vector3(0, 9.0, 28.5)
const CARGO_AFT_MAST := Vector3(0, 15.6, -24.0)
const CARGO_LANTERN := 1.6
const CARGO_SIDELIGHT := Vector3(6.3, 11.6, -24.0)
const CARGO_FUNNELS := [Color(0.85, 0.55, 0.12), Color(0.15, 0.35, 0.65), Color(0.75, 0.15, 0.13)]
const CONTAINERS := [Color(0.62, 0.2, 0.15), Color(0.18, 0.33, 0.6), Color(0.2, 0.48, 0.32),
	Color(0.88, 0.5, 0.15), Color(0.55, 0.57, 0.6), Color(0.14, 0.5, 0.55), Color(0.9, 0.9, 0.86),
	Color(0.85, 0.7, 0.2), Color(0.45, 0.25, 0.4)]


## A container ship about 64 m long and 11 m in the beam, its accommodation block
## aft. `variant` picks the funnel colour and how the boxes are stacked.
static func cargo_ship(variant: int) -> ArrayMesh:
	if mid_cargo:
		return _cached("cargo_mid_%d" % variant, func(): return _mid_cargo(variant).commit())
	return _cached("cargo_%d" % variant, func():
		var mb := MeshBuilder.new()
		var topsides := Color(0.12, 0.16, 0.24)
		_cargo_hull(mb, topsides, Color(0.4, 0.42, 0.43), CARGO_FUNNELS[variant % CARGO_FUNNELS.size()])
		# Containers: seven bays of four stacks, one to three high.
		var r := RandomNumberGenerator.new()
		r.seed = 4111 + variant * 97
		for bay in 7:
			var z := -18.5 + bay * 6.2
			for col in 4:
				var x := -3.75 + col * 2.5
				var tiers := r.randi_range(1, 3) if variant % 3 != 2 else r.randi_range(2, 3)
				for t in tiers:
					var c: Color = CONTAINERS[r.randi_range(0, CONTAINERS.size() - 1)]
					mb.box(Vector3(x, 3.2 + 1.25 + t * 2.5, z), Vector3(2.4, 2.45, 6.0), c.darkened(r.randf() * 0.12))
		return mb.commit())


# Tankers: dark topsides over a deck painted green or oxide red, by variant.
const TANKER_TOPSIDES := [Color(0.1, 0.1, 0.11), Color(0.42, 0.11, 0.1), Color(0.12, 0.2, 0.3)]
const TANKER_DECKS := [Color(0.3, 0.42, 0.3), Color(0.3, 0.42, 0.3), Color(0.5, 0.22, 0.17)]
const TANKER_FUNNELS := [Color(0.85, 0.15, 0.12), Color(0.92, 0.92, 0.9), Color(0.9, 0.72, 0.18)]


## Tankers and bulk carriers use mid-poly models on the container ship's hull too
## (art/tanker_mid.py and art/bulker_mid.py build them on art/cargo_mid.py), so they
## share its lights and its name's place on the bows; the code-built ones below are
## the fallbacks, as for the container ship.
const MID_TANKER_GLB := "res://assets/models/tanker_mid.glb"
const MID_BULKER_GLB := "res://assets/models/bulker_mid.glb"
# The band on the mid-poly ships' white funnels.
const MID_TANKER_FUNNELS := [Color(0.8, 0.14, 0.12), Color(0.12, 0.3, 0.55), Color(0.9, 0.72, 0.18)]


## A tanker on the same hull as the container ship: a flat deck with its cargo
## lines and the catwalk running fore and aft, the manifold and its hose crane
## amidships.
static func tanker(variant: int) -> ArrayMesh:
	if mid_tanker:
		return _cached("tanker_mid_%d" % variant, func(): return _mid_cargo_ship(MID_TANKER_GLB, {
			"hull": TANKER_TOPSIDES[variant % TANKER_TOPSIDES.size()],
			"deck": TANKER_DECKS[variant % TANKER_DECKS.size()],
			"funnel": MID_TANKER_FUNNELS[variant % MID_TANKER_FUNNELS.size()]}).commit())
	return _cached("tanker_%d" % variant, func():
		var mb := MeshBuilder.new()
		var deck: Color = TANKER_DECKS[variant % TANKER_DECKS.size()]
		_cargo_hull(mb, TANKER_TOPSIDES[variant % TANKER_TOPSIDES.size()], deck,
			TANKER_FUNNELS[variant % TANKER_FUNNELS.size()])
		var pipe := Color(0.62, 0.64, 0.6)
		var steel := Color(0.3, 0.32, 0.33)
		var z0 := -21.6
		var z1 := 22.8
		var zc := (z0 + z1) * 0.5
		var span := z1 - z0
		# Cargo lines along the deck either side of the centreline.
		for x: float in [-2.0, -1.4, 1.4, 2.0]:
			mb.box(Vector3(x, 3.5, zc), Vector3(0.3, 0.3, span), pipe)
		# The catwalk on its posts, high over the lines.
		mb.box(Vector3(0, 5.0, zc), Vector3(1.1, 0.12, span), WHITE)
		for i in 9:
			mb.box(Vector3(0, 4.1, z0 + 1.0 + i * (span - 2.0) / 8.0), Vector3(0.2, 1.8, 0.2), WHITE)
		# Tank hatches and vent posts down either side.
		for i in 6:
			var z := -17.0 + i * 7.0
			for x: float in [-3.6, 3.6]:
				mb.cylinder(Vector3(x, 3.2, z), 0.55, 0.55, 0.4, 8, steel)
				mb.box(Vector3(x * 0.8, 4.0, z + 2.0), Vector3(0.16, 1.6, 0.16), pipe)
		# The manifold athwartships, with its hose crane.
		for dz: float in [-0.6, 0.6]:
			mb.box(Vector3(0, 3.6, dz), Vector3(10.4, 0.36, 0.36), pipe)
		for x: float in [-5.0, 5.0]:
			mb.box(Vector3(x, 3.9, 0), Vector3(0.6, 1.1, 2.0), steel)
		mb.cylinder(Vector3(0, 3.2, -2.6), 0.4, 0.35, 4.4, 8, Color(0.88, 0.72, 0.2))
		var a := Vector3(0, 7.4, -2.6)
		var b := Vector3(3.6, 4.6, 3.0)
		mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
		mb.box(Vector3.ZERO, Vector3(0.36, 0.36, a.distance_to(b)), Color(0.88, 0.72, 0.2))
		mb.xform = Transform3D.IDENTITY
		# Fire monitors on their platform before the bridge.
		mb.box(Vector3(0, 5.6, -20.2), Vector3(4.0, 0.15, 1.4), WHITE)
		for x: float in [-1.4, 1.4]:
			mb.box(Vector3(x, 5.9, -20.2), Vector3(0.3, 0.5, 0.6), Color(0.75, 0.15, 0.13))
		return mb.commit())


# Bulk carriers: topsides, hatch covers and deck cranes, by variant.
const BULKER_TOPSIDES := [Color(0.14, 0.22, 0.34), Color(0.2, 0.21, 0.22), Color(0.48, 0.15, 0.12)]
const BULKER_HATCHES := [Color(0.55, 0.18, 0.14), Color(0.2, 0.42, 0.3), Color(0.18, 0.3, 0.5)]
const BULKER_CRANES := [Color(0.9, 0.74, 0.2), Color(0.92, 0.92, 0.9), Color(0.9, 0.74, 0.2)]
const BULKER_FUNNELS := [Color(0.15, 0.35, 0.65), Color(0.85, 0.55, 0.12), Color(0.94, 0.95, 0.94)]
# The mid-poly bulkers' deck and coamings, and the band on their white funnels.
const MID_BULKER_DECKS := [Color(0.32, 0.37, 0.34), Color(0.45, 0.2, 0.16), Color(0.36, 0.38, 0.38)]
const MID_BULKER_FUNNELS := [Color(0.15, 0.35, 0.65), Color(0.85, 0.55, 0.12), Color(0.1, 0.1, 0.11)]


## A geared bulk carrier on the same hull: five big hatches under folding
## covers, and four deck cranes between them with their jibs stowed forward.
static func bulk_carrier(variant: int) -> ArrayMesh:
	if mid_bulker:
		return _cached("bulker_mid_%d" % variant, func(): return _mid_cargo_ship(MID_BULKER_GLB, {
			"hull": BULKER_TOPSIDES[variant % BULKER_TOPSIDES.size()],
			"deck": MID_BULKER_DECKS[variant % MID_BULKER_DECKS.size()],
			"hatch": BULKER_HATCHES[variant % BULKER_HATCHES.size()],
			"crane": BULKER_CRANES[variant % BULKER_CRANES.size()],
			"funnel": MID_BULKER_FUNNELS[variant % MID_BULKER_FUNNELS.size()]}).commit())
	return _cached("bulker_%d" % variant, func():
		var mb := MeshBuilder.new()
		var topsides: Color = BULKER_TOPSIDES[variant % BULKER_TOPSIDES.size()]
		var hatch: Color = BULKER_HATCHES[variant % BULKER_HATCHES.size()]
		var crane: Color = BULKER_CRANES[variant % BULKER_CRANES.size()]
		_cargo_hull(mb, topsides, Color(0.45, 0.2, 0.16), BULKER_FUNNELS[variant % BULKER_FUNNELS.size()])
		var hatch_z := [-17.0, -8.2, 0.6, 9.4, 18.2]
		for z: float in hatch_z:
			# The coaming, and the two cover panels meeting on the centreline in
			# a shallow ridge.
			mb.box(Vector3(0, 3.95, z), Vector3(8.2, 1.5, 7.0), topsides.lightened(0.15))
			for x: float in [-1.0, 1.0]:
				mb.quad(Vector3(x * 4.0, 4.7, z - 3.4), Vector3(x * 4.0, 4.7, z + 3.4),
					Vector3(0, 5.2, z + 3.4), Vector3(0, 5.2, z - 3.4), hatch, Vector3(x * 0.2, 1, 0))
				for dz: float in [-1.7, 0.0, 1.7]:
					mb.box(Vector3(x * 2.0, 4.95, z + dz), Vector3(3.9, 0.12, 0.14), hatch.darkened(0.25))
			mb.tri(Vector3(-4.0, 4.7, z + 3.4), Vector3(4.0, 4.7, z + 3.4), Vector3(0, 5.2, z + 3.4), hatch.darkened(0.15), Vector3.BACK)
			mb.tri(Vector3(-4.0, 4.7, z - 3.4), Vector3(4.0, 4.7, z - 3.4), Vector3(0, 5.2, z - 3.4), hatch.darkened(0.15), Vector3.FORWARD)
		# Cranes between the hatches, jibs stowed forward and a touch outboard,
		# alternately to port and starboard.
		for i in 4:
			var z: float = (hatch_z[i] + hatch_z[i + 1]) * 0.5
			var side := 1.0 if i % 2 == 0 else -1.0
			mb.cylinder(Vector3(0, 3.2, z), 0.75, 0.65, 3.4, 8, crane)
			mb.box(Vector3(0, 7.3, z), Vector3(2.0, 1.6, 2.2), crane)
			mb.box(Vector3(side * 0.6, 7.5, z + 1.12), Vector3(0.7, 0.6, 0.06), GLASS)
			var a := Vector3(side * 0.5, 7.6, z + 0.6)
			var b := Vector3(side * 2.2, 9.8, z + 9.0)
			mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
			mb.box(Vector3.ZERO, Vector3(0.45, 0.5, a.distance_to(b)), crane)
			mb.xform = Transform3D.IDENTITY
			mb.box(Vector3(0, 8.5, z - 0.4), Vector3(0.3, 1.0, 0.3), crane)
		return mb.commit())


## What every cargo ship has in common, 64 m long and 11 m in the beam: the
## hull, forecastle, the accommodation block aft with its bridge and funnel,
## the masts and the sidelights.
static func _cargo_hull(mb: MeshBuilder, topsides: Color, deck: Color, funnel: Color) -> void:
	var hull := PackedVector2Array([Vector2(-5.6, -30), Vector2(-4.8, -32), Vector2(4.8, -32), Vector2(5.6, -30),
		Vector2(5.6, 20), Vector2(4.2, 27), Vector2(1.6, 31), Vector2(0, 32), Vector2(-1.6, 31), Vector2(-4.2, 27),
		Vector2(-5.6, 20)])
	mb.extrude(hull, -2.6, 0.25, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.85)
	mb.extrude(hull, 0.25, 3.2, topsides, deck)
	mb.extrude(hull, 0.18, 0.32, WHITE, Color(0, 0, 0, 0))
	# Forecastle and the breakwater behind it.
	mb.box(Vector3(0, 3.6, 26.0), Vector3(8.0, 0.8, 5.0), topsides)
	mb.box(Vector3(0, 4.4, 23.4), Vector3(10.4, 1.6, 0.25), WHITE)
	# Accommodation block, bridge with its wings, and the funnel.
	mb.box(Vector3(0, 7.2, -25.0), Vector3(10.0, 8.0, 6.0), WHITE)
	for y: float in [5.2, 7.4, 9.6]:
		mb.box(Vector3(0, y, -25.0), Vector3(10.1, 0.6, 6.1), WINDOW_LIT)
	mb.box(Vector3(0, 11.6, -24.0), Vector3(12.4, 1.4, 3.2), WHITE)
	mb.box(Vector3(0, 11.7, -24.0), Vector3(12.5, 0.5, 3.3), WINDOW_LIT)
	mb.box(Vector3(0, 12.4, -24.0), Vector3(12.8, 0.2, 3.6), Color(0.3, 0.32, 0.34))
	mb.box(Vector3(0, 14.0, -24.0), Vector3(0.25, 3.0, 0.25), WHITE)
	add_lantern(mb, CARGO_AFT_MAST, GlowBuilder.LED, CARGO_LANTERN)
	mb.box(Vector3(0, 13.4, -28.6), Vector3(2.6, 3.6, 2.8), funnel)
	mb.box(Vector3(0, 15.45, -28.6), Vector3(2.65, 0.5, 2.85), Color(0.1, 0.1, 0.1))
	# Port (+X) red, starboard green, on the bridge wings' ends.
	for x: float in [-1.0, 1.0]:
		mb.box(Vector3(x * CARGO_SIDELIGHT.x, CARGO_SIDELIGHT.y, CARGO_SIDELIGHT.z), Vector3(0.2, 0.35, 0.45),
			lamp_glass(GlowBuilder.RED if x > 0.0 else GlowBuilder.GREEN))
	# Foremast.
	mb.box(Vector3(0, 6.1, 28.5), Vector3(0.3, 5.8, 0.3), Color(0.85, 0.75, 0.2))
	add_lantern(mb, CARGO_FORE_MAST, GlowBuilder.LED, CARGO_LANTERN)


## Container ships use the mid-poly feeder modelled in Blender (MID_CARGO_GLB, source
## art/cargo_mid.py / cargo_mid.blend, which also writes CargoMidData: the glyph
## advances, the bow's surface and the container slots). The code-built one above is
## the fallback: with the `--classic-cargo` launch flag, or if the model is missing.
## Tankers and bulk carriers stay on the code-built hull for now.
const MID_CARGO_GLB := "res://assets/models/cargo_mid.glb"
static var mid_cargo := not "--classic-cargo" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_CARGO_GLB)
# (After mid_cargo: static vars are set in the order they're declared.)
static var mid_tanker := mid_cargo and ResourceLoader.exists(MID_TANKER_GLB)
static var mid_bulker := mid_cargo and ResourceLoader.exists(MID_BULKER_GLB)
const MID_CARGO_HULLS := [Color(0.12, 0.16, 0.24), Color(0.1, 0.1, 0.11), Color(0.42, 0.12, 0.1)]
# How often each line's boxes turn up (CargoMidData.LINES order); the leasing boxes last.
const MID_CARGO_LINE_WEIGHTS := [1.0, 1.0, 1.0, 1.0, 0.8, 0.8, 0.7, 0.7, 0.9, 0.6, 0.5]
const MID_CARGO_SIDELIGHT_SCALE := 1.4
const MID_CARGO_NAME_CAP := 0.8
const MID_CARGO_REGISTRIES := ["NASSAU", "MAJURO", "MONROVIA", "VALLETTA", "LIMASSOL"]


## Appends `part` to `mb` moved by `xf` (rigid, or uniformly scaled), its colours multiplied by
## `tint`, or all painted `paint` if that is given.
static func _append_part(mb: MeshBuilder, part: MeshBuilder, xf: Transform3D, tint := Color.WHITE,
		paint := Color(-1, 0, 0)) -> void:
	mb.verts.append_array(xf * part.verts)
	mb.normals.append_array(Transform3D(xf.basis.orthonormalized(), Vector3.ZERO) * part.normals)
	if paint.r >= 0.0:
		var c := PackedColorArray()
		c.resize(part.colors.size())
		c.fill(paint)
		mb.colors.append_array(c)
	elif tint == Color.WHITE:
		mb.colors.append_array(part.colors)
	else:
		for c in part.colors:
			mb.colors.append(c * tint)


## The mid-poly container ship in `variant`'s livery, loaded as the variant stows it.
static func _mid_cargo(variant: int) -> MeshBuilder:
	var mb := _mid_cargo_ship(MID_CARGO_GLB, {"hull": MID_CARGO_HULLS[variant % MID_CARGO_HULLS.size()],
		"funnel": CARGO_FUNNELS[variant % CARGO_FUNNELS.size()]})
	_stow_containers(mb, ModelParts.library(MID_CARGO_GLB), variant)
	return mb


## One of the mid-poly ships on the container ship's hull (the feeder, tanker or bulk
## carrier, from `glb`): its fixed parts, the livery's parts each painted as `paint`
## has them, the glass, and the lanterns and sidelights where CargoMidData has them.
static func _mid_cargo_ship(glb: String, paint: Dictionary) -> MeshBuilder:
	var lib := ModelParts.library(glb)
	var mb := MeshBuilder.new()
	var one := Transform3D.IDENTITY
	_append_part(mb, lib["fixed"], one)
	var parts := paint.merged({"glass": WINDOW_LIT, "window": WINDOW, "lens": lamp_glass(GlowBuilder.LED)})
	for part: String in parts:
		_append_part(mb, lib[part], one, Color.WHITE, parts[part])
	add_lantern(mb, CargoMidData.FORE_MAST, GlowBuilder.LED, CARGO_LANTERN)
	add_lantern(mb, CargoMidData.AFT_MAST, GlowBuilder.LED, CARGO_LANTERN)
	for sx: float in [-1.0, 1.0]:
		var sl := CargoMidData.SIDELIGHT
		add_sidelight(mb, Vector3(sx * sl.x, sl.y, sl.z), sx, 1.0, MID_CARGO_SIDELIGHT_SCALE)
	return mb


## Stows the deck cargo for `variant`: in each of the three hatches, each row takes a
## stack of forty-footers or two of twenty-footers; how high is picked per hatch and
## varied per stack. Only the sides and roofs not hidden by a neighbour are built.
static func _stow_containers(mb: MeshBuilder, lib: Dictionary, variant: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = 7019 + variant * 131
	var lines: Array = CargoMidData.LINES
	# A feeder on charter carries mostly its charterer's boxes.
	var weights: Array = MID_CARGO_LINE_WEIGHTS.duplicate()
	weights[variant * 3 % 8] = 4.0
	var tiers_lo := 1 if variant % 3 != 1 else 2
	var tiers_hi := 3
	var cols := CargoMidData.COL_X.size()
	# Stacks: [hatch, column, half (-1: a forty-footer, 0/1: aft/fore twenty), tiers].
	var stacks: Array = []
	# occ[hatch][column][half][tier]: whether that twenty-foot space is filled.
	var occ := {}
	for h in CargoMidData.HATCH_Z.size():
		var base := r.randi_range(tiers_lo, tiers_hi)
		for c in cols:
			var forty := r.randf() < 0.6
			for half: int in ([-1] if forty else [0, 1]):
				var t := clampi(base + r.randi_range(-1, 1) if r.randf() < 0.45 else base, 0, 3)
				# The outer rows forward sit a tier lower, for the bridge's view over the bow.
				if h == CargoMidData.HATCH_Z.size() - 1 and (c == 0 or c == cols - 1):
					t = mini(t, 2)
				stacks.append([h, c, half, t])
				for ti in t:
					for hh: int in ([0, 1] if half < 0 else [half]):
						occ[Vector4i(h, c, hh, ti)] = true
	for st: Array in stacks:
		var h: int = st[0]
		var c: int = st[1]
		var half: int = st[2]
		var halves: Array = [0, 1] if half < 0 else [half]
		var z: float = CargoMidData.HATCH_Z[h] + (0.0 if half < 0 else (half - 0.5) * CargoMidData.BAY_PITCH)
		for ti in st[3]:
			var line: String = lines[_pick_weighted(weights, r)]
			var tag := "c20" if half >= 0 else "c40"
			if half < 0 and line in CargoMidData.REEFERS and r.randf() < 0.3:
				tag = "c40r"
			var key := tag + line
			var tint := Color.WHITE.darkened(r.randf() * 0.14)
			var at := Vector3(CargoMidData.COL_X[c], CargoMidData.COVER_TOP + ti * CargoMidData.CONTAINER_H, z)
			var doors_aft := r.randf() < 0.5
			var turn := Basis(Vector3.UP, PI)
			_append_part(mb, lib[key + "body"], Transform3D(turn if doors_aft else Basis.IDENTITY, at), tint)
			if not _stowed(occ, h, c, halves, ti + 1):
				_append_part(mb, lib[key + "roof"], Transform3D(Basis.IDENTITY, at), tint)
			# The +X side as modelled; turned round for the -X one.
			if c == cols - 1 or not _stowed(occ, h, c + 1, halves, ti):
				_append_part(mb, lib[key + "side"], Transform3D(Basis.IDENTITY, at), tint)
			if c == 0 or not _stowed(occ, h, c - 1, halves, ti):
				_append_part(mb, lib[key + "side"], Transform3D(turn, at), tint)


static func _stowed(occ: Dictionary, h: int, c: int, halves: Array, tier: int) -> bool:
	for hh: int in halves:
		if not occ.has(Vector4i(h, c, hh, tier)):
			return false
	return true


static func _pick_weighted(weights: Array, r: RandomNumberGenerator) -> int:
	var total := 0.0
	for w: float in weights:
		total += w
	var x := r.randf() * total
	for i in weights.size():
		x -= weights[i]
		if x <= 0.0:
			return i
	return weights.size() - 1


## The ship's name in white capitals on both bows and across the transom, the port of
## registry under it there; in the ship's frame, for the mid-poly container ship.
static func cargo_name_plate(ship_name: String) -> ArrayMesh:
	if not mid_cargo:
		return null
	return _cached("cargo_name_" + ship_name, func():
		var lib := ModelParts.library(MID_CARGO_GLB)
		var mb := MeshBuilder.new()
		var text := ship_name.to_upper()
		var cap := MID_CARGO_NAME_CAP
		# Down each bow from abaft the draft marks, where the bow is still fair, reading
		# left to right from outside: aft on the port (+X) side, forward on the starboard.
		var bow: Array = CargoMidData.BOW
		var width := _text_width(text) * cap * 1.06
		var fwd := bow.size() - 5
		for sx: float in [1.0, -1.0]:
			var pen := 0.0 if sx > 0.0 else -width
			for ch in text:
				var adv: float = CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "]) * cap * 1.06
				if lib.has("gl" + ch.to_lower()):
					# Distance aft of the forward end: walk the table to the glyph's middle.
					var d := absf(pen + adv * 0.5)
					var f := clampf(fwd - d / 0.4, 0.0, fwd - 0.001)
					var i := int(f)
					var a: Array = bow[i]
					var b: Array = bow[i + 1]
					var p: Vector3 = (a[0] as Vector3).lerp(b[0], f - i)
					var n: Vector3 = (a[1] as Vector3).lerp(b[1], f - i).normalized()
					p.x *= sx
					n.x *= sx
					var x := (Vector3(0, 0, -sx)).slide(n).normalized()
					var y := n.cross(x).normalized()
					x = y.cross(n)
					var o := p + n * 0.03 - x * adv * 0.5 / 1.06 - y * cap * 0.5
					_append_part(mb, lib["gl" + ch.to_lower()], Transform3D(Basis(x * cap, y * cap, n * cap), o))
				pen += adv
		# The transom, facing aft: the name, the port of registry smaller under it.
		var port: String = MID_CARGO_REGISTRIES[absi(hash(ship_name)) % MID_CARGO_REGISTRIES.size()]
		for row: Array in [[text, 0.62, 2.55], [port, 0.42, 1.65]]:
			var s: float = row[1]
			var w := _text_width(row[0]) * s * 1.06
			var pen := w * 0.5
			for ch: String in row[0]:
				var adv: float = CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "]) * s * 1.06
				if lib.has("gl" + ch.to_lower()):
					var o := Vector3(pen, row[2] - s * 0.5, CargoMidData.TRANSOM_Z - 0.03)
					_append_part(mb, lib["gl" + ch.to_lower()],
						Transform3D(Basis(Vector3(-s, 0, 0), Vector3(0, s, 0), Vector3(0, 0, -s)), o))
				pen -= adv
		return mb.commit())


static func _text_width(text: String) -> float:
	var w := 0.0
	for ch in text:
		w += CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "])
	return w


## The mid-poly ship's masthead, stern and sidelights and its lit bridge's reflection.
static func _mid_cargo_lights() -> ArrayMesh:
	return _cached("cargo_mid_lights", func():
		var gb := GlowBuilder.new()
		for top: Vector3 in [CargoMidData.FORE_MAST, CargoMidData.AFT_MAST]:
			gb.glow(lantern_glow_at(top, CARGO_LANTERN), GlowBuilder.LED, 0.35, 9.0, true, 0.0, Vector3.ZERO, 0.0)
		var sl := CargoMidData.SIDELIGHT
		for sx: float in [-1.0, 1.0]:
			var w := Vector3(sx * sl.x, sl.y, sl.z)
			gb.glow(sidelight_glow_at(w, sx, MID_CARGO_SIDELIGHT_SCALE), GlowBuilder.RED if sx > 0.0 else GlowBuilder.GREEN,
				0.25, 7.0, true, 0.0, Vector3(sx, 0, 0.8), 0.0)
		gb.glow(CargoMidData.STERN_LIGHT - Vector3(0, 0, 0.1), GlowBuilder.LED, 0.2, 5.0, true, 0.0, Vector3(0, 0, -1), 0.0)
		var window := Color(1.0, 0.74, 0.42)
		var y := CargoMidData.BRIDGE_SILL + 0.55
		var bz := CargoMidData.BRIDGE_Z
		for sx: float in [-1.0, 1.0]:
			for i in 5:
				gb.reflection(Vector3(sx * (CargoMidData.BRIDGE_HW + 0.05), y, lerpf(bz.x + 0.4, bz.y - 0.6, i / 4.0)),
					window, 0.3, 2.2, Vector3(sx, 0, 0))
		for i in 7:
			gb.reflection(Vector3(-3.3 + i * 1.1, y, bz.y + 0.25), window, 0.3, 2.2, Vector3(0, 0, 1))
		return gb.commit())


## Masthead, stern and sidelights and the lit bridge's reflection, in the ship's frame
## (`mid`: the mid-poly container ship's; tankers and bulk carriers pass false).
static func cargo_ship_lights(mid := mid_cargo) -> ArrayMesh:
	if mid:
		return _mid_cargo_lights()
	return _cached("cargo_lights", func():
		var gb := GlowBuilder.new()
		for top: Vector3 in [CARGO_FORE_MAST, CARGO_AFT_MAST]:
			gb.glow(lantern_glow_at(top, CARGO_LANTERN), GlowBuilder.LED, 0.35, 9.0, true, 0.0, Vector3.ZERO, 0.0)
		gb.glow(Vector3(-CARGO_SIDELIGHT.x, CARGO_SIDELIGHT.y, CARGO_SIDELIGHT.z), GlowBuilder.GREEN, 0.25, 7.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0)
		gb.glow(CARGO_SIDELIGHT, GlowBuilder.RED, 0.25, 7.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
		gb.glow(Vector3(0, 4.0, -32.2), GlowBuilder.LED, 0.2, 5.0, true, 0.0, Vector3(0, 0, -1), 0.0)
		var window := Color(1.0, 0.74, 0.42)
		for x: float in [-6.25, 6.25]:
			for i in 5:
				gb.reflection(Vector3(x, 11.7, -25.4 + i * 0.7), window, 0.3, 2.2, Vector3(signf(x), 0, 0))
		for x in 7:
			gb.reflection(Vector3(-4.5 + x * 1.5, 11.7, -22.3), window, 0.3, 2.2, Vector3(0, 0, 1))
		return gb.commit())


# Stern trawler (+Z is the bow): about 20 m long and 6.4 m in the beam, the
# wheelhouse forward and the working deck aft under a gantry. The mast carries
# the trawling lights (green over white) and the masthead light.
const TRAWLER_DECK := 1.6
const TRAWLER_MAST := Vector3(0, 8.6, 1.3)       # the white lantern's foot
const TRAWLER_MAST_GREEN := Vector3(0, 9.6, 1.3)
const TRAWLER_LANTERN := 1.2
const TRAWLER_SIDELIGHT := Vector3(2.35, 4.45, 5.4)
const TRAWLER_GANTRY_Z := -9.3
const TRAWLER_GANTRY_TOP := 6.6
const TRAWLER_HULLS := [Color(0.12, 0.2, 0.36), Color(0.13, 0.33, 0.24), Color(0.58, 0.15, 0.12)]
const TRAWLER_GANTRIES := [Color(0.92, 0.52, 0.12), Color(0.9, 0.78, 0.2), Color(0.92, 0.52, 0.12)]
const TRAWLER_NETS := [Color(0.2, 0.55, 0.35), Color(0.85, 0.42, 0.15), Color(0.25, 0.4, 0.62)]


static func _trawler_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array([Vector2(-2.9, -10), Vector2(2.9, -10), Vector2(3.2, -8), Vector2(3.2, 3),
		Vector2(2.65, 6.5), Vector2(1.45, 8.8), Vector2(0, 10), Vector2(-1.45, 8.8), Vector2(-2.65, 6.5),
		Vector2(-3.2, 3), Vector2(-3.2, -8)])
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((3.2 + grow) / 3.2, (10.0 + grow) / 10.0)
	return pts


## Trawlers use the mid-poly stern trawler modelled in Blender (MID_TRAWLER_GLB, source
## art/trawler_mid.py / trawler_mid.blend), in the code-built one's frame and anchor
## points (mast lanterns, gantry blocks, perches, wheelhouse windows). The code-built
## trawler below is the fallback: with `--classic-trawler`, or if the model is missing.
## The glb's livery parts (hull, gantry, net) are recoloured per variant.
const MID_TRAWLER_GLB := "res://assets/models/trawler_mid.glb"
static var mid_trawler := not "--classic-trawler" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_TRAWLER_GLB)
# Sidelight lamps (add_sidelight) on boards at the wheelhouse roof's front corners.
const MID_TRAWLER_SIDELIGHT := Vector3(2.0, 5.63, 4.3)
const MID_TRAWLER_SIDELIGHT_SCALE := 1.2
# The stern light under the gantry's crossbar; the floods on its forward face and on
# the wheelhouse roof's after edge.
const MID_TRAWLER_STERN_LIGHT := Vector3(0, 6.28, -9.62)
const MID_TRAWLER_GANTRY_FLOOD := Vector3(2.05, 6.5, -8.9)
const MID_TRAWLER_HOUSE_FLOOD := Vector3(0.7, 5.65, 0.35)


static func _mid_trawler(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(MID_TRAWLER_GLB, ["fixed"])
	var paint := {"hull": TRAWLER_HULLS[variant % TRAWLER_HULLS.size()],
		"gantry": TRAWLER_GANTRIES[variant % TRAWLER_GANTRIES.size()],
		"net": TRAWLER_NETS[variant % TRAWLER_NETS.size()], "glass": WINDOW_LIT, "window": WINDOW,
		"lens": lamp_glass(GlowBuilder.LED)}
	for part: String in paint:
		var p := ModelParts.merge_named(MID_TRAWLER_GLB, [part])
		mb.verts.append_array(p.verts)
		mb.normals.append_array(p.normals)
		for i in p.verts.size():
			mb.colors.append(paint[part])
	add_lantern(mb, TRAWLER_MAST, GlowBuilder.LED, TRAWLER_LANTERN)
	add_lantern(mb, TRAWLER_MAST_GREEN, GlowBuilder.GREEN, TRAWLER_LANTERN)
	for sx: float in [-1.0, 1.0]:
		add_sidelight(mb, Vector3(sx * MID_TRAWLER_SIDELIGHT.x, MID_TRAWLER_SIDELIGHT.y, MID_TRAWLER_SIDELIGHT.z), sx,
			1.0, MID_TRAWLER_SIDELIGHT_SCALE)
	return mb


## A stern trawler; `variant` picks its colours.
static func trawler(variant: int) -> ArrayMesh:
	if mid_trawler:
		return _cached("trawler_mid_%d" % variant, func(): return _mid_trawler(variant).commit())
	return _cached("trawler_%d" % variant, func():
		var mb := MeshBuilder.new()
		var hull_col: Color = TRAWLER_HULLS[variant % TRAWLER_HULLS.size()]
		var gantry: Color = TRAWLER_GANTRIES[variant % TRAWLER_GANTRIES.size()]
		var net: Color = TRAWLER_NETS[variant % TRAWLER_NETS.size()]
		var deck_col := Color(0.42, 0.43, 0.42)
		var steel := Color(0.22, 0.23, 0.25)
		var d := TRAWLER_DECK
		var outline := _trawler_outline()
		mb.extrude(outline, -2.0, 0.05, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.7)
		mb.extrude(outline, 0.05, d, hull_col, deck_col)
		mb.extrude(_trawler_outline(0.06), d - 0.2, d - 0.05, WHITE, Color(0, 0, 0, 0))
		# Bulwarks down either side of the working deck, the transom's open aft.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 3.12, d + 0.4, -3.0), Vector3(0.14, 0.8, 12.0), hull_col)
			mb.box(Vector3(x * 3.12, d + 0.82, -3.0), Vector3(0.2, 0.06, 12.0), WHITE)
		# The raised foredeck.
		var fore := PackedVector2Array([Vector2(-3.2, 3), Vector2(3.2, 3), Vector2(2.65, 6.5), Vector2(1.45, 8.8),
			Vector2(0, 10), Vector2(-1.45, 8.8), Vector2(-2.65, 6.5)])
		mb.extrude(fore, d, d + 1.0, hull_col, deck_col)
		mb.box(Vector3(0, d + 1.15, 6.6), Vector3(0.6, 0.3, 0.8), steel)
		# Deckhouse and the wheelhouse on top of it, windows all round.
		mb.box(Vector3(0, d + 1.0, 2.0), Vector3(4.8, 2.0, 4.6), WHITE)
		mb.box(Vector3(0, d + 2.0 + 0.9, 3.3), Vector3(4.4, 1.8, 3.4), WHITE)
		mb.box(Vector3(0, d + 2.0 + 1.15, 3.3), Vector3(4.46, 0.6, 3.46), WINDOW_LIT)
		mb.box(Vector3(0, d + 2.0 + 1.85, 3.3), Vector3(4.9, 0.12, 3.9), WHITE)
		mb.box(Vector3(0, d + 1.1, 2.0), Vector3(4.86, 0.5, 2.2), WINDOW_LIT)
		# Sidelights in their screens on the wheelhouse sides.
		for x: float in [-1.0, 1.0]:
			var sl := Vector3(x * TRAWLER_SIDELIGHT.x, TRAWLER_SIDELIGHT.y, TRAWLER_SIDELIGHT.z)
			mb.box(sl + Vector3(0, 0, -0.25), Vector3(0.3, 0.32, 0.06), LAMP_DARK)
			mb.box(sl, Vector3(0.18, 0.24, 0.3), lamp_glass(GlowBuilder.RED if x > 0.0 else GlowBuilder.GREEN))
		# Mast with its crosstree and lights, the radar, the exhaust stack.
		var mast_base := d + 2.0 + 1.9
		mb.box(Vector3(0, (mast_base + TRAWLER_MAST_GREEN.y) * 0.5, TRAWLER_MAST.z), Vector3(0.18, TRAWLER_MAST_GREEN.y - mast_base, 0.18), WHITE)
		mb.box(Vector3(0, 7.6, TRAWLER_MAST.z), Vector3(2.4, 0.1, 0.1), WHITE)
		add_lantern(mb, TRAWLER_MAST, GlowBuilder.LED, TRAWLER_LANTERN)
		add_lantern(mb, TRAWLER_MAST_GREEN, GlowBuilder.GREEN, TRAWLER_LANTERN)
		mb.box(Vector3(0, mast_base + 0.45, 2.6), Vector3(0.25, 0.5, 0.25), steel)
		mb.box(Vector3(0, mast_base + 0.75, 2.6), Vector3(2.2, 0.12, 0.3), WHITE)
		mb.cylinder(Vector3(1.6, d + 2.0, 0.4), 0.22, 0.2, 3.6, 8, Color(0.85, 0.85, 0.83))
		mb.cylinder(Vector3(1.6, d + 5.6, 0.4), 0.21, 0.21, 0.4, 8, Color(0.08, 0.08, 0.08))
		mb.cylinder(Vector3(-1.5, d + 2.0 + 1.9, 2.2), 0.3, 0.3, 0.7, 8, WHITE)
		# The working deck: fish hatch, net drum, and the gantry over the stern
		# with the trawl doors hung either side.
		mb.box(Vector3(0, d + 0.25, -2.6), Vector3(1.8, 0.5, 1.8), steel)
		var saved := mb.xform
		mb.xform = saved * Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(1.8, d + 1.1, -6.4))
		mb.cylinder(Vector3.ZERO, 0.85, 0.85, 3.6, 10, net, Color(-1, 0, 0), 0.0, true)
		mb.cylinder(Vector3(0, -0.06, 0), 1.05, 1.05, 0.12, 10, steel, Color(-1, 0, 0), 0.0, true)
		mb.cylinder(Vector3(0, 3.54, 0), 1.05, 1.05, 0.12, 10, steel, Color(-1, 0, 0), 0.0, true)
		mb.xform = saved
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 1.95, d + 0.55, -6.4), Vector3(0.2, 1.1, 0.4), steel)
			mb.box(Vector3(x * 2.7, (d + TRAWLER_GANTRY_TOP) * 0.5, TRAWLER_GANTRY_Z), Vector3(0.32, TRAWLER_GANTRY_TOP - d, 0.32), gantry)
			mb.box(Vector3(x * 3.32, d + 0.9, -8.4), Vector3(0.14, 1.1, 1.7), steel)
			mb.box(Vector3(x * 2.95, d + 1.6, -8.4), Vector3(0.6, 0.06, 0.06), steel)
		mb.box(Vector3(0, TRAWLER_GANTRY_TOP, TRAWLER_GANTRY_Z), Vector3(5.8, 0.34, 0.4), gantry)
		for x: float in [-1.4, 1.4]:
			mb.box(Vector3(x, TRAWLER_GANTRY_TOP - 0.45, TRAWLER_GANTRY_Z), Vector3(0.3, 0.5, 0.25), steel)
		# Tyres slung along the topsides for coming alongside.
		for x: float in [-1.0, 1.0]:
			for z: float in [-6.5, -3.0, 0.5, 4.0]:
				mb.box(Vector3(x * 3.28, d - 0.35, z), Vector3(0.18, 0.6, 0.6), Color(0.08, 0.08, 0.09))
		# The stern light.
		mb.box(Vector3(0, d + 0.15, -10.02), Vector3(0.22, 0.2, 0.08), lamp_glass(GlowBuilder.LED))
		return mb.commit())


## The trawl warps, out from the gantry's blocks and down into the water astern
## (shown while the net is out).
static func trawler_warps() -> ArrayMesh:
	return _cached("trawler_warps", func():
		var mb := MeshBuilder.new()
		for x: float in [-1.4, 1.4]:
			var a := Vector3(x, TRAWLER_GANTRY_TOP - 0.7, TRAWLER_GANTRY_Z)
			var b := Vector3(x * 1.6, -0.6, TRAWLER_GANTRY_Z - 8.5)
			mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
			mb.box(Vector3.ZERO, Vector3(0.07, 0.07, a.distance_to(b)), Color(0.15, 0.15, 0.16))
		return mb.commit())


## The lit wheelhouse's reflection, drawn by NightLights on each trawler.
static func trawler_lights() -> ArrayMesh:
	return _cached("trawler_lights", func():
		var gb := GlowBuilder.new()
		var window := Color(1.0, 0.74, 0.42)
		for x: float in [-2.25, 2.25]:
			for i in 3:
				gb.reflection(Vector3(x, TRAWLER_DECK + 3.15, 2.4 + i * 0.9), window, 0.26, 1.8, Vector3(signf(x), 0, 0))
		for i in 4:
			gb.reflection(Vector3(-1.5 + i, TRAWLER_DECK + 3.15, 5.05), window, 0.26, 1.8, Vector3(0, 0, 1))
		return gb.commit())


## Sidelights and stern light, shown under way.
static func trawler_nav_lights() -> ArrayMesh:
	return _cached("trawler_nav", func():
		var gb := GlowBuilder.new()
		var sl := sidelight_glow_at(MID_TRAWLER_SIDELIGHT, 1.0, MID_TRAWLER_SIDELIGHT_SCALE) if mid_trawler \
			else TRAWLER_SIDELIGHT + Vector3(0, 0, 0.1)
		gb.glow(sl, GlowBuilder.RED, 0.2, 6.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
		gb.glow(Vector3(-sl.x, sl.y, sl.z), GlowBuilder.GREEN, 0.2, 6.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0)
		gb.glow(MID_TRAWLER_STERN_LIGHT if mid_trawler else Vector3(0, TRAWLER_DECK + 0.15, -10.1), GlowBuilder.LED,
			0.16, 4.0, true, 0.0, Vector3(0, 0, -1), 0.0)
		return gb.commit())


## The masthead light, shown steaming.
static func trawler_steaming_lights() -> ArrayMesh:
	return _cached("trawler_steaming", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(TRAWLER_MAST, TRAWLER_LANTERN), GlowBuilder.LED, 0.22, 7.0, true, 0.0, Vector3.ZERO, 0.0)
		return gb.commit())


## Trawling: green over white all round, and the working deck floodlit from the
## gantry and the back of the wheelhouse.
static func trawler_working_lights() -> ArrayMesh:
	return _cached("trawler_working", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(TRAWLER_MAST_GREEN, TRAWLER_LANTERN), GlowBuilder.GREEN, 0.24, 7.0, true, 0.0, Vector3.ZERO, 0.0)
		gb.glow(lantern_glow_at(TRAWLER_MAST, TRAWLER_LANTERN), GlowBuilder.LED, 0.22, 7.0, true, 0.0, Vector3.ZERO, 0.0)
		if mid_trawler:
			for sx: float in [-1.0, 1.0]:
				var g := MID_TRAWLER_GANTRY_FLOOD
				gb.glow(Vector3(sx * g.x, g.y, g.z), GlowBuilder.LED, 0.3, 6.0, true, 0.0, Vector3(0, -0.5, 1), 0.0)
				var h := MID_TRAWLER_HOUSE_FLOOD
				gb.glow(Vector3(sx * h.x, h.y, h.z), GlowBuilder.LED, 0.24, 5.0, false, 0.0, Vector3(0, -0.4, -1), 0.0)
		else:
			for x: float in [-1.4, 1.4]:
				gb.glow(Vector3(x, TRAWLER_GANTRY_TOP - 0.55, TRAWLER_GANTRY_Z + 0.15), GlowBuilder.LED, 0.3, 6.0, true, 0.0, Vector3(0, -0.5, 1), 0.0)
			gb.glow(Vector3(0, TRAWLER_DECK + 3.7, 1.55), GlowBuilder.LED, 0.28, 5.0, false, 0.0, Vector3(0, -0.4, -1), 0.0)
		gb.pool(Vector3(0, TRAWLER_DECK + 0.05, -5.0), GlowBuilder.LED, 4.2, 0.5, 0.0)
		gb.pool(Vector3(0, 0.05, -12.0), GlowBuilder.LED, 4.0, 0.1, 0.0)
		return gb.commit())


# Motor yacht (+Z is the bow), at the sailboats' scale: about 5.5 m long and
# 1.8 m in the beam, a saloon with a raked windscreen, a flybridge under a bimini,
# and a radar arch carrying its masthead (or, at anchor, anchor) light.
const YACHT_ARCH_TOP := Vector3(0, 2.1, -0.85)
const YACHT_LANTERN := 0.5
const YACHT_SIDELIGHT := Vector3(0.74, 1.4, 0.44)
const YACHT_HULLS := [Color(0.94, 0.95, 0.94), Color(0.1, 0.16, 0.3), Color(0.78, 0.8, 0.82)]
const YACHT_STRIPES := [Color(0.1, 0.2, 0.42), Color(0.94, 0.95, 0.94), Color(0.13, 0.13, 0.15)]
const YACHT_CANVAS := [Color(0.13, 0.22, 0.38), Color(0.82, 0.78, 0.68), Color(0.2, 0.2, 0.22)]
const TEAK := Color(0.62, 0.45, 0.28)
# Sidelight lenses that only shine when the boat shows its lights (the glow is in
# its nav-light mesh, shown under way): plain coloured glass.
const LENS_RED := Color(0.62, 0.1, 0.08)
const LENS_GREEN := Color(0.1, 0.5, 0.24)
const CUSHION := Color(0.88, 0.85, 0.77)


static func _yacht_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array([Vector2(-0.82, -2.75), Vector2(0.82, -2.75), Vector2(0.9, -1.8), Vector2(0.9, 0.4),
		Vector2(0.78, 1.5), Vector2(0.45, 2.3), Vector2(0, 2.75), Vector2(-0.45, 2.3), Vector2(-0.78, 1.5),
		Vector2(-0.9, 0.4), Vector2(-0.9, -1.8)])
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((0.9 + grow) / 0.9, (2.75 + grow) / 2.75)
	return pts


## A flybridge motor yacht; `variant` picks its colours.
static func motor_yacht(variant: int) -> ArrayMesh:
	return _cached("yacht_%d" % variant, func():
		var mb := MeshBuilder.new()
		var hull: Color = YACHT_HULLS[variant % YACHT_HULLS.size()]
		var stripe: Color = YACHT_STRIPES[variant % YACHT_STRIPES.size()]
		var canvas: Color = YACHT_CANVAS[variant % YACHT_CANVAS.size()]
		var deck := Color(0.92, 0.91, 0.87)
		var outline := _yacht_outline()
		mb.extrude(outline, -0.4, 0.05, Color(0.12, 0.14, 0.2), Color(0, 0, 0, 0), 0.5)
		mb.extrude(outline, 0.05, 0.62, hull, deck)
		mb.extrude(_yacht_outline(0.03), 0.12, 0.2, stripe, Color(0, 0, 0, 0))
		# Hull ports for the cabins below, a teak cockpit and swim platform aft.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 0.88, 0.4, 0.55), Vector3(0.05, 0.1, 0.8), WINDOW)
		mb.box(Vector3(0, 0.632, -2.15), Vector3(1.5, 0.02, 1.1), TEAK)
		mb.box(Vector3(0, 0.12, -2.95), Vector3(1.55, 0.07, 0.42), TEAK)
		mb.box(Vector3(0, 0.76, -2.58), Vector3(1.4, 0.28, 0.26), CUSHION)
		# The saloon, windows down its sides and glass doors aft, and its raked
		# windscreen.
		mb.box(Vector3(0, 0.91, -0.45), Vector3(1.5, 0.58, 2.1), WHITE)
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 0.755, 0.95, -0.5), Vector3(0.02, 0.3, 1.8), WINDOW)
			mb.tri(Vector3(x * 0.75, 1.2, 0.6), Vector3(x * 0.75, 0.62, 0.6), Vector3(x * 0.75, 0.62, 1.2), WHITE, Vector3(x, 0, 0))
		mb.box(Vector3(0, 0.92, -1.505), Vector3(1.1, 0.44, 0.02), WINDOW)
		mb.quad(Vector3(-0.75, 1.2, 0.6), Vector3(0.75, 1.2, 0.6), Vector3(0.75, 0.62, 1.2), Vector3(-0.75, 0.62, 1.2),
			GLASS, Vector3(0, 1, 1))
		# The flybridge: deck, screen, helm and seats.
		mb.box(Vector3(0, 1.25, -0.55), Vector3(1.56, 0.1, 2.0), WHITE)
		mb.box(Vector3(0, 1.4, 0.36), Vector3(1.5, 0.22, 0.18), WHITE)
		mb.box(Vector3(0.38, 1.46, 0.12), Vector3(0.42, 0.3, 0.24), WHITE)
		mb.box(Vector3(0.38, 1.62, 0.18), Vector3(0.36, 0.04, 0.14), GLASS)
		mb.box(Vector3(0.38, 1.42, -0.32), Vector3(0.44, 0.24, 0.4), CUSHION)
		mb.box(Vector3(0, 1.4, -1.25), Vector3(1.25, 0.2, 0.42), CUSHION)
		# Sidelights in the screen's corners.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * YACHT_SIDELIGHT.x, YACHT_SIDELIGHT.y, YACHT_SIDELIGHT.z), Vector3(0.06, 0.08, 0.12),
				LENS_RED if x > 0.0 else LENS_GREEN)
		# The radar arch, leaning aft, with the radome and the lantern on top;
		# the bimini forward of it.
		var a_y := YACHT_ARCH_TOP.y - 0.22
		var a_z := YACHT_ARCH_TOP.z
		for x: float in [-1.0, 1.0]:
			var lo := Vector3(x * 0.68, 1.3, a_z + 0.2)
			var hi := Vector3(x * 0.5, a_y, a_z)
			mb.xform = Transform3D(Basis.looking_at(hi - lo), (lo + hi) * 0.5)
			mb.box(Vector3.ZERO, Vector3(0.09, 0.12, lo.distance_to(hi)), WHITE)
			mb.xform = Transform3D.IDENTITY
		mb.box(Vector3(0, a_y, a_z), Vector3(1.1, 0.1, 0.2), WHITE)
		mb.cylinder(Vector3(0, a_y + 0.05, a_z), 0.16, 0.16, 0.12, 8, WHITE)
		add_lantern(mb, YACHT_ARCH_TOP, GlowBuilder.LED, YACHT_LANTERN)
		mb.box(Vector3(0, 1.9, -0.3), Vector3(1.4, 0.04, 1.1), canvas)
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 0.66, 1.62, 0.2), Vector3(0.03, 0.56, 0.03), Color(0.8, 0.8, 0.8))
		# Foredeck: a sunpad, the bow rail and the anchor in its roller.
		mb.box(Vector3(0, 0.67, 1.55), Vector3(0.9, 0.08, 0.6), CUSHION)
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 0.6, 0.85, 1.7), Vector3(0.03, 0.03, 1.5), Color(0.82, 0.82, 0.82))
		mb.box(Vector3(0, 0.66, 2.55), Vector3(0.12, 0.06, 0.34), Color(0.5, 0.52, 0.54))
		mb.box(Vector3(0, 0.45, -2.76), Vector3(0.1, 0.06, 0.03), lamp_glass(GlowBuilder.LED))
		return mb.commit())


## The anchor's rode, out from the bow roller and down into the water ahead
## (shown at anchor).
static func motor_yacht_rode() -> ArrayMesh:
	return _cached("yacht_rode", func():
		var mb := MeshBuilder.new()
		var a := Vector3(0, 0.62, 2.72)
		var b := Vector3(0, -0.5, 4.3)
		mb.xform = Transform3D(Basis.looking_at(b - a), (a + b) * 0.5)
		mb.box(Vector3.ZERO, Vector3(0.04, 0.04, a.distance_to(b)), Color(0.3, 0.3, 0.32))
		return mb.commit())


## The lit saloon's reflection, drawn by NightLights on each motor yacht.
static func motor_yacht_lights() -> ArrayMesh:
	return _cached("yacht_lights", func():
		var gb := GlowBuilder.new()
		var window := Color(1.0, 0.74, 0.42)
		for x: float in [-0.78, 0.78]:
			for i in 2:
				gb.reflection(Vector3(x, 0.95, -1.0 + i * 0.8), window, 0.12, 1.2, Vector3(signf(x), 0, 0))
		return gb.commit())


## Sidelights and stern light, shown under way.
static func motor_yacht_nav_lights() -> ArrayMesh:
	return _cached("yacht_nav", func():
		var gb := GlowBuilder.new()
		gb.glow(YACHT_SIDELIGHT + Vector3(0.02, 0, 0.04), GlowBuilder.RED, 0.1, 4.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
		gb.glow(Vector3(-YACHT_SIDELIGHT.x - 0.02, YACHT_SIDELIGHT.y, YACHT_SIDELIGHT.z + 0.04), GlowBuilder.GREEN, 0.1, 4.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0)
		gb.glow(Vector3(0, 0.45, -2.8), GlowBuilder.LED, 0.08, 3.0, true, 0.0, Vector3(0, 0, -1), 0.0)
		return gb.commit())


## The light on the arch: the masthead light under way, the anchor light at anchor.
static func motor_yacht_mast_light() -> ArrayMesh:
	return _cached("yacht_mast", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(YACHT_ARCH_TOP, YACHT_LANTERN), GlowBuilder.LED, 0.12, 4.5, true, 0.0, Vector3.ZERO, 0.0)
		return gb.commit())


# Pilot boat (+Z is the bow): about 9 m long and 3 m in the beam, heavily fendered
# to lie against a ship's side, the deckhouse forward and its mast carrying the
# pilot vessel's lights (white over red).
const PILOT_WHITE := Vector3(0, 3.95, 0.7)
const PILOT_RED := Vector3(0, 3.5, 0.7)
const PILOT_LANTERN := 0.9
const PILOT_SIDELIGHT := Vector3(1.13, 1.75, 1.8)
const PILOT_HULLS := [Color(0.08, 0.08, 0.09), Color(0.86, 0.33, 0.1), Color(0.1, 0.15, 0.28)]
const PILOT_TOPS := [Color(0.9, 0.4, 0.1), Color(0.94, 0.95, 0.94), Color(0.9, 0.4, 0.1)]


## Pilot boats use the mid-poly launch modelled in Blender (MID_PILOT_GLB, source
## art/pilot_mid.py / pilot_mid.blend). The code-built one below is the fallback: with
## the `--classic-pilot` launch flag, or if the model is missing. The glb's livery parts
## (hull, trim: the PILOT lettering and sheer stripe) are recoloured per variant.
const MID_PILOT_GLB := "res://assets/models/pilot_mid.glb"
static var mid_pilot := not "--classic-pilot" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_PILOT_GLB)
const MID_PILOT_HULLS := [Color(0.78, 0.13, 0.1), Color(0.14, 0.15, 0.16), Color(0.1, 0.15, 0.28)]
const MID_PILOT_TRIMS := [Color(0.78, 0.13, 0.1), Color(0.78, 0.13, 0.1), Color(0.9, 0.4, 0.1)]
# The red lantern sits on a bracket forward of the mast, the white one on its top.
const MID_PILOT_RED := Vector3(0, 3.5, 0.93)
# Sidelight lamps (add_sidelight) on the deckhouse sides, just below the windows.
const MID_PILOT_SIDELIGHT := Vector3(1.1, 1.42, 1.15)
const MID_PILOT_SIDELIGHT_SCALE := 0.75
const MID_PILOT_STERN_LIGHT := Vector3(0, 1.45, -4.46)


static func _pilot_red() -> Vector3:
	return MID_PILOT_RED if mid_pilot else PILOT_RED


## The mid-poly pilot boat in `variant`'s livery.
static func _mid_pilot(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(MID_PILOT_GLB, ["fixed"])
	var paint := {"hull": MID_PILOT_HULLS[variant % MID_PILOT_HULLS.size()],
		"trim": MID_PILOT_TRIMS[variant % MID_PILOT_TRIMS.size()], "glass": WINDOW_LIT,
		"lens": lamp_glass(GlowBuilder.LED)}
	for part: String in paint:
		var p := ModelParts.merge_named(MID_PILOT_GLB, [part])
		mb.verts.append_array(p.verts)
		mb.normals.append_array(p.normals)
		for i in p.verts.size():
			mb.colors.append(paint[part])
	add_lantern(mb, MID_PILOT_RED, GlowBuilder.RED, PILOT_LANTERN)
	add_lantern(mb, PILOT_WHITE, GlowBuilder.LED, PILOT_LANTERN)
	for sx: float in [-1.0, 1.0]:
		add_sidelight(mb, Vector3(sx * MID_PILOT_SIDELIGHT.x, MID_PILOT_SIDELIGHT.y, MID_PILOT_SIDELIGHT.z), sx, 1.0,
			MID_PILOT_SIDELIGHT_SCALE)
	return mb


static func _pilot_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array([Vector2(-1.4, -4.5), Vector2(1.4, -4.5), Vector2(1.5, -3.5), Vector2(1.5, 1.0),
		Vector2(1.3, 2.6), Vector2(0.75, 3.8), Vector2(0, 4.5), Vector2(-0.75, 3.8), Vector2(-1.3, 2.6),
		Vector2(-1.5, 1.0), Vector2(-1.5, -3.5)])
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((1.5 + grow) / 1.5, (4.5 + grow) / 4.5)
	return pts


## A pilot boat; `variant` picks its colours.
static func pilot_boat(variant: int) -> ArrayMesh:
	if mid_pilot:
		return _cached("pilot_mid_%d" % variant, func(): return _mid_pilot(variant).commit())
	return _cached("pilot_%d" % variant, func():
		var mb := MeshBuilder.new()
		var hull: Color = PILOT_HULLS[variant % PILOT_HULLS.size()]
		var top: Color = PILOT_TOPS[variant % PILOT_TOPS.size()]
		var deck := Color(0.4, 0.42, 0.42)
		var fender := Color(0.06, 0.06, 0.07)
		var outline := _pilot_outline()
		mb.extrude(outline, -0.8, 0.05, Color(0.5, 0.14, 0.12), Color(0, 0, 0, 0), 0.55)
		mb.extrude(outline, 0.05, 0.95, hull, deck)
		# The heavy rubber fender all round the gunwale.
		mb.extrude(_pilot_outline(0.14), 0.62, 0.95, fender, Color(0, 0, 0, 0))
		mb.extrude(_pilot_outline(0.04), 0.1, 0.18, WHITE, Color(0, 0, 0, 0))
		# Deckhouse, windows all round, and the roof in the station's colour with a
		# rail round it.
		mb.box(Vector3(0, 1.6, 0.4), Vector3(2.2, 1.3, 3.4), WHITE)
		mb.box(Vector3(0, 1.85, 0.4), Vector3(2.24, 0.48, 3.44), WINDOW_LIT)
		mb.box(Vector3(0, 2.3, 0.4), Vector3(2.4, 0.12, 3.6), top)
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 1.1, 2.6, 0.4), Vector3(0.05, 0.05, 3.2), WHITE)
		mb.box(Vector3(0, 2.6, -1.25), Vector3(2.2, 0.05, 0.05), WHITE)
		mb.box(Vector3(0, 2.6, 2.05), Vector3(2.2, 0.05, 0.05), WHITE)
		# A band of the top colour round the hull below the fender.
		mb.extrude(_pilot_outline(0.02), 0.38, 0.55, top, Color(0, 0, 0, 0))
		# Sidelights on the deckhouse's forward corners.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * PILOT_SIDELIGHT.x, PILOT_SIDELIGHT.y, PILOT_SIDELIGHT.z), Vector3(0.06, 0.16, 0.24),
				LENS_RED if x > 0.0 else LENS_GREEN)
		# The mast: radar, then the pilot's red and white lanterns.
		mb.box(Vector3(0, (2.36 + PILOT_WHITE.y) * 0.5, PILOT_WHITE.z), Vector3(0.12, PILOT_WHITE.y - 2.36, 0.12), WHITE)
		mb.box(Vector3(0, 3.05, PILOT_WHITE.z), Vector3(1.4, 0.08, 0.26), WHITE)
		mb.box(Vector3(0, 3.2, PILOT_WHITE.z), Vector3(0.8, 0.06, 0.08), Color(0.2, 0.2, 0.22))
		add_lantern(mb, PILOT_RED, GlowBuilder.RED, PILOT_LANTERN)
		add_lantern(mb, PILOT_WHITE, GlowBuilder.LED, PILOT_LANTERN)
		# Foredeck rails where the pilot steps across, a bitt aft and the stern light.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 1.05, 1.35, 3.0), Vector3(0.05, 0.05, 1.6), WHITE)
			for z: float in [2.3, 3.0, 3.7]:
				mb.box(Vector3(x * 1.05 * (1.0 - (z - 2.3) * 0.3), 1.15, z), Vector3(0.05, 0.4, 0.05), WHITE)
		mb.cylinder(Vector3(0, 0.95, -3.4), 0.14, 0.14, 0.35, 8, Color(0.2, 0.2, 0.22))
		mb.cylinder(Vector3(0.6, 0.95, -2.4), 0.3, 0.3, 0.5, 8, WHITE)
		mb.box(Vector3(0, 0.8, -4.52), Vector3(0.14, 0.1, 0.04), lamp_glass(GlowBuilder.LED))
		return mb.commit())


## The ship's pilot ladder, hung over its side down to just above the pilot
## boat's deck, in the boat's frame with the ship's side `out` metres to
## starboard (+X) and its deck `deck` metres up.
static func pilot_ladder(out: float, deck: float) -> ArrayMesh:
	return _cached("pilot_ladder_%.2f_%.2f" % [out, deck], func():
		var mb := MeshBuilder.new()
		var rope := Color(0.75, 0.66, 0.48)
		var foot := 1.45
		# Abreast of the foredeck, where the boat's boarding rails are.
		var z := 2.9
		for dz: float in [-0.25, 0.25]:
			mb.box(Vector3(out - 0.04, (deck + foot) * 0.5, z + dz), Vector3(0.04, deck - foot, 0.04), rope)
		var y := foot + 0.1
		while y < deck - 0.1:
			mb.box(Vector3(out - 0.05, y, z), Vector3(0.06, 0.05, 0.62), Color(0.55, 0.36, 0.2))
			y += 0.33
		# The pilot, stepping across from the foredeck in a hi-vis jacket.
		var px := out - 0.45
		mb.box(Vector3(px, 1.35, z), Vector3(0.24, 0.5, 0.22), Color(0.12, 0.13, 0.18))
		mb.box(Vector3(px, 1.78, z), Vector3(0.3, 0.38, 0.26), Color(0.95, 0.5, 0.1))
		mb.box(Vector3(px, 2.07, z), Vector3(0.18, 0.18, 0.18), Color(0.85, 0.65, 0.5))
		return mb.commit())


static func pilot_boat_lights() -> ArrayMesh:
	return _cached("pilot_lights", func():
		var gb := GlowBuilder.new()
		var window := Color(1.0, 0.74, 0.42)
		# (The mid-poly deckhouse's windows run higher and further aft.)
		var y := 1.92 if mid_pilot else 1.85
		var z0 := -0.9 if mid_pilot else -0.6
		for x: float in [-1.15, 1.15]:
			for i in 3:
				gb.reflection(Vector3(x, y, z0 + i), window, 0.16, 1.4, Vector3(signf(x), 0, 0))
		return gb.commit())


## Sidelights and stern light, shown under way.
static func pilot_boat_nav_lights() -> ArrayMesh:
	return _cached("pilot_nav", func():
		var gb := GlowBuilder.new()
		var sl := sidelight_glow_at(MID_PILOT_SIDELIGHT, 1.0, MID_PILOT_SIDELIGHT_SCALE) if mid_pilot \
			else PILOT_SIDELIGHT + Vector3(0.04, 0, 0.1)
		gb.glow(sl, GlowBuilder.RED, 0.15, 5.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
		gb.glow(Vector3(-sl.x, sl.y, sl.z), GlowBuilder.GREEN, 0.15, 5.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0)
		gb.glow(MID_PILOT_STERN_LIGHT if mid_pilot else Vector3(0, 0.8, -4.56), GlowBuilder.LED, 0.1, 3.5, true, 0.0,
			Vector3(0, 0, -1), 0.0)
		return gb.commit())


## On pilotage duty: white over red, all round.
static func pilot_boat_duty_lights() -> ArrayMesh:
	return _cached("pilot_duty", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(PILOT_WHITE, PILOT_LANTERN), GlowBuilder.LED, 0.17, 6.0, true, 0.0, Vector3.ZERO, 0.0)
		gb.glow(lantern_glow_at(_pilot_red(), PILOT_LANTERN), GlowBuilder.RED, 0.17, 6.0, true, 0.0, Vector3.ZERO, 0.0)
		return gb.commit())


# Tug (+Z is the bow): about 14 m long and 5 m in the beam, heavily fendered, the
# wheelhouse high on its deckhouse forward, the stack behind it and the towing
# winch and staple on the after deck.
const TUG_MAST := Vector3(0, 7.7, 1.4)
const TUG_LANTERN := 1.1
const TUG_SIDELIGHT := Vector3(1.56, 4.7, 2.9)
const TUG_HULLS := [Color(0.1, 0.1, 0.11), Color(0.62, 0.15, 0.12), Color(0.13, 0.22, 0.36)]
const TUG_HOUSES := [Color(0.94, 0.95, 0.94), Color(0.94, 0.95, 0.94), Color(0.9, 0.84, 0.62)]
const TUG_STACKS := [Color(0.86, 0.33, 0.1), Color(0.1, 0.1, 0.11), Color(0.75, 0.15, 0.13)]
const TUG_STERN_LIGHT := Vector3(0, 1.4, -7.08)

## Tugs use the mid-poly escort tug modelled in Blender (MID_TUG_GLB, source
## art/tug_mid.py / tug_mid.blend). The code-built tug below is the fallback: with the
## `--classic-tug` launch flag, or if the model is missing. The glb's livery parts
## (hull, house, stack) are recoloured per variant; its glass parts get their alpha.
const MID_TUG_GLB := "res://assets/models/tug_mid.glb"
static var mid_tug := not "--classic-tug" in OS.get_cmdline_user_args() \
	and ResourceLoader.exists(MID_TUG_GLB)
const MID_TUG_MAST := Vector3(0, 8.05, 1.25)
# Sidelight lamps (add_sidelight) on the wheelhouse sides, below the windows.
const MID_TUG_SIDELIGHT := Vector3(1.5, 3.95, 2.6)
const MID_TUG_SIDELIGHT_SCALE := 1.2
const MID_TUG_STERN_LIGHT := Vector3(0, 2.02, -7.11)


static func _tug_mast() -> Vector3:
	return MID_TUG_MAST if mid_tug else TUG_MAST


## Where the port (+x, red) sidelight's glow sits; the starboard one mirrors it.
static func _tug_sidelight() -> Vector3:
	return sidelight_glow_at(MID_TUG_SIDELIGHT, 1.0, MID_TUG_SIDELIGHT_SCALE) if mid_tug else TUG_SIDELIGHT


static func _tug_stern_light() -> Vector3:
	return MID_TUG_STERN_LIGHT if mid_tug else TUG_STERN_LIGHT


## The mid-poly tug in `variant`'s livery.
static func _mid_tug(variant: int) -> MeshBuilder:
	var mb := ModelParts.merge_named(MID_TUG_GLB, ["fixed"])
	var paint := {"hull": TUG_HULLS[variant % TUG_HULLS.size()], "house": TUG_HOUSES[variant % TUG_HOUSES.size()],
		"stack": TUG_STACKS[variant % TUG_STACKS.size()], "glass": WINDOW_LIT, "window": WINDOW,
		"lens": lamp_glass(GlowBuilder.LED)}
	for part: String in paint:
		var p := ModelParts.merge_named(MID_TUG_GLB, [part])
		mb.verts.append_array(p.verts)
		mb.normals.append_array(p.normals)
		for i in p.verts.size():
			mb.colors.append(paint[part])
	add_lantern(mb, MID_TUG_MAST, GlowBuilder.LED, TUG_LANTERN)
	for sx: float in [-1.0, 1.0]:
		add_sidelight(mb, Vector3(sx * MID_TUG_SIDELIGHT.x, MID_TUG_SIDELIGHT.y, MID_TUG_SIDELIGHT.z), sx, 1.0,
			MID_TUG_SIDELIGHT_SCALE)
	return mb


static func _tug_outline(grow := 0.0) -> PackedVector2Array:
	var pts := PackedVector2Array([Vector2(-2.2, -7), Vector2(2.2, -7), Vector2(2.5, -5.5), Vector2(2.5, 2.0),
		Vector2(2.2, 4.5), Vector2(1.4, 6.3), Vector2(0, 7), Vector2(-1.4, 6.3), Vector2(-2.2, 4.5),
		Vector2(-2.5, 2.0), Vector2(-2.5, -5.5)])
	if grow != 0.0:
		for i in pts.size():
			pts[i] = pts[i] * Vector2((2.5 + grow) / 2.5, (7.0 + grow) / 7.0)
	return pts


## A tug; `variant` picks its colours.
static func tug(variant: int) -> ArrayMesh:
	if mid_tug:
		return _cached("tug_mid_%d" % variant, func(): return _mid_tug(variant).commit())
	return _cached("tug_%d" % variant, func():
		var mb := MeshBuilder.new()
		var hull: Color = TUG_HULLS[variant % TUG_HULLS.size()]
		var house: Color = TUG_HOUSES[variant % TUG_HOUSES.size()]
		var stack: Color = TUG_STACKS[variant % TUG_STACKS.size()]
		var deck := Color(0.36, 0.37, 0.37)
		var fender := Color(0.06, 0.06, 0.07)
		var steel := Color(0.25, 0.26, 0.28)
		var outline := _tug_outline()
		mb.extrude(outline, -2.2, 0.05, Color(0.55, 0.14, 0.12), Color(0, 0, 0, 0), 0.65)
		mb.extrude(outline, 0.05, 1.3, hull, deck)
		mb.extrude(_tug_outline(0.04), 0.95, 1.08, WHITE, Color(0, 0, 0, 0))
		# Fendering all round, and the big bow fender for pushing.
		mb.extrude(_tug_outline(0.3), 0.35, 1.0, fender, Color(0, 0, 0, 0))
		mb.box(Vector3(0, 1.1, 6.75), Vector3(2.4, 1.3, 0.9), fender)
		# Bulwarks down the sides, a white cap on them.
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 2.42, 1.6, -1.8), Vector3(0.14, 0.6, 9.4), hull)
			mb.box(Vector3(x * 2.42, 1.92, -1.8), Vector3(0.2, 0.06, 9.4), WHITE)
		# The deckhouse, the wheelhouse high on it with windows all round, and the
		# mast on its roof.
		mb.box(Vector3(0, 2.4, 1.6), Vector3(3.6, 2.2, 5.0), house)
		mb.box(Vector3(0, 2.6, 1.6), Vector3(3.64, 0.5, 4.2), WINDOW)
		mb.box(Vector3(0, 4.4, 2.2), Vector3(3.0, 1.8, 2.6), house)
		mb.box(Vector3(0, 4.62, 2.2), Vector3(3.06, 0.7, 2.66), WINDOW_LIT)
		mb.box(Vector3(0, 5.36, 2.2), Vector3(3.5, 0.12, 3.1), house)
		for x: float in [-1.0, 1.0]:
			var sl := Vector3(x * TUG_SIDELIGHT.x, TUG_SIDELIGHT.y, TUG_SIDELIGHT.z)
			mb.box(sl + Vector3(0, 0, -0.25), Vector3(0.3, 0.34, 0.06), LAMP_DARK)
			mb.box(sl, Vector3(0.12, 0.24, 0.3), LENS_RED if x > 0.0 else LENS_GREEN)
		mb.box(Vector3(0, (5.42 + TUG_MAST.y) * 0.5, TUG_MAST.z), Vector3(0.16, TUG_MAST.y - 5.42, 0.16), house)
		mb.box(Vector3(0, 6.3, TUG_MAST.z), Vector3(2.4, 0.1, 0.3), house)
		mb.box(Vector3(0, 6.45, TUG_MAST.z), Vector3(1.2, 0.06, 0.1), Color(0.2, 0.2, 0.22))
		add_lantern(mb, TUG_MAST, GlowBuilder.LED, TUG_LANTERN)
		# The stack, behind the wheelhouse.
		mb.box(Vector3(0, 3.9, -1.5), Vector3(1.3, 2.6, 1.4), stack)
		mb.box(Vector3(0, 5.25, -1.5), Vector3(1.32, 0.3, 1.42), Color(0.08, 0.08, 0.08))
		mb.box(Vector3(0, 4.2, -1.5), Vector3(1.34, 0.3, 1.44), WHITE)
		# Towing winch and the staple over the after deck, bitts either side.
		mb.box(Vector3(0, 1.8, -3.6), Vector3(2.2, 1.0, 1.3), steel)
		mb.cylinder(Vector3(0, 1.55, -3.6), 0.5, 0.5, 0.5, 10, Color(0.75, 0.6, 0.18))
		for x: float in [-1.0, 1.0]:
			mb.box(Vector3(x * 1.9, 2.4, -5.8), Vector3(0.3, 2.2, 0.3), stack)
			mb.cylinder(Vector3(x * 1.4, 1.3, -6.3), 0.2, 0.2, 0.5, 8, steel)
		mb.box(Vector3(0, 3.5, -5.8), Vector3(4.1, 0.3, 0.3), stack)
		mb.box(TUG_STERN_LIGHT + Vector3(0, 0, 0.06), Vector3(0.18, 0.14, 0.04), lamp_glass(GlowBuilder.LED))
		return mb.commit())


static func tug_lights() -> ArrayMesh:
	return _cached("tug_lights", func():
		var gb := GlowBuilder.new()
		var window := Color(1.0, 0.74, 0.42)
		# The wheelhouse windows (the mid-poly one runs further aft, raked out forward).
		var y := 4.65 if mid_tug else 4.62
		var z0 := 1.0 if mid_tug else 1.3
		var front := 3.6 if mid_tug else 3.55
		for x: float in [-1.56, 1.56]:
			for i in 3:
				gb.reflection(Vector3(x, y, z0 + i * 0.9), window, 0.2, 1.6, Vector3(signf(x), 0, 0))
		for i in 3:
			gb.reflection(Vector3(-1.0 + i, y, front), window, 0.2, 1.6, Vector3(0, 0, 1))
		return gb.commit())


## Sidelights and stern light, shown under way.
static func tug_nav_lights() -> ArrayMesh:
	return _cached("tug_nav", func():
		var gb := GlowBuilder.new()
		var sl := _tug_sidelight()
		if not mid_tug:
			sl.z += 0.1
		gb.glow(Vector3(sl.x, sl.y, sl.z), GlowBuilder.RED, 0.18, 6.0, true, 0.0, Vector3(1, 0, 0.8), 0.0)
		gb.glow(Vector3(-sl.x, sl.y, sl.z), GlowBuilder.GREEN, 0.18, 6.0, true, 0.0, Vector3(-1, 0, 0.8), 0.0)
		gb.glow(_tug_stern_light(), GlowBuilder.LED, 0.12, 4.0, true, 0.0, Vector3(0, 0, -1), 0.0)
		return gb.commit())


## The masthead light, shown under way.
static func tug_mast_light() -> ArrayMesh:
	return _cached("tug_mast", func():
		var gb := GlowBuilder.new()
		gb.glow(lantern_glow_at(_tug_mast(), TUG_LANTERN), GlowBuilder.LED, 0.2, 7.0, true, 0.0, Vector3.ZERO, 0.0)
		return gb.commit())


const LIGHTHOUSE_KIT := "res://assets/models/lighthouse_kit.glb"
const LIGHTHOUSE_TOWERS := ["doubleband", "timber", "ironwork", "brick"]
const LIGHTHOUSE_ROOFS := ["oxblood", "copper", "graphite"]
const LIGHTHOUSE_HOUSES := ["keepershouse", "porchbungalow", "brickquarters"]
const LIGHTHOUSE_VARIANTS := 24
const LIGHTHOUSE_LENS_Y := 2.08
const LIGHTHOUSE_RAIL_Y := 1.53
const LIGHTHOUSE_RAIL_RADIUS := 3.07


## Four shafts and three caps. Returns the gallery's
## frame so birds and the sweeping light share the same mounting point as the art.
static func add_lighthouse(mb: MeshBuilder, base: Vector3, variant := 0, yaw := 0.0) -> Transform3D:
	var lib := ModelParts.library(LIGHTHOUSE_KIT)
	var tower: String = LIGHTHOUSE_TOWERS[variant % LIGHTHOUSE_TOWERS.size()]
	var roof: String = LIGHTHOUSE_ROOFS[(variant / LIGHTHOUSE_TOWERS.size()) % LIGHTHOUSE_ROOFS.size()]
	var foot := Transform3D(Basis(Vector3.UP, yaw), base)
	var shaft: MeshBuilder = lib[tower]
	_append_part(mb, shaft, foot)
	var gallery := foot.translated_local(Vector3.UP * _lighthouse_gallery_height(shaft))
	_append_part(mb, lib["gallery"], gallery)
	_append_part(mb, lib[roof], gallery.translated_local(Vector3.UP * 3.23))
	return gallery


static func add_keepers_house(mb: MeshBuilder, foot: Transform3D, style: int) -> void:
	var lib := ModelParts.library(LIGHTHOUSE_KIT)
	_append_part(mb, lib[LIGHTHOUSE_HOUSES[style]], foot)


static func _lighthouse_gallery_height(shaft: MeshBuilder) -> float:
	var height := 0.0
	for vertex in shaft.verts:
		height = maxf(height, vertex.y)
	return height


## A channel buoy with its flashing lantern on a short post at the top (see
## buoy_glow_at for where its glow goes).
static func add_buoy(mb: MeshBuilder, base: Vector3, col: Color, light: Color, blink_phase: float) -> void:
	mb.cylinder(base + Vector3(0, -1.5, 0), 1.5, 1.35, 3.9, 6, col)
	mb.cylinder(base + Vector3(0, 2.4, 0), 0.9, 0.0, 2.1, 6, col.darkened(0.2))
	mb.cylinder(base + Vector3(0, 3.6, 0), 0.18, 0.18, 1.35, 6, LAMP_DARK)
	add_cage_lantern(mb, base + Vector3(0, BUOY_LAMP_Y, 0), light, BUOY_LANTERN, blink_phase)


static func buoy_glow_at(base: Vector3) -> Vector3:
	return cage_lantern_glow_at(base + Vector3(0, BUOY_LAMP_Y, 0), BUOY_LANTERN)


# --- Lamp fixtures --------------------------------------------------------------------
# The fixtures are solid geometry in the lit_vc mesh; the glow sits in their glass
# (GlowBuilder, which draws in a separate mesh), so each pair of helpers below
# agrees on where that is.

## Pale glass in a light's colour, lit at night; flashing if `blink_phase` (0..1, from
## blink_phase_at) is given.
static func lamp_glass(col: Color, blink_phase := -1.0) -> Color:
	var c := col.lerp(Color.WHITE, 0.2)
	c.a = LAMP_GLASS_ALPHA
	if blink_phase >= 0.0:
		c.a = (BLINK_ALPHA0 + roundi(blink_phase * BLINK_STEPS) % BLINK_STEPS) / 255.0
	return c


## A flash phase picked from a light's position, on the steps flashing glass can hold.
static func blink_phase_at(p: Vector3) -> float:
	var h := fposmod(sin(p.x * 12.9898 + p.z * 78.233) * 43758.5453, 1.0)
	return floorf(h * BLINK_STEPS) / BLINK_STEPS


## GlowBuilder's blink for a light flashing with `phase`.
static func blink_of(phase: float) -> float:
	return BLINK_PERIOD + phase


## A caged bulkhead lamp, the ship's-deck kind: a round plate on the wall at `p`,
## an arm out along `out` (horizontal) to a domed cap, and the glass hanging under
## it in a cage. `s` scales it (1: about half a metre tall).
static func add_bulkhead_lamp(mb: MeshBuilder, p: Vector3, out: Vector3, col: Color, s := 1.0, body := BRASS) -> void:
	var saved := mb.xform
	mb.xform = saved * _lamp_frame(p, out, s)
	mb.box(Vector3(0, 0.02, 0.02), Vector3(0.2, 0.24, 0.04), body)
	mb.box(Vector3(0, 0.06, 0.11), Vector3(0.07, 0.07, 0.16), body)
	mb.cylinder(Vector3(0, 0.0, 0.24), 0.12, 0.1, 0.1, 8, body, Color(-1, 0, 0), PI / 8.0)
	mb.cylinder(Vector3(0, 0.1, 0.24), 0.1, 0.0, 0.05, 8, body, Color(-1, 0, 0), PI / 8.0)
	mb.cylinder(Vector3(0, -0.03, 0.24), 0.125, 0.125, 0.03, 8, body, Color(-1, 0, 0), PI / 8.0)
	var glass := lamp_glass(col)
	mb.cylinder(Vector3(0, -0.27, 0.24), 0.085, 0.085, 0.24, 8, glass, Color(-1, 0, 0), PI / 8.0)
	mb.cylinder(Vector3(0, -0.32, 0.24), 0.0, 0.085, 0.05, 8, glass, Color(-1, 0, 0), PI / 8.0)
	# The cage: four bars round the glass, a band at its waist, a ring at the foot.
	for i in 4:
		var a := TAU * (i + 0.5) / 4.0
		mb.box(Vector3(cos(a) * 0.1, -0.15, 0.24 + sin(a) * 0.1), Vector3(0.022, 0.27, 0.022), body)
	mb.cylinder(Vector3(0, -0.16, 0.24), 0.1, 0.1, 0.025, 8, body, Color(-1, 0, 0), PI / 8.0)
	mb.cylinder(Vector3(0, -0.31, 0.24), 0.08, 0.08, 0.025, 8, body, Color(-1, 0, 0), PI / 8.0)
	mb.xform = saved


## Where add_bulkhead_lamp's glass is, and its radius: put the glow there.
static func bulkhead_glow_at(p: Vector3, out: Vector3, s := 1.0) -> Vector3:
	return _lamp_frame(p, out, s) * Vector3(0, -0.16, 0.24)


static func bulkhead_glow_size(s := 1.0) -> float:
	return 0.1 * s


## A masthead lantern standing on `base`: a dark foot, a glass drum and a conical
## cap. `s` scales it (1: about 0.4 m tall).
static func add_lantern(mb: MeshBuilder, base: Vector3, col: Color, s := 1.0) -> void:
	mb.cylinder(base, 0.13 * s, 0.11 * s, 0.06 * s, 8, LAMP_DARK)
	mb.cylinder(base + Vector3(0, 0.06 * s, 0), 0.09 * s, 0.09 * s, 0.2 * s, 8, lamp_glass(col))
	mb.cylinder(base + Vector3(0, 0.26 * s, 0), 0.13 * s, 0.0, 0.1 * s, 8, LAMP_DARK)


static func lantern_glow_at(base: Vector3, s := 1.0) -> Vector3:
	return base + Vector3(0, 0.16 * s, 0)


## A brass-caged 360° lantern standing on `base`, for buoys, dolphins and the ramp
## lift: a foot, a glass drum in a cage of bars, and a domed cap. `s` scales it (1:
## about half a metre tall); `blink_phase` makes the glass flash (see lamp_glass).
static func add_cage_lantern(mb: MeshBuilder, base: Vector3, col: Color, s := 1.0, blink_phase := -1.0) -> void:
	var saved := mb.xform
	mb.xform = saved * Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * s), base)
	var r := PI / 8.0
	var none := Color(-1, 0, 0)
	mb.cylinder(Vector3.ZERO, 0.13, 0.11, 0.05, 8, BRASS, none, r)
	mb.cylinder(Vector3(0, 0.05, 0), 0.085, 0.085, 0.24, 8, lamp_glass(col, blink_phase), none, r)
	for i in 4:
		var a := TAU * (i + 0.5) / 4.0
		mb.box(Vector3(cos(a) * 0.1, 0.17, sin(a) * 0.1), Vector3(0.022, 0.24, 0.022), BRASS)
	mb.cylinder(Vector3(0, 0.16, 0), 0.1, 0.1, 0.025, 8, BRASS, none, r)
	mb.cylinder(Vector3(0, 0.29, 0), 0.13, 0.11, 0.05, 8, BRASS, none, r)
	mb.cylinder(Vector3(0, 0.34, 0), 0.11, 0.0, 0.08, 8, BRASS, none, r)
	mb.box(Vector3(0, 0.44, 0), Vector3(0.03, 0.06, 0.03), BRASS)
	mb.xform = saved


static func cage_lantern_glow_at(base: Vector3, s := 1.0) -> Vector3:
	return base + Vector3(0, 0.17 * s, 0)


## A sidelight on a wheelhouse wall at `w` (on its side `sx`, ±1, and the end
## `sz`, ±1, it serves): a lens drum on a bracket, a cap, and a screen on its aft
## side so it only shows ahead and abeam. Whichever end is the bow, port is where x
## and z have the same sign, so that lens is red and the other green.
static func add_sidelight(mb: MeshBuilder, w: Vector3, sx: float, sz: float, s := FERRY_SIDELIGHT_SCALE) -> void:
	var c := w + Vector3(sx * 0.2 * s, 0, 0)
	var none := Color(-1, 0, 0)
	mb.box(w + Vector3(sx * 0.1 * s, -0.13 * s, 0), Vector3(0.24 * s, 0.04 * s, 0.34 * s), LAMP_DARK)
	mb.box(w + Vector3(sx * 0.04 * s, 0, 0), Vector3(0.08 * s, 0.3 * s, 0.34 * s), LAMP_DARK)
	mb.cylinder(c + Vector3(0, -0.11 * s, 0), 0.11 * s, 0.11 * s, 0.2 * s, 8, NAV_RED if sx * sz > 0.0 else NAV_GREEN, none, PI / 8.0)
	mb.cylinder(c + Vector3(0, 0.09 * s, 0), 0.13 * s, 0.09 * s, 0.05 * s, 8, LAMP_DARK, none, PI / 8.0)
	# Screen on the aft side (towards the middle of the ship).
	mb.box(c + Vector3(-sx * 0.02 * s, -0.01 * s, -sz * 0.14 * s), Vector3(0.3 * s, 0.26 * s, 0.03 * s), LAMP_DARK)


static func sidelight_glow_at(w: Vector3, sx: float, s := FERRY_SIDELIGHT_SCALE) -> Vector3:
	return w + Vector3(sx * 0.2 * s, 0, 0)


## Frame for a wall fixture at `p`: +Z out from the wall, +Y up, scaled by `s`.
static func _lamp_frame(p: Vector3, out: Vector3, s: float) -> Transform3D:
	var z := Vector3(out.x, 0.0, out.z).normalized()
	var x := Vector3.UP.cross(z)
	return Transform3D(Basis(x, Vector3.UP, z).scaled(Vector3.ONE * s), p)

