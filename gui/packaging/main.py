"""PyInstaller entry point.

``docker_envs_gui/__main__.py`` uses relative imports, which do not resolve when
a file is handed to PyInstaller as a script, so the frozen build starts here.
"""

import sys

from docker_envs_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
