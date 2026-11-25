class_name FerryNetModel
extends RefCounted
## Builds one car-deck net to the width of its hull. FerryView positions the pair.

const ASSET := "res://assets/models/ferry_net_mid.glb"
const BAYS := [4, 5, 6]
const HEIGHT := 1.6
const ROPE := Color(0.7, 0.58, 0.38)
const POST := Color(0.88, 0.7, 0.12)

static var authored := (
	not "--classic-net" in OS.get_cmdline_user_args() and ResourceLoader.exists(ASSET)
)
static var _net_mat: ShaderMaterial


static func build(fc: FerryClass) -> ArrayMesh:
	if authored:
		return _authored_net(fc)
	var mb := MeshBuilder.new()
	var w := fc.net_half_w
	var y := Layout.DECK_Y
	for x: float in [-w / 3.0, w / 3.0]:
		mb.box(Vector3(x, y + HEIGHT * 0.5, 0), Vector3(0.15, HEIGHT, 0.15), POST)
	for f: float in [0.2, 0.46, 0.73, 0.95]:
		mb.box(Vector3(0, y + f * HEIGHT, 0), Vector3(2.0 * w, 0.06, 0.06), ROPE)
	var n := ceili(2.0 * w / 0.5)
	for i in range(1, n):
		mb.box(
			Vector3(lerpf(-w, w, i / float(n)), y + 0.575 * HEIGHT, 0),
			Vector3(0.06, 0.75 * HEIGHT, 0.06),
			ROPE
		)
	return mb.commit()


## Three bays across the deck, from a bracket on each wall to the posts at the
## thirds: the modelled width nearest a third of the deck's, stretched to fit. Each
## net vertex's alpha holds how freely it moves (1 - alpha / 2: 0 at the posts and
## walls and along the head rope's ends, most low in the middle of a bay), which
## net.gdshader scales by the wind. Posts and brackets keep alpha 1.
static func _authored_net(fc: FerryClass) -> ArrayMesh:
	var lib := ModelParts.library(ASSET)
	var k := FerryClass.MID_SCALE
	var w := fc.net_half_w
	var span := 2.0 * w / 3.0
	var bay_w: int = BAYS[0]
	for n: int in BAYS:
		if absf(n * k - span) < absf(bay_w * k - span):
			bay_w = n
	var bay: MeshBuilder = lib["bay%d" % bay_w]
	var mb := MeshBuilder.new()
	for b in 3:
		var x0 := -w + b * span
		var xf := Transform3D(
			Basis.from_scale(Vector3(span / bay_w, k, k)), Vector3(x0, Layout.DECK_Y, 0)
		)
		var start := mb.verts.size()
		mb.append_part(bay, xf)
		for i in range(start, mb.verts.size()):
			var u := clampf((mb.verts[i].x - x0) / span, 0.0, 1.0)
			var h := clampf((mb.verts[i].y - Layout.DECK_Y) / (HEIGHT * k), 0.0, 1.0)
			# Pinned at the ends; the head rope is slung taut, the foot slacker, the
			# belly a third of the way up freest.
			var free := sin(PI * u) * (0.35 + 0.65 * sin(PI * 0.75 * (1.0 - h)))
			var c := mb.colors[i]
			c.a = 1.0 - 0.5 * clampf(free, 0.0, 1.0)
			mb.colors[i] = c
	for x: float in [-w / 3.0, w / 3.0]:
		mb.append_part(
			lib["post"],
			Transform3D(Basis.from_scale(Vector3.ONE * k), Vector3(x, Layout.DECK_Y, 0))
		)
	# The brackets face in from the walls.
	for e: float in [-1.0, 1.0]:
		var basis := Basis(Vector3.UP, 0.0 if e < 0.0 else PI).scaled(Vector3.ONE * k)
		mb.append_part(lib["eye"], Transform3D(basis, Vector3(e * w, Layout.DECK_Y, 0)))
	if _net_mat == null:
		_net_mat = ShaderMaterial.new()
		_net_mat.shader = load("res://shaders/net.gdshader")
	var mesh := mb.commit(_net_mat)
	# The shadow and depth passes would draw it unmoved.
	mesh.shadow_mesh = null
	return mesh
