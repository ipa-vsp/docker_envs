# Isaac Sim / Isaac Lab with Compose

Persistent Compose service for a **creator** image with Isaac Sim and/or Isaac Lab.

- Same data layout as `creator/scripts/run_env.sh -S`, but with named volumes
- GPU, host network, host IPC, `init` enabled
- GUI → optional `compose.x11.yml` override
- Script alternative → [run_env.sh -S / -E / -K](../../creator/README.md#run-a-container)

## Prerequisites

- Final creator image built with your host UID/GID → [workflow step 3](../../docs/ISAAC_WORKFLOW.md#3-build)
- NVIDIA Container Toolkit configured → `docker run --rm --gpus all ubuntu nvidia-smi`
- Existing workspace → `mkdir -p ~/colcon_ws/src`

## Configure

```bash
cd composer/isaaclab
cp .env.example .env              # set IMAGE and HOST_WS
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose config --quiet
```

| Variable | Default | Meaning |
|---|---|---|
| `IMAGE` | required | final creator image |
| `HOST_WS` | required | existing absolute workspace path |
| `LOCAL_UID`, `LOCAL_GID` | required (export) | must match the image account |
| `CONTAINER_NAME` | `isaaclab` | container name |
| `CONTAINER_USER` | `admin` | account name inside the image |
| `WORKSPACE_UMASK` | `0022` | `0002` for shared group output |
| `ISAACSIM_KIT_CACHE` | `/opt/isaac-venv/lib/python3.12/site-packages/isaacsim/kit/cache` | Kit cache path in the image |
| `ISAACLAB_DIR` | `/opt/IsaacLab` | Isaac Lab source path in the image |
| `XAUTH_DIR` | required with `compose.x11.yml` | directory holding the wildcard cookie |

- Check paths of your image → `docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$IMAGE" | grep -E 'ISAAC(SIM_ROOT|LAB_DIR)'`

## Use (headless)

| Action | Command |
|---|---|
| Start | `docker compose up -d` |
| Shell | `docker compose exec isaaclab bash` |
| Stop, keep volumes | `docker compose down` |
| Stop, delete all volumes | `docker compose down -v` |

## Use with a GUI (X11)

- Create the wildcard cookie (same directory `run_env.sh` uses):

```bash
export XAUTH_DIR="${XDG_RUNTIME_DIR:-/tmp}/docker-envs-xauth-$(id -u)"
mkdir -p -m 700 "$XAUTH_DIR"
xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH_DIR/xauth" nmerge -
```

- Start with the override:

```bash
docker compose -f compose.yml -f compose.x11.yml up -d
docker compose exec isaaclab bash
```

- New login / cookie → rerun the `xauth` line; running containers see the update
- X server access controls → unchanged

## Inside the container

```bash
isaac-activate
cd /opt/IsaacLab
isaaclab -p scripts/tutorials/00_sim/create_empty.py --headless
```

- ROS 2 → separate shell, `deactivate`, `colcon build` from `~/colcon_ws`
- More → [workflow guide](../../docs/ISAAC_WORKFLOW.md#6-inside-the-container-isaac-lab)

## Volumes

| Volume | Container path |
|---|---|
| `isaac-cache-ov` | `~/.cache/ov` |
| `isaac-cache-pip` | `~/.cache/pip` |
| `isaac-cache-gl` | `~/.cache/nvidia/GLCache` |
| `isaac-cache-compute` | `~/.nv/ComputeCache` |
| `isaac-logs`, `isaac-config` | `~/.nvidia-omniverse/logs`, `~/.nvidia-omniverse/config` |
| `isaac-data`, `isaac-docs` | `~/.local/share/ov/data`, `~/Documents` |
| `isaac-cache-kit` | `$ISAACSIM_KIT_CACHE` |
| `isaaclab-logs`, `isaaclab-data` | `$ISAACLAB_DIR/logs`, `$ISAACLAB_DIR/data_storage` |

- Home paths → from [`creator/common/isaac-cache-dirs.txt`](../../creator/common/isaac-cache-dirs.txt); a test keeps both in sync
- Image pre-creates every path as the account → new volumes are writable
- Images built before this change → rebuild the final layer, or volumes come up root-owned
- Changing the image UID → existing volumes keep old ownership → `down -v` or migrate deliberately
- `down -v` → deletes caches, config, documents, Isaac Lab logs → back up first
- Copy Isaac Lab logs to the host:

```bash
docker compose cp isaaclab:/opt/IsaacLab/logs ./isaaclab-logs
```
