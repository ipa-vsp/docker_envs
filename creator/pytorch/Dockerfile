# syntax=docker/dockerfile:1
# Dockerfile for PyTorch + MuJoCo + ROS2 Environment

# -----------------------------------------------------------------------------
# Stage 1: base image
# -----------------------------------------------------------------------------
ARG BASE_IMAGE=nvidia/cuda:12.8.0-cudnn-devel-ubuntu24.04
ARG BASE_IMAGE_MUJOCO=base
ARG BASE_IMAGE_PYTORCH=mujoco
ARG BASE_IMAGE_FINAL=pytorch

FROM ${BASE_IMAGE} AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
SHELL ["/bin/bash", "-c"]

# Install system dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
        python3-pip \
        wget \
        libglfw3-dev \
        sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Interactive configuration comes after the system dependencies.
COPY --chmod=0644 creator/pytorch/bashrc /etc/bash.bashrc

# -----------------------------------------------------------------------------
# Stage 2: install MuJoCo and Gymnasium
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE_MUJOCO} AS mujoco

ARG MUJOCO_VERSION=3.4.0
ARG CPU_ARCH=x86_64
ARG GYM_VERSION=1.2.0

# Environment variables
ENV MUJOCO_VERSION=${MUJOCO_VERSION} \
    MUJOCO_DIR=/opt/mujoco/mujoco-${MUJOCO_VERSION}

RUN mkdir -p ${MUJOCO_DIR} /home/mujoco && \
    wget https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz && \
    tar -xzf mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz -C $(dirname ${MUJOCO_DIR}) && \
    rm mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz

RUN apt-get update && \
    apt-get install -y python3-venv && \
    rm -rf /var/lib/apt/lists/* && apt-get clean && \
    python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    source /opt/venv/bin/activate && \
    pip3 install --upgrade pip && \
    pip3 install gradio tensorboard mujoco==${MUJOCO_VERSION} gymnasium==${GYM_VERSION}

# -----------------------------------------------------------------------------
# Stage 3: install PyTorch
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE_PYTORCH} AS pytorch

# Define common build-time arguments
ARG TORCH_VERSION=2.8.0
ARG TORCHVISION_VERSION
ARG TORCHAUDIO_VERSION
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    source /opt/venv/bin/activate && \
    pip3 install torch==${TORCH_VERSION} --index-url ${TORCH_INDEX_URL}
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    source /opt/venv/bin/activate && \
    pip3 install \
    torchvision${TORCHVISION_VERSION:+==${TORCHVISION_VERSION}}  --index-url ${TORCH_INDEX_URL}
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    source /opt/venv/bin/activate && \
    pip3 install \
    torchaudio${TORCHAUDIO_VERSION:+==${TORCHAUDIO_VERSION}} \
    --index-url ${TORCH_INDEX_URL}

# -----------------------------------------------------------------------------
# Stage 4: create user and final image
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE_FINAL} AS final

USER root
RUN apt-get update && apt-get install -y --no-install-recommends sudo && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000
RUN --mount=type=bind,source=creator/common/create_user.sh,target=/tmp/create_user.sh \
    bash /tmp/create_user.sh

ENV USERNAME=${USERNAME} USER_UID=${USER_UID} USER_GID=${USER_GID}
ENV HOME=/home/${USERNAME}
COPY --chmod=0755 creator/scripts/workspace-entrypoint.sh /usr/local/bin/scripts/workspace-entrypoint.sh
USER ${USERNAME}
WORKDIR /home/${USERNAME}/workspace
ENTRYPOINT ["/usr/local/bin/scripts/workspace-entrypoint.sh"]
CMD ["/bin/bash"]
