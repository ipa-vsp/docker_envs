FROM nvcr.io/nvidia/isaac-sim:4.2.0

ENV DEBIAN_FRONTEND noninteractive

# Set locale
RUN apt-get update && apt-get install -y locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*
ENV LANG en_US.UTF-8
ENV ROS_PYTHON_VERSION 3

# Install basic dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Add ROS2 apt repository
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2-testing/ubuntu jammy main" > /etc/apt/sources.list.d/ros2.list

# Install ROS fundamentals
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3-colcon-common-extensions \
    python3-colcon-clean \
    python3-flake8 \
    python3-flake8-blind-except \
    python3-flake8-builtins \
    python3-flake8-class-newline \
    python3-flake8-comprehensions \
    python3-flake8-deprecated \
    python3-flake8-docstrings \
    python3-flake8-import-order \
    python3-flake8-quotes \
    python3-pip \
    python3-pytest \
    python3-pytest-cov \
    python3-pytest-repeat \
    python3-pytest-rerunfailures \
    python3-rosdep \
    python3-vcstool \
    python3-rosinstall-generator \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set ROS environment variables
ENV ROS_DISTRO humble
ENV ROS_ROOT /opt/ros/${ROS_DISTRO}

# Install specific Python setuptools version
RUN python3 -m pip install setuptools==58.2.0

# Install ROS2 packages
RUN apt-get update && apt-get install -y \
    ros-${ROS_DISTRO}-desktop \
    ros-${ROS_DISTRO}-moveit \
    ros-${ROS_DISTRO}-rviz-visual-tools \
    ros-${ROS_DISTRO}-moveit-resources \
    ros-${ROS_DISTRO}-ros2-control \
    ros-${ROS_DISTRO}-ros2-controllers \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Initialize and update rosdep
RUN apt-get update \
    && rosdep init \
    && rosdep update
