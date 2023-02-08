#!/bin/bash
# Build ROS dependency
echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
echo "export TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL}" >> ~/.bashrc
source /opt/ros/${ROS_DISTRO}/setup.bash
export TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL}

sudo apt-get update
rosdep update

$@
