"""Regression coverage for query.sh, the machine-readable front end to stages.sh.

The GUI reads every rule about what is valid and what a stack is called through
this script. Its job is to say exactly what run_env.sh would say, so most of the
assertions here compare the two against one another rather than against literals.
"""

import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUERY = ROOT / "creator/scripts/lib/query.sh"
US = "\x1f"


def query(*args, **selection):
    """Run query.sh with a DEG_* selection, returning parsed records."""
    env = dict(os.environ)
    env.update({f"DEG_{key.upper()}": str(value) for key, value in selection.items()})
    result = subprocess.run(
        ["bash", str(QUERY), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result, [line.split(US) for line in result.stdout.splitlines() if line]


def records_of(kind, records):
    return [record[1:] for record in records if record[0] == kind]


def first(kind, records, default=""):
    values = records_of(kind, records)
    return values[0][0] if values else default


class PlanRecordTests(unittest.TestCase):
    def test_plain_stack_names_every_layer(self):
        result, records = query("plan", os="24.04", ros="jazzy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first("IMAGE", records), "docker_envs:24.04-jazzy")
        self.assertEqual(
            [record[1] for record in records_of("LAYER", records)],
            ["common/Dockerfile.base", "ros2/Dockerfile.jazzy", "common/Dockerfile.user"],
        )

    def test_layer_records_carry_build_arguments(self):
        _result, records = query(
            "plan", os="24.04", ros="jazzy", mujoco="true", mujoco_version="3.12.0"
        )
        mujoco = next(
            r for r in records_of("LAYER", records) if r[1].endswith("Dockerfile.mujoco")
        )
        self.assertIn("MUJOCO_VERSION=3.12.0", mujoco)
        self.assertIn("GYM_VERSION=1.3.0", mujoco)

    def test_warnings_are_records_not_prose_on_stderr(self):
        # 24.04 + rolling is buildable but frozen upstream, and iron is not in CI.
        _result, records = query("plan", os="24.04", ros="rolling")
        warnings = " ".join(record[0] for record in records_of("WARN", records))
        self.assertIn("Rolling", warnings)
        self.assertTrue(first("IMAGE", records), "a warning must not suppress the plan")

    def test_unset_fields_keep_the_stages_defaults(self):
        _result, records = query("plan")
        self.assertEqual(first("IMAGE", records), "docker_envs:24.04-rolling")

    def test_stages_variables_from_the_environment_are_ignored(self):
        # Only DEG_* may steer a plan; a stray STAGES_* must not leak in.
        env = dict(os.environ, STAGES_ROS="humble", STAGES_OS="22.04")
        result = subprocess.run(
            ["bash", str(QUERY), "plan"], cwd=ROOT, env=env, capture_output=True, text=True
        )
        self.assertIn("docker_envs:24.04-rolling", result.stdout)


class ValidationTests(unittest.TestCase):
    def assert_rejects(self, fragment, **selection):
        result, records = query("plan", **selection)
        self.assertEqual(result.returncode, 0, "an invalid selection is data, not a failure")
        errors = " ".join(record[0] for record in records_of("ERROR", records))
        self.assertIn(fragment, errors)
        self.assertEqual(first("IMAGE", records), "", "a rejected selection has no image")

    def test_ros_must_be_offered_for_the_ubuntu_release(self):
        self.assert_rejects("is not offered for Ubuntu 24.04", os="24.04", ros="humble")

    def test_kit_visualization_requires_isaac_sim(self):
        self.assert_rejects(
            "require the Isaac Sim layer",
            os="24.04",
            ros="jazzy",
            isaaclab="true",
            isaaclab_version="release/3.0.0",
            isaaclab_visualizer="kit",
        )

    def test_python_env_requires_isaac_sim(self):
        self.assert_rejects(
            "python-env requires Isaac Sim",
            os="24.04",
            ros="jazzy",
            isaaclab="true",
            isaaclab_version="release/3.0.0",
            isaaclab_method="python-env",
        )

    def test_legacy_forbids_isaac_sim(self):
        self.assert_rejects(
            "legacy selects Kit-less",
            os="24.04",
            ros="jazzy",
            isaacsim="true",
            isaacsim_version="6.1.0.0",
            isaaclab="true",
            isaaclab_version="release/3.0.0",
            isaaclab_method="legacy",
        )

    def test_backend_selection_requires_isaac_lab_3x(self):
        self.assert_rejects(
            "requires Isaac Lab 3.x",
            os="24.04",
            ros="jazzy",
            isaaclab="true",
            isaaclab_version="v2.3.2",
            isaaclab_physics="newton",
        )

    def test_malformed_package_selectors_are_rejected(self):
        self.assert_rejects(
            "Invalid Isaac Lab package selectors",
            os="24.04",
            ros="jazzy",
            isaaclab="true",
            isaaclab_version="release/3.0.0",
            isaaclab_install="rl[rsl-rl",
        )


class AgreementWithRunEnvTests(unittest.TestCase):
    """query.sh and run_env.sh must never disagree about a selection."""

    CASES = (
        (
            {"os": "24.04", "ros": "jazzy", "usage": "manipulation"},
            ["-o", "24.04", "-v", "jazzy", "-u", "manipulation"],
        ),
        (
            {
                "os": "24.04",
                "ros": "jazzy",
                "use_cuda": "true",
                "cuda_version": "13.3.1",
                "isaacsim": "true",
                "isaacsim_version": "6.1.0.0",
                "isaaclab": "true",
                "isaaclab_version": "release/3.0.0",
                "isaaclab_physics": "newton",
                "isaaclab_visualizer": "rerun",
            },
            [
                "-o",
                "24.04",
                "-v",
                "jazzy",
                "-c",
                "13.3.1",
                "-I",
                "6.1.0.0",
                "-L",
                "release/3.0.0",
                "-B",
                "newton",
                "-V",
                "rerun",
            ],
        ),
        (
            {
                "os": "22.04",
                "ros": "humble",
                "mujoco": "true",
                "mujoco_version": "3.12.0",
                "zenoh": "true",
                "simulation": "true",
                "namespace": "acme",
                "username": "dev",
            },
            [
                "-o",
                "22.04",
                "-v",
                "humble",
                "-m",
                "3.12.0",
                "-z",
                "-s",
                "-N",
                "acme",
                "-n",
                "dev",
            ],
        ),
    )

    def run_env_plan(self, flags):
        return subprocess.run(
            [str(ROOT / "creator/scripts/run_env.sh"), "-p", *flags],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_image_and_replay_match_the_cli(self):
        for selection, flags in self.CASES:
            with self.subTest(flags=" ".join(flags)):
                _result, records = query("plan", **selection)
                cli = self.run_env_plan(flags)
                self.assertEqual(cli.returncode, 0, cli.stderr)
                self.assertIn(f"Final image: {first('IMAGE', records)}", cli.stdout)
                self.assertIn(first("REPLAY", records), cli.stdout)

    def test_layer_count_matches_the_cli(self):
        for selection, flags in self.CASES:
            with self.subTest(flags=" ".join(flags)):
                _result, records = query("plan", **selection)
                cli = self.run_env_plan(flags)
                self.assertIn(
                    f"Build plan ({len(records_of('LAYER', records))} layers)", cli.stdout
                )


class LookupTests(unittest.TestCase):
    def test_ros_for_os_annotates_ci_and_frozen_combinations(self):
        _result, records = query("ros-for-os", "24.04")
        table = {record[0]: record[1] for record in records}
        self.assertEqual(set(table), {"rolling", "kilted", "jazzy"})
        self.assertIn("ci", table["jazzy"])
        self.assertIn("frozen", table["rolling"])
        self.assertNotIn("frozen", table["jazzy"])

    def test_ros_for_os_22_04(self):
        _result, records = query("ros-for-os", "22.04")
        self.assertEqual([record[0] for record in records], ["humble", "iron"])

    def test_isaaclab_selectors_follow_the_major_version(self):
        _result, three = query("isaaclab-selectors", "release/3.0.0")
        self.assertEqual(dict(three)["rsl_rl"], "rl[rsl-rl]")
        self.assertEqual(dict(three)["none"], "core")
        _result, two = query("isaaclab-selectors", "v2.3.2")
        self.assertEqual(dict(two)["rsl_rl"], "rsl_rl")
        self.assertEqual(dict(two)["none"], "none")

    def test_defaults_expose_the_offline_fallbacks(self):
        _result, records = query("defaults")
        fallbacks = {record[0]: record[1] for record in records_of("DEFAULT", records)}
        self.assertEqual(
            set(fallbacks),
            {"CUDA", "MUJOCO", "GYM", "ISAACSIM", "ISAACLAB", "TORCH", "TORCHVISION"},
        )
        selection = {record[0]: record[1] for record in records_of("SELECTION", records)}
        self.assertEqual(selection["OS"], "24.04")
        self.assertEqual(selection["USAGE"], "skip")
        self.assertEqual(selection["FINAL_IMAGE"], "")

    def test_unknown_subcommand_is_an_error(self):
        result = subprocess.run(
            ["bash", str(QUERY), "nonsense"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
