#requires -Version 5.1
<#
.SYNOPSIS
Deploy the knowledge Skills, Workflow templates and project scaffold on Windows.
.DESCRIPTION
Prompts for the three deployment roots. Archives are built locally; the project
archive is copied to the selected project root and unpacked there by Windows.
Checks this Windows Python, not the server behind a mapped network drive.
.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
.EXAMPLE
.\deploy.ps1 -Plan -NonInteractive -Python PATH_TO_PYTHON
.EXAMPLE
.\deploy.ps1 -NonInteractive -SkillsRoot SKILLS_ROOT -WorkflowsRoot WORKFLOWS_ROOT -ProjectRoot Y:\thursday\work_code -Python PATH_TO_PYTHON
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot,
    [string]$WorkflowsRoot,
    [string]$ProjectRoot,
    [string]$Python,
    [string]$SourceRoot,
    [switch]$InstallDependencies,
    [switch]$Plan,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-DeploymentPath {
    param([Parameter(Mandatory = $true)][string]$Value)
    $taskValue = [Environment]::ExpandEnvironmentVariables($Value.Trim())
    if ($taskValue -eq '~') {
        $taskValue = [Environment]::GetFolderPath('UserProfile')
    }
    elseif ($taskValue.StartsWith('~\') -or $taskValue.StartsWith('~/')) {
        $taskValue = [IO.Path]::Combine(
            [Environment]::GetFolderPath('UserProfile'), $taskValue.Substring(2))
    }
    return [IO.Path]::GetFullPath($taskValue)
}

function Read-DeploymentPath {
    param([string]$Label, [string]$Value, [string]$Default, [bool]$Ask)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return Resolve-DeploymentPath $Value
    }
    $taskSelected = $Default
    if ($Ask) {
        $taskAnswer = Read-Host "$Label [$Default]"
        if (-not [string]::IsNullOrWhiteSpace($taskAnswer)) {
            $taskSelected = $taskAnswer
        }
    }
    return Resolve-DeploymentPath $taskSelected
}

function Test-DeploymentPython {
    param([string]$Command, [string[]]$Prefix = @())
    try {
        if (Test-Path -LiteralPath $Command -PathType Leaf) {
            $taskExecutable = Resolve-DeploymentPath $Command
        }
        else {
            $taskApplication = Get-Command $Command -CommandType Application -ErrorAction SilentlyContinue
            if (-not $taskApplication) { return $null }
            $taskExecutable = $taskApplication.Source
        }
        # Avoid opening the Microsoft Store alias while probing interpreters.
        if ($taskExecutable -match '\\Microsoft\\WindowsApps\\') { return $null }
        $taskProbeCode = "import json,sys; print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:3])}))"
        $taskProbeLines = @(& $taskExecutable @Prefix -I -c $taskProbeCode 2>$null)
        if ($LASTEXITCODE -ne 0) { return $null }
        $taskProbe = ($taskProbeLines -join "`n") | ConvertFrom-Json
        if ($taskProbe.version[0] -eq 3 -and
            $taskProbe.version[1] -ge 10 -and $taskProbe.version[1] -le 12) {
            return [string]$taskProbe.executable
        }
    }
    catch { return $null }
    return $null
}

function Find-DeploymentPython {
    param([string]$Requested, [bool]$Ask)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $taskFound = Test-DeploymentPython $Requested
        if ($taskFound) { return $taskFound }
        throw "-Python 必须指向可用的 Python 3.10–3.12 解释器：$Requested"
    }
    foreach ($taskVersion in @('-3.12', '-3.11', '-3.10')) {
        $taskFound = Test-DeploymentPython 'py' @($taskVersion)
        if ($taskFound) { return $taskFound }
    }
    foreach ($taskCommand in @('python3', 'python')) {
        $taskFound = Test-DeploymentPython $taskCommand
        if ($taskFound) { return $taskFound }
    }
    if ($Ask) {
        $taskAnswer = Read-Host '未找到 Python 3.10–3.12，请输入已安装的 python.exe 完整路径（留空结束）'
        if (-not [string]::IsNullOrWhiteSpace($taskAnswer)) {
            $taskFound = Test-DeploymentPython (Resolve-DeploymentPath $taskAnswer)
            if ($taskFound) { return $taskFound }
        }
    }
    throw '未找到本机 Python 3.10–3.12。请先安装，或用 -Python 指定现有解释器；脚本不会自动下载 Python。'
}

$taskExitCode = 3
$taskPreviousEncoding = [Console]::OutputEncoding
$taskPreviousInputEncoding = [Console]::InputEncoding
$taskPreviousPythonEncoding = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'Process')
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'deploy.ps1 仅用于 Windows 部署。'
    }
    if ($Plan -and $InstallDependencies) {
        throw '-Plan 为只读预检，不能与 -InstallDependencies 一起使用。'
    }
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
    [Console]::InputEncoding = New-Object Text.UTF8Encoding($false)
    $env:PYTHONIOENCODING = 'utf-8'
    $taskAsk = -not ($NonInteractive -or $Plan)
    $taskUserProfile = [Environment]::GetFolderPath('UserProfile')
    $taskSkills = Read-DeploymentPath 'Skill 部署根目录' $SkillsRoot (
        [IO.Path]::Combine($taskUserProfile, '.openflow', 'config', 'skills')) $taskAsk
    $taskWorkflows = Read-DeploymentPath 'Workflow 模板部署根目录' $WorkflowsRoot (
        [IO.Path]::Combine($taskUserProfile, '.openflow', 'config', 'workflow-templates')) $taskAsk
    $taskProject = Read-DeploymentPath '代码仓／知识项目根目录' $ProjectRoot 'Y:\thursday\work_code' $taskAsk
    $taskPython = Find-DeploymentPython $Python $taskAsk
    if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
        $SourceRoot = [IO.Path]::GetDirectoryName($PSCommandPath)
    }
    $taskSource = Resolve-DeploymentPath $SourceRoot
    $taskBackend = Join-Path $taskSource 'tools\deploy\deploy.py'
    if (-not (Test-Path -LiteralPath $taskBackend -PathType Leaf)) {
        throw "找不到部署程序：$taskBackend。请从完整分发仓运行 deploy.ps1。"
    }
    $taskArguments = @(
        $taskBackend, '--source-root', $taskSource,
        '--skills-root', $taskSkills, '--workflows-root', $taskWorkflows,
        '--project-root', $taskProject
    )
    if ($taskAsk -and -not $InstallDependencies) {
        $taskPlanLines = @(& $taskPython @taskArguments --plan)
        $taskPlanCode = $LASTEXITCODE
        $taskPreview = ($taskPlanLines -join "`n") | ConvertFrom-Json
        if ($taskPreview.status -eq 'missing_dependencies') {
            Write-Host '当前 Windows 解释器有缺失或版本不符的运行依赖：'
            $taskPreview.missing | Format-Table name, required, installed | Out-Host
            $taskInstall = Read-Host '是否将配套运行依赖安装到这个 Python？[y/N]'
            if ($taskInstall -match '^(?i:y|yes)$') {
                $InstallDependencies = $true
            }
            else {
                Write-Output ($taskPlanLines -join "`n")
                $taskExitCode = 2
            }
        }
        elseif ($taskPlanCode -ne 0) {
            Write-Output ($taskPlanLines -join "`n")
            $taskExitCode = $taskPlanCode
        }
        if (($taskPlanCode -ne 0 -and -not $InstallDependencies)) {
            exit $taskExitCode
        }
    }
    if ($Plan) { $taskArguments += '--plan' }
    if ($InstallDependencies) { $taskArguments += '--install-dependencies' }
    & $taskPython @taskArguments
    $taskExitCode = $LASTEXITCODE
    if ($taskExitCode -eq 0 -and $taskAsk -and -not $Plan) {
        Write-Host '部署完成。请重启 OpenFlow，检查 Skill／Workflow 列表并新建任务验证。'
        Write-Host '本次只检查当前 Windows 的 Python；映射盘服务器的执行环境仍须另外核对。'
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    $taskExitCode = 3
}
finally {
    [Console]::OutputEncoding = $taskPreviousEncoding
    [Console]::InputEncoding = $taskPreviousInputEncoding
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $taskPreviousPythonEncoding, 'Process')
}
exit $taskExitCode
