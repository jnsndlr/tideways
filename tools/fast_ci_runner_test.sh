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
  early-exit) exit 0 ;;
  script-error) printf '\033[31mSCRIPT ERROR: Assertion failed.\033[0m\n' ;;
  leaked) echo 'WARNING: 1 ObjectDB instances were leaked at exit' ;;
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
for outcome in early-exit script-error leaked process-failure; do
  if OUTCOME="$outcome" GODOT_BIN="$fixture/engine" bash tools/fast_ci.sh > "$fixture/result" 2>&1; then
    echo "Runner accepted $outcome" >&2
    exit 1
  fi
done
echo "Runner detects incomplete tests, script errors, leaks and process failures."
