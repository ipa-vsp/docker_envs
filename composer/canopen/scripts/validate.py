#!/usr/bin/env python3
"""Run package tests and isolated, bounded example probes inside the container."""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

WORKSPACE = Path("/home/admin/colcon_ws")
RESULTS = Path("/tmp/canopen-results")
SCENARIOS = (
    "cia402_setup",
    "cia402_lifecycle_setup",
    "canopen_system",
    "cia402_system",
    "robot_control_setup",
)


def stop_group(process):
    # launch/colcon can leave descendants even when the parent has already exited.
    for sig, delay in ((signal.SIGINT, 5), (signal.SIGTERM, 3), (signal.SIGKILL, 0)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        if delay:
            time.sleep(delay)
    process.wait()


def run(command, name, timeout=300):
    print(f"RUN {name}", flush=True)
    start = time.monotonic()
    with (RESULTS / f"{name}.log").open("w") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = process.wait(timeout=timeout)
            detail = f"exit {code}"
        except subprocess.TimeoutExpired:
            code, detail = 124, f"timeout after {timeout}s"
        finally:
            stop_group(process)
    result = {
        "name": name,
        "passed": code == 0,
        "detail": detail,
        "seconds": round(time.monotonic() - start, 1),
    }
    print(result, flush=True)
    return result


def example(name):
    print(f"RUN example-{name}", flush=True)
    start = time.monotonic()
    log_path = RESULTS / f"example-{name}-launch.log"
    with log_path.open("w") as log:
        launch = subprocess.Popen(
            ["ros2", "launch", "canopen_tests", f"{name}.launch.py"],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            result = run(
                ["python3", "/opt/canopen/probe.py", name], f"example-{name}", timeout=280
            )
            if launch.poll() is not None:
                result.update(passed=False, detail=f"launch exited early: {launch.returncode}")
            # Check before deliberate shutdown so SIGINT exits do not look like crashes.
            text = log_path.read_text(errors="replace")
            if re.search(
                r"process has died|Caught exception in launch|Traceback \(most recent", text
            ):
                result.update(passed=False, detail="launch reported a crashed process")
        finally:
            stop_group(launch)
    result["seconds"] = round(time.monotonic() - start, 1)
    return result


def main():
    os.chdir(WORKSPACE)
    RESULTS.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(
        ["git", "-C", "src/ros2_canopen", "rev-parse", "HEAD"], text=True
    ).strip()
    patches = (WORKSPACE / "applied-patches.txt").read_text()
    summary = {
        "distro": os.environ["ROS_DISTRO"],
        "revision": revision,
        "patches": patches.splitlines(),
        "checks": [],
        "passed": False,
    }
    checks = summary["checks"]
    try:
        checks.append(
            run(
                [
                    "colcon",
                    "test",
                    "--executor",
                    "sequential",
                    "--return-code-on-test-failure",
                    "--event-handlers",
                    "console_direct+",
                    "--ctest-args",
                    "-j1",
                    "--timeout",
                    "300",
                ],
                "package-tests",
                3600,
            )
        )
        checks.append(run(["colcon", "test-result", "--verbose"], "package-test-results"))
        xml_paths = list((WORKSPACE / "build").glob("*/test_results/**/*.xml"))
        tests = sum(len(ET.parse(path).findall(".//testcase")) for path in xml_paths)
        checks.append({"name": "test-discovery", "passed": tests > 0, "test_cases": tests})
        # These exist upstream but are not registered by canopen_tests/CMakeLists.txt.
        for test in ("test_proxy_driver_namespaced", "test_cia402_driver", "test_robot_control"):
            checks.append(
                run(
                    [
                        "launch_test",
                        str(
                            WORKSPACE
                            / "src/ros2_canopen/canopen_tests/launch_tests"
                            / f"{test}.py"
                        ),
                        "--junit-xml",
                        str(RESULTS / f"{test}.xml"),
                    ],
                    test,
                )
            )
        for scenario in SCENARIOS:
            checks.append(example(scenario))
        summary["passed"] = all(check["passed"] for check in checks)
    finally:
        for package in (WORKSPACE / "build").iterdir():
            if (package / "test_results").is_dir():
                shutil.copytree(
                    package / "test_results",
                    RESULTS / "test_results" / package.name,
                    dirs_exist_ok=True,
                )
        shutil.copytree(WORKSPACE / "log", RESULTS / "colcon-log", dirs_exist_ok=True)
        (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (RESULTS / "applied-patches.txt").write_text(patches)
        print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
