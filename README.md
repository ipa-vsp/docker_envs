# docker_envs

This repository contains Dockerfiles, compose templates and helper scripts used to build robotics development environments.  Images are automatically published to [GitHub Container Registry](https://ghcr.io) using GitHub Actions.

## Continuous Integration

| Workflow | Status |
|----------|--------|
| ROS2 Staged | [![ROS2 Staged](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2-staged.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2-staged.yml) |
| PyTorch Staged | [![PyTorch Staged](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-staged.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-staged.yml) |
| Docker Builder | [![Docker](https://github.com/ipa-vsp/docker_envs/actions/workflows/docker.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/docker.yml) |
| Formatting | [![Formatting](https://github.com/ipa-vsp/docker_envs/actions/workflows/format.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/format.yml) |

## Available Docker Images

Images are published under `ghcr.io/ipa-vsp/docker_envs`.  The tables below list every published tag together with the main components included in the image.

### ROS 2 Images (staged workflow - final user images)

| Tag | Notes |
|-----|-------|
| `ghcr.io/ipa-vsp/docker_envs:24.04-rolling` | Staged ROS 2 Rolling developer image on Ubuntu 24.04 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-kilted` | Staged ROS 2 Kilted developer image on Ubuntu 24.04 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy` | Staged ROS 2 Jazzy developer image on Ubuntu 24.04 |
| `ghcr.io/ipa-vsp/docker_envs:22.04-humble` | Staged ROS 2 Humble developer image on Ubuntu 22.04 |
| `ghcr.io/ipa-vsp/docker_envs:20.04-noetic` | Staged ROS 1 Noetic developer image on Ubuntu 20.04 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-kilted-moveit` | ROS 2 Kilted staged image with MoveIt pre-installed |
| `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy-moveit` | ROS 2 Jazzy staged image with MoveIt pre-installed |
| `ghcr.io/ipa-vsp/docker_envs:22.04-humble-moveit` | ROS 2 Humble staged image with MoveIt pre-installed |
| `ghcr.io/ipa-vsp/docker_envs:20.04-noetic-moveit` | ROS 1 Noetic staged image with MoveIt pre-installed |
| `ghcr.io/ipa-vsp/docker_envs:24.04-kilted-mujoco` | ROS 2 Kilted staged image with MuJoCo 3.4.0 and Gymnasium 1.2.0 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy-mujoco` | ROS 2 Jazzy staged image with MuJoCo 3.4.0 and Gymnasium 1.2.0 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-kilted-mujoco-moveit` | ROS 2 Kilted staged image with MuJoCo 3.4.0, Gymnasium 1.2.0, and MoveIt |
| `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy-mujoco-moveit` | ROS 2 Jazzy staged image with MuJoCo 3.4.0, Gymnasium 1.2.0, and MoveIt |
| `ghcr.io/ipa-vsp/docker_envs:24.04-kilted-mujoco-nav2` | ROS 2 Kilted staged image with MuJoCo 3.4.0, Gymnasium 1.2.0, and Nav2 |
| `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy-mujoco-nav2` | ROS 2 Jazzy staged image with MuJoCo 3.4.0, Gymnasium 1.2.0, and Nav2 |

### PyTorch Images

| Tag | Notes |
|-----|-------|
| `ghcr.io/ipa-vsp/docker_envs:cuda12.8-torch2.8` | Staged final image with PyTorch 2.8.0, TorchVision 0.23.0, TorchAudio 2.8.0, CUDA 12.8.0, MuJoCo 3.4.0 |
| `ghcr.io/ipa-vsp/docker_envs:cuda12.8-torch2.8-base` | Staged base layer for the CUDA 12.8 / PyTorch 2.8.0 build |
| `ghcr.io/ipa-vsp/docker_envs:cuda12.8-torch2.8-mujoco` | MuJoCo 3.4.0 and Gymnasium 1.2.0 layer for the staged PyTorch build |
| `ghcr.io/ipa-vsp/docker_envs:cuda12.8-torch2.8-pytorch` | PyTorch layer (2.8.0 / 0.23.0 / 2.8.0) prior to adding the final user setup |

Use `docker pull <tag>` to download an image.  The `creator/scripts/run_env.sh` helper script can build or run images locally.

## Usage compose files

```bash
services:
    <container_name>:
        image: ghcr.io/ipa-vsp/docker_envs:<tag>
        user: admin:1000 # adjust UID if needed. Recommended to use non-root user
        volumes:
            - /tmp/.X11-unix:/tmp/.X11-unix:ro
            - /etc/localtime:/etc/localtime:ro
            - /your/local/path/to/colcon_ws/src:/home/admin/colcon_ws/src
        environment:
            - DISPLAY=$DISPLAY
            - ROS_DOMAIN_ID=73
        entrypoint: /usr/local/bin/scripts/workspace-entrypoint.sh # already installed in the image
        command: tail -f /dev/null # change to your desired command
```

### Build Locally

```bash
# Build and publish an image
cd creator/scripts
./run_env.sh -o 24.04 -v rolling -i ghcr.io/ipa-vsp/docker_envs:rolling -b

# Run the container with a workspace attached
./run_env.sh -r -i ghcr.io/ipa-vsp/docker_envs:rolling -w ~/colcon_ws
```

## Pre-commit Hook

1. Install: `pip install pre-commit`
2. Install git hook: `pre-commit install`
3. Run on all files: `pre-commit run --all-files`

### Attaching your workspace
If the workspace on the host is not owned by UID `1000`, adjust permissions:

```bash
sudo chown -R 1000:1000 <workspace> || sudo chmod -R u+w <workspace>
```

### GUI with Docker on Windows
For using GUI applications on Windows see [docker_gui_windows11](https://github.com/prachandabhanu/docker_gui_windows11.git).
