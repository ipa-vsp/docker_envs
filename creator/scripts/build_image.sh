#!/bin/bash -e

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <dockerfile> <base_image> <image_name> [additional build args...]" >&2
    exit 1
fi

ON_EXIT=()
function cleanup {
    for command in "${ON_EXIT[@]}"
    do
        $command &>/dev/null
    done
}
trap cleanup EXIT

DOCKERFILE="$1"
BASE_IMAGE="$2"
IMAGE_NAME="$3"
shift 3
EXTRA_BUILD_ARGS=("$@")

# The layer Dockerfiles COPY from paths like `creator/scripts/bashrc`, so the
# build context has to be the repository root regardless of the caller's cwd.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd )"
BUILD_CONTEXT="${BUILD_CONTEXT:-${REPO_ROOT}}"

# Cap the build at the available CPUs; the previous hard-coded 0-11 cpuset fails
# on machines with fewer cores.
CPUSET_ARGS=()
if [ -n "${DOCKER_BUILD_CPUSET:-}" ]; then
    CPUSET_ARGS=(--cpuset-cpus="${DOCKER_BUILD_CPUSET}")
fi

echo "Building Docker image from: ${DOCKERFILE} with base: ${BASE_IMAGE} and Image name: ${IMAGE_NAME}"
docker build "${CPUSET_ARGS[@]}" \
             -f "${DOCKERFILE}" \
             --network host \
             -t "${IMAGE_NAME}" \
             --build-arg BASE_IMAGE="${BASE_IMAGE}" \
             "${EXTRA_BUILD_ARGS[@]}" \
             "${BUILD_CONTEXT}"
