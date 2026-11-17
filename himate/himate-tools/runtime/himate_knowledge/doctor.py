"""Read-only execution-host diagnostics, independent of business assets."""

import importlib.metadata
import platform
import re
import socket
import sys

from .protocol import (FRAMEWORK_LOCK, RULE_CONTRACT_PREFIX, NodeError as CommandError,
                       envelope, read_regular_bytes, verify_rule_files)


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


def doctor(tool_root, knowledge_root, manifest):
    requirements = tool_root / "runtime/requirements.lock.txt"
    reports, gaps = inspect_dependencies(requirements)
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
