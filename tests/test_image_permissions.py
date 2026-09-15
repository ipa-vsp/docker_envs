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

    def test_claude_and_workspace_skills_are_installed_for_development_user(self):
        result = self.docker(
            "run",
            "--rm",
            "--network=none",
            IMAGE,
            "bash",
            "-c",
            "claude --version && "
            "graphify --version && "
            'test -s "$HOME/.claude/skills/graphify/SKILL.md" && '
            'test -w "$HOME/.claude/skills/graphify/SKILL.md" && '
            'test -w "$HOME/.local/share/claude" && '
            'test -w "$HOME/colcon_ws/.claude" && '
            'git -C "$HOME/colcon_ws/.claude" remote get-url origin',
        )
        self.assertIn("Claude Code", result.stdout)
        self.assertIn("https://github.com/ipa-vsp/.claude.git", result.stdout)

    def test_interactive_banner_reports_identity_and_root_warning(self):
        for user in ("12345:23456", "0:0"):
            with self.subTest(user=user):
                result = self.docker(
                    "run",
                    "--rm",
                    "--network=none",
                    "--user",
                    user,
                    "-e",
                    "NO_COLOR=1",
                    IMAGE,
                    "bash",
                    "-ic",
                    "exit",
                )
                self.assertIn("docker_envs", result.stdout)
                self.assertIn("/home/admin/colcon_ws", result.stdout)
                self.assertNotIn("\x1b[", result.stdout)
                if user == "0:0":
                    self.assertIn("WARNING: This shell is running as root", result.stdout)
                    self.assertIn('"$(id -u):$(id -g)"', result.stdout)
                else:
                    self.assertIn("UID 12345 · GID 23456", result.stdout)
                    self.assertIn("Running as a non-root user", result.stdout)
                    self.assertNotIn("WARNING", result.stdout)

    def test_isaac_source_and_active_venv_are_writable_without_changing_system_paths(self):
        self.docker(
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
            "ISAACLAB_DIR=/opt/test-isaaclab",
            "-e",
            "ISAAC_VENV=/opt/test-venv",
            IMAGE,
            "-ec",
            'mkdir -p "$ISAACLAB_DIR/source/isaaclab/isaaclab.egg-info" '
            '"$ISAAC_VENV/lib/python3.12/site-packages/packaging.dist-info" /opt/test-system; '
            'touch "$ISAACLAB_DIR/source/isaaclab/isaaclab.egg-info/PKG-INFO" '
            '"$ISAAC_VENV/pyvenv.cfg" '
            '"$ISAAC_VENV/lib/python3.12/site-packages/packaging.dist-info/INSTALLER" '
            "/opt/test-system/probe; "
            'ln -s /opt/test-system "$ISAACLAB_DIR/system-link"; '
            'ln -s /opt/test-system "$ISAAC_VENV/system-link"; '
            "bash /tmp/create_user.sh; "
            "runuser -u admin -- bash -ec ' "
            'touch "$ISAACLAB_DIR/source/isaaclab/isaaclab.egg-info/PKG-INFO"; '
            'mkdir "$ISAACLAB_DIR/source/isaaclab/build"; '
            'rm "$ISAAC_VENV/lib/python3.12/site-packages/packaging.dist-info/INSTALLER"; '
            'touch "$ISAAC_VENV/lib/python3.12/site-packages/packaging.dist-info/INSTALLER"; '
            "test ! -w /opt/test-system/probe'; "
            'test "$(stat -c %u:%g /opt/test-system/probe)" = 0:0',
        )

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
