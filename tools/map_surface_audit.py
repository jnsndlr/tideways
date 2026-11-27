# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26,<3"]
# ///
"""Report co-facing, overlapping static map triangles. Requires NumPy.

Export in a rendered Godot 4.7.2 build (use --seed=123 instead of --scenario for Sandbox):
    godot --path . --resolution 320x180 --script tools/map_surface_export.gd -- --scenario=opening --out=/tmp/opening
Then: uv run --script tools/map_surface_audit.py /tmp/opening > opening-overlaps.json
A Python interpreter with NumPy installed can also run it directly.

A candidate is a pair of co-facing faces within 2 mm across their vertices,
with at least 0.1 square metres of shared area. Back-to-back contact and shared
edges are excluded. Each overlap samples its interior upwards or, for side
faces, at 35 degrees towards the outward side for 50 m. "Open" means no other
indexed front face blocks this sample; coverage is not a full pixel visibility test. This is a geometry inventory; an overlying roof, paint or
material may hide a hit. Terrain-to-terrain pairs, undersides, water, foliage,
runtime actors and (unless exported with --rocks) rock instances are outside the scan.
"""

import argparse
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit('map_surface_audit.py requires NumPy in the active Python environment')


CELL = 12.0
TOLERANCE = 0.002
MIN_AREA = 0.1


# Pair signed-grid coordinates into a sortable key, including negative cells.
def cell_key(x, z):
    return (x.astype(np.int64) << 32) | (z.astype(np.int64) & 0xFFFFFFFF)


def grid_entries(lower, upper, cell):
    """Emit a triangle index per grid cell touched by its bounding box."""
    lo = np.floor(lower[:, [0, 2]] / cell).astype(np.int32)
    hi = np.floor(upper[:, [0, 2]] / cell).astype(np.int32)
    extent = hi - lo + 1
    counts = extent[:, 0] * extent[:, 1]
    ids = np.repeat(np.arange(len(lo), dtype=np.int32), counts)
    index = np.arange(len(ids)) - np.repeat(np.cumsum(counts) - counts, counts)
    keys = cell_key(lo[ids, 0] + index // extent[ids, 1], lo[ids, 1] + index % extent[ids, 1])
    return ids, keys


def read_map(directory):
    manifest = json.loads((directory / "map.json").read_text())
    binary = np.memmap(directory / "triangles.bin", mode="r", dtype="<f4")
    triangles, sources, face_numbers = [], [], []
    instances = manifest["instances"]
    placed = 0
    # Keep terrain only in cells that contain other geometry. This prevents an
    # ocean floor or a remote highland from filling the fine-grained index.
    near = set()
    for terrain_pass in (False, True):
        near_keys = np.asarray(sorted(near), dtype=np.int64)
        for source, item in enumerate(instances):
            is_terrain = item["group"].startswith("Terrain_")
            if is_terrain != terrain_pass:
                continue
            mesh = manifest["meshes"][item["mesh"]]
            offset = mesh["offset"] // 4
            coords = binary[offset:offset + mesh["count"] * 3].reshape((-1, 3))
            transform = np.asarray(item["transform"], dtype=np.float32).reshape((4, 3))
            points = (coords @ transform[:3] + transform[3]).reshape((-1, 3, 3))
            placed += len(points)
            # Godot fronts are clockwise; negative cross-product points outward.
            normal = np.cross(points[:, 2] - points[:, 0], points[:, 1] - points[:, 0])
            lengths = np.linalg.norm(normal, axis=1)
            mask = (lengths >= 2 * MIN_AREA) & (normal[:, 1] >= -0.05 * lengths)
            original = np.flatnonzero(mask)
            kept = points[mask]
            if not len(kept):
                continue
            ids, keys = grid_entries(kept.min(axis=1) - TOLERANCE, kept.max(axis=1) + TOLERANCE, 64.0)
            if is_terrain:
                nearby = np.unique(ids[np.isin(keys, near_keys)])
                kept, original = kept[nearby], original[nearby]
            else:
                near.update(np.unique(keys).tolist())
            triangles.append(kept)
            sources.append(np.full(len(kept), source, dtype=np.int32))
            face_numbers.append(original.astype(np.int32))
    if not triangles:
        raise ValueError("No indexed triangles in the exported map")
    return manifest, placed, np.concatenate(triangles), np.concatenate(sources), np.concatenate(face_numbers)


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def overlap(a, b, normal):
    """Clip on the dominant 2D plane; return true 3D area in square metres."""
    axis = np.argmax(np.abs(normal))
    # Local coordinates keep small shared edges stable on distant islands.
    origin = a[0]
    a, b = a - origin, b - origin
    poly, clip = np.delete(a, axis, 1), np.delete(b, axis, 1)
    sign = 1 if cross2(clip[1] - clip[0], clip[2] - clip[0]) > 0 else -1
    for i in range(3):
        if not len(poly):
            return 0.0, None
        p, q = clip[i], clip[(i + 1) % 3]
        direction = q - p
        result = []
        prev = poly[-1]
        dp = sign * cross2(direction, prev - p)
        for current in poly:
            dc = sign * cross2(direction, current - p)
            if (dp >= 0) != (dc >= 0):
                result.append(prev + (current - prev) * (dp / (dp - dc)))
            if dc >= 0:
                result.append(current)
            prev, dp = current, dc
        poly = result
    if len(poly) < 3:
        return 0.0, None
    double_area = sum(cross2(poly[i] - poly[0], poly[i + 1] - poly[0]) for i in range(1, len(poly) - 1))
    area = abs(double_area) * 0.5 / abs(normal[axis])
    if area < MIN_AREA:
        return area, None
    # The mean of a convex polygon's vertices lies in the intersection.
    point = np.insert(np.mean(poly, axis=0), axis, 0.0)
    point[axis] = -np.dot(point, normal) / normal[axis]
    return area, origin + point


def sky_open(point, triangles):
    """Is there an indexed triangle above this world XZ point? No camera assumptions."""
    xz = triangles[:, :, ::2] - point[::2]
    # Barycentric weights obtained from three 2D cross products.
    next_vertex = np.roll(xz, -1, axis=1)
    weights = xz[:, :, 0] * next_vertex[:, :, 1] - xz[:, :, 1] * next_vertex[:, :, 0]
    inside = np.min(weights, axis=1) >= -1e-8
    inside |= np.max(weights, axis=1) <= 1e-8
    sums = weights.sum(axis=1)
    inside &= np.abs(sums) > 1e-8
    heights = np.sum(weights[inside] * triangles[inside][:, [2, 0, 1], 1], axis=1) / sums[inside]
    return not np.any(heights > point[1] + TOLERANCE)



def side_open(point, outward, tri, normal, entries, buckets):
    """Sample a 35-degree outward view, looking past up to 50 metres of scenery."""
    ray = np.array([outward[0], 0.7, outward[2]])
    ray /= np.linalg.norm(ray)
    distance = 50.0
    end = point + ray * distance
    lo = np.floor(np.minimum(point, end)[[0, 2]] / CELL).astype(np.int32)
    hi = np.floor(np.maximum(point, end)[[0, 2]] / CELL).astype(np.int32)
    ranges = []
    for x in range(lo[0], hi[0] + 1):
        for z in range(lo[1], hi[1] + 1):
            pair = buckets.get(cell_key(np.int64(x), np.int64(z)))
            if pair is not None:
                ranges.append(entries[pair[0]:pair[1]])
    ids = np.unique(np.concatenate(ranges))
    denominator = normal[ids] @ ray
    front = denominator > 1e-6
    ids, denominator = ids[front], denominator[front]
    delta = tri[ids, 0] - point
    t = np.einsum("ij,ij->i", normal[ids], delta) / denominator
    along = (t > 2 * TOLERANCE) & (t < distance)
    ids = ids[along]
    relative = tri[ids] - (point + t[along, None] * ray)[:, None]
    crosses = np.cross(relative, np.roll(relative, -1, axis=1))
    signed = np.einsum("ijk,ik->ij", crosses, normal[ids])
    return not np.any(np.max(signed, axis=1) <= 1e-8)


def candidates(ids, normal, lower, upper, groups, grid_key):
    structural = ids[~groups[ids]]
    # Work in bounded arrays for dense architectural meshes sharing one cell.
    for start in range(0, len(structural), 48):
        a = structural[start:start + 48]
        mask = (a[:, None] < ids) | groups[ids]
        for axis in range(3):
            mask &= lower[a, axis, None] <= upper[ids, axis] + TOLERANCE
            mask &= upper[a, axis, None] + TOLERANCE >= lower[ids, axis]
        ai, bi = np.nonzero(mask)
        first, second = a[ai], ids[bi]
        lo = np.maximum(lower[first], lower[second]) - TOLERANCE
        cells = np.floor(lo[:, [0, 2]] / CELL).astype(np.int32)
        keep = cell_key(cells[:, 0], cells[:, 1]) == grid_key
        keep &= np.einsum("ij,ij->i", normal[first], normal[second]) > 0.99999
        yield first[keep], second[keep]


def scan(directory):
    manifest, placed, tri, source, face = read_map(directory)
    lower, upper = tri.min(axis=1), tri.max(axis=1)
    normal = np.cross(tri[:, 2] - tri[:, 0], tri[:, 1] - tri[:, 0]).astype(np.float64)
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    instances = manifest["instances"]
    terrain = np.array([v["group"].startswith("Terrain_") for v in instances])[source]
    entries, keys = grid_entries(lower - TOLERANCE, upper + TOLERANCE, CELL)
    order = np.argsort(keys, kind="stable")
    keys, entries = keys[order], entries[order]
    boundaries = np.flatnonzero(keys[1:] != keys[:-1]) + 1
    results = {}
    buckets = {keys[start]: (start, stop) for start, stop in
               zip(np.r_[0, boundaries], np.r_[boundaries, len(keys)])}
    for start, stop in buckets.values():
        ids = entries[start:stop]
        if len(ids) < 2 or terrain[ids].all():
            continue
        for first, second in candidates(ids, normal, lower, upper, terrain, keys[start]):
            if not len(first):
                continue
            distances = np.einsum("ijk,ik->ij", tri[second] - tri[first, :1], normal[first])
            keep = np.max(np.abs(distances), axis=1) <= TOLERANCE
            distances = np.einsum("ijk,ik->ij", tri[first] - tri[second, :1], normal[second])
            keep &= np.max(np.abs(distances), axis=1) <= TOLERANCE
            for a, b in zip(first[keep], second[keep]):
                area, point = overlap(tri[a].astype(np.float64), tri[b].astype(np.float64), normal[a])
                if point is None:
                    continue
                rows = [instances[source[a]], instances[source[b]]]
                names = sorted("Terrain" if r["group"].startswith("Terrain_") else r["group"] for r in rows)
                group = " / ".join(names)
                hit = results.setdefault(group, {"face_pairs": 0, "max_area_m2": 0.0})
                hit["face_pairs"] += 1
                if normal[a, 1] > 0.1:
                    cell = np.floor(point[[0, 2]] / CELL).astype(np.int32)
                    begin, end = buckets[cell_key(*cell)]
                    exposure = "sky_open" if sky_open(point, tri[entries[begin:end]]) else "covered_from_above"
                else:
                    exposure = ("open_from_side" if side_open(point, normal[a], tri, normal, entries, buckets)
                                else "covered_from_side")
                hit[exposure] = hit.get(exposure, 0) + 1
                if exposure == "open_from_side" and area > hit.get("max_open_side_m2", 0):
                    hit.update(max_open_side_m2=area, side_point=np.round(point, 3).tolist(),
                               side_faces=[int(face[a]), int(face[b])], side_paths=[r["path"] for r in rows])
                if exposure == "sky_open" and area > hit.get("max_sky_open_m2", 0):
                    hit.update(max_sky_open_m2=area, open_point=np.round(point, 3).tolist(),
                               open_faces=[int(face[a]), int(face[b])], open_paths=[r["path"] for r in rows])
                if area > hit["max_area_m2"]:
                    hit.update(max_area_m2=area, paths=[r["path"] for r in rows],
                               faces=[int(face[a]), int(face[b])],
                               world_triangles=np.round(tri[[a, b]].astype(np.float64), 3).tolist())
    return {
        "seed": manifest["seed"], "scenario": manifest.get("scenario"), "placed_meshes": len(instances), "placed_triangles": placed,
        "triangles_in_index": len(tri), "skipped_nodes": manifest["skipped_nodes"],
        "candidate_groups": dict(sorted(results.items(), key=lambda hit: -hit[1]["max_area_m2"])),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(scan(parser.parse_args().directory), indent=2))
