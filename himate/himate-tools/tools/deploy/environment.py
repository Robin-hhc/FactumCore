"""Check or install dependencies and the knowledge command on the execution host."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from deploy import install_dependencies


TOOL_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = TOOL_ROOT / "runtime/requirements.lock.txt"
INSTALL_TIMEOUT_SECONDS = 30 * 60
DEPENDENCY_CHECK_MESSAGE = "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"
CLI_CHECK_MESSAGE = "知识命令无法启动，请检查命令目录、工具包和 Python 路径后重试。"


def load_runtime():
    if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
        raise ValueError("Unsupported Python version")
    sys.path.insert(0, str(TOOL_ROOT))
    import knowledge

    manifest, verified = knowledge.verified_runtime(TOOL_ROOT)
    loader = knowledge._VerifiedRuntime(TOOL_ROOT, verified)
    sys.meta_path.insert(0, loader)
    try:
        from himate_knowledge import command_install, doctor, protocol
    finally:
        sys.meta_path.remove(loader)
    return manifest["version"], doctor.inspect_dependencies, command_install, protocol.NodeError


def report(runtime, bin_dir):
    version, inspect_dependencies, commands, command_error = runtime
    dependencies, gaps = inspect_dependencies(REQUIREMENTS)
    dependencies_missing = bool(gaps)
    command = None
    try:
        command = commands.inspect_command(TOOL_ROOT, bin_dir)
    except command_error as error:
        gaps = [*gaps, {"code": error.code, "message": "无法检查知识命令，请检查命令目录。"}]
    except OSError:
        gaps = [*gaps, {"code": "CLI_CHECK_FAILED", "message": "无法读取知识命令，请检查命令目录的权限。"}]
    status = "needs_install" if dependencies_missing else "needs_cli"
    if not dependencies_missing and command and command["installed"]:
        try:
            verify_command(command)
        except (OSError, subprocess.SubprocessError):
            gaps = [*gaps, {"code": "CLI_VERIFICATION_FAILED", "message": CLI_CHECK_MESSAGE}]
        else:
            status = "ready"
    if command and bin_dir is None and command.get("shadowed_by"):
        gaps = [*gaps, {"code": "COMMAND_PATH_CONFLICT", "message": "PATH 中有另一个 knowledge 命令，请检查顺序。"}]
    if status == "ready" and os.name != "nt" and bin_dir is None and not command["on_path"]:
        gaps = [*gaps, {"code": "COMMAND_NOT_ON_PATH", "message": "知识命令已安装，请将命令目录加入终端 PATH。"}]
    return {"status": status, "python": sys.executable,
            "python_version": platform.python_version(), "toolkit_version": version,
            "tool_root": str(TOOL_ROOT), "dependencies": dependencies, "diagnostics": gaps,
            "command": command}


def emit(**event):
    print(json.dumps(event), flush=True)


def fail(phase, code, message):
    diagnostic = {"code": code, "message": message}
    emit(phase=phase, diagnostics=[diagnostic], **diagnostic)
    return 1


def verify_command(command):
    executable = [sys.executable, "-B", command["dispatcher"]] if os.name == "nt" else [command["path"]]
    subprocess.run([*executable, "--help"], cwd=command["bin_dir"], check=True, timeout=10,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install(runtime, bin_dir, result):
    _, _, commands, command_error = runtime
    if result["status"] == "needs_install":
        emit(phase="installing", message="正在为当前 Python 安装锁定依赖。")
        try:
            install_dependencies(sys.executable, REQUIREMENTS, cwd=TOOL_ROOT,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 timeout=INSTALL_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return fail("installing", "DEPENDENCY_INSTALL_FAILED",
                        "依赖安装失败，请检查 pip、软件源和当前 Python 的写入权限后重试。")
        try:
            result = report(runtime, bin_dir)
        except (OSError, ValueError, ImportError):
            return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
        if result["status"] == "needs_install":
            return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")
    if result["status"] == "needs_cli":
        emit(phase="registering", message="正在注册知识命令。")
        try:
            commands.deploy_command(TOOL_ROOT, bin_dir, add_path=os.name == "nt" and bin_dir is None)
        except command_error as error:
            message = {
                "COMMAND_EXISTS": "命令目录中有同名文件，请确认其来源后重试。",
                "COMMAND_PATH_CONFLICT": "PATH 中有另一个 knowledge 命令，请检查顺序后重试。",
                "PATH_REGISTRATION_FAILED": "无法更新执行账户的用户 PATH，请检查权限后重试。",
            }.get(error.code, "知识命令注册失败，请检查命令目录和 PATH 配置后重试。")
            return fail("registering", error.code, message)
        except PermissionError:
            return fail("registering", "CLI_PERMISSION_DENIED", "没有权限写入命令目录或用户 PATH，请调整权限后重试。")
        except OSError:
            return fail("registering", "CLI_REGISTRATION_FAILED", "无法写入知识命令，请检查命令目录后重试。")
    emit(phase="verifying", message="正在复查 Python 依赖和知识命令。")
    try:
        result = report(runtime, bin_dir)
    except (OSError, ValueError, ImportError):
        return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
    if result["status"] == "needs_install":
        return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")
    if result["status"] != "ready":
        return fail("verifying", "CLI_VERIFICATION_FAILED", CLI_CHECK_MESSAGE)
    emit(**result)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("--bin-dir", type=Path, help="Select a command directory and manage PATH separately")
    options = parser.parse_args(argv)
    if options.action == "install":
        emit(phase="checking", message="正在检查工具包和 Python 依赖。")
    try:
        runtime = load_runtime()
        result = report(runtime, options.bin_dir)
    except (OSError, ValueError, ImportError):
        if options.action == "install":
            return fail("checking", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
        emit(status="unavailable", diagnostics=[{"code": "DEPENDENCY_CHECK_FAILED", "message": DEPENDENCY_CHECK_MESSAGE}])
        return 1
    if options.action == "install":
        return install(runtime, options.bin_dir, result)
    emit(**result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
