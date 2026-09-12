"""Reading and steering the local Docker state.

The builder's own work goes through stages.sh; this is the separate, read-mostly
view of what that work left behind — which images exist and which containers are
running. Everything shells out to the ``docker`` CLI rather than talking to the
daemon socket, so it behaves exactly like the commands in the project's docs and
needs no extra dependency.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from dataclasses import dataclass

# Reads are quick; an action on a container can take as long as its stop timeout.
READ_TIMEOUT = 30
ACTION_TIMEOUT = 120

# Written onto every final image by stages::build_plan.
BUILD_COMMAND_LABEL = "org.docker_envs.build-command"

# States in which a container is doing something and can be stopped.
LIVE_STATES = frozenset({"running", "restarting", "paused"})


class DockerError(RuntimeError):
    """A docker command failed or could not be run."""


@dataclass(frozen=True)
class ImageInfo:
    """One row of ``docker image ls``."""

    image_id: str
    repository: str
    tag: str
    created: str
    created_since: str
    size: str
    containers: str
    built_here: bool = False

    @property
    def reference(self) -> str:
        if self.repository == "<none>" or self.tag == "<none>":
            return self.image_id
        return f"{self.repository}:{self.tag}"

    @property
    def dangling(self) -> bool:
        return self.repository == "<none>"


@dataclass(frozen=True)
class ContainerInfo:
    """One row of ``docker ps -a``."""

    container_id: str
    name: str
    image: str
    state: str
    status: str
    created: str
    created_since: str
    ports: str
    size: str

    @property
    def running(self) -> bool:
        return self.state in LIVE_STATES


# Docker prints human sizes ("80.8GB", "38.5GB (virtual 87.6GB)"), which sort
# wrongly as text. Parsing them to bytes is only for ordering a column.
_UNITS = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}
_SIZE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?B)", re.IGNORECASE)


def parse_size(text: str) -> float:
    """Bytes for a docker size string; 0 when it cannot be read."""
    match = _SIZE.match(text or "")
    if not match:
        return 0.0
    return float(match.group(1)) * _UNITS[match.group(2).upper()]


def parse_timestamp(text: str) -> float:
    """Epoch seconds for docker's CreatedAt; 0 when it cannot be read.

    Docker prints "2026-09-12 12:45:48 +0200 CEST" — a trailing zone *name* that
    %z cannot parse, so only the first three fields are used.
    """
    parts = (text or "").split()
    if len(parts) < 3:
        return 0.0
    try:
        return datetime.strptime(" ".join(parts[:3]), "%Y-%m-%d %H:%M:%S %z").timestamp()
    except ValueError:
        return 0.0


def _rows(output: str) -> list[dict]:
    """Parse ``--format '{{json .}}'`` output, one object per line."""
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A malformed line is not worth failing a whole listing over.
            continue
    return rows


class DockerCli:
    """Thin wrapper over the docker command line."""

    def __init__(self, executable: str = "docker"):
        self.executable = executable

    def _run(self, args: list[str], timeout: int = READ_TIMEOUT) -> str:
        try:
            result = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise DockerError(f"{self.executable} is not installed or not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerError(f"docker {' '.join(args)} timed out") from exc
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise DockerError(message or f"docker {' '.join(args)} failed")
        return result.stdout

    # ----- listings ------------------------------------------------------------- #

    def images(self) -> list[ImageInfo]:
        """Every image, newest first, flagging the ones this tool built."""
        listing = _rows(self._run(["image", "ls", "--all", "--format", "{{json .}}"]))
        # docker image ls cannot print labels, but it can filter on them, so one
        # extra call is enough to mark this project's own images.
        try:
            ours = {
                line.strip()
                for line in self._run(
                    [
                        "image",
                        "ls",
                        "--all",
                        "--filter",
                        f"label={BUILD_COMMAND_LABEL}",
                        "--format",
                        "{{.ID}}",
                    ]
                ).splitlines()
                if line.strip()
            }
        except DockerError:
            ours = set()

        return [
            ImageInfo(
                image_id=row.get("ID", ""),
                repository=row.get("Repository", ""),
                tag=row.get("Tag", ""),
                created=row.get("CreatedAt", ""),
                created_since=row.get("CreatedSince", ""),
                size=row.get("Size", ""),
                containers=row.get("Containers", ""),
                built_here=row.get("ID", "") in ours,
            )
            for row in listing
        ]

    def build_command(self, image: str) -> str:
        """The replay command stored on an image, or empty when it has none."""
        try:
            value = self._run(
                [
                    "image",
                    "inspect",
                    "-f",
                    f'{{{{index .Config.Labels "{BUILD_COMMAND_LABEL}"}}}}',
                    image,
                ]
            ).strip()
        except DockerError:
            return ""
        return "" if value in {"", "<no value>"} else value

    def containers(self) -> list[ContainerInfo]:
        """Every container, running ones first."""
        rows = _rows(self._run(["ps", "--all", "--size", "--format", "{{json .}}"]))
        containers = [
            ContainerInfo(
                container_id=row.get("ID", ""),
                name=row.get("Names", ""),
                image=row.get("Image", ""),
                state=row.get("State", ""),
                status=row.get("Status", ""),
                created=row.get("CreatedAt", ""),
                # RunningFor is time since creation, for stopped ones too.
                created_since=row.get("RunningFor", ""),
                ports=row.get("Ports", ""),
                size=row.get("Size", ""),
            )
            for row in rows
        ]
        containers.sort(key=lambda container: (not container.running, container.name.lower()))
        return containers

    # ----- actions ---------------------------------------------------------------- #

    def stop(self, name: str) -> None:
        self._run(["container", "stop", name], timeout=ACTION_TIMEOUT)

    def restart(self, name: str) -> None:
        self._run(["container", "restart", name], timeout=ACTION_TIMEOUT)

    def remove(self, name: str, force: bool = False) -> None:
        """Remove a container. *force* also kills it if it is still running."""
        args = ["container", "rm"]
        if force:
            args.append("--force")
        self._run([*args, name], timeout=ACTION_TIMEOUT)
