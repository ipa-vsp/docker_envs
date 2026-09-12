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
    if os.environ.get('TEST_ISAACLAB'):
        print('ISAACLAB_DIR=/opt/IsaacLab')
    sys.exit(0)
if sys.argv[1:3] == ['container', 'inspect']:
    running = bool(os.environ.get('TEST_RUNNING'))
    print('running' if running else '')
    sys.exit(0 if running else 1)
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
            STAGES_ISAACLAB_OUTPUT_ROOT=str(self.temp / "lab output"),
            XDG_RUNTIME_DIR=str(self.temp / "runtime"),
        )
        for name in ("TEST_ISAAC", "TEST_ISAACLAB", "TEST_RUNNING", "TEST_DOCKER_EXIT", "DISPLAY"):
            self.env.pop(name, None)

    def launch(self, *args):
        return subprocess.run(
            ["bash", str(RUNNER), "-i", "test:runtime", *args],
            env=self.env,
            capture_output=True,
            text=True,
        )

    def run_launcher(self, *args, workspace=None, mode="-r"):
        workspace = workspace if workspace is not None else self.workspace
        return self.launch(mode, "-w", str(workspace), *args)

    def docker_args(self):
        return json.loads(self.log.read_text())

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
        # The Kit cache is scoped by the image's Isaac Sim version.
        self.assertTrue((self.temp / "isaac cache/cache/kit/test").is_dir())
        self.assertIn(
            "target=/opt/isaac-venv/lib/python3.12/site-packages/isaacsim/kit/cache",
            " ".join(args),
        )
        self.assertNotIn("--privileged", args)

    def test_isaaclab_outputs_persist_on_host(self):
        self.env["TEST_ISAACLAB"] = "1"
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.docker_args()
        for sub in ("logs", "data_storage"):
            host = self.temp / "lab output" / sub
            self.assertTrue(host.is_dir())
            self.assertIn(f"type=bind,source={host},target=/opt/IsaacLab/{sub}", args)
        # Kit-less Isaac Lab keeps GPU access explicit.
        self.assertNotIn("--gpus", args)

    def test_disabling_isaac_setup_skips_lab_outputs(self):
        self.env["TEST_ISAACLAB"] = "1"
        result = self.run_launcher("-X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("/opt/IsaacLab/logs", " ".join(self.docker_args()))
        self.assertFalse((self.temp / "lab output").exists())

    def test_host_network_is_opt_in(self):
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertNotIn("--network", self.docker_args())
        self.assertEqual(self.run_launcher("-H").returncode, 0)
        args = self.docker_args()
        self.assertEqual(args[args.index("--network") + 1], "host")
        self.assertEqual(args[args.index("--ipc") + 1], "host")

    def test_exactly_one_mode(self):
        for modes in ((), ("-r", "-S"), ("-S", "-K"), ("-b", "-E")):
            with self.subTest(modes=modes):
                result = self.launch(*modes, "-w", str(self.workspace))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_start_detaches_with_run_arguments(self):
        result = self.run_launcher("-g", mode="-S")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.docker_args()
        self.assertEqual(args[:3], ["run", "-d", "--init"])
        self.assertNotIn("-it", args)
        self.assertEqual(args[-3:], ["test:runtime", "sleep", "infinity"])
        self.assertIn("--rm", args)
        self.assertEqual(args[args.index("--name") + 1], "test_runtime_container")
        self.assertEqual(args[args.index("--user") + 1], f"{os.getuid()}:{os.getgid()}")
        self.assertIn(f"type=bind,source={self.workspace},target=/home/admin/colcon_ws", args)
        self.assertEqual(args.count("--gpus"), 1)
        self.assertIn(" -E -i test:runtime", result.stdout)

    def test_start_is_idempotent(self):
        self.env["TEST_RUNNING"] = "1"
        result = self.run_launcher(mode="-S")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already running", result.stdout)
        self.assertFalse(self.log.exists())

    def test_start_requires_existing_workspace(self):
        result = self.run_launcher(mode="-S", workspace=self.temp / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_enter_opens_shell_through_entrypoint(self):
        self.env["TEST_RUNNING"] = "1"
        result = self.launch("-E", "-n", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.docker_args()
        self.assertEqual(args[:2], ["exec", "-it"])
        self.assertEqual(args[args.index("--workdir") + 1], "/home/dev/colcon_ws")
        self.assertEqual(
            args[-3:],
            ["test_runtime_container", "/usr/local/bin/scripts/workspace-entrypoint.sh", "bash"],
        )

    def test_enter_and_stop_need_a_running_container(self):
        result = self.launch("-E")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not running", result.stderr)
        result = self.launch("-K")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log.exists())

    def test_stop_running_container(self):
        self.env["TEST_RUNNING"] = "1"
        result = self.launch("-K", "-C", "my-box")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.docker_args(), ["stop", "my-box"])

    def test_container_name_override(self):
        result = self.run_launcher("-C", "isaac.dev-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.docker_args()
        self.assertEqual(args[args.index("--name") + 1], "isaac.dev-1")
        self.log.unlink()
        self.assertNotEqual(self.run_launcher("-C", "bad name").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_x11_wildcard_cookie_directory(self):
        xauth = self.temp / "xauth"
        xauth.write_text("""#!/usr/bin/env python3
import sys
if sys.argv[1] == 'nlist':
    print('0100 0004 7f000001 0001 30 0012 4d49542d4d414749432d434f4f4b49452d31 0004 abcd')
else:
    with open(sys.argv[sys.argv.index('-f') + 1], 'w') as f:
        f.write(sys.stdin.read())
""")
        xauth.chmod(0o755)
        self.env["DISPLAY"] = ":0"
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        cookie_dir = self.temp / "runtime" / f"docker-envs-xauth-{os.getuid()}"
        self.assertTrue((cookie_dir / "xauth").read_text().startswith("ffff 0004 7f000001"))
        self.assertEqual(cookie_dir.stat().st_mode & 0o777, 0o700)
        args = self.docker_args()
        self.assertIn(
            f"type=bind,source={cookie_dir},target=/tmp/docker-envs-xauth,readonly", args
        )
        self.assertIn("XAUTHORITY=/tmp/docker-envs-xauth/xauth", args)


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
