# Native Windows companion to stages.sh. Keep stage semantics in sync; the
# cross-platform parity tests compare Dockerfiles, parents, tags and build args.
Set-StrictMode -Version 2.0
$script:CreatorRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$script:RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $script:CreatorRoot '..'))
$script:StageDefaults = @{ Cuda = '13.3.1'; Mujoco = '3.12.0'; Gym = '1.3.0'; IsaacSim = '6.1.0.0'; IsaacLab = 'release/3.0.0'; Torch = '2.11.0'; TorchVision = '0.26.0'; Curobo = 'main' }

function New-StageSelection {
    @{
        OS = '24.04'; Ros = 'rolling'; Usage = 'skip'; Cuda = ''; Mujoco = ''
        Gym = $script:StageDefaults.Gym; IsaacSim = ''; IsaacLab = ''; LabMethod = 'auto'
        LabPackages = 'default'; LabPhysics = 'default'; LabVisualizer = 'default'; Curobo = ''
        Zenoh = $false; Gazebo = $false; Username = 'admin'; UserUid = '1000'; UserGid = '1000'
        Namespace = 'docker_envs'; Image = ''
    }
}

function Get-RosOptions([string]$OS) {
    switch ($OS) { '22.04' { 'humble', 'iron' }; '24.04' { 'rolling', 'kilted', 'jazzy' }; '26.04' { 'lyrical', 'rolling' } }
}

function Get-LabMajor([string]$Ref) {
    if (($Ref -replace '^release/', '' -replace '^v', '') -match '^(\d+)\.') { return [int]$Matches[1] }
    return 3
}

function Get-LabMethod([hashtable]$Selection) {
    if ($Selection.LabMethod -ne 'auto') { return $Selection.LabMethod }
    if ($Selection.IsaacSim) { return 'python-env' }
    return 'legacy'
}

function Get-LabFramework([string]$Ref, [string]$Framework) {
    if ((Get-LabMajor $Ref) -lt 3) { return $Framework }
    switch ($Framework) {
        'none' { 'core' }; 'all' { 'rl[rsl-rl],rl[rl-games],rl[skrl],rl[sb3]' }
        'rsl_rl' { 'rl[rsl-rl]' }; 'rl_games' { 'rl[rl-games]' }
        'skrl' { 'rl[skrl]' }; 'sb3' { 'rl[sb3]' }; default { $Framework }
    }
}

function Get-LabPackages([hashtable]$Selection) {
    $packages = $Selection.LabPackages
    $extras = @()
    switch ($Selection.LabPhysics) {
        'newton' { $extras += 'newton' }; 'ovphysx' { $extras += 'ov[ovphysx]' }
        { $_ -in 'both', 'all' } { $extras += 'newton', 'ov[ovphysx]' }
    }
    if ($Selection.LabVisualizer -ne 'default') { $extras += "visualizer[$($Selection.LabVisualizer)]" }
    if (!$extras.Count) { return $packages }
    if ($packages -in 'default', 'all') { $packages = 'mimic,teleop,newton,rl,visualizer' }
    if ($packages -in 'core', 'none') { $packages = '' }
    return ((@($packages) + $extras | Where-Object { $_ }) -join ',')
}

function Assert-StageSelection([hashtable]$Selection) {
    $s = $Selection
    if ($s.OS -cnotin @('22.04', '24.04', '26.04')) { throw "Unsupported Ubuntu release: $($s.OS)" }
    if ($s.Ros -cnotin @(Get-RosOptions $s.OS)) { throw "ROS '$($s.Ros)' is not offered for Ubuntu $($s.OS)." }
    if ($s.Usage -cnotin @('skip', 'manipulation', 'navigation', 'both')) { throw "Unknown usage: $($s.Usage)" }
    if ($s.Username -cnotmatch '^[a-z_][a-z0-9_-]*$') { throw 'Username must be a lowercase Linux account name.' }
    foreach ($key in 'UserUid', 'UserGid') {
        $number = 0L
        if ($s[$key] -notmatch '^\d+$' -or ![long]::TryParse($s[$key], [ref]$number) -or $number -lt 1 -or $number -gt 4294967294) {
            throw "$key must be an integer between 1 and 4294967294."
        }
    }
    # Namespace is a repository prefix, optionally including registry and port.
    if ($s.Namespace -cnotmatch '^(?:[a-z0-9.-]+(?::[0-9]+)?/)?[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*$') {
        throw "Invalid image namespace: $($s.Namespace)"
    }
    foreach ($key in 'Cuda', 'Mujoco', 'Gym', 'IsaacSim') {
        if ($s[$key] -and $s[$key] -cnotmatch '^\d+(?:\.\d+)+(?:[A-Za-z0-9._-]*)$') { throw "Invalid $key version: $($s[$key])" }
    }
    if ($s.IsaacLab) {
        if ($s.IsaacLab -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$') { throw 'Invalid Isaac Lab tag or branch.' }
        $major = Get-LabMajor $s.IsaacLab
        $method = Get-LabMethod $s
        if ($s.LabPhysics -cnotin @('default', 'newton', 'ovphysx', 'isaacsim', 'both', 'all')) { throw 'Unknown Isaac Lab physics.' }
        if ($s.LabVisualizer -cnotin @('default', 'newton', 'rerun', 'viser', 'kit', 'all')) { throw 'Unknown Isaac Lab visualizer.' }
        if ($major -lt 3 -and ($s.LabPhysics -ne 'default' -or $s.LabVisualizer -ne 'default')) { throw 'Physics and visualization selection requires Isaac Lab 3.x.' }
        if (!$s.IsaacSim -and ($s.LabPhysics -in 'isaacsim', 'all' -or $s.LabVisualizer -eq 'kit')) { throw 'Isaac Sim PhysX and Kit visualization require the Isaac Sim layer.' }
        switch -CaseSensitive ($method) {
            'python-env' {
                if (!$s.IsaacSim) { throw 'python-env requires Isaac Sim; use legacy for Kit-less Isaac Lab 3.x.' }
                if ($major -ge 3 -and $s.IsaacSim.Split('.')[0] -ne '6') { throw 'Isaac Lab 3.x requires Isaac Sim 6.x with Python 3.12.' }
            }
            'legacy' { if ($major -lt 3 -or $s.IsaacSim) { throw 'legacy requires Kit-less Isaac Lab 3.x without Isaac Sim.' } }
            default { throw 'Isaac Lab method must be auto, legacy, or python-env.' }
        }
        if ($s.LabPackages -cnotmatch '^[a-z0-9_-]+(\[[a-z0-9_,-]+\])?(,[a-z0-9_-]+(\[[a-z0-9_,-]+\])?)*$') { throw 'Invalid Isaac Lab package selectors.' }
        if (("," + $s.LabPackages + ',') -match ',isaacsim,') { throw 'Select Isaac Sim through -IsaacSim, not the isaacsim package selector.' }
    }
    if ($s.Curobo) {
        # cuRobo is installed for Python 3.12 only (mirrors stages::validate_curobo).
        if ($s.Curobo -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$') { throw 'Invalid cuRobo tag or branch.' }
        if ($s.IsaacSim -and (Get-VenvPython $s) -ne '3.12') { throw "cuRobo needs Python 3.12; Isaac Sim $($s.IsaacSim) pins Python $(Get-VenvPython $s). Use Isaac Sim 6.x." }
        if ($s.Cuda -and $s.Cuda.Split('.')[0] -notin '12', '13') { throw "cuRobo supports CUDA 12 and 13, not $($s.Cuda)." }
        if ($s.OS -eq '22.04') { Write-Warning 'cuRobo uses Python 3.12; ROS on Ubuntu 22.04 uses 3.10, so ROS nodes cannot import it.' }
    }
    if ($s.OS -eq '24.04' -and $s.Ros -eq 'rolling') { Write-Warning 'ROS Rolling has migrated to Ubuntu 26.04; 24.04 no longer receives updated Rolling packages.' }
    if ("$($s.OS):$($s.Ros)" -notin @('24.04:rolling', '24.04:kilted', '24.04:jazzy', '22.04:humble', '26.04:lyrical')) { Write-Warning 'This Ubuntu/ROS combination is not built in CI; upstream packages may be missing.' }
    if ($s.Ros -eq 'lyrical' -and $s.Usage -ne 'skip') { Write-Warning 'MoveIt/Nav2 packages are not published for lyrical; that layer will be a no-op.' }
    if ($s.IsaacSim -and !$s.Cuda) { Write-Warning 'Isaac Sim without a CUDA base needs a CUDA-capable runtime at run time.' }
}

# The one /opt/venv interpreter (mirrors stages::venv_python).
function Get-VenvPython([hashtable]$Selection) {
    if ($Selection.IsaacSim) {
        $python = switch ($Selection.IsaacSim.Split('.')[0]) { '6' { '3.12' }; '5' { '3.11' }; '4' { '3.10' }; default { '3.11' } }
        return $python
    }
    if ($Selection.IsaacLab -or $Selection.Curobo) { return '3.12' }
    return 'system'
}

function Get-StageReplay([hashtable]$Selection) {
    $parts = @('& ./creator/scripts/create_env.ps1 -NonInteractive')
    foreach ($key in 'OS', 'Ros', 'Usage', 'Cuda', 'Mujoco', 'Gym', 'IsaacSim', 'IsaacLab', 'LabMethod', 'LabPackages', 'LabPhysics', 'LabVisualizer', 'Curobo', 'Username', 'UserUid', 'UserGid', 'Namespace', 'Image') {
        $value = [string]$Selection[$key]
        if ($key -eq 'LabMethod' -and $Selection.IsaacLab) { $value = Get-LabMethod $Selection }
        if ($value) { $parts += "-$key '" + $value.Replace("'", "''") + "'" }
    }
    foreach ($key in 'Zenoh', 'Gazebo') { if ($Selection[$key]) { $parts += "-$key" } }
    return $parts -join ' '
}

function New-StagePlan([hashtable]$Selection) {
    Assert-StageSelection $Selection
    $s = $Selection
    $state = @{ Tag = $s.OS; Parent = $s.OS; Layers = [Collections.Generic.List[object]]::new() }
    # A child scope mutates this state object rather than relying on dynamic variable assignment.
    $add = {
        param($Layer, $File, $Component, $BuildArguments)
        if ($Component) { $state.Tag += "-$Component" }
        if ($state.Tag.Length -gt 128) { throw 'Derived tag exceeds Docker limit of 128 characters (including intermediate images). Shorten the selection or version ref.' }
        $image = "$($s.Namespace)/${Layer}:$($state.Tag)"
        $state.Layers.Add([pscustomobject]@{ Dockerfile = "creator/$File"; Base = $state.Parent; Image = $image; Arguments = @($BuildArguments) })
        $state.Parent = $image
    }
    if ($s.Cuda) {
        $state.Parent = "nvidia/cuda:$($s.Cuda)-cudnn-devel-ubuntu$($s.OS)"
        & $add 'base' 'common/Dockerfile.cuda' "cuda$($s.Cuda)" @()
    } else { & $add 'base' 'common/Dockerfile.base' '' @() }
    & $add 'ros' "ros2/Dockerfile.$($s.Ros)" $s.Ros @()
    # The shared /opt/venv is created once, straight after ROS.
    $python = Get-VenvPython $s
    $component = ''
    if ($python -ne 'system') { $component = "py$python" }
    & $add 'venv' 'common/Dockerfile.venv' $component @('--build-arg', "PYTHON_VERSION=$python")
    if ($s.Mujoco) {
        & $add 'mujoco' 'common/Dockerfile.mujoco' "mujoco$($s.Mujoco)" @('--build-arg', "MUJOCO_VERSION=$($s.Mujoco)", '--build-arg', "GYM_VERSION=$($s.Gym)")
    }
    if ($s.Usage -in 'manipulation', 'both') { & $add 'moveit' 'usage/Dockerfile.moveit' 'moveit' @('--build-arg', "ROS_DISTRO=$($s.Ros)") }
    if ($s.Usage -in 'navigation', 'both') { & $add 'nav2' 'usage/Dockerfile.nav2' 'nav2' @('--build-arg', "ROS_DISTRO=$($s.Ros)") }
    if ($s.IsaacSim) {
        & $add 'isaacsim' 'common/Dockerfile.isaacsim' "isaacsim$($s.IsaacSim)" @('--build-arg', "ISAACSIM_VERSION=$($s.IsaacSim)", '--build-arg', "PYTHON_VERSION=$python", '--build-arg', "TORCH_VERSION=$($script:StageDefaults.Torch)", '--build-arg', "TORCHVISION_VERSION=$($script:StageDefaults.TorchVision)")
    }
    if ($s.IsaacLab) {
        $method = Get-LabMethod $s
        $packages = Get-LabPackages $s
        $ref = ($s.IsaacLab -creplace '^v', '') -creplace '[^A-Za-z0-9._-]', '-'
        $component = "isaaclab$ref-$method"
        if ($packages -ne 'default') {
            $sha = [Security.Cryptography.SHA256]::Create()
            try { $hash = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($packages)))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }
            $component += '-packages' + $hash.Substring(0, 8)
        }
        & $add 'isaaclab' 'common/Dockerfile.isaaclab' $component @('--build-arg', "ISAACLAB_VERSION=$($s.IsaacLab)", '--build-arg', "ISAACLAB_METHOD=$method", '--build-arg', "ISAACLAB_INSTALL=$packages")
    }
    if ($s.Curobo) {
        $cuda = '12'
        if ($s.Cuda) { $cuda = $s.Cuda.Split('.')[0] }
        $ref = ($s.Curobo -creplace '^v', '') -creplace '[^A-Za-z0-9._-]', '-'
        & $add 'curobo' 'common/Dockerfile.curobo' "curobo$ref" @('--build-arg', "CUROBO_VERSION=$($s.Curobo)", '--build-arg', "CUROBO_CUDA=$cuda")
    }
    if ($s.Zenoh) { & $add 'zenoh' 'usage/Dockerfile.zenoh' 'zenoh' @() }
    if ($s.Gazebo) { & $add 'gazebo' 'usage/Dockerfile.gazebo' 'gazebo' @() }
    $final = "$($s.Namespace):$($state.Tag)"
    if ($s.Image) { $final = $s.Image }
    # Reuse namespace validation for repository names; validate the optional tag separately.
    if ($final -cnotmatch '^(?:[a-z0-9.-]+(?::[0-9]+)?/)?[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?$') { throw "Invalid final image name: $final" }
    $replaySelection = $s.Clone()
    $replaySelection.Image = $final
    $replay = Get-StageReplay $replaySelection
    $state.Layers.Add([pscustomobject]@{ Dockerfile = 'creator/common/Dockerfile.user'; Base = $state.Parent; Image = $final; Arguments = @('--build-arg', "USERNAME=$($s.Username)", '--build-arg', "USER_UID=$($s.UserUid)", '--build-arg', "USER_GID=$($s.UserGid)", '--build-arg', "ROS_DISTRO=$($s.Ros)", '--label', "org.docker_envs.build-command=$replay") })
    foreach ($layer in $state.Layers) { if (!(Test-Path -LiteralPath (Join-Path $script:RepositoryRoot $layer.Dockerfile) -PathType Leaf)) { throw "Missing Dockerfile: $($layer.Dockerfile)" } }
    [pscustomobject]@{ Layers = $state.Layers.ToArray(); FinalImage = $final; Replay = $replay }
}

function Sort-StageVersions([string[]]$Versions) {
    # Numeric segments avoid lexicographic 9 > 10 ordering; retain prerelease refs.
    $Versions | Sort-Object -Unique | Sort-Object -Descending -Property @{ Expression = { [regex]::Replace($_, '\d+', { param($m) $m.Value.PadLeft(12, '0') }) } }
}

function Get-StageVersions([string]$Kind, [string]$OS = '24.04', [int]$Limit = 8) {
    $previousTls = [Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol = $previousTls -bor [Net.SecurityProtocolType]::Tls12
        $request = @{ UseBasicParsing = $true; TimeoutSec = 20; ErrorAction = 'Stop'; Headers = @{ 'User-Agent' = 'docker-envs-windows' } }
        switch ($Kind) {
            'Cuda' {
                $response = Invoke-RestMethod @request -Uri "https://hub.docker.com/v2/repositories/nvidia/cuda/tags?page_size=100&name=cudnn-devel-ubuntu$OS"
                $versions = @($response.results | ForEach-Object { if ($_.name -match "^(\d+\.\d+\.\d+)-cudnn-devel-ubuntu$([regex]::Escape($OS))$") { $Matches[1] } })
            }
            'IsaacSim' {
                $response = Invoke-WebRequest @request -Uri 'https://pypi.nvidia.com/isaacsim/'
                $versions = @([regex]::Matches($response.Content, 'isaacsim-([0-9]+(?:\.[0-9]+)+)') | ForEach-Object { $_.Groups[1].Value })
            }
            default {
                $repository = 'isaac-sim/IsaacLab'
                $refType = 'tags'
                if ($Kind -eq 'Mujoco') { $repository = 'google-deepmind/mujoco' }
                if ($Kind -eq 'IsaacLabBranches') { $refType = 'heads' }
                $response = @(Invoke-RestMethod @request -Uri "https://api.github.com/repos/$repository/git/matching-refs/$refType/")
                $versions = @($response | ForEach-Object { $_.ref -replace "^refs/$refType/", '' })
                if ($Kind -eq 'Mujoco') { $versions = @($versions | Where-Object { $_ -match '^\d+\.\d+(\.\d+)?$' }) }
                elseif ($Kind -eq 'IsaacLab') { $versions = @($versions | Where-Object { $_ -match '^v\d+\.\d+\.\d+' }) }
                else {
                    $branches = @('main', 'develop' | Where-Object { $_ -in $versions })
                    $branches += @(Sort-StageVersions @($versions | Where-Object { $_ -match '^release/v?\d+\.\d+' }))
                    return $branches | Select-Object -First $Limit
                }
            }
        }
        Sort-StageVersions $versions | Select-Object -First $Limit
    } catch { Write-Warning "Could not look up $Kind versions: $($_.Exception.Message)" }
    finally { [Net.ServicePointManager]::SecurityProtocol = $previousTls }
}

function Resolve-StageVersions([hashtable]$Selection) {
    # cuRobo is built from a branch; "latest" means its main line.
    if ($Selection.Curobo -eq 'latest') { $Selection.Curobo = $script:StageDefaults.Curobo }
    foreach ($key in 'Cuda', 'Mujoco', 'IsaacSim', 'IsaacLab') {
        if ($Selection[$key] -eq 'latest') {
            $found = @(Get-StageVersions $key $Selection.OS 1)
            if ($found.Count) { $Selection[$key] = $found[0] }
            else { Write-Warning "Using built-in $key default: $($script:StageDefaults[$key])"; $Selection[$key] = $script:StageDefaults[$key] }
        }
    }
}

function ConvertTo-NativeArgument([AllowEmptyString()][string]$Value) {
    # ProcessStartInfo.Arguments uses CRT quoting on Windows. Explicit quoting
    # also preserves embedded quotes on Windows PowerShell 5.1 (unlike & splatting).
    '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Invoke-StageDocker([string[]]$Arguments, [switch]$Capture) {
    $docker = Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $docker.Source
    $info.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = [bool]$Capture
    $info.RedirectStandardError = [bool]$Capture
    $info.EnvironmentVariables['DOCKER_BUILDKIT'] = '1'
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    $started = $false
    try {
        [void]$process.Start()
        $started = $true
        $output = ''
        $errorOutput = ''
        if ($Capture) {
            # Drain both pipes concurrently: Docker sends connection failures
            # to stderr, and reading either pipe sequentially can deadlock.
            $stdoutTask = $process.StandardOutput.ReadToEndAsync()
            $stderrTask = $process.StandardError.ReadToEndAsync()
            $output = $stdoutTask.GetAwaiter().GetResult()
            $errorOutput = $stderrTask.GetAwaiter().GetResult()
        }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            $message = "Docker exited with code $($process.ExitCode): $($Arguments -join ' ')"
            if ($errorOutput.Trim()) { $message += "`n$($errorOutput.Trim())" }
            throw $message
        }
        if ($errorOutput.Trim()) { [Console]::Error.WriteLine($errorOutput.Trim()) }
        if ($Capture) { return $output.Trim() }
    } finally {
        # Also disconnect the Docker client if the user interrupts a build.
        if ($started -and !$process.HasExited) { $process.Kill() }
        $process.Dispose()
    }
}

function Invoke-StagePlan($Plan) {
    if (!(Get-Command docker -CommandType Application -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found. Install Docker Desktop and start its Linux engine.' }
    try { $osType = Invoke-StageDocker @('info', '--format', '{{.OSType}}') -Capture }
    catch {
        throw "Cannot connect to the Docker engine. Start Docker Desktop and wait until its Linux engine is running, then retry the printed replay command. If Docker is already running, check the selected endpoint with 'docker context ls' and any DOCKER_HOST/DOCKER_CONTEXT overrides.`n$($_.Exception.Message)"
    }
    if ($osType -ne 'linux') { throw 'Docker must be running Linux containers. Switch Docker Desktop to Linux containers.' }
    $null = Invoke-StageDocker @('buildx', 'version') -Capture
    # Text fields work with the Buildx shipped in older Docker Desktop releases,
    # where inspect does not yet accept --format.
    $builder = Invoke-StageDocker @('buildx', 'inspect') -Capture
    if ($builder -notmatch '(?m)^Driver:\s+(\S+)\s*$' -or $Matches[1] -ne 'docker') { throw 'A Docker-driver builder is required so each stage can use local parent images. Select one with docker buildx use <name>.' }
    if ($builder -notmatch '(?m)^Name:\s+(\S+)\s*$') { throw 'Could not determine the selected Buildx builder name.' }
    $builderName = $Matches[1]
    $step = 0
    foreach ($layer in $Plan.Layers) {
        $step++
        Write-Host "`nBuilding $($layer.Image) (layer $step/$($Plan.Layers.Count))" -ForegroundColor Cyan
        $dockerArgs = @('buildx', 'build', '--builder', $builderName, '--load', '-f', (Join-Path $script:RepositoryRoot $layer.Dockerfile), '-t', $layer.Image, '--build-arg', "BASE_IMAGE=$($layer.Base)") + $layer.Arguments + @($script:RepositoryRoot)
        try { Invoke-StageDocker $dockerArgs }
        catch { throw "Layer $step/$($Plan.Layers.Count) failed: $($layer.Image). Stopping; final image was NOT built. Completed layers remain cached. $($_.Exception.Message)" }
    }
    Write-Host "Done. Final image: $($Plan.FinalImage)" -ForegroundColor Green
}
