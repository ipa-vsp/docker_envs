FROM redhat/ubi9:latest

RUN dnf install langpacks-en glibc-langpack-en -y
# RUN dnf install 'dnf-command(config-manager)' epel-release -y
# RUN dnf config-manager --set-enabled crb
RUN subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms
RUN dnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm -y

RUN dnf install curl
RUN curl --output /etc/yum.repos.d/ros2.repo http://packages.ros.org/ros2/rhel/ros2.repo
RUN dnf makecache -y

RUN dnf install -y \
  cmake \
  gcc-c++ \
  git \
  make \
  patch \
  python3-colcon-common-extensions \
  python3-flake8-builtins \
  python3-flake8-comprehensions \
  python3-flake8-docstrings \
  python3-flake8-import-order \
  python3-flake8-quotes \
  python3-mypy \
  python3-pip \
  python3-pydocstyle \
  python3-pytest \
  python3-pytest-repeat \
  python3-pytest-rerunfailures \
  python3-rosdep \
  python3-setuptools \
  python3-vcstool \
  wget

RUN python3 -m pip install -U --user \
  flake8-blind-except==0.1.1 \
  flake8-class-newline \
  flake8-deprecated

RUN dnf update && dnf install ros-rolling-ros-base
