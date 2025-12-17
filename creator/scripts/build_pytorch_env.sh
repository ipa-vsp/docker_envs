#!/bin/bash

# Set strict error handling
set -euo pipefail

# Get the directory of the script
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# Repository root is two directories up from this script
REPO_ROOT="$(cd "${ROOT_DIR}/../.." >/dev/null 2>&1 && pwd)"

# Helper functions
print_warning() {
    echo -e "\033[33mWARNING: $1\033[0m"
}

print_info() {
    echo -e "\033[32mINFO: $1\033[0m"
}

cleanup() {
    for command in "${ON_EXIT[@]:-}"; do
        $command &>/dev/null || true
    done
}
trap cleanup EXIT

print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -o <os_version>     OS version (default: 24.04)"
    echo "  -t <torch_version>  PyTorch version (default: 2.8.0)"
    echo "  -tv <vision_version> torchvision version (optional)"
    echo "  -ta <audio_version> torchaudio version (optional)"
    echo "  -m <mujoco_version> MuJoCo version (default: 3.4.0)"
    echo "  -g <gym_version>    Gymnasium version (default: 1.2.0)"
    echo "  -c <cuda_version>   CUDA version (default: 12.8.0)"
    echo "  -i <image_name>     Docker image name (required)"
    echo "  -w <workspace_path> Path to the workspace (required)"
    echo "  -h                  Show this help message"
    exit 1
}

# Default values
OS_VERSION="24.04"
TORCH_VERSION="2.8.0"
TORCHVISION_VERSION=""
TORCHAUDIO_VERSION=""
MUJOCO_VERSION="3.4.0"
GYM_VERSION="1.2.0"
CUDA_VERSION="12.8.0"
IMAGE_NAME=""
WORKSPACE_PATH=""

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -o) OS_VERSION="$2"; shift 2;;
        -t) TORCH_VERSION="$2"; shift 2;;
        -tv) TORCHVISION_VERSION="$2"; shift 2;;
        -ta) TORCHAUDIO_VERSION="$2"; shift 2;;
        -m) MUJOCO_VERSION="$2"; shift 2;;
        -g) GYM_VERSION="$2"; shift 2;;
        -c) CUDA_VERSION="$2"; shift 2;;
        -i) IMAGE_NAME="$2"; shift 2;;
        -h) print_help;;
        *) print_warning "Unknown option $1"; print_help;;
    esac
done

case $CUDA_VERSION in
  12.8.0) TORCH_INDEX_URL="https://download.pytorch.org/whl/cu128" ;;
  12.6.0) TORCH_INDEX_URL="https://download.pytorch.org/whl/cu126" ;;
  11.8.0) TORCH_INDEX_URL="https://download.pytorch.org/whl/cu118" ;;
  *) echo "Unsupported CUDA version for PyTorch: $CUDA_VERSION" && exit 1 ;;
esac

print_info "Building Docker image: ${IMAGE_NAME}"
docker build \
    --build-arg BASE_IMAGE=nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${OS_VERSION} \
    --build-arg TORCH_VERSION=${TORCH_VERSION} \
    --build-arg TORCHVISION_VERSION=${TORCHVISION_VERSION} \
    --build-arg TORCHAUDIO_VERSION=${TORCHAUDIO_VERSION} \
    --build-arg MUJOCO_VERSION=${MUJOCO_VERSION} \
    --build-arg GYM_VERSION=${GYM_VERSION} \
    --build-arg TORCH_INDEX_URL=${TORCH_INDEX_URL} \
    --file ${REPO_ROOT}/creator/pytorch/Dockerfile \
    --tag ${IMAGE_NAME} \
    ${REPO_ROOT}
