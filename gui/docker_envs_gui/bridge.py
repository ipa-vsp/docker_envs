"""Thin client for ``creator/scripts/lib/query.sh``.

Every question about what is valid, what a stack will be named and which layers
it needs is answered by stages.sh through the bridge script. Nothing in this
module encodes build rules; it only turns unit-separated records into objects.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .model import Plan, PlanLayer, Selection

US = "\x1f"

# Planning is local and instant. Version discovery is curl/git ls-remote with
# stages.sh's own 20 s timeout and three retries, so it needs a lot more room.
PLAN_TIMEOUT = 30
LOOKUP_TIMEOUT = 120


class BridgeError(RuntimeError):
    """The bridge script could not be run at all."""


@dataclass
class RosOption:
    """One ROS distro offered for the selected Ubuntu release."""

    distro: str
    in_ci: bool = False
    frozen: bool = False
    note: str = ""


@dataclass
class Defaults:
    """stages.sh's offline fallbacks and its initial selection."""

    fallbacks: dict[str, str] = field(default_factory=dict)
    selection: dict[str, str] = field(default_factory=dict)
    supported_os: list[str] = field(default_factory=list)


@dataclass
class DockerStatus:
    """What the preflight check found."""

    client: bool = False
    daemon: bool = False
    buildx: bool = False
    detail: str = ""

    @property
    def ready(self) -> bool:
        return self.client and self.daemon and self.buildx


class Bridge:
    """Runs query.sh inside a docker_envs checkout."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.script = self.repo_root / "creator/scripts/lib/query.sh"

    # ----- plumbing --------------------------------------------------------- #

    def _run(
        self,
        args: list[str],
        extra_env: dict[str, str] | None = None,
        timeout: int = PLAN_TIMEOUT,
    ) -> list[list[str]]:
        env = dict(os.environ)
        # A DEG_* left over from a previous call would silently re-enter the
        # selection, so the namespace is cleared before each run.
        for name in [key for key in env if key.startswith("DEG_")]:
            del env[name]
        env.update(extra_env or {})
        try:
            result = subprocess.run(
                ["bash", str(self.script), *args],
                cwd=self.repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:  # no bash, or the script is missing
            raise BridgeError(f"Cannot run {self.script}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise BridgeError(f"query.sh {' '.join(args)} timed out") from exc
        if result.returncode not in (0, 1):
            raise BridgeError(result.stderr.strip() or f"query.sh {args[0]} failed")
        return [line.split(US) for line in result.stdout.splitlines() if line]

    # ----- questions -------------------------------------------------------- #

    def plan(self, selection: Selection) -> Plan:
        """Validate a selection and derive its image name, layers and command."""
        plan = Plan()
        for record in self._run(["plan"], extra_env=selection.env()):
            kind = record[0]
            if kind == "ERROR":
                plan.errors.append(record[1])
            elif kind == "WARN":
                plan.warnings.append(record[1])
            elif kind == "IMAGE":
                plan.image = record[1]
            elif kind == "REPLAY":
                plan.replay = record[1]
            elif kind == "ISAACLAB_EFFECTIVE":
                plan.isaaclab_method, plan.isaaclab_packages = record[1], record[2]
            elif kind == "LAYER":
                plan.layers.append(
                    PlanLayer(
                        index=int(record[1]),
                        dockerfile=record[2],
                        base=record[3],
                        image=record[4],
                        args=list(record[5:]),
                    )
                )
        return plan

    def versions(self, kind: str, os_version: str | None = None, limit: int = 8) -> list[str]:
        """Newest-first releases for one layer. Empty when the lookup failed."""
        args = ["versions", kind]
        if kind == "cuda":
            args += [os_version or "", str(limit)]
        else:
            args.append(str(limit))
        return [record[0] for record in self._run(args, timeout=LOOKUP_TIMEOUT)]

    def branches(self, limit: int = 4) -> list[str]:
        return [
            record[0] for record in self._run(["branches", str(limit)], timeout=LOOKUP_TIMEOUT)
        ]

    def ros_for_os(self, os_version: str) -> list[RosOption]:
        options = []
        for record in self._run(["ros-for-os", os_version]):
            flags = record[1].split(",") if len(record) > 1 and record[1] else []
            options.append(
                RosOption(
                    distro=record[0],
                    in_ci="ci" in flags,
                    frozen="frozen" in flags,
                    note=record[2] if len(record) > 2 else "",
                )
            )
        return options

    def isaaclab_selectors(self, version: str) -> dict[str, str]:
        """Framework name -> the package selector for this Isaac Lab version."""
        return {record[0]: record[1] for record in self._run(["isaaclab-selectors", version])}

    def defaults(self) -> Defaults:
        out = Defaults()
        for record in self._run(["defaults"]):
            if record[0] == "DEFAULT":
                out.fallbacks[record[1]] = record[2]
            elif record[0] == "SELECTION":
                out.selection[record[1]] = record[2]
            elif record[0] == "SUPPORTED_OS":
                out.supported_os = record[1].split()
        return out

    # ----- preflight -------------------------------------------------------- #

    def docker_status(self) -> DockerStatus:
        """Check what build_image.sh will need before the user presses Build."""
        status = DockerStatus()
        if shutil.which("docker") is None:
            status.detail = "docker is not on PATH"
            return status
        status.client = True

        def probe(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=15)

        try:
            info = probe("info", "--format", "{{.ServerVersion}}")
            status.daemon = info.returncode == 0
            if not status.daemon:
                status.detail = "docker daemon is not reachable"
                return status
            # build_image.sh refuses to run without it, so surface it up front.
            status.buildx = probe("buildx", "version").returncode == 0
            status.detail = (
                f"Docker {info.stdout.strip()}" if status.buildx else "docker buildx is missing"
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            status.detail = str(exc)
        return status
