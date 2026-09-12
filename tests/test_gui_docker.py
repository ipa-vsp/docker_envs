"""Coverage for the Images and Containers tabs' view of Docker.

Follows the idiom the rest of this suite uses for anything that shells out: a
stub ``docker`` executable is put on PATH and its argv is recorded, so the real
daemon is never involved and destructive actions are asserted, not performed.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from docker_envs_gui.docker_cli import (  # noqa: E402  (path set up above)
    BUILD_COMMAND_LABEL,
    ContainerInfo,
    DockerCli,
    DockerError,
    ImageInfo,
    parse_size,
    parse_timestamp,
)

IMAGE_ROWS = [
    {
        "ID": "3a688ca3926e",
        "Repository": "docker_envs",
        "Tag": "24.04-jazzy",
        "CreatedAt": "2026-09-12 12:45:48 +0200 CEST",
        "CreatedSince": "4 hours ago",
        "Size": "130GB",
        "Containers": "0",
    },
    {
        "ID": "388fc08195ca",
        "Repository": "docker_envs/ros",
        "Tag": "24.04-jazzy",
        "CreatedAt": "2026-09-11 09:00:00 +0200 CEST",
        "CreatedSince": "27 hours ago",
        "Size": "30.4GB",
        "Containers": "1",
    },
    {
        "ID": "deadbeef0001",
        "Repository": "<none>",
        "Tag": "<none>",
        "CreatedAt": "2026-09-10 09:00:00 +0200 CEST",
        "CreatedSince": "2 days ago",
        "Size": "1.2GB",
        "Containers": "0",
    },
]

CONTAINER_ROWS = [
    {
        "ID": "b5eeb20559b8",
        "Names": "zulu",
        "Image": "docker_envs:24.04-jazzy",
        "State": "exited",
        "Status": "Exited (0) 2 hours ago",
        "CreatedAt": "2026-09-12 07:44:20 +0200 CEST",
        "RunningFor": "9 hours ago",
        "Ports": "",
        "Size": "0B",
    },
    {
        "ID": "c1111111111a",
        "Names": "alpha",
        "Image": "docker_envs:24.04-jazzy",
        "State": "running",
        "Status": "Up 9 hours",
        "CreatedAt": "2026-09-12 07:00:00 +0200 CEST",
        "RunningFor": "9 hours ago",
        "Ports": "0.0.0.0:8080->80/tcp",
        "Size": "38.5GB (virtual 87.6GB)",
    },
]

STUB = '''#!/usr/bin/env python3
"""Stub docker: records argv and replies with canned listings."""
import json
import os
import sys

argv = sys.argv[1:]
with open(os.environ["DOCKER_STUB_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(argv) + "\\n")

fail = os.environ.get("DOCKER_STUB_FAIL", "")
if fail and fail in " ".join(argv):
    sys.stderr.write("Error response from daemon: no such container\\n")
    sys.exit(1)

data = json.loads(os.environ["DOCKER_STUB_DATA"])
if argv[:3] == ["image", "ls", "--all"] and "--filter" in argv:
    print("3a688ca3926e")
elif argv[:2] == ["image", "ls"]:
    for row in data["images"]:
        print(json.dumps(row))
elif argv[:2] == ["image", "inspect"]:
    print(data.get("label", ""))
elif argv[0] == "ps":
    for row in data["containers"]:
        print(json.dumps(row))
else:
    pass
'''


class StubDockerTest(unittest.TestCase):
    """Base class providing a recorded, canned ``docker``."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)

        stub = directory / "docker"
        stub.write_text(STUB)
        stub.chmod(0o755)

        self.log = directory / "argv.log"
        self.original = os.environ.copy()
        self.addCleanup(lambda: os.environ.update(self.original) or None)
        os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ['PATH']}"
        os.environ["DOCKER_STUB_LOG"] = str(self.log)
        os.environ["DOCKER_STUB_DATA"] = json.dumps(
            {"images": IMAGE_ROWS, "containers": CONTAINER_ROWS, "label": "run_env.sh -b -v jazzy"}
        )
        os.environ.pop("DOCKER_STUB_FAIL", None)
        self.docker = DockerCli()

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines() if line]


class ParsingTests(unittest.TestCase):
    def test_sizes_become_bytes_for_sorting(self):
        self.assertEqual(parse_size("130GB"), 130 * 10**9)
        self.assertEqual(parse_size("512MB"), 512 * 10**6)
        # ps reports two numbers; the first one is the container's own size.
        self.assertEqual(parse_size("38.5GB (virtual 87.6GB)"), 38.5 * 10**9)

    def test_unreadable_sizes_sort_as_zero(self):
        for text in ("N/A", "", "unknown"):
            self.assertEqual(parse_size(text), 0.0)

    def test_docker_timestamps_are_parsed_despite_the_zone_name(self):
        self.assertGreater(parse_timestamp("2026-09-12 12:45:48 +0200 CEST"), 0)
        self.assertGreater(
            parse_timestamp("2026-09-12 12:45:48 +0200 CEST"),
            parse_timestamp("2026-09-11 12:45:48 +0200 CEST"),
        )

    def test_unreadable_timestamps_sort_as_zero(self):
        for text in ("", "nonsense", "2026-09-12"):
            self.assertEqual(parse_timestamp(text), 0.0)

    def test_an_image_reference_falls_back_to_the_id_when_untagged(self):
        tagged = ImageInfo("abc", "docker_envs", "24.04-jazzy", "", "", "", "")
        self.assertEqual(tagged.reference, "docker_envs:24.04-jazzy")
        self.assertFalse(tagged.dangling)

        dangling = ImageInfo("abc123", "<none>", "<none>", "", "", "", "")
        self.assertEqual(dangling.reference, "abc123")
        self.assertTrue(dangling.dangling)

    def test_only_live_states_count_as_running(self):
        for state in ("running", "restarting", "paused"):
            self.assertTrue(ContainerInfo("i", "n", "img", state, "", "", "", "", "").running)
        for state in ("exited", "created", "dead", "removing"):
            self.assertFalse(ContainerInfo("i", "n", "img", state, "", "", "", "", "").running)


class ListingTests(StubDockerTest):
    def test_images_are_read_and_flagged(self):
        images = self.docker.images()
        self.assertEqual(
            [image.repository for image in images][:2], ["docker_envs", "docker_envs/ros"]
        )
        self.assertTrue(images[0].built_here, "the label filter marks this tool's images")
        self.assertFalse(images[1].built_here)
        self.assertTrue(images[2].dangling)

    def test_images_asks_for_all_images_and_for_the_label_filter(self):
        self.docker.images()
        calls = self.calls()
        self.assertIn("--all", calls[0])
        self.assertIn(f"label={BUILD_COMMAND_LABEL}", calls[1])

    def test_containers_are_read_running_first(self):
        containers = self.docker.containers()
        self.assertEqual([c.name for c in containers], ["alpha", "zulu"])
        self.assertTrue(containers[0].running)
        self.assertEqual(containers[0].ports, "0.0.0.0:8080->80/tcp")
        self.assertEqual(containers[1].created_since, "9 hours ago")

    def test_containers_asks_for_stopped_ones_too(self):
        self.docker.containers()
        self.assertIn("--all", self.calls()[0])

    def test_a_malformed_line_does_not_lose_the_listing(self):
        os.environ["DOCKER_STUB_DATA"] = json.dumps(
            {"images": IMAGE_ROWS, "containers": CONTAINER_ROWS, "label": ""}
        )
        self.assertEqual(len(self.docker.images()), 3)

    def test_the_build_command_label_is_read_back(self):
        self.assertEqual(
            self.docker.build_command("docker_envs:24.04-jazzy"), "run_env.sh -b -v jazzy"
        )
        self.assertIn(BUILD_COMMAND_LABEL, " ".join(self.calls()[-1]))

    def test_an_image_without_the_label_reports_nothing(self):
        os.environ["DOCKER_STUB_DATA"] = json.dumps(
            {"images": [], "containers": [], "label": "<no value>"}
        )
        self.assertEqual(self.docker.build_command("alpine"), "")


class ActionTests(StubDockerTest):
    def test_stop_and_restart_name_the_container(self):
        self.docker.stop("alpha")
        self.docker.restart("alpha")
        self.assertEqual(
            self.calls(), [["container", "stop", "alpha"], ["container", "restart", "alpha"]]
        )

    def test_remove_forces_only_when_asked(self):
        self.docker.remove("zulu")
        self.docker.remove("alpha", force=True)
        self.assertEqual(
            self.calls(),
            [["container", "rm", "zulu"], ["container", "rm", "--force", "alpha"]],
        )

    def test_a_failing_action_raises_with_docker_s_own_message(self):
        os.environ["DOCKER_STUB_FAIL"] = "ghost"
        with self.assertRaises(DockerError) as raised:
            self.docker.remove("ghost")
        self.assertIn("no such container", str(raised.exception))

    def test_a_missing_docker_is_reported_not_crashed(self):
        with self.assertRaises(DockerError) as raised:
            DockerCli(executable="docker-that-does-not-exist").containers()
        self.assertIn("not installed", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
