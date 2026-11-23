#!/usr/bin/env bash
# Launch the slip-move scenario. Pass --demo to follow repeated moves automatically.
set -euo pipefail
cd "$(dirname "$0")/.."
engine=${GODOT_BIN:-godot}
if [[ -z ${GODOT_BIN:-} ]] && ! command -v godot >/dev/null && [[ -x /Applications/Godot.app/Contents/MacOS/Godot ]]; then
  engine=/Applications/Godot.app/Contents/MacOS/Godot
fi
if [[ ${1:-} == --demo ]]; then
  shift
  set -- --shift-demo --time=13 "$@"
fi
exec "$engine" res://scenes/main_map.tscn -- --scenario=slip_move --select=1 "$@"
