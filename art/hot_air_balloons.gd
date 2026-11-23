extends RefCounted
## Tideways balloon models, in metres. All four share this silhouette and basket.
const GORES := 16
const AROUND := 48
const RINGS := 16
const SKIN_COUNT := 4
const SKIN_NAMES := ["Sunburst", "Harbor Flame", "Golden Crown", "Festival Ribbons"]
# Each row spans a sewn course. The column offset gives Festival its spiral.
static func panel_color(skin: int, row: float, column: float) -> Color:
	var gore := floori(column / 3.0)
	var course := floori(row)
	match skin:
		0: # Sunburst, paired vermilion and marigold gores with a bright shoulder.
			if course in [3, 12]: return Color("ffce74")
			if row < 3: return Color("923e36") if gore % 2 else Color("c97433")
			return Color("da493b") if (gore / 2) % 2 else Color("f6aa37")
		1: # Harbor Flame, ocean blue and a broad tangerine belt.
			if row < 4 or row >= 14: return Color("204866")
			if course in [6, 11]: return Color("ffd28a")
			if course in range(7, 11): return Color("e76535")
			return Color("168f97")
		2: # Golden Crown, gold points descending over a cobalt body.
			if row < 3: return Color("223858")
			var point := absf(3 - fposmod(column, 6))
			if row >= 9 + point: return Color("f4c04c")
			if row >= 8 + point: return Color("ffe096")
			return Color("325cad")
		_: # Festival Ribbons, broad diagonal streamers.
			var stripe := fposmod(column - row, 12)
			if stripe < 4: return Color("ed6772")
			if stripe == 4: return Color("ffd9a5")
			if stripe < 8: return Color("39b9b2")
			return Color("764aa1")

static var palette: Array[Color] = []

static func _set_uv(st: SurfaceTool, color: Color) -> void:
	var index := palette.find(color)
	if index == -1:
		index = palette.size()
		palette.append(color)
	st.set_uv(Vector2((index + 0.5) / 32.0, 0.5))

static func build(skin:int=0) -> MeshInstance3D:
	palette.clear()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# Rounded teardrop envelope: open narrow throat, broad high shoulder, domed cap.
	for ring in RINGS:
		for side in AROUND:
			var a := _point(float(ring)/RINGS,float(side)/AROUND)
			var b := _point(float(ring+1)/RINGS,float(side)/AROUND)
			var c := _point(float(ring)/RINGS,float(side+1)/AROUND)
			var d := _point(float(ring+1)/RINGS,float(side+1)/AROUND)
			# Follow the print boundary with the quad diagonal for crisp points and ribbons.
			var rising := skin == 3 or (skin == 2 and side % 6 >= 3)
			var first := panel_color(skin, ring+0.33, side+(0.67 if rising else 0.33))
			var second := panel_color(skin, ring+0.67, side+(0.33 if rising else 0.67))
			if (side / 3) % 2 == 1:
				first = first.darkened(0.045)
				second = second.darkened(0.045)
			if rising:
				_tri(st,a,c,d,first)
				if ring < RINGS - 1: _tri(st,a,d,b,second)
			else:
				_tri(st,a,c,b,first)
				if ring < RINGS - 1: _tri(st,c,d,b,second)
	st.generate_normals()
	_add_basket(st)
	var brass := Color("bb8749")
	var iron := Color("364549")
	# Padded uprights, overhead burner rack and four taut flying wires.
	for x in [-0.83, 0.83]:
		for z in [-0.54, 0.54]:
			var rack := Vector3(x * 0.86, 2.35, z * 0.9)
			_rod(st, Vector3(x, 1.12, z), rack, 0.065, iron)
			_rod(st, rack, Vector3(signf(x)*0.79, 3.56, signf(z)*0.53), 0.036, brass)
	for z in [-0.49, 0.49]:
		_box(st, Vector3(0,2.35,z), Vector3(1.51,0.09,0.08), iron)
	for x in [-0.31, 0.31]:
		_box(st, Vector3(x,2.35,0), Vector3(0.1,0.09,1.04), iron)
		_box(st, Vector3(x,2.47,0), Vector3(0.36,0.26,0.4), brass)
		_box(st, Vector3(x,2.62,0), Vector3(0.30,0.06,0.34), iron)
	var material := StandardMaterial3D.new()
	var colors := Image.create_empty(32, 1, false, Image.FORMAT_RGBA8)
	assert(palette.size() <= 32)
	for i in palette.size(): colors.set_pixel(i, 0, palette[i])
	material.albedo_texture = ImageTexture.create_from_image(colors)
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	material.roughness = 0.92
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	st.index()
	st.set_material(material)
	var result := MeshInstance3D.new()
	result.name = "EnvelopeAndBasket"
	result.mesh = st.commit()
	result.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return result

static func _point(t: float, fraction: float) -> Vector3:
	var theta := fraction*TAU
	var angle := lerpf(-1.43,PI/2.0,t)
	# Ellipsoidal upper dome: radial extent approaches the crown with a
	# horizontal tangent, rather than linearly tapering into a pointed cone.
	# Long lower skirt and short broad crown put the shoulder in the upper third.
	var radius := 8.0*cos(angle)*lerpf(0.82,1.0,smoothstep(-1.43,-0.15,angle))
	# Shallow inflated gores create fabric volume without faceted blockiness.
	radius *= 1.0+0.027*(1.0-cos(theta*GORES))
	var y := 15.3+(6.0 if angle >= 0.0 else 11.9)*sin(angle)
	return Vector3(cos(theta)*radius,y,sin(theta)*radius)

static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
	_set_uv(st,color)
	for p in [a,b,c]: st.add_vertex(p)

static func _box(st: SurfaceTool, center: Vector3, size: Vector3, color: Color) -> void:
	var mesh := BoxMesh.new()
	mesh.size = size
	var arrays := mesh.get_mesh_arrays()
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	for index in arrays[Mesh.ARRAY_INDEX]:
		_set_uv(st,color);st.set_normal(normals[index]);st.add_vertex(vertices[index]+center)

static func _rod(st: SurfaceTool, a: Vector3, b: Vector3, radius: float, color: Color) -> void:
	var axis := (b-a).normalized()
	var reference := Vector3.UP if absf(axis.y) < 0.9 else Vector3.RIGHT
	var side := axis.cross(reference).normalized()*radius
	var other := axis.cross(side)
	for i in 6:
		var u := side*cos(i*TAU/6)+other*sin(i*TAU/6)
		var v := side*cos((i+1)*TAU/6)+other*sin((i+1)*TAU/6)
		st.set_normal((u+v).normalized())
		_tri(st,a+u,b+u,a+v,color);_tri(st,a+v,b+u,b+v,color)

# Octagonal courses create clipped corners, a tapered tub and an open rolled rim.
static func _basket_loop(y: float, width: float, depth: float) -> PackedVector3Array:
	var cut := 0.18
	return PackedVector3Array([
		Vector3(width-cut,y,-depth), Vector3(width,y,-depth+cut),
		Vector3(width,y,depth-cut), Vector3(width-cut,y,depth),
		Vector3(-width+cut,y,depth), Vector3(-width,y,depth-cut),
		Vector3(-width,y,-depth+cut), Vector3(-width+cut,y,-depth)
	])

static func _course(st: SurfaceTool, base: PackedVector3Array, top: PackedVector3Array, color: Color) -> void:
	for i in base.size():
		var j := (i + 1) % base.size()
		st.set_normal((base[j]-base[i]).cross(top[i]-base[i]).normalized() * -1)
		_tri(st,base[i],base[j],top[i],color)
		_tri(st,base[j],top[j],top[i],color)

static func _add_basket(st: SurfaceTool) -> void:
	var foot := _basket_loop(0,0.84,0.57)
	var lip := _basket_loop(1.22,1.04,0.76)
	var inner := _basket_loop(1.22,0.94,0.66)
	_course(st,foot,lip,Color("a76d3e"))
	_course(st,lip,inner,Color("66422f"))
	_course(st,inner,_basket_loop(0.15,0.77,0.50),Color("815333"))
	_box(st,Vector3(0,0.09,0),Vector3(1.59,0.18,1.05),Color("865b3d"))
	for row in 6:
		var height := 0.12 + row * 0.19
		var course := _basket_loop(height,0.85+0.20*height/1.22,0.58+0.19*height/1.22)
		for i in course.size():
			_rod(st,course[i],course[(i+1)%8],0.028,Color("d1a067"))
	for i in lip.size():
		_rod(st,foot[i],lip[i],0.042,Color("815337"))
		_rod(st,lip[i],lip[(i+1)%8],0.078,Color("634332"))
