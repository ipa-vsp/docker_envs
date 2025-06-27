# Dockerfile for PyTorch + MuJoCo + ROS2 Environment

# Base image setup
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
COPY creator/scripts/bashrc /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc
ENV SHELL /bin/bash
SHELL ["/bin/bash", "-c"]

# Define build-time arguments
ARG ROS_DISTRO
ARG MUJOCO_VERSION=3.3.3
ARG CPU_ARCH=x86_64
ARG TORCH_VERSION=2.6.0
ARG TORCHVISION_VERSION
ARG TORCHAUDIO_VERSION
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ARG GYM_VERSION=1.2.0

# Environment variables
ENV ROS_DISTRO=${ROS_DISTRO} \
    MUJOCO_VERSION=${MUJOCO_VERSION} \
    MUJOCO_DIR=/opt/mujoco/mujoco-${MUJOCO_VERSION}

# Install system dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
        python3-pip \
        wget \
        libglfw3-dev \
        sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install MuJoCo
RUN mkdir -p ${MUJOCO_DIR} /home/mujoco && \
    wget https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz && \
    tar -xzf mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz -C $(dirname ${MUJOCO_DIR}) && \
    rm mujoco-${MUJOCO_VERSION}-linux-${CPU_ARCH}.tar.gz

# Install Python packages
RUN apt-get update && \
    apt-get install -y python3-venv && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip

# Update PATH to use venv Python
ENV PATH="/opt/venv/bin:$PATH"
RUN source /opt/venv/bin/activate && \
    pip3 install --upgrade pip && \
    pip3 install --no-cache-dir gradio tensorboard mujoco==${MUJOCO_VERSION} gymnasium==${GYM_VERSION}

# Conditionally install PyTorch packages
RUN source /opt/venv/bin/activate && \
    pip3 install --no-cache-dir torch==${TORCH_VERSION} \
    torchvision${TORCHVISION_VERSION:+==${TORCHVISION_VERSION}} \
    torchaudio${TORCHAUDIO_VERSION:+==${TORCHAUDIO_VERSION}} \
    --index-url ${TORCH_INDEX_URL}

# Setup non-root admin user
ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

# Install prerequisites and cleanup in a single step
RUN apt-get update && apt-get install -y sudo && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

# Ensure the group exists before creating the user
RUN if ! getent group ${USER_GID} >/dev/null 2>&1; then \
        groupadd --gid ${USER_GID} ${USERNAME}; \
    fi

# Explicitly create the home directory before adding the user
RUN mkdir -p /home/${USERNAME} && chown root:root /home/${USERNAME}

# Ensure the user exists and belongs to the correct group
RUN if ! getent passwd ${USER_UID} >/dev/null 2>&1; then \
        useradd --uid ${USER_UID} --gid ${USER_GID} -m -d /home/${USERNAME} -s /bin/bash ${USERNAME}; \
    fi

# Set proper ownership of the home directory after user creation
RUN chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}

# Ensure usermod only runs if the user exists
RUN if getent passwd ${USERNAME} >/dev/null 2>&1; then \
        usermod -aG sudo,video ${USERNAME}; \
    fi

# Ensure sudoers file is set correctly
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# Copy and set permissions for scripts
# RUN mkdir -p /usr/local/bin/scripts
# COPY creator/scripts/workspace-entrypoint.sh /usr/local/bin/scripts/
# RUN chmod +x /usr/local/bin/scripts/*.sh

# Create appropriate workspace depending on ROS_DISTRO and set permissions
RUN mkdir -p /home/${USERNAME}/workspace && \
    chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}/workspace

# Keep root as the active user for further builds
USER root

# Set Environment Variables
ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}

# Optionally switch to the user when running interactively
CMD ["/bin/bash"]