# Isaac Sim 6.0.1 with ROS 2 Jazzy (fixed example)

- Status → fixed-version example, not the creator path
- Selectable versions, Isaac Lab, launcher support → [creator builder](../../creator/README.md#isaac-sim-and-isaac-lab) + [composer/isaaclab](../isaaclab/README.md)
- Base → published `ghcr.io/ipa-vsp/docker_envs:24.04-jazzy`
- Isaac Sim wheels → venv at `/home/<user>/colcon_ws/.venv`, on `PATH`
- Caches → named volumes

## Setup

- Run from this directory
- NVIDIA container runtime configured

```bash
cp .env.example .env
# Edit HOST_WS in .env → existing absolute workspace path
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
mkdir -p /your/workspace/src
docker compose build
docker compose up -d
docker compose exec mp0700-6.0.1 bash
```

- Build context → repository root (shared account setup + entrypoint)
- Build → applies your UID/GID to `CONTAINER_USER` (default `admin`) before creating home, wheels, caches
- Conflicting system UIDs → rejected
- Changing IDs → rebuild; existing named volumes keep old ownership → migrate deliberately
- Only `HOST_WS/src` mounted → missing path = error, never created as root
- Never bind the whole workspace → it would hide the venv at `/home/<user>/colcon_ws/.venv`

## Run Isaac or ROS

- Isaac (venv on `PATH`):

```bash
isaacsim
python -c "from isaacsim import SimulationApp"
```

- ROS commands needing the distribution Python → separate shell:

```bash
docker compose exec mp0700-6.0.1 bash -c 'export PATH=/usr/bin:$PATH; exec bash'
```

- Entrypoint sources ROS, but does not change which Python the venv puts first
- Creator layout (`/opt/isaac-venv` + `isaac-activate`) → avoids this issue

## GUI

- X server socket → shared read-only
- Cookie → add a valid Xauthority mount + `XAUTHORITY` for your session (or reuse [compose.x11.yml](../isaaclab/compose.x11.yml) pattern)
- X server access controls → not disabled
- `OMNI_KIT_ACCEPT_EULA=YES` → use under the applicable NVIDIA license

## Persistent storage

| Volume | Path relative to the container home |
|---|---|
| `isaac-cache-ov` | `.cache/ov` |
| `isaac-cache-gl` | `.cache/nvidia/GLCache` |
| `isaac-cache-compute` | `.nv/ComputeCache` |
| `isaac-cache-pip` | `.cache/pip` |
| `isaac-cache-kit` | `colcon_ws/.venv/lib/python3.12/site-packages/isaacsim/kit/cache` |
| `isaac-logs`, `isaac-config` | `.nvidia-omniverse/logs`, `.nvidia-omniverse/config` |
| `isaac-data`, `isaac-docs` | `.local/share/ov/data`, `Documents` |

- Dockerfile pre-creates these as the development user → empty volumes inherit usable ownership
- Wheel-installation paths; NGC binary-image paths differ
- Access check:

```bash
docker compose exec mp0700-6.0.1 sh -c 'id; touch "$HOME/.cache/ov/.probe"; rm "$HOME/.cache/ov/.probe"'
```

- `docker compose down` → keeps volumes
- `docker compose down -v` → deletes all volumes incl. documents, config, data → only when disposable or backed up

## Pinned dependencies

- Python 3.12
- Torch `2.11.0` from `cu130`
- `mujoco-usd-converter==0.2.0` (installed from PyPI before NVIDIA's index participates)
- `isaacsim[all,extscache]==6.0.1.0`
- Validate these together before changing any pin
