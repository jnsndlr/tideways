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


## Car-deck nets at either end share their class mesh.
static func ferry_net(fc: FerryClass) -> ArrayMesh:
	var key := "ferry_net_mid_%d" if FerryNetModel.authored else "ferry_net_%d"
	return _cached(key % fc.size, func(): return FerryNetModel.build(fc))


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


static func seagull() -> ArrayMesh:
	var key := "seagull_mid" if SeagullModel.baked_fold else "seagull"
	return _cached(key, func(): return SeagullModel.build(vc_material()))


## A bald eagle at life size, 2.1 m across (+Z forward, wings out along X), modelled
## in Blender (EAGLE_GLB, built by art/eagle_mid.py) to eagle.gdshader's conventions:
## wing vertices alpha 0.5 carrying their folded pose in UV / UV2.x, legs 0.93, tail
## 0.97. Null if the model is missing (then there are no eagles).
const EAGLE_GLB := "res://assets/models/eagle_mid.glb"


static func eagle() -> ArrayMesh:
	if not ResourceLoader.exists(EAGLE_GLB):
		return null
	return _cached("eagle_mid", func(): return ModelParts.shader_mesh(EAGLE_GLB, "eagle", vc_material()))


static func orca() -> ArrayMesh:
	var key := "orca_mid" if OrcaModel.uv_markings else "orca"
	return _cached(key, func(): return OrcaModel.build(vc_material()))


static func humpback() -> ArrayMesh:
	var key := "humpback_mid" if WhaleModel.authored else "humpback"
	return _cached(key, func(): return WhaleModel.humpback(vc_material()))


static func gray_whale() -> ArrayMesh:
	var key := "gray_whale_mid" if WhaleModel.authored else "gray_whale"
	return _cached(key, func(): return WhaleModel.gray_whale(vc_material()))


static func dalls_porpoise() -> ArrayMesh:
	return _cached("dalls_porpoise", func(): return PorpoiseModel.dalls_porpoise(vc_material()))


static func harbor_porpoise() -> ArrayMesh:
	return _cached("harbor_porpoise", func(): return PorpoiseModel.harbor_porpoise(vc_material()))


static func harbor_seal() -> ArrayMesh:
	var key := "harbor_seal_mid" if PinnipedModel.authored else "harbor_seal"
	return _cached(key, func(): return PinnipedModel.harbor_seal(vc_material()))


static func sea_lion() -> ArrayMesh:
	var key := "sea_lion_mid" if PinnipedModel.authored else "sea_lion"
	return _cached(key, func(): return PinnipedModel.sea_lion(vc_material()))


## A blow or a splash: a white plume one unit tall, drawn per puff by Cetaceans.
static func spout() -> ArrayMesh:
	return _cached("spout", func():
		var mb := MeshBuilder.new()
		mb.cylinder(Vector3.ZERO, 0.12, 0.45, 0.6, 6, Color(0.95, 0.97, 1.0, 0.85))
		mb.cylinder(Vector3(0, 0.6, 0), 0.45, 0.2, 0.4, 6, Color(0.95, 0.97, 1.0, 0.6))
		return mb.commit(unshaded_material()))


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


static func sailboat() -> ArrayMesh:
	return _cached("sailboat_mid" if SailboatModel.authored else "sailboat", SailboatModel.hull)


static func sailboat_main() -> ArrayMesh:
	return _cached(
		"sailboat_main_mid" if SailboatModel.authored else "sailboat_main", SailboatModel.mainsail
	)


static func sailboat_jib() -> ArrayMesh:
	return _cached(
		"sailboat_jib_mid" if SailboatModel.authored else "sailboat_jib", SailboatModel.jib
	)


static func sailboat_furled() -> ArrayMesh:
	return _cached(
		"sailboat_furled_mid" if SailboatModel.authored else "sailboat_furled",
		func(): return SailboatModel.hull(true)
	)


static func sailboat_lights() -> ArrayMesh:
	return _cached("sailboat_lights", SailboatModel.anchor_light)


static func cargo_ship(variant: int) -> ArrayMesh:
	var key := "cargo_mid_%d" if CargoShipModel.authored_container else "cargo_%d"
	return _cached(key % variant, func(): return CargoShipModel.container(variant))


static func tanker(variant: int) -> ArrayMesh:
	var key := "tanker_mid_%d" if CargoShipModel.authored_tanker else "tanker_%d"
	return _cached(key % variant, func(): return CargoShipModel.tanker(variant))


static func bulk_carrier(variant: int) -> ArrayMesh:
	var key := "bulker_mid_%d" if CargoShipModel.authored_bulker else "bulker_%d"
	return _cached(key % variant, func(): return CargoShipModel.bulker(variant))


static func cargo_name_plate(ship_name: String) -> ArrayMesh:
	if not CargoShipModel.authored_container:
		return null
	return _cached("cargo_name_" + ship_name, func(): return CargoHullLettering.build(ship_name))


static func cargo_ship_lights(mid := CargoShipModel.authored_container) -> ArrayMesh:
	var key := "cargo_mid_lights" if mid else "cargo_lights"
	return _cached(key, func(): return CargoShipModel.lights(mid))


## Appends `part` to `mb` moved by `xf` (rigid, or uniformly scaled), its colours multiplied by
## `tint`, or all painted `paint` if that is given.
static func _append_part(mb: MeshBuilder, part: MeshBuilder, xf: Transform3D, tint := Color.WHITE,
		paint := Color(-1, 0, 0)) -> void:
	mb.append_part(part, xf, tint, paint)


static func trawler(variant: int) -> ArrayMesh:
	var key := "trawler_mid_%d" if TrawlerModel.authored else "trawler_%d"
	return _cached(key % variant, func(): return TrawlerModel.hull(variant))


static func trawler_warps() -> ArrayMesh:
	return _cached("trawler_warps", TrawlerModel.warps)


static func trawler_lights() -> ArrayMesh:
	return _cached("trawler_lights", TrawlerModel.wheelhouse_lights)


static func trawler_nav_lights() -> ArrayMesh:
	return _cached("trawler_nav", TrawlerModel.navigation_lights)


static func trawler_steaming_lights() -> ArrayMesh:
	return _cached("trawler_steaming", TrawlerModel.steaming_lights)


static func trawler_working_lights() -> ArrayMesh:
	return _cached("trawler_working", TrawlerModel.working_lights)


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


static func pilot_boat(variant: int) -> ArrayMesh:
	var key := "pilot_mid_%d" if PilotBoatModel.authored else "pilot_%d"
	return _cached(key % variant, func(): return PilotBoatModel.hull(variant))


static func pilot_ladder(out: float, deck: float) -> ArrayMesh:
	return _cached(
		"pilot_ladder_%.2f_%.2f" % [out, deck], func(): return PilotBoatModel.ladder(out, deck)
	)


static func pilot_boat_lights() -> ArrayMesh:
	return _cached("pilot_lights", PilotBoatModel.lights)


static func pilot_boat_nav_lights() -> ArrayMesh:
	return _cached("pilot_nav", PilotBoatModel.navigation_lights)


static func pilot_boat_duty_lights() -> ArrayMesh:
	return _cached("pilot_duty", PilotBoatModel.duty_lights)


static func tug(variant: int) -> ArrayMesh:
	var key := "tug_mid_%d" if TugModel.authored else "tug_%d"
	return _cached(key % variant, func(): return TugModel.hull(variant))


static func tug_lights() -> ArrayMesh:
	return _cached("tug_lights", TugModel.lights)


static func tug_nav_lights() -> ArrayMesh:
	return _cached("tug_nav", TugModel.navigation_lights)


static func tug_mast_light() -> ArrayMesh:
	return _cached("tug_mast", TugModel.mast_light)


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


## Size and marking shared by fitted and classic guide dolphins.
const DOLPHIN_LANTERN := 3.9


static func slip_mark(port: bool) -> Color:
	return GlowBuilder.GREEN if port else GlowBuilder.RED


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

