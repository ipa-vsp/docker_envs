#!/bin/bash
set -eux

USERNAME=admin
USER_UID=1000
USER_GID=1000

# Ensure the group exists
if ! getent group ${USER_GID} >/dev/null 2>&1; then
    groupadd --gid ${USER_GID} ${USERNAME}
fi

# Ensure the user exists and belongs to the correct group
if ! getent passwd ${USER_UID} >/dev/null 2>&1; then
    useradd --uid ${USER_UID} --gid ${USER_GID} -m -d /home/${USERNAME} -s /bin/bash ${USERNAME}
fi

# Set proper ownership of the home directory
chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}

# Add user to necessary groups
usermod -aG sudo,video ${USERNAME}

# Configure sudo permissions
echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}
chmod 0440 /etc/sudoers.d/${USERNAME}

# Ensure colcon_ws exists
mkdir -p /home/${USERNAME}/colcon_ws/src
chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}/colcon_ws
