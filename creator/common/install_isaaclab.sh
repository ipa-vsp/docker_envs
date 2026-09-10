#!/usr/bin/env bash
# Invoked at build time after cloning the selected Isaac Lab ref.
set -euo pipefail
: "${ISAACLAB_DIR:=/opt/IsaacLab}" "${ISAAC_VENV:=/opt/isaac-venv}"
: "${ISAACLAB_METHOD:=python-env}" "${ISAACLAB_INSTALL:=default}"

if [[ ",$ISAACLAB_INSTALL," == *,isaacsim,* ]]; then
    echo "Install Isaac Sim in its own layer and select python-env; omit the isaacsim selector." >&2
    exit 1
fi

case "$ISAACLAB_METHOD" in
    legacy)
        # The Kit-less path is supported by the 3.x Python installer.
        if [[ ! -d "$ISAACLAB_DIR/source/isaaclab/isaaclab/cli" ]]; then
            echo "Kit-less installation requires Isaac Lab 3.x; use python-env with Isaac Sim for 2.x." >&2
            exit 1
        fi
        uv venv --python 3.12 --seed "$ISAAC_VENV"
        ;;
    python-env)
        if [[ ! -x "$ISAAC_VENV/bin/python" ]]; then
            echo "python-env requires the Isaac Sim layer at $ISAAC_VENV." >&2
            exit 1
        fi
        "$ISAAC_VENV/bin/python" -c 'from importlib.metadata import version; print("Isaac Sim:", version("isaacsim"))'
        ;;
    *) echo "Unknown Isaac Lab method: $ISAACLAB_METHOD" >&2; exit 1 ;;
esac
source "$ISAAC_VENV/bin/activate"
if [[ -d "$ISAACLAB_DIR/source/isaaclab/isaaclab/cli" ]]; then
    python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Isaac Lab 3.x requires Python 3.12"'
fi
uv pip install --upgrade pip
cd "$ISAACLAB_DIR"
# A missing selector has upstream's documented default meaning. Do not pass
# the literal word "default", and preserve comma/bracket selectors as one arg.
args=(-i)
if [[ "$ISAACLAB_INSTALL" != default ]]; then
    args+=("$ISAACLAB_INSTALL")
fi
./isaaclab.sh "${args[@]}"
