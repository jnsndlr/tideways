#!/bin/zsh
# Watch the tie-up slip move on a loop: Rhododendron backs out of her tie-up at
# Madrona Island, comes round into the working slip, sails a round trip, then lays
# up again, over and over. No clicking needed; the camera follows her.
cd "$(dirname "$0")"
/Applications/Godot.app/Contents/MacOS/Godot res://scenes/main_map.tscn -- --scenario=slip_move --shift-demo --time=13 "$@"
