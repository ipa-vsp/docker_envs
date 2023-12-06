ARG ROS_DISTRO=humble

FROM ros:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

ENV ROS_DISTRO=${ROS_DISTRO}

# Setup non-root admin user
ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive
COPY dockerhub/ros2_ci_build/bashrc /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc
ENV SHELL /bin/bash
SHELL ["/bin/bash", "-c"]

# Addition dependencies for the future
RUN apt-get update && apt-get install -q -y --no-install-recommends \
    clang-format \
    && rm -rf /var/lib/apt/lists/*

# Copy scripts
RUN mkdir -p /usr/local/bin/scripts
COPY dockerhub/ros2_ci_build/*entrypoint.sh /usr/local/bin/scripts/
RUN  chmod +x /usr/local/bin/scripts/*entrypoint.sh

# Create/modify the 'admin' user and group if necessary
RUN if [ ! $(getent passwd ${USERNAME}) ]; then \
        groupadd --gid ${USER_GID} ${USERNAME} && \
        useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} ; \
    fi

# Update 'admin' user
RUN echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    && adduser ${USERNAME} video && adduser ${USERNAME} sudo

USER ${USERNAME}
WORKDIR /home/${USERNAME}

RUN mkdir -p colcon_ws/src

# Set Environment Variables
ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}

# ENTRYPOINT [ "/usr/local/bin/scripts/ros2_entrypoint.sh" ]
# CMD [ "bash" ]
