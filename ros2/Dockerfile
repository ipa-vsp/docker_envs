ARG USE_CUDA="false"
ARG CUDA_VERSION="11.4.0"
ARG UBUNTU_DISTRO="20.04"
ARG BASE_CUDA_IMAGE=${USE_CUDA:+"nvidia/cuda:${CUDA_VERSION}-devel-ubuntu${UBUNTU_DISTRO}"}
ARG BASE_IMAGE=${BASE_CUDA_IMAGE:-"ubuntu:${UBUNTU_DISTRO}"}

FROM ${BASE_IMAGE}
# FROM ubuntu:20.04
ARG ROS_DISTRO=galactic

ENV DEBIAN_FRONTEND=noninteractive
COPY bashrc /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc
ENV SHELL /bin/bash
SHELL ["/bin/bash", "-c"] 

# setup timezone
RUN echo 'Etc/UTC' > /etc/timezone && \
    ln -s /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    apt-get update && \
    apt-get install -q -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

# install packages
RUN apt-get update && apt-get install -q -y --no-install-recommends \
    dirmngr \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# setup keys
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654

# setup sources.list
RUN echo "deb http://packages.ros.org/ros2/ubuntu focal main" > /etc/apt/sources.list.d/ros2-latest.list

# setup environment
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

ENV ROS_DISTRO galactic

# install ros2 packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-galactic-ros-core=0.9.3-2* \
    && rm -rf /var/lib/apt/lists/*

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    cmake \
    git \
    python3-colcon-common-extensions \
    python3-flake8 \
    python3-pip \
    python3-pytest-cov \
    python3-rosdep \
    python3-setuptools \
    python3-vcstool \
    wget \
    && python3 -m pip install -U \
    flake8-blind-except \
    flake8-builtins \
    flake8-class-newline \
    flake8-comprehensions \
    flake8-deprecated \
    flake8-docstrings \
    flake8-import-order \
    flake8-quotes \
    pytest-repeat \
    pytest-rerunfailures \
    pytest \
    setuptools\
    && rm -rf /var/lib/apt/lists/*

# setup colcon mixin and metadata
# RUN colcon mixin add default \
#       https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml && \
#     colcon mixin update && \
#     colcon metadata add default \
#       https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml && \
#     colcon metadata update

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
COPY *entrypoint.sh /usr/local/bin/scripts/
RUN  chmod +x /usr/local/bin/scripts/*.sh

WORKDIR /home/${USERNAME}

ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}
