#requires -Version 5.1
<#
.SYNOPSIS
Install the HiMate knowledge toolkit and optionally prepare a knowledge root for OCR.
.EXAMPLE
.\deploy.ps1 -SkillsRoot SKILLS_ROOT -WorkflowsRoot WORKFLOWS_ROOT -Python PATH_TO_PYTHON -NonInteractive
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot,
    [string]$CacSkillsRoot,
    [string]$WorkflowsRoot,
    [string]$Python = 'python',
    [string]$SourceRoot,
    [string]$CapabilitiesRoot,
    [string]$KnowledgeRoot,
    [switch]$NonInteractive,
    [switch]$DownloadModels
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$deployArguments = @((Join-Path $PSScriptRoot 'tools\deploy\deploy.py'),
                     '--python', $Python)
if (-not [string]::IsNullOrWhiteSpace($SourceRoot)) {
    $deployArguments += @('--source-root', $SourceRoot)
}
if (-not [string]::IsNullOrWhiteSpace($CapabilitiesRoot)) {
    $deployArguments += @('--capabilities-root', $CapabilitiesRoot)
}
if (-not [string]::IsNullOrWhiteSpace($KnowledgeRoot)) {
    $deployArguments += @('--knowledge-root', $KnowledgeRoot)
}
if (-not [string]::IsNullOrWhiteSpace($SkillsRoot)) {
    $deployArguments += @('--skills-root', $SkillsRoot)
}
if (-not [string]::IsNullOrWhiteSpace($CacSkillsRoot)) {
    $deployArguments += @('--cac-skills-root', $CacSkillsRoot)
}
if (-not [string]::IsNullOrWhiteSpace($WorkflowsRoot)) {
    $deployArguments += @('--workflows-root', $WorkflowsRoot)
}
if ($NonInteractive) { $deployArguments += '--non-interactive' }
if ($DownloadModels) { $deployArguments += '--download-models' }

& $Python @deployArguments
exit $LASTEXITCODE
