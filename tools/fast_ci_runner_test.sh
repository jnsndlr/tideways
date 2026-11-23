#!/usr/bin/env bash
# Exercise the gate itself without importing the game.
set -euo pipefail
cd "$(dirname "$0")/.."
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
cat > "$fixture/engine" <<'ENGINE'
#!/usr/bin/env bash
case " $* " in
  *" --script "*) ;;
  *) exit 0 ;;
esac
for arg in "$@"; do
  case "$arg" in
    tools/*_test.gd) echo "$arg" >> "$TEST_INVENTORY" ;;
  esac
done
case "$OUTCOME" in
  unrelated-load-error)
    if [[ " $* " == *" tools/region_load_recovery_test.gd "* ]]; then
      echo 'ERROR: Failed loading resource: res://scenes/main_map.tscn.'
    fi ;;
  early-exit) exit 0 ;;
  script-error) printf '\033[31mSCRIPT ERROR: Assertion failed.\033[0m\n' ;;
  one-leak) echo 'WARNING: 1 ObjectDB instance was leaked at exit (run with `--verbose` for details).' ;;
  multiple-leaks) echo 'WARNING: 2 ObjectDB instances were leaked at exit (run with `--verbose` for details).' ;;
  pass) echo 'WARNING: Cannot schedule Test ferry: no suitable slip for this leg' ;;
  process-failure) echo 'TEST PASSED'; exit 5 ;;
esac
echo 'TEST PASSED'
ENGINE
chmod +x "$fixture/engine"
export TEST_INVENTORY="$fixture/invoked"
for suite in fast traffic; do
  OUTCOME=pass GODOT_BIN="$fixture/engine" bash tools/fast_ci.sh "$suite" > "$fixture/control"
done
if ! diff -u <(printf '%s\n' tools/*_test.gd | LC_ALL=C sort) <(LC_ALL=C sort -u "$TEST_INVENTORY"); then
  echo "Every tools/*_test.gd should run in the fast or traffic suite." >&2
  exit 1
fi
for outcome in unrelated-load-error early-exit script-error one-leak multiple-leaks process-failure; do
  if OUTCOME="$outcome" GODOT_BIN="$fixture/engine" bash tools/fast_ci.sh > "$fixture/result" 2>&1; then
    echo "Runner accepted $outcome" >&2
    exit 1
  fi
done
echo "Runner detects incomplete tests, script errors, leaks and process failures."
