ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

# disable terminal interaction for apt
ENV DEBIAN_FRONTEND=noninteractive
COPY kuka/bashrc /etc/bash.bashrc
RUN chmod a+rwx /etc/bash.bashrc
ENV SHELL /bin/bash
SHELL ["/bin/bash", "-c"]

# Fundamentals
RUN apt-get update && apt-get install -y \
        apt-transport-https bash-completion build-essential \
        ca-certificates clang-format cmake curl \
        git gnupg2 locales lsb-release rsync \
        software-properties-common wget vim \
        unzip mlocate libgoogle-glog-dev \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

# Python basics
RUN apt-get update && apt-get install -y \
        python3-flake8 \
        python3-pip \
        python3-pybind11 \
        python3-pytest-cov \
        python3-setuptools \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

# Python3 (PIP)
RUN python3 -m pip install -U \
        argcomplete \
        autopep8 \
        flake8 \
        flake8-blind-except \
        flake8-builtins \
        flake8-class-newline \
        flake8-comprehensions \
        flake8-deprecated \
        flake8-docstrings \
        flake8-import-order \
        flake8-quotes \
        onnx \
        pytest-repeat \
        pytest-rerunfailures \
        pytest \
        pydocstyle \
        scikit-learn

# Install Git-LFS
RUN curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash && \
        apt-get update && apt-get install -y \
        git-lfs \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN locale-gen en_US en_US.UTF-8
RUN update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV ROS_PYTHON_VERSION=3

# Basics
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        curl \
        gnupg \
        lsb-release \
        software-properties-common \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && add-apt-repository universe \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Add ROS2 apt repository
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2-testing/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

# ROS fundamentals
RUN apt-get update && apt-get install -y \
        build-essential \
        cmake \
        git \
        python3-colcon-common-extensions \
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
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

ENV ROS_DISTRO=humble
ENV ROS_ROOT=/opt/ros/${ROS_DISTRO}

RUN python3 -m pip install setuptools==58.2.0

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        ros-${ROS_DISTRO}-desktop \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        ros-${ROS_DISTRO}-moveit \
        ros-${ROS_DISTRO}-rviz-visual-tools \
        ros-${ROS_DISTRO}-moveit-resources \
        ros-${ROS_DISTRO}-ros2-control \
        ros-${ROS_DISTRO}-ros2-controllers \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update \
    && rosdep init \
    && rosdep update


# Install Extra dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
#         ros-${ROS_DISTRO}-gazebo-ros \
        ros-${ROS_DISTRO}-gazebo-ros2-control \
        ros-${ROS_DISTRO}-gazebo-plugins \
        ros-${ROS_DISTRO}-gazebo-msgs \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        ros-${ROS_DISTRO}-moveit-servo \
        ros-humble-moveit-visual-tools \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        clang gdb gdbserver\
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && apt install -y \
        ros-humble-rmw-cyclonedds-cpp \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

RUN apt-get update && \
        python3 -m pip install python-snap7 \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

# Setup non-root admin user
ARG USERNAME=admin
ARG USER_UID=1000
ARG USER_GID=1000

# Install prerequisites
RUN apt-get update && apt-get install -y \
        sudo \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

# Reuse triton-server user as 'admin' user if exists
RUN if [ $(getent group triton-server) ]; then \
        groupmod --gid ${USER_GID} -n ${USERNAME} triton-server ; \
        usermod -l ${USERNAME} -m -d /home/${USERNAME} triton-server ; \
        mkdir -p /home/${USERNAME} ; \
        sudo chown ${USERNAME}:${USERNAME} /home/${USERNAME} ; \
    fi

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
COPY kuka/*entrypoint.sh /usr/local/bin/scripts/
RUN  chmod +x /usr/local/bin/scripts/*.sh

USER ${USERNAME}
WORKDIR /home/${USERNAME}
RUN mkdir -p colcon_ws

ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}

ENV NVIDIA_VISIBLE_DEVICES \
    ${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES \
    ${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}graphics
