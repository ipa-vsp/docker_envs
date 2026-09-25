# docker_envs

Docker development environments for ROS 2, PyTorch, MuJoCo and NVIDIA Isaac Sim / Isaac Lab.

- Staged builder → pick only the layers you need
- Published images → ROS 2, MoveIt, PyTorch
- Development images → compilers, dev tools, passwordless `sudo` for the development account
- Non-root by default → your host UID/GID inside the container

## Requirements

- Docker Engine + Buildx plugin
- Linux scripts: Bash; Windows builder: PowerShell 5.1 or 7
- Tests: Python 3 (Linux regression suite: PyYAML, `jq`)
- GPU stacks → NVIDIA driver + NVIDIA Container Toolkit
- GUI → X11 display + `xauth`

## Quick start

Run from the repository root.

### ROS 2

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy -u manipulation      # build
mkdir -p "$HOME/colcon_ws/src"
creator/scripts/run_env.sh -r -i docker_envs:24.04-jazzy-moveit -w "$HOME/colcon_ws"
```

### Isaac Sim + Isaac Lab

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -I 6.1.0.0 -L release/3.0.0 -j python-env -i docker_envs:isaaclab
creator/scripts/run_env.sh -S -H -i docker_envs:isaaclab -w "$HOME/colcon_ws"
creator/scripts/run_env.sh -E -i docker_envs:isaaclab
```

### Isaac Lab without Isaac Sim (Kit-less)

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -L release/3.0.0 -j legacy -i docker_envs:isaaclab-kitless
```

### Other entry points

| Goal | Command |
|---|---|
| Interactive stage selection | `creator/scripts/create_env.sh` |
| Windows interactive stage selection | `creator\scripts\create_env.bat` or `./creator/scripts/create_env.ps1` ([Windows guide](creator/README.md#windows-image-builder)) |
| Graphical stage selection | AppImage from a release, or `pip install ./gui && docker-envs-gui` |
| Preview a build (no build) | replace `-b` with `-p` |
| All flags | `creator/scripts/run_env.sh -h` |

### Graphical builder

A desktop front end over the same staged builder: all nine stages on one form,
with the derived image name, the layer plan and the equivalent `run_env.sh`
command updating as you choose, and the build log streamed with per-layer
progress. It runs the command it shows, so images are identical to CLI builds.
Combinations `stages.sh` would reject are disabled with the reason attached.
Two further tabs list the local images — marking the ones this tool built and
showing their stored build command — and the containers, with stop, restart and
remove.

```bash
pip install ./gui && docker-envs-gui      # from a checkout
./docker-envs-gui-<version>-x86_64.AppImage   # self-contained; no checkout needed
```

See the [GUI guide](gui/README.md).

## Daily loop

| Action | Command |
|---|---|
| Start in background | `creator/scripts/run_env.sh -S -H -i <img> -w <workspace>` |
| New shell (repeatable) | `creator/scripts/run_env.sh -E -i <img>` |
| Stop + remove | `creator/scripts/run_env.sh -K -i <img>` |
| One-off shell | `creator/scripts/run_env.sh -r -i <img> -w <workspace>` |

- Workspace → must already exist; mounted at `~/colcon_ws`; ownership never changed
- Devices → explicit only: `-g` all NVIDIA GPUs, `-d /dev/<device>` one device
- `-H` → host network + IPC (ROS 2 discovery)
- Isaac images → GPU, caches and Isaac Lab output mounts added automatically
- Replay a build → `docker image inspect -f '{{index .Config.Labels "org.docker_envs.build-command"}}' <img>`

## Published images

Registry: `ghcr.io/ipa-vsp/docker_envs`

| Stack | Tags |
|---|---|
| ROS 2 | `24.04-rolling`, `24.04-kilted`, `24.04-jazzy`, `22.04-humble`, `26.04-lyrical` |
| ROS 2 + MoveIt | `24.04-kilted-moveit`, `24.04-jazzy-moveit`, `22.04-humble-moveit` |
| PyTorch | `cuda12.8-torch2.8` (Torch 2.8.0, CUDA wheels, MuJoCo 3.4.0, Ubuntu 24.04) |

- Publication status → check workflow results
- Existing registry images → keep previous behavior until rebuilt
- CI PyTorch image → Ubuntu + CUDA-enabled wheels
- Local PyTorch helper → CUDA development base
- CUDA, Isaac Sim/Lab, Nav2, other MuJoCo combinations → local builds only
- Workflows:
  - [ROS publication](.github/workflows/ros2-staged.yml)
  - [PyTorch publication](.github/workflows/pytorch-staged.yml)
  - [Build regression checks](.github/workflows/build-validation.yml)

## Repository layout

| Path | Contents |
|---|---|
| `creator/scripts/` | `create_env.sh` (interactive), `run_env.sh` (flags), shared `lib/stages.sh` |
| `creator/common/`, `creator/ros2/`, `creator/usage/` | layer Dockerfiles + build-time helpers |
| `gui/` | desktop image builder (PySide6) + its AppImage packaging |
| `composer/template/` | minimal Compose file for any creator image |
| `composer/isaaclab/` | persistent Isaac Sim / Lab Compose service for a creator image |
| `composer/isaacsim/` | fixed Isaac Sim 6.0.1 example (not the creator path) |
| `composer/isaac/` | legacy NGC Isaac Sim 4.5 reference |
| `composer/<other>/` | application examples → review hardware, network, paths first |
| `creator/_deprecated/` | historical references |
| `docs/` | Sphinx documentation site (`make -C docs html`), workflow guides |
| `tests/` | regression tests (no Docker needed) |

## Documentation map

| Topic | Guide |
|---|---|
| Full documentation site (all guides, Compose examples, Zed, development) | [docs/](docs/) → `pip install -r docs/requirements.txt && make -C docs html` |
| Isaac Sim + Lab end-to-end workflow | [docs/ISAAC_WORKFLOW.md](docs/ISAAC_WORKFLOW.md) |
| Build flags, run flags, Isaac options, permissions, caching | [creator/README.md](creator/README.md) |
| Graphical builder, its bridge to `stages.sh`, AppImage packaging | [gui/README.md](gui/README.md) |
| Compose with a creator image, custom Dockerfile | [composer/template/README.md](composer/template/README.md) |
| Isaac Compose service | [composer/isaaclab/README.md](composer/isaaclab/README.md) |
| Fixed Isaac Sim example | [composer/isaacsim/README.md](composer/isaacsim/README.md) |
| Zed editor over SSH (Windows, macOS, Linux) | [docs/usage/zed.rst](docs/usage/zed.rst) |
| `uv sync: Permission denied` | [creator/README.md#uv-sync-permission-denied](creator/README.md#uv-sync-permission-denied) |

## Compose in one minute

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
export HOST_WS="$HOME/colcon_ws"
export IMAGE=docker_envs:24.04-jazzy-moveit
docker compose -f composer/template/docker-compose.yml run --rm ros
```

## Permissions in one minute

- UID/GID → decide ownership; umask → decides initial permissions
- Shared group access → launcher `-a <gid> -M 0002`, or Compose `group_add` + `WORKSPACE_UMASK: "0002"`
- Published images → account `admin`, `1000:1000`
- Different IDs + writable named home → rebuild the final user layer
- Never recursively `chown` a repository to match an image
- Details → [permissions and storage](creator/README.md#permissions-and-storage)

## Extending an image

- Final images end as the non-root account
- Package installs → switch to `root`, then back to the account

```dockerfile
FROM ghcr.io/ipa-vsp/docker_envs:24.04-jazzy
USER root
RUN apt-get update && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/*
USER admin
```

## Container startup behavior

- Loads ROS and Zenoh (when installed), applies `WORKSPACE_UMASK`, then `exec`s the command
- No package updates, rosdep updates, Git pulls or host sysctl changes at startup
- Interactive Bash → banner with user, workspace, ROS distro; warning when root
- Claude Code → installed in final images; [`ipa-vsp/.claude`](https://github.com/ipa-vsp/.claude) cloned at `~/colcon_ws/.claude`
- Python → one shared environment, `/opt/venv`: active by default (`(venv)` prompt), writable by the user, visible to ROS 2 → see [Python environment](creator/README.md#python-environment-optvenv)
- Graphify → installed into `/opt/venv` after Claude; skill registered with `graphify install`
- Mounted workspace hides that clone → see [Claude Code and skills](creator/README.md#claude-code-and-skills)

## Validation

```bash
python3 -m unittest discover -s tests -v
pre-commit run --all-files
```

- Install hooks once → `pre-commit install`
- Image smoke checks, cache inspection → [creator checks](creator/README.md#checks)
