"""Run the vehicle-overlap probe with bounded Godot console and engine logs."""

import argparse
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile


def run_probe(engine, script, arguments, *, timeout=600, log_limit=8 * 1024 * 1024):
    # Enforce the limit in Godot itself, including its independent engine log.
    inherited, _ = resource.getrlimit(resource.RLIMIT_FSIZE)
    if inherited != resource.RLIM_INFINITY:
        log_limit = min(log_limit, inherited)

    def limit_files():
        resource.setrlimit(resource.RLIMIT_FSIZE, (log_limit, log_limit))

    with tempfile.TemporaryDirectory(prefix="tideways-road-") as directory:
        engine_log = Path(directory) / "engine.log"
        command = [
            engine, "--headless", "--path", ".", "--log-file", str(engine_log),
            "--fixed-fps", "30", "--script", script, "--", "--verify", *arguments,
        ]
        with tempfile.TemporaryFile() as console:
            try:
                result = subprocess.run(
                    command, stdout=console, stderr=subprocess.STDOUT,
                    timeout=timeout, preexec_fn=limit_files,
                )
            except subprocess.TimeoutExpired:
                print(f"Road traffic timed out after {timeout} seconds.", file=sys.stderr)
                result = None
            capped = console.seek(0, os.SEEK_END) >= log_limit or (
                engine_log.exists() and engine_log.stat().st_size >= log_limit
            )
            console.seek(0)
            if capped:
                # Keep the first errors without copying a full log into CI or the terminal.
                sys.stdout.buffer.write(console.read(4096))
                print(f"Road traffic reached its {log_limit}-byte log limit.", file=sys.stderr)
                return 1
            shutil.copyfileobj(console, sys.stdout.buffer)
            sys.stdout.buffer.flush()
            if result is None or result.returncode != 0:
                return 1
            console.seek(0)
            checker = Path(__file__).with_name("godot_result.awk")
            return subprocess.run(
                ["awk", "-v", "phase=road-traffic", "-v", "expected=test", "-f", checker],
                stdin=console,
            ).returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", default="tests/traffic/vehicle_overlap_test.gd")
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help="Probe arguments after --")
    options = parser.parse_args()
    arguments = options.arguments
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    sys.exit(run_probe(os.environ.get("GODOT_BIN", "godot"), options.script, arguments))
