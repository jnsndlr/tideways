# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["gdtoolkit==4.5.0"]
# ///
"""Report GDScript style violations on changed lines without rewriting files."""

import argparse
import os
import subprocess
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from gdtoolkit.formatter import format_code
from gdtoolkit.linter import lint_code
from lark.exceptions import UnexpectedInput


def git(*args):
    return subprocess.check_output(["git", *args])


def changed_scripts(base):
    fields = iter(git("diff", "--name-status", "-z", "-M", "--diff-filter=AMRT",
                      base, "--", "*.gd").split(b"\0")[:-1])
    for status in fields:
        first = os.fsdecode(next(fields))
        current = os.fsdecode(next(fields)) if status.startswith(b"R") else first
        before = "" if status == b"A" else git("show", f"{base}:{first}").decode()
        yield Path(current), before
    for path in git("ls-files", "-z", "--others", "--exclude-standard", "--", "*.gd").split(b"\0")[:-1]:
        yield Path(os.fsdecode(path)), ""


def edits(before, after):
    return [op for op in SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
            if op[0] != "equal"]


def check_file(path, before):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    changes = edits(before.splitlines(keepends=True), lines)
    if not changes:
        return []
    changed = {i for _, _, _, start, end in changes for i in range(start, end)}
    # Removing a required blank line can create a formatting fault at a seam
    # even when the lines on either side were untouched.
    seams = {start for _, _, _, start, end in changes if start == end}
    findings = []
    try:
        problems = lint_code(source)
        formatted = format_code(source, max_line_length=100)
    except UnexpectedInput as error:
        return [f"{path}:{error.line}: GDScript parser: {error.get_context(source).strip()}"]
    # Some rules report on the declaration, although edits inside its body
    # caused the warning (e.g. too many return statements).
    try:
        previous = Counter((p.name, p.description) for p in lint_code(before)) if before else Counter()
    except UnexpectedInput:
        # A change can repair old syntax that this toolkit could not parse.
        previous = Counter((p.name, p.description) for p in problems)
    for problem in problems:
        key = (problem.name, problem.description)
        if problem.line - 1 in changed or previous[key] <= 0:
            findings.append(f"{path}:{problem.line}: {problem.description} ({problem.name})")
        previous[key] -= 1
    for _, start, end, _, _ in edits(lines, formatted.splitlines(keepends=True)):
        affected = any(i in changed for i in range(start, end))
        if start == end:
            affected = start in seams or start in changed or start - 1 in changed
        if affected:
            findings.append(f"{path}:{start + 1}: gdformat expects different formatting")
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="compare with the common ancestor of this revision and HEAD")
    args = parser.parse_args()
    os.chdir(os.fsdecode(git("rev-parse", "--show-toplevel")).strip())
    base = git("merge-base", args.base, "HEAD").decode().strip()
    findings = []
    for path, before in changed_scripts(base):
        findings.extend(check_file(path, before))
    for finding in findings:
        print(finding)
    print(f"GDScript style: {len(findings)} findings for this change")
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
