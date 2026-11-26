class_name CargoHullLettering
extends RefCounted
## Fits the vessel name to the bow and the name and port of registry to the transom.

const MID_CARGO_NAME_CAP := 0.8
const MID_CARGO_REGISTRIES := ["NASSAU", "MAJURO", "MONROVIA", "VALLETTA", "LIMASSOL"]


## The ship's name in white capitals on both bows and across the transom, the port of
## registry under it there; in the ship's frame, for the mid-poly container ship.
static func build(ship_name: String) -> ArrayMesh:
	var lib := ModelParts.library(CargoShipModel.CONTAINER_ASSET)
	var mb := MeshBuilder.new()
	var text := ship_name.to_upper()
	var cap := MID_CARGO_NAME_CAP
	# Down each bow from abaft the draft marks, where the bow is still fair, reading
	# left to right from outside: aft on the port (+X) side, forward on the starboard.
	var bow: Array = CargoMidData.BOW
	var width := _text_width(text) * cap * 1.06
	var fwd := bow.size() - 5
	for sx: float in [1.0, -1.0]:
		var pen := 0.0 if sx > 0.0 else -width
		for ch in text:
			var adv: float = CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "]) * cap * 1.06
			if lib.has("gl" + ch.to_lower()):
				# Distance aft of the forward end: walk the table to the glyph's middle.
				var d := absf(pen + adv * 0.5)
				var f := clampf(fwd - d / 0.4, 0.0, fwd - 0.001)
				var i := int(f)
				var a: Array = bow[i]
				var b: Array = bow[i + 1]
				var p: Vector3 = (a[0] as Vector3).lerp(b[0], f - i)
				var n: Vector3 = (a[1] as Vector3).lerp(b[1], f - i).normalized()
				p.x *= sx
				n.x *= sx
				var x := (Vector3(0, 0, -sx)).slide(n).normalized()
				var y := n.cross(x).normalized()
				x = y.cross(n)
				var o := p + n * 0.03 - x * adv * 0.5 / 1.06 - y * cap * 0.5
				mb.append_part(
					lib["gl" + ch.to_lower()], Transform3D(Basis(x * cap, y * cap, n * cap), o)
				)
			pen += adv
	# The transom, facing aft: the name, the port of registry smaller under it.
	var port: String = MID_CARGO_REGISTRIES[absi(hash(ship_name)) % MID_CARGO_REGISTRIES.size()]
	for row: Array in [[text, 0.62, 2.55], [port, 0.42, 1.65]]:
		var s: float = row[1]
		var w := _text_width(row[0]) * s * 1.06
		var pen := w * 0.5
		for ch: String in row[0]:
			var adv: float = CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "]) * s * 1.06
			if lib.has("gl" + ch.to_lower()):
				var o := Vector3(pen, row[2] - s * 0.5, CargoMidData.TRANSOM_Z - 0.03)
				mb.append_part(
					lib["gl" + ch.to_lower()],
					Transform3D(Basis(Vector3(-s, 0, 0), Vector3(0, s, 0), Vector3(0, 0, -s)), o)
				)
			pen -= adv
	return mb.commit()


static func _text_width(text: String) -> float:
	var w := 0.0
	for ch in text:
		w += CargoMidData.ADVANCE.get(ch, CargoMidData.ADVANCE[" "])
	return w
