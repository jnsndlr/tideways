class_name Backdrop
extends Node3D
## The world past the map: the mainland's shores, foothills and snowy ranges
## (Terrain.outer_height, i.e. Mainland) out to the horizon. They're painted with
## their own aerial haze (backdrop.gdshader) so distant layers fade into the sky like
## a landscape painting instead of vanishing into the depth fog. The clouds behind
## them are in the sky shader (sky.gdshader).
##
## The land is a ring of rings around the terrain grid: the first ring is the grid's
## own edge vertices (so the two meet without a crack), and each ring further out is
## a little larger, halving its samples twice so far ranges get broad facets.

const LAND_SHADER := "res://shaders/backdrop.gdshader"

const SAND := Color(0.8, 0.73, 0.54)
const CLIFF := Color(0.5, 0.43, 0.42)
const CLIFF_LIGHT := Color(0.63, 0.54, 0.49)
const FOREST := Color(0.12, 0.24, 0.15)
const FOREST_LIGHT := Color(0.19, 0.31, 0.17)
const FOREST_DARK := Color(0.1, 0.19, 0.15)
const ALPINE := Color(0.36, 0.4, 0.48)
const ALPINE_LIGHT := Color(0.46, 0.49, 0.56)
const SNOW := Color(0.94, 0.95, 0.98)

## Modelled trees where the mainland touches the map; flat cards (tree_card.gdshader)
## on the far shores, thinning out with distance. The two cross-fade between
## TREE_FADE and TREE_BAND past the edge, so there's no line where one gives way.
const TREE_FADE := 60.0
const TREE_BAND := 200.0  # (without a WorldBuilder; with one, WorldBuilder.card_share)
## Over this far past the edge the ground and its woods turn from the islands' own
## (WorldBuilder.ground_color, tree_density: fields and patchy woods) to the
## mainland's unbroken forest, so the map's edge doesn't show as a line.
const EDGE_BLEND := 600.0
## Within this far past the edge the land is coloured per vertex, not per facet.
const VERTEX_COLOURED := 1500.0
const TREE_TILE := 384.0
const CARD_SHADER := "res://shaders/tree_card.gdshader"
const CARD_SPRITE := "res://assets/textures/pine_card.png"
const CARD_FAR := 3000.0
const CARD_TILE := 768.0

var terrain: Terrain
var builder: WorldBuilder
var _rng := RandomNumberGenerator.new()
var _trees: Array[Transform3D] = []
var _tree_cols: Array[Color] = []
var _cards: Array[Transform3D] = []
var _near_trees: Array[MultiMeshInstance3D] = []
var _card_cols: Array[Color] = []


func setup(t: Terrain, b: WorldBuilder = null) -> void:
	name = "Backdrop"
	terrain = t
	builder = b
	_rng.seed = int(t.mainland.snowline * 1000.0)
	_build_land()
	if builder:
		# The cards WorldBuilder put inside the map, on the mainland's shores.
		for at in builder.edge_cards:
			_card_at(at)
	_build_trees()


# --- Land ---------------------------------------------------------------------------

func _build_land() -> void:
	var hs := terrain.half_size
	var n := terrain.n
	var smax := Mainland.FAR / hs
	var mb := MeshBuilder.new()

	var inner := _edge_ring()
	# 15 m rings for the near shore, then 30 m samples on rings growing ~2% each.
	var d := 24.0
	var level := 1
	while true:
		var s := 1.0 + d / hs
		if s > smax:
			break
		var outer := _ring(s, n >> level)
		_stitch(mb, inner, outer)
		inner = outer
		if d < 420.0:
			d += 15.0
		else:
			level = 2
			d = (s * 1.022 - 1.0) * hs
	var mi := MeshInstance3D.new()
	mi.name = "Mainland"
	mi.mesh = mb.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load(LAND_SHADER)
	mat.set_shader_parameter("map_half", terrain.half_size)
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


## The terrain grid's boundary vertices, clockwise from the (-x, -z) corner.
func _edge_ring() -> PackedVector3Array:
	var n := terrain.n
	var hs := terrain.half_size
	var pts := PackedVector3Array()
	for k in 4 * n:
		var t := k % n
		var i: int
		var j: int
		match k / n:
			0:
				i = t
				j = 0
			1:
				i = n
				j = t
			2:
				i = n - t
				j = n
			_:
				i = 0
				j = n - t
		pts.append(Vector3(-hs + i * Terrain.CELL, terrain.h_index(i, j), -hs + j * Terrain.CELL))
	return pts


## `m` samples per side of the square `s` times the grid's size, in the same order.
func _ring(s: float, m: int) -> PackedVector3Array:
	var e := terrain.half_size * s
	var pts := PackedVector3Array()
	for k in 4 * m:
		var f := float(k % m) / m * 2.0 - 1.0
		var p: Vector2
		match k / m:
			0:
				p = Vector2(f, -1.0)
			1:
				p = Vector2(1.0, f)
			2:
				p = Vector2(-f, 1.0)
			_:
				p = Vector2(-1.0, -f)
		p *= e
		pts.append(Vector3(p.x, terrain.outer_height(p.x, p.y), p.y))
	return pts


## Joins two rings; the inner one has the same number of samples or twice as many.
func _stitch(mb: MeshBuilder, a: PackedVector3Array, b: PackedVector3Array) -> void:
	var na := a.size()
	var nb := b.size()
	if na == nb:
		for k in na:
			var k1 := (k + 1) % na
			if k % 2 == 0:
				_tri(mb, a[k], a[k1], b[k1])
				_tri(mb, a[k], b[k1], b[k])
			else:
				_tri(mb, a[k], a[k1], b[k])
				_tri(mb, a[k1], b[k1], b[k])
	else:
		for c in nb:
			var f0 := a[2 * c]
			var f1 := a[2 * c + 1]
			var f2 := a[(2 * c + 2) % na]
			var c0 := b[c]
			var c1 := b[(c + 1) % nb]
			_tri(mb, f0, f1, c0)
			_tri(mb, f1, c1, c0)
			_tri(mb, f1, f2, c1)


func _tri(mb: MeshBuilder, a: Vector3, b: Vector3, c: Vector3) -> void:
	if a.y < -15.6 and b.y < -15.6 and c.y < -15.6:
		return
	var nrm := (b - a).cross(c - a)
	if nrm.length_squared() < 1e-10:
		return
	nrm = nrm.normalized()
	if nrm.y < 0.0:
		nrm = -nrm
	var p := (a + b + c) / 3.0
	var out := maxf(absf(p.x), absf(p.z)) - terrain.half_size
	var blend := 1.0
	if builder and not builder.backdrop_side(p.x, p.z):
		blend = smoothstep(0.0, EDGE_BLEND, out)
	if out < VERTEX_COLOURED:
		# Coloured per corner near the map, like the terrain, so the beach line runs
		# smoothly instead of stepping from one facet to the next.
		mb.tri3(a, b, c, _ground(a, nrm.y, blend), _ground(b, nrm.y, blend), _ground(c, nrm.y, blend), Vector3.UP)
	else:
		mb.tri(a, b, c, _ground(p, nrm.y, blend), Vector3.UP)
	_wood(a, b, c, p, nrm.y, out, blend)


func _ground(p: Vector3, ny: float, blend: float) -> Color:
	var col := _color(p, ny)
	if blend < 1.0:
		col = builder.ground_color(p.y, ny, p.x, p.z).lerp(col, blend)
	return col


## Forest on gentle ground near the map gets real trees, as on the islands.
func _wood(a: Vector3, b: Vector3, c: Vector3, p: Vector3, ny: float, out: float, blend: float) -> void:
	if out < CARD_FAR and p.y > 4.8 and ny > 0.72 and p.y < _treeline(p) - 180.0:
		var area := (b - a).cross(c - a).length() * 0.5
		# Woods as thick as the islands' at the edge (one try per 8.1 m step),
		# filling in to the mainland's unbroken forest.
		var dense := 1.0
		if blend < 1.0:
			dense = lerpf(clampf(builder.tree_density(p.x, p.z, p.y) * 81.0 / 65.6, 0.0, 1.0), 1.0, blend)
		# Modelled trees give way to cards across the band either side of the edge
		# (WorldBuilder.card_share); a side with no port is cards all the way.
		var cards := builder.card_share(p.x, p.z) if builder else smoothstep(TREE_FADE, TREE_BAND, out)
		if cards > 0.0:
			_scatter_cards(a, b, c, area / 420.0 * dense * cards * (1.0 - smoothstep(1050.0, CARD_FAR, out)))
		var want := area / 81.0 * dense * (1.0 - cards)
		while want > 0.0:
			if _rng.randf() < want:
				var u := _rng.randf()
				var v := _rng.randf()
				if u + v > 1.0:
					u = 1.0 - u
					v = 1.0 - v
				var at := a + (b - a) * u + (c - a) * v
				var s := _rng.randf_range(0.8, 1.45)
				var basis := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(s, s * _rng.randf_range(0.9, 1.25), s) * Models.LEGACY_SCALE)
				_trees.append(Transform3D(basis, at - Vector3(0, 0.3, 0)))
				_tree_cols.append(Color(_rng.randf_range(0.75, 0.95), _rng.randf_range(0.8, 0.95), _rng.randf_range(0.8, 0.95)).darkened(cards * 0.15))
			want -= 1.0


## Island colours on the shore, forest on the hills, bare rock above the trees and
## snow on the tops (what faces up, at least; the shader's haze does the rest).
func _color(p: Vector3, ny: float) -> Color:
	var r := _hash(p.x, p.z)
	var h := p.y
	var snow := _snowline(p)
	var treeline := _treeline(p)
	var col: Color
	if h < -0.9:
		col = SAND.darkened(clampf(-h * 0.023333, 0.0, 0.45))
	elif h < 3.45 and ny >= 0.72:
		col = SAND
	elif h > snow and ny > 0.42:
		col = SNOW
	elif h > treeline:
		col = ALPINE.lerp(ALPINE_LIGHT, r * 0.5)
	elif ny < 0.72 and h < 75.0:
		col = CLIFF.lerp(CLIFF_LIGHT, r)
	elif ny < 0.72:
		# Steep forest: darker, and bare rock showing through high up.
		col = FOREST_DARK.lerp(ALPINE, smoothstep(treeline - 600.0, treeline, h) * r)
	else:
		col = FOREST.lerp(FOREST_LIGHT, r)
	return col.darkened(r * 0.06)



func _scatter_cards(a: Vector3, b: Vector3, c: Vector3, want: float) -> void:
	while want > 0.0:
		if _rng.randf() < want:
			var u := _rng.randf()
			var v := _rng.randf()
			if u + v > 1.0:
				u = 1.0 - u
				v = 1.0 - v
			_card_at(a + (b - a) * u + (c - a) * v)
		want -= 1.0


func _card_at(at: Vector3) -> void:
	var h := _rng.randf_range(21.0, 33.0)
	# The sprite's own proportions (250 x 353), give or take.
	var basis := Basis.from_scale(Vector3(h * 0.71 * _rng.randf_range(0.88, 1.08), h, 1.0))
	_cards.append(Transform3D(basis, at - Vector3(0, 0.9, 0)))
	var k := _rng.randf_range(0.85, 1.1)
	_card_cols.append(Color(k * _rng.randf_range(0.9, 1.05), k, k * _rng.randf_range(0.9, 1.05)))


## Snowline and treeline wander smoothly along the ranges (no per-facet speckle).
func _snowline(p: Vector3) -> float:
	return terrain.mainland.snowline + sin(p.x * 0.0010333 + 1.7) * sin(p.z * 0.0009 + 0.4) * 270.0


func _treeline(p: Vector3) -> float:
	return _snowline(p) - 660.0 + sin(p.x * 0.0023333 + p.z * 0.0016667) * 120.0


## Tiled like WorldBuilder's forests so the camera culls what it can't see.
func _build_trees() -> void:
	# Tiles per pine variant (Models.tree_variants), each level of detail at its
	# distances (Models.tree_lod_levels).
	var variants := Models.tree_variants(false)
	var tiles := {}
	for i in _trees.size():
		var o := _trees[i].origin
		var key := Vector3i(floori(o.x / TREE_TILE), floori(o.z / TREE_TILE), Models.tree_variant(o, variants.size()))
		if not tiles.has(key):
			tiles[key] = []
		tiles[key].append(i)
	for key: Vector3i in tiles:
		var idx: Array = tiles[key]
		var levels := Models.tree_lod_levels(variants[key.z])
		for l in levels.size():
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_colors = true
			mm.mesh = levels[l][0]
			mm.instance_count = idx.size()
			for j in idx.size():
				mm.set_instance_transform(j, _trees[idx[j]])
				mm.set_instance_color(j, _tree_cols[idx[j]])
			var mmi := MultiMeshInstance3D.new()
			mmi.multimesh = mm
			# Dense forest hides its own floor; their shadows aren't worth the cascades.
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			var c := mm.get_aabb().get_center()
			var slack := 0.0
			for i: int in idx:
				slack = maxf(slack, _trees[i].origin.distance_to(c))
			Models.dither_lod(mmi, levels[l][0], levels[l][1], levels[l][2], slack, levels[l][3] if levels[l].size() > 3 else Vector3.ONE)
			_near_trees.append(mmi)
			mmi.name = "MainlandPines_%d_%d_%d%s" % [key.x, key.y, key.z, "_lod%d" % l if l > 0 else ""]
			add_child(mmi)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	quad.center_offset = Vector3(0.0, 0.5, 0.0)
	var mat := ShaderMaterial.new()
	mat.shader = load(CARD_SHADER)
	mat.set_shader_parameter("sprite", load(CARD_SPRITE))
	mat.set_shader_parameter("map_half", terrain.half_size)
	quad.material = mat
	tiles = {}
	for i in _cards.size():
		var o := _cards[i].origin
		var key := Vector2i(floori(o.x / CARD_TILE), floori(o.z / CARD_TILE))
		if not tiles.has(key):
			tiles[key] = []
		tiles[key].append(i)
	for key: Vector2i in tiles:
		var idx: Array = tiles[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = quad
		mm.instance_count = idx.size()
		for j in idx.size():
			mm.set_instance_transform(j, _cards[idx[j]])
			mm.set_instance_color(j, _card_cols[idx[j]])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# The cards turn to face the camera, past the quad's flat bounds.
		mmi.extra_cull_margin = 24.0
		mmi.name = "TreeCards_%d_%d" % [key.x, key.y]
		add_child(mmi)
	print("Backdrop: %d mainland trees, %d tree cards" % [_trees.size(), _cards.size()])


## Hides the modelled trees by the map's edge (the island editor's ground preview).
func show_near_trees(on: bool) -> void:
	for mmi in _near_trees:
		mmi.visible = on


static func _hash(x: float, z: float) -> float:
	var v := sin(x * 12.9898 + z * 78.233) * 43758.5453
	return v - floorf(v)
