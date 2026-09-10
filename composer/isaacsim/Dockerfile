# syntax=docker/dockerfile:1
FROM ghcr.io/ipa-vsp/docker_envs:24.04-jazzy
USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        sudo \
        tmux \
        vim \
        wget \
        ros-dev-tools \
        python3-colcon-common-extensions \
        python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

# Install shared tooling before personalized account setup.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_UNMANAGED_INSTALL=1 sh \
    && uv --version

ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

# Apply the requested IDs before creating user-owned wheels and caches.
RUN --mount=type=bind,source=creator/common/create_user.sh,target=/tmp/create_user.sh \
    bash /tmp/create_user.sh
ENV HOME=/home/${USERNAME}
ENV USERNAME=${USERNAME} USER_UID=${USER_UID} USER_GID=${USER_GID}

ENV VIRTUAL_ENV=/home/${USERNAME}/colcon_ws/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

USER $USERNAME
WORKDIR /home/${USERNAME}/colcon_ws

RUN --mount=type=cache,id=isaacsim-uv-${USER_UID}-${USER_GID},target=/home/${USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID},sharing=locked \
    uv venv --python 3.12 --seed $VIRTUAL_ENV \
    && uv pip install --upgrade pip \
    && uv pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu130 \
    && uv pip install mujoco-usd-converter==0.2.0 \
    && uv pip install "isaacsim[all,extscache]==6.0.1.0" --extra-index-url https://pypi.nvidia.com

# Pre-create the Omniverse cache directories while running as ${USERNAME}.
# A named volume inherits ownership from the image path it covers, but ONLY if
# that path already exists; otherwise docker creates it root-owned and the
# container (which runs as ${USERNAME}) cannot write to it, leaving every cache
# silently empty and shaders recompiling on each start. See compose.yml.
RUN mkdir -p /home/${USERNAME}/.cache/ov \
             /home/${USERNAME}/.cache/pip \
             /home/${USERNAME}/.cache/nvidia/GLCache \
             /home/${USERNAME}/.nv/ComputeCache \
             /home/${USERNAME}/.nvidia-omniverse/logs \
             /home/${USERNAME}/.nvidia-omniverse/config \
             /home/${USERNAME}/.local/share/ov/data \
             /home/${USERNAME}/Documents \
             ${VIRTUAL_ENV}/lib/python3.12/site-packages/isaacsim/kit/cache

COPY --chmod=0755 creator/scripts/workspace-entrypoint.sh /usr/local/bin/scripts/workspace-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/scripts/workspace-entrypoint.sh"]
CMD ["/bin/bash"]
