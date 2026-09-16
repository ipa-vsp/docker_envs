"""Regression coverage for the two Isaac Lab source-installation paths."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PlanTests(unittest.TestCase):
    def test_mujoco_python_matches_later_isaac_layers(self):
        tags = []
        for sim, lab, python in (
            ("", "", "/usr/bin/python3"),
            ("4.5.0", "", "3.10"),
            ("5.1.0", "", "3.11"),
            ("6.1.0.0", "release/3.0.0", "3.12"),
            ("", "release/3.0.0", "3.12"),
        ):
            with self.subTest(sim=sim, lab=lab):
                result = subprocess.run(
                    [
                        "bash",
                        "-ec",
                        """
source "$1/creator/scripts/lib/stages.sh"
stages::init_selection
STAGES_MUJOCO=true
if [[ -n "$2" ]]; then STAGES_ISAACSIM=true; STAGES_ISAACSIM_VERSION="$2"; fi
if [[ -n "$3" ]]; then STAGES_ISAACLAB=true; STAGES_ISAACLAB_VERSION="$3"; fi
stages::build_plan
printf '%s\\n' "${STAGES_PLAN[@]}"
""",
                        "test-plan",
                        str(ROOT),
                        sim,
                        lab,
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                mujoco = next(
                    row.split("|")
                    for row in result.stdout.splitlines()
                    if "Dockerfile.mujoco|" in row
                )
                self.assertIn(f"PYTHON_VERSION={python}", mujoco)
                tags.append(mujoco[2])
        self.assertEqual(len(set(tags[:4])), 4)
        self.assertEqual(tags[3], tags[4])

    def plan(self, *args):
        return subprocess.run(
            [str(ROOT / "creator/scripts/run_env.sh"), "-p", "-o", "24.04", "-v", "jazzy", *args],
            capture_output=True,
            text=True,
        )

    def test_kitless_plan_does_not_include_sim(self):
        result = self.plan("-L", "release/3.0.0", "-e", "newton,rl[rsl-rl],visualizer[newton]")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Dockerfile.isaacsim", result.stdout)
        self.assertIn(
            "installation: legacy; packages: newton,rl[rsl-rl],visualizer[newton]", result.stdout
        )

    def test_full_sim_plan_and_package_variants(self):
        tags = []
        for selector in ("default", "core", "rl[rsl-rl]"):
            result = self.plan("-I", "6.1.0.0", "-L", "release/3.0.0", "-e", selector)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Dockerfile.isaacsim", result.stdout)
            self.assertIn(f"installation: python-env; packages: {selector}", result.stdout)
            tags.append(
                next(line for line in result.stdout.splitlines() if "Final image:" in line)
            )
        self.assertEqual(len(set(tags)), 3)

    def test_invalid_combinations_fail_before_building(self):
        for args in (
            ("-L", "release/3.0.0", "-j", "python-env"),
            ("-I", "6.1.0.0", "-L", "release/3.0.0", "-j", "legacy"),
            ("-I", "5.1.0", "-L", "release/3.0.0"),
            ("-L", "v2.3.2"),
            ("-L", "release/3.0.0", "-j", "unknown"),
            ("-L", "release/3.0.0", "-e", "rl[broken"),
            ("-L", "release/3.0.0", "-e", "core|injected"),
            ("-L", "release/3.0.0", "-e", "isaacsim"),
        ):
            with self.subTest(args=args):
                result = self.plan(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Build plan", result.stdout)

    def test_physics_and_visualization_selection(self):
        for physics, physics_selector in (
            ("newton", "newton"),
            ("ovphysx", "ov[ovphysx]"),
            ("both", "newton,ov[ovphysx]"),
        ):
            for visualizer in ("newton", "rerun", "viser", "all"):
                with self.subTest(physics=physics, visualizer=visualizer):
                    result = self.plan(
                        "-L", "release/3.0.0", "-e", "core", "-B", physics, "-V", visualizer
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(
                        f"packages: {physics_selector},visualizer[{visualizer}]", result.stdout
                    )
                    self.assertIn(
                        f"physics: {physics}; visualization: {visualizer}", result.stdout
                    )

    def test_sim_physics_and_kit_require_sim(self):
        for extra in (("-B", "isaacsim"), ("-B", "all"), ("-V", "kit")):
            with self.subTest(extra=extra):
                result = self.plan("-L", "release/3.0.0", *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("require the Isaac Sim layer", result.stderr)
                result = self.plan("-I", "6.1.0.0", "-L", "release/3.0.0", "-e", "core", *extra)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_and_v2_backend_selections_are_rejected(self):
        for extra in (("-B", "invalid"), ("-V", "invalid")):
            self.assertNotEqual(self.plan("-L", "release/3.0.0", *extra).returncode, 0)
        result = self.plan("-I", "5.1.0", "-L", "v2.3.2", "-B", "newton")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires Isaac Lab 3.x", result.stderr)

    def test_backend_additions_preserve_default_packages(self):
        result = self.plan("-L", "release/3.0.0", "-B", "ovphysx", "-V", "rerun")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "packages: mimic,teleop,newton,rl,visualizer,ov[ovphysx],visualizer[rerun]",
            result.stdout,
        )

    def test_effective_selectors_reach_docker_build(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = Path(directory) / "docker"
            log = Path(directory) / "calls"
            docker.write_text("""#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:3] != ['buildx', 'version']:
    with open(os.environ['LAB_BUILD_LOG'], 'a') as log:
        log.write(json.dumps(sys.argv[1:]) + '\\n')
""")
            docker.chmod(0o755)
            env = dict(
                os.environ, PATH=f"{directory}:{os.environ['PATH']}", LAB_BUILD_LOG=str(log)
            )
            result = subprocess.run(
                [
                    str(ROOT / "creator/scripts/run_env.sh"),
                    "-b",
                    "-o",
                    "24.04",
                    "-v",
                    "jazzy",
                    "-L",
                    "release/3.0.0",
                    "-e",
                    "rl[rsl-rl]",
                    "-B",
                    "ovphysx",
                    "-V",
                    "viser",
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            lab = next(
                call for call in calls if any(arg.endswith("Dockerfile.isaaclab") for arg in call)
            )
            self.assertIn("ISAACLAB_INSTALL=rl[rsl-rl],ov[ovphysx],visualizer[viser]", lab)
            user = next(
                call for call in calls if any(arg.endswith("Dockerfile.user") for arg in call)
            )
            label = user[user.index("--label") + 1]
            self.assertTrue(
                label.startswith("org.docker_envs.build-command=creator/scripts/run_env.sh -b ")
            )
            replay = shlex.split(label.split("=", 1)[1])
            self.assertEqual(replay[replay.index("-L") + 1], "release/3.0.0")
            self.assertEqual(replay[replay.index("-e") + 1], "rl[rsl-rl]")

    def test_v2_with_sim_remains_available(self):
        result = self.plan("-I", "5.1.0", "-L", "v2.3.2", "-e", "none")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_interactive_command_preserves_selectors_and_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            curl = Path(directory) / "curl"
            curl.write_text("#!/bin/sh\nexit 7\n")
            curl.chmod(0o755)
            git = Path(directory) / "git"
            git.write_text("#!/bin/sh\nexit 7\n")
            git.chmod(0o755)
            env = dict(os.environ, PATH=f"{directory}:{os.environ['PATH']}")
            answers = [
                "2",
                "n",
                "3",
                "4",
                "n",
                "n",
                "y",
                "release/3.0.0",
                "8",
                "newton,rl[rsl-rl],visualizer[newton]",
                "3",  # OV PhysX
                "4",  # Viser
                "n",
                "n",
                "admin",
                "12345",
                "23456",
                "test-envs",
                "",
            ]
            result = subprocess.run(
                [str(ROOT / "creator/scripts/create_env.sh"), "--dry-run"],
                input="\n".join(answers) + "\n",
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            command = next(
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip().startswith("creator/scripts/run_env.sh")
            )
            args = shlex.split(command)
            self.assertEqual(args[args.index("-e") + 1], answers[9])
            self.assertEqual(args[args.index("-j") + 1], "legacy")
            self.assertEqual(args[args.index("-B") + 1], "ovphysx")
            self.assertEqual(args[args.index("-V") + 1], "viser")
            self.assertEqual(args[args.index("-N") + 1], "test-envs")
            args[0] = str(ROOT / "creator/scripts/run_env.sh")
            args[args.index("-b")] = "-p"
            replay = subprocess.run(args, env=env, capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            for line in result.stdout.splitlines():
                if "Final image:" in line:
                    self.assertIn(line, replay.stdout)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.temp = Path(self.directory.name)
        self.lab = self.temp / "IsaacLab"
        (self.lab / "source/isaaclab/isaaclab/cli").mkdir(parents=True)
        self.venv = self.temp / "venv"
        (self.venv / "bin").mkdir(parents=True)
        self.log = self.temp / "calls.jsonl"
        fake = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ['INSTALL_TEST_LOG'], 'a') as log:
    log.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + '\\n')
"""
        for path in (self.temp / "uv", self.venv / "bin/python", self.lab / "isaaclab.sh"):
            path.write_text(fake)
            path.chmod(0o755)
        (self.venv / "bin/activate").write_text(
            f"export VIRTUAL_ENV={shlex.quote(str(self.venv))}\n"
            f'export PATH={shlex.quote(str(self.venv / "bin"))}:$PATH\n'
        )
        self.env = dict(
            os.environ,
            PATH=f"{self.temp}:{os.environ['PATH']}",
            ISAACLAB_DIR=str(self.lab),
            ISAAC_VENV=str(self.venv),
            INSTALL_TEST_LOG=str(self.log),
        )

    def install(self, method, selector="default"):
        return subprocess.run(
            ["bash", str(ROOT / "creator/common/install_isaaclab.sh")],
            env=dict(self.env, ISAACLAB_METHOD=method, ISAACLAB_INSTALL=selector),
            capture_output=True,
            text=True,
        )

    def test_default_is_a_bare_install_flag(self):
        result = self.install("legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["uv", "venv"] for call in calls))
        self.assertEqual(calls[-1], ["isaaclab.sh", "-i"])

    def test_kitless_creates_environment_when_missing(self):
        (self.venv / "bin/python").unlink()
        # The uv stub records creation; supply Python for the following checks.
        (self.temp / "python").write_text("#!/bin/sh\nexit 0\n")
        (self.temp / "python").chmod(0o755)
        result = self.install("legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertIn(
            ["uv", "venv", "--python", "3.12", "--system-site-packages", "--seed", str(self.venv)],
            calls,
        )

    def test_python_env_reuses_sim_and_preserves_selectors(self):
        selector = "newton,rl[rsl-rl],visualizer[newton]"
        result = self.install("python-env", selector)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["uv", "venv"] for call in calls))
        self.assertEqual(calls[-1], ["isaaclab.sh", "-i", selector])

    def test_missing_sim_environment_fails(self):
        (self.venv / "bin/python").unlink()
        self.assertNotEqual(self.install("python-env").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_sim_installs_platform_torch_and_nvidia_resolution_options(self):
        dockerfile = (ROOT / "creator/common/Dockerfile.isaacsim").read_text()
        instruction = dockerfile.split("RUN --mount=type=cache", 1)[1].split("\n\n", 1)[0]
        command = "\n".join(instruction.splitlines()[1:])
        for architecture, index in (("amd64", "cu128"), ("arm64", "cu130")):
            with self.subTest(architecture=architecture):
                self.log.unlink(missing_ok=True)
                env = dict(
                    self.env,
                    TARGETARCH=architecture,
                    PYTHON_VERSION="3.12",
                    ISAACSIM_VERSION="6.1.0.0",
                    ISAACSIM_EXTRAS="all,extscache",
                    TORCH_VERSION="2.11.0",
                    TORCHVISION_VERSION="0.26.0",
                    TORCH_INDEX_URL="",
                )
                result = subprocess.run(
                    ["bash", "-e", "-c", command], env=env, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = [json.loads(line) for line in self.log.read_text().splitlines()]
                self.assertFalse(any(call[:2] == ["uv", "venv"] for call in calls))
                sim = next(call for call in calls if "isaacsim[all,extscache]==6.1.0.0" in call)
                self.assertIn("unsafe-best-match", sim)
                self.assertIn("--prerelease=allow", sim)
                self.assertIn("torch==2.11.0", calls[-1])
                self.assertIn("torchvision==0.26.0", calls[-1])
                self.assertIn(f"https://download.pytorch.org/whl/{index}", calls[-1])
