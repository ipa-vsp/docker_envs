"""Optional Docker smoke checks; CI supplies a freshly built account image."""

import os
from pathlib import Path
import subprocess
import unittest
import uuid

IMAGE = os.environ.get("DOCKER_ENVS_TEST_IMAGE")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(IMAGE, "Set DOCKER_ENVS_TEST_IMAGE to a UID 12345/GID 23456 user image")
class ImagePermissionsTests(unittest.TestCase):
    def docker(self, *args, check=True):
        return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)

    def test_default_account_and_workspace_are_writable(self):
        self.docker(
            "run",
            "--rm",
            "--network=none",
            IMAGE,
            "bash",
            "-c",
            'test "$(id -u)" = 12345 && test "$(id -g)" = 23456 && '
            'test -w "$HOME" && test -w "$HOME/colcon_ws" && '
            'test -w "$HOME/colcon_ws/src" && test -w "$HOME/workspace" && '
            'touch "$HOME/colcon_ws/probe"',
        )

    def test_empty_named_volume_inherits_workspace_ownership(self):
        volume = f"docker-envs-permissions-{uuid.uuid4().hex}"
        self.docker("volume", "create", volume)
        try:
            self.docker(
                "run",
                "--rm",
                "--network=none",
                "--mount",
                f"type=volume,source={volume},target=/home/admin/colcon_ws",
                IMAGE,
                "bash",
                "-c",
                'touch "$HOME/colcon_ws/probe"',
            )
        finally:
            self.docker("volume", "rm", volume)

    def test_conflicting_accounts_are_rejected(self):
        for name, uid, gid in (
            ("root", "12345", "23456"),
            ("daemon", "12345", "23456"),
            ("admin", "1", "23456"),
            ("admin", "0", "23456"),
            ("admin", "12345", "0"),
        ):
            with self.subTest(name=name, uid=uid, gid=gid):
                result = self.docker(
                    "run",
                    "--rm",
                    "--network=none",
                    "--user",
                    "0:0",
                    "--entrypoint",
                    "bash",
                    "--mount",
                    f"type=bind,source={ROOT}/creator/common/create_user.sh,target=/tmp/create_user.sh,readonly",
                    "-e",
                    f"USERNAME={name}",
                    "-e",
                    f"USER_UID={uid}",
                    "-e",
                    f"USER_GID={gid}",
                    IMAGE,
                    "/tmp/create_user.sh",
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(
                    any(
                        text in result.stderr
                        for text in ("must be", "Refusing", "already assigned")
                    ),
                    result.stderr,
                )
