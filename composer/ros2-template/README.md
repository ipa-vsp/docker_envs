# ROS2 Template (Compose + Devcontainer)

This template provides two ways to run a ROS2 container: via `docker compose` or directly in VS Code as a devcontainer.

---

## VS Code Devcontainer (image-based)

The devcontainer uses the image directly — no docker-compose required.

### Setup

1. Open this folder in VS Code.
2. Run **"Reopen in Container"** (F1 → `Dev Containers: Reopen in Container`).

VS Code will start the container with:
- Only the `src/` subfolder of your host workspace mounted into the container at `/home/admin/colcon_ws/src`.
- The workspace-entrypoint script run on container creation to source ROS and configure the shell.

### Customise

Edit `.devcontainer/devcontainer.json` to adapt the template to your project:

| Field | What to change |
|---|---|
| `"image"` | Replace with your target image tag (e.g. `22.04-humble-nav2`, `24.04-jazzy-moveit`) |
| `ROS_DOMAIN_ID` | Set via host env var `export ROS_DOMAIN_ID=73` or hard-code the value |
| `"extensions"` | Add/remove VS Code extensions as needed |

### Why `postCreateCommand` calls the entrypoint

The `workspace-entrypoint.sh` script appends ROS sourcing and shell configuration to `~/.bashrc` inside the container. Running it via `postCreateCommand` ensures the shell is correctly configured when VS Code opens a new terminal.

> **Note:** The script appends to `~/.bashrc` on every call. Rebuilding the container (not just reloading) will re-run `postCreateCommand` on a fresh `~/.bashrc`.

### User and permissions

The devcontainer runs as the `admin` user (UID 1000) defined in the image.
If your host user has a different UID, new files created inside the container may appear with mismatched ownership on the host. To avoid this, rebuild the image with your host UID/GID using the `Dockerfile.user` build args:

```bash
docker build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g) ...
```

---

## Docker Compose

### Setup

1. Copy `.env.example` to `.env` and adjust the variables:

   | Variable | Description |
   |---|---|
   | `IMAGE` | Full image reference (e.g. `ghcr.io/ipa-vsp/docker_envs:22.04-humble-moveit`) |
   | `LOCAL_UID` / `LOCAL_GID` | Your host user IDs (`id -u` / `id -g`) — avoids root-owned files in mounts |
   | `USERNAME` | Username inside the container (default: `admin`) |
   | `HOST_WS` | Absolute path to your workspace on the host |
   | `ROS_DISTRO` | ROS distribution (e.g. `humble`, `jazzy`, `rolling`) |

2. Bring the container up:

   ```bash
   docker compose up ros
   ```

3. Open a shell:

   ```bash
   docker compose exec ros bash
   ```

The workspace at `HOST_WS` is mounted to `/home/${USERNAME}/colcon_ws` inside the container.

---

## Shell prompt and git branch

The image's `workspace-entrypoint.sh` configures the shell prompt to display the current git branch when inside a git repository:

```
user@hostname:~/colcon_ws/src[origin: main]$
```

This is written into `~/.bashrc` by the entrypoint on first run. If the prompt is missing the branch, rebuild the container so `postCreateCommand` runs again on a clean `~/.bashrc`.
