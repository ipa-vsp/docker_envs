#!/bin/bash -e

ON_EXIT=()
function cleanup {
    for command in "${ON_EXIT[@]}"
    do
        $command &>/dev/null
    done
}
trap cleanup EXIT

echo "Building Docker image from: $1 with argument: $2 and Image name: $3"
# export DOCKER_BUILD_OPTS="--cpu-period=100000 --cpu-quota=400000"
docker build --cpuset-cpus=0-11 -f $1 --network host -t $3 --build-arg BASE_IMAGE=$2 .
