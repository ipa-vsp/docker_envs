# docker_envs Image Builder

A desktop front end for the staged image builder in `creator/`. It is the third
way to build the same images, beside the two existing ones:

| Front end | Best for |
| --------- | -------- |
| `creator/scripts/create_env.sh` | A guided walk through the stages on a terminal. |
| `creator/scripts/run_env.sh` | Scripting and CI, once you know the flags. |
| **`docker-envs-gui`** | Seeing every stage at once, with the image name, the build plan and the resulting command updating as you choose. |

All three produce identical images, because all three ask the same library —
`creator/scripts/lib/stages.sh` — what is valid and what a stack is called.

## Running it

From a checkout:

```bash
pip install ./gui        # or: pip install -e ./gui
docker-envs-gui          # or: python -m docker_envs_gui
```

Or download the AppImage from a release, make it executable and run it. The
AppImage carries its own copy of `creator/`, so it builds images on a machine
with no checkout at all.

Useful arguments:

| Argument | Effect |
| -------- | ------ |
| `--repo-root PATH` | Build from a particular `docker_envs` checkout. |
| `--check` | Resolve the checkout, plan the default stack, print the result and exit. No window; used by the packaging pipeline. |
| `--version` | Print the version. |

The checkout is resolved in this order:

1. `--repo-root`
2. `$DOCKER_ENVS_ROOT`
3. the path saved from *Change checkout…*
4. the checkout this package was installed from — an editable install or
   `python -m docker_envs_gui` inside the repository
5. the checkout the process was launched from, walking up from the working
   directory — this is what makes a plain `pip install ./gui` work
6. the copy bundled into the AppImage

Whichever wins is shown in the header, so it is never a guess. Running the
AppImage from inside a checkout therefore uses that checkout rather than its
bundled copy; launch it from anywhere else, or pass `--repo-root`, to use the
bundle.

## What it does

Three tabs, with the build status bar shared across all of them so a build stays
visible and cancellable wherever you are:

| Tab | Contents |
| --- | -------- |
| **Build** | The nine stages, the plan, and the build log. |
| **Images** | Everything `docker image ls --all` reports. |
| **Containers** | Everything `docker ps -a` reports, with Stop, Restart and Remove. |

The two Docker tabs load the first time you open them and then only when you
press **Refresh**; nothing polls the daemon behind your back. The Images tab also
re-reads itself after a build finishes.

### Build

The left column is `create_env.sh`'s nine stages as one form. Choices that
`stages.sh` would reject are disabled with the reason in a tooltip — Kit
visualization without the Isaac Sim layer, backend selection on Isaac Lab 2.x,
`legacy` installation alongside Isaac Sim — so an invalid stack is hard to
express and always explained.

The right column shows what the selection produces: the derived image name, the
ordered layers with their build arguments, any warnings `stages.sh` raised, and
the `run_env.sh -b …` command that reproduces it. **Build** runs that exact
command, so the log is the same log the CLI prints and the image carries the
same `org.docker_envs.build-command` label. **Dry run** appends `-p` and stops
after the plan.

### Version pickers

CUDA, MuJoCo, Isaac Sim and Isaac Lab are filled by the same online lookups
`create_env.sh` uses — MuJoCo tags, the NVIDIA package index, Isaac Lab tags and
branches, CUDA images on Docker Hub — newest first, and they fall back to the
built-in defaults when a lookup fails.

Each entry's text is the version exactly as it is passed to `run_env.sh`, never a
decorated label. Isaac Lab annotates its entries — `latest tag`, `tag`,
`branch, moves with upstream` — but the annotation is drawn only in the dropdown,
so picking `release/3.0.0` yields the ref git can resolve rather than
`release/3.0.0 (branch, …)`. The pickers stay editable, so an exact version can
always be typed in, and **Refresh versions** keeps a version you deliberately
chose instead of resetting it to the newest one. A picker you have not touched
does follow the newest release, as the wizard does.

### Build log

The log has two size controls, because it is the part of the window you actually
watch:

| Control | Effect |
| ------- | ------ |
| **Expand** (`Ctrl+Shift+E`) | Collapses the stage form and the plan so the log fills the window. **Restore** puts the split back exactly as it was. |
| **Pop out** (`Ctrl+Shift+L`) | Moves the log into a window of its own — parentless, so it can sit on another monitor or behind the builder. **Dock**, closing that window, or *Bring it back* returns it. |

It is the same widget either way, so output keeps streaming and the scrollback
survives the move. Alongside them: a live filter, a Follow toggle for
auto-scroll, Save and Clear.

Cancelling signals the whole build process group, so the `docker build`
underneath `run_env.sh` stops with it rather than being orphaned.

### Images

Repository, tag, ID, age and size for every image, newest first, including
dangling layers left by rebuilds. Sizes sort by their real magnitude rather than
as text. A **Built here** column marks images carrying
`org.docker_envs.build-command`, and selecting one shows that stored command, so
you can see exactly how an image was made — and copy it to make it again.

### Containers

Name, image, state, status, age and ports for every container, running ones
first. Select one or several, then:

| Action | Behaviour |
| ------ | --------- |
| **Stop** | `docker container stop`. Offered only when something selected is running, and it skips the ones that are not. |
| **Restart** | `docker container restart`. |
| **Remove** | `docker container rm`, after a confirmation naming every container, saying how many are running and will be killed first, and noting that bind-mounted host workspaces are not touched. `--force` is added only for the containers that are actually running. |

If one container in a batch fails, the others still run and the failure is
reported with Docker's own message; the listing is re-read either way.

Starting containers stays on the command line: `run_env.sh -r/-S` needs a
workspace, device and network decisions that belong with the launcher.

## How it talks to stages.sh

Nothing in the Python encodes a build rule. `creator/scripts/lib/query.sh`
sources `stages.sh`, swaps its four output helpers for record emitters and
exposes the answers as unit-separated (`0x1f`) records:

```bash
DEG_OS=24.04 DEG_ROS=jazzy DEG_USAGE=manipulation creator/scripts/lib/query.sh plan
```

```
IMAGE  docker_envs:24.04-jazzy-moveit
REPLAY creator/scripts/run_env.sh -b -o 24.04 -v jazzy -u manipulation …
LAYER  1 common/Dockerfile.base  24.04  docker_envs/base:24.04
…
```

Subcommands: `plan`, `versions`, `branches`, `ros-for-os`, `isaaclab-selectors`,
`defaults`. A selection is passed as `DEG_<FIELD>` environment variables, which
`query.sh` overlays onto `stages::init_selection` — a deliberately separate
namespace, so a `STAGES_*` variable exported in your shell can never steer a
build. `plan` always exits 0; an invalid selection is reported as `ERROR`
records, not as a failure.

`tests/test_gui_bridge.py` asserts that `query.sh` and `run_env.sh -p` agree on
the image name, the replay command and the layer count for the same selection.
That is what keeps the GUI from drifting away from the CLI.

## Development

```bash
pip install -e ./gui
python3 -m unittest discover -s tests -p 'test_gui_*.py' -v
pre-commit run --all-files
```

Tests are stdlib `unittest`, like the rest of the repository.
`test_gui_bridge.py` and `test_gui_model.py` need no Qt; `test_gui_smoke.py`
runs on the offscreen platform plugin and skips itself where PySide6 is missing.

## Building the AppImage

```bash
pip install ./gui pyinstaller
gui/packaging/build-appimage.sh          # writes gui/dist/
```

This is the same script `.github/workflows/gui-appimage.yml` runs, so a CI
failure reproduces locally. The workflow builds on `ubuntu-22.04` on purpose: an
AppImage inherits the glibc of the machine that built it, so building on a newer
runner would produce one that refuses to start on older systems. Tagged pushes
(`v*`) attach the AppImage and its checksum to the GitHub release.

The final step runs the packaged application with `--check` from `/`, which
proves the bundled `creator/` tree is not merely present but usable.
