"""The build selection and the plan that stages.sh derives from it.

Field names mirror the ``STAGES_*`` variables in ``creator/scripts/lib/stages.sh``
so the mapping to the bridge stays a mechanical rename rather than a translation
table that can drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields

# --------------------------------------------------------------------------- #
# Vocabulary shared with stages.sh. Anything that is a fixed list there is a
# fixed list here; anything discovered online is fetched through the bridge.
# --------------------------------------------------------------------------- #

SUPPORTED_OS = ("22.04", "24.04", "26.04")

USAGE_CHOICES = (
    ("skip", "Skip", "No application packages."),
    ("manipulation", "MoveIt", "Manipulation stack (ros-<distro>-moveit)."),
    ("navigation", "Nav2", "Navigation stack (ros-<distro>-navigation2)."),
    ("both", "Both", "MoveIt then Nav2, stacked as two layers."),
)

ISAACLAB_METHODS = (
    ("auto", "Auto", "python-env when Isaac Sim is selected, otherwise legacy."),
    ("python-env", "Python env", "Reuse the Isaac Sim venv. Requires the Isaac Sim layer."),
    ("legacy", "Legacy (Kit-less)", "Standalone Python 3.12 env. Isaac Lab 3.x without Sim."),
)

# The eight presets create_env.sh offers. The selector strings are version
# dependent (2.x and 3.x use different vocabulary), so the label carries the
# framework name and the resolved selector is filled in from the bridge.
ISAACLAB_FRAMEWORKS = ("none", "rsl_rl", "rl_games", "skrl", "sb3", "all")

ISAACLAB_PHYSICS = (
    ("default", "Default", "Keep the package selection as chosen above.", False),
    ("newton", "Newton", "Newton physics backend.", False),
    ("ovphysx", "OV PhysX", "Omniverse PhysX runtime.", False),
    ("both", "Newton + OV PhysX", "Both open backends.", False),
    ("isaacsim", "Isaac Sim PhysX", "Requires the Isaac Sim layer.", True),
    ("all", "All", "Newton, OV PhysX and Isaac Sim. Requires the Isaac Sim layer.", True),
)

ISAACLAB_VISUALIZERS = (
    ("default", "Default", "Keep the package selection as chosen above.", False),
    ("newton", "Newton", "Newton viewer.", False),
    ("rerun", "Rerun", "Rerun viewer.", False),
    ("viser", "Viser", "Viser web viewer.", False),
    ("all", "All", "Newton, Rerun and Viser.", False),
    ("kit", "Kit", "Isaac Sim Kit viewer. Requires the Isaac Sim layer.", True),
)

# stages::validate_isaaclab rejects anything this does not match.
SELECTOR_PATTERN = re.compile(
    r"^[a-z0-9_-]+(\[[a-z0-9_,-]+\])?(,[a-z0-9_-]+(\[[a-z0-9_,-]+\])?)*$"
)

# Printed by stages::run_plan before each layer: which of the plan's images
# is being built now.
LAYER_HEADING = re.compile(
    r"^== Building (?P<image>.+) \(layer (?P<step>\d+)/(?P<total>\d+)\) ==$"
)

# BuildKit's plain renderer prefixes each Dockerfile instruction with its
# position, e.g. "#7 [ 4/12] RUN apt-get install ...". That is the only
# progress signal available inside a layer, and a layer can run for minutes.
BUILD_STEP = re.compile(r"^#\d+ \[\s*(?P<done>\d+)/(?P<total>\d+)\]")


def overall_progress(layer: int, layers: int, fraction: float = 0.0) -> float:
    """Position within the whole plan, 0.0-1.0.

    *layer* is 1-based and *fraction* is how far the current layer has got, so a
    build sitting on instruction 4 of 12 of layer 2 of 3 reports 0.44 rather than
    standing still at 0.33 for minutes.
    """
    if layers <= 0:
        return 0.0
    fraction = min(max(fraction, 0.0), 1.0)
    return min(max((layer - 1 + fraction) / layers, 0.0), 1.0)


def isaaclab_major(version: str) -> int:
    """Mirror of ``stages::isaaclab_major``: branches without a number are 3.x."""
    ref = version.removeprefix("release/").removeprefix("v")
    match = re.match(r"^(\d+)\.", ref)
    return int(match.group(1)) if match else 3


@dataclass
class Selection:
    """One build configuration, i.e. the answers to create_env.sh's nine stages."""

    os: str = "24.04"
    ros: str = "rolling"
    use_cuda: bool = False
    cuda_version: str = ""
    usage: str = "skip"
    mujoco: bool = False
    mujoco_version: str = ""
    gym_version: str = ""
    isaacsim: bool = False
    isaacsim_version: str = ""
    isaaclab: bool = False
    isaaclab_version: str = ""
    isaaclab_method: str = "auto"
    isaaclab_install: str = "default"
    isaaclab_physics: str = "default"
    isaaclab_visualizer: str = "default"
    curobo: bool = False
    curobo_version: str = ""
    zenoh: bool = False
    simulation: bool = False
    username: str = "admin"
    user_uid: str = ""
    user_gid: str = ""
    namespace: str = "docker_envs"
    final_image: str = ""

    # Field name -> the STAGES_/DEG_ suffix, where the two differ.
    _ALIASES = {
        "username": "USERNAME",
        "user_uid": "USER_UID",
        "user_gid": "USER_GID",
        "final_image": "FINAL_IMAGE",
    }

    def env(self) -> dict[str, str]:
        """The ``DEG_*`` overlay query.sh applies on top of init_selection.

        Empty strings are dropped: query.sh treats an unset variable as "keep the
        stages.sh default", which is exactly what an untouched field means.
        """
        out: dict[str, str] = {}
        for spec in fields(self):
            value = getattr(self, spec.name)
            if isinstance(value, bool):
                text = "true" if value else "false"
            else:
                text = str(value)
                if not text:
                    continue
            out["DEG_" + self._ALIASES.get(spec.name, spec.name.upper())] = text
        return out

    # ----- cross-field rules, mirrored from stages::validate_isaaclab -------- #
    # The bridge is the authority on validity; these only drive enabled/disabled
    # states so the UI can stop a bad combination from being entered at all.

    def isaaclab_effective_method(self) -> str:
        if self.isaaclab_method != "auto":
            return self.isaaclab_method
        return "python-env" if self.isaacsim else "legacy"

    def isaaclab_backends_selectable(self) -> bool:
        """Physics and visualization package selection requires Isaac Lab 3.x."""
        return self.isaaclab and isaaclab_major(self.isaaclab_version) >= 3

    def option_available(self, needs_isaacsim: bool) -> bool:
        return self.isaacsim or not needs_isaacsim


@dataclass
class PlanLayer:
    """One ``docker build`` in the plan."""

    index: int
    dockerfile: str
    base: str
    image: str
    args: list[str] = field(default_factory=list)

    @property
    def build_args(self) -> list[str]:
        """``KEY=value`` pairs, without the ``--build-arg`` flags or the label."""
        out = []
        for flag, value in zip(self.args, self.args[1:]):
            if flag == "--build-arg":
                out.append(value)
        return out


@dataclass
class Plan:
    """The result of ``query.sh plan``."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    image: str = ""
    replay: str = ""
    layers: list[PlanLayer] = field(default_factory=list)
    isaaclab_method: str = ""
    isaaclab_packages: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.image)
