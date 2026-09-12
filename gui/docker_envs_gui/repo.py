"""Locating the docker_envs checkout the GUI drives.

The app is only a form: the Dockerfiles, the stage library and the build scripts
all live in the repository. When the GUI runs from a checkout that repository is
the one above this file, but a packaged build (AppImage) carries its own copy, so
the location has to be resolved rather than assumed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Every consumer needs these three; their presence is what makes a directory a
# usable docker_envs root.
REQUIRED = (
    "creator/scripts/lib/stages.sh",
    "creator/scripts/lib/query.sh",
    "creator/scripts/run_env.sh",
)

ENV_VAR = "DOCKER_ENVS_ROOT"


class RepoError(RuntimeError):
    """Raised when no usable docker_envs root can be found."""


def is_repo_root(path: Path) -> bool:
    """True when *path* contains everything the GUI needs to build an image."""
    return all((path / relative).is_file() for relative in REQUIRED)


def _bundled_root() -> Path | None:
    """The copy of ``creator/`` shipped inside a PyInstaller/AppImage build."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is None:
        return None
    candidate = Path(bundle) / "docker_envs"
    return candidate if is_repo_root(candidate) else None


def _checkout_root() -> Path | None:
    """Walk up from this file looking for the checkout it was installed from."""
    for parent in Path(__file__).resolve().parents:
        if is_repo_root(parent):
            return parent
    return None


def resolve(explicit: str | os.PathLike[str] | None = None, saved: str | None = None) -> Path:
    """Resolve the active repository root.

    Order: explicit argument, ``DOCKER_ENVS_ROOT``, the value saved in settings,
    the checkout this package lives in, then the bundled copy. The first
    candidate that looks like a docker_envs root wins; an explicit one that does
    not is an error rather than a silent fallback.
    """
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
        if not is_repo_root(path):
            raise RepoError(f"Not a docker_envs checkout: {path}")
        return path

    from_env = os.environ.get(ENV_VAR)
    if from_env:
        path = Path(from_env).expanduser().resolve()
        if not is_repo_root(path):
            raise RepoError(f"{ENV_VAR} is not a docker_envs checkout: {path}")
        return path

    for candidate in (
        Path(saved).expanduser().resolve() if saved else None,
        _checkout_root(),
        _bundled_root(),
    ):
        if candidate is not None and is_repo_root(candidate):
            return candidate

    raise RepoError(
        "No docker_envs checkout found. Pass --repo-root /path/to/docker_envs "
        f"or set {ENV_VAR}."
    )
