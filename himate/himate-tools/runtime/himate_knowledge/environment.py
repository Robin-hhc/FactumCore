"""Check or install execution dependencies and the knowledge launcher."""

from ast import literal_eval
from contextlib import contextmanager
import errno
import hashlib
from importlib.util import find_spec
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from . import command_install, doctor
from .execution import PIP_LOCATION_OPTIONS, child_environment, managed_home
from .protocol import NodeError


INSTALL_TIMEOUT_SECONDS = 30 * 60
APT_COMMAND_TIMEOUT_SECONDS = 10 * 60
DEPENDENCY_CHECK_MESSAGE = "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"
CLI_CHECK_MESSAGE = "知识命令无法启动，请检查命令目录、工具包和 Python 路径后重试。"
NPM_PACKAGE = "@himate/knowledge-cli"
NPM_REPAIR_MESSAGE = "请重新安装 @himate/knowledge-cli，并检查 npm 命令目录是否在 PATH 中。"
PIP_MISSING_MESSAGE = "当前 Python 缺少 pip，请选择已安装 pip 的 Python 3.10–3.12，然后重试 knowledge setup。"
PIP_FAILURE_MESSAGE = "依赖安装失败，请查看本地安装日志后重试。"
LOG_FAILURE_MESSAGE = "无法写入本地安装日志，请检查用户目录的权限和磁盘空间。"
PIP_LOCATION_MESSAGE = "pip 安装位置被配置覆盖，请移除 pip 配置中的 target、prefix、root 或 python 设置后重试。"
APT_GET = "/usr/bin/apt-get"
SUDO = "/usr/bin/sudo"
LIBREOFFICE_PACKAGE = "libreoffice-writer-nogui"
LIBREOFFICE_INSTALL_HINT = "请让执行端管理员安装 libreoffice-writer-nogui，并确认该账户可以运行 soffice --version。"
PYTHON_MODULE_FLAGS = ("-E", "-X", "utf8", "-m")
SECRET_URL = re.compile(r"\b(?:https?|socks5h?)://[^\s\"'<>]+", re.IGNORECASE)


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
        package_json = json.loads((package / "package.json").read_text(encoding="utf-8"))
        reference = package_json["bin"]["knowledge"]
        if (package_json["name"] != NPM_PACKAGE or package_json["version"] != version
                or reference not in ("distribution/npm/knowledge.js", "bin/knowledge.js")):
            return None
        dispatcher = package / reference
        if hashlib.sha256(dispatcher.read_bytes()).hexdigest() != metadata["launcherSha256"]:
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
        executable = [sys.executable, "-E", "-B", str(tool_root / "knowledge.py")]
    else:
        executable = [sys.executable, "-E", "-B", command["dispatcher"]] if os.name == "nt" else [command["path"]]
    subprocess.run([*executable, "--help"], cwd=command["bin_dir"], check=True, timeout=10,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env=child_environment())


def _report(tool_root, version, bin_dir, *, dependencies_only=False):
    dependencies, gaps = doctor.inspect_runtime_dependencies(tool_root / "runtime/requirements.lock.txt")
    if any(gap["code"] == "DEPENDENCY_UNAVAILABLE" for gap in gaps) and find_spec("pip") is None:
        gaps.insert(0, {"code": "DEPENDENCY_PIP_MISSING", "message": PIP_MISSING_MESSAGE})
    needs_install = bool(gaps)
    result = {"status": "needs_install" if needs_install else "ready", "python": sys.executable,
              "python_version": platform.python_version(), "toolkit_version": version,
              "tool_root": str(tool_root), "dependencies": dependencies, "diagnostics": gaps, "command": None}
    if dependencies_only:
        return result
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
    status = "needs_install" if needs_install else "needs_cli"
    if not needs_install and command and command["installed"]:
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
    result.update(status=status, command=command)
    return result


def _emit(event, output, *, progress=False):
    if output == "jsonl" or (output == "json" and not progress):
        print(json.dumps(event), flush=True)
    elif output == "text":
        if progress or event.get("message"):
            print(event["message"], file=sys.stderr, flush=True)
        else:
            stream = sys.stderr if event["status"] in {"unavailable", "failed"} else sys.stdout
            label = "{status} · Python {python_version}".format(**event) if event.get("python_version") else event["status"]
            print(label, file=stream, flush=True)
            for item in event["diagnostics"]:
                print(item["message"], file=stream, flush=True)
        if event.get("log_path"):
            print("安装日志 " + event["log_path"], file=sys.stderr, flush=True)


def _failure(phase, code, message, *, legacy=False):
    diagnostic = {"code": code, "message": message}
    result = {"phase": phase, "diagnostics": [diagnostic], **diagnostic}
    if not legacy:
        result["status"] = "failed"
    return result, 1


def _log_output(output):
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")

    def safe_url(match):
        try:
            parsed = urlsplit(match[0])
            if parsed.hostname:
                return f"{parsed.scheme}://{parsed.hostname}/…"
        except ValueError:
            pass
        return "<redacted URL>"

    return SECRET_URL.sub(safe_url, output or "")


def _run_logged(argv, cwd, log, phase, *, log_output=True, timeout=INSTALL_TIMEOUT_SECONDS):
    env = child_environment()
    env.update({"PIP_NO_INPUT": "1", "PYTHONIOENCODING": "utf-8"})
    log.write("\n[" + phase + "]\n")
    log.flush()
    try:
        process = subprocess.run(argv, cwd=cwd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=timeout,
                                 text=True, encoding="utf-8", errors="replace", env=env)
    except (OSError, subprocess.SubprocessError) as error:
        output = _log_output(getattr(error, "stdout", None) or getattr(error, "stderr", None)) if log_output else ""
        log.write(output + "\n[" + type(error).__name__ + "] " + _log_output(str(error)) + "\n")
        log.flush()
        raise
    else:
        if log_output:
            log.write(_log_output(process.stdout) + "\n")
            log.flush()
        return process.stdout


def _install_diagnostic(error):
    raw = getattr(error, "stdout", None) or getattr(error, "stderr", None) or ""
    output = (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw).casefold()
    if getattr(error, "errno", None) in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)} or any(phrase in output for phrase in (
            "no space left", "disk quota exceeded", "not enough space on the disk", "[winerror 112]", "[errno 28]")):
        return "DEPENDENCY_DISK_FULL", "磁盘空间或配额不足，请释放空间后重试。"
    if isinstance(error, PermissionError) or any(phrase in output for phrase in (
            "permission denied", "access is denied", "[winerror 5]", "[errno 13]", "read-only file system")):
        return "DEPENDENCY_PERMISSION_DENIED", "无法写入 Python 依赖目录，请检查执行账户的权限。"
    if "no module named pip" in output:
        return "DEPENDENCY_PIP_MISSING", PIP_MISSING_MESSAGE
    if "externally-managed-environment" in output or "externally managed" in output:
        return "DEPENDENCY_EXTERNALLY_MANAGED", "当前 Python 由系统管理，请选择允许 pip 安装依赖的 Python。"
    if any(phrase in output for phrase in (
            "401 client error", "403 client error", "401 unauthorized", "403 forbidden", "401 error, credentials")):
        return "DEPENDENCY_INDEX_AUTH_FAILED", "软件源拒绝访问，请检查内网软件源的账号或访问权限。"
    if any(phrase in output for phrase in ("connectionerror", "connection refused", "newconnectionerror",
                                          "failed to establish a new connection", "temporary failure in name resolution",
                                          "read timed out", "certificate_verify_failed", "proxyerror", "max retries exceeded")):
        return "DEPENDENCY_INDEX_UNAVAILABLE", "无法连接软件源，请检查网络、代理、证书和 pip 软件源配置。"
    return "DEPENDENCY_INSTALL_FAILED", PIP_FAILURE_MESSAGE


def _is_link(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT


@contextmanager
def _setup_lock(home):
    home.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(home / ".setup.lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            raise NodeError("INSTALL_BUSY", "知识库环境正在安装，请等待当前安装结束后重试。") from error
        yield


def _open_install_log(home):
    directory = home / "logs"
    directory.mkdir(mode=0o700, exist_ok=True)
    if _is_link(directory):
        raise OSError("The install log directory is linked")
    return tempfile.NamedTemporaryFile(dir=directory, mode="w", encoding="utf-8", prefix="setup-", suffix=".log", delete=False)


def _python_key(python):
    return os.path.normcase(os.path.normpath(python))


def _fresh_report(tool_root, version, bin_dir, *, dependencies_only=False):
    # A first per-user install may create the user site directory after this
    # process started. Reopen the selected Python to inspect its new sys.path.
    argv = [sys.executable, "-E", "-B", str(tool_root / "knowledge.py"), "doctor", "--environment-only", "--json"]
    if bin_dir is not None:
        argv.extend(["--bin-dir", str(bin_dir)])
    if dependencies_only:
        argv.append("--dependencies-only")
    statuses = {"ready", "needs_install"} if dependencies_only else {"ready", "needs_install", "needs_cli"}
    try:
        process = subprocess.run(argv, cwd=tool_root, stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=30, env=child_environment())
        result = json.loads(process.stdout)
        if (process.returncode == 0 and isinstance(result, dict)
                and result.get("status") in statuses
                and isinstance(result.get("python"), str)
                and _python_key(result["python"]) == _python_key(sys.executable)
                and result.get("tool_root") == str(tool_root) and result.get("toolkit_version") == version):
            return result
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _pip_configuration(cwd, pip, log):
    arguments = [*pip, "--python=", "config", "list"]
    try:
        # Read configuration using the target interpreter, even when a global
        # pip setting would normally dispatch pip to another Python.
        return _run_logged(arguments, cwd, log, "inspect pip configuration", log_output=False)
    except subprocess.CalledProcessError as error:
        if "no such option: --python" not in _log_output(error.stdout or error.stderr):
            raise
    # Older bundled pip releases neither accept --python nor dispatch through it.
    return _run_logged([*pip, "config", "list"], cwd, log, "inspect pip configuration", log_output=False)


def _has_pip_location_override(configuration):
    sections = {"global": {}, "install": {}}
    for line in configuration.splitlines():
        key, _, raw = line.partition("=")
        section, _, option = key.partition(".")
        if section not in sections or option not in PIP_LOCATION_OPTIONS:
            continue
        try:
            sections[section][option] = literal_eval(raw)
        except (SyntaxError, ValueError):
            return True
    settings = sections["global"] | sections["install"]
    return bool(sections["global"].get("python")) or any(settings.values())


def _install_dependencies(tool_root, log):
    pip = [sys.executable, *PYTHON_MODULE_FLAGS, "pip"]
    requirements = str((tool_root / "runtime/requirements.lock.txt").absolute())
    # Python 3.10 searches the working directory when invoking a module. Use
    # an empty directory while keeping the selected interpreter's user site.
    with tempfile.TemporaryDirectory(prefix="knowledge-pip-") as cwd:
        configuration = _pip_configuration(cwd, pip, log)
        if _has_pip_location_override(configuration):
            log.write("Pip configuration attempted to change the install location.\n")
            raise NodeError("DEPENDENCY_LOCATION_OVERRIDE", PIP_LOCATION_MESSAGE)
        _run_logged([*pip, "install", "-r", requirements], cwd, log, "install dependencies")


def _install_libreoffice(log):
    if not os.access(APT_GET, os.X_OK):
        raise NodeError("LIBREOFFICE_PACKAGE_MANAGER_UNAVAILABLE", "执行端没有可用的 apt-get。" + LIBREOFFICE_INSTALL_HINT)
    prefix = []
    if os.geteuid() != 0:
        if not os.access(SUDO, os.X_OK):
            raise NodeError("LIBREOFFICE_INSTALL_PERMISSION_REQUIRED", LIBREOFFICE_INSTALL_HINT)
        prefix = [SUDO, "-n", "--"]
    try:
        _run_logged([*prefix, APT_GET, "update"], "/", log, "update apt package lists",
                    timeout=APT_COMMAND_TIMEOUT_SECONDS)
        _run_logged([*prefix, APT_GET, "install", "-y", "--no-install-recommends", "--no-remove", LIBREOFFICE_PACKAGE],
                    "/", log, "install LibreOffice Writer", timeout=APT_COMMAND_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        output = _log_output(getattr(error, "stdout", None) or getattr(error, "stderr", None))
        if prefix and any(line.startswith("sudo:") for line in output.splitlines()):
            raise NodeError("LIBREOFFICE_INSTALL_PERMISSION_REQUIRED", LIBREOFFICE_INSTALL_HINT) from error
        raise NodeError("LIBREOFFICE_INSTALL_FAILED",
                        "LibreOffice 安装失败，请查看本地安装日志并检查执行端的 apt 软件源。" + LIBREOFFICE_INSTALL_HINT) from error


def _install(tool_root, version, bin_dir, result, progress, *, legacy, dependencies_only):
    log_path = None

    def fail(phase, code, message):
        final, status = _failure(phase, code, message, legacy=legacy)
        if log_path:
            final["log_path"] = log_path
        return final, status

    if result["status"] == "needs_install":
        pip_needed = any(item["code"] == "DEPENDENCY_UNAVAILABLE" for item in result["diagnostics"])
        office_gap = next((item for item in result["diagnostics"] if item["code"].startswith("LIBREOFFICE_")), None)
        office_progress = "正在用 apt 安装 LibreOffice Writer。"
        if office_gap and office_gap["code"] != "LIBREOFFICE_MISSING":
            return fail("checking", office_gap["code"], office_gap["message"])
        progress("installing", "正在用 pip 安装知识库依赖。" if pip_needed else office_progress)
        try:
            log = _open_install_log(managed_home(tool_root))
        except OSError:
            return fail("installing", "INSTALL_LOG_UNAVAILABLE", LOG_FAILURE_MESSAGE)
        with log:
            log_path = log.name
            prerequisite = next((item for item in result["diagnostics"]
                                 if item["code"] == "DEPENDENCY_PIP_MISSING"), None)
            if prerequisite:
                log.write(prerequisite["message"] + "\n")
                return fail("installing", prerequisite["code"], prerequisite["message"])
            try:
                if pip_needed:
                    _install_dependencies(tool_root, log)
                if office_gap:
                    if pip_needed:
                        progress("installing", office_progress)
                    _install_libreoffice(log)
            except NodeError as error:
                return fail("installing", error.code, str(error))
            except (OSError, subprocess.SubprocessError) as error:
                return fail("installing", *_install_diagnostic(error))
        result = _fresh_report(tool_root, version, bin_dir, dependencies_only=dependencies_only)
        if result is None:
            return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
        if result["status"] == "needs_install":
            office_gap = next((item for item in result["diagnostics"] if item["code"].startswith("LIBREOFFICE_")), None)
            if office_gap:
                return fail("verifying", "LIBREOFFICE_VERIFICATION_FAILED", LIBREOFFICE_INSTALL_HINT)
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
        except (OSError, ValueError, subprocess.SubprocessError):
            return fail("registering", "CLI_REGISTRATION_FAILED", "无法写入知识命令，请检查命令目录后重试。")

    progress("verifying", "正在复查执行端依赖。" if dependencies_only else "正在复查执行端依赖和知识命令。")
    if result["status"] == "needs_cli":
        report = _fresh_report if log_path else _try_report
        result = report(tool_root, version, bin_dir)
        if result is None:
            return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
        if result["status"] == "needs_install":
            return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")
    if result["status"] != "ready":
        return fail("verifying", "CLI_VERIFICATION_FAILED", CLI_CHECK_MESSAGE)
    if log_path:
        result["log_path"] = log_path
    return result, 0


def _try_report(tool_root, version, bin_dir, *, dependencies_only=False):
    try:
        return _report(tool_root, version, bin_dir, dependencies_only=dependencies_only)
    except (OSError, ValueError, ImportError, subprocess.SubprocessError):
        return None


def run_environment(tool_root, manifest, action, *, bin_dir=None, output="text", legacy=False, dependencies_only=False):
    def progress(phase, message):
        _emit({"phase": phase, "message": message}, output, progress=True)

    installing = action == "install"
    if installing:
        progress("checking", "正在检查工具包和执行端依赖。")
    version = manifest["version"]
    result = _try_report(tool_root, version, bin_dir, dependencies_only=dependencies_only)
    code = 0
    if result is None:
        if installing:
            result, code = _failure("checking", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE, legacy=legacy)
        else:
            result = {"status": "unavailable", "diagnostics": [{"code": "DEPENDENCY_CHECK_FAILED",
                                                                  "message": DEPENDENCY_CHECK_MESSAGE}]}
            code = 1
    elif installing:
        if result["status"] == "ready":
            progress("verifying", "执行端依赖已就绪。" if dependencies_only else "执行端依赖和知识命令已就绪。")
        else:
            try:
                with _setup_lock(managed_home(tool_root)):
                    result = _try_report(tool_root, version, bin_dir, dependencies_only=dependencies_only)
                    if result is None:
                        result, code = _failure("checking", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE,
                                                legacy=legacy)
                    else:
                        result, code = _install(tool_root, version, bin_dir, result, progress, legacy=legacy,
                                                dependencies_only=dependencies_only)
            except NodeError as error:
                result, code = _failure("installing", error.code, str(error), legacy=legacy)
            except OSError as error:
                result, code = _failure("installing", *_install_diagnostic(error), legacy=legacy)
    _emit(result, output)
    return code
