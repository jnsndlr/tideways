class_name TreeModel
extends RefCounted
## Supplies tree meshes, distance levels, cards and shadows to both forests and backdrop.

## Trees use the faceted ones modelled in Blender (TREES_GLB, built by art/trees.py into
## art/trees.blend): several pines and broadleaves, each with a cheap stand-in
## ("<name>_lod") for far off. The two above are the fallback: with `--classic-trees`,
## or if the model is missing.
const TREES_GLB := "res://assets/models/trees.glb"

const SPRUCE_VARIANTS := [
	"spruce", "spruce_open", "spruce_lean", "spruce_broad", "spruce_tall", "spruce_young"
]

## Jon's pine (matching the Backdrop's card sprite), baked by art/pines_meshy.py; the
## spruces above with `--old-pines`.
const MPINES_GLB := "res://assets/models/pines_meshy.glb"

const MPINE_VARIANTS := ["mpine", "mpine_tall", "mpine_broad", "mpine_young"]

## The 300-triangle pine (art/pine_tree.py's stand-in): one model drawn out to
## impostor_dist and as its impostor (tree_impostor.gdshader, baked by
## tools/bake_impostor.gd) past it, its variants that model rescaled as Jon's pines'
## are. Jon's pines above with `--meshy-pines`.
const LPINE_GLB := "res://assets/models/pine_tree_lod.glb"

const LPINE_SCALE := {
	"lpine": Vector3.ONE,
	"lpine_tall": Vector3(0.98, 1.16, 0.98),
	"lpine_broad": Vector3(0.93, 0.81, 0.93),
	"lpine_young": Vector3(0.53, 0.53, 0.53)
}

const IMPOSTOR_DIR := "res://assets/textures/impostors/"

const BROAD_VARIANTS := ["oak", "poplar", "spreading", "leaning", "round", "birches"]

const CARD_SHADER := "res://shaders/tree_card.gdshader"

const CARD_SPRITE := "res://assets/textures/pine_card.png"

const BROAD_CARD_SPRITE := "res://assets/textures/broad_card.png"

## How wide a stand-in is drawn against its full tree's crown: being solid, it reads
## bigger than an airy crown of the same outline (Jon's pines', the broadleaves' clumps).
const STAND_IN_WIDTH := {"mpine": 0.8, "broad": 0.85}

## The impostor's layout (tools/bake_impostor.gd, tree_impostor.gdshader): frames of
## IMPOSTOR_FRAME px, a column per IMPOSTOR_AZIMUTHS headings round the tree, a row per
## IMPOSTOR_ELEVATIONS heights above it, IMPOSTOR_EL_STEP degrees apart from level.
const IMPOSTOR_SHADER := "res://shaders/tree_impostor.gdshader"

const IMPOSTOR_FRAME := 128

const IMPOSTOR_AZIMUTHS := 16

const IMPOSTOR_ELEVATIONS := 4

const IMPOSTOR_EL_STEP := 20.0

static var authored := (
	not "--classic-trees" in OS.get_cmdline_user_args() and ResourceLoader.exists(TREES_GLB)
)

static var pine_variants: Array = (
	(func() -> Array:
		var args := OS.get_cmdline_user_args()
		if "--old-pines" in args:
			return SPRUCE_VARIANTS
		if ResourceLoader.exists(LPINE_GLB) and not "--meshy-pines" in args:
			return LPINE_SCALE.keys()
		return MPINE_VARIANTS if ResourceLoader.exists(MPINES_GLB) else SPRUCE_VARIANTS)
	. call()
)

static var _card_mat: ShaderMaterial

static var _broad_card_mat: ShaderMaterial

## A tree drawn as its card sprite, standing as tall as the modelled `near` one: a pine
## in the sprite's own 250 x 353 proportions, a broadleaf as wide as its crown.
## tree_card.gdshader turns it to the camera.
static var _cards := {}

## The pine card toned to the far pines' muted olive (tree_card.gdshader). Tune with
## `--card-tone=contrast,saturation[,yellow_cap,low_sun,low_sun_direct]`.
static var card_contrast := 0.6

static var card_saturation := 0.85

static var card_yellow_cap := 0.65

static var card_low_sun := 0.7

static var card_low_sun_direct := 0.3

static var _card_tone: bool = (
	(func() -> bool:
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--card-tone="):
				var d := a.substr(12).split_floats(",")
				card_contrast = d[0]
				card_saturation = d[1]
				if d.size() > 2:
					card_yellow_cap = d[2]
				if d.size() > 3:
					card_low_sun = d[3]
				if d.size() > 4:
					card_low_sun_direct = d[4]
		return true)
	. call()
)


static func classic_pine() -> ArrayMesh:
	return Models._cached(
		"pine",
		func():
			var mb := MeshBuilder.new()
			mb.cylinder(Vector3(0, -0.4, 0), 0.28, 0.2, 1.6, 5, Color(0.36, 0.25, 0.17))
			mb.cylinder(
				Vector3(0, 0.9, 0), 1.6, 0.0, 2.4, 6, Color(0.16, 0.34, 0.22), Color(-1, 0, 0), 0.3
			)
			mb.cylinder(
				Vector3(0, 2.2, 0), 1.25, 0.0, 2.1, 6, Color(0.25, 0.42, 0.2), Color(-1, 0, 0), 0.8
			)
			mb.cylinder(
				Vector3(0, 3.4, 0), 0.85, 0.0, 1.8, 6, Color(0.34, 0.5, 0.19), Color(-1, 0, 0), 0.1
			)
			return mb.commit()
	)


static func classic_broadleaf() -> ArrayMesh:
	return Models._cached(
		"round",
		func():
			var mb := MeshBuilder.new()
			mb.cylinder(Vector3(0, -0.4, 0), 0.26, 0.2, 1.8, 5, Color(0.38, 0.27, 0.18))
			var c := Color(0.4, 0.53, 0.19)
			mb.cylinder(Vector3(0, 1.2, 0), 0.9, 1.5, 0.9, 7, c)
			mb.cylinder(Vector3(0, 2.1, 0), 1.5, 0.6, 1.2, 7, c.lightened(0.08))
			return mb.commit()
	)


## The pine (or broadleaf) variants as [near mesh, far mesh or null, middle mesh or null,
## card or null, farthest mesh or null]. Jon's pines' and the broadleaves' "far"
## (stand-ins) only cast their shadows (or with `--cone-trees`, are drawn in place of the
## card); "farthest" is what Jon's pines draw from mpine_mid_dist.
static func variants(broadleaf: bool) -> Array:
	if not authored:
		return [[classic_broadleaf() if broadleaf else classic_pine(), null, null, null]]
	var out := []
	for n: String in BROAD_VARIANTS if broadleaf else pine_variants:
		if n.begins_with("lpine"):
			# One model all the way out, casting its own shadow, then its impostor.
			var m := part(n)
			out.append([m, m, null, impostor_card(n, m), null])
			continue
		var near := part(n)
		var lod := part(n + "_lod")
		if (
			(broadleaf or n.begins_with("mpine"))
			and not "--raw-stand-ins" in OS.get_cmdline_user_args()
		):
			lod = _fit_stand_in(n, lod, near)
		out.append(
			[
				near,
				lod,
				part(n + "_mid") if n.begins_with("spruce") or n.begins_with("mpine") else null,
				tree_card(n, near) if n.begins_with("mpine") or broadleaf else null,
				part(n + "_far") if n.begins_with("mpine") else null
			]
		)
	return out


## `lod` moved and scaled so it stands where `near` does, so zooming across the swap
## doesn't grow or shift the trees: its foliage (green vertices) fitted to `near`'s
## crown, STAND_IN_WIDTH as wide, the trunk below stretched to meet it.
static func _fit_stand_in(n: String, lod: ArrayMesh, near: ArrayMesh) -> ArrayMesh:
	return Models._cached(
		"tree_fit_" + n,
		func():
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
				var cs: PackedColorArray = (
					arr[Mesh.ARRAY_COLOR] if arr[Mesh.ARRAY_COLOR] != null else PackedColorArray()
				)
				for j in vs.size():
					var v := vs[j]
					var y: float
					if v.y >= a.position.y:
						y = b.position.y + (v.y - a.position.y) * b.size.y / a.size.y
					else:
						y = (
							foot
							+ (v.y - foot) * (b.position.y - foot) / maxf(a.position.y - foot, 0.01)
						)
					if cs.is_empty() or _leafy(cs[j]):
						vs[j] = Vector3(cb.x + (v.x - ca.x) * sx, y, cb.z + (v.z - ca.z) * sz)
					else:
						vs[j] = Vector3(v.x, y, v.z)
				arr[Mesh.ARRAY_VERTEX] = vs
				out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
				out.surface_set_material(i, lod.surface_get_material(i))
			return out
	)


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
				box = AABB(vs[j], Vector3.ZERO)
				first = false
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
			_broad_card_mat.set_shader_parameter("low_sun", card_low_sun)
			_broad_card_mat.set_shader_parameter("low_sun_direct", card_low_sun_direct)
		return _broad_card_mat
	if _card_mat == null:
		_card_mat = ShaderMaterial.new()
		_card_mat.shader = load(CARD_SHADER)
		_card_mat.set_shader_parameter("sprite", load(CARD_SPRITE))
		_card_mat.set_shader_parameter("sprite_mean", _sprite_mean(CARD_SPRITE))
		_card_mat.set_shader_parameter("contrast", card_contrast)
		_card_mat.set_shader_parameter("saturation", card_saturation)
		_card_mat.set_shader_parameter("yellow_cap", card_yellow_cap)
		_card_mat.set_shader_parameter("low_sun", card_low_sun)
		_card_mat.set_shader_parameter("low_sun_direct", card_low_sun_direct)
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


static func tree_card(n: String, near: Mesh) -> Mesh:
	if not _cards.has(n):
		var box := near.get_aabb()
		var q := QuadMesh.new()
		var broadleaf := not n.begins_with("mpine")
		q.size = Vector2(
			maxf(box.size.x, box.size.z) if broadleaf else box.size.y * 0.71, box.size.y
		)
		q.center_offset = Vector3(0.0, box.position.y + box.size.y * 0.5, 0.0)
		# It faces the camera whichever way the tree is turned.
		q.custom_aabb = AABB(
			Vector3(-q.size.x, box.position.y, -q.size.x),
			Vector3(q.size.x * 2.0, box.size.y, q.size.x * 2.0)
		)
		q.material = card_material(broadleaf)
		_cards[n] = q
	return _cards[n]


## The model the impostor is baked from and the sphere it's framed in: [mesh, centre, radius].
static func impostor_base() -> Array:
	var m := part("lpine")
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


## Which variant a tree standing at `at` is: from its position, so the choice draws
## no random numbers and the rest of the map comes out the same.
static func variant_at(at: Vector3, count: int) -> int:
	return absi(hash(Vector2i(roundi(at.x * 10.0), roundi(at.z * 10.0)))) % count


static func part(n: String) -> ArrayMesh:
	if n.begins_with("lpine"):
		return Models._cached(
			"tree_" + n,
			func():
				var mb := ModelParts.merge_named(LPINE_GLB, ["pinetreelod"])
				var k: Vector3 = LPINE_SCALE[n]
				for i in mb.verts.size():
					mb.verts[i] *= k
					mb.normals[i] = (mb.normals[i] / k).normalized()
				var m := mb.commit()
				m.set_meta("impostor_base", "lpine")
				return m
		)
	var glb := MPINES_GLB if n.begins_with("mpine") else TREES_GLB
	return Models._cached(
		"tree_" + n, func(): return ModelParts.merge_named(glb, [n.replace("_", "")]).commit()
	)
