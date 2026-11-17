"""Check or prepare the knowledge virtual environment and launcher."""

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
from .execution import managed_home, managed_python, selected_python
from .protocol import NodeError


INSTALL_TIMEOUT_SECONDS = 30 * 60
DEPENDENCY_CHECK_MESSAGE = "无法读取工具包的依赖清单，请检查工具包版本和 Python 路径。"
CLI_CHECK_MESSAGE = "知识命令无法启动，请检查命令目录、工具包和 Python 路径后重试。"
NPM_PACKAGE = "@himate/knowledge-cli"
NPM_REPAIR_MESSAGE = "请重新安装 @himate/knowledge-cli，并检查 npm 命令目录是否在 PATH 中。"
VENV_REQUIRED_MESSAGE = "知识库虚拟环境尚未就绪，请运行 knowledge setup。"
PIP_FAILURE_MESSAGE = "依赖安装失败，请查看本地安装日志后重试。"
LOG_FAILURE_MESSAGE = "无法写入本地安装日志，请检查用户目录的权限和磁盘空间。"
PIP_LOCATION_OPTIONS = {"target", "prefix", "user", "root", "python"}
PIP_LOCATION_MESSAGE = "pip 安装位置被配置覆盖，请移除 pip 配置中的 target、prefix、root、python 或 user 安装位置设置后重试。"
PYTHON_MODULE_FLAGS = ("-I", "-X", "utf8", "-m")
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
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env=_child_environment())


def _report(tool_root, version, bin_dir):
    dependencies, gaps = doctor.inspect_dependencies(tool_root / "runtime/requirements.lock.txt")
    dependencies_missing = bool(gaps)
    if dependencies_missing:
        prerequisite = _venv_diagnostic(creating_venv=False)
        if prerequisite:
            gaps.insert(0, prerequisite)
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


def _missing_environment_report(tool_root, version, bin_dir):
    prerequisite = _venv_diagnostic(creating_venv=True)
    gaps = [prerequisite or {"code": "VENV_REQUIRED", "message": VENV_REQUIRED_MESSAGE}]
    command = None
    try:
        if bin_dir is None:
            command = _inspect_npm_command(tool_root, version)
        if command is None:
            command = command_install.inspect_command(tool_root, bin_dir)
    except (NodeError, OSError):
        pass
    return {"status": "needs_install", "python": None, "python_version": None,
            "bootstrap_python": sys.executable, "bootstrap_python_version": platform.python_version(),
            "environment_path": str(managed_home(tool_root) / ".venv"),
            "toolkit_version": version, "tool_root": str(tool_root), "dependencies": [],
            "diagnostics": gaps, "command": command}


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


def _child_environment():
    ignored = {"PIP_" + option.upper() for option in PIP_LOCATION_OPTIONS}
    ignored.update({"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"})
    return {key: value for key, value in os.environ.items()
            if key.upper() not in ignored}


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


def _run_logged(argv, cwd, log, phase, *, log_output=True):
    env = _child_environment()
    env.update({"PIP_NO_INPUT": "1", "PYTHONIOENCODING": "utf-8"})
    log.write("\n[" + phase + "]\n")
    log.flush()
    try:
        process = subprocess.run(argv, cwd=cwd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=INSTALL_TIMEOUT_SECONDS,
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


def _venv_package_hint():
    if sys.platform == "linux":
        try:
            release = platform.freedesktop_os_release()
        except OSError:
            release = {}
        if {release.get("ID"), *release.get("ID_LIKE", "").split()} & {"debian", "ubuntu"}:
            version = f"{sys.version_info.major}.{sys.version_info.minor}"
            return f"请运行 sudo apt install python{version}-venv，然后重试 knowledge setup。"
    if sys.platform == "win32":
        return "请使用完整的 Python 3.10–3.12 安装程序，勾选 pip，然后重试 knowledge setup。"
    return "请安装带 venv 和 ensurepip 的 Python 3.10–3.12，然后重试 knowledge setup。"


def _venv_diagnostic(*, creating_venv):
    missing = []
    if creating_venv and find_spec("venv") is None:
        missing.append("venv")
    if (creating_venv or find_spec("pip") is None) and find_spec("ensurepip") is None:
        missing.append("ensurepip")
    if not missing:
        return None
    modules = "、".join(missing)
    return {"code": "VENV_MODULE_MISSING",
            "message": f"Python {platform.python_version()}（{sys.executable}）缺少 {modules}。"
                       + _venv_package_hint()}


def _install_diagnostic(error, *, creating_venv=False):
    raw = getattr(error, "stdout", None) or getattr(error, "stderr", None) or ""
    output = (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw).casefold()
    if getattr(error, "errno", None) in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)} or any(phrase in output for phrase in (
            "no space left", "disk quota exceeded", "not enough space on the disk", "[winerror 112]", "[errno 28]")):
        return "DEPENDENCY_DISK_FULL", "磁盘空间或配额不足，请释放空间后重试。"
    if isinstance(error, PermissionError) or any(phrase in output for phrase in (
            "permission denied", "access is denied", "[winerror 5]", "[errno 13]", "read-only file system")):
        return "DEPENDENCY_PERMISSION_DENIED", "无法写入虚拟环境或依赖目录，请检查执行账户的权限。"
    if ((creating_venv and any(phrase in output for phrase in ("ensurepip", "no module named venv", "python3-venv")))
            or "no module named ensurepip" in output):
        return "VENV_MODULE_MISSING", _venv_package_hint()
    if creating_venv:
        return "VENV_CREATE_FAILED", "无法准备知识库虚拟环境，请查看本地安装日志。"
    if "externally-managed-environment" in output or "externally managed" in output:
        return "DEPENDENCY_EXTERNALLY_MANAGED", "Python 拒绝安装到当前环境，请检查虚拟环境解释器与 pip 配置。"
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


def _same_python(python):
    # The POSIX venv executable usually links to the base interpreter. Keep its
    # invoked path so dependency inspection still takes place in the venv.
    return python is not None and _python_key(python) == _python_key(sys.executable)


def _python_key(python):
    return os.path.normcase(os.path.normpath(python))


def _target_json(tool_root, python, arguments, bin_dir):
    argv = [str(python), "-B", str(tool_root / "knowledge.py"), *arguments, "--json"]
    if bin_dir is not None:
        argv.extend(["--bin-dir", str(bin_dir)])
    process = subprocess.run(argv, cwd=tool_root, stdin=subprocess.DEVNULL, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=30, env=_child_environment())
    result = json.loads(process.stdout)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object from the virtual environment")
    return result, process.returncode


def _register(tool_root, python, bin_dir):
    add_path = os.name == "nt" and bin_dir is None
    if _same_python(python):
        command_install.deploy_command(tool_root, bin_dir, add_path=add_path)
        return
    result, code = _target_json(tool_root, python, ["install-command", *(["--add-path"] if add_path else [])], bin_dir)
    if code != 0:
        error = next(iter(result.get("diagnostics", [])), {})
        raise NodeError(error.get("code", "CLI_REGISTRATION_FAILED"), "Could not register the target launcher")


def _pip_configuration(tool_root, pip, log):
    arguments = [*pip, "--python=", "config", "list"]
    try:
        # Read configuration using the target interpreter, even when a global
        # pip setting would normally dispatch pip to another Python.
        return _run_logged(arguments, tool_root, log, "inspect pip configuration", log_output=False)
    except subprocess.CalledProcessError as error:
        if "no such option: --python" not in _log_output(error.stdout or error.stderr):
            raise
    # Older bundled pip releases neither accept --python nor dispatch through it.
    return _run_logged([*pip, "config", "list"], tool_root, log, "inspect pip configuration", log_output=False)


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
    user = settings.pop("user", "")
    return (bool(sections["global"].get("python")) or any(settings.values())
            or str(user).casefold() not in {"", "0", "no", "n", "f", "false", "off"})


def _install_dependencies(tool_root, python, log):
    pip = [str(python), *PYTHON_MODULE_FLAGS, "pip"]
    try:
        configuration = _pip_configuration(tool_root, pip, log)
    except subprocess.CalledProcessError as error:
        # An interrupted venv creation can leave a usable interpreter without pip.
        if "no module named pip" not in _log_output(error.stdout or error.stderr).casefold():
            raise
        _run_logged([str(python), *PYTHON_MODULE_FLAGS, "ensurepip", "--upgrade"], tool_root, log, "bootstrap pip")
        configuration = _pip_configuration(tool_root, pip, log)
    if _has_pip_location_override(configuration):
        log.write("Pip configuration attempted to change the install location.\n")
        raise NodeError("DEPENDENCY_LOCATION_OVERRIDE", PIP_LOCATION_MESSAGE)
    arguments = [*pip, "--require-virtualenv", "install", "-r", str(tool_root / "runtime/requirements.lock.txt")]
    _run_logged(arguments, tool_root, log, "install dependencies")


def _install(tool_root, version, bin_dir, python, result, progress, *, legacy):
    log_path = None

    def fail(phase, code, message):
        final, status = _failure(phase, code, message, legacy=legacy)
        if log_path:
            final["log_path"] = log_path
        return final, status

    if result["status"] == "needs_install":
        progress("installing", "正在准备知识库虚拟环境和锁定依赖。")
        try:
            log = _open_install_log(managed_home(tool_root))
        except OSError:
            return fail("installing", "INSTALL_LOG_UNAVAILABLE", LOG_FAILURE_MESSAGE)
        with log:
            log_path = log.name
            prerequisite = next((item for item in result["diagnostics"]
                                 if item["code"] == "VENV_MODULE_MISSING"), None)
            if prerequisite:
                log.write(prerequisite["message"] + "\n")
                return fail("installing", prerequisite["code"], prerequisite["message"])
            creating_venv = python is None
            try:
                if creating_venv:
                    directory = managed_home(tool_root) / ".venv"
                    if _is_link(directory):
                        raise OSError("The virtual environment directory is linked")
                    _run_logged([sys.executable, *PYTHON_MODULE_FLAGS, "venv", str(directory)],
                                tool_root, log, "create virtual environment")
                    python = selected_python(tool_root)
                    if python is None or _python_key(python) != _python_key(managed_python(tool_root)):
                        raise OSError("The virtual environment interpreter is unavailable")
                creating_venv = False
                _install_dependencies(tool_root, python, log)
            except NodeError as error:
                return fail("installing", error.code, str(error))
            except (OSError, subprocess.SubprocessError) as error:
                return fail("installing", *_install_diagnostic(error, creating_venv=creating_venv))
        result = _try_report(tool_root, version, bin_dir, python)
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
            _register(tool_root, python, bin_dir)
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

    progress("verifying", "正在复查 Python 依赖和知识命令。")
    result = _try_report(tool_root, version, bin_dir, python)
    if result is None:
        return fail("verifying", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE)
    if result["status"] == "needs_install":
        return fail("verifying", "DEPENDENCY_INSTALL_FAILED", "依赖复查仍有缺失或版本不匹配，请检查 Python 后重试。")
    if result["status"] != "ready":
        return fail("verifying", "CLI_VERIFICATION_FAILED", CLI_CHECK_MESSAGE)
    if log_path:
        result["log_path"] = log_path
    return result, 0


def _try_report(tool_root, version, bin_dir, python):
    try:
        if python is None:
            return _missing_environment_report(tool_root, version, bin_dir)
        if _same_python(python):
            return _report(tool_root, version, bin_dir)
        result, code = _target_json(tool_root, python, ["doctor", "--environment-only"], bin_dir)
        if (code == 0 and isinstance(result.get("python"), str) and _python_key(result["python"]) == _python_key(python)
                and result.get("tool_root") == str(tool_root) and result.get("toolkit_version") == version):
            return result
        return None
    except (OSError, ValueError, ImportError, subprocess.SubprocessError):
        return None


def run_environment(tool_root, manifest, action, *, bin_dir=None, output="text", legacy=False):
    def progress(phase, message):
        _emit({"phase": phase, "message": message}, output, progress=True)

    installing = action == "install"
    if installing:
        progress("checking", "正在检查工具包和 Python 依赖。")
    version = manifest["version"]
    python = selected_python(tool_root)
    result = _try_report(tool_root, version, bin_dir, python)
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
            progress("verifying", "Python 依赖和知识命令已就绪。")
        else:
            try:
                with _setup_lock(managed_home(tool_root)):
                    python = selected_python(tool_root)
                    result = _try_report(tool_root, version, bin_dir, python)
                    if result is None:
                        result, code = _failure("checking", "DEPENDENCY_CHECK_FAILED", DEPENDENCY_CHECK_MESSAGE,
                                                legacy=legacy)
                    else:
                        result, code = _install(tool_root, version, bin_dir, python, result, progress, legacy=legacy)
            except NodeError as error:
                result, code = _failure("installing", error.code, str(error), legacy=legacy)
            except OSError as error:
                result, code = _failure("installing", *_install_diagnostic(error), legacy=legacy)
    _emit(result, output)
    return code
