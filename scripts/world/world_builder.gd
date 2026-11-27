class_name WorldBuilder
extends RefCounted
## Turns MapData + Terrain into renderable nodes: terrain, water, terminals, roads,
## towns, forests, rocks, marinas, the route overlay and all of their night lights.
## Pure presentation — no sim state.

## How far in from the map's edge on the mainland's shores the woods close up (edge_wood).
const EDGE_WOOD := 420.0
## On a shore with a mainland port the modelled woods give way to the Backdrop's
## flat tree cards (and its darker forest floor) across half this band, just past the
## map's edge, so the map itself is all modelled and neither style stops at a line.
const EDGE_MIX := 700.0
## The faceted shore rock meshes (_build_shore_rocks). Off for now: the painted
## cliff reads well on its own. TIDEWAYS_SHORE_ROCKS=1 turns them back on to tweak.
const SHORE_ROCKS := false
const ASPHALT := Color(0.26, 0.27, 0.29)
const CONCRETE := Color(0.62, 0.62, 0.6)
const ROAD := Color(0.3, 0.31, 0.33)
const LINE_WHITE := Color(0.9, 0.9, 0.86)
const LINE_YELLOW := Color(0.92, 0.78, 0.3)
const WALLS := [Color(0.93, 0.89, 0.8), Color(0.94, 0.94, 0.92), Color(0.62, 0.7, 0.78),
	Color(0.66, 0.74, 0.62), Color(0.66, 0.38, 0.3), Color(0.92, 0.82, 0.52)]
const ROOFS := [Color(0.72, 0.26, 0.2), Color(0.28, 0.3, 0.34), Color(0.25, 0.36, 0.52),
	Color(0.45, 0.3, 0.22), Color(0.2, 0.45, 0.42)]
# Alternatives: water_gem.gdshader, water_sharp.gdshader, water_fold.gdshader, water_reference.gdshader.
const WATER_SHADER := "res://shaders/water.gdshader"
const TERRAIN_SHADER := "res://shaders/terrain.gdshader"
const ROAD_SHADER := "res://shaders/road.gdshader"
## Towns this big get a double yellow line down the main road.
const DOUBLE_LINE_POP := 4000
# Cells per side of each terrain mesh, so the camera and shadows can cull them.
const TERRAIN_TILE := 50
# Scale of the caged lamps on the ramp lift towers.
const LIFT_LAMP := 4.8
# Scale of the 360° lanterns on top of the lift.
const LIFT_LANTERN := 3.9
# The modelled channel buoys (art/buoys.py) are life-size; the world is drawn a bit larger.
const BUOY_PORT_GLB := "res://assets/models/buoys/buoy_port_can.glb"
const BUOY_STARBOARD_GLB := "res://assets/models/buoys/buoy_starboard_nun.glb"
const BUOY_SCALE := 1.7
const SPAR_GLB := "res://assets/models/buoys/buoy_hazard_spar.glb"
const BELL_GLB := "res://assets/models/buoys/buoy_bell_tower.glb"
const MARKER_PORT_GLB := "res://assets/models/buoys/marker_channel_port.glb"
const MARKER_STARBOARD_GLB := "res://assets/models/buoys/marker_channel_starboard.glb"
const AMBER := Color(1.0, 0.65, 0.15)
# Side (m) of the tiles that trees, rocks and houses are batched in for culling.
const MULTIMESH_TILE := 192.0
# Eagle trees: within this of the water, the tallest one in each cell this size.
const EAGLE_SHORE := 45.0
const EAGLE_CELL := 27.0

const CITY_HALL := "city_hall"
## Shell size before awnings and decks. Pair each foundation with its authored model.
const SHOP_SHELLS := {
	"salt_and_rye": Vector2(8, 5.8),
	"sound_chandlery": Vector2(7, 6.6),
	"tideline_cafe": Vector2(8.4, 6),
	"harbor_inn": Vector2(11.6, 7),
	"glass_hall": Vector2(11.2, 7),
	"brick_mercantile": Vector2(9.8, 6.3),
	"sunset_terrace": Vector2(12, 6),
	"harbor_office": Vector2(10.5, 6),
	"seafoam_cafe": Vector2(9.1, 5.65),
	"tidetable_books": Vector2(6.4, 5.6),
	"post_office": Vector2(3.3, 5.4),
	"poppy_and_stem": Vector2(6.6, 5.8),
	"sound_fish_market": Vector2(6.2, 5.4),
	CITY_HALL: Vector2(11, 7),
}

const PIER_RESTAURANTS := ["sea_glass_grill", "red_net_kitchen"]

const TREE_CELL := 64.0
const LIFT_CELL := 2.0
# The most the ground may fall (m) across a building's plan; steeper lots are
# left empty rather than graded.
const KIT_MAX_DROP := 3.5
# A building's graded lot reaches this far past its plan, then eases back to the
# hillside over KIT_LOT_BLEND (m).
const KIT_LOT_MARGIN := 1.5
const KIT_LOT_BLEND := 6.0

var map: MapData
var terrain: Terrain
var rng := RandomNumberGenerator.new()
## Tree cards inside the map, on the mainland's shores (the Backdrop draws them).
var edge_cards: Array[Vector3] = []
## The terrain's material (its `facet` sets how faceted the ground looks).
var terrain_material: ShaderMaterial
var root: Node3D
## Where the bell buoys float (world, at the waterline), for Ambience to ring them.
var landmarks := LandmarkMeshes.new()
var bell_buoys: Array[Vector3] = []
var route_overlay: MeshInstance3D
var water_material: ShaderMaterial
var night_lights: MeshInstance3D
var glows := GlowBuilder.new()
## Cached town building meshes & names so runtime growth reuses exact variants.
var house_meshes: Array[Mesh] = []
var house_kit_names: Array[String] = []
var shop_meshes: Array[Mesh] = []
var shop_names_list: Array[String] = []
## Places seagulls can sit (where the feet go, in world space).
var gull_perches: Array[Seagulls.Perch] = []
## The shadow-only tree copies; the sandbox sets how far they reach by zoom.
var tree_shadows: Array[MultiMeshInstance3D] = []
## Every tree's foot, bucketed by TREE_CELL square, for how near the camera is to one.
var tree_cells := {}
## Eagles' lookouts: shoreline treetops, terminal dolphins, the tops of ramp lifts.
var eagle_perches: Array[Eagles.Perch] = []
## Per terrain grid vertex (row-major, terrain.n + 1 a side): the ground's colour
## in RGB and how much grass grows there in A (Grass reads it as a texture).
var ground_rgba := PackedByteArray()
## The tops of the shore rocks' grassy caps, for the grass blades (Grass.gd): one byte
## a LIFT_CELL square, 0 for none, else the cap's height as (h + 4) * 4.
var grass_lift := PackedByteArray()
var lift_side := 0

var _frames := BuildFrameBudget.new()
var _tie_up_piers := {}  # town id -> TieUpPier node
# Card picks by the edge, kept apart from `rng` so the rest of the woods don't reshuffle.
var _edge_rng := RandomNumberGenerator.new()
var _forest_noise := FastNoiseLite.new()
var _pasture_noise := FastNoiseLite.new()
## Terminals not open yet: town id -> [hidden node, its lights (MeshInstance3D)].
var _sites := {}
var _highest_tree_crown := -INF
var _blocked := {}


func _init(m: MapData, t: Terrain) -> void:
	map = m
	terrain = t
	rng.seed = m.map_seed * 31 + 7


## Construct engine resources on the main thread. With a frame signal the build
## yields between batches and returns null if the loading scene exits.
func build(frame: Signal = Signal()) -> Node3D:
	_frames.start(frame)
	root = Node3D.new()
	root.name = "World"
	# Towns grade their lots before terrain tiles read the heights.
	for part: Callable in [
		_build_water,
		_build_terminals,
		_build_marinas,
		_build_quays,
		_build_roads,
		_build_towns,
		_build_radio_towers,
		_build_terrain,
		_build_lighthouses,
		_build_nav_aids,
		_build_haul_outs,
		_build_vegetation,
		_build_shore_rocks,
		_build_route_overlay,
		_clear_grass_where_blocked
	]:
		if not await _frames.can_continue():
			break
		await part.call()
	_frames.finish()
	if _frames.cancelled:
		root.free()
		root = null
		return null
	night_lights = _add_mesh(glows.commit(), "NightLights", false)
	night_lights.visible = false
	# Hidden sites' lights hang under the night lights, so they follow the day.
	for id in _sites:
		var site_glows: GlowBuilder = _sites[id][1]
		var mi := MeshInstance3D.new()
		mi.name = map.towns[id].name + " Lights"
		mi.mesh = site_glows.commit() if not site_glows.is_empty() else null
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.visible = false
		night_lights.add_child(mi)
		_sites[id][1] = mi
	return root


## Shows the terminal built hidden at `town`'s dock site, now it has opened.
func show_terminal(town: MapData.Town) -> void:
	if not _sites.has(town.id):
		return
	for node: Node3D in _sites[town.id]:
		node.visible = true
	_sites.erase(town.id)


## Builds slip `i` of `town`'s terminal, bought in play (stage 5), into the world
## as it opens: its pier (or a tie-up's catwalk), lift, lights and buoys, and for a
## working slip beyond the lot, a forecourt for cars to reach it. Nothing else moves.
func build_bought_slip(town: MapData.Town, i: int) -> void:
	var saved := glows
	glows = GlowBuilder.new()
	var mb := MeshBuilder.new()
	mb.xform = town.terminal_xform()
	glows.xform = mb.xform
	var v := town.slip_offset(i)
	if town.slips[i].tie_up:
		if TieUpPier.available():
			_rebuild_tie_up_pier(town, mb)
		else:
			_build_tie_up(mb, town, i)
	else:
		_build_slip(mb, town, v)
		mb.xform = town.lot_xform()
		_forecourt(mb, town.lot_half_width, v)
	if not mb.is_empty():
		_add_mesh(mb.commit(), "%s Slip %d" % [town.name, i])
	if not glows.is_empty() and night_lights:
		var mi := MeshInstance3D.new()
		mi.name = "%s Slip %d Lights" % [town.name, i]
		mi.mesh = glows.commit()
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		night_lights.add_child(mi)
	glows = saved


func _rebuild_tie_up_pier(town: MapData.Town, mb: MeshBuilder) -> void:
	var old: TieUpPier = _tie_up_piers.get(town.id)
	var existing_rows: Array[float] = []
	if is_instance_valid(old):
		existing_rows = old.rows
		old.get_parent().remove_child(old)
		old.queue_free()
		_tie_up_piers.erase(town.id)
	var centres: Array[float] = []
	for i in town.tie_ups():
		centres.append(town.slip_offset(i))
	if centres.is_empty():
		return
	centres.sort()
	var pier := TieUpPier.new(centres, town)
	pier.name = town.name + " Tie-up Pier"
	root.add_child(pier)
	pier.transform = town.terminal_xform()
	_tie_up_piers[town.id] = pier
	# Purchased slips retain their centres. Existing rows keep their navigation
	# lantern and eagle lookout when a neighbouring berth extends this pier.
	for v in pier.rows:
		if existing_rows.has(v):
			continue
		var lookout := TieUpPier.SMALL_CAP + Vector3.RIGHT * v
		eagle_perches.append(Eagles.Perch.new(mb.xform * lookout, Eagles.Kind.DOLPHIN))
		var cap := TieUpPier.LARGE_CAP + Vector3.RIGHT * v
		var mark := Models.slip_mark(v in pier.port_rows)
		Models.add_cage_lantern(mb, cap, mark, Models.DOLPHIN_LANTERN)
		_add_dolphin_glow(glows, cap, mark)


## Paving along the front of the lot out to a slip at `v` beyond its edge (`hw`),
## where cars cross from the lanes to the pier and back.
func _forecourt(mb: MeshBuilder, hw: float, v: float) -> void:
	var reach := absf(v) + 7.5 - hw
	if reach <= 0.0:
		return
	var mid := signf(v) * (hw + reach * 0.5)
	var u0 := Layout.LANE_HEAD + 1.5
	var u1 := Layout.LOT_FRONT + 1.2
	mb.box(Vector3(mid, Layout.LOT_Y - 0.9, (u0 + u1) * 0.5), Vector3(reach + 0.6, 1.8, u1 - u0), ASPHALT)
	mb.box(Vector3(mid, Layout.LOT_Y - 1.35, (u0 + u1) * 0.5), Vector3(reach + 2.4, 2.4, u1 - u0 + 1.8), CONCRETE)


func cancel_build() -> void:
	_frames.cancel()


func _add_mesh(mesh: Mesh, node_name: String, shadows := true) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.name = node_name
	if not shadows:
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mi)
	return mi


## Instances are split into MULTIMESH_TILE-sized tiles, one MultiMesh each, so the
## camera and every shadow cascade can cull the ones out of view (a single MultiMesh
## covering the map is drawn whole, everywhere).
## Trees shared out among TreeModel.variants by where they stand, one set of tiles
## per variant.
func _forest(variants: Array, xforms: Array[Transform3D], colors: Array[Color], node_name: String) -> void:
	if _frames.cancelled:
		return
	var xs: Array = []
	var cs: Array = []
	for v in variants:
		xs.append([] as Array[Transform3D])
		cs.append([] as Array[Color])
	for i in xforms.size():
		var v := TreeModel.variant_at(xforms[i].origin, variants.size())
		xs[v].append(xforms[i])
		cs[v].append(colors[i])
	for v in variants.size():
		await _multimesh(variants[v][0], xs[v], cs[v], "%s%d" % [node_name, v], variants[v])


## Instances batched in tiles for culling. With a tree `variant` (TreeModel.variants),
## each tile draws its levels of detail at their distances (TreeLod.lod_levels).
func _multimesh(mesh: Mesh, xforms: Array[Transform3D], colors: Array[Color], node_name: String, variant: Array = []) -> void:
	if _frames.cancelled or xforms.is_empty():
		return
	var tiles := {}
	for i in xforms.size():
		var o := xforms[i].origin
		var key := Vector2i(floori(o.x / MULTIMESH_TILE), floori(o.z / MULTIMESH_TILE))
		if not tiles.has(key):
			tiles[key] = []
		tiles[key].append(i)
	var group := Node3D.new()
	group.name = node_name
	root.add_child(group)
	var levels: Array = (
		TreeLod.lod_levels(variant) if not variant.is_empty() else [[mesh, 0.0, 0.0]]
	)
	for key: Vector2i in tiles:
		if not await _frames.can_continue():
			return
		var idx: Array = tiles[key]
		# Each level gets its own MultiMesh, filled afresh: duplicate() copies the
		# instance buffer, which the headless renderer hands back empty.
		var make := func(m: Mesh) -> MultiMesh:
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_colors = not colors.is_empty()
			mm.mesh = m
			mm.instance_count = idx.size()
			fill_multimesh(mm, xforms, colors, idx)
			return mm
		var base := "%s_%d_%d" % [node_name, key.x, key.y]
		for l in levels.size():
			var lv: Array = levels[l]
			var mmi := MultiMeshInstance3D.new()
			mmi.multimesh = make.call(lv[0])
			TreeLod.dither_lod(
				mmi,
				lv[0],
				lv[1],
				lv[2],
				tile_slack(lv[0], idx, xforms),
				lv[3] if lv.size() > 3 else Vector3.ONE
			)
			mmi.name = base if l == 0 else "%s_lod%d" % [base, l]
			group.add_child(mmi)
			if not variant.is_empty() and (levels.size() > 1 or levels[0][0] != variant[0]):
				# Every level's shadow is cast by a shadow-only copy of the cheapest model:
				# nobody can tell them apart in a shadow, and they cost a fraction.
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if not variant.is_empty() and (levels.size() > 1 or levels[0][0] != variant[0]):
			var shade := MultiMeshInstance3D.new()
			shade.multimesh = make.call(TreeLod.shadow_mesh(variant))
			shade.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			# Far off, a tree's shadow is under a pixel but still costs a draw in every
			# cascade; the sandbox ends them where the shadow cascades end.
			shade.visibility_range_end = 1200.0
			shade.name = base + "_shadow"
			group.add_child(shade)
			tree_shadows.append(shade)



## How far from the middle of a tile's bounds (which its visibility range is measured
## from) any of its trees stands.
## Fills `mm` (instance_count already set) with xforms[idx[j]] (and colors[idx[j]]
## when it uses colours) in one buffer upload rather than a renderer call per
## instance: from the loading screen's worker thread each of those calls syncs
## with the renderer.
static func fill_multimesh(mm: MultiMesh, xforms: Array[Transform3D], colors: Array[Color], idx: Array) -> void:
	var stride := 16 if mm.use_colors else 12
	var buf := PackedFloat32Array()
	buf.resize(idx.size() * stride)
	for j in idx.size():
		var t: Transform3D = xforms[idx[j]]
		var o := j * stride
		buf[o] = t.basis.x.x; buf[o + 1] = t.basis.y.x; buf[o + 2] = t.basis.z.x; buf[o + 3] = t.origin.x
		buf[o + 4] = t.basis.x.y; buf[o + 5] = t.basis.y.y; buf[o + 6] = t.basis.z.y; buf[o + 7] = t.origin.y
		buf[o + 8] = t.basis.x.z; buf[o + 9] = t.basis.y.z; buf[o + 10] = t.basis.z.z; buf[o + 11] = t.origin.z
		if mm.use_colors:
			var c: Color = colors[idx[j]]
			buf[o + 12] = c.r; buf[o + 13] = c.g; buf[o + 14] = c.b; buf[o + 15] = c.a
	mm.buffer = buf


## Bounds are worked out here rather than asked of the MultiMesh: get_aabb() waits
## on the renderer, a frame at a time when called from a worker thread.
static func tile_slack(mesh: Mesh, idx: Array, xforms: Array[Transform3D]) -> float:
	var local := mesh.get_aabb()
	var box := xforms[idx[0]] * local
	for i: int in idx:
		box = box.merge(xforms[i] * local)
	var c := box.get_center()
	var r := 0.0
	for i: int in idx:
		r = maxf(r, xforms[i].origin.distance_to(c))
	return r

# --- Blocking grid so props don't overlap roads, lots and houses -------------------

func _block(p: Vector3, radius: float) -> void:
	var r := ceili(radius / 6.0)
	var cx := floori(p.x / 6.0)
	var cz := floori(p.z / 6.0)
	for dz in range(-r, r + 1):
		for dx in range(-r, r + 1):
			_blocked[Vector2i(cx + dx, cz + dz)] = true


## Mount slip glows on the fitted caps and move them when the slip is refitted.
func add_slip_guide_lights(guide: SlipGuides) -> void:
	guide.fitted.connect(_build_slip_guide_lights.bind(guide))
	if not guide.outer_caps.is_empty():
		_build_slip_guide_lights(guide)


func _build_slip_guide_lights(guide: SlipGuides) -> void:
	var glows := GlowBuilder.new()
	glows.xform = guide.slip_to_world
	for i in guide.outer_caps.size():
		_add_dolphin_glow(glows, guide.outer_caps[i], Models.slip_mark(i == 0))
	var lights := guide.get_node_or_null(^"Lights") as MeshInstance3D
	if not lights:
		lights = MeshInstance3D.new()
		lights.name = "Lights"
		lights.material_override = GlowBuilder.material()
		lights.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		lights.top_level = true  # GlowBuilder already positioned the vertices in world space.
		lights.layers = NightLights.LAYER
		guide.add_child(lights)
	lights.mesh = glows.commit()


func _add_dolphin_glow(glows: GlowBuilder, cap: Vector3, mark: Color) -> void:
	glows.glow(Models.cage_lantern_glow_at(cap, Models.DOLPHIN_LANTERN), mark, 0.42, 3.5, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)


## Fitted slip guides have room for three gulls across each deck. Only the inner
## dolphins have space for an eagle. The outer ones carry the slip lanterns.
func add_slip_perches(guide: SlipGuides) -> void:
	for cap in guide.inner_caps:
		_add_slip_gull_perches(guide.slip_to_world, cap)
		eagle_perches.append(Eagles.Perch.new(guide.slip_to_world * cap, Eagles.Kind.DOLPHIN))
	for cap in guide.outer_caps:
		_add_slip_gull_perches(guide.slip_to_world, cap)


func _add_slip_gull_perches(slip_to_world: Transform3D, cap: Vector3) -> void:
	for k in 3:
		var seat := slip_to_world * (cap + Vector3(0, 0, (k - 1) * 1.6))
		gull_perches.append(Seagulls.Perch.new(seat, seat, 0.0, Seagulls.Kind.DOLPHIN))


## A perch along a → b, `spread` either side of it (see Seagulls.Perch).
## None on a terminal not open yet (it's hidden).
func _perch(a: Vector3, b: Vector3, spread: float, kind: int) -> void:
	if root.visible:
		gull_perches.append(Seagulls.Perch.new(a, b, spread, kind))


func _is_blocked(x: float, z: float) -> bool:
	return _blocked.has(Vector2i(floori(x / 6.0), floori(z / 6.0)))


static func _hash(x: float, z: float) -> float:
	return fposmod(sin(x * 12.9898 + z * 78.233) * 43758.5453, 1.0)


# --- Terrain ------------------------------------------------------------------------

func _build_terrain() -> void:
	_setup_cover()
	var mat := ShaderMaterial.new()
	mat.shader = load(TERRAIN_SHADER)
	terrain_material = mat
	var n := terrain.n
	ground_rgba.resize((n + 1) * (n + 1) * 4)
	for tj in range(0, n, TERRAIN_TILE):
		for ti in range(0, n, TERRAIN_TILE):
			if not await _frames.can_continue():
				return
			_terrain_tile_node(ti / TERRAIN_TILE, tj / TERRAIN_TILE)

	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2.ONE * (Mainland.FAR * 2.0 + 3000.0)
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.4, 0.45, 0.36)
	floor_mesh.material = floor_mat
	var fl := _add_mesh(floor_mesh, "SeaFloor", false)
	fl.position.y = -16.05


## Builds the terrain tiles again over `rect` (grid vertex indices), after the
## editor re-stamps an island, and the water's seabed with them.
func rebuild_terrain(rect: Rect2i) -> void:
	var g := rect.grow(1)
	for tj in range(maxi(g.position.y, 0) / TERRAIN_TILE, mini(g.end.y, terrain.n - 1) / TERRAIN_TILE + 1):
		for ti in range(maxi(g.position.x, 0) / TERRAIN_TILE, mini(g.end.x, terrain.n - 1) / TERRAIN_TILE + 1):
			var old := root.get_node_or_null("Terrain_%d_%d" % [ti, tj])
			if old:
				root.remove_child(old)
				old.queue_free()
			_terrain_tile_node(ti, tj)
	(water_material.get_shader_parameter("seabed_height") as ImageTexture).update(_seabed_image())


func _terrain_tile_node(ti: int, tj: int) -> void:
	var n := terrain.n
	var i0 := ti * TERRAIN_TILE
	var j0 := tj * TERRAIN_TILE
	var mesh := _terrain_tile(i0, j0, mini(i0 + TERRAIN_TILE, n), mini(j0 + TERRAIN_TILE, n))
	if mesh:
		mesh.surface_set_material(0, terrain_material)
		_add_mesh(mesh, "Terrain_%d_%d" % [ti, tj])


func _seabed_image() -> Image:
	return Image.create_from_data(terrain.n + 1, terrain.n + 1, false, Image.FORMAT_RF, terrain.h_grid.to_byte_array())


## One tile of the terrain grid, cells [i0, i1) x [j0, j1): shared vertices with
## smooth normals and their own colours (the terrain shader adds the facets back),
## split on the same alternating diagonals as Terrain.height_at. Null if it's all
## deep water.
func _terrain_tile(i0: int, j0: int, i1: int, j1: int) -> ArrayMesh:
	var n := terrain.n
	var vn := n + 1
	var hs := terrain.half_size
	var c := Terrain.CELL
	var h := terrain.h_grid
	var w := i1 - i0 + 1
	var local := PackedInt32Array()
	local.resize(w * (j1 - j0 + 1))
	local.fill(-1)
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var idx := PackedInt32Array()
	for j in range(j0, j1):
		for i in range(i0, i1):
			var k := j * vn + i
			if maxf(maxf(h[k], h[k + 1]), maxf(h[k + vn], h[k + vn + 1])) < -15.6:
				continue
			var q := PackedInt32Array([0, 0, 0, 0])  # 00, 10, 01, 11
			for corner in 4:
				var ci := i + (corner & 1)
				var cj := j + (corner >> 1)
				var li := (cj - j0) * w + (ci - i0)
				if local[li] < 0:
					local[li] = verts.size()
					var y := h[cj * vn + ci]
					var x := -hs + ci * c
					var z := -hs + cj * c
					verts.append(Vector3(x, y, z))
					var nrm := Vector3(h[cj * vn + maxi(ci - 1, 0)] - h[cj * vn + mini(ci + 1, n)], 2.0 * c,
						h[maxi(cj - 1, 0) * vn + ci] - h[mini(cj + 1, n) * vn + ci]).normalized()
					normals.append(nrm)
					var col := ground_color(y, nrm.y, x, z)
					colors.append(col)
					_record_ground(cj * vn + ci, col, y, nrm.y, x, z)
				q[corner] = local[li]
			if (i + j) % 2 == 0:
				idx.append_array([q[0], q[1], q[3], q[0], q[3], q[2]])
			else:
				idx.append_array([q[0], q[1], q[2], q[1], q[3], q[2]])
	if idx.is_empty():
		return null
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = normals
	arr[Mesh.ARRAY_COLOR] = colors
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var sarr := []
	sarr.resize(Mesh.ARRAY_MAX)
	sarr[Mesh.ARRAY_VERTEX] = verts
	sarr[Mesh.ARRAY_INDEX] = idx
	var shadow := ArrayMesh.new()
	shadow.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, sarr)
	mesh.shadow_mesh = shadow
	return mesh


func _record_ground(k: int, col: Color, h: float, ny: float, x: float, z: float) -> void:
	var o := k * 4
	ground_rgba[o] = col.r8
	ground_rgba[o + 1] = col.g8
	ground_rgba[o + 2] = col.b8
	# Grass on gentle ground above the beach, thinning into the edge's woods.
	var g := smoothstep(3.9, 5.2, h) * smoothstep(0.72, 0.8, ny) * (1.0 - edge_wood(x, z))
	ground_rgba[o + 3] = roundi(g * 255.0)


## No grass through roads, lots, houses, quays and the like.
func _clear_grass_where_blocked() -> void:
	var vn := terrain.n + 1
	var hs := terrain.half_size
	var c := Terrain.CELL
	for key: Vector2i in _blocked:
		var i0 := maxi(floori((key.x * 6.0 - 1.5 + hs) / c), 0)
		var i1 := mini(ceili(((key.x + 1) * 6.0 + 1.5 + hs) / c), vn - 1)
		var j0 := maxi(floori((key.y * 6.0 - 1.5 + hs) / c), 0)
		var j1 := mini(ceili(((key.y + 1) * 6.0 + 1.5 + hs) / c), vn - 1)
		for j in range(j0, j1 + 1):
			for i in range(i0, i1 + 1):
				ground_rgba[(j * vn + i) * 4 + 3] = 0


func ground_image() -> Image:
	var vn := terrain.n + 1
	return Image.create_from_data(vn, vn, false, Image.FORMAT_RGBA8, ground_rgba)


## The islands' ground colour (the Backdrop blends the mainland's edge into it too).
func ground_color(h: float, ny: float, x: float, z: float) -> Color:
	var r := _hash(x, z)
	var col: Color
	if h < -0.9:
		col = Color(0.66, 0.63, 0.47).darkened(clampf(-h * 0.023333, 0.0, 0.45))
	elif ny < 0.72:
		col = Color(0.5, 0.43, 0.42).lerp(Color(0.63, 0.54, 0.49), r)
	elif h < 3.45:
		col = Color(0.8, 0.73, 0.54)
	else:
		var g := clampf((h - 3.6) / 60.0, 0.0, 1.0)
		col = Color(0.52, 0.6, 0.25).lerp(Color(0.33, 0.46, 0.2), g)
		# Open fields read lighter and warmer than the woods' floor.
		var f := field_at(x, z)
		if f > 0.0:
			col = col.lerp(Color(0.68, 0.7, 0.36), f * 0.55 * (1.0 - g * 0.6))
		# Into the mainland's forest floor where its woods close up at the map's edge.
		var w := edge_wood(x, z)
		if w > 0.0:
			col = col.lerp(Backdrop.FOREST.lerp(Backdrop.FOREST_LIGHT, r), w)
	return col.darkened(r * 0.08)


# --- Cover: forest and fields ------------------------------------------------------

func _setup_cover() -> void:
	_forest_noise.seed = map.map_seed + 5
	_edge_rng.seed = map.map_seed + 7
	_forest_noise.frequency = 0.0033333
	_pasture_noise.seed = map.map_seed + 6
	_pasture_noise.frequency = 0.0014
	_pasture_noise.fractal_octaves = 3


## How open the ground is at x, z: 0 under woods, 1 in the middle of a field. The
## island's `fields` sets how much of it is open (0.4: the old default).
func field_at(x: float, z: float) -> float:
	var id := terrain.island_at(x, z)
	var amount := map.islands[id].fields if id >= 0 else 0.4
	var t := lerpf(0.6, -0.5, amount)
	return smoothstep(t, t + 0.12, _pasture_noise.get_noise_2d(x, z)) * (1.0 - edge_wood(x, z))


## 1 where the ground runs into the mainland's unbroken forest at the map's edge
## (on the channel's shores), easing to 0 a few hundred metres in: no fields or
## clearings there, so the woods carry on past the edge without a seam.
func edge_wood(x: float, z: float) -> float:
	var v := absf(x) if terrain.mainland.axis == 1 else absf(z)
	return smoothstep(terrain.half_size - EDGE_WOOD, terrain.half_size - 40.0, v)


## The mainland's side of the channel that x, z lies on has no port: nothing there
## is played on, so it is all Backdrop (Mainland.port_side).
func backdrop_side(x: float, z: float) -> bool:
	return not terrain.mainland.has_port(x, z)


## Share of the woods at x, z drawn as the Backdrop's flat cards rather than
## modelled trees: 1 on a side with no port, and on a port's side easing from 0
## 0 at the map's edge to 1 EDGE_MIX / 2 outside it.
func card_share(x: float, z: float) -> float:
	var v := absf(x) if terrain.mainland.axis == 1 else absf(z)
	if backdrop_side(x, z):
		return 1.0 if v > terrain.half_size else 0.0
	return smoothstep(0.0, EDGE_MIX * 0.5, v - terrain.half_size)


## Chance of a tree on each 8.1 m step of gentle ground at x, z (height h), before
## towns thin it: the woods' patches, the island's `forest`, its open fields, and
## taller, thinner stands up on the hills. Past the map the Backdrop starts from it.
func tree_density(x: float, z: float, h: float) -> float:
	var density := (0.85 + _forest_noise.get_noise_2d(x, z) * 1.2) * forest_at(x, z)
	density *= 1.0 - field_at(x, z)
	density *= 1.0 - smoothstep(12.0, 36.0, h) * 0.45
	return lerpf(density, 0.7, edge_wood(x, z))


## The island's woods density multiplier at x, z.
func forest_at(x: float, z: float) -> float:
	var id := terrain.island_at(x, z)
	return map.islands[id].forest if id >= 0 else 1.0


# --- Water --------------------------------------------------------------------------

func _build_water() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = load(WATER_SHADER)
	# Float heights retain negative seabed elevations. The shader interpolates the
	# same triangles as Terrain, so shallow colours stay attached to the shore.
	mat.set_shader_parameter("seabed_height", ImageTexture.create_from_image(_seabed_image()))
	mat.set_shader_parameter("terrain_half_size", terrain.half_size)
	mat.set_shader_parameter("terrain_cell", Terrain.CELL)
	var inner := map.half_size + 300.0
	mat.set_shader_parameter("swell_extent", inner)
	water_material = mat
	var plane := PlaneMesh.new()
	plane.size = Vector2(inner * 2.0, inner * 2.0)
	plane.subdivide_width = 300
	plane.subdivide_depth = 300
	var water := _add_mesh(plane, "Water", false)
	water.material_override = mat

	# Flat ring out to the horizon around the detailed plane.
	var o := Mainland.FAR + 900.0
	var w := inner
	var mb := MeshBuilder.new()
	var col := Color.WHITE
	mb.quad(Vector3(-o, 0, -o), Vector3(o, 0, -o), Vector3(o, 0, -w), Vector3(-o, 0, -w), col, Vector3.UP)
	mb.quad(Vector3(-o, 0, w), Vector3(o, 0, w), Vector3(o, 0, o), Vector3(-o, 0, o), col, Vector3.UP)
	mb.quad(Vector3(-o, 0, -w), Vector3(-w, 0, -w), Vector3(-w, 0, w), Vector3(-o, 0, w), col, Vector3.UP)
	mb.quad(Vector3(w, 0, -w), Vector3(o, 0, -w), Vector3(o, 0, w), Vector3(w, 0, w), col, Vector3.UP)
	var ring := _add_mesh(mb.commit(), "WaterRing", false)
	ring.material_override = mat


# --- Terminals ----------------------------------------------------------------------

## Every dock site's terminal is built with the map (TID-319). One the company
## doesn't own yet is built into its own hidden node, its lights hidden under
## the night lights, so buying it only has to show them (show_terminal).
func _build_terminals() -> void:
	var main_root := root
	var main_glows := glows
	for isl in map.towns:
		if not await _frames.can_continue():
			return
		if not isl.has_dock:
			continue
		var site: Node3D = null
		if not isl.built:
			site = Node3D.new()
			site.name = isl.name + " Terminal (site)"
			site.visible = false
			main_root.add_child(site)
			root = site
			glows = GlowBuilder.new()
		_terminal_for(isl)
		if site:
			_sites[isl.id] = [site, glows]
		root = main_root
		glows = main_glows


func _terminal_for(isl: MapData.Town) -> void:
	var mb := MeshBuilder.new()
	# The lot and everything on it in the lot's frame (raised and set back behind
	# the trestle); the slips in the terminal's.
	mb.xform = isl.lot_xform()
	glows.xform = mb.xform
	var hw := isl.lot_half_width
	var ly := Layout.LOT_Y
	var mid_u := (Layout.LOT_FRONT + Layout.LOT_BACK) * 0.5
	_build_lot_foundation(mb, hw)
	var open := Layout.open_lanes(hw, isl.open_lanes)
	if isl.open_lanes > 0:
		# Only the lanes in use are paved; the rest of the site is graded gravel.
		mb.box(Vector3(0, ly - 0.95, mid_u), Vector3(hw * 2.0, 1.8, Layout.LOT_LENGTH), PavingCrew.GRAVEL.darkened(0.1))
		var lo := minf(open.front() - Layout.LANE_WIDTH * 0.5, -Layout.EXIT_CLEAR + Layout.LANE_WIDTH * 0.5)
		var hi := maxf(open.back() + Layout.LANE_WIDTH * 0.5, Layout.EXIT_CLEAR - Layout.LANE_WIDTH * 0.5)
		mb.box(Vector3((lo + hi) * 0.5, ly - 0.9, mid_u), Vector3(hi - lo, 1.8, Layout.LOT_LENGTH), ASPHALT)
	else:
		mb.box(Vector3(0, ly - 0.9, mid_u), Vector3(hw * 2.0, 1.8, Layout.LOT_LENGTH), ASPHALT)

	# Lane markings
	var mark_len := Layout.LANE_HEAD - (Layout.LOT_BACK + 7.5) + 3.0
	var mark_u := (Layout.LANE_HEAD + 3.0 + Layout.LOT_BACK + 7.5) * 0.5
	var marked: Array[float] = open
	if isl.open_lanes == 0:
		marked = []
		for lane_set in Layout.lane_positions(hw, maxi(isl.route_ids().size(), 1)):
			for v in lane_set:
				marked.append(v)
	for v in marked:
		for side: float in [-3.6, 3.6]:
			mb.box(Vector3(v + side, ly + 0.03, mark_u), Vector3(0.36, 0.06, mark_len), LINE_WHITE)
	var u := Layout.LOT_BACK + 4.5
	while u < Layout.LOT_FRONT - 3.0:
		mb.box(Vector3(0, ly + 0.03, u), Vector3(0.42, 0.06, 3.6), LINE_YELLOW)
		u += 7.2

	if SlipModel.authored_trestle:
		_lot_edge(mb, isl)
	mb.xform = isl.terminal_xform()
	glows.xform = mb.xform
	var timber_pier := not isl.tie_ups().is_empty() and TieUpPier.available()
	for i in isl.slips.size():
		if not isl.slips[i].tie_up:
			_build_slip(mb, isl, isl.slip_offset(i))
		elif not timber_pier:
			_build_tie_up(mb, isl, i)
	if timber_pier:
		_rebuild_tie_up_pier(isl, mb)
	mb.xform = isl.lot_xform()
	glows.xform = mb.xform

	# The entry porch faces the holding lanes. The gulls sit along the hall ridge.
	var bv := hw + 15.0
	var hall := _terminal_model(preload("res://assets/models/ferry_passenger_terminal.glb"),
		mb.xform.translated_local(Vector3(bv, ly, -36)))
	_perch(hall.transform * Vector3(1, 10.59, -8.0),
		hall.transform * Vector3(1, 10.59, 14.5), 0.0, Seagulls.Kind.ROOF)
	glows.pool(Vector3(bv - 11, ly + 0.15, -34), GlowBuilder.WARM, 13.5, 0.3)

	var tu := Layout.TICKET_U
	var plaza_y := ly
	if isl.road_main_a.size() >= 2:
		var near := mb.xform.affine_inverse() * isl.road_main_a[0]
		for i in range(1, isl.road_main_a.size()):
			var far := mb.xform.affine_inverse() * isl.road_main_a[i]
			if far.z <= tu:
				plaza_y = remap(tu, near.z, far.z, near.y, far.y)
				break
			near = far
	_terminal_model(preload("res://assets/models/ferry_ticket_plaza.glb"),
		mb.xform.translated_local(Vector3(0, plaza_y, tu)))
	for v: float in Layout.TICKET_LANES:
		mb.box(Vector3(v, plaza_y + 6.12, tu), Vector3(1.6, 0.12, 1.2), Models.lamp_glass(GlowBuilder.LED))
		glows.glow(Vector3(v, plaza_y + 6.0, tu), GlowBuilder.LED, 0.48, 4.0, false, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	glows.pool(Vector3(-6, plaza_y + 0.15, tu), GlowBuilder.SODIUM, 16.5, 0.3)

	# Light poles
	for v: float in [-hw + 1.2, hw - 1.2]:
		for pu: float in [Layout.LOT_FRONT - 3.0, Layout.LOT_BACK + 3.0]:
			mb.box(Vector3(v, ly + 7.5, pu), Vector3(0.54, 15.0, 0.54), Color(0.35, 0.36, 0.38))
			mb.box(Vector3(v, ly + 15.0, pu), Vector3(1.8, 0.54, 1.8), Color(0.95, 0.95, 0.8))
			mb.box(Vector3(v, ly + 14.61, pu), Vector3(1.44, 0.24, 1.44), Models.lamp_glass(GlowBuilder.SODIUM))
			glows.glow(Vector3(v, ly + 14.55, pu), GlowBuilder.SODIUM, 0.9, 6.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
			glows.pool(Vector3(v * 0.7, ly + 0.15, pu), GlowBuilder.SODIUM, 24.0, 0.22)
			var top := mb.xform * Vector3(v, ly + 15.27, pu)
			_perch(top, top, 0.0, Seagulls.Kind.LAMP)

	_add_mesh(mb.commit(), isl.name + " Terminal")

	# Keep trees and houses off the lot, piers and building, and off the shore either
	# side where more slips may be bought (Terminal.new_slip_v).
	var t := isl.lateral()
	var spare := (Terminal.MAX_WORKING_SLIPS + Terminal.MAX_TIE_UPS - 1) * Layout.SLIP_SPACING + 12.0
	var bu := Layout.LOT_BACK - isl.lot_shift() - 18.0
	while bu < Layout.PIER_END:
		var bvv := -hw - 9.0
		var far := hw + 36.0
		if bu > Layout.LANE_HEAD:
			bvv = minf(bvv, -spare)
			far = maxf(far, spare)
		while bvv < far:
			_block(isl.shore + isl.dock_dir * bu + t * bvv, 3.0)
			bvv += 4.5
		bu += 4.5


func _terminal_model(scene: PackedScene, pose: Transform3D) -> Node3D:
	var model: Node3D = scene.instantiate()
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		for surface in part.mesh.get_surface_count():
			var material := part.mesh.surface_get_material(surface)
			if material.resource_name.ends_with("glazing"):
				part.set_surface_override_material(surface, Models.vc_material())
	root.add_child(model)
	model.transform = pose
	return model


func _build_slip(mb: MeshBuilder, isl: MapData.Town, v: float) -> void:
	var ly := Layout.LOT_Y
	var pe := Layout.PIER_END
	# With the mid-poly slip a trestle runs out from the lot to the transfer span's hinge
	# (the span, apron and counterweights are SlipRampView's, the towers are scenery here).
	var mid := SlipModel.authored_span
	var deck_end := Layout.RAMP_HINGE_U if mid else pe
	if SlipModel.authored_trestle:
		_build_trestle(mb, isl, v)
	else:
		_build_plain_trestle(mb, isl, v, deck_end, mid)
	# Tower lateral offset (the eagles sit over it) and how far the header's top runs.
	var tower_x := 8.7
	var beam_x := 8.7
	if mid:
		if not SlipModel.authored_trestle:
			# The hinge bent: a concrete cap on piles carrying the span's hinge pin.
			mb.box(Vector3(v, ly - 1.9, deck_end), Vector3(15.6, 1.4, 1.5), CONCRETE)
			for side: float in [-6.0, -2.0, 2.0, 6.0]:
				mb.box(
					Vector3(v + side, -4.5, deck_end),
					Vector3(1.0, 9.0, 1.0),
					CONCRETE.darkened(0.2)
				)
		Models._append_part(
			mb,
			SlipModel.span_part("towers"),
			mb.xform * Transform3D(Basis.IDENTITY, Vector3(v, 0, 0))
		)
		tower_x = SlipRampView.TOWER_X
		beam_x = 8.0
	else:
		mb.box(Vector3(v, ly - 0.36, pe - 4.5), Vector3(15.6, 1.08, 9.0), Color(0.4, 0.42, 0.45))
		for side: float in [-8.7, 8.7]:
			mb.box(Vector3(v + side, 8.4, pe - 3.0), Vector3(1.5, 16.8, 1.5), Models.WSF_GREEN)
		mb.box(Vector3(v, 16.2, pe - 3.0), Vector3(18.9, 1.5, 1.5), Models.WSF_GREEN)
	# Steady red 360° light on top of the lift, for ferries lining up at night.
	var top := Vector3(v, 16.95, pe - 3.0)
	Models.add_cage_lantern(mb, top, GlowBuilder.RED, LIFT_LANTERN)
	glows.glow(Models.cage_lantern_glow_at(top, LIFT_LANTERN), GlowBuilder.RED, 0.6, 7.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	# Along the lift's cross beam, either side of the lantern.
	for side: float in [-1.0, 1.0]:
		_perch(mb.xform * Vector3(v + side * 1.35, 16.95, pe - 3.0), mb.xform * Vector3(v + side * beam_x, 16.95, pe - 3.0),
			0.0, Seagulls.Kind.LIFT)
		# An eagle on top of each tower.
		eagle_perches.append(Eagles.Perch.new(mb.xform * Vector3(v + side * tower_x, 16.95, pe - 3.0), Eagles.Kind.LIFT))
	for side: float in [-1.0, 1.0]:
		var mark := Models.slip_mark(side < 0)
		# The modelled wing walls and dolphins are the slip's own live part (SlipGuides).
		if not SlipModel.authored_guides:
			var ww: Array = Layout.WING_WALL
			for k in ww.size() - 1:
				var w0: Vector2 = ww[k]
				var w1: Vector2 = ww[k + 1]
				_wing_wall(mb, Vector2(w0.x, v + side * w0.y), Vector2(w1.x, v + side * w1.y), side)
			var inner := Layout.DOLPHIN_INNER
			var inner_cap := _dolphin(mb, Vector3(v + side * inner.y, 0, inner.x), inner.z, 6)
			# (The outer ones' lanterns leave no room for an eagle.)
			eagle_perches.append(Eagles.Perch.new(mb.xform * inner_cap, Eagles.Kind.DOLPHIN))
			# The outer dolphins carry the slip's lanterns.
			var outer := Layout.DOLPHIN_OUTER
			var cap := _dolphin(mb, Vector3(v + side * outer.y, 0, outer.x), outer.z, 8)
			Models.add_cage_lantern(mb, cap, mark, Models.DOLPHIN_LANTERN)
			_add_dolphin_glow(glows, cap, mark)
		# Channel buoy, flashing.
		var buoy := Vector3(v + side * 25.5, 0.0, Layout.CHANNEL_BUOY_U)
		var phase := Models.blink_phase_at(mb.xform * buoy)
		var glow_at := _buoy_model(
			mb.xform, buoy, side < 0, "%s Buoy %d %s" % [isl.name, int(v), "G" if side < 0 else "R"]
		)
		if glow_at == Vector3.INF:
			Models.add_buoy(
				mb, buoy, Color(0.2, 0.55, 0.3) if side < 0 else Color(0.8, 0.2, 0.15), mark, phase
			)
			glow_at = Models.buoy_glow_at(buoy)
		glows.glow(
			glow_at, mark, 0.66, 7.0, true, Models.blink_of(phase), Vector3.ZERO, Models.LAMP_ON_AT
		)
		# A caged lamp on the inside of each lift tower, lighting the ramp.
		var lamp := Vector3(v + side * 7.95, 13.8, pe - 3.0)
		var out := Vector3(-side, 0, 0)
		Models.add_bulkhead_lamp(mb, lamp, out, GlowBuilder.WARM, LIFT_LAMP)
		glows.glow(Models.bulkhead_glow_at(lamp, out, LIFT_LAMP), GlowBuilder.WARM,
			Models.bulkhead_glow_size(LIFT_LAMP), 5.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	glows.pool(Vector3(v, ly + 0.15, pe - 9.0), GlowBuilder.SODIUM, 10.5, 0.3)


## Places the modelled can (port, green) or nun (starboard, red) buoy at `base` in
## the frame `xf`, and returns where its lantern's glow goes in that frame, or
## Vector3.INF if the model isn't there (the caller draws the plain one).
func _buoy_model(xf: Transform3D, base: Vector3, port: bool, node_name: String) -> Vector3:
	return _nav_aid(BUOY_PORT_GLB if port else BUOY_STARBOARD_GLB, xf, base, 0.0, node_name)


## Instances the nav-aid model at `path` at `base` (turned by `yaw`) in the frame
## `xf`; returns its lantern's glow point in that frame, or Vector3.INF if missing.
func _nav_aid(
	path: String, xf: Transform3D, base: Vector3, yaw: float, node_name: String
) -> Vector3:
	if root == null or not ResourceLoader.exists(path):
		return Vector3.INF
	var aid := (load(path) as PackedScene).instantiate() as Node3D
	aid.name = node_name
	root.add_child(aid)
	var b := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * BUOY_SCALE)
	aid.transform = xf * Transform3D(b, base)
	var beacon := aid.find_child("BeaconLight", true, false) as Node3D
	var lamp := beacon.position if beacon else Vector3(0, 2.9, 0)
	return base + b * (lamp + Vector3(0, 0.35, 0))


## Open-water marks: a hazard spar off the shoal edge of most islands, a bell
## buoy out in deep water off each inhabited one, and a pair of channel markers
## further out on each terminal's approach. All flash at night.
func _build_nav_aids() -> void:
	glows.xform = Transform3D.IDENTITY
	var n := 0
	for isl in map.islands:
		if isl.is_mainland:
			continue
		var c := Vector3(isl.center.x, 0, isl.center.y)
		# Spar on the shoal's edge, bell further out in deep water.
		for kind in ["spar", "bell"]:
			if kind == "bell" and not isl.inhabited:
				continue
			if kind == "spar" and rng.randf() > 0.7:
				continue
			var depth := -2.5 if kind == "spar" else -14.0
			for _try in 6:
				var ang := rng.randf() * TAU
				var dir := Vector3(cos(ang), 0, sin(ang))
				var r := 0.0
				while r < isl.radius * 3.0 and terrain.height_v(c + dir * r) > depth:
					r += 2.0
				var p := c + dir * (r + (6.0 if kind == "spar" else 40.0))
				if terrain.height_v(p) > depth or _is_blocked(p.x, p.z):
					continue
				var path := SPAR_GLB if kind == "spar" else BELL_GLB
				var col := AMBER if kind == "spar" else GlowBuilder.LED
				var at := _nav_aid(
					path, Transform3D.IDENTITY, p, rng.randf() * TAU, "Nav %s %d" % [kind, n]
				)
				if at != Vector3.INF:
					if kind == "bell":
						bell_buoys.append(p)
					var phase := Models.blink_phase_at(p)
					glows.glow(
						at,
						col,
						0.6,
						7.0,
						true,
						Models.blink_of(phase),
						Vector3.ZERO,
						Models.LAMP_ON_AT
					)
					_block(p, 12.0)
					n += 1
				break
	# Channel markers out on each terminal's approach, wider than the slip buoys.
	for town in map.towns:
		if town.slips.is_empty():
			continue
		var xf := town.terminal_xform()
		for side: float in [-1.0, 1.0]:
			var base := Vector3(side * 48.0, 0.0, Layout.CHANNEL_BUOY_U + 70.0)
			var w := xf * base
			if terrain.height_v(w) > -1.5 or _is_blocked(w.x, w.z):
				continue
			var path := MARKER_PORT_GLB if side < 0 else MARKER_STARBOARD_GLB
			var at := _nav_aid(
				path, xf, base, 0.0, "%s Channel Marker %s" % [town.name, "G" if side < 0 else "R"]
			)
			if at != Vector3.INF:
				var phase := Models.blink_phase_at(w)
				glows.glow(
					xf * at,
					GlowBuilder.GREEN if side < 0 else GlowBuilder.RED,
					0.6,
					7.0,
					true,
					Models.blink_of(phase),
					Vector3.ZERO,
					Models.LAMP_ON_AT
				)
				_block(w, 10.0)


## The concrete rim meets the gravel 10 cm above the graded ground. Leave its
## center open: the gravel and asphalt already supply the surface there.
static func _build_lot_foundation(mb: MeshBuilder, half_width: float) -> void:
	var center := Vector3(0, Layout.LOT_Y - 0.05, (Layout.LOT_FRONT + Layout.LOT_BACK) * 0.5)
	var inner := PackedVector3Array()
	var outer := PackedVector3Array()
	for corner in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(1, 0, 1), Vector3(-1, 0, 1)]:
		var offset: Vector3 = corner * Vector3(half_width, 0, Layout.LOT_LENGTH * 0.5)
		inner.append(center + offset)
		outer.append(center + offset + corner * 1.8)
	var down := Vector3.DOWN * 2.5
	for i in 4:
		var j := (i + 1) % 4
		mb.quad(inner[i], inner[j], outer[j], outer[i], CONCRETE, Vector3.UP)
		var outward := (outer[i] + outer[j]) * 0.5 - center
		mb.quad(outer[i], outer[j], outer[j] + down, outer[i] + down, CONCRETE, outward)


## When the authored deck is unavailable, the concrete deck still follows the
## same profile as the vehicles, including the join to the raised lot.
static func _build_plain_trestle(mb: MeshBuilder, isl: MapData.Town, v: float, end: float, mid: bool) -> void:
	var front := isl.lot_front_u()
	var deck := MeshBuilder.new()
	var u := front
	while u < end:
		var next := minf(u + 4.0, end)
		var center := (u + next) * 0.5
		deck.box(Vector3(0, -0.6, center), Vector3(15.0, 1.2, next - u), CONCRETE)
		deck.box(Vector3(0, 0.03, center), Vector3(0.36, 0.06, next - u), LINE_YELLOW)
		u = next
	SlipModel.append_on_profile(mb, deck, mb.xform, v, 0.0, isl.road_y)
	u = front + 3.0
	while u < end:
		for side: float in [-6.6, 6.6]:
			var top := isl.road_y(u) - 1.2
			mb.box(Vector3(v + side, (top - 10.5) * 0.5, u), Vector3(1.2, top + 10.5, 1.2), Models.WOOD)
		u += 9.0 if not mid else 4.5


## The trestle from the lot's edge out to slip `v`'s span hinge (SlipModel.trestle_part):
## the abutment at the lot, deck bays lifted onto the road's profile (Island.road_y),
## the landing onto the hinge last, pile bents under the joints and light poles on the
## barrier every other bay. Terminal frame.
func _build_trestle(mb: MeshBuilder, isl: MapData.Town, v: float) -> void:
	var n := isl.approach_bays
	var u0 := isl.lot_front_u()
	var road := isl.road_y
	Models._append_part(
		mb,
		SlipModel.trestle_part("abutment"),
		mb.xform * Transform3D(Basis.IDENTITY, Vector3(v, isl.lot_y, u0))
	)
	var lamp := SlipModel.trestle_part("lamp")
	for i in n:
		var u := u0 + i * Layout.TRESTLE_BAY
		var part := SlipModel.trestle_part("landing" if i == n - 1 else "bay")
		SlipModel.append_on_profile(mb, part, mb.xform, v, u, road)
		if i > 0:
			Models._append_part(
				mb,
				SlipModel.trestle_part("bent"),
				(
					mb.xform
					* Transform3D(
						Basis.IDENTITY, Vector3(v, isl.road_y(u) - Layout.TRESTLE_SLAB, u)
					)
				)
			)
		if i % 2 == 1 or n == 1:
			var lu := u + Layout.TRESTLE_BAY * 0.5
			var foot := Vector3(v + Layout.TRESTLE_LAMP_V, isl.road_y(lu) + Layout.TRESTLE_LAMP_Y, lu)
			Models._append_part(mb, lamp, mb.xform * Transform3D(Basis.IDENTITY, foot))
			var head := foot + Vector3(-3.75, 9.8, 0.0)
			glows.glow(head, GlowBuilder.SODIUM, 0.6, 5.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
			glows.pool(Vector3(head.x, isl.road_y(lu) + 0.15, lu), GlowBuilder.SODIUM, 12.0, 0.22)
			_perch(mb.xform * (head + Vector3(0, 0.4, 0)), mb.xform * (head + Vector3(0, 0.4, 0)), 0.0, Seagulls.Kind.LAMP)


## Along the lot's seaward edge, where it stands over the bank: a low concrete wall
## with a pipe rail, open where each trestle (or tie-up catwalk) leaves. Lot frame.
func _lot_edge(mb: MeshBuilder, isl: MapData.Town) -> void:
	var hw := isl.lot_half_width
	var ly := Layout.LOT_Y
	var u := Layout.LOT_FRONT + 0.3
	var gaps: Array[Vector2] = []
	for i in isl.slips.size():
		var sv := isl.slip_offset(i)
		if isl.slips[i].tie_up:
			gaps.append(Vector2(sv - 1.5, sv + 1.5))
		else:
			gaps.append(Vector2(sv + Layout.TRESTLE_V_WALK, sv + Layout.TRESTLE_V_OUT))
	gaps.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
	var runs: Array[Vector2] = []
	var from := -hw - 1.8
	for g in gaps:
		if g.x > from:
			runs.append(Vector2(from, minf(g.x, hw + 1.8)))
		from = maxf(from, g.y)
	if from < hw + 1.8:
		runs.append(Vector2(from, hw + 1.8))
	for r in runs:
		if r.y - r.x < 0.5:
			continue
		var mid := (r.x + r.y) * 0.5
		var w := r.y - r.x
		mb.box(Vector3(mid, ly - 0.6, u), Vector3(w, 2.1, 0.6), CONCRETE)
		mb.box(Vector3(mid, ly + 1.1, u), Vector3(w, 0.08, 0.08), Color(0.68, 0.69, 0.68))
		mb.box(Vector3(mid, ly + 0.75, u), Vector3(w, 0.06, 0.06), Color(0.68, 0.69, 0.68))
		var x := r.x + 0.2
		while x <= r.y:
			mb.box(Vector3(x, ly + 0.75, u), Vector3(0.08, 0.7, 0.08), Color(0.68, 0.69, 0.68))
			x += 2.0


## A tie-up slip: a catwalk out from the shore for the crew, and a pair of dolphins
## either side to lie against, but no transfer span (it loads no cars). Tie-ups lie
## side by side (Layout.TIE_UP_SPACING, as at Eagle Harbor), so neighbours share the
## dolphins between them: tie-up `i` leaves out a side an earlier one has built.
func _build_tie_up(mb: MeshBuilder, isl: MapData.Town, i: int) -> void:
	var v := isl.slip_offset(i)
	var ly := Layout.LOT_Y
	var pe := Layout.PIER_END
	var lf := isl.lot_front_u()
	# The catwalk follows the road's profile down from the lot, then runs level.
	var cu := lf
	while cu < pe - 0.01:
		var cu1 := minf(cu + 6.0, pe)
		var y0 := isl.road_y(cu)
		var y1 := isl.road_y(cu1)
		var a := Vector3(v, (y0 + y1) * 0.5 - 0.3, (cu + cu1) * 0.5)
		var saved := mb.xform
		mb.xform = saved * Transform3D(Basis(Vector3.RIGHT, atan2(y0 - y1, cu1 - cu)), a)
		mb.box(Vector3.ZERO, Vector3(2.4, 0.3, Vector2(cu1 - cu, y1 - y0).length() + 0.05), Models.WOOD)
		mb.xform = saved
		cu = cu1
	var u := lf + 3.0
	while u < pe:
		for side: float in [-1.2, 1.2]:
			var pile_top := isl.road_y(u) - 0.45
			mb.box(Vector3(v + side, (pile_top - 10.5) * 0.5, u), Vector3(0.6, pile_top + 10.5, 0.6), Models.WOOD)
		u += 6.0
	# A fendered head across the catwalk's end, where her end lies.
	mb.box(Vector3(v, ly - 0.6, pe), Vector3(12.0, 1.2, 2.4), CONCRETE)
	mb.box(Vector3(v, ly - 1.8, pe + 1.4), Vector3(10.0, 3.0, 0.5), Models.HULL_DARK)
	for side: float in [-1.0, 1.0]:
		var dv := v + side * Layout.TIE_UP_SPACING * 0.5
		var shared := false
		for j in i:
			if isl.slips[j].tie_up and absf(isl.slip_offset(j) - side * Layout.TIE_UP_SPACING * 0.5 - dv) < 1.0:
				shared = true
		if shared:
			continue
		var inner_cap := _dolphin(mb, Vector3(dv, 0, pe + 22.0), 2.4, 6)
		eagle_perches.append(Eagles.Perch.new(mb.xform * inner_cap, Eagles.Kind.DOLPHIN))
		var cap := _dolphin(mb, Vector3(dv, 0, pe + 62.0), 3.15, 8)
		var mark := Models.slip_mark(side < 0)
		Models.add_cage_lantern(mb, cap, mark, Models.DOLPHIN_LANTERN)
		_add_dolphin_glow(glows, cap, mark)


## A wing wall from `a` to `b` (u, v in the terminal frame), its fendered face on
## the line, towards the slip, and its piles and bracing behind on the `side` (±1)
## away from it.
func _wing_wall(mb: MeshBuilder, a: Vector2, b: Vector2, side: float) -> void:
	var p0 := Vector3(a.y, 0, a.x)
	var p1 := Vector3(b.y, 0, b.x)
	var along := (p1 - p0).normalized()
	var out := Vector3(along.z, 0, -along.x)
	if out.x * side < 0.0:
		# (Keeping the frame right-handed.)
		out = -out
		along = -along
	var length := p0.distance_to(p1)
	var saved := mb.xform
	mb.xform = saved * Transform3D(Basis(out, Vector3.UP, along), (p0 + p1) * 0.5)
	# Fender panel, the timber wall behind it and a cap along the top.
	mb.box(Vector3(0.36, 1.8, 0), Vector3(0.72, 10.8, length + 0.6), Models.HULL_DARK)
	mb.box(Vector3(1.5, 1.2, 0), Vector3(1.65, 13.2, length), Models.WOOD)
	mb.box(Vector3(1.35, 7.65, 0), Vector3(2.7, 0.54, length + 0.9), Color(0.72, 0.72, 0.7))
	var n := maxi(2, ceili(length / 5.1))
	for i in n + 1:
		var z := -length * 0.5 + length * i / n
		mb.cylinder(Vector3(3.0, -6.0, z), 0.72, 0.66, 13.8, 6, Models.WOOD, Color(0.62, 0.6, 0.56))
	mb.xform = saved


## A dolphin: a cluster of piles round one at `c` (on the waterline, terminal
## frame), `r` across, under a concrete cap. Returns the top of the cap.
func _dolphin(mb: MeshBuilder, c: Vector3, r: float, piles: int) -> Vector3:
	var top := 10.2
	mb.cylinder(c + Vector3(0, -6.0, 0), 0.9, 0.84, top + 6.0, 6, Models.WOOD)
	for i in piles:
		var ang := TAU * i / piles
		var d := Vector3(cos(ang), 0, sin(ang))
		var foot := c + d * (r - 0.15) + Vector3(0, -6.0, 0)
		mb.cylinder(foot, 0.78, 0.66, top + 5.4, 6, Models.WOOD)
	mb.cylinder(c + Vector3(0, top - 0.6, 0), r + 0.3, r, 1.65, piles, Color(0.74, 0.74, 0.71), Color(0.8, 0.8, 0.77))
	var cap := c + Vector3(0, top + 1.05, 0)
	for k in 3:
		var ang := TAU * (k + 0.25) / 3.0
		var seat := mb.xform * (cap + Vector3(cos(ang), 0, sin(ang)) * r * 0.55)
		_perch(seat, seat, 0.0, Seagulls.Kind.DOLPHIN)
	return cap


func _add_tree_cell(p: Vector3) -> void:
	var k := Vector2i(floori(p.x / TREE_CELL), floori(p.z / TREE_CELL))
	if not tree_cells.has(k):
		tree_cells[k] = PackedVector3Array()
	var crown := p + Vector3(0.0, 4.0, 0.0)
	tree_cells[k].append(crown)
	_highest_tree_crown = maxf(_highest_tree_crown, crown.y)


## How far the nearest tree is from `p`, looking no further than `reach` (INF past it).
func nearest_tree_distance(p: Vector3, reach: float) -> float:
	if p.y > _highest_tree_crown + reach:
		return INF
	var r := ceili(reach / TREE_CELL)
	var c := Vector2i(floori(p.x / TREE_CELL), floori(p.z / TREE_CELL))
	var best := reach * reach
	for dz in range(-r, r + 1):
		for dx in range(-r, r + 1):
			var pts: Variant = tree_cells.get(c + Vector2i(dx, dz))
			if pts == null:
				continue
			for t: Vector3 in pts:
				best = minf(best, t.distance_squared_to(p))
	return sqrt(best) if best < reach * reach else INF


## Eagle lookouts: the tallest conifer in each EAGLE_CELL along the shore, its top
## (the variant's highest point) facing out over the nearest water.
func _eagle_trees(pines: Array[Transform3D]) -> void:
	var variants := TreeModel.variants(false)
	var tops: Array[Vector3] = []
	for vr: Array in variants:
		var mesh: Mesh = vr[0]
		var top := Vector3.ZERO
		for si in mesh.get_surface_count():
			for p: Vector3 in mesh.surface_get_arrays(si)[Mesh.ARRAY_VERTEX]:
				if p.y > top.y:
					top = p
		tops.append(top)
	var best := {}
	for xf in pines:
		if not await _frames.can_continue():
			return
		var o := xf.origin
		var lowest := INF
		var away := 0.0
		for i in 8:
			var a := TAU * i / 8.0
			var h := terrain.height_at(o.x + cos(a) * EAGLE_SHORE, o.z + sin(a) * EAGLE_SHORE)
			if h < lowest:
				lowest = h
				away = a
		if lowest > -1.0:
			continue
		var top := xf * tops[TreeModel.variant_at(o, variants.size())]
		var key := Vector2i(floori(o.x / EAGLE_CELL), floori(o.z / EAGLE_CELL))
		if not best.has(key) or top.y > (best[key][0] as Vector3).y:
			best[key] = [top, atan2(cos(away), sin(away))]
	for key: Vector2i in best:
		eagle_perches.append(Eagles.Perch.new(best[key][0], Eagles.Kind.TREE, best[key][1]))


# --- Roads & towns ------------------------------------------------------------------

func _build_roads() -> void:
	var mb := MeshBuilder.new()
	var lamps := MeshBuilder.new()
	var aprons := MeshBuilder.new()
	for isl in map.towns:
		if isl.road_main_a.is_empty():
			continue
		_ticket_approach(aprons, isl)
		var main := isl.road_main_a.duplicate()
		var centre := RoadMesh.length_of(isl.road_main_a)
		if isl.road_main_b.size() > 1:
			main.append_array(isl.road_main_b.slice(1))
		var total := RoadMesh.length_of(main)
		var crossed := not isl.road_cross.is_empty()
		var style := RoadMesh.Style.DOUBLE_EDGES if isl.population >= DOUBLE_LINE_POP else RoadMesh.Style.DASHED_EDGES
		# No markings over the lot's apron, through the junction or right at the end.
		var show_main := func(s: float) -> float:
			var k := smoothstep(3.0, 9.0, s) * smoothstep(0.0, 4.0, total - s)
			return k * smoothstep(6.0, 11.0, absf(s - centre)) if crossed else k
		RoadMesh.strip(mb, main, ROAD, style, show_main)
		var lines: Array[PackedVector3Array] = [main]
		for line in isl.road_cross:
			var length := RoadMesh.length_of(line)
			var show := func(s: float) -> float:
				return smoothstep(RoadMesh.HALF, RoadMesh.HALF + 5.0, s) * smoothstep(0.0, 4.0, length - s)
			RoadMesh.strip(mb, line, ROAD, RoadMesh.Style.DASHED, show, RoadMesh.HALF)
			lines.append(line)
		for line in lines:
			for i in range(0, line.size(), 3):
				_block(line[i], 9.0)
			_street_lamps(lamps, line, isl.road_main_a[isl.road_main_a.size() - 1])
	var mat := ShaderMaterial.new()
	mat.shader = load(ROAD_SHADER)
	_add_mesh(mb.commit(mat), "Roads", false)
	_add_mesh(lamps.commit(), "StreetLamps", false)
	_add_mesh(aprons.commit(), "TicketApproaches", false)


func _ticket_approach(mb: MeshBuilder, isl: MapData.Town) -> void:
	# Widen the inbound shoulder into the three staffed channels. Build only
	# the extra pavement so the existing through road retains its surface.
	var lateral := isl.lateral()
	var entrance := isl.road_main_a[0]
	var length := (entrance - isl.road_main_a[-1]).dot(isl.dock_dir)
	for i in range(1, isl.road_main_a.size()):
		var a := isl.road_main_a[i - 1]
		var b := isl.road_main_a[i]
		var sa := Layout.ticket_spread((entrance - a).dot(isl.dock_dir), length)
		var sb := Layout.ticket_spread((entrance - b).dot(isl.dock_dir), length)
		if sa <= 0.0:
			break
		var inner_a := a - lateral * RoadMesh.HALF
		var inner_b := b - lateral * RoadMesh.HALF
		var outer_a := inner_a - lateral * Layout.TICKET_EXTRA_WIDTH * sa
		var outer_b := inner_b - lateral * Layout.TICKET_EXTRA_WIDTH * sb
		mb.quad(inner_a, outer_a, outer_b, inner_b, ROAD, Vector3.UP)
		mb.quad(outer_a, outer_a - Vector3.UP * 1.5, outer_b - Vector3.UP * 1.5, outer_b, ROAD.darkened(0.25), -lateral)
		# Broken white dividers follow the paved fan and stop at the booth islands.
		if sa > 0.4 and (entrance - b).dot(isl.dock_dir) > 10.0:
			for index in Layout.TICKET_LANES.size() - 1:
				var divider: float = (Layout.TICKET_LANES[index] + Layout.TICKET_LANES[index + 1]) * 0.5
				var p := a + lateral * lerpf(-Layout.EXIT_V, divider, sa) + Vector3.UP * 0.04
				var q := b + lateral * lerpf(-Layout.EXIT_V, divider, sb) + Vector3.UP * 0.04
				var tip := p.lerp(q, 0.55)
				mb.quad(p - lateral * 0.10, p + lateral * 0.10, tip + lateral * 0.10, tip - lateral * 0.10, LINE_WHITE, Vector3.UP)
		_block(outer_a, 4)


## Sodium lamps every LAMP_GAP along a road, alternating sides, none in the
## junction at `crossing`.
func _street_lamps(mb: MeshBuilder, line: PackedVector3Array, crossing: Vector3) -> void:
	const LAMP_GAP := 48.0
	glows.xform = Transform3D.IDENTITY
	var next := LAMP_GAP * 0.5
	var walked := 0.0
	var side := 1.0
	for i in line.size() - 1:
		var a := line[i]
		var b := line[i + 1]
		var lat := (b - a).cross(Vector3.UP)
		lat.y = 0.0
		var seg := Vector3(b.x - a.x, 0.0, b.z - a.z).length()
		if seg < 0.03:
			continue
		lat = lat.normalized()
		while next <= walked + seg:
			var p := a.lerp(b, (next - walked) / seg) + lat * 6.6 * side
			if Vector2(p.x - crossing.x, p.z - crossing.z).length() < 14.0:
				next += LAMP_GAP * 0.25
				continue
			mb.box(p + Vector3(0, 5.1, 0), Vector3(0.36, 11.4, 0.36), Color(0.3, 0.31, 0.33))
			mb.box(p + Vector3(0, 10.8, 0), Vector3(1.2, 0.42, 1.2), Color(0.25, 0.26, 0.28))
			mb.box(p + Vector3(0, 10.5, 0), Vector3(0.9, 0.21, 0.9), Models.lamp_glass(GlowBuilder.SODIUM))
			glows.glow(p + Vector3(0, 10.35, 0), GlowBuilder.SODIUM, 0.66, 5.0, p.y < 12.0, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
			glows.pool(p + Vector3(0, 0.36, 0) - lat * 3.6 * side, GlowBuilder.SODIUM, 15.0, 0.22)
			_perch(p + Vector3(0, 11.01, 0), p + Vector3(0, 11.01, 0), 0.0, Seagulls.Kind.LAMP)
			side = -side
			next += LAMP_GAP
		walked += seg




func _build_towns() -> void:
	# The kit houses: the painted families twice each in different colours, the
	# contemporary ones as authored. Then the downtown storefronts.
	house_meshes.clear()
	house_kit_names.clear()
	shop_meshes.clear()
	shop_names_list.clear()
	var variants: Array[Mesh] = []
	var kit_names: Array[String] = []
	for k in Models.KIT_HOUSES.size():
		var kit_name: String = Models.KIT_HOUSES[k]
		var coats := 1 if kit_name.begins_with("contemporary") else 2
		for c in coats:
			if not await _frames.can_continue():
				return
			var n := kit_names.size()
			var mesh: Mesh
			if coats == 1:
				mesh = Models.kit_house(kit_name)
			else:
				mesh = Models.kit_house(
					kit_name, WALLS[n % WALLS.size()], ROOFS[(n * 3 + 1) % ROOFS.size()]
				)
			variants.append(mesh)
			house_meshes.append(mesh)
			kit_names.append(kit_name)
			house_kit_names.append(kit_name)
	var houses := kit_names.size()
	var shop_names := SHOP_SHELLS.keys()
	shop_names.erase(CITY_HALL)
	var city_hall_variant := houses + shop_names.size()
	shop_names.append(CITY_HALL)
	var shop_plans: Array[Rect2] = []
	for shop_name: String in shop_names:
		if not await _frames.can_continue():
			return
		var path := "res://assets/models/coastal_shops/%s.glb" % shop_name
		var mb := MeshBuilder.new()
		Models._append_part(mb, ModelParts.baked(path), Transform3D.IDENTITY)
		var shell: Vector2 = SHOP_SHELLS[shop_name]
		mb.box(Vector3(0, -KIT_MAX_DROP / 2, 0), Vector3(shell.x, KIT_MAX_DROP, shell.y), Models.KIT_FOUNDATION)
		var mesh := mb.commit()
		var bounds := mesh.get_aabb()
		shop_plans.append(Rect2(bounds.position.x, bounds.position.z, bounds.size.x, bounds.size.z))
		variants.append(mesh)
		shop_meshes.append(mesh)
		shop_names_list.append(shop_name)
	var per_variant: Array = []
	for v in variants:
		var list: Array[Transform3D] = []
		per_variant.append(list)

	var town_rng := RandomNumberGenerator.new()
	town_rng.seed = map.map_seed * 41 + 19
	const RESERVE_LANDMARKS := 4
	const RESERVE_COMMERCIAL := 12
	const RESERVE_HOUSES := 36

	for isl in map.towns:
		isl.growth_lots.clear()
		isl.initial_houses = 0
		isl.initial_commercial = 0
		var tc := isl.town_center
		var t := isl.town_axis
		var inland := Vector3.UP.cross(t)  # perpendicular to the cross street
		if isl.has_dock:
			inland = -isl.dock_dir
		var spacing := 16.5
		var candidates: Array[Dictionary] = []
		for b in range(-10, 11):
			if not await _frames.can_continue():
				return
			for a in range(-10, 11):
				if isl.has_dock and (a == 0 or b == 0):
					continue  # the streets
				var p := tc + t * (a * spacing) + inland * (b * spacing)
				p += Vector3(town_rng.randf_range(-2.2, 2.2), 0, town_rng.randf_range(-2.2, 2.2))
				if isl.has_dock and (p - isl.shore).dot(isl.dock_dir) > Layout.LOT_BACK - isl.lot_shift() - 12.0:
					continue
				if _is_blocked(p.x, p.z):
					continue
				var h := terrain.height_v(p)
				if h < 4.2 or h > 55.0:
					continue
				var hmin := h
				var hmax := h
				for o: Vector3 in [t * 4.8, -t * 4.8, inland * 5.7, -inland * 5.7]:
					var hh := terrain.height_v(p + o)
					hmin = minf(hmin, hh)
					hmax = maxf(hmax, hh)
				if hmax - hmin > 4.2 or hmin < 2.4:
					continue
				var front := -inland * signf(b) if absi(b) <= absi(a) or a == 0 else -t * signf(a)
				if not isl.has_dock:
					front = -inland
				var yaw := atan2(front.x, front.z) + town_rng.randf_range(-0.05, 0.05)
				var r := Vector2(a, b).length() * spacing
				(
					candidates
					. append(
						{
							"p": p,
							"yaw": yaw,
							"r": r,
							"sort_r": r + town_rng.randf_range(-9.0, 9.0),
							"drop": hmax - hmin,
							"h": h,
						}
					)
				)
		candidates.sort_custom(
			func(x: Dictionary, y: Dictionary) -> bool:
				return float(x["sort_r"]) < float(y["sort_r"])
		)

		var want_houses := TownGrowth.target_houses_for(isl.population)
		var want_commercial := TownGrowth.target_commercial_for(isl.population)
		var has_city_hall := false
		var placed_comm := 0
		var placed_houses := 0
		var reserved_landmarks := 0
		var reserved_comm := 0
		var reserved_houses := 0
		var used_idx := {}

		# 1. Reserve up to 4 flat landmark pads (1 near downtown, 3 on the outer apron for
		# Depot / Hangar+Windsock / Observatory) so milestones always have clean room.
		for idx in candidates.size():
			if reserved_landmarks >= RESERVE_LANDMARKS:
				break
			var c: Dictionary = candidates[idx]
			if float(c["drop"]) > 2.6:
				continue
			var r: float = float(c["r"])
			if reserved_landmarks == 0 and r > 70.0:
				continue
			if reserved_landmarks >= 1 and r < 52.0:
				continue
			var p: Vector3 = c["p"]
			var too_close := false
			for existing in isl.growth_lots:
				if existing.pos.distance_to(p) < 28.0:
					too_close = true
					break
			if too_close:
				continue
			used_idx[idx] = true
			var llot := MapData.TownLot.new()
			llot.pos = Vector3(p.x, float(c["h"]), p.z)
			llot.yaw = float(c["yaw"])
			llot.lot_y = float(c["h"])
			llot.kind = MapData.TownLot.Kind.LANDMARK
			llot.waterfront = float(c["h"]) < 15.0
			isl.growth_lots.append(llot)
			_block(p, 7.5)
			reserved_landmarks += 1

		# 2. Place initial commercial buildings (1 per 333 pop) and reserve commercial growth lots.
		var shop_count := shop_names.size()
		var regular_shop_count := maxi(shop_count - 1, 1)
		for idx in candidates.size():
			if used_idx.has(idx):
				continue
			if placed_comm >= want_commercial and reserved_comm >= RESERVE_COMMERCIAL:
				break
			var c: Dictionary = candidates[idx]
			var p: Vector3 = c["p"]
			var yaw: float = float(c["yaw"])
			var sc := town_rng.randf_range(0.92, 1.08)
			var shop_idx := town_rng.randi_range(0, regular_shop_count - 1)
			if (
				placed_comm < want_commercial
				and not has_city_hall
				and isl.population >= 2500
				and isl.community_type == "residential"
			):
				shop_idx = city_hall_variant - houses
			var vi := houses + shop_idx
			var basis := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * sc)
			var plan: Rect2 = shop_plans[shop_idx]
			var lot := _kit_lot_heights(p, basis, plan)
			if lot.x - lot.y > KIT_MAX_DROP or lot.y < 2.4:
				continue
			used_idx[idx] = true
			if placed_comm < want_commercial:
				var pad := Rect2(plan.position * sc, plan.size * sc).grow(KIT_LOT_MARGIN)
				terrain.level_now(Vector3(p.x, 0, p.z), basis.z.normalized(),
					pad.position.y, pad.end.y, pad.position.x, pad.end.x, lot.z, KIT_LOT_BLEND)
				var xf := Transform3D(basis, Vector3(p.x, lot.z, p.z))
				(per_variant[vi] as Array[Transform3D]).append(xf)
				if vi == city_hall_variant:
					has_city_hall = true
				var shop_name: String = shop_names[shop_idx]
				var front_z: float = SHOP_SHELLS[shop_name].y / 2
				if shop_name == "glass_hall":
					front_z += 0.46
				_entry_light(
					xf,
					Vector3(.83, 2.59, front_z + .30),
					Vector3(0, .34, front_z + .64),
					float(c["h"]) < 15.0
				)
				_block(p, 7.8)
				placed_comm += 1
			else:
				var clot := MapData.TownLot.new()
				clot.pos = Vector3(p.x, lot.z, p.z)
				clot.yaw = yaw
				clot.scale = sc
				clot.lot_y = lot.z
				clot.kind = MapData.TownLot.Kind.COMMERCIAL
				clot.variant = shop_idx
				clot.waterfront = float(c["h"]) < 15.0
				isl.growth_lots.append(clot)
				_block(p, 5.5)
				reserved_comm += 1

		# 3. Place initial houses (1 per 100 pop) and reserve residential expansion lots.
		for idx in candidates.size():
			if used_idx.has(idx):
				continue
			if placed_houses >= want_houses and reserved_houses >= RESERVE_HOUSES:
				break
			var c: Dictionary = candidates[idx]
			var p: Vector3 = c["p"]
			var yaw: float = float(c["yaw"])
			var vi := town_rng.randi_range(0, houses - 1)
			var basis := Basis(Vector3.UP, yaw)
			var plan: Rect2 = Models.kit_footprint(kit_names[vi])
			var lot := _kit_lot_heights(p, basis, plan)
			if lot.x - lot.y > KIT_MAX_DROP or lot.y < 2.4:
				continue
			used_idx[idx] = true
			if placed_houses < want_houses:
				var pad := Rect2(plan.position, plan.size).grow(KIT_LOT_MARGIN)
				terrain.level_now(
					Vector3(p.x, 0, p.z),
					basis.z.normalized(),
					pad.position.y,
					pad.end.y,
					pad.position.x,
					pad.end.x,
					lot.z,
					KIT_LOT_BLEND
				)
				var xf := Transform3D(basis, Vector3(p.x, lot.z, p.z))
				(per_variant[vi] as Array[Transform3D]).append(xf)
				_entry_light(
					xf,
					Models.kit_marker(kit_names[vi], "PorchLight"),
					Models.kit_marker(kit_names[vi], "Entry"),
					float(c["h"]) < 15.0
				)
				_block(p, 7.8)
				placed_houses += 1
			else:
				var hlot := MapData.TownLot.new()
				hlot.pos = Vector3(p.x, lot.z, p.z)
				hlot.yaw = yaw
				hlot.scale = 1.0
				hlot.lot_y = lot.z
				hlot.kind = MapData.TownLot.Kind.HOUSE
				hlot.variant = vi
				hlot.waterfront = float(c["h"]) < 15.0
				isl.growth_lots.append(hlot)
				_block(p, 5.5)
				reserved_houses += 1

		isl.initial_houses = placed_houses
		isl.initial_commercial = placed_comm

	var no_colors: Array[Color] = []
	for i in variants.size():
		var xforms: Array[Transform3D] = per_variant[i]
		var group_name: String = "Houses%d" % i if i < houses else shop_names[i - houses]
		await _multimesh(variants[i], xforms, no_colors, group_name)


## Reserves a hilltop radio tower pad on each inhabited island and builds the
## starting tower on Madrona Island immediately (other islands build at 6k pop).
func _build_radio_towers() -> void:
	for isl in map.islands:
		if isl.is_mainland or not isl.inhabited:
			continue
		if not await _frames.can_continue():
			return
		var best_pos := Vector3.ZERO
		var best_h := -INF
		var span := minf(isl.radius * 0.6, 360.0)
		var step := 24.0
		var z := -span
		while z <= span:
			var x := -span
			while x <= span:
				var px := isl.center.x + x
				var pz := isl.center.y + z
				if not _is_blocked(px, pz):
					var h := terrain.height_at(px, pz)
					if h > best_h and h >= 10.0:
						var hmin := h
						var hmax := h
						for o: Vector2 in [
							Vector2(5, 0), Vector2(-5, 0), Vector2(0, 5), Vector2(0, -5)
						]:
							var hh := terrain.height_at(px + o.x, pz + o.y)
							hmin = minf(hmin, hh)
							hmax = maxf(hmax, hh)
						if hmax - hmin <= 4.5 and hmin >= 6.0:
							best_h = h
							best_pos = Vector3(px, (hmin + hmax) * 0.5, pz)
				x += step
			z += step
		if best_h <= -INF:
			continue
		var rlot := MapData.TownLot.new()
		rlot.pos = best_pos
		rlot.lot_y = best_pos.y
		rlot.yaw = 0.0
		rlot.kind = MapData.TownLot.Kind.RADIO_TOWER
		isl.radio_tower_lot = rlot
		_block(best_pos, 8.0)
		if isl.radio_tower_built:
			rlot.occupied = true
			terrain.level_now(
				Vector3(best_pos.x, 0.0, best_pos.z),
				Vector3.FORWARD,
				-6.5,
				6.5,
				-6.5,
				6.5,
				best_pos.y,
				KIT_LOT_BLEND
			)
			var mesh := landmarks.mesh_for("radio_tower")
			if mesh != null:
				var mi := _add_mesh(mesh, "RadioTower_%s" % isl.name)
				mi.position = best_pos
			glows.xform = Transform3D(Basis.IDENTITY, best_pos)
			glows.glow(
				Vector3(0.0, 55.2, 0.0),
				Color(1.0, 0.22, 0.16),
				0.75,
				18.0,
				false,
				0.0,
				Vector3.ZERO,
				Models.LAMP_ON_AT
			)


## The highest (x), lowest (y) and mean (z) ground under `plan` (house frame x, z)
## placed at `p` turned by `basis`, sampled on a 5 x 5 grid.
func _kit_lot_heights(p: Vector3, basis: Basis, plan: Rect2) -> Vector3:
	var hi := -INF
	var lo := INF
	var sum := 0.0
	for i in 5:
		for j in 5:
			var local := Vector3(plan.position.x + plan.size.x * i / 4.0, 0,
				plan.position.y + plan.size.y * j / 4.0)
			var h := terrain.height_v(p + basis * local)
			hi = maxf(hi, h)
			lo = minf(lo, h)
			sum += h
	return Vector3(hi, lo, sum / 25.0)


## A lamp by the door and the light it throws on the path.
func _entry_light(xf: Transform3D, lamp: Vector3, entry: Vector3, waterfront: bool) -> void:
	glows.xform = xf
	glows.glow(lamp + Vector3(0, 0, 0.08), GlowBuilder.WARM, 0.22, 3.5, waterfront, 0.0, Vector3(0, 0, 1), Models.LAMP_ON_AT)
	glows.pool(Vector3(lamp.x, entry.y + 0.05, entry.z - 0.6), GlowBuilder.WARM, 4.5, 0.3)


func _build_lighthouses() -> void:
	var mb := MeshBuilder.new()
	for isl in map.islands:
		if isl.is_mainland or not isl.inhabited or rng.randf() > 0.5:
			continue
		var ang := rng.randf() * TAU
		var dir := Vector3(cos(ang), 0, sin(ang))
		var c := Vector3(isl.center.x, 0, isl.center.y)
		var r := 0.0
		while r < isl.radius * 1.6 and terrain.height_v(c + dir * r) > 4.8:
			r += 1.5
		var p := c + dir * maxf(r - 9.0, 0.0)
		var h := terrain.height_v(p)
		if h < 3.6 or _is_blocked(p.x, p.z):
			continue
		var variant := floori(_hash(p.x, p.z) * Models.LIGHTHOUSE_VARIANTS)
		var gallery := Models.add_lighthouse(mb, Vector3(p.x, h - 0.3, p.z), variant, PI - ang)
		if variant < Models.LIGHTHOUSE_VARIANTS / 2:
			_place_keepers_house(mb, p, gallery.basis)
		for k in 3:
			var rail_angle := (k - 1) * TAU / 16.0
			var seat := gallery * Vector3(cos(rail_angle) * Models.LIGHTHOUSE_RAIL_RADIUS,
					Models.LIGHTHOUSE_RAIL_Y, sin(rail_angle) * Models.LIGHTHOUSE_RAIL_RADIUS)
			_perch(seat, seat, 0.0, Seagulls.Kind.LIGHTHOUSE)
		var lamp := gallery * (Vector3.UP * Models.LIGHTHOUSE_LENS_Y)
		var beacon := Color(1.0, 0.92, 0.75)
		glows.xform = Transform3D.IDENTITY
		glows.glow(lamp, beacon, 2.4, 9.0, true, 0.0, Vector3.ZERO, 0.0)
		glows.beam(lamp, beacon, 6.6, 225.0, 0.5, 0.3, _hash(p.x, p.z) * TAU)
		_block(p, 18.0)
	_add_mesh(mb.commit(), "Lighthouses")


## Sample the house's own footprint so rising ground cannot swallow its windows.
func _place_keepers_house(mb: MeshBuilder, tower: Vector3, basis: Basis) -> void:
	var style := floori(_hash(tower.z, tower.x) * Models.LIGHTHOUSE_HOUSES.size())
	for offset in [Vector3(10, 0, 3), Vector3(7, 0, 10), Vector3(7, 0, -10)]:
		var center: Vector3 = tower + basis * offset
		var high := terrain.height_v(center)
		var low := high
		var clear := true
		# Include the widest eaves and the front porch in the site check.
		for x in [-4.2, 0.0, 4.2]:
			for z in [-2.9, 0.0, 4.4]:
				var point := center + basis * Vector3(x, 0, z)
				var ground := terrain.height_v(point)
				high = maxf(high, ground)
				low = minf(low, ground)
				if _is_blocked(point.x, point.z):
					clear = false
		if clear and low > 2.0 and high - low < 2.1:
			center.y = high - 0.25
			Models.add_keepers_house(mb, Transform3D(basis, center), style)
			return


# --- Haul-outs -----------------------------------------------------------------------

## The seals' rock ledges: a low flat slab off the shore, dark and wet along the
## waterline, its top whitened by the birds, with a boulder or two about. Beaches
## and ledges are kept clear of trees and scattered rocks so there's room to lie.
func _build_haul_outs() -> void:
	var mb := MeshBuilder.new()
	var r := RandomNumberGenerator.new()
	for h in map.haul_outs:
		match h.kind:
			MapData.HaulOut.Kind.ROCK:
				r.seed = map.map_seed * 41 + h.id
				mb.xform = h.ledge
				var hx := h.ledge_size.x * 0.5
				var hz := h.ledge_size.z * 0.5
				var outline := PackedVector2Array()
				for k in 12:
					var a := TAU * k / 12.0
					var j := r.randf_range(0.8, 1.0)
					outline.append(Vector2(cos(a) * hx * j, sin(a) * hz * j))
				var wet := PackedVector2Array()
				for p in outline:
					wet.append(p * 1.02 + p.normalized() * 0.04)
				var grey := Color(0.44, 0.41, 0.4).lerp(Color(0.52, 0.47, 0.45), r.randf())
				mb.extrude(outline, -13.8 - h.top, 0.0, grey, grey.lerp(Color(0.8, 0.79, 0.74), 0.18), 1.3)
				mb.extrude(wet, -13.8 - h.top, -h.top + 0.22, Color(0.2, 0.2, 0.19), Color(0, 0, 0, 0), 1.3)
				for k in r.randi_range(1, 3):
					var at := Vector3(r.randf_range(-hx, hx) * 1.1, 0.0, r.randf_range(-hz, -hz * 0.3))
					var s := r.randf_range(0.6, 1.1)
					mb.cylinder(at + Vector3(0, -0.4, 0), s * 1.0, s * 0.35, s * 0.55 + 0.4, 5, grey.darkened(0.1),
						grey.lerp(Color(0.8, 0.79, 0.74), 0.15), r.randf() * TAU)
				_block(h.ledge.origin, maxf(hx, hz) + 1.5)
			MapData.HaulOut.Kind.BEACH:
				for sp in h.spots:
					_block(sp.at, 2.0)
					_block(sp.edge, 1.0)
	mb.xform = Transform3D.IDENTITY
	if not mb.is_empty():
		_add_mesh(mb.commit(), "HaulOutRocks")


# --- Vegetation ---------------------------------------------------------------------

func _build_vegetation() -> void:
	var pines: Array[Transform3D] = []
	var pine_cols: Array[Color] = []
	var rounds: Array[Transform3D] = []
	var round_cols: Array[Color] = []
	var rocks: Array[Transform3D] = []
	var towns := map.towns

	var step := 8.1
	var hs := terrain.half_size - 9.0
	var z := -hs
	while z < hs:
		if not await _frames.can_continue():
			return
		var x := -hs
		while x < hs:
			var px := x + rng.randf_range(-4.2, 4.2)
			var pz := z + rng.randf_range(-4.2, 4.2)
			x += step
			var h := terrain.height_at(px, pz)
			# Open water gets nothing (and draws no random numbers), so skip the slope.
			if h <= -3.0 or _is_blocked(px, pz):
				continue
			var slope := Vector2(terrain.height_at(px + 3.0, pz) - terrain.height_at(px - 3.0, pz),
				terrain.height_at(px, pz + 3.0) - terrain.height_at(px, pz - 3.0)).length() / 6.0
			if h > 3.9 and slope < 1.0:
				var density := tree_density(px, pz, h)
				var upland := smoothstep(12.0, 36.0, h)
				var near_town := false
				for isl in towns:
					var town_r := sqrt(isl.population / 90.0) * 9.0 + 18.0
					if Vector2(px - isl.town_center.x, pz - isl.town_center.z).length() < town_r:
						near_town = true
						break
				if near_town:
					density *= 0.2
				if rng.randf() > density:
					continue
				var cs := card_share(px, pz)
				if cs > 0.0 and _edge_rng.randf() < cs:
					# A card stands for the ~7 trees around it (Backdrop: one per 420 m²).
					if _edge_rng.randf() < 81.0 / 420.0:
						edge_cards.append(Vector3(px, h, pz))
					continue
				var s := rng.randf_range(0.75, 1.35) * (1.0 + upland * 0.25)
				var basis := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s, s * rng.randf_range(0.9, 1.2), s) * Models.LEGACY_SCALE)
				var xf := Transform3D(basis, Vector3(px, h - 0.3, pz))
				var tint := Color(rng.randf_range(0.8, 1.0), rng.randf_range(0.85, 1.0), rng.randf_range(0.8, 0.95))
				# Darkening toward the cards' shade where they mix in.
				tint = tint.darkened(cs * 0.15)
				if rng.randf() < (0.45 if near_town else 0.2):
					rounds.append(xf)
					round_cols.append(tint)
				else:
					pines.append(xf)
					pine_cols.append(tint)
			elif (h > -3.0 and h < 2.1 and rng.randf() < 0.14) or (h > 2.1 and slope >= 1.0 and rng.randf() < 0.1):
				var s := rng.randf_range(0.5, 1.7)
				var basis := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s * rng.randf_range(0.8, 1.4), s, s) * Models.LEGACY_SCALE)
				rocks.append(Transform3D(basis, Vector3(px, h, pz)))
		z += step
	await _eagle_trees(pines)
	for list: Array[Transform3D] in [pines, rounds]:
		for xf in list:
			if not await _frames.can_continue():
				return
			_add_tree_cell(xf.origin)
	for c in edge_cards:
		_add_tree_cell(c)
	TreeModel.card_material().set_shader_parameter("map_half", terrain.half_size)
	TreeModel.card_material(true).set_shader_parameter("map_half", terrain.half_size)
	await _forest(TreeModel.variants(false), pines, pine_cols, "Pines")
	await _forest(TreeModel.variants(true), rounds, round_cols, "RoundTrees")
	var no_colors: Array[Color] = []
	await _multimesh(Models.rock(), rocks, no_colors, "Rocks")


## Rock along the shores: big faceted blocks stacked into the steep faces, turned
## along the shore and half-buried, and boulders and stacks in the shallows at their
## foot. The terrain's painted cliff stays behind them and takes over far away.
func _build_shore_rocks() -> void:
	if not (SHORE_ROCKS or OS.has_environment("TIDEWAYS_SHORE_ROCKS")) \
			or OS.has_environment("TIDEWAYS_NO_SHORE_ROCKS"):
		return
	var t0 := Time.get_ticks_msec()
	var r := RandomNumberGenerator.new()
	r.seed = map.map_seed * 53 + 11
	var cliff_kit := Models.rock_kit("cliff")
	var boulder_kit := Models.rock_kit("boulder")
	var cliffs: Array = []
	var boulders: Array = []
	for i in cliff_kit.size():
		cliffs.append([] as Array[Transform3D])
		boulders.append([] as Array[Transform3D])
	var vn := terrain.n + 1
	var cell := Terrain.CELL
	var hs := terrain.half_size
	lift_side = ceili(hs * 2.0 / LIFT_CELL)
	grass_lift.resize(lift_side * lift_side)
	for j in range(4, vn - 4):
		if not await _frames.can_continue():
			return
		for i in range(4, vn - 4):
			var h := terrain.h_grid[j * vn + i]
			if h < -4.0 or h > 45.0:
				continue
			var gx := (terrain.h_grid[j * vn + i + 1] - terrain.h_grid[j * vn + i - 1]) / (2.0 * cell)
			var gz := (terrain.h_grid[(j + 1) * vn + i] - terrain.h_grid[(j - 1) * vn + i]) / (2.0 * cell)
			var slope := sqrt(gx * gx + gz * gz)
			var cliff := slope > 0.75 and h > -1.5
			var shallows := h > -3.2 and h < 1.0
			if not cliff and not shallows:
				continue
			var x := -hs + i * cell + r.randf_range(-0.5, 0.5) * cell
			var z := -hs + j * cell + r.randf_range(-0.5, 0.5) * cell
			if _is_blocked(x, z):
				continue
			# Downhill, i.e. out to sea for a shore.
			var out := Vector3(-gx, 0.0, -gz).normalized() if slope > 0.01 else Vector3(1, 0, 0)
			var side := Vector3(-out.z, 0, out.x)
			var along := atan2(out.x, out.z) + PI * 0.5
			if cliff and r.randf() < 0.5:
				# Stand a block at the foot of the face, tall enough to reach its lip.
				var p := Vector3(x, 0.0, z)
				var top := maxf(terrain.height_at(p.x - out.x * 5.0, p.z - out.z * 5.0), h)
				var foot := maxf(minf(terrain.height_at(p.x + out.x * 5.0, p.z + out.z * 5.0), h), -2.0)
				# Only faces that come down to the water: inland slopes keep their painted
				# crags, and a low step stays grass.
				if foot > 2.5 or top - foot < 1.5:
					continue
				var tall := clampf(top - foot, 2.0, 12.0) * r.randf_range(0.95, 1.15)
				var wide := clampf(tall * r.randf_range(0.7, 1.2), 3.0, 9.0)
				p += out * r.randf_range(0.5, 2.0) + side * r.randf_range(-1.0, 1.0)
				p.y = foot - tall * 0.15
				var b := Basis(Vector3.UP, along + r.randf_range(-0.3, 0.3))
				# Leaning back into the hill a little.
				b = Basis(side, r.randf_range(0.0, 0.15)) * b
				b = b.scaled(Vector3(wide, tall, maxf(wide * 0.7, 3.0)))
				var vi := r.randi() % cliff_kit.size()
				var xf := Transform3D(b, p)
				cliffs[vi].append(xf)
				_lift_cap(xf, cliff_kit[vi].get_meta("caps"))
			if shallows and r.randf() < (0.18 if slope > 0.5 else 0.03):
				for k in r.randi_range(1, 3):
					var s := r.randf_range(0.8, 3.0) if r.randf() < 0.8 else r.randf_range(3.5, 6.0)
					var p := Vector3(x, 0.0, z) + out * r.randf_range(0.0, 6.0) + side * r.randf_range(-4.0, 4.0)
					var gh := terrain.height_at(p.x, p.z)
					if gh < -4.0:
						continue
					p.y = gh - s * 0.2
					var b := Basis(Vector3.UP, r.randf() * TAU).scaled(Vector3(s, s * r.randf_range(0.7, 1.3), s * r.randf_range(0.8, 1.1)))
					boulders[r.randi() % boulder_kit.size()].append(Transform3D(b, p))
	var no_colors: Array[Color] = []
	var count := 0
	for i in cliff_kit.size():
		var c: Array[Transform3D] = cliffs[i]
		var bo: Array[Transform3D] = boulders[i]
		count += c.size() + bo.size()
		await _multimesh(cliff_kit[i], c, no_colors, "ShoreCliffs%d" % i)
		await _multimesh(boulder_kit[i], bo, no_colors, "ShoreBoulders%d" % i)
	print("Shore rocks: %d pieces (%d ms)" % [count, Time.get_ticks_msec() - t0])


## Marks the grass lift cells whose middle lies on a rock's cap (pulled in a metre
## from its edge, so blades don't hang over it) with the cap's height there.
func _lift_cap(xf: Transform3D, caps: PackedVector3Array) -> void:
	if caps.is_empty():
		return
	var w := PackedVector3Array()
	w.resize(caps.size())
	var mid := Vector3.ZERO
	for k in caps.size():
		w[k] = xf * caps[k]
		mid += w[k]
	mid /= caps.size()
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	var reach := 0.0
	for k in w.size():
		reach = maxf(reach, Vector2(w[k].x - mid.x, w[k].z - mid.z).length())
	if reach < 1.6:
		return
	var pull := 1.0 / reach
	for k in w.size():
		w[k] = w[k].lerp(Vector3(mid.x, w[k].y, mid.z), pull)
		lo = Vector2(minf(lo.x, w[k].x), minf(lo.y, w[k].z))
		hi = Vector2(maxf(hi.x, w[k].x), maxf(hi.y, w[k].z))
	var hs := terrain.half_size
	for cj in range(maxi(floori((lo.y + hs) / LIFT_CELL), 0), mini(ceili((hi.y + hs) / LIFT_CELL), lift_side)):
		for ci in range(maxi(floori((lo.x + hs) / LIFT_CELL), 0), mini(ceili((hi.x + hs) / LIFT_CELL), lift_side)):
			var q := Vector2(-hs + (ci + 0.5) * LIFT_CELL, -hs + (cj + 0.5) * LIFT_CELL)
			for k in range(0, w.size(), 3):
				var a := w[k]
				var b := w[k + 1]
				var c := w[k + 2]
				var d := (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z)
				if absf(d) < 1e-6:
					continue
				var l1 := ((b.z - c.z) * (q.x - c.x) + (c.x - b.x) * (q.y - c.z)) / d
				var l2 := ((c.z - a.z) * (q.x - c.x) + (a.x - c.x) * (q.y - c.z)) / d
				if l1 < 0.0 or l2 < 0.0 or l1 + l2 > 1.0:
					continue
				var h := a.y * l1 + b.y * l2 + c.y * (1.0 - l1 - l2)
				var v := clampi(roundi((h + 4.0) * 4.0), 1, 255)
				var o := cj * lift_side + ci
				grass_lift[o] = maxi(grass_lift[o], v)
				break


func lift_image() -> Image:
	return Image.create_from_data(lift_side, lift_side, false, Image.FORMAT_R8, grass_lift)




## Put the dining deck flush with the right edge of the jetty, landward of its T-head.
## The deck surface is local Y=0 and the opening in its railing is on the -X side.
func _marina_restaurant(m: MapData.Marina) -> void:
	var center := Vector3(2.7 + 7.0, 2.25 + 0.375, 24.0)
	for x: float in [-7.0, 0.0, 7.0]:
		for z: float in [-4.0, 1.0, 6.0]:
			if terrain.height_v(m.at(center.z + z, center.x + x)) >= 0.0:
				return
	var model: String = PIER_RESTAURANTS[m.id % PIER_RESTAURANTS.size()]
	var path := "res://assets/models/coastal_shops/%s.glb" % model
	var mesh := Models._cached(path, func(): return ModelParts.baked(path).commit())
	var dining := _add_mesh(mesh, model + "_" + str(m.id))
	dining.transform = m.xform() * Transform3D(Basis.IDENTITY, center)


## A wooden pier out to a T-head float with berths along its seaward face (the
## sailboats themselves are MarineTraffic's), a lamp at each end of the head.
func _build_marinas() -> void:
	var plank := Color(0.56, 0.46, 0.34)
	var float_col := Color(0.66, 0.6, 0.5)
	for m in map.marinas:
		if not await _frames.can_continue():
			return
		var mb := MeshBuilder.new()
		mb.xform = m.xform()
		glows.xform = mb.xform
		var pe := Layout.MARINA_PIER_END
		var hu := Layout.MARINA_HEAD_U
		var hh := Layout.MARINA_HEAD_HALF
		mb.box(Vector3(0, 2.25, (pe - 12.0) * 0.5), Vector3(5.4, 0.75, pe + 12.0), plank)
		var u := -3.0
		while u < pe:
			for side: float in [-1.0, 1.0]:
				mb.box(Vector3(side * 3.0, -3.9, u), Vector3(0.84, 12.9, 0.84), Models.WOOD)
			u += 10.5
		# The T-head, a little lower, its pilings standing proud.
		mb.box(Vector3(0, 1.5, hu), Vector3(hh * 2.0, 0.9, 6.0), float_col)
		mb.box(Vector3(0, 1.08, hu + 3.06), Vector3(hh * 2.0, 0.36, 0.24), Color(0.25, 0.25, 0.26))
		for v: float in [-hh + 0.9, -4.5, 4.5, hh - 0.9]:
			mb.cylinder(Vector3(v, -6.0, hu - 3.6), 0.6, 0.54, 10.8, 6, Models.WOOD, Color(0.4, 0.33, 0.27))
		for b in Layout.MARINA_BERTHS:
			# A cleat for each berth.
			mb.box(Vector3(m.berth_v(b), 2.1, hu + 2.25), Vector3(1.05, 0.3, 0.36), Color(0.3, 0.3, 0.32))
		for side: float in [-1.0, 1.0]:
			var post := Vector3(side * (hh - 0.9), 1.95, hu)
			mb.box(post + Vector3(0, 2.4, 0), Vector3(0.3, 4.8, 0.3), Color(0.25, 0.26, 0.28))
			var lamp := post + Vector3(0, 4.8, 0)
			Models.add_lantern(mb, lamp, GlowBuilder.WARM, 2.7)
			glows.glow(Models.lantern_glow_at(lamp, 2.7), GlowBuilder.WARM, 0.48, 4.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
			glows.pool(Vector3(side * (hh - 3.6), 1.98, hu), GlowBuilder.WARM, 9.0, 0.25)
			var top := mb.xform * (lamp + Vector3(0, 1.08, 0))
			_perch(top, top, 0.0, Seagulls.Kind.LAMP)
		_add_mesh(mb.commit(), map.islands[m.island].name + " Marina")
		_marina_restaurant(m)
		# Keep trees and houses off the pier's landing.
		var bu := -24.0
		while bu < 6.0:
			for bv: float in [-9.0, -4.5, 0.0, 4.5, 9.0]:
				_block(m.at(bu, bv), 3.0)
			bu += 4.5


## A timber jetty out to a wharf the boats lie alongside (the boats themselves
## are MarineTraffic's): bollards and tyre fenders along its face, and
## floodlights for working in the dark. A fish quay has a fish shed and stacked
## totes on it and a hoist over the water; the pilot station its pilot house,
## with a lookout and radar mast.
func _build_quays() -> void:
	var plank := Color(0.5, 0.42, 0.33)
	var cap := Color(0.6, 0.6, 0.57)
	var tyre := Color(0.1, 0.1, 0.11)
	var steel := Color(0.35, 0.36, 0.38)
	var r := RandomNumberGenerator.new()
	for q in map.wharves():
		if not await _frames.can_continue():
			return
		var fish := q is MapData.FishQuay
		r.seed = map.map_seed * 13 + q.id + (0 if fish else 7919)
		var mb := MeshBuilder.new()
		mb.xform = q.xform()
		glows.xform = mb.xform
		var deck := 3.6
		var face := Layout.QUAY_FACE_U
		var back := Layout.QUAY_JETTY_END - 6.0
		var hh := Layout.QUAY_HALF
		# The jetty, on its pilings.
		mb.box(Vector3(0, deck - 0.45, (back - 6.0) * 0.5), Vector3(12.0, 0.9, back + 6.0), plank)
		var u := 0.0
		while u < back:
			for side: float in [-5.4, 5.4]:
				mb.box(Vector3(side, -4.8, u), Vector3(0.9, 16.2, 0.9), Models.WOOD)
			u += 9.0
		# The wharf: a heavy timber deck with a concrete cap along its face.
		var mid := (back + face) * 0.5
		mb.box(Vector3(0, deck - 0.6, mid), Vector3(hh * 2.0, 1.2, face - back), plank)
		# The cap starts on the deck and the lower facing ends at its underside.
		# All three fronts share a plane, so their height bands must meet edge to edge.
		mb.box(Vector3(0, deck + 0.135, face - 1.05), Vector3(hh * 2.0, 0.27, 2.1), cap)
		mb.box(Vector3(0, deck - 2.85, face - 0.24), Vector3(hh * 2.0, 3.3, 0.48), Models.WOOD)
		var v := -hh + 1.2
		while v <= hh - 0.9:
			mb.box(Vector3(v, -5.4, face - 0.6), Vector3(1.08, 16.8, 1.08), Models.WOOD)
			mb.box(Vector3(v, -4.8, back + 0.9), Vector3(0.96, 16.2, 0.96), Models.WOOD)
			v += 9.6
		# Tyre fenders hung along the face, and bollards for the boats' lines.
		v = -hh + 4.5
		while v < hh - 3.0:
			mb.box(Vector3(v, 0.9, face + 0.36), Vector3(2.25, 2.25, 0.78), tyre)
			mb.box(Vector3(v, 0.9, face + 0.78), Vector3(1.2, 1.2, 0.12), Color(0.03, 0.03, 0.03))
			v += 10.8 + r.randf() * 3.6
		var spread := (Layout.QUAY_BERTH_SPACING if fish else Layout.STATION_BERTH_SPACING) * 0.37
		for b in q.berths():
			for o: float in [-spread, 0.0, spread]:
				var bp := Vector3(q.berth_v(b) + o, deck + 0.27, face - 1.35)
				mb.cylinder(bp, 0.51, 0.45, 1.2, 8, Color(0.16, 0.17, 0.18))
				mb.cylinder(bp + Vector3(0, 1.2, 0), 0.72, 0.72, 0.21, 8, Color(0.16, 0.17, 0.18))
		if fish:
			_fish_quay_props(mb, q, r, deck, back, face, hh)
		else:
			_pilot_station_props(mb, q, r, deck, back, face, hh)
		# Floodlights on poles, lighting the wharf and the boats alongside (at the
		# pilot station, only at the end away from the pilot house).
		for fv: float in [-hh + 12.0, hh - 12.0]:
			if not fish and signf(fv) == -q.side:
				continue
			var pole := Vector3(fv, deck, back + 1.8)
			mb.box(pole + Vector3(0, 10.5, 0), Vector3(0.6, 21.0, 0.6), steel)
			mb.box(pole + Vector3(0, 21.0, 0.9), Vector3(2.7, 1.05, 1.5), Color(0.25, 0.26, 0.27))
			mb.box(pole + Vector3(0, 20.58, 1.26), Vector3(2.25, 0.24, 0.9), Models.lamp_glass(GlowBuilder.LED))
			glows.glow(pole + Vector3(0, 20.55, 1.35), GlowBuilder.LED, 0.96, 7.0, true, 0.0, Vector3(0, 0, 1), Models.LAMP_ON_AT)
			glows.pool(Vector3(fv * 0.85, deck + 0.15, (back + face) * 0.5 + 3.0), GlowBuilder.LED, 22.5, 0.22)
			var top := mb.xform * (pole + Vector3(0, 21.6, 0.9))
			_perch(top, top, 0.0, Seagulls.Kind.LAMP)
		_perch(mb.xform * Vector3(-hh + 3.0, deck + 0.48, face - 1.05), mb.xform * Vector3(hh - 3.0, deck + 0.48, face - 1.05),
			0.0, Seagulls.Kind.DOLPHIN)
		_add_mesh(mb.commit(), q.title(map).capitalize())
		# Keep trees and houses off the wharf and the jetty's landing.
		var bu := -30.0
		while bu < face:
			var half := hh + 4.5 if bu >= back - 3.0 else 13.5
			var bv := -half
			while bv <= half:
				_block(q.at(bu, bv), 3.0)
				bv += 4.5
			bu += 4.5


## The fish shed at one end, its big door onto the wharf, totes stacked about,
## and a hoist for landing the catch.
func _fish_quay_props(mb: MeshBuilder, q: MapData.Wharf, r: RandomNumberGenerator, deck: float, back: float,
		face: float, hh: float) -> void:
	var shed_wall := Color(0.6, 0.24, 0.19)
	var trim := Color(0.9, 0.89, 0.84)
	var totes := [Color(0.18, 0.38, 0.66), Color(0.9, 0.48, 0.14), Color(0.86, 0.86, 0.82)]
	# The fish shed at one end, its big door onto the wharf.
	var sv := -q.side * (hh - 24.0)
	var sz := Vector3(33.0, 9.0, 13.8)
	var sc := Vector3(sv, deck + sz.y * 0.5, back + sz.z * 0.5 + 0.9)
	mb.box(sc, sz, shed_wall)
	mb.box(sc + Vector3(0, -1.05, sz.z * 0.5 + 0.03), Vector3(9.6, 6.9, 0.12), shed_wall.darkened(0.45))
	for wv: float in [-11.4, 11.4]:
		mb.box(sc + Vector3(wv, 1.2, sz.z * 0.5 + 0.03), Vector3(3.0, 2.1, 0.12), Models.WINDOW)
	mb.box(sc + Vector3(0, sz.y * 0.5 - 0.18, 0), Vector3(sz.x + 0.3, 0.36, sz.z + 0.3), trim)
	var ry := deck + sz.y
	var rx := sz.x * 0.5 + 0.75
	var rz := sz.z * 0.5 + 1.05
	var roof := Color(0.3, 0.31, 0.33)
	var l0 := sc + Vector3(-rx, ry - sc.y, -rz)
	var l1 := sc + Vector3(rx, ry - sc.y, -rz)
	var f0 := sc + Vector3(-rx, ry - sc.y, rz)
	var f1 := sc + Vector3(rx, ry - sc.y, rz)
	var t0 := sc + Vector3(-rx, ry - sc.y + 4.5, 0)
	var t1 := sc + Vector3(rx, ry - sc.y + 4.5, 0)
	mb.quad(l0, t0, t1, l1, roof, Vector3(0, 1, -1))
	mb.quad(f0, f1, t1, t0, roof, Vector3(0, 1, 1))
	mb.quad(l0, l1, f1, f0, roof.darkened(0.4), Vector3.DOWN)
	for e: float in [-1.0, 1.0]:
		var ex := sc.x + e * sz.x * 0.5
		mb.tri(Vector3(ex, ry, sc.z - sz.z * 0.5), Vector3(ex, ry, sc.z + sz.z * 0.5),
			Vector3(ex, ry + 4.2, sc.z), shed_wall, Vector3(e, 0, 0))
	_perch(mb.xform * Vector3(sc.x - rx + 1.8, ry + 4.5, sc.z), mb.xform * Vector3(sc.x + rx - 1.8, ry + 4.5, sc.z), 0.0, Seagulls.Kind.ROOF)
	# Fish totes stacked about the wharf.
	for k in 9:
		var tv := r.randf_range(-hh + 9.0, hh - 9.0)
		if absf(tv - sv) < sz.x * 0.5 + 4.5:
			continue
		var tu := r.randf_range(back + 3.0, face - 6.6)
		var high := r.randi_range(1, 4)
		var col: Color = totes[r.randi_range(0, totes.size() - 1)]
		for t in high:
			mb.box(Vector3(tv, deck + 0.9 + t * 1.65, tu), Vector3(3.6, 1.56, 2.4), col.darkened(r.randf() * 0.15))
	# A hoist for landing the catch, its boom out over the berths.
	var hv := q.side * 6.0
	mb.box(Vector3(hv, deck + 7.8, face - 3.6), Vector3(1.05, 15.6, 1.05), Color(0.85, 0.72, 0.18))
	var saved := mb.xform
	mb.xform = saved * Transform3D(Basis(Vector3.RIGHT, -0.55), Vector3(hv, deck + 1.0, face - 1.2))
	mb.box(Vector3(0, 0, 9.0), Vector3(0.72, 0.72, 19.2), Color(0.85, 0.72, 0.18))
	mb.xform = saved
	mb.box(Vector3(hv, deck + 8.4, face + 12.0), Vector3(0.09, 4.2, 0.09), Color(0.2, 0.2, 0.2))
	var hook := mb.xform * Vector3(hv, deck + 15.6, face - 3.6)
	_perch(hook, hook, 0.0, Seagulls.Kind.LAMP)


## The pilot house at one end of the wharf (where the pilots wait between ships
## and the boats' crews keep watch), a lookout mast with the radar and a
## windsock, a liferaft and lifebuoys.
func _pilot_station_props(mb: MeshBuilder, q: MapData.Wharf, _r: RandomNumberGenerator, deck: float, back: float,
		face: float, hh: float) -> void:
	var wall := Color(0.92, 0.91, 0.87)
	var band := Color(0.86, 0.33, 0.1)
	var roof := Color(0.22, 0.24, 0.27)
	var sv := -q.side * (hh - 21.0)
	var sz := Vector3(27.0, 16.8, 14.4)
	var sc := Vector3(sv, deck + sz.y * 0.5, back + sz.z * 0.5 + 0.9)
	mb.box(sc, sz, wall)
	# An orange band at the eaves and round the ground floor, windows all round,
	# the upper floor's the watch room.
	mb.box(sc + Vector3(0, sz.y * 0.5 - 0.9, 0), Vector3(sz.x + 0.18, 1.8, sz.z + 0.18), band)
	mb.box(sc + Vector3(0, -sz.y * 0.5 + 0.75, 0), Vector3(sz.x + 0.18, 1.5, sz.z + 0.18), band.darkened(0.2))
	mb.box(sc + Vector3(0, 3.6, 0), Vector3(sz.x + 0.12, 3.3, sz.z - 2.4), Models.WINDOW_LIT)
	mb.box(sc + Vector3(0, 3.6, 0), Vector3(sz.x - 2.4, 3.3, sz.z + 0.12), Models.WINDOW_LIT)
	for wv: float in [-7.8, 7.8]:
		mb.box(sc + Vector3(wv, -3.6, sz.z * 0.5 + 0.03), Vector3(4.2, 2.7, 0.12), Models.WINDOW)
	mb.box(sc + Vector3(0, -5.25, sz.z * 0.5 + 0.03), Vector3(3.3, 6.3, 0.12), band.darkened(0.45))
	# A flat roof with a rail, the mast on it.
	var ry := deck + sz.y
	mb.box(Vector3(sc.x, ry + 0.24, sc.z), Vector3(sz.x + 1.5, 0.48, sz.z + 1.5), roof)
	for e: float in [-1.0, 1.0]:
		mb.box(Vector3(sc.x, ry + 1.8, sc.z + e * (sz.z * 0.5 + 0.6)), Vector3(sz.x + 1.2, 0.18, 0.18), wall)
		mb.box(Vector3(sc.x + e * (sz.x * 0.5 + 0.6), ry + 1.8, sc.z), Vector3(0.18, 0.18, sz.z + 1.2), wall)
	var mast := Vector3(sc.x + q.side * 7.5, ry, sc.z)
	mb.box(mast + Vector3(0, 9.0, 0), Vector3(0.6, 18.0, 0.6), wall)
	mb.box(mast + Vector3(0, 13.8, 0), Vector3(4.8, 0.24, 0.24), wall)
	mb.box(mast + Vector3(0, 15.9, 0), Vector3(0.9, 0.9, 0.9), roof)
	mb.box(mast + Vector3(0, 16.65, 0), Vector3(7.2, 0.36, 1.05), wall)
	Models.add_lantern(mb, mast + Vector3(0, 18.0, 0), GlowBuilder.RED, 2.7)
	glows.glow(Models.lantern_glow_at(mast + Vector3(0, 18.0, 0), 2.7), GlowBuilder.RED, 0.48, 5.0, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	# The windsock, streaming off the yard.
	var sock := mast + Vector3(2.4, 13.8, 0)
	mb.box(sock + Vector3(1.35, -0.3, 0), Vector3(2.7, 0.9, 0.9), band)
	mb.box(sock + Vector3(3.3, -0.54, 0), Vector3(1.5, 0.6, 0.6), wall)
	var top := mb.xform * (mast + Vector3(0, 19.2, 0))
	_perch(top, top, 0.0, Seagulls.Kind.LAMP)
	_perch(mb.xform * Vector3(sc.x - sz.x * 0.5 + 1.5, ry + 0.6, sc.z), mb.xform * Vector3(sc.x + sz.x * 0.5 - 1.5, ry + 0.6, sc.z),
		0.0, Seagulls.Kind.ROOF)
	# A liferaft canister in its cradle and lifebuoys on posts along the face.
	var lr := Vector3(-sv * 0.35, deck + 1.2, back + 4.2)
	mb.box(lr, Vector3(4.8, 1.5, 2.7), Color(0.3, 0.32, 0.34))
	mb.cylinder(lr + Vector3(0, 0.75, 0), 1.2, 1.2, 1.5, 8, Color(0.95, 0.95, 0.93))
	for lv: float in [-hh * 0.5, hh * 0.5]:
		mb.box(Vector3(lv, deck + 1.8, face - 3.0), Vector3(0.36, 3.6, 0.36), Color(0.2, 0.2, 0.22))
		mb.box(Vector3(lv, deck + 3.0, face - 2.76), Vector3(2.1, 2.1, 0.3), band)
		mb.box(Vector3(lv, deck + 3.0, face - 2.7), Vector3(1.05, 1.05, 0.36), Color(0.2, 0.2, 0.22))


func _build_route_overlay() -> void:
	route_overlay = _add_mesh(_route_overlay_mesh(), "RouteOverlay", false)


## Redraws the dashes after a schedule change, for the routes now in service.
func rebuild_route_overlay() -> void:
	if route_overlay:
		route_overlay.mesh = _route_overlay_mesh()


func _route_overlay_mesh() -> Mesh:
	var mb := MeshBuilder.new()
	var col := Color(0.92, 0.96, 1.0, 0.1)
	for r in map.routes:
		if not r.in_service:
			continue
		var s := 42.0
		while s < r.length - 48.0:
			var a := r.curve.sample_baked(s)
			var b := r.curve.sample_baked(s + 7.2)
			var lat := (b - a).normalized().cross(Vector3.UP) * 0.75
			# High enough to clear the swell so waves don't swallow dashes.
			a.y = 2.4
			b.y = 2.4
			mb.quad(a - lat, a + lat, b + lat, b - lat, col, Vector3.UP)
			s += 16.5
	# Water is also transparent and both meshes sit centred on the origin, so depth
	# sorting between them flips with the camera. Force the overlay to draw after it.
	var mat := Models.unshaded_material()
	mat.render_priority = 5
	return mb.commit(mat)
