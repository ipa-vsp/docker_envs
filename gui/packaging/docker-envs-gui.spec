# PyInstaller build of the docker_envs image builder.
#
# The bundle carries a copy of creator/ so the AppImage is a complete builder
# rather than a form that needs a checkout beside it. repo.py prefers a real
# checkout when it can find one and falls back to this copy otherwise.
#
# Build with:  pyinstaller --noconfirm gui/packaging/docker-envs-gui.spec

import os
from pathlib import Path

# SPECPATH is set by PyInstaller to the directory holding this file.
PACKAGING = Path(SPECPATH).resolve()
GUI = PACKAGING.parent
REPO = GUI.parent

# Everything a `docker build` from this repository reads. The Dockerfiles COPY
# from paths like creator/scripts/bashrc, and build_image.sh uses the repository
# root as the build context, so the tree has to keep its shape.
BUNDLED_REPO = [
    (str(REPO / "creator"), "docker_envs/creator"),
    (str(REPO / ".dockerignore"), "docker_envs"),
]

datas = BUNDLED_REPO + [
    (str(GUI / "docker_envs_gui" / "resources"), "docker_envs_gui/resources"),
]

# Qt ships far more than a form and a log view need. Dropping these keeps the
# AppImage close to 100 MB instead of several hundred.
excludes = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNfc", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSpatialAudio", "PySide6.QtSql",
    "PySide6.QtStateMachine", "PySide6.QtTest", "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
    # Nothing in the app does numerics, plotting or notebooks.
    "matplotlib", "numpy", "pandas", "scipy", "tkinter", "IPython", "pytest",
]

block_cipher = None

a = Analysis(
    [str(PACKAGING / "main.py")],
    pathex=[str(GUI)],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg"],  # used to draw the window icon
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="docker-envs-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="docker-envs-gui",
)
