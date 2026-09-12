"""Entry point for ``python -m docker_envs_gui``."""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
