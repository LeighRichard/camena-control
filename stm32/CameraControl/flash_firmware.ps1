[CmdletBinding()]
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

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "scripts/FirmwareTools.ps1")

Invoke-FirmwareFlash `
    -Preset $Preset `
    -BuildTimeoutSeconds $BuildTimeoutSeconds `
    -LinkTimeoutSeconds $LinkTimeoutSeconds `
    -SkipBuild:$SkipBuild `
    -ProgrammerCliPath $ProgrammerCliPath `
    -Address $Address `
    -Port $Port `
    -Mode $Mode `
    -Reset $Reset `
    -DryRun:$DryRun
