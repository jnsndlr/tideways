class_name LandDistanceField
extends RefCounted


## Chamfer distance (in metres) from every cell of an `n` × `n` grid of `cell`-metre
## cells to the nearest land cell. Returns an empty array if `should_stop` says so.
static func compute(land: PackedByteArray, n: int, cell: float, should_stop := Callable()) -> PackedFloat32Array:
	var d := PackedFloat32Array()
	d.resize(n * n)
	for k in n * n:
		d[k] = 0.0 if land[k] == 1 else INF
	var o := cell
	var dg := cell * sqrt(2.0)
	for j in n:
		if should_stop.is_valid() and should_stop.call():
			return PackedFloat32Array()
		for i in n:
			var k := j * n + i
			var v := d[k]
			if i > 0:
				v = minf(v, d[k - 1] + o)
			if j > 0:
				v = minf(v, d[k - n] + o)
				if i > 0:
					v = minf(v, d[k - n - 1] + dg)
				if i < n - 1:
					v = minf(v, d[k - n + 1] + dg)
			d[k] = v
	for j in range(n - 1, -1, -1):
		if should_stop.is_valid() and should_stop.call():
			return PackedFloat32Array()
		for i in range(n - 1, -1, -1):
			var k := j * n + i
			var v := d[k]
			if i < n - 1:
				v = minf(v, d[k + 1] + o)
			if j < n - 1:
				v = minf(v, d[k + n] + o)
				if i < n - 1:
					v = minf(v, d[k + n + 1] + dg)
				if i > 0:
					v = minf(v, d[k + n - 1] + dg)
			d[k] = v
	return d
