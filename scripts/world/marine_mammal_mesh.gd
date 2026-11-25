class_name MarineMammalMesh
extends RefCounted
## Shared geometry for procedural whales, porpoises and pinnipeds.


## A whale or porpoise one unit long (+Z forward, nose at z = 0.5), built like
## the orca for cetacean.gdshader (Cetaceans scales each to its length): rings
## of 8 facets through the stations in `st` ([z, half-width, half-height, centre
## height] nose to tail), each facet coloured by `paint`(station, band, facet)
## where band 0 is the back and 3 the belly.
static func body(mb: MeshBuilder, st: Array, paint: Callable) -> void:
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
static func dorsal_fin(
	mb: MeshBuilder, front: float, back: float, y: float, base: Color, tip: Color
) -> void:
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
static func flukes(
	mb: MeshBuilder, root: float, span: float, tip_z: float, top: Color, under: Color
) -> void:
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
static func flipper(
	mb: MeshBuilder, root: Vector3, tip: Vector3, chord: float, top: Color, under: Color
) -> void:
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


static func spots(i: int, k: int, salt: float) -> float:
	return fposmod(sin(i * 12.9898 + k * 78.233 + salt) * 43758.5453, 1.0)
