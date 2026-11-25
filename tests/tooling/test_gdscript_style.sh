#!/usr/bin/env bash
# Exercise the same Git comparison and pinned tools used for pull requests.
set -euo pipefail
checker="$(cd "$(dirname "$0")/../../tools" && pwd)/check_gdscript.py"
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
cd "$fixture"
git init --quiet
printf 'extends Node\n\n\nfunc legacy():\n\tvar BadName=1\n' > sample.gd
write_chooser() {
  printf 'extends Node\n\n\nfunc choose(value: int) -> int:\n'
  for ((i=1; i<=$1; i++)); do
    printf '\tif value == %s:\n\t\treturn %s\n' "$i" "$i"
  done
  printf '\treturn 0\n'
}
write_chooser 5 > chooser.gd
git add sample.gd chooser.gd
git -c user.name=Fixture -c user.email=fixture@example.invalid commit --quiet -m baseline
check() { uv run --locked --script "$checker" --base HEAD; }

printf '\n\nfunc added() -> int:\n\treturn 1\n' >> sample.gd
check
write_chooser 6 > chooser.gd
printf 'extends Node\n\n\nfunc new_rule():\n\tvar BadName=1\n' > new_rule.gd
if check > output; then
  echo "New lint and formatting violations were accepted" >&2
  exit 1
fi
grep -F 'max-returns' output
grep -F 'function-variable-name' output
grep -F 'gdformat expects different formatting' output
