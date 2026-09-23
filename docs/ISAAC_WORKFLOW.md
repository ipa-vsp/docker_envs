# Isaac Sim + Isaac Lab workflow

End-to-end steps for developing with Isaac Sim, Isaac Lab and ROS 2 in `docker_envs`.

- Run every command from the `docker_envs` repository root unless noted
- `<img>` = your final image name, e.g. `docker_envs:isaaclab`
- Details for each flag: [creator guide](../creator/README.md)

## 1. Prepare the host (once)

| Step | Command |
|---|---|
| NVIDIA driver installed | `nvidia-smi` |
| NVIDIA Container Toolkit | `sudo apt install nvidia-container-toolkit` |
| Register the runtime | `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker` |
| GPU visible in containers | `docker run --rm --gpus all ubuntu nvidia-smi` |
| Buildx available | `docker buildx version` |
| X11 cookie tool (GUI) | `sudo apt install xauth` |
| Workspace exists, owned by you | `mkdir -p ~/colcon_ws/src` |

- Run Docker as your normal login, not through `sudo`
- Reserve disk space: the Isaac Sim layer alone downloads ~8 GB of wheels

## 2. Choose the stack

- Interactive, prints a pinned replay command, builds nothing:

```bash
creator/scripts/create_env.sh --dry-run
```

- Recommended Isaac stack:
  - Ubuntu 24.04 + ROS 2 Jazzy + Isaac Sim 6.x → one Python version (3.12) for ROS and Isaac
  - `python-env` method → Isaac Lab installed next to Isaac Sim in the shared `/opt/venv`
  - Short `-i` name → easy run commands

```bash
creator/scripts/run_env.sh -p -o 24.04 -v jazzy \
  -I 6.1.0.0 -L release/3.0.0 -j python-env -e 'rl[rsl-rl]' \
  -i docker_envs:isaaclab
```

- Kit-less alternative (no Isaac Sim, Newton physics, smaller image):

```bash
creator/scripts/run_env.sh -p -o 24.04 -v jazzy \
  -L release/3.0.0 -j legacy -e 'newton,rl[rsl-rl],visualizer[newton]' \
  -i docker_envs:isaaclab-kitless
```

- Pin every version (`-I`, `-L`); `latest` and branches change between builds
- Save the replay command in your project notes or README

## 3. Build

```bash
creator/scripts/run_env.sh -b -o 24.04 -v jazzy \
  -I 6.1.0.0 -L release/3.0.0 -j python-env -e 'rl[rsl-rl]' \
  -i docker_envs:isaaclab
```

- Layers build in order; a failed layer stops the build, and a rerun resumes from it
- Recover the exact build command later:

```bash
docker image inspect -f '{{index .Config.Labels "org.docker_envs.build-command"}}' docker_envs:isaaclab
```

## 4. Workspace layout

```text
~/colcon_ws/                  # mounted at /home/admin/colcon_ws
├── src/
│   ├── <ros_packages>/       # colcon packages
│   └── <isaaclab_project>/   # external Isaac Lab project (own logs/)
├── build/ install/ log/      # colcon output (workspace root only)
└── .claude/                  # optional: git clone https://github.com/ipa-vsp/.claude.git
```

| Data | Where it persists |
|---|---|
| Source code, project `logs/` | `~/colcon_ws` (bind mount) |
| Isaac Lab `logs/`, `data_storage/` in `/opt/IsaacLab` | `~/docker/isaac-lab/` |
| Omniverse caches, shaders, config | `~/docker/isaac-sim/` |
| Kit extension cache | `~/docker/isaac-sim/cache/kit/<Isaac Sim version>` |
| Anything else in the container | lost when the container is removed |

## 5. Daily loop

| Action | Command |
|---|---|
| Start (background, once per session) | `creator/scripts/run_env.sh -S -H -i <img> -w ~/colcon_ws` |
| Open a shell (any terminal, repeatable) | `creator/scripts/run_env.sh -E -i <img>` |
| Stop and remove | `creator/scripts/run_env.sh -K -i <img>` |
| One-off shell instead | `creator/scripts/run_env.sh -r -H -i <img> -w ~/colcon_ws` |

- `-H` → host network + IPC → ROS 2 discovery with the host, shared memory for workers
- Isaac Sim images → GPU, EULA variables and caches added automatically
- Kit-less images → add `-g` for the GPU
- Second container from the same image → `-C <name>` on every command
- Compose alternative → [composer/isaaclab](../composer/isaaclab/README.md)

## 6. Inside the container: Isaac Lab

```bash
isaac-activate                                   # shared /opt/venv (already active by default)
cd /opt/IsaacLab
isaaclab -p scripts/environments/list_envs.py    # discover task names
isaaclab -p scripts/tutorials/00_sim/create_empty.py --headless
isaaclab -p scripts/reinforcement_learning/train.py --rl_library rsl_rl --task <Task> --headless
```

- GUI check → replace `--headless` with `--viz kit` (Isaac Sim images)
- First Isaac Sim start → several minutes of shader compilation; later starts reuse the cache
- Training output → `/opt/IsaacLab/logs/rsl_rl/...` → host `~/docker/isaac-lab/logs/`

### External project

```bash
isaac-activate
cd ~/colcon_ws/src
isaaclab --new                                   # generate a project from the template
cd <project>
python -m pip install -e source/<project>
python scripts/list_envs.py
```

- Project logs → `~/colcon_ws/src/<project>/logs/` (already on the host)
- uv projects → [project env vs active Isaac env](../creator/README.md#uv-project-env-or-active-isaac-env)

### TensorBoard

```bash
isaac-activate
python -m pip install tensorboard        # only if not already installed
python -m tensorboard.main --logdir /opt/IsaacLab/logs --bind_all
```

- Open `http://localhost:6006` on the host (needs `-H`)
- Package changes at runtime → lost when the container is removed → add them to a custom Dockerfile

## 7. Inside the container: ROS 2

```bash
deactivate 2>/dev/null || true                   # back to the ROS Python
cd ~/colcon_ws
colcon build --symlink-install
source install/setup.bash
```

- Use a separate `-E` shell for ROS work; keep the Isaac shell activated
- Always run `colcon` from the workspace root, never from `src/`

## 8. Update and clean up

| Goal | Command |
|---|---|
| Change one version | edit the flag → rerun the same `-b` command (lower layers cached) |
| Refresh everything | `docker pull ubuntu:24.04 && DOCKER_BUILD_EXTRA="--no-cache" creator/scripts/run_env.sh -b ...` |
| List intermediate layers | `docker image ls 'docker_envs/*'` |
| Remove an old stack | `docker image rm <final> docker_envs/<layer>:<tag> ...` |
| Free build cache | `docker builder prune` |
| Reset Isaac caches | stop containers → `rm -rf ~/docker/isaac-sim/cache/<dir>` |

## 9. Troubleshooting

| Symptom | Check / fix |
|---|---|
| First start "hangs" for minutes | shader compilation; wait once; cache persists in `~/docker/isaac-sim` |
| Every start recompiles shaders | `-X` used, or cache dir not writable → `ls -ld ~/docker/isaac-sim/cache/*` |
| `could not select device driver "nvidia"` | toolkit not configured → step 1 |
| GUI: `cannot open display` | `echo $DISPLAY` on the host; `xauth` installed; restart with `-S` |
| GUI broke after re-login | new X cookie → run `-E` again (refreshes the cookie) |
| `Permission denied` in workspace | image UID ≠ host UID → [permissions](../creator/README.md#permissions-and-storage) |
| `uv sync` permission error | [uv repair](../creator/README.md#uv-sync-permission-denied) |
| ROS 2 topics invisible from host | start with `-H`; same `ROS_DOMAIN_ID` on both sides |
| `-E` says not running | start with `-S`; with `-C`, pass the same name |

## How this compares to IsaacLab/docker

| IsaacLab/docker | docker_envs | Status |
|---|---|---|
| `container.py start / enter / stop` | `run_env.sh -S / -E / -K` | adopted |
| `--suffix` for parallel containers | `-C <name>` | adopted |
| `network_mode: host` | `-H` (opt-in), `network_mode: host` in `composer/isaaclab` | adopted |
| `x11.yaml` + wildcard xauth cookie, refreshed on `enter` | same cookie approach in `run_env.sh`; `compose.x11.yml` | adopted |
| Named volumes for `logs/`, `data_storage/` | host dirs under `~/docker/isaac-lab`; named volumes in Compose | adopted |
| Compose file drives pre-created mount points (`volume_mounts.py`) | `creator/common/isaac-cache-dirs.txt` drives launcher, image and a Compose sync test | adopted |
| Versions in `.env.base` / `.env.ros2` | pinned replay command stored as image label | adopted (label instead of env files) |
| NGC `isaac-sim` binary image as base, root home | pip wheels on Ubuntu + ROS, non-root account with host UID/GID | different by design |
| Isaac Lab source copied from the local checkout | Isaac Lab cloned at a pinned tag/branch | different by design |
| `copy` command for artifacts | outputs already on the host | not needed |
| Singularity export + SLURM/PBS submission | none | roadmap |
| Bash history in a bind-mounted file | none | roadmap |
| ROS 2 `fastdds.xml` / `cyclonedds.xml` profiles | none | roadmap |

## Roadmap

- Cluster: `apptainer build isaaclab.sif docker-daemon://<img>` + SLURM job template
- Persist shell history: bind `~/docker/isaac-lab/bash_history` → `HISTFILE`
- ROS 2 middleware profiles: ship `fastdds.xml` / `cyclonedds.xml`, select with `RMW_IMPLEMENTATION`
