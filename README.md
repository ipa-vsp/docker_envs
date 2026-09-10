# docker_envs

Docker development environments for ROS 2, PyTorch, MuJoCo, and NVIDIA Isaac.
Use the staged builder for a custom stack or start with a published image.
These images include compilers, development tools, and passwordless sudo for the
named development account.

## Quick start

Run from the repository root with Docker Engine and the Buildx plugin installed:

```bash
# Build a named account with your host UID/GID.
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -u manipulation

mkdir -p "$HOME/colcon_ws/src"
creator/scripts/run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w "$HOME/colcon_ws"
```

Isaac Lab 3.x can also be built without Isaac Sim using `-L release/3.0.0 -j legacy`.
For the full Sim environment, use `-I 6.1.0.0 -L release/3.0.0 -j python-env`.

For interactive stage selection, run `creator/scripts/create_env.sh`. To inspect
a build without executing it, replace `-b` with `-p`. See the
[creator guide](creator/README.md) for flags, Isaac configuration, and caching.

Final creator images start as `admin` by default; local builds use your numeric
UID/GID. The launcher also supplies your host IDs at runtime and requires an
existing workspace. It never changes workspace ownership. Device access is
explicit: use `-g` for NVIDIA GPUs or `-d /dev/<device>` for a specific device.

## Published images

The active workflows configure the following tags under
`ghcr.io/ipa-vsp/docker_envs`. Check workflow results for publication status;
existing registry images keep their previous behavior until rebuilt.

| Stack | Tags |
|---|---|
| ROS 2 | `24.04-rolling`, `24.04-kilted`, `24.04-jazzy`, `22.04-humble`, `26.04-lyrical` |
| ROS 2 + MoveIt | `24.04-kilted-moveit`, `24.04-jazzy-moveit`, `22.04-humble-moveit` |
| PyTorch | `cuda12.8-torch2.8` (Torch 2.8.0, CUDA wheels, MuJoCo 3.4.0, Ubuntu 24.04) |

CI's PyTorch image uses Ubuntu plus CUDA-enabled wheels. The local PyTorch helper
uses a CUDA development base. CUDA, Isaac Sim/Lab, Nav2, and additional MuJoCo
combinations are available through local builds.

- [ROS publication workflow](.github/workflows/ros2-staged.yml)
- [PyTorch publication workflow](.github/workflows/pytorch-staged.yml)
- [Build regression checks](.github/workflows/build-validation.yml)

## Compose and host files

Use the [minimal Compose template](composer/template/docker-compose.yml):

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
export HOST_WS="$HOME/colcon_ws"
export IMAGE=docker_envs:24.04-jazzy-moveit
docker compose -f composer/template/docker-compose.yml run --rm ros
```

UID/GID determine ownership; umask determines initial permissions. For shared
group access, use the launcher's `-a <gid> -M 0002`, or Compose `group_add` and
`WORKSPACE_UMASK: "0002"`. Published accounts use `1000:1000`; rebuild the final
user layer if your application needs a writable named home with different IDs.
Do not recursively change ownership of a repository to match a published image.

See [permissions and storage](creator/README.md#permissions-and-storage) for
named volumes, troubleshooting, and platform differences, and the
[Isaac Sim example](composer/isaacsim/README.md) for persistent simulator caches.
Other `composer/` directories are application-specific examples; review their
hardware, network, and path settings before using them. Files under
`creator/_deprecated/` are historical references.

## Extending an image

Final images now default to non-root. Downstream package installation must select
root explicitly, then restore the development user:

```dockerfile
FROM ghcr.io/ipa-vsp/docker_envs:24.04-jazzy
USER root
RUN apt-get update && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/*
USER admin
```

Startup loads ROS/Zenoh when installed, applies `WORKSPACE_UMASK`, and executes
the command. Package updates, rosdep updates, Git pulls, host sysctl changes, and
Claude CLI/config installation are no longer automatic. Run development setup
commands explicitly when needed.

## Validation

```bash
python3 -m unittest discover -s tests -v
pre-commit run --all-files
```

Tests require Python, PyYAML, and `jq`. Install hooks with `pre-commit install`.
See the creator guide for image smoke checks and cache inspection.
