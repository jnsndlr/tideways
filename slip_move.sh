#!/bin/zsh
# Tie-up slip move test: Rhododendron starts laid up at Madrona Island's tie-up.
# Select her and Return to service to watch her back out and come round into the
# working slip; Lay up again to watch the way back. Camera starts on Madrona.
cd "$(dirname "$0")"
/Applications/Godot.app/Contents/MacOS/Godot res://scenes/main_map.tscn -- --scenario=slip_move --select=1 "$@"
