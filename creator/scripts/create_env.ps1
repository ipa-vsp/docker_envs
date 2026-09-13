#Requires -Version 5.1
<#
.SYNOPSIS
Interactively build Linux development images from Windows using Docker Desktop.
.EXAMPLE
.\creator\scripts\create_env.ps1 -DryRun
.EXAMPLE
.\creator\scripts\create_env.ps1 -NonInteractive -OS 24.04 -Ros jazzy -Usage manipulation
.EXAMPLE
.\creator\scripts\create_env.ps1 -NonInteractive -IsaacLab release/3.0.0 -LabPackages 'rl[rsl-rl]' -LabPhysics ovphysx -LabVisualizer viser
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [switch]$DryRun,
    [switch]$NonInteractive,
    [string]$OS = '24.04',
    [string]$Ros = 'rolling',
    [string]$Usage = 'skip',
    [string]$Cuda = '',
    [string]$Mujoco = '',
    [string]$Gym = '1.3.0',
    [string]$IsaacSim = '',
    [string]$IsaacLab = '',
    [string]$LabMethod = 'auto',
    [string]$LabPackages = 'default',
    [string]$LabPhysics = 'default',
    [string]$LabVisualizer = 'default',
    [switch]$Zenoh,
    [switch]$Gazebo,
    [string]$Username = 'admin',
    [string]$UserUid = '1000',
    [string]$UserGid = '1000',
    [string]$Namespace = 'docker_envs',
    [string]$Image = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib/stages.ps1')

function Read-BuilderLine([string]$Prompt) {
    Write-Host -NoNewline "${Prompt}: "
    # ReadLine supports piped answers on both PowerShell versions. EOF must not
    # silently accept defaults and authorize an unintended build.
    $answer = [Console]::ReadLine()
    if ($null -eq $answer) { throw 'Input ended. Nothing further will be built; use -NonInteractive for unattended builds.' }
    return $answer.Trim()
}

function Read-BuilderValue([string]$Prompt, [string]$Default) {
    $answer = Read-BuilderLine "$Prompt [$Default]"
    if (!$answer) { return $Default }
    return $answer
}

function Read-BuilderChoice([string]$Prompt, [string[]]$Options, [int]$Default = 1) {
    Write-Host "`n$Prompt"
    for ($i = 0; $i -lt $Options.Count; $i++) {
        $hint = ''
        if (($i + 1) -eq $Default) { $hint = ' [default]' }
        Write-Host ('  {0,2}) {1}{2}' -f ($i + 1), $Options[$i], $hint)
    }
    while ($true) {
        $answer = Read-BuilderValue "Select [1-$($Options.Count)]" ([string]$Default)
        $index = 0
        if ([int]::TryParse($answer, [ref]$index) -and $index -ge 1 -and $index -le $Options.Count) {
            Write-Host "  -> $($Options[$index - 1])"
            return $index - 1
        }
        Write-Host "Please enter a number between 1 and $($Options.Count)."
    }
}

function Read-BuilderYesNo([string]$Prompt, [bool]$Default = $false) {
    $hint = 'y/N'
    if ($Default) { $hint = 'Y/n' }
    while ($true) {
        $answer = Read-BuilderLine "$Prompt [$hint]"
        if (!$answer) { return $Default }
        if ($answer -match '^(y|yes)$') { return $true }
        if ($answer -match '^(n|no)$') { return $false }
        Write-Host 'Please answer y or n.'
    }
}

function Read-BuilderVersion([string]$Kind, [string]$Ubuntu) {
    Write-Host "`nLooking up available $Kind versions..."
    $limit = 8
    if ($Kind -eq 'IsaacLab') { $limit = 4 }
    $versions = @(Get-StageVersions $Kind $Ubuntu $limit)
    $branches = @()
    if ($Kind -eq 'IsaacLab') { $branches = @(Get-StageVersions 'IsaacLabBranches' $Ubuntu 4) }
    if (!$versions.Count -and !$branches.Count) {
        Write-Warning "Using built-in $Kind default."
        return Read-BuilderValue "$Kind version" $script:StageDefaults[$Kind]
    }
    $values = @($versions) + @($branches)
    $labels = @()
    for ($i = 0; $i -lt $versions.Count; $i++) {
        $label = $versions[$i]
        if ($i -eq 0) { $label += ' (latest release)' }
        elseif ($Kind -eq 'IsaacLab') { $label += ' (tag)' }
        $labels += $label
    }
    $labels += @($branches | ForEach-Object { "$_ (branch, moves with upstream)" })
    $labels += 'other (type a version, tag or branch)'
    $index = Read-BuilderChoice "Which $Kind version?" $labels
    if ($index -eq $values.Count) { return Read-BuilderValue "$Kind version" $values[0] }
    return $values[$index]
}

function Read-BuilderSelection([hashtable]$Selection) {
    $s = $Selection
    Write-Host "`ndocker_envs :: interactive Windows image builder`nPress Enter to accept the [default]."
    Write-Host "`n== Stage 1/9 - Ubuntu release ==" -ForegroundColor Cyan
    $options = @('22.04', '24.04', '26.04')
    $s.OS = $options[(Read-BuilderChoice 'Which Ubuntu release?' $options 2)]
    Write-Host "`n== Stage 2/9 - Base image ==" -ForegroundColor Cyan
    $s.Cuda = ''
    if (Read-BuilderYesNo 'Use the NVIDIA CUDA + cuDNN development base?') { $s.Cuda = Read-BuilderVersion 'Cuda' $s.OS }
    Write-Host "`n== Stage 3/9 - ROS 2 distribution ==" -ForegroundColor Cyan
    $options = @(Get-RosOptions $s.OS)
    $labels = @($options | ForEach-Object {
        $label = $_
        if ("$($s.OS):$_" -in '24.04:rolling', '24.04:kilted', '24.04:jazzy', '22.04:humble', '26.04:lyrical') { $label += ' (built in CI)' }
        if ($s.OS -eq '24.04' -and $_ -eq 'rolling') { $label += ' (frozen upstream)' }
        $label
    })
    $s.Ros = $options[(Read-BuilderChoice 'Which ROS 2 distribution?' $labels)]
    Write-Host "`n== Stage 4/9 - Application stack ==" -ForegroundColor Cyan
    $options = @('manipulation (MoveIt)', 'navigation (Nav2)', 'both', 'skip')
    $default = 4
    if ($s.Ros -eq 'lyrical') {
        Write-Warning 'MoveIt/Nav2 are not published for lyrical yet.'
        $options = @('skip', 'manipulation (MoveIt)', 'navigation (Nav2)', 'both'); $default = 1
    }
    $s.Usage = $options[(Read-BuilderChoice 'Which application packages?' $options $default)].Split(' ')[0]
    Write-Host "`n== Stage 5/9 - MuJoCo ==" -ForegroundColor Cyan
    if (Read-BuilderYesNo 'Add the MuJoCo physics layer?') {
        $s.Mujoco = Read-BuilderVersion 'Mujoco' $s.OS
        $s.Gym = Read-BuilderValue 'Gymnasium version' $s.Gym
    }
    Write-Host "`n== Stage 6/9 - NVIDIA Isaac Sim ==" -ForegroundColor Cyan
    if (Read-BuilderYesNo 'Add Isaac Sim (large: several GB of wheels)?') { $s.IsaacSim = Read-BuilderVersion 'IsaacSim' $s.OS }
    Write-Host "`n== Stage 7/9 - NVIDIA Isaac Lab ==" -ForegroundColor Cyan
    if (Read-BuilderYesNo 'Add the Isaac Lab layer?') {
        $s.IsaacLab = Read-BuilderVersion 'IsaacLab' $s.OS
        $s.LabMethod = Get-LabMethod $s
        Write-Host "Installation method: $($s.LabMethod)"
        $values = @('default')
        $labels = @('default (upstream -i defaults)')
        foreach ($framework in 'none', 'rsl_rl', 'rl_games', 'skrl', 'sb3', 'all') {
            $selector = Get-LabFramework $s.IsaacLab $framework
            $values += $selector
            $name = $framework
            if ($framework -eq 'none') { $name = 'core (no optional packages)' }
            if ($framework -eq 'all') { $name = 'all RL frameworks' }
            $labels += "$name ($selector)"
        }
        $labels += 'custom (comma-separated package selectors)'
        $index = Read-BuilderChoice 'Which Isaac Lab packages?' $labels
        if ($index -eq $values.Count) { $s.LabPackages = Read-BuilderValue 'Selectors, e.g. newton,rl[rsl-rl],visualizer[newton]' 'core' }
        else { $s.LabPackages = $values[$index] }
        if ((Get-LabMajor $s.IsaacLab) -ge 3) {
            $options = @('default', 'newton', 'ovphysx', 'both')
            if ($s.IsaacSim) { $options += 'isaacsim', 'all' }
            $s.LabPhysics = $options[(Read-BuilderChoice 'Which physics support?' $options)]
            $options = @('default', 'newton', 'rerun', 'viser', 'all')
            if ($s.IsaacSim) { $options += 'kit' }
            $s.LabVisualizer = $options[(Read-BuilderChoice 'Which visualization support?' $options)]
            Write-Host 'These choices add packages. Select physics and visualization at task launch.'
        } else { Write-Host 'Isaac Lab 2.x uses Isaac Sim physics and Kit visualization.' }
    }
    Write-Host "`n== Stage 8/9 - Extra layers ==" -ForegroundColor Cyan
    $s.Zenoh = Read-BuilderYesNo 'Add Zenoh middleware (rmw_zenoh_cpp)?'
    $s.Gazebo = Read-BuilderYesNo 'Add Gazebo simulation?'
    Write-Host "`n== Stage 9/9 - Container user and image name ==" -ForegroundColor Cyan
    $s.Username = Read-BuilderValue 'Username inside the image' $s.Username
    $s.UserUid = Read-BuilderValue 'Container UID' $s.UserUid
    $s.UserGid = Read-BuilderValue 'Container GID' $s.UserGid
    $s.Namespace = Read-BuilderValue 'Image namespace' $s.Namespace
    Resolve-StageVersions $s
    $preview = New-StagePlan $s
    $s.Image = Read-BuilderValue 'Final image name' $preview.FinalImage
}

try {
    if ($Help) {
        Write-Host @'
Usage: create_env.ps1 [-DryRun] | -NonInteractive [selection parameters] [-DryRun]
       create_env.bat forwards the same parameters from Command Prompt.

Interactive mode walks through all nine stages. -DryRun prints the plan without
requiring Docker. -NonInteractive builds immediately using the given selection.
Selection parameters require -NonInteractive; omitted parameters use defaults.

  -OS 22.04|24.04|26.04     Ubuntu release (24.04)
  -Ros <distro>             ROS distribution (rolling)
  -Usage skip|manipulation|navigation|both (skip)
  -Cuda <version|latest>    Enable CUDA + cuDNN development base
  -Mujoco <version|latest>  Enable MuJoCo
  -Gym <version>            Gymnasium version (1.3.0)
  -IsaacSim <version|latest>  Enable Isaac Sim
  -IsaacLab <ref|latest>    Enable Isaac Lab, including Kit-less installations
  -LabMethod auto|python-env|legacy (auto)
  -LabPackages <selectors>  default, core, or custom selectors (default)
  -LabPhysics default|newton|ovphysx|both|isaacsim|all
  -LabVisualizer default|newton|rerun|viser|kit|all
  -Zenoh -Gazebo            Enable optional middleware/simulation layers
  -Username <name>          Container user (admin)
  -UserUid <id> -UserGid <id>  Linux container IDs (1000:1000)
  -Namespace <repository>   Image namespace (docker_envs)
  -Image <name:tag>          Override final image name

Requires Docker Desktop running Linux containers and a Docker-driver Buildx
builder. Runs in Windows PowerShell 5.1 or PowerShell 7. No host Bash required.
Replay commands are PowerShell commands to run from the repository root.
'@
        exit 0
    }
    $selection = New-StageSelection
    $selectionKeys = @($selection.Keys)
    if (!$NonInteractive -and @($PSBoundParameters.Keys | Where-Object { $_ -in $selectionKeys }).Count) {
        throw 'Selection parameters require -NonInteractive. Omit them to use the interactive menus.'
    }
    foreach ($key in $selectionKeys) {
        $selection[$key] = Get-Variable -Name $key -ValueOnly
        if ($selection[$key] -is [Management.Automation.SwitchParameter]) { $selection[$key] = [bool]$selection[$key] }
    }
    if ($NonInteractive) { Resolve-StageVersions $selection }
    else { Read-BuilderSelection $selection }
    $plan = New-StagePlan $selection
    Write-Host "`n== Summary ==" -ForegroundColor Cyan
    foreach ($key in $selectionKeys | Sort-Object) { Write-Host ('  {0,-16} {1}' -f ($key + ':'), $selection[$key]) }
    if ($selection.IsaacLab) { Write-Host "  Effective Lab selectors: $(Get-LabPackages $selection)" }
    Write-Host "`nBuild plan ($($plan.Layers.Count) layers)"
    foreach ($layer in $plan.Layers) { Write-Host "  $($layer.Dockerfile) -> $($layer.Image)`n    from $($layer.Base)" }
    Write-Host "`nFinal image: $($plan.FinalImage)`nReplay command (PowerShell, from repository root):`n  $($plan.Replay)"
    if ($DryRun) { Write-Host "`nDry run: nothing was built."; exit 0 }
    if (!$NonInteractive -and !(Read-BuilderYesNo 'Start the build?' $true)) { Write-Host 'Aborted; nothing was built.'; exit 0 }
    Invoke-StagePlan $plan
    exit 0
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
