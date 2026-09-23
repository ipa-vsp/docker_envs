# CANopen development and validation

Four images clone and build ROS-Industrial's `ros2_canopen` in
`/home/admin/colcon_ws/src/ros2_canopen`, using the non-root `admin` account.

| Compose service | Local base image | Upstream branch |
| --- | --- | --- |
| rolling | `docker_envs:26.04-rolling` | `master` |
| lyrical | `docker_envs:26.04-lyrical` | `master` |
| jazzy | `docker_envs:24.04-jazzy` | `master` |
| humble | `docker_envs:22.04-humble` | `humble` |

Rolling follows its current Ubuntu 26.04 platform. The upstream main development
branch is called `master`. Derived images are `docker_envs/canopen:<distro>`.

## Build and validate

Requires Linux Docker Engine, Compose v2 or newer, Bash, Git, internet access,
`patch`, and a host kernel with `vcan` support. No physical CAN hardware or display is needed.
Run from this directory:

```bash
./build_images.sh          # all four; missing bases use ../../creator/scripts/run_env.sh
./validate.sh              # all four; continues after individual failures
./build_images.sh jazzy    # rebuild one
./validate.sh jazzy        # retest one
```

Builds use four compilation jobs by default (`BUILD_JOBS=8 ./build_images.sh`).
The source branches are resolved once per invocation, and every master image uses
that same commit. `artifacts/revisions.env` records the resolution. To replay:

```bash
set -a
source artifacts/revisions.env
set +a
./build_images.sh
```

Rolling's base uses the ROS testing apt feed because Rolling desktop for 26.04
is currently absent from the stable feed. The helper applies the documented patch
to an isolated creator copy under `artifacts/rolling/`.

Commit IDs pin CANopen source; base images and apt/rosdep packages can change on
future rebuilds. Their image identities are recorded alongside build logs.
Validation refuses a failed build or a replaced image to avoid testing stale tags.

## Interactive examples

`validate.sh` loads the host's `vcan` kernel module with a short-lived Docker helper
granted `SYS_MODULE` and read-only access to `/lib/modules`. Alternatively, load it
manually with `sudo modprobe vcan` before opening a shell:

```bash
docker compose run --rm jazzy
# Inside the container, ROS and the workspace are sourced and vcan0 is up:
ros2 launch canopen_tests cia402_setup.launch.py
```

Each service has an independent network namespace and virtual CAN bus. Runtime
containers receive `NET_ADMIN` to set up that bus; the source/build/install trees
are in the image, with no host workspace mounts. Interactive container changes
are discarded by `--rm`.

## Checks and evidence

The runner builds with `BUILD_TESTING=ON` and `CANOPEN_ENABLED=ON`, then runs:

- All registered package tests, serially, followed by verbose colcon results.
- The upstream namespaced proxy, CiA402, and robot-control launch tests that are
  not registered in upstream CMake.
- The five documented examples: CiA402 service, lifecycle service, proxy
  ros2_control, CiA402 ros2_control, and robot control. Probes check SDO responses,
  lifecycle states, active controllers, PDO round trips, and commanded positions
  in joint-state feedback as applicable.

Examples run serially with a five-minute budget, including process cleanup.
Unexpected launch exits, crashed processes, failed assertions and timeouts fail
validation. Package tests have a one-hour overall budget and five-minute CTest
timeouts. Failures are not converted into skips.

`artifacts/<distro>/` contains build/validation status files, image metadata and
logs. `results/summary.json` records every check, source revision, and applied
patches; JUnit XML and colcon logs are retained. Previous result directories are
archived when validation is rerun. These generated artifacts are Git-ignored.

Compatibility changes, if needed, live in `patches/` and are applied only to the
container clone. The adjacent reference checkout remains untouched.

## Cleanup

```bash
docker compose down --remove-orphans
```

This stops/removes only containers belonging to this Compose project. It retains
images and artifacts. Remove `artifacts/` manually when its evidence is no longer
needed; no global Docker pruning is used.
