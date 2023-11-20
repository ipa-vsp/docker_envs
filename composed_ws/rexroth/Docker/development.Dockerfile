ARG BASE_IMAGE=arm64v8/ubuntu:22.04
FROM $BASE_IMAGE

WORKDIR /ros_ws

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive
RUN apt-get install -y fuse snapd snap-confine squashfuse sudo init
RUN apt-get clean
RUN dpkg-divert --local --rename --add /sbin/udevadm
RUN ln -s /bin/true /sbin/udevadm
RUN systemctl enable snapd


# The steps for core22 installation
RUN mkdir -p snap && \
    apt-get update && \
    apt-get install -y curl jq squashfs-tools git make build-essential zlib1g-dev liblzma-dev liblzo2-dev liblz4-dev ca-certificates && \
    git clone https://github.com/plougher/squashfs-tools.git && \
    cd squashfs-tools && \
    git checkout 4.5.1 && \
    sed -Ei 's/#(XZ_SUPPORT.*)/\1/' squashfs-tools/Makefile && \
    sed -Ei 's/#(LZO_SUPPORT.*)/\1/' squashfs-tools/Makefile && \
    sed -Ei 's/#(LZ4_SUPPORT.*)/\1/' squashfs-tools/Makefile && \
    sed -Ei 's|(INSTALL_PREFIX = ).*|\1 /usr|' squashfs-tools/Makefile && \
    sed -Ei 's/\$\(INSTALL_DIR\)/$(DESTDIR)$(INSTALL_DIR)/g' squashfs-tools/Makefile && \
    cd squashfs-tools && \
    make -j$(nproc) && \
    make install && \
    mkdir -p /snap/core22 && \
    curl -L -H 'Snap-CDN: none' $(curl -kH 'X-Ubuntu-Series: 16' -H "X-Ubuntu-Architecture: arm64" 'https://api.snapcraft.io/api/v1/snaps/details/core22' | jq '.download_url' -r) --output core22.snap && \
    unsquashfs -d /snap/core22/x1 core22.snap && \
    ln -s x1 /snap/core22/current

# Ensure snapcraft is installed and set up Python symlink if necessary
RUN mkdir -p /snap/snapcraft && \
    curl -L -H 'Snap-CDN: none' $(curl -kH 'X-Ubuntu-Series: 16' -H "X-Ubuntu-Architecture: arm64" 'https://api.snapcraft.io/api/v1/snaps/details/snapcraft?channel='$SNAPCRAFT | jq '.download_url' -r) --output snapcraft.snap && \
    unsquashfs -d /snap/snapcraft/current snapcraft.snap && \
    ln -s x1 /snap/snapcraft/current

# Additional steps to set up Python and ROS2
RUN unlink /snap/snapcraft/current/usr/bin/python3 && \
    ln -s /snap/snapcraft/current/usr/bin/python3.* /snap/snapcraft/current/usr/bin/python3 && \
    echo /snap/snapcraft/current/lib/python3.*/site-packages >> /snap/snapcraft/current/usr/lib/python3/dist-packages/site-packages.pth

# Create a snapcraft runner
RUN mkdir -p /snap/bin && \
    echo '#!/bin/sh' > /snap/bin/snapcraft && \
    snap_version="$(awk '/^version:/{print $2}' /snap/snapcraft/current/meta/snap.yaml)" && \
    echo "export SNAP_VERSION=\"$snap_version\"" >> /snap/bin/snapcraft && \
    echo 'export SNAP="/snap/snapcraft/current"' >> /snap/bin/snapcraft && \
    echo 'export SNAP_NAME="snapcraft"' >> /snap/bin/snapcraft && \
    echo "export SNAP_ARCH=\"arm64\"" >> /snap/bin/snapcraft && \
    echo 'exec "$SNAP/usr/bin/python3" "$SNAP/bin/snapcraft" "$@"' >> /snap/bin/snapcraft && \
    chmod +x /snap/bin/snapcraft

RUN apt update &&  apt-get install -y locales && \
    locale-gen en_US en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    apt-get install -y software-properties-common && \
    add-apt-repository universe

ENV DEBIAN_FRONTEND=noninteractive
RUN echo "Europe/London" > /etc/timezone && \
    apt-get install -y tzdata

RUN apt-get update && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null && \
    apt update && \
    apt-get install -y ca-certificates && \
    apt-get install -y ros-humble-ros-base python3-argcomplete && \
    apt-get install -y ros-dev-tools && \
    apt-get install -y python3-rosdep && \
    rosdep init

ENV LANG="en_US.UTF-8"
ENV LANGUAGE="en_US:en"
ENV LC_ALL="en_US.UTF-8"
ENV PATH=/snap/bin:$PATH
ENV SNAP="/snap/snapcraft/current"
ENV SNAP_NAME="snapcraft"
ENV SNAP_ARCH="arm64"
ENV SNAPCRAFT_BUILD_ENVIRONMENT="host"
RUN echo SNAPCRAFT_BUILD_ENVIRONMENT=$SNAPCRAFT_BUILD_ENVIRONMENT >> /etc/environment
ENV SNAPCRAFT_ENABLE_EXPERIMENTAL_TARGET_ARCH=1
RUN echo SNAPCRAFT_ENABLE_EXPERIMENTAL_TARGET_ARCH=$SNAPCRAFT_ENABLE_EXPERIMENTAL_TARGET_ARCH >> /etc/environment
ENV SNAPCRAFT_BUILD_INFO=1
ENV PYTHONPATH=/snap/snapcraft/current/lib/python3.10/site-packages/:$PYTHONPATH

COPY entrypoint.sh /ros_ws/entrypoint.sh
RUN chmod +x /ros_ws/entrypoint.sh
COPY build_snap.sh /ros_ws/build_snap.sh
RUN chmod +x /ros_ws/build_snap.sh

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
        libsystemd-dev:arm64 libssl-dev:arm64 libzmq3-dev:arm64 unzip  jq curl \
&& rm -rf /var/lib/apt/lists/* \
&& apt-get clean

# Installation ctrlx data layer
COPY scripts /root/scripts


# Setup non-root admin user
# ARG USERNAME=admin
# ARG USER_UID=1000
# ARG USER_GID=1000

# # Install prerequisites and cleanup in a single step
# RUN apt-get update && apt-get install -y \
#         sudo \
#     && rm -rf /var/lib/apt/lists/* \
#     && apt-get clean

# # Create/modify the 'admin' user and group if necessary
# RUN if [ ! $(getent passwd ${USERNAME}) ]; then \
#         groupadd --gid ${USER_GID} ${USERNAME} && \
#         useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} ; \
#     fi

# # Update 'admin' user
# RUN echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
#     && chmod 0440 /etc/sudoers.d/${USERNAME} \
#     && adduser ${USERNAME} video && adduser ${USERNAME} sudo

# USER ${USERNAME}
# WORKDIR /home/${USERNAME}
WORKDIR /ros_ws

VOLUME ["/sys/fs/cgroup"]
STOPSIGNAL SIGRTMIN+3
ENTRYPOINT ["/sbin/init"]
SHELL ["/bin/bash", "-c"]
