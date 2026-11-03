"""Keep bundled libraries out of external system commands."""

import os
import sys


def host_environment() -> dict[str, str]:
    """Undo PyInstaller's loader override for bash, Docker and their children."""
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
    return env
