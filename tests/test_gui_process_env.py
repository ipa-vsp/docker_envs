"""External commands must use host libraries even inside a frozen application."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from docker_envs_gui.bridge import Bridge, BridgeError
from docker_envs_gui.process_env import host_environment


class HostEnvironmentTests(unittest.TestCase):
    def test_frozen_process_restores_original_path_without_mutating_parent(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(
            os.environ,
            {"LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/host"},
            clear=True,
        ):
            self.assertEqual(host_environment()["LD_LIBRARY_PATH"], "/host")
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/bundle")

    def test_frozen_process_removes_path_when_host_had_none(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/bundle"}, clear=True
        ):
            self.assertNotIn("LD_LIBRARY_PATH", host_environment())

    def test_source_process_keeps_user_library_path(self):
        with patch.object(sys, "frozen", False, create=True), patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/custom"}, clear=True
        ):
            self.assertEqual(host_environment()["LD_LIBRARY_PATH"], "/custom")

    def test_bridge_cannot_pass_bundle_libraries_to_shell_commands(self):
        # An invalid .so breaks any dynamically linked host command that inherits
        # this directory. query.sh invokes dirname before it can read defaults.
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "libc.so.6").write_text("not a shared library")
            with patch.object(sys, "frozen", True, create=True), patch.dict(
                os.environ, {"LD_LIBRARY_PATH": directory}
            ):
                defaults = Bridge(ROOT).defaults()
        self.assertIn("CUDA", defaults.fallbacks)
        self.assertIn("24.04", defaults.supported_os)

    def test_empty_defaults_are_reported_as_a_bridge_error(self):
        with patch.object(Bridge, "_run", return_value=[]):
            with self.assertRaisesRegex(BridgeError, "Cannot read stage defaults"):
                Bridge(ROOT).defaults()


if __name__ == "__main__":
    unittest.main()
