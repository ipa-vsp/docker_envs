"""Exercise runtime arguments and startup behavior without requiring Docker."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "creator/scripts/run_env.sh"
ENTRYPOINT = ROOT / "creator/scripts/workspace-entrypoint.sh"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.temp = Path(self.directory.name)
        self.workspace = self.temp / "workspace with spaces"
        self.workspace.mkdir()
        self.log = self.temp / "docker.json"
        docker = self.temp / "docker"
        docker.write_text("""#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:3] == ['image', 'inspect']:
    if os.environ.get('TEST_ISAAC'):
        print('ISAACSIM_VERSION=test')
        print('ISAACSIM_ROOT=/opt/isaac-venv/lib/python3.12/site-packages/isaacsim')
    sys.exit(0)
with open(os.environ['RUNTIME_TEST_LOG'], 'w') as f:
    json.dump(sys.argv[1:], f)
sys.exit(int(os.environ.get('TEST_DOCKER_EXIT', '0')))
""")
        docker.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=f"{self.temp}:{os.environ['PATH']}",
            RUNTIME_TEST_LOG=str(self.log),
            STAGES_ISAAC_CACHE_ROOT=str(self.temp / "isaac cache"),
        )
        self.env.pop("TEST_ISAAC", None)
        self.env.pop("TEST_DOCKER_EXIT", None)

    def run_launcher(self, *args, workspace=None):
        return subprocess.run(
            [
                "bash",
                str(RUNNER),
                "-r",
                "-i",
                "test:runtime",
                "-w",
                str(workspace if workspace is not None else self.workspace),
                *args,
            ],
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_default_identity_and_narrow_mount(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())
        self.assertNotIn("--privileged", args)
        self.assertEqual(args[args.index("--user") + 1], f"{os.getuid()}:{os.getgid()}")
        self.assertIn(f"type=bind,source={self.workspace},target=/home/admin/colcon_ws", args)
        self.assertIn("WORKSPACE_UMASK=0022", args)
        self.assertEqual(args[args.index("--workdir") + 1], "/home/admin/colcon_ws")

    def test_missing_workspace_is_not_created(self):
        missing = self.temp / "missing"
        result = self.run_launcher(workspace=missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(missing.exists())
        self.assertFalse(self.log.exists())

    def test_shared_group_device_and_explicit_privilege(self):
        result = self.run_launcher(
            "-a",
            "2000",
            "-a",
            "3000",
            "-M",
            "0002",
            "-d",
            "/dev/ttyUSB0",
            "-P",
            "-U",
            "12345",
            "-G",
            "23456",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())
        self.assertIn("12345:23456", args)
        self.assertEqual(args.count("--group-add"), 2)
        self.assertIn("2000", args)
        self.assertIn("3000", args)
        self.assertIn("WORKSPACE_UMASK=0002", args)
        self.assertIn("--privileged", args)
        self.assertEqual(args[args.index("--device") + 1], "/dev/ttyUSB0")

    def test_rejects_bad_identity_and_umask(self):
        for flag, value in (("-U", "admin"), ("-G", "group"), ("-a", "bad"), ("-M", "0082")):
            with self.subTest(flag=flag):
                self.assertNotEqual(self.run_launcher(flag, value).returncode, 0)
                self.assertFalse(self.log.exists())

    def test_preserves_docker_failure(self):
        self.env["TEST_DOCKER_EXIT"] = "23"
        self.assertEqual(self.run_launcher().returncode, 23)

    def test_isaac_cache_failure_prevents_launch(self):
        self.env["TEST_ISAAC"] = "1"
        cache = self.temp / "not-a-directory"
        cache.write_text("sentinel")
        self.env["STAGES_ISAAC_CACHE_ROOT"] = str(cache)
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertEqual(cache.read_text(), "sentinel")

    def test_isaac_creates_caches_and_adds_gpu_once(self):
        self.env["TEST_ISAAC"] = "1"
        result = self.run_launcher("-g")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())
        self.assertEqual(args.count("--gpus"), 1)
        self.assertTrue((self.temp / "isaac cache/cache/kit").is_dir())
        self.assertNotIn("--privileged", args)


class EntrypointTests(unittest.TestCase):
    def test_umask_exit_status_and_no_home_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            rc = temp / ".bashrc"
            rc.write_text("unchanged\n")
            env = dict(
                os.environ,
                HOME=directory,
                ROS_DISTRO="",
                RMW_IMPLEMENTATION="",
                WORKSPACE_UMASK="0002",
            )
            for _ in range(2):
                result = subprocess.run(
                    [
                        "bash",
                        str(ENTRYPOINT),
                        "bash",
                        "-c",
                        'touch "$HOME/output"; mkdir -p "$HOME/directory"; exit 23',
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 23, result.stderr)
            self.assertEqual((temp / "output").stat().st_mode & 0o777, 0o664)
            self.assertEqual((temp / "directory").stat().st_mode & 0o777, 0o775)
            self.assertEqual(rc.read_text(), "unchanged\n")
            self.assertEqual({p.name for p in temp.iterdir()}, {".bashrc", "output", "directory"})

    def test_invalid_umask_does_not_execute_command(self):
        result = subprocess.run(
            ["bash", str(ENTRYPOINT), "echo", "should not execute"],
            env=dict(os.environ, WORKSPACE_UMASK="invalid"),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("should not execute", result.stdout)
