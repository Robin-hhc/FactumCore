"""Read-only execution-host diagnostics, independent of business assets."""

import importlib.metadata
from importlib.util import find_spec
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys

from .execution import child_environment
from .protocol import (FRAMEWORK_LOCK, RULE_CONTRACT_PREFIX, NodeError as CommandError,
                       envelope, read_regular_bytes, verify_rule_files)


PIP_MISSING_MESSAGE = "当前 Python 缺少 pip，请选择已安装 pip 的 Python 3.10–3.12，然后重试 knowledge setup。"


def _doctor_gap(gaps, code, message, path, next_step):
    gaps.append({"code": code, "message": message, "path": str(path), "next_step": next_step})


def _doctor_configuration(tool_root, knowledge_root, gaps, verified):
    """Load only the verified metadata selector, never the governance package."""
    data = {"path": None, "status": "not_checked", "knowledge_root": None,
            "verification": "knowledge_root_configuration_only"}
    guidance = "Provide the module configuration as config.yml inside this knowledge root"
    if verified.report["status"] != "verified":
        return data
    reference = RULE_CONTRACT_PREFIX + "workspace_config.py"
    try:
        lock_path = tool_root / FRAMEWORK_LOCK
        source = verified.files[reference]
        if read_regular_bytes(tool_root / reference) != source:
            raise ValueError("Configuration selector changed after rules verification")
        if read_regular_bytes(lock_path) != verified.lock_bytes:
            raise ValueError("Framework lock changed before configuration discovery")
        # No package import, sys.path edit or cached pyc: only this small data
        # selector is compiled, after all registered rules passed diagnosis.
        selector = {"__name__": "_himate_doctor_workspace_config"}
        exec(compile(source, str(tool_root / reference), "exec"), selector)
    except Exception as error:
        _doctor_gap(gaps, "RULE_FILE_UNAVAILABLE", str(error), tool_root / reference, guidance)
        data["status"] = "blocked"
        return data
    try:
        path, raw, _ = selector["context"](knowledge_root)
        data["path"] = str(path)
        if read_regular_bytes(path) != raw:
            raise selector["WorkspaceConfigError"]("WORKSPACE_CONFIG_CHANGED", "Workspace configuration changed during diagnosis", path)
    except selector["WorkspaceConfigError"] as error:
        codes = {"WORKSPACE_CONFIG_INVALID": "CONFIG_INVALID", "WORKSPACE_CONFIG_AMBIGUOUS": "CONFIG_AMBIGUOUS",
                 "WORKSPACE_CONFIG_UNAVAILABLE": "CONFIG_UNAVAILABLE",
                 "WORKSPACE_CONFIG_CHANGED": "CONFIG_CHANGED", "UNSAFE_WORKSPACE_PATH": "CONFIG_KNOWLEDGE_ROOT_MISMATCH",
                 "WORKSPACE_LINKED_PATH": "CONFIG_KNOWLEDGE_ROOT_MISMATCH", "PATH_CASE_ALIAS": "CONFIG_KNOWLEDGE_ROOT_MISMATCH"}
        code = codes.get(error.code, "CONFIG_KNOWLEDGE_ROOT_MISMATCH" if error.path else "CONFIG_UNAVAILABLE")
        data["path"] = error.path or data["path"]
        _doctor_gap(gaps, code, error.message, error.path or knowledge_root, guidance)
        data["status"] = "blocked"
        return data
    except (OSError, ValueError) as error:
        _doctor_gap(gaps, "CONFIG_INVALID", str(error), data["path"] or knowledge_root, guidance)
        data["status"] = "blocked"
        return data
    data["knowledge_root"] = str(knowledge_root)
    data["status"] = "verified"
    return data


def _matches_pin(actual, expected):
    if actual is None:
        return False
    if actual == expected:
        return True
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import InvalidVersion
    except ImportError:
        return False
    try:
        return SpecifierSet("==" + expected).contains(actual, prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return False


def inspect_dependencies(requirements):
    gaps, dependencies = [], []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;*]+)(?:\s*;\s*(.+))?", line)
        if not match:
            raise CommandError("INVALID_RUNTIME_LOCK", "Expected exact runtime dependency pins")
        name, expected, marker = match.groups()
        if marker:
            try:
                from packaging.markers import InvalidMarker, Marker
            except ImportError:
                gaps.append({"code": "DEPENDENCY_UNAVAILABLE", "message": "packaging is required to evaluate runtime dependency markers"})
                continue
            try:
                if not Marker(marker).evaluate():
                    continue
            except InvalidMarker as error:
                raise CommandError("INVALID_RUNTIME_LOCK", "Invalid runtime dependency marker") from error
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        ready = _matches_pin(actual, expected)
        status = "ready" if ready else "missing" if actual is None else "mismatch"
        dependencies.append({"name": name, "expected": expected, "actual": actual, "status": status})
        if not ready:
            gaps.append({"code": "DEPENDENCY_UNAVAILABLE", "message": name + " requires " + expected})
    return dependencies, gaps


def _is_apt_linux():
    if sys.platform != "linux":
        return False
    try:
        return platform.freedesktop_os_release().get("ID") in {"ubuntu", "debian"}
    except OSError:
        return False


def _office_command_on_path(name, search_path):
    if sys.platform != "win32":
        return shutil.which(name, path=search_path)
    # shutil.which can implicitly prepend the working directory on Windows.
    extensions = (os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD").split(os.pathsep)
    names = [name + extension for extension in extensions if extension]
    if Path(name).suffix.casefold() in {extension.casefold() for extension in extensions if extension}:
        names.insert(0, name)
    for directory in search_path.split(os.pathsep):
        if not directory:
            continue
        for filename in names:
            candidate = Path(directory) / filename
            if candidate.is_file():
                return str(candidate)
    return None


def _libreoffice_gap():
    # Match Docling's precedence. Installing an apt package cannot repair an
    # explicit override that still points to a broken executable.
    configured = os.environ.get("DOCLING_LIBREOFFICE_CMD")
    # A check may run with the knowledge repository as its cwd.
    search_path = os.pathsep.join(item for item in os.get_exec_path() if Path(item).is_absolute())
    if configured:
        command = configured if Path(configured).is_absolute() else None
        if not command and not os.path.dirname(configured):
            command = _office_command_on_path(configured, search_path)
    else:
        command = _office_command_on_path("libreoffice", search_path) or _office_command_on_path("soffice", search_path)
        if command is None:
            if not _is_apt_linux():
                return {"code": "LIBREOFFICE_MANUAL_SETUP_REQUIRED",
                        "message": "请在执行端安装 LibreOffice Writer，并让该账户通过 PATH 或 DOCLING_LIBREOFFICE_CMD 找到它。"}
            return {"code": "LIBREOFFICE_MISSING",
                    "message": "执行端缺少用于渲染 Office 矢量图的 LibreOffice Writer。"}
    if command:
        try:
            subprocess.run([command, "--version"], cwd="/", check=True, timeout=10, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=dict(child_environment(), PATH=search_path))
        except (OSError, subprocess.SubprocessError):
            pass
        else:
            return None
    return {"code": "LIBREOFFICE_COMMAND_UNAVAILABLE",
            "message": "无法运行 LibreOffice，请检查 DOCLING_LIBREOFFICE_CMD 或 PATH 中的软件路径和权限。"}


def dependency_lock(tool_root, capability):
    filename = "requirements.lock.txt" if capability else "requirements-base.lock.txt"
    return tool_root / "runtime" / filename


def inspect_runtime_dependencies(requirements, capability=None):
    dependencies, gaps = inspect_dependencies(requirements)
    if gaps and find_spec("pip") is None:
        gaps.insert(0, {"code": "DEPENDENCY_PIP_MISSING", "message": PIP_MISSING_MESSAGE})
    office_gap = _libreoffice_gap() if capability == "libreoffice" else None
    if office_gap:
        gaps.append(office_gap)
    return dependencies, gaps


def doctor(tool_root, knowledge_root, manifest, *, capability=None):
    requirements = dependency_lock(tool_root, capability)
    reports, gaps = inspect_runtime_dependencies(requirements, capability)
    yaml_available = any(row["name"].casefold() == "pyyaml" and row["status"] == "ready"
                         for row in reports)
    dependencies = [{key: value for key, value in row.items() if key != "status"} for row in reports]
    if not yaml_available:
        _doctor_gap(gaps, "YAML_PARSER_UNAVAILABLE", "Pinned PyYAML is required to inspect rule/configuration data",
                    requirements, "Prepare the pinned dependencies on this execution host and rerun doctor")
    verified = verify_rule_files(tool_root, manifest["assets"][FRAMEWORK_LOCK]["sha256"],
                                 yaml_available=yaml_available)
    rules = verified.report
    gaps.extend(rules["gaps"])
    configuration = _doctor_configuration(tool_root, knowledge_root, gaps, verified)
    data = {"executor": "knowledge-cli", "knowledge_root": str(knowledge_root), "tool_root": str(tool_root),
            "hostname": socket.gethostname(),
            "platform": platform.system(), "python": sys.executable, "python_version": platform.python_version(),
            "runtime_version": manifest["version"], "dependencies": dependencies, "config_path": configuration["path"],
            "rules_lock": str(tool_root / FRAMEWORK_LOCK),
            "rules": rules, "rules_digest": rules["digest"], "rules_version": rules["tool_version"],
            "configuration": configuration,
            "execution_location": "current_host", "content_checked": False,
            "next_step": "Resolve the reported dependency, rule or workspace configuration gaps on this execution host and rerun doctor"
                         if gaps else "Choose a knowledge task"}
    return envelope("blocked" if gaps else "ok", "blocked" if gaps else "ready", data, gaps), 3 if gaps else 0
