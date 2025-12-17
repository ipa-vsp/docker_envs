# ROS2 Template (Compose + Devcontainer)

This template lets you either run a ROS2 container with `docker compose` or open it directly in VS Code via a devcontainer.

## Quick start with docker compose
- Copy `.env.example` to `.env` and adjust `IMAGE`, `LOCAL_UID`, `LOCAL_GID`, `USERNAME`, `HOST_WS`, `ROS_DISTRO`.
- From this folder, bring the container up:
  `docker compose up ros`
- The workspace on your host (`HOST_WS`) mounts to `/home/${USERNAME}/colcon_ws` in the container.

### About the `.env` file
- The `.env` file sits next to `docker-compose.yml` and defines variables that the compose file references (image tag, UID/GID, username, host workspace path, ROS distro).
- Values in `.env` are automatically loaded by `docker compose`; no extra flags are needed.
- Edit `.env` to match your host user (UID/GID) to avoid permission issues on mounted files.

## VS Code devcontainer
- Copy `.env.example` to `.env` and tune values as above.
- Open this folder (`composer/ros2-template`) in VS Code and run “Reopen in Container”.
- The devcontainer uses `docker-compose.yml` and mounts your current workspace to `/home/${USERNAME}/colcon_ws`.
- Adjust extensions or settings in `.devcontainer/devcontainer.json` if needed.
