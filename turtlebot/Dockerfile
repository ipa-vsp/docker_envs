ARG TB3_MODEL=burger
FROM ros:melodic-robot

ENV ROS_DISTRO melodic

# Build test 1

ENV TURTLEBOT3_MODEL ${TB3_MODEL}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-melodic-joy ros-melodic-teleop-twist-joy \
    ros-melodic-teleop-twist-keyboard ros-melodic-laser-proc \
    ros-melodic-rgbd-launch ros-melodic-rosserial-arduino \
    ros-melodic-rosserial-python ros-melodic-rosserial-client \
    ros-melodic-rosserial-msgs ros-melodic-amcl ros-melodic-map-server \
    ros-melodic-move-base ros-melodic-urdf ros-melodic-xacro \
    ros-melodic-compressed-image-transport ros-melodic-rqt* ros-melodic-rviz \
    ros-melodic-gmapping ros-melodic-navigation ros-melodic-interactive-markers \
    && rm -rf /var/lib/apt/lists/*


RUN apt-get update && apt-get install -q -y --no-install-recommends \
    ros-melodic-dynamixel-sdk \
    ros-melodic-turtlebot3-msgs \
    ros-melodic-turtlebot3 \
    && rm -rf /var/lib/apt/lists/*

# setup entrypoint
COPY ./ros_entrypoint.sh /

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
