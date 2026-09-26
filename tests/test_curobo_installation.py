"""cuRobo layer: build-plan rules and the installer's CUDA extra selection."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def plan(*args):
    return subprocess.run(
        [str(ROOT / "creator/scripts/run_env.sh"), "-p", "-o", "24.04", "-v", "jazzy", *args],
        capture_output=True,
        text=True,
    )


class CuroboPlanTests(unittest.TestCase):
    def layer_args(self, stdout_plan_args):
        result = subprocess.run(
            [
                "bash",
                "-ec",
                'source "$1/creator/scripts/lib/stages.sh"; stages::init_selection; '
                'STAGES_CUROBO=true; eval "$2"; stages::build_plan; '
                'printf "%s\\n" "${STAGES_PLAN[@]}"',
                "test-plan",
                str(ROOT),
                stdout_plan_args,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return next(r.split("|") for r in result.stdout.splitlines() if "Dockerfile.curobo|" in r)

    def test_cuda_extra_follows_the_base(self):
        for setup, cuda in (
            ("", "12"),
            ("STAGES_USE_CUDA=true; STAGES_CUDA_VERSION=13.3.1", "13"),
            ("STAGES_USE_CUDA=true; STAGES_CUDA_VERSION=12.8.1", "12"),
        ):
            with self.subTest(setup=setup):
                self.assertIn(f"CUROBO_CUDA={cuda}", self.layer_args(setup))

    def test_curobo_follows_isaac_and_is_replayable(self):
        result = plan("-I", "6.1.0.0", "-L", "release/3.0.0", "-R", "main")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        order = [
            n
            for n in (
                "Dockerfile.venv",
                "Dockerfile.isaacsim",
                "Dockerfile.isaaclab",
                "Dockerfile.curobo",
                "Dockerfile.user",
            )
            if any(n in line for line in lines)
        ]
        self.assertEqual(len(order), 5)
        positions = [next(i for i, l in enumerate(lines) if n in l) for n in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("-R main", result.stdout)

    def test_bare_flag_selects_main(self):
        result = plan("-R")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("curobomain", result.stdout)

    def test_python_311_isaac_sim_is_rejected(self):
        result = plan("-I", "5.1.0", "-R")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.12", result.stderr)
        self.assertNotIn("Build plan", result.stdout)

    def test_ubuntu_2204_warns_about_ros_python(self):
        result = subprocess.run(
            [str(ROOT / "creator/scripts/run_env.sh"), "-p", "-o", "22.04", "-v", "humble", "-R"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cannot import it", result.stderr)


class CuroboInstallerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.temp = Path(directory.name)
        self.source = self.temp / "curobo"
        self.source.mkdir()
        (self.source / "pyproject.toml").write_text("[project.optional-dependencies]\ncu12 = []\n")
        self.venv = self.temp / "venv"
        (self.venv / "bin").mkdir(parents=True)
        self.log = self.temp / "calls.jsonl"
        uv = self.temp / "uv"
        uv.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            "open(os.environ['TEST_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        )
        # Answers the installer's three probes: version assert, torch CUDA, metadata.
        python = self.venv / "bin/python"
        python.write_text(
            "#!/bin/sh\n"
            'case "$2" in\n'
            '  *torch*) [ -n "$TEST_TORCH" ] || exit 1; echo "$TEST_TORCH" ;;\n'
            '  *sys.version_info*) [ "$TEST_PY" = 3.12 ] || exit 1 ;;\n'
            "  *) echo cuRobo: 0.0 ;;\n"
            "esac\n"
        )
        for path in (uv, python):
            path.chmod(0o755)

    def install(self, torch="", py="3.12", cuda="12"):
        env = dict(
            os.environ,
            PATH=f"{self.temp}:{os.environ['PATH']}",
            CUROBO_DIR=str(self.source),
            VIRTUAL_ENV=str(self.venv),
            CUROBO_CUDA=cuda,
            TEST_LOG=str(self.log),
            TEST_TORCH=torch,
            TEST_PY=py,
        )
        return subprocess.run(
            ["bash", str(ROOT / "creator/common/install_curobo.sh")],
            env=env,
            capture_output=True,
            text=True,
        )

    def installed_extra(self):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return calls[-1][-1]

    def test_fresh_environment_gets_pytorch_extra(self):
        for cuda in ("12", "13"):
            with self.subTest(cuda=cuda):
                self.assertEqual(self.install(cuda=cuda).returncode, 0)
                self.assertEqual(self.installed_extra(), f".[cu{cuda}-torch]")

    def test_existing_pytorch_decides_the_extra(self):
        result = self.install(torch="12", cuda="13")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.installed_extra(), ".[cu12]")

    def test_rejects_non_312_environment_and_missing_environment(self):
        self.assertNotEqual(self.install(py="3.11").returncode, 0)
        (self.venv / "bin/python").unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("build the venv layer first", result.stderr)
        self.assertFalse(self.log.exists())

    def test_legacy_refs_without_extras_fail_clearly(self):
        (self.source / "pyproject.toml").write_text("[project]\nname = 'curobo'\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no cu12/cu13 extras", result.stderr)


if __name__ == "__main__":
    unittest.main()
