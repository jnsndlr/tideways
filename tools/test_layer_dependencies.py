"""Exercise the dependency check against small GDScript fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from layer_dependencies import inventory


class LayerDependenciesTest(unittest.TestCase):
    def test_global_names_and_script_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = {
                "world/view.gd": "class_name ModelView",
                "world/parts.gd": "extends RefCounted",
                "sim/rules.gd": "class_name Rules\nvar view: ModelView",
                "map/data.gd": 'extends "../sim/rules.gd"\nconst P = preload("res://scripts/world/parts.gd")',
                "map/layout.gd": 'const P = preload("../world/parts.gd")',
                "map/clean.gd": '# Rules\nvar label = "ModelView"\nvar text = """\nRules\n"""',
            }
            for name, source in scripts.items():
                path = root / "scripts" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            self.assertEqual(inventory(root), {
                "scripts/map/data.gd -> scripts/sim/rules.gd",
                "scripts/map/data.gd -> scripts/world/parts.gd",
                "scripts/map/layout.gd -> scripts/world/parts.gd",
                "scripts/sim/rules.gd -> scripts/world/view.gd",
            })


if __name__ == "__main__":
    unittest.main()
