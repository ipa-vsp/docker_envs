"""Running a build and reporting its progress.

The GUI never assembles its own docker command. It executes the exact
``run_env.sh -b ...`` string that stages::equivalent_command produced and that the
plan panel is displaying, so what the user reads is what runs, and the image ends
up with the same ``org.docker_envs.build-command`` label as a CLI build.

The build runs in its own session (``start_new_session``) so that cancelling can
signal the whole process group. Without that, terminating the shell would leave
the ``docker build`` underneath it running.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from .model import BUILD_STEP, LAYER_HEADING

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# How long a cancelled build gets to exit on SIGTERM before it is killed.
KILL_GRACE_MS = 5000


def build_environment() -> dict[str, str]:
    """Environment for the build subprocess."""
    env = dict(os.environ)
    # Without a TTY, BuildKit's default renderer still emits cursor-addressing
    # escapes; plain mode keeps the log line-oriented and readable in a QTextEdit.
    env["BUILDKIT_PROGRESS"] = "plain"
    env["DOCKER_BUILDKIT"] = "1"
    return env


class _Reader(QThread):
    """Streams a process's merged output, then reports its exit status."""

    chunk = Signal(str)
    done = Signal(int)

    def __init__(self, process: subprocess.Popen[bytes], parent: QObject | None = None):
        super().__init__(parent)
        self._process = process

    def run(self) -> None:
        stream = self._process.stdout
        if stream is not None:
            for line in iter(stream.readline, b""):
                self.chunk.emit(line.decode("utf-8", "replace"))
            stream.close()
        self.done.emit(self._process.wait())


class BuildRunner(QObject):
    """Drives one ``run_env.sh -b`` (or ``-p``) process."""

    output = Signal(str)
    layer_started = Signal(int, int, str)  # step, total, image
    step_progress = Signal(int, int)  # instruction, instructions in this layer
    started = Signal(str)  # the command line
    finished = Signal(bool, str)  # success, summary

    def __init__(self, repo_root: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.repo_root = Path(repo_root)
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: _Reader | None = None
        self._cancelled = False

    @property
    def running(self) -> bool:
        return self._process is not None

    # ----- lifecycle -------------------------------------------------------- #

    def start(self, replay_command: str, dry_run: bool = False) -> None:
        """Run *replay_command*; ``-p`` turns it into a plan-only pass."""
        if self.running:
            return
        command = f"{replay_command} -p" if dry_run else replay_command
        self._cancelled = False
        try:
            self._process = subprocess.Popen(
                ["bash", "-c", command],
                cwd=str(self.repo_root),
                env=build_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self._process = None
            self.finished.emit(False, f"Could not start the build: {exc}")
            return

        self._reader = _Reader(self._process, self)
        self._reader.chunk.connect(self._on_chunk)
        self._reader.done.connect(self._on_finished)
        self._reader.start()
        self.started.emit(command)

    def cancel(self) -> None:
        if not self.running:
            return
        self._cancelled = True
        self.output.emit("\n== Cancelling: signalling the build process group ==\n")
        self._signal_group(signal.SIGTERM)
        QTimer.singleShot(KILL_GRACE_MS, self._force_kill)

    def wait(self, timeout_ms: int = 10000) -> None:
        """Block until the reader thread has finished; for shutdown only."""
        if self._reader is not None:
            self._reader.wait(timeout_ms)

    # ----- internals -------------------------------------------------------- #

    def _signal_group(self, sig: int) -> None:
        if self._process is None:
            return
        try:
            # start_new_session makes the child a session leader, so its pid is
            # also its process group id.
            os.killpg(self._process.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def _force_kill(self) -> None:
        if self.running and self._cancelled:
            self._signal_group(signal.SIGKILL)

    def _on_chunk(self, line: str) -> None:
        self.output.emit(line)
        plain = ANSI.sub("", line).strip()
        heading = LAYER_HEADING.match(plain)
        if heading:
            self.layer_started.emit(int(heading["step"]), int(heading["total"]), heading["image"])
            return
        step = BUILD_STEP.match(plain)
        if step:
            self.step_progress.emit(int(step["done"]), int(step["total"]))

    def _on_finished(self, exit_code: int) -> None:
        self._process = None
        if self._cancelled:
            self.finished.emit(False, "Build cancelled.")
        elif exit_code == 0:
            self.finished.emit(True, "Build finished successfully.")
        elif exit_code < 0:
            self.finished.emit(False, f"Build terminated by signal {-exit_code}.")
        else:
            self.finished.emit(False, f"Build failed (exit status {exit_code}).")
