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

echo "Building Docker image from: ${DOCKERFILE} with base: ${BASE_IMAGE} and Image name: ${IMAGE_NAME}"
# export DOCKER_BUILD_OPTS="--cpu-period=100000 --cpu-quota=400000"
docker build --cpuset-cpus=0-11 \
             -f "${DOCKERFILE}" \
             --network host \
             -t "${IMAGE_NAME}" \
             --build-arg BASE_IMAGE="${BASE_IMAGE}" \
             "${EXTRA_BUILD_ARGS[@]}" \
             .
