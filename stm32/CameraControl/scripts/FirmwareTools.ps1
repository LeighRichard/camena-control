Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-BuildContext {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string]$Preset
    )

    $buildDir = Join-Path $ProjectRoot "build/$Preset"
    $logsDir = Join-Path $ProjectRoot "logs"
    if (-not (Test-Path $logsDir)) {
        $null = New-Item -ItemType Directory -Path $logsDir
    }

    return [pscustomobject]@{
        ProjectRoot = $ProjectRoot
        Preset = $Preset
        BuildDir = $buildDir
        BuildNinja = Join-Path $buildDir "build.ninja"
        Cache = Join-Path $buildDir "CMakeCache.txt"
        Elf = Join-Path $buildDir "CameraControl.elf"
        Hex = Join-Path $buildDir "CameraControl.hex"
        Bin = Join-Path $buildDir "CameraControl.bin"
        Map = Join-Path $buildDir "CameraControl.map"
        LogsDir = $logsDir
    }
}

function Get-CacheValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CachePath,

        [Parameter(Mandatory = $true)]
        [string]$VariableName
    )

    if (-not (Test-Path $CachePath)) {
        return $null
    }

    $pattern = "^" + [regex]::Escape($VariableName) + ":[^=]+=(.+)$"
    $match = Select-String -Path $CachePath -Pattern $pattern | Select-Object -First 1
    if ($null -eq $match) {
        return $null
    }

    return $match.Matches[0].Groups[1].Value.Trim()
}

function Remove-FileIfExists {
    param([string]$Path)

    if (Test-Path $Path) {
        Remove-Item -Path $Path -Force
    }
}

function Read-LogText {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return ""
    }

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            return Get-Content -Path $Path -Raw -ErrorAction Stop
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }

    return "<log unavailable>"
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$StdoutPath,

        [Parameter(Mandatory = $true)]
        [string]$StderrPath,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    Remove-FileIfExists -Path $StdoutPath
    Remove-FileIfExists -Path $StderrPath

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -PassThru

    $timedOut = $false
    try {
        Wait-Process -Id $process.Id -Timeout $TimeoutSeconds -ErrorAction Stop | Out-Null
    } catch {
        $timedOut = $true
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Milliseconds 300

    $exitCode = if ($timedOut) {
        124
    } else {
        try {
            $process.Refresh()
            if ($process.HasExited) {
                $process.ExitCode
            } else {
                0
            }
        } catch {
            0
        }
    }

    return [pscustomobject]@{
        TimedOut = $timedOut
        ExitCode = $exitCode
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
        Stdout = Read-LogText -Path $StdoutPath
        Stderr = Read-LogText -Path $StderrPath
    }
}

function Ensure-Configured {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context
    )

    if (Test-Path $Context.BuildNinja) {
        return
    }

    Write-Host "[configure] Running cmake --preset $($Context.Preset)"
    & cmake --preset $Context.Preset
    if ($LASTEXITCODE -ne 0) {
        throw "cmake configure failed for preset '$($Context.Preset)'"
    }
}

function Get-NinjaPath {
    param([pscustomobject]$Context)

    $ninjaPath = Get-CacheValue -CachePath $Context.Cache -VariableName "CMAKE_MAKE_PROGRAM"
    if ([string]::IsNullOrWhiteSpace($ninjaPath)) {
        return "ninja"
    }

    return $ninjaPath
}

function Get-LatestObject {
    param([pscustomobject]$Context)

    $objects = Get-ChildItem -Path $Context.BuildDir -Recurse -Filter "*.obj" -ErrorAction SilentlyContinue
    if ($null -eq $objects -or $objects.Count -eq 0) {
        return $null
    }

    return $objects | Sort-Object LastWriteTime | Select-Object -Last 1
}

function Get-LinkCommand {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context,

        [Parameter(Mandatory = $true)]
        [string]$NinjaPath
    )

    $commands = & $NinjaPath "-C" $Context.BuildDir "-t" "commands" "CameraControl.elf"
    if ($LASTEXITCODE -ne 0) {
        throw "failed to query ninja link commands"
    }

    $linkCommand = $commands | Where-Object { $_ -match "CameraControl\.elf" } | Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($linkCommand)) {
        throw "unable to locate link command for CameraControl.elf"
    }

    return $linkCommand
}

function Split-LinkCommand {
    param([string]$LinkCommand)

    $match = [regex]::Match($LinkCommand, '^\s*"?(?<exe>(?:[A-Za-z]:)?[^"]*cmd(?:\.exe)?)"?\s+/C\s+"(?<body>.*)"\s*$')
    if ($match.Success) {
        return [pscustomobject]@{
            FilePath = $match.Groups["exe"].Value
            ArgumentList = @("/C", $match.Groups["body"].Value)
        }
    }

    return [pscustomobject]@{
        FilePath = "cmd.exe"
        ArgumentList = @("/C", $LinkCommand)
    }
}

function Get-ToolchainBinDir {
    param([string]$LinkCommand)

    $match = [regex]::Match($LinkCommand, '(?<compiler>[A-Za-z]:[^"]*arm-none-eabi-gcc\.exe)')
    if (-not $match.Success) {
        throw "unable to derive GNU toolchain path from link command"
    }

    return Split-Path -Parent $match.Groups["compiler"].Value
}

function Invoke-PrimaryBuild {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    Write-Host "[build] Running primary build wrapper for preset $($Context.Preset)"

    $stdoutPath = Join-Path $Context.LogsDir "build-$($Context.Preset.ToLowerInvariant())-stdout.log"
    $stderrPath = Join-Path $Context.LogsDir "build-$($Context.Preset.ToLowerInvariant())-stderr.log"
    $result = Invoke-LoggedProcess `
        -FilePath "cmake" `
        -ArgumentList @("--build", "--preset", $Context.Preset) `
        -WorkingDirectory $Context.ProjectRoot `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $TimeoutSeconds

    if ($result.TimedOut) {
        Write-Warning "[build] Primary build timed out. Continuing with manual validation and link fallback."
        return
    }

    if ($result.ExitCode -ne 0) {
        throw "[build] Primary build failed.`nSTDOUT:`n$($result.Stdout)`nSTDERR:`n$($result.Stderr)"
    }
}

function Invoke-ManualLink {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context,

        [Parameter(Mandatory = $true)]
        [string]$NinjaPath,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $linkCommand = Get-LinkCommand -Context $Context -NinjaPath $NinjaPath
    $split = Split-LinkCommand -LinkCommand $linkCommand

    $previousElfTimestamp = [DateTime]::MinValue
    if (Test-Path $Context.Elf) {
        $previousElfTimestamp = (Get-Item -Path $Context.Elf).LastWriteTimeUtc
    }

    Write-Host "[link] Running manual link command"

    $stdoutPath = Join-Path $Context.LogsDir "link-$($Context.Preset.ToLowerInvariant())-stdout.log"
    $stderrPath = Join-Path $Context.LogsDir "link-$($Context.Preset.ToLowerInvariant())-stderr.log"
    $result = Invoke-LoggedProcess `
        -FilePath $split.FilePath `
        -ArgumentList $split.ArgumentList `
        -WorkingDirectory $Context.BuildDir `
        -StdoutPath $stdoutPath `
        -StderrPath $stderrPath `
        -TimeoutSeconds $TimeoutSeconds

    $elfUpdated = $false
    if (Test-Path $Context.Elf) {
        $elfUpdated = (Get-Item -Path $Context.Elf).LastWriteTimeUtc -gt $previousElfTimestamp
    }

    if ($result.TimedOut -or (($result.ExitCode -ne 0) -and -not $elfUpdated)) {
        throw "[link] Manual link failed.`nSTDOUT:`n$($result.Stdout)`nSTDERR:`n$($result.Stderr)"
    }

    if (-not (Test-Path $Context.Elf)) {
        throw "[link] CameraControl.elf was not produced"
    }

    if ($result.ExitCode -ne 0 -and $elfUpdated) {
        Write-Warning "[link] Link command returned exit code $($result.ExitCode), but ELF was updated successfully. Continuing."
    }

    return Get-ToolchainBinDir -LinkCommand $linkCommand
}

function Invoke-FirmwareArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context,

        [Parameter(Mandatory = $true)]
        [string]$ToolchainBinDir
    )

    $objcopyPath = Join-Path $ToolchainBinDir "arm-none-eabi-objcopy.exe"
    $sizePath = Join-Path $ToolchainBinDir "arm-none-eabi-size.exe"

    if (-not (Test-Path $objcopyPath)) {
        throw "objcopy not found: $objcopyPath"
    }
    if (-not (Test-Path $sizePath)) {
        throw "size not found: $sizePath"
    }

    Write-Host "[artifacts] Generating HEX/BIN"
    & $objcopyPath "-O" "ihex" $Context.Elf $Context.Hex
    if ($LASTEXITCODE -ne 0) {
        throw "failed to generate HEX artifact"
    }

    & $objcopyPath "-O" "binary" $Context.Elf $Context.Bin
    if ($LASTEXITCODE -ne 0) {
        throw "failed to generate BIN artifact"
    }

    & $sizePath $Context.Elf
    if ($LASTEXITCODE -ne 0) {
        throw "failed to print ELF size"
    }
}

function Show-FirmwareSummary {
    param([pscustomobject]$Context)

    Write-Host "[summary] Firmware artifacts"
    Get-ChildItem -Path $Context.BuildDir -Filter "CameraControl.*" |
        Select-Object Name, Length, LastWriteTime |
        Format-Table -AutoSize
}

function Invoke-FirmwareBuild {
    param(
        [ValidateSet("Debug", "Release")]
        [string]$Preset = "Debug",

        [int]$BuildTimeoutSeconds = 45,
        [int]$LinkTimeoutSeconds = 45,

        [switch]$SkipConfigure,
        [switch]$SkipPrimaryBuild,
        [switch]$SkipArtifactGeneration
    )

    $projectRoot = Get-ProjectRoot
    $context = Get-BuildContext -ProjectRoot $projectRoot -Preset $Preset

    if (-not $SkipConfigure) {
        Ensure-Configured -Context $context
    }

    if (-not $SkipPrimaryBuild) {
        Invoke-PrimaryBuild -Context $context -TimeoutSeconds $BuildTimeoutSeconds
    }

    $ninjaPath = Get-NinjaPath -Context $context
    $latestObject = Get-LatestObject -Context $context
    if ($null -eq $latestObject) {
        throw "no object files found under $($context.BuildDir)"
    }

    $linkNeeded = -not (Test-Path $context.Elf)
    if (-not $linkNeeded) {
        $elfItem = Get-Item -Path $context.Elf
        $linkNeeded = $latestObject.LastWriteTime -gt $elfItem.LastWriteTime
    }

    $toolchainBinDir = $null
    if ($linkNeeded) {
        $toolchainBinDir = Invoke-ManualLink -Context $context -NinjaPath $ninjaPath -TimeoutSeconds $LinkTimeoutSeconds
    } else {
        $linkCommand = Get-LinkCommand -Context $context -NinjaPath $ninjaPath
        $toolchainBinDir = Get-ToolchainBinDir -LinkCommand $linkCommand
        Write-Host "[link] Existing ELF is newer than object files. Reusing current link output."
    }

    if (-not $SkipArtifactGeneration) {
        Invoke-FirmwareArtifacts -Context $context -ToolchainBinDir $toolchainBinDir
    }

    Show-FirmwareSummary -Context $context
}

function Get-ProgrammerCliPath {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Context,

        [string]$ExplicitPath
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path $ExplicitPath)) {
            throw "STM32_Programmer_CLI not found: $ExplicitPath"
        }
        return (Resolve-Path $ExplicitPath).Path
    }

    $cliPath = Get-CacheValue -CachePath $Context.Cache -VariableName "STM32_PROGRAMMER_CLI"
    if (-not [string]::IsNullOrWhiteSpace($cliPath) -and (Test-Path $cliPath)) {
        return $cliPath
    }

    $fromPath = Get-Command "STM32_Programmer_CLI.exe" -ErrorAction SilentlyContinue
    if ($null -ne $fromPath) {
        return $fromPath.Source
    }

    throw "STM32_Programmer_CLI was not found. Install STM32CubeProgrammer or pass -ProgrammerCliPath."
}

function Invoke-FirmwareFlash {
    param(
        [ValidateSet("Debug", "Release")]
        [string]$Preset = "Debug",

        [int]$BuildTimeoutSeconds = 45,
        [int]$LinkTimeoutSeconds = 45,

        [switch]$SkipBuild,
        [string]$ProgrammerCliPath,
        [string]$Address = "0x08000000",
        [string]$Port = "SWD",
        [string]$Mode = "UR",
        [string]$Reset = "HWrst",
        [switch]$DryRun
    )

    $projectRoot = Get-ProjectRoot
    $context = Get-BuildContext -ProjectRoot $projectRoot -Preset $Preset

    if (-not $SkipBuild) {
        Invoke-FirmwareBuild -Preset $Preset -BuildTimeoutSeconds $BuildTimeoutSeconds -LinkTimeoutSeconds $LinkTimeoutSeconds
    }

    if (-not (Test-Path $context.Bin)) {
        throw "BIN artifact not found: $($context.Bin)"
    }

    $cliPath = Get-ProgrammerCliPath -Context $context -ExplicitPath $ProgrammerCliPath
    $arguments = @(
        "-c", "port=$Port", "mode=$Mode", "reset=$Reset",
        "-w", $context.Bin, $Address,
        "-v",
        "-rst"
    )

    Write-Host "[flash] CLI: $cliPath"
    Write-Host "[flash] Arguments: $($arguments -join ' ')"

    if ($DryRun) {
        Write-Host "[flash] Dry run requested. Flash command was not executed."
        return
    }

    & $cliPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "flash command failed with exit code $LASTEXITCODE"
    }
}
