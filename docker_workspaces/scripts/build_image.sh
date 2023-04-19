#!/bin/bash -e

echo "Building Docker image from: $1 with argument: $2 and Image name: $3"
# export DOCKER_BUILD_OPTS="--cpu-period=100000 --cpu-quota=400000"
docker build -f $1 --network host -t $3 --build-arg BASE_IMAGE=$2 .
