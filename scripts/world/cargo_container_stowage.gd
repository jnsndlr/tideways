class_name CargoContainerStowage
extends RefCounted
## Builds seeded stacks of containers from the authored box library.

const MID_CARGO_LINE_WEIGHTS := [1.0, 1.0, 1.0, 1.0, 0.8, 0.8, 0.7, 0.7, 0.9, 0.6, 0.5]


## Stows the deck cargo for `variant`: in each of the three hatches, each row takes a
## stack of forty-footers or two of twenty-footers; how high is picked per hatch and
## varied per stack. Only the sides and roofs not hidden by a neighbour are built.
static func append(mb: MeshBuilder, lib: Dictionary, variant: int) -> void:
	var r := RandomNumberGenerator.new()
	r.seed = 7019 + variant * 131
	var lines: Array = CargoMidData.LINES
	# A feeder on charter carries mostly its charterer's boxes.
	var weights: Array = MID_CARGO_LINE_WEIGHTS.duplicate()
	weights[variant * 3 % 8] = 4.0
	var tiers_lo := 1 if variant % 3 != 1 else 2
	var tiers_hi := 3
	var cols := CargoMidData.COL_X.size()
	# Stacks: [hatch, column, half (-1: a forty-footer, 0/1: aft/fore twenty), tiers].
	var stacks: Array = []
	# occ[hatch][column][half][tier]: whether that twenty-foot space is filled.
	var occ := {}
	for h in CargoMidData.HATCH_Z.size():
		var base := r.randi_range(tiers_lo, tiers_hi)
		for c in cols:
			var forty := r.randf() < 0.6
			for half: int in [-1] if forty else [0, 1]:
				var t := clampi(base + r.randi_range(-1, 1) if r.randf() < 0.45 else base, 0, 3)
				# The outer rows forward sit a tier lower, for the bridge's view over the bow.
				if h == CargoMidData.HATCH_Z.size() - 1 and (c == 0 or c == cols - 1):
					t = mini(t, 2)
				stacks.append([h, c, half, t])
				for ti in t:
					for hh: int in [0, 1] if half < 0 else [half]:
						occ[Vector4i(h, c, hh, ti)] = true
	for st: Array in stacks:
		var h: int = st[0]
		var c: int = st[1]
		var half: int = st[2]
		var halves: Array = [0, 1] if half < 0 else [half]
		var z: float = (
			CargoMidData.HATCH_Z[h] + (0.0 if half < 0 else (half - 0.5) * CargoMidData.BAY_PITCH)
		)
		for ti in st[3]:
			var line: String = lines[_pick_weighted(weights, r)]
			var tag := "c20" if half >= 0 else "c40"
			if half < 0 and line in CargoMidData.REEFERS and r.randf() < 0.3:
				tag = "c40r"
			var key := tag + line
			var tint := Color.WHITE.darkened(r.randf() * 0.14)
			var at := Vector3(
				CargoMidData.COL_X[c], CargoMidData.COVER_TOP + ti * CargoMidData.CONTAINER_H, z
			)
			var doors_aft := r.randf() < 0.5
			var turn := Basis(Vector3.UP, PI)
			mb.append_part(
				lib[key + "body"], Transform3D(turn if doors_aft else Basis.IDENTITY, at), tint
			)
			if not _stowed(occ, h, c, halves, ti + 1):
				mb.append_part(lib[key + "roof"], Transform3D(Basis.IDENTITY, at), tint)
			# The +X side as modelled; turned round for the -X one.
			if c == cols - 1 or not _stowed(occ, h, c + 1, halves, ti):
				mb.append_part(lib[key + "side"], Transform3D(Basis.IDENTITY, at), tint)
			if c == 0 or not _stowed(occ, h, c - 1, halves, ti):
				mb.append_part(lib[key + "side"], Transform3D(turn, at), tint)


static func _stowed(occ: Dictionary, h: int, c: int, halves: Array, tier: int) -> bool:
	for hh: int in halves:
		if not occ.has(Vector4i(h, c, hh, tier)):
			return false
	return true


static func _pick_weighted(weights: Array, r: RandomNumberGenerator) -> int:
	var total := 0.0
	for w: float in weights:
		total += w
	var x := r.randf() * total
	for i in weights.size():
		x -= weights[i]
		if x <= 0.0:
			return i
	return weights.size() - 1
