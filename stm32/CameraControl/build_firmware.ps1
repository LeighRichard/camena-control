[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Preset = "Debug",

    [int]$BuildTimeoutSeconds = 45,
    [int]$LinkTimeoutSeconds = 45,

    [switch]$SkipConfigure,
    [switch]$SkipPrimaryBuild,
    [switch]$SkipArtifactGeneration
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "scripts/FirmwareTools.ps1")

Invoke-FirmwareBuild `
    -Preset $Preset `
    -BuildTimeoutSeconds $BuildTimeoutSeconds `
    -LinkTimeoutSeconds $LinkTimeoutSeconds `
    -SkipConfigure:$SkipConfigure `
    -SkipPrimaryBuild:$SkipPrimaryBuild `
    -SkipArtifactGeneration:$SkipArtifactGeneration
