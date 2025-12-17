ARG BASE_IMAGE
ARG ROS_DISTRO=
FROM ${BASE_IMAGE}

ENV ROS_DISTRO $ROS_DISTRO
ARG MUJOCO_VERSION=3.4.0
ARG CPU_ARCH=x86_64

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Base system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    python3-pip \
    python3-venv \
    wget \
    libglfw3-dev \
    git

# Setup virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip

# Install PyTorch with CUDA 12.6
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Install Gymnasium and Stable-Baselines3
RUN pip install gymnasium stable-baselines3

# Install MuJoCo
ENV MUJOCO_VERSION=${MUJOCO_VERSION}
ENV MUJOCO_DIR="/opt/mujoco/mujoco-${MUJOCO_VERSION}"
RUN mkdir -p ${MUJOCO_DIR}
RUN wget https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz
RUN tar -xzf "mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz" -C $(dirname "${MUJOCO_DIR}")
