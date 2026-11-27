"""Exercise the optional NumPy map scan with true intersections and hidden surfaces."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("numpy"), "optional map audit uses NumPy")
class SurfaceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
        import map_surface_audit
        cls.audit = map_surface_audit
        sys.path.pop(0)

    def test_seams_and_exposure(self):
        np = self.audit.np
        top = np.array([[0, 0, 0], [30, 0, 0], [0, 0, 30]], dtype="<f4")
        side = np.array([[0, 0, 0], [0, 2, 0], [2, 0, 0]], dtype="<f4")
        faces = {
            "Deck": top, "Paint": top + [0, .001, 0],
            "Joined": top * [-1, 1, -1] + [30, 0, 30],  # shares only the diagonal
            "Above": top + [0, .005, 0], "Terrain_0_0": top + [45, 0, 0],
            "Apron": top + [45, 0, 0], "Opposite": (top + [45, 0, 0])[::-1],
            # One wall on each side of a cell boundary within tolerance.
            "Wall": side + [0, 2, 47.9995], "Fascia": side + [0, 2, 48.0005],
        }
        meshes, instances = [], []
        transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with (folder / "triangles.bin").open("wb") as data:
                for i, (name, vertices) in enumerate(faces.items()):
                    meshes.append({"index": i, "count": 3, "offset": data.tell()})
                    data.write(vertices.astype("<f4").tobytes())
                    instances.append({"mesh": i, "group": name, "path": name, "transform": transform})
            (folder / "map.json").write_text(json.dumps({
                "seed": 1, "skipped_nodes": {}, "meshes": meshes, "instances": instances,
            }))
            hits = self.audit.scan(folder)["candidate_groups"]
        self.assertEqual(set(hits), {"Deck / Paint", "Apron / Terrain", "Fascia / Wall"})
        self.assertEqual(hits["Deck / Paint"]["face_pairs"], 1)
        self.assertEqual(hits["Deck / Paint"]["covered_from_above"], 1)
        self.assertEqual(hits["Apron / Terrain"]["sky_open"], 1)
        self.assertAlmostEqual(hits["Apron / Terrain"]["max_area_m2"], 450)
        self.assertEqual(hits["Fascia / Wall"]["open_from_side"], 1)
