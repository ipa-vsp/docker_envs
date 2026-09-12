"""Coverage for the GUI's pure-Python layer.

These import only the standard library side of the package, so they run in the
same job as the rest of the suite without PySide6 installed.
"""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from docker_envs_gui.model import (  # noqa: E402  (path set up above)
    BUILD_STEP,
    LAYER_HEADING,
    Plan,
    PlanLayer,
    Selection,
    isaaclab_major,
    overall_progress,
)
from docker_envs_gui import repo  # noqa: E402
from docker_envs_gui.repo import is_repo_root, resolve, RepoError  # noqa: E402


class SelectionEnvironmentTests(unittest.TestCase):
    def test_booleans_become_true_and_false(self):
        env = Selection(mujoco=True, zenoh=False).env()
        self.assertEqual(env["DEG_MUJOCO"], "true")
        self.assertEqual(env["DEG_ZENOH"], "false")

    def test_empty_strings_are_omitted_so_defaults_survive(self):
        env = Selection(final_image="", cuda_version="").env()
        self.assertNotIn("DEG_FINAL_IMAGE", env)
        self.assertNotIn("DEG_CUDA_VERSION", env)

    def test_field_names_map_onto_the_stages_variables(self):
        env = Selection(user_uid="1000", user_gid="1000", os="22.04").env()
        self.assertEqual(env["DEG_USER_UID"], "1000")
        self.assertEqual(env["DEG_USER_GID"], "1000")
        self.assertEqual(env["DEG_OS"], "22.04")

    def test_defaults_match_stages_init_selection(self):
        """The form must open on the same answers create_env.sh starts from."""
        result = subprocess.run(
            ["bash", str(ROOT / "creator/scripts/lib/query.sh"), "defaults"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        stages = {
            line.split("\x1f")[1]: line.split("\x1f")[2]
            for line in result.stdout.splitlines()
            if line.startswith("SELECTION\x1f")
        }
        default = Selection()
        self.assertEqual(default.os, stages["OS"])
        self.assertEqual(default.ros, stages["ROS"])
        self.assertEqual(default.usage, stages["USAGE"])
        self.assertEqual(default.username, stages["USERNAME"])
        self.assertEqual(default.namespace, stages["NAMESPACE"])
        self.assertEqual(default.isaaclab_method, stages["ISAACLAB_METHOD"])
        self.assertEqual(default.isaaclab_install, stages["ISAACLAB_INSTALL"])


class CrossFieldRuleTests(unittest.TestCase):
    def test_method_follows_the_isaac_sim_layer(self):
        self.assertEqual(Selection(isaacsim=True).isaaclab_effective_method(), "python-env")
        self.assertEqual(Selection(isaacsim=False).isaaclab_effective_method(), "legacy")
        self.assertEqual(
            Selection(isaacsim=True, isaaclab_method="legacy").isaaclab_effective_method(),
            "legacy",
        )

    def test_backends_need_isaac_lab_3x(self):
        self.assertTrue(
            Selection(
                isaaclab=True, isaaclab_version="release/3.0.0"
            ).isaaclab_backends_selectable()
        )
        self.assertFalse(
            Selection(isaaclab=True, isaaclab_version="v2.3.2").isaaclab_backends_selectable()
        )
        self.assertFalse(Selection(isaaclab=False).isaaclab_backends_selectable())

    def test_isaaclab_major_matches_the_shell_implementation(self):
        for ref, expected in (
            ("release/3.0.0", 3),
            ("v3.0.0-beta2", 3),
            ("v2.3.2", 2),
            ("2.1.0", 2),
            ("main", 3),
            ("develop", 3),
        ):
            with self.subTest(ref=ref):
                self.assertEqual(isaaclab_major(ref), expected)
                shell = subprocess.run(
                    [
                        "bash",
                        "-c",
                        f'source "{ROOT}/creator/scripts/lib/stages.sh"; '
                        f'stages::isaaclab_major "{ref}"',
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(int(shell.stdout.strip()), expected)


class ProgressParsingTests(unittest.TestCase):
    def test_layer_heading_is_recognised(self):
        match = LAYER_HEADING.match("== Building docker_envs/ros:24.04-jazzy (layer 2/5) ==")
        self.assertIsNotNone(match)
        self.assertEqual((match["step"], match["total"]), ("2", "5"))
        self.assertEqual(match["image"], "docker_envs/ros:24.04-jazzy")

    def test_other_headings_are_not_progress(self):
        for line in (
            "== Summary ==",
            "== Build plan (3 layers) ==",
            "Building Docker image from: creator/common/Dockerfile.base",
        ):
            with self.subTest(line=line):
                self.assertIsNone(LAYER_HEADING.match(line))

    def test_buildkit_instruction_counter_is_recognised(self):
        for line, expected in (
            ("#5 [2/4] RUN echo one", ("2", "4")),
            ("#7 [ 4/12] RUN apt-get install -y x", ("4", "12")),
            ("#4 [1/4] FROM docker.io/library/ubuntu:24.04", ("1", "4")),
        ):
            with self.subTest(line=line):
                match = BUILD_STEP.match(line)
                self.assertEqual((match["done"], match["total"]), expected)

    def test_other_buildkit_lines_are_not_a_counter(self):
        for line in ("#10 28.28 Setting up python3", "#8 exporting to image", "#1 DONE 0.1s"):
            with self.subTest(line=line):
                self.assertIsNone(BUILD_STEP.match(line))

    def test_progress_spans_the_plan_not_the_layer(self):
        self.assertAlmostEqual(overall_progress(1, 3, 0.0), 0.0)
        self.assertAlmostEqual(overall_progress(1, 3, 1.0), 1 / 3)
        self.assertAlmostEqual(overall_progress(2, 3, 4 / 12), 0.4444, places=3)
        self.assertAlmostEqual(overall_progress(3, 3, 1.0), 1.0)

    def test_progress_is_clamped_and_safe_when_nothing_is_known(self):
        self.assertEqual(overall_progress(1, 0), 0.0)
        self.assertEqual(overall_progress(5, 3, 2.0), 1.0)
        self.assertEqual(overall_progress(1, 3, -1.0), 0.0)

    def test_ansi_is_stripped_before_matching(self):
        from docker_envs_gui.builder import ANSI

        line = "\x1b[1;36m== Building docker_envs/base:24.04 (layer 1/3) ==\x1b[0m"
        self.assertIsNotNone(LAYER_HEADING.match(ANSI.sub("", line).strip()))


class PlanTests(unittest.TestCase):
    def test_build_args_ignore_the_label_and_the_flags(self):
        layer = PlanLayer(
            index=1,
            dockerfile="common/Dockerfile.user",
            base="docker_envs/ros:24.04-jazzy",
            image="docker_envs:24.04-jazzy",
            args=[
                "--build-arg",
                "USERNAME=admin",
                "--build-arg",
                "USER_UID=1000",
                "--label",
                "org.docker_envs.build-command=run_env.sh -b",
            ],
        )
        self.assertEqual(layer.build_args, ["USERNAME=admin", "USER_UID=1000"])

    def test_a_plan_without_an_image_is_not_ok(self):
        self.assertFalse(Plan(errors=["nope"]).ok)
        self.assertFalse(Plan().ok)
        self.assertTrue(Plan(image="docker_envs:24.04-jazzy", warnings=["fyi"]).ok)


class RepoResolutionTests(unittest.TestCase):
    def setUp(self):
        self.cwd = Path.cwd()
        self.addCleanup(os.chdir, self.cwd)

    def installed_outside_the_checkout(self):
        """Pretend the package was copied into site-packages.

        ``pip install ./gui`` (without ``-e``) leaves no path from the installed
        module back to the repository, so the walk up from ``__file__`` finds
        nothing. Stubbing it is how that install shape is reproduced here.
        """
        original = repo._checkout_root
        repo._checkout_root = lambda: None
        self.addCleanup(setattr, repo, "_checkout_root", original)

    def test_the_checkout_is_recognised(self):
        self.assertTrue(is_repo_root(ROOT))
        self.assertFalse(is_repo_root(ROOT / "tests"))

    def test_resolve_finds_the_checkout_this_package_lives_in(self):
        self.assertEqual(resolve(), ROOT)

    def test_an_explicit_non_checkout_is_an_error_not_a_fallback(self):
        with self.assertRaises(RepoError):
            resolve(ROOT / "tests")

    def test_a_non_editable_install_resolves_the_checkout_it_runs_in(self):
        self.installed_outside_the_checkout()
        for start in (ROOT, ROOT / "creator" / "scripts"):
            with self.subTest(cwd=str(start)):
                os.chdir(start)
                self.assertEqual(resolve(), ROOT)

    def test_a_non_editable_install_outside_a_checkout_says_what_to_do(self):
        self.installed_outside_the_checkout()
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)
            with self.assertRaises(RepoError) as raised:
                resolve()
        message = str(raised.exception)
        self.assertIn("--repo-root", message)
        self.assertIn("DOCKER_ENVS_ROOT", message)

    def test_the_environment_variable_wins_over_the_working_directory(self):
        self.installed_outside_the_checkout()
        os.chdir(ROOT)
        os.environ["DOCKER_ENVS_ROOT"] = str(ROOT / "tests")
        self.addCleanup(os.environ.pop, "DOCKER_ENVS_ROOT", None)
        with self.assertRaises(RepoError):
            resolve()


if __name__ == "__main__":
    unittest.main()
