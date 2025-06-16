ARG BASE_IMAGE
ARG ROS_DISTRO=
FROM ${BASE_IMAGE}

ENV ROS_DISTRO $ROS_DISTRO
ARG MUJOCO_VERSION=3.3.0
ARG CPU_ARCH=x86_64

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Configure base dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y python3-pip wget libglfw3-dev


# Configure and install MuJoCo
ENV MUJOCO_VERSION=${MUJOCO_VERSION}
ENV MUJOCO_DIR="/opt/mujoco/mujoco-${MUJOCO_VERSION}"
RUN mkdir -p ${MUJOCO_DIR}

RUN wget https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz
RUN mkdir -p /home/mujoco
RUN tar -xzf "mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz" -C $(dirname "${MUJOCO_DIR}")
