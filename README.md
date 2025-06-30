# docker_envs

This repository contains Dockerfiles, compose templates and helper scripts used to build robotics development environments.  Images are automatically published to [GitHub Container Registry](https://ghcr.io) using GitHub Actions.

## Continuous Integration

| Workflow | Status |
|----------|--------|
| ROS2 Images | [![ROS2 Images](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2.yml) |
| ROS2 Staged | [![ROS2 Staged](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2-staged.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ros2-staged.yml) |
| PyTorch | [![PyTorch](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch.yml) |
| PyTorch Staged | [![PyTorch Staged](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-staged.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pytorch-staged.yml) |
| Docker Builder | [![Docker](https://github.com/ipa-vsp/docker_envs/actions/workflows/docker.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/docker.yml) |
| Clang Format | [![Clang Format](https://github.com/ipa-vsp/docker_envs/actions/workflows/ci-formater.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/ci-formater.yml) |
| Pre-commit | [![Pre-commit](https://github.com/ipa-vsp/docker_envs/actions/workflows/pre-formater.yml/badge.svg)](https://github.com/ipa-vsp/docker_envs/actions/workflows/pre-formater.yml) |

## Available Docker Images

Images are published under `ghcr.io/ipa-vsp/docker_envs`.  The build matrix covers multiple Ubuntu and ROS releases.

| Tag example | Notes |
|-------------|-------|
| `ghcr.io/ipa-vsp/docker_envs:rolling` | ROS2 Rolling on Ubuntu 24.04 |
| `ghcr.io/ipa-vsp/docker_envs:humble`  | ROS2 Humble on Ubuntu 22.04 |
| `ghcr.io/ipa-vsp/docker_envs:cuda12.8-torch2.7` | PyTorch 2.7 with CUDA 12.8 |

Use `docker pull <tag>` to download an image.  The `creator/scripts/run_env.sh` helper script can build or run images locally.

### Example

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
