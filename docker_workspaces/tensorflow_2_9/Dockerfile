FROM tensorflow/tensorflow:2.9.0-gpu

ARG DEBIAN_FRONTEND=noninteractive

# Install apt dependencies
RUN apt-get update && apt-get install -y \
    git \
    gpg-agent \
    python3-cairocffi \
    protobuf-compiler \
    python3-pil \
    python3-lxml \
    python3-tk \
    wget \
    protobuf-compiler

RUN useradd -ms /bin/bash tensorflow
USER tensorflow
WORKDIR /home/tensorflow

RUN git clone https://github.com/tensorflow/models

RUN cd models/research && protoc object_detection/protos/*.proto --python_out=. && cp object_detection/packages/tf2/setup.py . && python -m pip install .

ENV TF_CPP_MIN_LOG_LEVEL 3
