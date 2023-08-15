ARG ROS_DISTRO=humble

FROM ros:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

ENV ROS_DISTRO=${ROS_DISTRO}

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
RUN mkdir -p colcon_ws/src

# ENTRYPOINT [ "/usr/local/bin/scripts/ros2_entrypoint.sh" ]
# CMD [ "bash" ]
