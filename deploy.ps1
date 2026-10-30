#requires -Version 5.1
<#
.SYNOPSIS
Copy knowledge Skills and pip install dependencies into the selected Python.
.EXAMPLE
.\deploy.ps1 -SkillsRoot SKILLS_ROOT -Python PATH_TO_PYTHON -NonInteractive
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot,
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

& $Python (Join-Path $PSScriptRoot 'tools\deploy\deploy.py') `
    --source-root $SourceRoot --skills-root $SkillsRoot --python $Python
exit $LASTEXITCODE
