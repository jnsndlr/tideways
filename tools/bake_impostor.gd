extends SceneTree
## Bakes the 300-triangle pine's impostor (tree_impostor.gdshader) into
## Models.IMPOSTOR_DIR: the model drawn unlit and square on (orthographic) from every
## heading and height of Models' impostor layout, framed in the sphere round it.
##   lpine_albedo.res  rgb its vertex colours, a its coverage
##   lpine_normal.res  rgb its normals (model frame, 0.5 + n / 2), a its depth
## Each frame's empty texels take its average colour and normal, so the silhouette
## doesn't fringe dark as it's filtered and mipmapped.
##   godot --path . --rendering-driver vulkan --script tools/bake_impostor.gd -- [--preview=DIR]

var preview := ""


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--preview="):
			preview = a.substr(10)
	_bake.call_deferred()


func _bake() -> void:
	var base := Models.impostor_base()
	var mesh: ArrayMesh = base[0]
	var center: Vector3 = base[1]
	var radius: float = base[2]
	var F := Models.IMPOSTOR_FRAME
	var AZ := Models.IMPOSTOR_AZIMUTHS
	var EL := Models.IMPOSTOR_ELEVATIONS

	var vp := SubViewport.new()
	vp.size = Vector2i(F, F)
	vp.own_world_3d = true
	vp.transparent_bg = true
	vp.msaa_3d = Viewport.MSAA_DISABLED
	vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
	vp.use_taa = false
	vp.use_debanding = false
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/impostor_bake.gdshader")
	mat.set_shader_parameter("center", center)
	mat.set_shader_parameter("radius", radius)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	vp.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = radius * 2.0
	cam.near = 0.01
	cam.far = radius * 4.0
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	cam.environment = env
	vp.add_child(cam)
	cam.current = true

	var albedo := Image.create(F * AZ, F * EL, false, Image.FORMAT_RGBA8)
	var normal := Image.create(F * AZ, F * EL, false, Image.FORMAT_RGBA8)
	for j in EL:
		for i in AZ:
			var a := TAU * i / AZ
			var e := deg_to_rad(Models.IMPOSTOR_EL_STEP * j)
			var d := Vector3(cos(e) * cos(a), sin(e), cos(e) * sin(a))
			# Camera basis as the shader builds its card: x across, y up, z towards us.
			var x := Vector3.UP.cross(d).normalized()
			var y := d.cross(x)
			cam.transform = Transform3D(Basis(x, y, d), center + d * radius * 2.0)
			mat.set_shader_parameter("view_dir", d)
			var shots: Array[Image] = []
			for mode in 3:
				mat.set_shader_parameter("mode", mode)
				# One frame to take the change, one to draw it.
				await RenderingServer.frame_post_draw
				await RenderingServer.frame_post_draw
				var img := vp.get_texture().get_image()
				img.convert(Image.FORMAT_RGBA8)
				shots.append(img)
			_fill_frame(shots, albedo, normal, Vector2i(i * F, j * F))
	if preview != "":
		DirAccess.make_dir_recursive_absolute(preview)
		albedo.save_png(preview.path_join("lpine_albedo.png"))
		normal.save_png(preview.path_join("lpine_normal.png"))
	DirAccess.make_dir_recursive_absolute(Models.IMPOSTOR_DIR)
	for pair in [[albedo, "lpine_albedo.res"], [normal, "lpine_normal.res"]]:
		var img: Image = pair[0]
		img.generate_mipmaps()
		var err := ResourceSaver.save(ImageTexture.create_from_image(img), Models.IMPOSTOR_DIR + pair[1])
		print("bake_impostor: saved %s (%s)" % [pair[1], error_string(err)])
	quit()


## One frame's three passes into the atlases at `at`, its empty texels filled.
func _fill_frame(shots: Array[Image], albedo: Image, normal: Image, at: Vector2i) -> void:
	var col := shots[0]
	var nrm := shots[1]
	var dep := shots[2]
	var sum_c := Color(0, 0, 0, 0)
	var sum_n := Color(0, 0, 0, 0)
	var n := 0
	for y in col.get_height():
		for x in col.get_width():
			if col.get_pixel(x, y).a > 0.5:
				sum_c += col.get_pixel(x, y)
				sum_n += nrm.get_pixel(x, y)
				n += 1
	var avg_c := sum_c / maxf(n, 1)
	var avg_n := sum_n / maxf(n, 1)
	for y in col.get_height():
		for x in col.get_width():
			var c := col.get_pixel(x, y)
			if c.a > 0.5:
				albedo.set_pixel(at.x + x, at.y + y, Color(c.r, c.g, c.b, 1.0))
				var nn := nrm.get_pixel(x, y)
				normal.set_pixel(at.x + x, at.y + y, Color(nn.r, nn.g, nn.b, dep.get_pixel(x, y).r))
			else:
				albedo.set_pixel(at.x + x, at.y + y, Color(avg_c.r, avg_c.g, avg_c.b, 0.0))
				normal.set_pixel(at.x + x, at.y + y, Color(avg_n.r, avg_n.g, avg_n.b, 0.5))
