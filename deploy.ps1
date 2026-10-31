#requires -Version 5.1
<#
.SYNOPSIS
Install dependencies, remove old Skill/Workflow packages, then copy new packages.
.EXAMPLE
.\deploy.ps1 -SkillsRoot SKILLS_ROOT -WorkflowsRoot WORKFLOWS_ROOT -Python PATH_TO_PYTHON -NonInteractive
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot,
    [string]$WorkflowsRoot,
    [string]$Python = 'python',
    [string]$SourceRoot = $PSScriptRoot,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SkillsRoot)) {
    $SkillsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.openflow\config\skills'
    if (-not $NonInteractive) {
        $taskAnswer = Read-Host "Skill installation directory [$SkillsRoot]"
        if (-not [string]::IsNullOrWhiteSpace($taskAnswer)) { $SkillsRoot = $taskAnswer }
    }
}

if ([string]::IsNullOrWhiteSpace($WorkflowsRoot)) {
    $WorkflowsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.openflow\config\workflow-templates'
    if (-not $NonInteractive) {
        $taskAnswer = Read-Host "Workflow template installation directory [$WorkflowsRoot]"
        if (-not [string]::IsNullOrWhiteSpace($taskAnswer)) { $WorkflowsRoot = $taskAnswer }
    }
}

& $Python (Join-Path $PSScriptRoot 'tools\deploy\deploy.py') `
    --source-root $SourceRoot --skills-root $SkillsRoot --workflows-root $WorkflowsRoot --python $Python
exit $LASTEXITCODE
