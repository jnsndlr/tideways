"""Check direct project-script dependencies from region data and simulation."""
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tools/layer_dependencies.txt"
FORBIDDEN = {"map": {"sim", "world"}, "sim": {"world"}}
# Keep strings intact so class names inside labels and comments are ignored.
TOKEN = re.compile(r"""\#[^\n]*|'''[\s\S]*?'''|""" + '"""[\\s\\S]*?"""' +
                   r"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[A-Za-z_]\w*|[^\s]""")


def inventory(root):
    sources = {}
    classes = {}
    for path in sorted((root / "scripts").rglob("*.gd")):
        name = path.relative_to(root).as_posix()
        tokens = [t for t in TOKEN.findall(path.read_text()) if not t.startswith("#")]
        sources[name] = tokens
        for i, token in enumerate(tokens[:-1]):
            if token == "class_name":
                classes[tokens[i + 1]] = name
    edges = set()
    for source, tokens in sources.items():
        forbidden = FORBIDDEN.get(source.split("/")[1], set())
        if not forbidden:
            continue
        for i, token in enumerate(tokens):
            target = classes.get(token)
            if token[:1] in ('"', "'") and token[1:-1].endswith(".gd"):
                path = token[1:-1]
                if path.startswith("res://"):
                    target = posixpath.normpath(path[6:])
                else:
                    call = tokens[max(0, i - 2):i]
                    if call not in (["preload", "("], ["load", "("]) and tokens[i - 1:i] != ["extends"]:
                        continue
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
            if target in sources and target.split("/")[1] in forbidden:
                edges.add(f"{source} -> {target}")
    return edges


def main():
    edges = inventory(ROOT)
    allowed = set(BASELINE.read_text().splitlines())
    for edge in sorted(edges - allowed):
        print(f"New forbidden dependency: {edge}")
    for edge in sorted(allowed - edges):
        print(f"Remove retired dependency from baseline: {edge}")
    print(f"{len(edges)} direct layer dependencies")
    return int(edges != allowed)


if __name__ == "__main__":
    sys.exit(main())
