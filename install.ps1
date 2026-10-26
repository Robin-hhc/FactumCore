<#
Prepare a private knowledge runtime using an existing Python 3.11/3.12.
Example: .\install.ps1 -IndexUrl https://packages.example.internal/simple
#>
[CmdletBinding()]
param(
    [string]$Python,
    [string]$Destination,
    [string]$Wheelhouse,
    [string]$IndexUrl
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
$helper = Join-Path $PSScriptRoot 'skills/common/knowledge/hs-workspace-explore/scripts/install_environment.py'
$helperArgs = @('-X', 'utf8', $helper, '--source-root', $PSScriptRoot)
if ($Destination) { $helperArgs += @('--destination', $Destination) }
if ($Wheelhouse) { $helperArgs += @('--wheelhouse', $Wheelhouse) }
if ($IndexUrl) { $helperArgs += @('--index-url', $IndexUrl) }
& $Python @pythonArgs @helperArgs
exit $LASTEXITCODE
