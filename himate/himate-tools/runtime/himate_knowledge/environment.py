"""Check or repair the selected interpreter and its knowledge launcher."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from . import command_install, doctor
from .protocol import NodeError


INSTALL_TIMEOUT_SECONDS = 30 * 60
DEPENDENCY_CHECK_MESSAGE = "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"
CLI_CHECK_MESSAGE = "知识命令无法启动，请检查命令目录、工具包和 Python 路径后重试。"
NPM_PACKAGE = "@himate/knowledge-cli"
NPM_REPAIR_MESSAGE = "请重新安装 @himate/knowledge-cli，并检查 npm 命令目录是否在 PATH 中。"


def _npm_launcher_candidates(modules):
    if os.name == "nt":
        return [modules.parent / "knowledge.cmd", modules / ".bin/knowledge.cmd"]
    local = modules / ".bin/knowledge"
    if modules.parent.name == "lib":
        return [modules.parent.parent / "bin/knowledge", local]
    return [local]


def _is_npm_launcher(shim, dispatcher):
    try:
        if os.name != "nt":
            return shim.is_symlink() and shim.resolve(strict=True) == dispatcher and os.access(shim, os.X_OK)
        if shim.is_symlink() or not shim.is_file() or shim.stat().st_size > 32 * 1024:
            return False
        destination = os.path.relpath(dispatcher, shim.parent).replace("\\", "/").casefold()
        content = shim.read_text(encoding="utf-8").replace("\\", "/").casefold()
        return content.startswith("@echo off\n") and f'"%dp0%/{destination}" %*' in content
    except (OSError, ValueError):
        return False


def _npm_owned_dispatcher(metadata, version):
    try:
        package = Path(metadata["packageRoot"])
        if (not package.is_absolute() or package.name != "knowledge-cli" or package.parent.name != "@himate"
                or package.parent.parent.name != "node_modules" or metadata.get("version") != version):
            return None
        dispatcher = package / "bin/knowledge.js"
        package_json = json.loads((package / "package.json").read_text(encoding="utf-8"))
        if (package_json["name"] != NPM_PACKAGE or package_json["version"] != version
                or package_json["bin"]["knowledge"] != "bin/knowledge.js"
                or hashlib.sha256(dispatcher.read_bytes()).hexdigest() != metadata["launcherSha256"]):
            return None
        return dispatcher.resolve(strict=True)
    except (KeyError, OSError, TypeError, ValueError):
        return None


def _resolved_path(path):
    return os.path.normcase(os.path.normpath(path)) if os.name == "nt" else str(Path(path).resolve())


def _inspect_npm_command(tool_root, version):
    marker = tool_root / ".install.json"
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        metadata = {}
    if not isinstance(metadata, dict) or metadata.get("package") != NPM_PACKAGE:
        metadata = {}
    dispatcher = _npm_owned_dispatcher(metadata, version)
    candidates = _npm_launcher_candidates(Path(metadata["packageRoot"]).parent.parent) if dispatcher else []
    installed = [candidate for candidate in candidates if _is_npm_launcher(candidate, dispatcher)]
    found = command_install._find_on_path()
    effective = next((item for item in installed if found and _resolved_path(found) == _resolved_path(item)), None)
    launcher = effective or next(iter(installed or candidates), None)
    return {
        "kind": "npm", "path": str(launcher) if launcher else None,
        "bin_dir": str(launcher.parent) if launcher else None, "dispatcher": str(dispatcher) if dispatcher else None,
        "installed": bool(installed) and (not found or effective is not None),
        "path_registered": effective is not None, "on_path": effective is not None,
        "shadowed_by": found if found and effective is None else None,
    }


def _verify_command(tool_root, command):
    if command.get("kind") == "npm":
        # The npm shim was inspected without executing a PATH candidate. Verify
        # the matching tool entry with the selected interpreter.
        executable = [sys.executable, "-B", str(tool_root / "knowledge.py")]
    else:
        executable = [sys.executable, "-B", command["dispatcher"]] if os.name == "nt" else [command["path"]]
    subprocess.run([*executable, "--help"], cwd=command["bin_dir"], check=True, timeout=10,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _report(tool_root, version, bin_dir):
    dependencies, gaps = doctor.inspect_dependencies(tool_root / "runtime/requirements.lock.txt")
    dependencies_missing = bool(gaps)
    command = None
    try:
        if bin_dir is None:
            command = _inspect_npm_command(tool_root, version)
        if command is None:
            command = command_install.inspect_command(tool_root, bin_dir)
    except NodeError as error:
        gaps.append({"code": error.code, "message": "无法检查知识命令，请检查命令目录。"})
    except OSError:
        gaps.append({"code": "CLI_CHECK_FAILED", "message": "无法读取知识命令，请检查命令目录的权限。"})
    status = "needs_install" if dependencies_missing else "needs_cli"
    if not dependencies_missing and command and command["installed"]:
        try:
            _verify_command(tool_root, command)
        except (OSError, subprocess.SubprocessError):
            gaps.append({"code": "CLI_VERIFICATION_FAILED", "message": CLI_CHECK_MESSAGE})
        else:
            status = "ready"
    if command and bin_dir is None and command.get("shadowed_by"):
        gaps.append({"code": "COMMAND_PATH_CONFLICT", "message": "PATH 中有另一个 knowledge 命令，请检查顺序。"})
    npm = command and command.get("kind") == "npm"
    if npm and not command["installed"]:
        gaps.append({"code": "NPM_LAUNCHER_UNAVAILABLE", "message": NPM_REPAIR_MESSAGE})
    if status == "ready" and (os.name != "nt" or npm) and bin_dir is None and not command["on_path"]:
        gaps.append({"code": "COMMAND_NOT_ON_PATH", "message": "知识命令已安装，请将命令目录加入终端 PATH。"})
    return {"status": status, "python": sys.executable,
            "python_version": platform.python_version(), "toolkit_version": version,
            "tool_root": str(tool_root), "dependencies": dependencies, "diagnostics": gaps, "command": command}


def _emit(event, output, *, progress=False):
    if output == "jsonl" or (output == "json" and not progress):
        print(json.dumps(event), flush=True)
    elif output == "text":
        if progress or event.get("message"):
            print(event["message"], file=sys.stderr, flush=True)
        else:
            stream = sys.stderr if event["status"] in {"unavailable", "failed"} else sys.stdout
            print("{status} · Python {python_version}".format(**event) if "python_version" in event else event["status"],
                  file=stream, flush=True)
            for item in event["diagnostics"]:
                print(item["message"], file=stream, flush=True)


def _failure(phase, code, message, *, legacy=False):
    diagnostic = {"code": code, "message": message}
    result = {"phase": phase, "diagnostics": [diagnostic], **diagnostic}
    if not legacy:
        result["status"] = "failed"
    return result, 1


def _install(tool_root, version, bin_dir, result, progress, *, legacy):
    def fail(phase, code, message):
        return _failure(phase, code, message, legacy=legacy)

    if result["status"] == "needs_install":
        progress("installing", "正在为当前 Python 安装锁定依赖。")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                            str(tool_root / "runtime/requirements.lock.txt")],
                           cwd=tool_root, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=INSTALL_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return fail("installing", "DEPENDENCY_INSTALL_FAILED",
                        "依赖安装失败，请检查 pip、软件源和当前 Python 的写入权限后重试。")
        result = _try_report(tool_root, version, bin_dir)
        if result is None:
            return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
        if result["status"] == "needs_install":
            return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")

    if result["status"] == "needs_cli":
        command = result["command"] or {}
        if command.get("kind") == "npm":
            code = "COMMAND_PATH_CONFLICT" if command.get("shadowed_by") else "NPM_LAUNCHER_UNAVAILABLE"
            return fail("verifying", code, NPM_REPAIR_MESSAGE)
        progress("registering", "正在注册知识命令。")
        try:
            command_install.deploy_command(tool_root, bin_dir, add_path=os.name == "nt" and bin_dir is None)
        except NodeError as error:
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

    progress("verifying", "正在复查 Python 依赖和知识命令。")
    result = _try_report(tool_root, version, bin_dir)
    if result is None:
        return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
    if result["status"] == "needs_install":
        return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")
    if result["status"] != "ready":
        return fail("verifying", "CLI_VERIFICATION_FAILED", CLI_CHECK_MESSAGE)
    return result, 0


def _try_report(tool_root, version, bin_dir):
    try:
        return _report(tool_root, version, bin_dir)
    except (OSError, ValueError, ImportError):
        return None


def run_environment(tool_root, manifest, action, *, bin_dir=None, output="text", legacy=False):
    def progress(phase, message):
        _emit({"phase": phase, "message": message}, output, progress=True)

    installing = action == "install"
    if installing:
        progress("checking", "正在检查工具包和 Python 依赖。")
    version = manifest["version"]
    result = _try_report(tool_root, version, bin_dir)
    code = 0
    if result is None:
        if installing:
            result, code = _failure("checking", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE, legacy=legacy)
        else:
            result = {"status": "unavailable", "diagnostics": [{"code": "DEPENDENCY_CHECK_FAILED",
                                                                  "message": DEPENDENCY_CHECK_MESSAGE}]}
            code = 1
    elif installing:
        result, code = _install(tool_root, version, bin_dir, result, progress, legacy=legacy)
    _emit(result, output)
    return code
