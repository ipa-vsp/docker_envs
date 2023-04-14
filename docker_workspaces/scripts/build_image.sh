#!/bin/bash -e

echo "Building Docker image from: $1 with argument: $2 and Image name: $3"

docker build -f $1 --network host -t $3 --build-arg BASE_IMAGE=$2 .
