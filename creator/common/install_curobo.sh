#!/usr/bin/env bash
# Invoked at build time after cloning the selected cuRobo ref.
set -euo pipefail
: "${CUROBO_DIR:=/opt/curobo}" "${VIRTUAL_ENV:=/opt/venv}" "${CUROBO_CUDA:=12}"

# The shared environment comes from Dockerfile.venv; never create another one.
if [[ ! -x "$VIRTUAL_ENV/bin/python" ]]; then
    echo "No Python environment at $VIRTUAL_ENV; build the venv layer first." >&2
    exit 1
fi
python="$VIRTUAL_ENV/bin/python"
"$python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "cuRobo is installed for Python 3.12 only; this environment has %d.%d" % sys.version_info[:2]'

if ! grep -Eq '^cu1[23] *=' "$CUROBO_DIR/pyproject.toml"; then
    echo "cuRobo ref ${CUROBO_VERSION:-?} has no cu12/cu13 extras; use main or a cuRobo 2 release." >&2
    exit 1
fi

# An installed PyTorch fixes the CUDA runtime; reuse it rather than letting
# the -torch extra replace it with a different build.
torch_cuda="$("$python" -c 'import torch; print((torch.version.cuda or "").split(".")[0])' 2>/dev/null || true)"
case "$torch_cuda" in
    12|13) extra="cu${torch_cuda}"; echo "Using the installed PyTorch (CUDA ${torch_cuda})." ;;
    "")    extra="cu${CUROBO_CUDA}-torch" ;;
    *)     echo "Installed PyTorch targets CUDA ${torch_cuda}; cuRobo supports 12 and 13." >&2; exit 1 ;;
esac
case "$extra" in
    cu12|cu13|cu12-torch|cu13-torch) ;;
    *) echo "CUROBO_CUDA must be 12 or 13, got ${CUROBO_CUDA}." >&2; exit 1 ;;
esac

cd "$CUROBO_DIR"
uv pip install --python "$python" ".[${extra}]"
"$python" -c 'from importlib.metadata import version; print("cuRobo:", version("nvidia-curobo"))'
