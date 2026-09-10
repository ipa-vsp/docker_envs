# Isaac Sim with ROS 2 Jazzy

This fixed example installs Isaac Sim wheels on the published Jazzy development
image and persists simulator caches in named volumes. For selectable versions
and Isaac Lab, use the [creator builder](../../creator/README.md#isaac-sim-and-isaac-lab).

## Setup

Run from this directory with a configured NVIDIA container runtime:

```bash
cp .env.example .env
# Edit HOST_WS in .env to an existing absolute workspace path.
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
mkdir -p /your/workspace/src
docker compose build
docker compose up -d
docker compose exec mp0700-6.0.1 bash
```

The build context is the repository root so the shared account setup and
entrypoint are available. The build applies your UID/GID to `CONTAINER_USER`
(default `admin`) before creating its home, wheels, and cache directories. It
rejects conflicting system UIDs. Changing IDs requires rebuilding; existing
named volumes keep their previous ownership and need a deliberate migration.

Only `HOST_WS/src` is mounted. A missing source path is an error instead of being
created by Docker as root. Do not bind the whole workspace: it would hide the
image's venv at `/home/<user>/colcon_ws/.venv`.

## Run Isaac or ROS

The venv is on PATH in this example:

```bash
isaacsim
python -c "from isaacsim import SimulationApp"
```

For ROS commands that require the distribution Python, open a separate shell:

```bash
docker compose exec mp0700-6.0.1 bash -c 'export PATH=/usr/bin:$PATH; exec bash'
```

The entrypoint sources ROS, but sourcing ROS does not change which Python the
venv places on PATH. The creator's `/opt/isaac-venv` layout avoids this issue by
requiring explicit activation.

GUI use requires access to the host X server. The Compose file shares its socket
read-only; configure a valid Xauthority cookie mount and `XAUTHORITY` for your
desktop session. The example does not disable X server access controls. The
wheel installation sets `OMNI_KIT_ACCEPT_EULA=YES`; use it under the applicable
NVIDIA license.

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

The Dockerfile creates these paths as the development user so empty named
volumes can inherit usable ownership on first start. They are wheel-installation
paths; NGC binary-image mount paths are different. Test access with expansion
inside the container:

```bash
docker compose exec mp0700-6.0.1 sh -c 'id; touch "$HOME/.cache/ov/.probe"; rm "$HOME/.cache/ov/.probe"'
```

`docker compose down` preserves volumes. `docker compose down -v` deletes all
these volumes, including saved documents, configuration, and application data;
use it only when that data is disposable or backed up.

The fixed dependency set remains Torch `2.11.0` from `cu130`,
`mujoco-usd-converter==0.2.0`, and `isaacsim[all,extscache]==6.0.1.0` with Python
3.12. Validate those dependencies together before changing pins. The converter
is installed from PyPI before NVIDIA's index participates in resolution.
