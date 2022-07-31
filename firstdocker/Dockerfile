ARG ROS_DISTRO=melodic
FROM ros:${ROS_DISTRO}-robot

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-perception-pcl \
    && rm -rf /var/lib/apt/lists/*

# setup entrypoint
ENV ROS_DISTRO ${ROS_DISTRO}
COPY ./ros_entrypoint.sh /
RUN chmod a+rwx ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
