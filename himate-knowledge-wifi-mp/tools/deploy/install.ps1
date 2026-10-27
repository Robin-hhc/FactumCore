<#
Prepare a private knowledge runtime using an existing Python 3.11/3.12.
Run from the project root: .\himate-knowledge-wifi-mp\tools\deploy\install.ps1
#>
[CmdletBinding()]
param(
    [string]$Python,
    [string]$Destination,
    [string]$Wheelhouse,
    [string]$IndexUrl,
    [string]$SkillsRoot,
    [string]$WorkflowsRoot,
    [string]$WorkspaceConfig,
    [string]$SourceRoot
)

$ErrorActionPreference = 'Stop'
$pythonArgs = @()
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = (Get-Command py).Source
        $pythonArgs = @('-3.11')
    } elseif (Get-Command python3.11 -ErrorAction SilentlyContinue) {
        $Python = (Get-Command python3.11).Source
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = (Get-Command python).Source
    } else {
        throw 'Python 3.11 was not found. Specify -Python with the existing interpreter path.'
    }
}
$helper = Join-Path $PSScriptRoot 'install_environment.py'
$helperArgs = @('-X', 'utf8', $helper)
if ($WorkspaceConfig) { $helperArgs += @('--workspace-config', $WorkspaceConfig) }
if ($SourceRoot) { $helperArgs += @('--source-root', $SourceRoot) }
if ($Destination) { $helperArgs += @('--destination', $Destination) }
if ($Wheelhouse) { $helperArgs += @('--wheelhouse', $Wheelhouse) }
if ($IndexUrl) { $helperArgs += @('--index-url', $IndexUrl) }
if ($SkillsRoot) { $helperArgs += @('--skills-root', $SkillsRoot) }
if ($WorkflowsRoot) { $helperArgs += @('--workflows-root', $WorkflowsRoot) }
& $Python @pythonArgs @helperArgs
exit $LASTEXITCODE
