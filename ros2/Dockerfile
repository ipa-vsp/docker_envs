ARG USE_CUDA
ARG CUDA_VERSION="11.4.0"
ARG UBUNTU_DISTRO="20.04"
ARG BASE_CUDA_IMAGE=${USE_CUDA:+"nvidia/cuda:${CUDA_VERSION}-devel-ubuntu${UBUNTU_DISTRO}"}
ARG BASE_IMAGE=${BASE_CUDA_IMAGE:-"ubuntu:${UBUNTU_DISTRO}"}

FROM ${BASE_IMAGE}
ARG ROS_DISTRO=foxy

RUN echo "Building image: ${BASE_IMAGE}""

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

# setup sources.list
RUN echo "deb http://packages.ros.org/ros2/ubuntu focal main" > /etc/apt/sources.list.d/ros2-latest.list

# setup keys
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654

# setup environment
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

# install ros2 packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-ros-core \
    && rm -rf /var/lib/apt/lists/*

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-rosdep \
    python3-vcstool \
    && rm -rf /var/lib/apt/lists/*

# setup colcon mixin and metadata
RUN colcon mixin add default \
      https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml && \
    colcon mixin update && \
    colcon metadata add default \
      https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml && \
    colcon metadata update

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

# setup entrypoint
ENV ROS_DISTRO ${ROS_DISTRO}
COPY ./ros_entrypoint.sh /
RUN chmod a+rwx ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]