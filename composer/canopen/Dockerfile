# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    git sudo iproute2 can-utils kmod python3-colcon-common-extensions \
    python3-rosdep python3-pytest python3-yaml \
    ros-${ROS_DISTRO}-launch-testing ros-${ROS_DISTRO}-launch-testing-ament-cmake \
    && rm -rf /var/lib/apt/lists/*
COPY --chmod=0755 scripts/apply-patches.sh /opt/canopen/apply-patches.sh
COPY patches/ /opt/canopen/patches/
RUN mkdir -p /home/admin/colcon_ws/src && chown admin: /home/admin/colcon_ws/src
USER admin
WORKDIR /home/admin/colcon_ws
ARG CANOPEN_BRANCH
ARG CANOPEN_REV
RUN test -n "${CANOPEN_REV}" && \
    git clone --branch "${CANOPEN_BRANCH}" --single-branch \
      https://github.com/ros-industrial/ros2_canopen.git src/ros2_canopen && \
    git -C src/ros2_canopen checkout --detach "${CANOPEN_REV}" && \
    test "$(git -C src/ros2_canopen rev-parse HEAD)" = "${CANOPEN_REV}" && \
    /opt/canopen/apply-patches.sh
RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    sudo apt-get update && rosdep update --rosdistro "${ROS_DISTRO}" && \
    rosdep install --from-paths src --ignore-src --rosdistro "${ROS_DISTRO}" -y && \
    sudo rm -rf /var/lib/apt/lists/*
ARG BUILD_JOBS=4
ENV CMAKE_BUILD_PARALLEL_LEVEL=${BUILD_JOBS} MAKEFLAGS=-j${BUILD_JOBS}
RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    colcon build --executor sequential --event-handlers console_direct+ \
      --cmake-args -DBUILD_TESTING=ON -DCANOPEN_ENABLED=ON
COPY --chmod=0755 scripts/ /opt/canopen/
LABEL org.opencontainers.image.source="https://github.com/ros-industrial/ros2_canopen" \
      org.opencontainers.image.revision="${CANOPEN_REV}" \
      org.canopen.branch="${CANOPEN_BRANCH}"
ENTRYPOINT ["/opt/canopen/entrypoint.sh"]
CMD ["bash"]
