"""Native Windows builder behavior and parity with the existing Bash planner.

No Docker daemon or network is needed. Run on Windows for native argv and batch
coverage; Linux with pwsh runs the planner and Bash parity checks as well.
"""

import base64
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = [shutil.which(name) for name in ("powershell.exe", "pwsh")]
SHELLS = list(dict.fromkeys(shell for shell in SHELLS if shell))
GIT_BASH = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_ps(shell, code, **kwargs):
    return subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", code],
        capture_output=True,
        text=True,
        timeout=60,
        **kwargs,
    )


def helper_code(root=ROOT):
    return (
        "$ErrorActionPreference='Stop'; $WarningPreference='SilentlyContinue'; . "
        + ps_quote(root / "creator/scripts/lib/stages.ps1")
        + "; "
    )


def selection_code(selection):
    code = "$s=New-StageSelection; "
    for key, value in {"Ros": "jazzy", **selection}.items():
        literal = ("$true" if value else "$false") if isinstance(value, bool) else ps_quote(value)
        code += "$s[" + ps_quote(key) + "]=" + literal + "; "
    return code


@unittest.skipUnless(SHELLS, "PowerShell not installed")
class WindowsPlannerTests(unittest.TestCase):
    def test_stage_parity_with_bash(self):
        if not BASH:
            self.skipTest("Bash not installed")
        variable_map = {
            "OS": "OS",
            "Ros": "ROS",
            "Usage": "USAGE",
            "Cuda": "CUDA_VERSION",
            "Mujoco": "MUJOCO_VERSION",
            "Gym": "GYM_VERSION",
            "IsaacSim": "ISAACSIM_VERSION",
            "IsaacLab": "ISAACLAB_VERSION",
            "LabMethod": "ISAACLAB_METHOD",
            "LabPackages": "ISAACLAB_INSTALL",
            "LabPhysics": "ISAACLAB_PHYSICS",
            "LabVisualizer": "ISAACLAB_VISUALIZER",
            "Zenoh": "ZENOH",
            "Gazebo": "SIMULATION",
            "Namespace": "NAMESPACE",
            "Image": "FINAL_IMAGE",
            "Username": "USERNAME",
            "UserUid": "USER_UID",
            "UserGid": "USER_GID",
        }
        enables = {
            "Cuda": "USE_CUDA",
            "Mujoco": "MUJOCO",
            "IsaacSim": "ISAACSIM",
            "IsaacLab": "ISAACLAB",
        }
        cases = [
            {},
            {"OS": "22.04", "Ros": "humble", "Usage": "manipulation"},
            {"Usage": "navigation"},
            {"Usage": "both", "Zenoh": True, "Gazebo": True},
            {"Cuda": "12.8.1", "Mujoco": "3.4.0", "Gym": "1.2.0"},
            {"IsaacSim": "6.1.0.0", "IsaacLab": "release/3.0.0"},
            {"Mujoco": "3.4.0", "IsaacSim": "6.1.0.0", "IsaacLab": "release/3.0.0"},
            {"Mujoco": "3.4.0", "IsaacSim": "5.1.0"},
            {"Mujoco": "3.4.0", "IsaacLab": "release/3.0.0"},
            {
                "IsaacLab": "release/3.0.0",
                "LabPackages": "rl[rsl-rl]",
                "LabPhysics": "ovphysx",
                "LabVisualizer": "viser",
            },
            {
                "IsaacLab": "main",
                "LabPackages": "default",
                "LabPhysics": "both",
                "LabVisualizer": "all",
            },
            {"IsaacSim": "5.1.0", "IsaacLab": "v2.3.0", "LabPackages": "rsl_rl"},
            {
                "OS": "26.04",
                "Ros": "lyrical",
                "Namespace": "localhost:5000/team/dev",
                "Image": "localhost:5000/team/custom:chosen",
                "Username": "developer",
                "UserUid": "12345",
                "UserGid": "23456",
            },
        ]
        for selection in cases:
            bash_code = "source " + shlex.quote(
                (ROOT / "creator/scripts/lib/stages.sh").as_posix()
            )
            bash_code += "; stages::init_selection; STAGES_ROS=jazzy; STAGES_USER_UID=1000; STAGES_USER_GID=1000; "
            for key, value in selection.items():
                if key in enables:
                    bash_code += "STAGES_" + enables[key] + "=true; "
                literal = str(value).lower() if isinstance(value, bool) else str(value)
                bash_code += "STAGES_" + variable_map[key] + "=" + shlex.quote(literal) + "; "
            bash_code += 'stages::validate_selection >/dev/null && stages::build_plan && printf "%s\\n" "${STAGES_PLAN[@]}"'
            expected_result = subprocess.run(
                [BASH, "-c", bash_code], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(expected_result.returncode, 0, expected_result.stderr)
            expected = []
            for line in expected_result.stdout.splitlines():
                fields = line.split("|")
                fields[0] = "creator/" + fields[0].split("/creator/", 1)[1]
                if "--label" in fields:
                    fields = fields[: fields.index("--label")]
                expected.append(fields)
            for shell in SHELLS:
                with self.subTest(selection=selection, shell=shell):
                    result = run_ps(
                        shell,
                        helper_code()
                        + selection_code(selection)
                        + "New-StagePlan $s | ConvertTo-Json -Depth 8 -Compress",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    plan = json.loads(result.stdout)
                    actual = []
                    for layer in plan["Layers"]:
                        args = layer["Arguments"]
                        if "--label" in args:
                            args = args[: args.index("--label")]
                        actual.append([layer["Dockerfile"], layer["Base"], layer["Image"], *args])
                    self.assertEqual(actual, expected)
                    self.assertIn("-NonInteractive", plan["Replay"])
                    self.assertEqual(
                        plan["Layers"][-1]["Arguments"][-1],
                        "org.docker_envs.build-command=" + plan["Replay"],
                    )

    def test_invalid_combinations_and_names(self):
        cases = [
            {"OS": "20.04"},
            {"OS": "22.04"},
            {"Usage": "unknown"},
            {"UserUid": "0"},
            {"UserGid": "4294967295"},
            {"Username": "admin;echo bad"},
            {"Image": "Bad Image"},
            {"IsaacLab": "v2.3.0"},
            {"IsaacLab": "main", "LabMethod": "python-env"},
            {"IsaacSim": "5.1.0", "IsaacLab": "main"},
            {"IsaacSim": "6.1.0.0", "IsaacLab": "main", "LabMethod": "legacy"},
            {"IsaacLab": "main", "LabPhysics": "isaacsim"},
            {"IsaacLab": "main", "LabVisualizer": "kit"},
            {"IsaacLab": "main", "LabPackages": "isaacsim"},
            {"IsaacLab": "main", "LabPackages": "rl[$(whoami)]"},
            {"IsaacLab": "x" * 129, "Image": "custom:short"},
        ]
        # Batch cases in one interpreter to keep regression checks fast.
        code = helper_code()
        for case in cases:
            code += selection_code(case)
            code += "$failed=$false; try { $null=New-StagePlan $s } catch { $failed=$true }; if (!$failed) { throw 'Invalid selection accepted' }; "
        for shell in SHELLS:
            result = run_ps(shell, code)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_discovery_offline_defaults_ordering_and_branches(self):
        code = helper_code() + r"""
function Invoke-RestMethod { throw 'offline fixture' }
function Invoke-WebRequest { throw 'offline fixture' }
$s=New-StageSelection
foreach ($key in 'Cuda','Mujoco','IsaacSim','IsaacLab') { $s[$key]='latest' }
Resolve-StageVersions $s
foreach ($key in 'Cuda','Mujoco','IsaacSim','IsaacLab') {
    if ($s[$key] -ne $script:StageDefaults[$key]) { throw 'Offline fallback mismatch' }
}
function Invoke-RestMethod {
    param($Uri, $Headers, $TimeoutSec, $ErrorAction, $UseBasicParsing)
    if ($TimeoutSec -ne 20) { throw 'Missing bounded timeout' }
    if ($Uri -like '*heads/*') {
        @('release/2.0.0','main','feature/ignored','release/10.0.0','develop') |
            ForEach-Object { [pscustomobject]@{ ref="refs/heads/$_" } }
    } elseif ($Uri -like '*tags/*') {
        @('v2.9.0','v2.10.0','v3.0.0-beta','invalid') |
            ForEach-Object { [pscustomobject]@{ ref="refs/tags/$_" } }
    } else {
        @{results=@(@{name='12.9.0-cudnn-devel-ubuntu24.04'}, @{name='12.10.0-cudnn-devel-ubuntu24.04'}, @{name='13.0.0-cudnn-devel-ubuntu22.04'})}
    }
}
function Invoke-WebRequest {
    @{ Content='isaacsim-6.1.0.0 isaacsim-6.1.0.0 isaacsim-5.1.0.0' }
}
if ((@(Get-StageVersions IsaacLabBranches) -join ',') -ne 'main,develop,release/10.0.0,release/2.0.0') { throw 'Branch order mismatch' }
if ((@(Get-StageVersions IsaacLab) -join ',') -ne 'v3.0.0-beta,v2.10.0,v2.9.0') { throw 'Tag order mismatch' }
if ((@(Get-StageVersions Cuda) -join ',') -ne '12.10.0,12.9.0') { throw 'CUDA filtering mismatch' }
if ((@(Get-StageVersions IsaacSim) -join ',') -ne '6.1.0.0,5.1.0.0') { throw 'Wheel discovery mismatch' }
"""
        for shell in SHELLS:
            result = run_ps(shell, code)
            self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(os.name == "nt" and SHELLS, "Native Windows integration checks")
class WindowsLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="docker builder tests ")
        cls.work = Path(cls.temp.name)
        cls.repo = cls.work / "checkout with spaces"
        shutil.copytree(ROOT / "creator", cls.repo / "creator")
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.exists():
            cls.temp.cleanup()
            raise unittest.SkipTest(".NET Framework C# compiler not installed")
        result = subprocess.run(
            [
                str(compiler),
                "/nologo",
                "/target:exe",
                "/out:" + str(cls.work / "docker.exe"),
                str(ROOT / "tests/fixtures/docker_stub.cs"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.log = self.work / "docker.log"
        self.log.unlink(missing_ok=True)
        self.env = dict(
            os.environ,
            PATH=str(self.work) + os.pathsep + os.environ["PATH"],
            DOCKER_TEST_LOG=str(self.log),
            DOCKER_TEST_MODE="",
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [
            [base64.b64decode(arg).decode() for arg in line.split("\t")]
            for line in self.log.read_text().splitlines()
        ]

    def launch(self, shell, args=(), input=None):
        return subprocess.run(
            [
                shell,
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.repo / "creator/scripts/create_env.ps1"),
                *args,
            ],
            cwd=self.work,
            env=self.env,
            input=input,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_dry_run_help_menus_and_eof_do_not_call_docker(self):
        for shell in SHELLS:
            for args, answers in [
                (["-Help"], None),
                (["-NonInteractive", "-DryRun", "-Ros", "jazzy"], None),
                (["-DryRun"], "\n" * 14),
                ([], "\n" * 14 + "n\n"),
            ]:
                with self.subTest(shell=shell, args=args):
                    result = self.launch(shell, args, answers)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if answers:
                        for stage in range(1, 10):
                            self.assertIn(f"Stage {stage}/9", result.stdout)
            result = self.launch(shell, input="")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Input ended", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_build_arguments_and_replay(self):
        for shell in SHELLS:
            self.log.unlink(missing_ok=True)
            result = self.launch(
                shell,
                [
                    "-NonInteractive",
                    "-Ros",
                    "jazzy",
                    "-IsaacLab",
                    "release/3.0.0",
                    "-LabPackages",
                    "rl[rsl-rl]",
                    "-LabPhysics",
                    "ovphysx",
                    "-LabVisualizer",
                    "viser",
                    "-Image",
                    "test:custom",
                ],
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self.calls()
            builds = [args for args in calls if args[:2] == ["buildx", "build"]]
            self.assertEqual(len(builds), 4)
            for args in builds:
                self.assertEqual(Path(args[-1]), self.repo)
                self.assertTrue(Path(args[args.index("-f") + 1]).is_file())
                self.assertNotIn("--network", args)
                self.assertIn("--load", args)
                self.assertEqual(args[args.index("--builder") + 1], "desktop-linux")
            self.assertIn("ISAACLAB_INSTALL=rl[rsl-rl],ov[ovphysx],visualizer[viser]", builds[2])
            replay = builds[-1][builds[-1].index("--label") + 1].split("=", 1)[1]
            replay_result = run_ps(shell, replay + " -DryRun", cwd=self.repo, env=self.env)
            self.assertEqual(replay_result.returncode, 0, replay_result.stderr)
            self.assertIn("Final image: test:custom", replay_result.stdout)
            self.assertEqual(len(self.calls()), len(calls))

    def test_all_interactive_stages_with_offline_manual_versions(self):
        answers = [
            "invalid",
            "",
            "y",
            "12.8.1",
            "3",
            "3",
            "y",
            "",
            "1.2.3",
            "y",
            "",
            "y",
            "main",
            "3",
            "5",
            "6",
            "y",
            "y",
            "developer",
            "12345",
            "23456",
            "test",
            "test:full",
        ]
        for shell in SHELLS:
            code = "function Invoke-RestMethod { throw 'offline fixture' }; function Invoke-WebRequest { throw 'offline fixture' }; & "
            code += ps_quote(self.repo / "creator/scripts/create_env.ps1") + " -DryRun"
            result = run_ps(
                shell, code, input="\n".join(answers) + "\n", cwd=self.work, env=self.env
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Build plan (10 layers)", result.stdout)
            self.assertIn("Effective Lab selectors: rl[rsl-rl],visualizer[kit]", result.stdout)
            self.assertIn("-Gym '1.2.3'", result.stdout)
            self.assertIn("Final image: test:full", result.stdout)
            self.assertIn("Please enter a number", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_prerequisites_and_stop_on_first_build_failure(self):
        for shell in SHELLS:
            for mode, expected_builds in [
                ("offline", 0),
                ("windows", 0),
                ("remote", 0),
                ("no-buildx", 0),
                ("fail-second", 2),
            ]:
                with self.subTest(shell=shell, mode=mode):
                    self.log.unlink(missing_ok=True)
                    self.env["DOCKER_TEST_MODE"] = mode
                    result = self.launch(shell, ["-NonInteractive", "-Ros", "jazzy"])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Done. Final image", result.stdout)
                    if mode == "offline":
                        self.assertIn("Start Docker Desktop", result.stderr)
                        self.assertIn("dockerDesktopLinuxEngine pipe is missing", result.stderr)
                        self.assertIn("printed replay command", result.stderr)
                    self.assertEqual(
                        sum(args[:2] == ["buildx", "build"] for args in self.calls()),
                        expected_builds,
                    )
                    if expected_builds:
                        self.assertIn("Layer 2/3 failed", result.stderr)
                        self.assertIn("code 23", result.stderr)

    def test_native_argument_quoting(self):
        values = [
            "probe",
            'a "quoted" path\\',
            "",
            "a b\\\\",
            "$(whoami); & | < >",
            "it's literal",
        ]
        for shell in SHELLS:
            self.log.unlink(missing_ok=True)
            code = (
                helper_code(self.repo)
                + "Invoke-StageDocker @("
                + ",".join(ps_quote(value) for value in values)
                + ")"
            )
            result = run_ps(shell, code, env=self.env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.calls(), [values])

    def test_batch_forwards_parameters_and_exit_status(self):
        batch = str(self.repo / "creator/scripts/create_env.bat")
        for mode, expected in [("", 0), ("fail-second", 1)]:
            self.log.unlink(missing_ok=True)
            self.env["DOCKER_TEST_MODE"] = mode
            # cmd uses doubled outer quotes, not the CRT escaping subprocess
            # applies when converting an argv list for a normal executable.
            command = (
                f'cmd.exe /d /s /c ""{batch}" -NonInteractive -Ros jazzy -Image "test:batch""'
            )
            result = subprocess.run(
                command, env=self.env, cwd=self.work, capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            if not expected:
                builds = [args for args in self.calls() if args[:2] == ["buildx", "build"]]
                self.assertEqual(builds[-1][builds[-1].index("-t") + 1], "test:batch")


if __name__ == "__main__":
    unittest.main()
