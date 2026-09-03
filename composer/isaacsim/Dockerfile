FROM ghcr.io/ipa-vsp/docker_envs:24.04-jazzy

ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

# RUN set -eux; \
#     if getent passwd $USER_UID >/dev/null; then \
#         userdel -r "$(getent passwd $USER_UID | cut -d: -f1)"; \
#     fi; \
#     if getent group $USER_GID >/dev/null; then \
#         groupdel "$(getent group $USER_GID | cut -d: -f1)"; \
#     fi; \
#     groupadd --gid $USER_GID $USERNAME; \
#     useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME; \
#     apt-get update; \
#     apt-get install -y --no-install-recommends sudo; \
#     echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME; \
#     chmod 0440 /etc/sudoers.d/$USERNAME; \
#     rm -rf /var/lib/apt/lists/*

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

RUN echo 'source /opt/ros/jazzy/setup.bash' >> /home/$USERNAME/.bashrc \
    && echo '[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash' >> /home/$USERNAME/.bashrc

RUN mkdir -p /home/admin/colcon_ws \
    && chown $USERNAME:$USERNAME /home/admin/colcon_ws

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_UNMANAGED_INSTALL=1 sh \
    && uv --version

ENV VIRTUAL_ENV=/home/admin/colcon_ws/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

USER $USERNAME
WORKDIR /home/admin/colcon_ws

RUN uv venv --python 3.12 --seed $VIRTUAL_ENV \
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
