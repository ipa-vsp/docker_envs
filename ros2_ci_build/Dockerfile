ARG ROS_DISTRO=galactic

FROM ros:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_VISIBLE_DEVICES \
    ${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES \
    ${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}graphics

ENV ROS_DISTRO=${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive
COPY bashrc_ros /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc
ENV SHELL /bin/bash
SHELL ["/bin/bash", "-c"]


# upgrade current version
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

# Include ros2 dependencies for the future
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-perception-pcl \
    ros-${ROS_DISTRO}-ament-clang-format \
    ros-${ROS_DISTRO}-tf2 \
    && rm -rf /var/lib/apt/lists/*

# Addition dependencies for the future
RUN apt-get update && apt-get install -q -y --no-install-recommends \
    clang-format \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

# Create the 'admin' user if not already exists
RUN if [ ! $(getent passwd ${USERNAME}) ]; then \
        groupadd --gid ${USER_GID} ${USERNAME} ; \
        useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} ; \
    fi

# Update 'admin' user
RUN echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    && adduser ${USERNAME} video && adduser ${USERNAME} sudo

# Copy scripts
RUN mkdir -p /usr/local/bin/scripts
COPY ros2_entrypoint.sh /usr/local/bin/scripts/
RUN  chmod +x /usr/local/bin/scripts/ros2_entrypoint.sh

WORKDIR /home/${USERNAME}

ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}

ENTRYPOINT [ "/usr/local/bin/scripts/ros2_entrypoint.sh" ]
CMD [ "bash" ]
