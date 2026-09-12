"""Headless checks that the form enforces the rules stages.sh would reject.

Skipped where PySide6 is unavailable, so the suite still runs on a machine that
only cares about the shell tooling. Everything here runs on the offscreen
platform plugin and never touches the network: the version lists are injected.
"""

import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE = True
except ImportError:  # pragma: no cover - depends on the environment
    PYSIDE = False

if PYSIDE:
    from PySide6.QtCore import QEventLoop, QTimer

    from docker_envs_gui.bridge import Bridge
    from docker_envs_gui.builder import BuildRunner
    from docker_envs_gui.widgets.log_view import LogView, strip_ansi
    from docker_envs_gui.widgets.plan_view import PlanView
    from docker_envs_gui.widgets.stage_cards import CUSTOM, StageForm


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class StageFormTests(unittest.TestCase):
    application = None

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)
        cls.defaults = cls.bridge.defaults()

    def setUp(self):
        self.form = StageForm(self.defaults)
        self.form.set_ros_options(self.bridge.ros_for_os("24.04"))
        self.form.set_isaaclab_selectors(self.bridge.isaaclab_selectors("release/3.0.0"))

    def plan(self):
        return self.bridge.plan(self.form.selection())

    def test_the_form_opens_on_a_buildable_default(self):
        plan = self.plan()
        self.assertTrue(plan.ok, plan.errors)
        self.assertEqual(plan.image, "docker_envs:24.04-rolling")

    def test_changing_ubuntu_changes_the_available_ros_distros(self):
        self.form.set_ros_options(self.bridge.ros_for_os("22.04"))
        self.assertEqual(self.form.ros_choice.values(), ["humble", "iron"])
        self.form.os_choice.set_value("22.04")
        self.assertTrue(self.plan().ok)

    def test_toggling_a_layer_changes_the_derived_name(self):
        before = self.plan().image
        self.form.mujoco_card.set_on(True)
        self.form.mujoco_version.set_value("3.12.0")
        after = self.plan().image
        self.assertNotEqual(before, after)
        self.assertIn("mujoco3.12.0", after)

    def test_isaac_sim_only_options_are_disabled_until_isaac_sim_is_on(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")

        kit = self.form.isaaclab_visualizer.findData("kit")
        self.assertFalse(self.form.isaaclab_visualizer.model().item(kit).isEnabled())
        self.form.isaacsim_card.set_on(True)
        self.assertTrue(self.form.isaaclab_visualizer.model().item(kit).isEnabled())

    def test_an_isaac_sim_only_choice_is_reset_when_isaac_sim_goes_away(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")
        self.form.isaacsim_card.set_on(True)
        self.form.isaaclab_physics.setCurrentIndex(self.form.isaaclab_physics.findData("isaacsim"))
        self.assertEqual(self.form.selection().isaaclab_physics, "isaacsim")

        self.form.isaacsim_card.set_on(False)
        self.assertEqual(self.form.selection().isaaclab_physics, "default")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_backend_pickers_are_disabled_for_isaac_lab_2x(self):
        # 2.x has no Kit-less installation path, so it also needs the Isaac Sim layer.
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("v2.3.2")
        self.assertFalse(self.form.isaaclab_physics.isEnabled())
        self.assertFalse(self.form.isaaclab_visualizer.isEnabled())
        self.assertIn("Enable the Isaac Sim layer", self.form.isaaclab_note.text())

        self.form.isaacsim_card.set_on(True)
        self.form.isaacsim_version.set_value("6.1.0.0")
        plan = self.plan()
        self.assertTrue(plan.ok, plan.errors)
        self.assertIn("isaaclab2.3.2-python-env", plan.image)

    def test_installation_method_falls_back_when_it_becomes_invalid(self):
        self.form.isaaclab_card.set_on(True)
        self.form.isaaclab_version.set_value("release/3.0.0")
        self.form.isaaclab_method.set_value("legacy")
        self.assertEqual(self.form.selection().isaaclab_method, "legacy")

        self.form.isaacsim_card.set_on(True)  # legacy forbids the Isaac Sim layer
        self.assertEqual(self.form.selection().isaaclab_method, "auto")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_custom_selectors_are_only_asked_for_when_chosen(self):
        self.form.isaaclab_card.set_on(True)
        self.assertFalse(self.form.isaaclab_custom.isVisible())
        self.form.isaaclab_packages.setCurrentIndex(self.form.isaaclab_packages.findData(CUSTOM))
        self.form.isaaclab_custom.setText("newton,rl[rsl-rl]")
        self.assertEqual(self.form.selection().isaaclab_install, "newton,rl[rsl-rl]")
        self.assertTrue(self.plan().ok, self.plan().errors)

    def test_an_image_name_override_reaches_the_plan(self):
        self.form.final_image.setText("acme/dev:latest")
        self.assertEqual(self.plan().image, "acme/dev:latest")
        self.form.final_image.clear()
        self.assertEqual(self.plan().image, "docker_envs:24.04-rolling")

    def test_a_rejected_selection_surfaces_an_error(self):
        self.form.os_choice.set_value("22.04")  # ROS options still list 24.04 distros
        plan = self.plan()
        self.assertFalse(plan.ok)
        self.assertTrue(any("not offered for Ubuntu" in message for message in plan.errors))


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.bridge = Bridge(ROOT)

    def test_plan_view_renders_every_layer(self):
        from docker_envs_gui.model import Selection

        view = PlanView()
        plan = self.bridge.plan(Selection(os="24.04", ros="jazzy", usage="both"))
        view.set_plan(plan)
        self.assertEqual(view.layers.topLevelItemCount(), len(plan.layers))
        self.assertEqual(view.image_name.text(), plan.image)
        self.assertEqual(view.replay.text(), plan.replay)

    def test_plan_view_shows_errors_and_hides_the_command(self):
        from docker_envs_gui.model import Selection

        view = PlanView()
        view.set_plan(self.bridge.plan(Selection(os="24.04", ros="humble")))
        self.assertTrue(view.messages.isVisibleTo(view))
        self.assertEqual(view.replay.text(), "")

    def test_log_view_renders_colour_and_filters_lines(self):
        view = LogView()
        view.append("\x1b[32mINFO:\x1b[0m ready\n")
        view.append("\x1b[1;36m== Building img (layer 1/2) ==\x1b[0m\n")
        self.assertEqual(view.plain_text(), "INFO: ready\n== Building img (layer 1/2) ==")
        view.filter.setText("layer")
        self.assertEqual(view.console.toPlainText().strip(), "== Building img (layer 1/2) ==")

    def test_partial_lines_are_held_until_complete(self):
        view = LogView()
        view.append("half ")
        self.assertEqual(view.console.toPlainText(), "")
        view.append("a line\n")
        self.assertEqual(view.console.toPlainText().strip(), "half a line")

    def test_strip_ansi_removes_cursor_movement_too(self):
        self.assertEqual(strip_ansi("\x1b[2K\x1b[32mdone\x1b[0m"), "done")


if __name__ == "__main__":
    unittest.main()


def group_gone(pgid, timeout=5.0):
    """True once no process in *pgid* is left.

    The shell exits on SIGTERM before its children have been reaped, so the group
    disappears shortly after the runner reports it finished, not at the same
    instant.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@unittest.skipUnless(PYSIDE, "PySide6 is not installed")
class BuildRunnerTests(unittest.TestCase):
    """The runner against a real subprocess, without Docker.

    The command stands in for run_env.sh: the runner only ever reads its merged
    output and its exit status, so synthetic output exercises the same path a
    build takes.
    """

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def run_until_finished(self, command, timeout_ms=15000):
        runner = BuildRunner(ROOT)
        events = {"output": [], "layers": [], "steps": [], "result": None}
        runner.output.connect(events["output"].append)
        runner.layer_started.connect(lambda *a: events["layers"].append(a))
        runner.step_progress.connect(lambda *a: events["steps"].append(a))

        loop = QEventLoop()
        runner.finished.connect(lambda ok, summary: events.update(result=(ok, summary)))
        runner.finished.connect(loop.quit)
        guard = QTimer()
        guard.setSingleShot(True)
        guard.timeout.connect(loop.quit)
        guard.start(timeout_ms)

        runner.start(command)
        loop.exec()
        runner.wait()
        return runner, events

    def test_output_layers_and_steps_reach_the_signals(self):
        script = (
            r"printf '== Building docker_envs/base:24.04 (layer 1/2) ==\n'; "
            r"printf '#4 [1/4] FROM ubuntu:24.04\n'; "
            r"printf '#5 [ 3/4] RUN apt-get update\n'; "
            r"printf '== Building docker_envs:24.04 (layer 2/2) ==\n'; "
            r"printf '#9 DONE 1.2s\n'"
        )
        _runner, events = self.run_until_finished(script)
        self.assertEqual(events["result"], (True, "Build finished successfully."))
        self.assertEqual(
            events["layers"],
            [(1, 2, "docker_envs/base:24.04"), (2, 2, "docker_envs:24.04")],
        )
        self.assertEqual(events["steps"], [(1, 4), (3, 4)])
        self.assertIn("RUN apt-get update", "".join(events["output"]))

    def test_a_failing_command_reports_its_exit_status(self):
        _runner, events = self.run_until_finished("echo nope >&2; exit 3")
        self.assertEqual(events["result"], (False, "Build failed (exit status 3)."))
        # stderr is merged, so a failure explains itself in the log.
        self.assertIn("nope", "".join(events["output"]))

    def test_cancel_stops_the_whole_process_group(self):
        runner = BuildRunner(ROOT)
        result = {}
        loop = QEventLoop()
        runner.finished.connect(lambda ok, summary: result.update(ok=ok, summary=summary))
        runner.finished.connect(loop.quit)

        # A child that ignores its parent dying: only a process-group signal ends
        # this, which is what a docker build under run_env.sh behaves like.
        runner.start("sleep 120 & wait")
        self.assertTrue(runner.running)
        group = runner._process.pid

        QTimer.singleShot(300, runner.cancel)
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        runner.wait()

        self.assertEqual(result.get("summary"), "Build cancelled.")
        self.assertFalse(result.get("ok"))
        self.assertTrue(group_gone(group), "the build process group outlived the cancel")

    def test_the_build_environment_forces_plain_buildkit_output(self):
        from docker_envs_gui.builder import build_environment

        env = build_environment()
        self.assertEqual(env["BUILDKIT_PROGRESS"], "plain")
        self.assertEqual(env["DOCKER_BUILDKIT"], "1")
