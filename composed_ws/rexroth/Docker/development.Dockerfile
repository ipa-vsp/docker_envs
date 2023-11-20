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

COPY install_snapcarft.sh /ros_ws/install_snapcarft.sh
RUN chmod +x /ros_ws/install_snapcarft.sh
RUN /ros_ws/install_snapcarft.sh
COPY install_ros_humble.sh /ros_ws/install_ros_humble.sh
RUN chmod +x /ros_ws/install_ros_humble.sh
RUN /ros_ws/install_ros_humble.sh
COPY entrypoint.sh /ros_ws/entrypoint.sh
RUN chmod +x /ros_ws/entrypoint.sh
COPY build_snap.sh /ros_ws/build_snap.sh
RUN chmod +x /ros_ws/build_snap.sh


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
