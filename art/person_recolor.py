"""Recolour tags for low-poly people (walk-on passengers).

The game swaps the colours of a few labelled parts per passenger so the same
model shows up with different hair, skin, clothes and accessories. This module
writes those labels into the mesh. Call it once in a person script, after
`mb.bm.to_mesh(me)` and before the GLB export:

    import person_recolor  # needs art/ on sys.path; see below
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

RECOLOR_GROUPS maps a part to the palette constants painted on it:

    RECOLOR_GROUPS = {
        "skin":   [SKIN, SKIN_SHADE],
        "hair":   [HAIR_DARK, HAIR_MID, BEARD],   # beards and brows count as hair
        "top":    [JACKET, JACKET_SHADE],         # the outermost upper garment
        "bottom": [PANTS, PANTS_SHADE],           # trousers, shorts, skirt, leggings
        "accent": [BEANIE, BEANIE_CUFF],          # one hat, bag, scarf or umbrella
    }

The FIRST colour in each list is the part's main colour. The other colours keep
their brightness relative to it, so shades and highlights survive the swap.
Leave out anything that should never change: eyes, glasses, logos, hi-vis,
tools and other props, and grey hair that must stay grey. Any part may be
omitted. Each colour may sit in one group only.

How it is stored: a second UV map named "Part" (TEXCOORD_1, UV2 in Godot).
U is the slot number (0 none, 1 skin, 2 hair, 3 top, 4 bottom, 5 accent).
V is the shade ratio against the group's main colour. If the mesh has no UV map
yet, an empty "UVMap" is added first so "Part" is always the second one.
"""

SLOTS = {"skin": 1, "hair": 2, "top": 3, "bottom": 4, "accent": 5}
_TOL = 1e-4


def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _same(a, b):
    return all(abs(a[i] - b[i]) < _TOL for i in range(3))


def _to_byte(c):
    """Rounds to the 8 bits a byte colour attribute keeps. The person scripts
    write their palette values straight into the byte layer, so compare the
    raw stored values (`color_srgb`), not the converted `color`."""
    return tuple(int(round(max(0.0, min(1.0, v)) * 255.0)) for v in c[:3])


def tag_parts(me, groups, color_name="Col"):
    """Writes the "Part" UV map on mesh `me` from `groups` (see module doc)."""
    table = []  # (rgb, slot, ratio)
    for part, colors in groups.items():
        if part not in SLOTS:
            raise ValueError(f"unknown recolour part {part!r}; use one of {list(SLOTS)}")
        if not colors:
            continue
        base = max(_lum(colors[0]), 1e-5)
        for c in colors:
            for other, slot, _ in table:
                if _same(other, c) and slot != SLOTS[part]:
                    raise ValueError(f"colour {tuple(c)} is in two recolour groups")
            table.append((tuple(c[:3]), SLOTS[part], _lum(c) / base))
    lookup = {}
    for rgb, slot, ratio in table:
        lookup.setdefault(_to_byte(rgb), (slot, ratio))

    if len(me.uv_layers) == 0:
        me.uv_layers.new(name="UVMap")
    part_uv = me.uv_layers.get("Part") or me.uv_layers.new(name="Part")
    col = me.color_attributes[color_name]
    if col.domain != "CORNER":
        raise ValueError("expected a per-corner colour attribute")

    counts = {}
    for i, loop_col in enumerate(col.data):
        slot, ratio = lookup.get(_to_byte(loop_col.color_srgb), (0, 1.0))
        part_uv.data[i].uv = (float(slot), ratio)
        counts[slot] = counts.get(slot, 0) + 1
    names = {v: k for k, v in SLOTS.items()}
    names[0] = "fixed"
    print("Recolour tags (corners):", {names[s]: n for s, n in sorted(counts.items())})
    return counts
