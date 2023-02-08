#!/bin/bash
set -e

# setup ros2 environment
source "/opt/ros/$ROS_DISTRO/setup.bash"
echo "Docker base image: ${BASE_IMAGE}"
exec "$@"
