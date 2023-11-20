#!/bin/bash

apt update &&  apt-get install -y locales
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
export DEBIAN_FRONTEND=noninteractive
echo "Europe/London" > /etc/timezone
apt-get install -y tzdata
apt-get install -y software-properties-common
add-apt-repository universe
apt-get update

curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" |  tee /etc/apt/sources.list.d/ros2.list > /dev/null
apt update
apt-get install -y ca-certificates
apt-get install -y ros-humble-ros-base python3-argcomplete
apt-get install -y ros-dev-tools
apt-get install -y python3-rosdep
rosdep init
