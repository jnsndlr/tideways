extends RefCounted


## The hull's outline where it meets the water, as seen from above: the glTF part
## `part` (waterline at y = 0, z along its length) from its waterline up to `top`,
## taking in any flare or guard overhanging the water. Its half length, then `n`
## half-widths at stations evenly spaced from tip to tip (all model metres). Both
## ends are taken as the wider of the two, for double-enders.
static func measure(path: String, part: String, n: int, top: float) -> PackedFloat32Array:
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
	return out
