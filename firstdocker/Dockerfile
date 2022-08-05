ARG ROS_DISTRO=melodic
FROM ros:${ROS_DISTRO}-robot

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-perception-pcl \
    && rm -rf /var/lib/apt/lists/*

# setup entrypoint
ENV ROS_DISTRO ${ROS_DISTRO}
RUN mkdir -p /usr/local/bin/scripts
COPY *entrypoint.sh /usr/local/bin/scripts/
RUN  chmod +x /usr/local/bin/scripts/*.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
