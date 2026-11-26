import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.check_road_traffic import run_probe


class RoadTrafficLimitsTest(unittest.TestCase):
    def run_fake_engine(self, body, timeout=3):
        with tempfile.TemporaryDirectory() as directory:
            engine = Path(directory) / "fake-godot"
            engine.write_text(f"#!{sys.executable}\nimport os, sys, time\n{body}\n")
            engine.chmod(0o700)
            with patch("sys.stdout") as output, patch("sys.stderr", new_callable=io.StringIO) as errors:
                output.buffer = io.BytesIO()
                status = run_probe(str(engine), "fixture.gd", [], timeout=timeout, log_limit=8192)
                return status, output.buffer.getvalue(), errors.getvalue()

    def test_console_and_engine_log_are_bounded_independently(self):
        for destination in ["1", 'os.open(sys.argv[sys.argv.index("--log-file") + 1], os.O_CREAT | os.O_WRONLY)']:
            with self.subTest(destination=destination):
                status, output, error = self.run_fake_engine(
                    f"fd = {destination}\nos.write(fd, b'x' * 16384)\nprint('TEST PASSED')"
                )
                self.assertNotEqual(status, 0)
                self.assertIn("8192-byte log limit", error)
                self.assertLessEqual(len(output), 4096)

    def test_silent_hang_times_out(self):
        status, _, error = self.run_fake_engine("time.sleep(10)", timeout=0.25)
        self.assertNotEqual(status, 0)
        self.assertIn("timed out", error)
