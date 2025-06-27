# Dockerfile for PyTorch + MuJoCo + ROS2 Environment

# Base image setup
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

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

# Use bash shell with pipefail for safety
# Copy custom bash config (if available)
ENV DEBIAN_FRONTEND=noninteractive
# COPY creator/scripts/bashrc /etc/bash.bashrc
# RUN chmod a+rwx /etc/bash.bashrc
# ENV SHELL /bin/bash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

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
    pip3 install cmake tensorboard mujoco==${MUJOCO_VERSION} gymnasium==${GYM_VERSION}

# Conditionally install PyTorch packages
RUN source /opt/venv/bin/activate && \
    pip3 install torch==${TORCH_VERSION} torchvision${TORCHVISION_VERSION:+==${TORCHVISION_VERSION}} torchaudio${TORCHAUDIO_VERSION:+==${TORCHAUDIO_VERSION}} \
    --index-url ${TORCH_INDEX_URL}

# Setup non-root admin user
ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd -g ${USER_GID} ${USERNAME} || true && \
    useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash ${USERNAME} || true && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME} && \
    usermod -aG sudo,video ${USERNAME} && \
    mkdir -p /home/${USERNAME}/workspace && \
    chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}

# Copy entry scripts if needed
# RUN mkdir -p /usr/local/bin/scripts
# COPY creator/scripts/workspace-entrypoint.sh /usr/local/bin/scripts/
# RUN chmod +x /usr/local/bin/scripts/*.sh

# Final user setup
USER root

# Set environment for container usage
ENV USERNAME=${USERNAME} \
    USER_UID=${USER_UID} \
    USER_GID=${USER_GID}

CMD ["/bin/bash"]
