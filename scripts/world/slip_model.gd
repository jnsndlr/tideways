class_name SlipModel
extends RefCounted
## Selects the terminal slip models and fits deck geometry to the road profile.

## The mid-poly slip (art/slip_mid.py): lattice lift towers with their header, sheaves
## and ladders (`towers`, static scenery in the slip frame) and the moving parts SlipRamp
## works: the transfer span, the apron, counterweights, hoist cables and the apron's
## rams. The old boxes are the fallback: with `--classic-slip`, or if the model is missing.
const SPAN_GLB := "res://assets/models/slip_mid.glb"

## The slip's guide structures, modelled in metres with the water at y = 0 and their
## fendered faces looking +Z: a six-pile dolphin for the lit outer pair, a four-pile
## one for the inner pair (art/ferry_dolphin*.blend) and the splayed wing wall
## (art/wing_wall.blend, art/export_wing_wall.py), the wall running along X. Their
## material colours are baked in (ModelParts.baked). The procedural piles and boxes are
## the fallback: with `--classic-slip`, or if a model is missing.
const OUTER_DOLPHIN_GLB := "res://assets/models/ferry_dolphin_lod.glb"
const INNER_DOLPHIN_GLB := "res://assets/models/ferry_dolphin_small_lod.glb"
const WING_WALL_GLB := "res://assets/models/wing_wall_lod.glb"

## The terminal trestle (art/trestle_mid.py): deck `bay`s and the `landing` onto the
## span's hinge, both built level and lifted onto the road's profile vertex by vertex
## (append_on_profile), the pile `bent`s under their joints, the `abutment` at the
## lot's edge and the `lamp` poles on the barrier. Without it the old flat pier stands.
const TRESTLE_GLB := "res://assets/models/trestle_mid.glb"

static var authored_span := (
	not "--classic-slip" in OS.get_cmdline_user_args() and ResourceLoader.exists(SPAN_GLB)
)
static var authored_guides := (
	not "--classic-slip" in OS.get_cmdline_user_args()
	and ResourceLoader.exists(OUTER_DOLPHIN_GLB)
	and ResourceLoader.exists(INNER_DOLPHIN_GLB)
	and ResourceLoader.exists(WING_WALL_GLB)
)
static var authored_trestle := authored_span and ResourceLoader.exists(TRESTLE_GLB)


## One part of the mid-poly slip, about its own pivot (see SlipRamp).
static func span_part(part: String) -> MeshBuilder:
	return ModelParts.library(SPAN_GLB)[part]


static func trestle_part(part: String) -> MeshBuilder:
	return ModelParts.library(TRESTLE_GLB)[part]


## Appends `part` at (v, 0, u) in the frame `xf` maps to the world, each vertex lifted by
## `height.call(u)` where it stands along u, so level-built deck parts follow a profile
## and neighbours meet exactly (verticals stay vertical; the grades are gentle enough
## to keep the normals).
static func append_on_profile(
	mb: MeshBuilder, part: MeshBuilder, xf: Transform3D, v: float, u: float, height: Callable
) -> void:
	var verts := PackedVector3Array()
	verts.resize(part.verts.size())
	for i in part.verts.size():
		var p := part.verts[i] + Vector3(v, 0.0, u)
		p.y += height.call(p.z)
		verts[i] = xf * p
	mb.verts.append_array(verts)
	mb.normals.append_array(Transform3D(xf.basis.orthonormalized(), Vector3.ZERO) * part.normals)
	mb.colors.append_array(part.colors)
