#!/usr/bin/env bash
# Build the docker_envs Image Builder AppImage.
#
# This is exactly what .github/workflows/gui-appimage.yml runs, so a failure in
# CI can be reproduced locally with one command. Artefacts land in gui/dist/.
#
# An AppImage inherits the glibc of the machine that builds it, so build on the
# oldest distribution you intend to support (CI uses ubuntu-22.04).

set -euo pipefail

PACKAGING="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
GUI="$( cd "${PACKAGING}/.." >/dev/null 2>&1 && pwd )"
REPO="$( cd "${GUI}/.." >/dev/null 2>&1 && pwd )"

DIST="${GUI}/dist"      # deliverables only: the AppImage and its checksum
WORK="${GUI}/build"     # scratch: the frozen tree, the AppDir, appimagetool
FROZEN="${WORK}/frozen"
APPDIR="${WORK}/AppDir"
APP="docker-envs-gui"
ARCH="${ARCH:-$(uname -m)}"
TOOLS="${APPIMAGETOOL_CACHE:-${WORK}/tools}"

info() { echo -e "\033[32mINFO:\033[0m $*"; }

VERSION="$(
    python3 - "${GUI}" <<'PY'
import re
import sys
from pathlib import Path

source = Path(sys.argv[1], "docker_envs_gui", "__init__.py").read_text()
print(re.search(r'__version__ = "([^"]+)"', source).group(1))
PY
)"
info "Building ${APP} ${VERSION} for ${ARCH}"

# --- 1. freeze --------------------------------------------------------------- #
rm -rf "${APPDIR}" "${FROZEN}"
mkdir -p "${DIST}"
python3 -m PyInstaller --noconfirm --clean \
    --distpath "${FROZEN}" --workpath "${WORK}/pyinstaller" \
    "${PACKAGING}/${APP}.spec"

# --- 2. assemble the AppDir --------------------------------------------------- #
info "Assembling ${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" \
         "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
cp -a "${FROZEN}/${APP}/." "${APPDIR}/usr/bin/"
install -m 0755 "${PACKAGING}/AppRun" "${APPDIR}/AppRun"
install -m 0644 "${PACKAGING}/${APP}.desktop" "${APPDIR}/${APP}.desktop"
install -m 0644 "${PACKAGING}/${APP}.desktop" "${APPDIR}/usr/share/applications/${APP}.desktop"

ICON="${GUI}/docker_envs_gui/resources/${APP}.svg"
install -m 0644 "${ICON}" "${APPDIR}/${APP}.svg"
install -m 0644 "${ICON}" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP}.svg"

# appimagetool wants a raster .DirIcon; Qt is already a dependency, so render it
# here rather than adding one.
QT_QPA_PLATFORM=offscreen python3 - "${ICON}" "${APPDIR}/.DirIcon" <<'PY'
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

source, target = sys.argv[1], sys.argv[2]
QGuiApplication([])
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
QSvgRenderer(source).render(painter)
painter.end()
if not image.save(target, "PNG"):
    raise SystemExit(f"could not write {target}")
PY

# --- 3. verify the bundled checkout ------------------------------------------- #
# The AppImage must be able to build without a docker_envs checkout on the host.
for required in creator/scripts/lib/stages.sh creator/scripts/lib/query.sh \
                creator/scripts/run_env.sh creator/common/Dockerfile.base; do
    if [[ ! -f "${APPDIR}/usr/bin/_internal/docker_envs/${required}" ]]; then
        echo "ERROR: the bundle is missing ${required}" >&2
        exit 1
    fi
done
# PyInstaller copies data without the executable bit.
chmod +x "${APPDIR}/usr/bin/_internal/docker_envs/creator/scripts/"*.sh \
         "${APPDIR}/usr/bin/_internal/docker_envs/creator/scripts/lib/"*.sh \
         "${APPDIR}/usr/bin/_internal/docker_envs/creator/common/"*.sh

# --- 4. package ---------------------------------------------------------------- #
mkdir -p "${TOOLS}"
APPIMAGETOOL="${TOOLS}/appimagetool-${ARCH}.AppImage"
if [[ ! -x "${APPIMAGETOOL}" ]]; then
    info "Fetching appimagetool"
    curl -fsSL -o "${APPIMAGETOOL}" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    chmod +x "${APPIMAGETOOL}"
fi

OUTPUT="${DIST}/${APP}-${VERSION}-${ARCH}.AppImage"
rm -f "${OUTPUT}"
# --appimage-extract-and-run: CI runners have no FUSE.
ARCH="${ARCH}" "${APPIMAGETOOL}" --appimage-extract-and-run --no-appstream \
    "${APPDIR}" "${OUTPUT}"

( cd "${DIST}" && sha256sum "$(basename "${OUTPUT}")" > "$(basename "${OUTPUT}").sha256" )

# --- 5. self-test ---------------------------------------------------------------- #
# --check resolves the bundled checkout and plans the default stack, so this
# proves the packaged tree is usable rather than merely present.
info "Self-testing the AppImage"
( cd / && APPIMAGE_EXTRACT_AND_RUN=1 QT_QPA_PLATFORM=offscreen "${OUTPUT}" --check )

info "Built ${OUTPUT}"
ls -lh "${OUTPUT}"
