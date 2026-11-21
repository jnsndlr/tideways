#!/usr/bin/env bash
# Record one seeded player-camera view on a connected iPad with a playtest app installed.
set -euo pipefail
if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "Usage: $0 DEVICE BUNDLE_ID grass|terminal|follow NEW_OUTPUT_DIR [PROCESS_NAME]" >&2
  exit 2
fi
device=$1
bundle=$2
camera=$3
out=$4
process=${5:-Tideways}
duration=20
case "$camera" in
  grass) args=(--cam=1386,-2524.5,130,118.65,20.05 --speed=0) ;;
  terminal) args=(--cam=-422.47,-454.07,260,100,32 --speed=0) ;;
  follow) args=(--follow=0 --speed=1); duration=90 ;;
  *) echo "Unknown camera: $camera" >&2; exit 2 ;;
esac

# A fresh directory preserves earlier recordings, and a unique device screenshot
# confirms that this launch finished loading its map before the trace starts.
mkdir -- "$out"
shot="frame-probe-$(uuidgen).png"
printf '%s\n' "bundle=$bundle" "seed=123" "time=11" "camera=$camera" "arguments=${args[*]}" \
  "duration_seconds=$duration" "build_ref=${BUILD_REF:-unspecified}" > "$out/run.txt"
xcodebuild -version >> "$out/run.txt"
xcrun devicectl device process launch --device "$device" --terminate-existing "$bundle" \
  -- -- --seed=123 --time=11 "${args[@]}" "--shot=user://$shot" --shot-delay=5

return_to_menu() {
  local status=$?
  trap - EXIT
  xcrun devicectl device process launch --device "$device" --terminate-existing "$bundle" || status=1
  exit "$status"
}
trap return_to_menu EXIT

ready=false
for ((attempt=0; attempt<45; attempt++)); do
  sleep 2
  if xcrun devicectl device copy from --device "$device" --domain-type appDataContainer \
      --domain-identifier "$bundle" --source "Documents/$shot" --destination "$out/camera.png" \
      > "$out/copy.log" 2>&1 && [[ -s "$out/camera.png" ]]; then
    ready=true
    break
  fi
done
if [[ $ready != true ]]; then
  cat "$out/copy.log" >&2
  echo "The game did not produce its camera capture." >&2
  exit 1
fi

xcrun xctrace record --template 'Game Performance Overview' --device "$device" \
  --all-processes --time-limit "${duration}s" --output "$out/game.trace" --no-prompt
python3 "$(dirname "$0")/ipad_frame_report.py" "$out/game.trace" --process "$process" | tee "$out/frames.csv"
