"""Regression checks for publication boundaries and local build failure handling."""

import json
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    # BaseLoader preserves GitHub's `on` key instead of treating it as YAML 1.1 true.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), yaml.BaseLoader)


class WorkflowTests(unittest.TestCase):
    def test_prs_have_no_publication_credentials_or_cleanup(self):
        for name in ("ros2-staged.yml", "pytorch-staged.yml"):
            with self.subTest(workflow=name):
                config = workflow(name)
                self.assertIn("pull_request", config["on"])
                pr = config["jobs"]["validate-pr"]
                self.assertEqual(pr["permissions"], {"contents": "read"})
                self.assertIn("github.event_name == 'pull_request'", pr["if"])
                for step in pr["steps"]:
                    self.assertNotIn("login-action", step.get("uses", ""))
                    self.assertNotIn("cache-to", step.get("with", {}))
                    self.assertNotEqual(step.get("with", {}).get("push"), "true")
                for job_name, job in config["jobs"].items():
                    if job_name != "validate-pr":
                        self.assertIn("github.event_name != 'pull_request'", job["if"])
                cleanup = config["jobs"]["cleanup-intermediates"]
                self.assertIn("success()", cleanup["if"])
                self.assertNotIn("always()", cleanup["if"])

    def test_publication_caches_are_distinct_and_outside_cleanup(self):
        refs = set()
        for name in ("ros2-staged.yml", "pytorch-staged.yml", "docker.yml"):
            config = workflow(name)
            self.assertEqual(config["concurrency"]["cancel-in-progress"], "false")
            for job in config["jobs"].values():
                for step in job.get("steps", []):
                    settings = step.get("with", {})
                    if settings.get("push") != "true":
                        continue
                    cache = settings["cache-from"]
                    self.assertIn("/buildcache:", cache)
                    self.assertNotIn(cache, refs)
                    refs.add(cache)
                    self.assertEqual(settings["cache-to"], cache + ",mode=max")
                    self.assertNotIn("/buildcache:", settings["tags"])
        self.assertEqual(len(refs), 10)
        cleanup = workflow("ghcr-cleanup.yml")
        self.assertNotIn("buildcache", cleanup["env"]["EXTRA_PACKAGES_TO_DELETE"])

    def test_ros_pr_matrix_matches_published_final_images(self):
        jobs = workflow("ros2-staged.yml")["jobs"]
        expected = set()
        for name, usage in (
            ("finalize-base-ros-user", "skip"),
            ("finalize-base-ros-moveit-user", "manipulation"),
        ):
            for row in jobs[name]["strategy"]["matrix"]["include"]:
                expected.add((row["os"], row["ros"], usage))
        actual = {
            (row["os"], row["ros"], row["usage"])
            for row in jobs["validate-pr"]["strategy"]["matrix"]["include"]
        }
        self.assertEqual(actual, expected)

    def test_cleanup_preserves_digests_with_final_or_other_tags(self):
        job = workflow("pytorch-staged.yml")["jobs"]["cleanup-intermediates"]
        script = job["steps"][0]["run"]
        query = re.search(r"jq --arg tag \"\$\{TAG\}\" '(.*?)'", script, re.S).group(1)
        tag = "cuda12.8-torch2.8"
        tag_sets = [
            [tag + "-base"],
            [tag + "-mujoco", tag],
            [tag + "-pytorch", "other-release"],
            [],
            [tag],
            [tag + "-base", tag + "-mujoco"],
        ]
        versions = [
            {"id": i, "metadata": {"container": {"tags": tags}}} for i, tags in enumerate(tag_sets)
        ]
        result = subprocess.run(
            ["jq", "--arg", "tag", tag, query],
            input=json.dumps(versions),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual([v["id"] for v in json.loads(result.stdout)], [0, 5])

    def test_pytorch_pr_versions_match_publication(self):
        jobs = workflow("pytorch-staged.yml")["jobs"]
        matrix = jobs["finalize"]["strategy"]["matrix"]["env"]
        self.assertEqual(len(matrix), 1, "Extend PR coverage when adding a published stack")
        settings = next(
            step["with"]
            for step in jobs["validate-pr"]["steps"]
            if "build-push-action" in step.get("uses", "")
        )
        args = dict(line.split("=", 1) for line in settings["build-args"].splitlines())
        expected = matrix[0]
        self.assertEqual(args["BASE_IMAGE"], "ubuntu:" + expected["OS_VERSION"])
        for arg, key in (
            ("TORCH_VERSION", "TORCH"),
            ("TORCHVISION_VERSION", "VISION"),
            ("TORCHAUDIO_VERSION", "AUDIO"),
            ("MUJOCO_VERSION", "MUJOCO"),
            ("GYM_VERSION", "GYM"),
        ):
            self.assertEqual(args[arg], expected[key])


class RosCleanupTests(unittest.TestCase):
    def run_cleanup(self, error="", owner_type="User"):
        job = workflow("ros2-staged.yml")["jobs"]["cleanup-intermediates"]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            gh = temp / "gh"
            gh.write_text("""#!/bin/bash
set -eu
if [[ "$2" == /repos/* ]]; then
  echo "$TEST_OWNER_TYPE"
elif [[ "$2" == --paginate ]]; then
  printf '1\\n2\\n'
elif [[ "$2" == -X && "$3" == DELETE ]]; then
  echo "$4" >> "$TEST_DELETE_LOG"
  if [[ "$4" == */base/versions/1 && -n "$TEST_DELETE_ERROR" ]]; then
    echo "$TEST_DELETE_ERROR" >&2
    exit 1
  fi
else
  exit 99
fi
""")
            gh.chmod(0o755)
            log = temp / "deletions"
            result = subprocess.run(
                ["bash", "-c", job["steps"][0]["run"]],
                env=dict(
                    os.environ,
                    PATH=f"{temp}:{os.environ['PATH']}",
                    REPO="test/docker_envs",
                    INTERMEDIATE_PACKAGES='["base", "docker_envs/ros"]',
                    TEST_OWNER_TYPE=owner_type,
                    TEST_DELETE_LOG=str(log),
                    TEST_DELETE_ERROR=error,
                ),
                capture_output=True,
                text=True,
            )
            return result, log.read_text().splitlines()

    def test_download_protection_retains_package_and_continues_cleanup(self):
        error = (
            "gh: Publicly visible package versions with more than 5000 downloads "
            "cannot be deleted. Contact GitHub support for further assistance. (HTTP 400)"
        )
        for owner_type, prefix in (("User", "/users"), ("Organization", "/orgs")):
            with self.subTest(owner_type=owner_type):
                result, deletions = self.run_cleanup(error, owner_type)
                base = f"{prefix}/test/packages/container"
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("::warning::Retaining base version 1", result.stdout)
                self.assertEqual(
                    deletions,
                    [
                        f"{base}/base/versions/1",
                        f"{base}/base/versions/2",
                        f"{base}/docker_envs%2Fros/versions/1",
                        f"{base}/docker_envs%2Fros/versions/2",
                        f"{base}/docker_envs%2Fros",
                    ],
                )

    def test_successful_cleanup_removes_packages(self):
        result, deletions = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(deletions), 6)
        self.assertEqual(deletions[2], "/users/test/packages/container/base")
        self.assertEqual(deletions[5], "/users/test/packages/container/docker_envs%2Fros")
        self.assertNotIn("::warning::", result.stdout)

    def test_unexpected_deletion_errors_fail_cleanup(self):
        for error in ("gh: Forbidden (HTTP 403)", "gh: Bad request (HTTP 400)"):
            with self.subTest(error=error):
                result, deletions = self.run_cleanup(error)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)
                self.assertEqual(deletions, ["/users/test/packages/container/base/versions/1"])


class LocalBuilderTests(unittest.TestCase):
    def test_stage_failure_stops_the_stack(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            builder = temp / "build_image.sh"
            builder.write_text('#!/bin/bash\necho attempted >> "$BUILD_TEST_LOG"\nexit 23\n')
            builder.chmod(0o755)
            log = temp / "calls"
            env = dict(
                os.environ, BUILD_TEST_LOG=str(log), TEST_SCRIPTS=str(temp), TEST_ROOT=str(ROOT)
            )
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    """
source "$TEST_ROOT/creator/scripts/lib/stages.sh"
SCRIPTS_DIR="$TEST_SCRIPTS"
STAGES_FINAL_IMAGE=test:final
STAGES_PLAN=("$TEST_ROOT/creator/common/Dockerfile.base|24.04|test:base"
             "$TEST_ROOT/creator/common/Dockerfile.user|test:base|test:final")
stages::run_plan
""",
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(log.read_text(), "attempted\n")
            self.assertNotIn("Done. Final image:", result.stdout)

    def test_buildkit_context_and_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            docker = temp / "docker"
            docker.write_text("""#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:3] == ['buildx', 'version']:
    sys.exit(0)
with open(os.environ['BUILD_TEST_LOG'], 'w') as log:
    json.dump({'args': sys.argv[1:], 'buildkit': os.environ.get('DOCKER_BUILDKIT')}, log)
sys.exit(23)
""")
            docker.chmod(0o755)
            log = temp / "arguments.json"
            env = dict(
                os.environ,
                PATH=f"{temp}:{os.environ['PATH']}",
                BUILD_TEST_LOG=str(log),
                DOCKER_BUILDKIT="0",
            )
            for key in ("BUILD_CONTEXT", "DOCKER_BUILD_EXTRA", "DOCKER_BUILD_CPUSET"):
                env.pop(key, None)
            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "creator/scripts/build_image.sh"),
                    str(ROOT / "creator/common/Dockerfile.base"),
                    "24.04",
                    "test:base",
                ],
                cwd=temp,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 23, result.stderr)
            invocation = json.loads(log.read_text())
            self.assertEqual(invocation["buildkit"], "1")
            self.assertEqual(invocation["args"][-1], str(ROOT))


if __name__ == "__main__":
    unittest.main()


class IsaacCachePathTests(unittest.TestCase):
    def test_isaaclab_compose_volumes_match_cache_list(self):
        listed = {
            line.split(":", 1)[1]
            for line in (ROOT / "creator/common/isaac-cache-dirs.txt").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        compose = yaml.safe_load((ROOT / "composer/isaaclab/compose.yml").read_text())
        home = "/home/${CONTAINER_USER:-admin}/"
        mounted = set()
        for volume in compose["services"]["isaaclab"]["volumes"]:
            if isinstance(volume, str) and volume.startswith("isaac-"):
                target = volume.split(":", 1)[1]
                if target.startswith(home):
                    mounted.add(target[len(home) :])
        self.assertEqual(mounted, listed)
