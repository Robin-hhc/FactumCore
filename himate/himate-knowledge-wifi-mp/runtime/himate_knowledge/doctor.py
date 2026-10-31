"""Read-only execution-host diagnostics, independent of business assets."""

import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import socket
import sys

from .protocol import NodeError as CommandError, envelope

def _doctor_gap(gaps, code, message, path, next_step):
    gaps.append({"code": code, "message": message, "path": str(path), "next_step": next_step})


def _doctor_read(path):
    """Read one named metadata file without traversing business directories."""
    path = Path(path)
    for part in (path, *path.parents):
        if part.is_symlink() or (os.path.lexists(part) and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked metadata path is not allowed")
    if not path.is_file():
        raise ValueError("Metadata file is missing or unreadable")
    return path.read_bytes()


def _doctor_yaml(raw):
    """Parse data only after the pinned installed YAML dependency was found."""
    import yaml

    class DoctorLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("Metadata mapping has a non-string or duplicate key")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    DoctorLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    result = yaml.load(raw.decode("utf-8-sig"), Loader=DoctorLoader)
    if not isinstance(result, dict):
        raise ValueError("Metadata must contain a YAML mapping")
    return result


def _doctor_rule_path(root, reference):
    from pathlib import PurePosixPath

    if (not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference
            or reference.startswith("/")):
        raise ValueError("Rule path must be knowledge-root relative")
    parts = PurePosixPath(reference).parts
    if (len(parts) < 3 or parts[0] != "governance"
            or parts[1] not in {"contracts", "schemas", "specs", "templates"}
            or "/".join(parts) != reference or any(part in {".", ".."} for part in parts)):
        raise ValueError("Rule path must name a registered governance framework file")
    return root.joinpath(*parts)


def _doctor_rules(root, yaml_available, gaps):
    """Verify declared rule bytes without importing any governance program."""
    path = root / "governance/framework.lock.yaml"
    data = {"path": str(path), "status": "not_checked", "digest": None,
            "schema_version": None, "contract_family": None, "tool_version": None,
            "files_registered": 0, "files_verified": 0, "gaps": []}
    start = len(gaps)
    guidance = "Restore the matching governance framework and lock on this execution host"
    try:
        raw = _doctor_read(path)
        data["digest"] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError) as error:
        _doctor_gap(gaps, "RULE_LOCK_UNAVAILABLE", str(error), path, guidance)
        data.update(status="blocked", gaps=gaps[start:])
        return data
    if not yaml_available:
        return data
    try:
        lock = _doctor_yaml(raw)
    except Exception as error:
        _doctor_gap(gaps, "RULE_LOCK_INVALID", "Cannot parse framework lock: " + str(error), path, guidance)
        data.update(status="blocked", gaps=gaps[start:])
        return data
    for key in ("schema_version", "contract_family", "tool_version"):
        value = lock.get(key)
        data[key] = value if isinstance(value, str) else None
    if (lock.get("schema_version") != "2.0" or lock.get("contract_family") != "aiot-wifi"
            or not isinstance(lock.get("tool_version"), str) or not lock["tool_version"].strip()):
        _doctor_gap(gaps, "RULE_CONTRACT_UNSUPPORTED", "Expected aiot-wifi contract 2.0 and an explicit tool version", path, guidance)
    capabilities = lock.get("capabilities")
    if (not isinstance(capabilities, dict)
            or any(capabilities.get(name) != "1.0" for name in ("checks", "indexing", "ingest_records"))
            or any(capabilities.get(name) not in (None, "1.0") for name in
                   ("workspace_mapping", "code_navigation", "incremental_patrol", "local_dbox"))):
        _doctor_gap(gaps, "RULE_CAPABILITY_UNSUPPORTED", "Required rule capabilities are absent or incompatible", path, guidance)
    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        _doctor_gap(gaps, "RULE_LOCK_INCOMPLETE", "Framework lock has no registered rule files", path, guidance)
    else:
        data["files_registered"] = len(files)
        seen = set()
        for row in files.values():
            if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                    or not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                    or row["path"] in seen):
                _doctor_gap(gaps, "RULE_LOCK_INVALID", "Invalid or duplicate registered rule entry", path, guidance)
                continue
            reference = row["path"]
            seen.add(reference)
            try:
                target = _doctor_rule_path(root, reference)
            except ValueError as error:
                _doctor_gap(gaps, "RULE_LOCK_INVALID", str(error), reference, guidance)
                continue
            try:
                content = _doctor_read(target)
            except (OSError, ValueError) as error:
                _doctor_gap(gaps, "RULE_FILE_UNAVAILABLE", str(error), target, guidance)
                continue
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                _doctor_gap(gaps, "RULE_FILE_DIGEST_MISMATCH", "Rule bytes differ from the registered digest", target, guidance)
            else:
                data["files_verified"] += 1
        required = {"governance/contracts/" + name + ".py" for name in
                    ("__init__", "validation", "workspace_config", "knowledge", "source_resources",
                     "indexing", "catalog", "cards_v3", "ingest", "library")}
        required.update({"governance/schemas/" + name for name in
                         ("profiles.yaml", "registries.yaml", "workspace.schema.json", "frontmatter.schema.json",
                          "sources.schema.json", "records.schema.json")})
        if isinstance(capabilities, dict) and capabilities.get("code_navigation") == "1.0":
            required.add("governance/contracts/code_symbols.py")
        if not required.issubset(seen):
            _doctor_gap(gaps, "RULE_LOCK_INCOMPLETE", "Required rules are not registered: " + ", ".join(sorted(required - seen)), path, guidance)
    try:
        if _doctor_read(path) != raw:
            _doctor_gap(gaps, "RULE_LOCK_CHANGED", "Framework lock changed during diagnosis", path, guidance)
    except (OSError, ValueError) as error:
        _doctor_gap(gaps, "RULE_LOCK_CHANGED", str(error), path, guidance)
    data.update(status="blocked" if len(gaps) > start else "verified", gaps=gaps[start:])
    return data


def _doctor_configuration(root, yaml_available, gaps, rules):
    """Load only the verified metadata selector, never the governance package."""
    data = {"path": None, "status": "not_checked", "knowledge_root": None,
            "verification": "knowledge_root_mapping_only"}
    guidance = "Provide the intended workspace config.yml with knowledge_roots.wifi mapped to this knowledge root"
    if not yaml_available or rules["status"] != "verified":
        return data
    try:
        lock_path = root / "governance/framework.lock.yaml"
        lock_bytes = _doctor_read(lock_path)
        if hashlib.sha256(lock_bytes).hexdigest() != rules["digest"]:
            raise ValueError("Framework lock changed before configuration discovery")
        lock = _doctor_yaml(lock_bytes)
        reference = "governance/contracts/workspace_config.py"
        registered = [row for row in lock["files"].values() if row["path"] == reference]
        source = _doctor_read(root / reference)
        if len(registered) != 1 or hashlib.sha256(source).hexdigest() != registered[0]["sha256"]:
            raise ValueError("Configuration selector differs from its verified rule entry")
        if _doctor_read(lock_path) != lock_bytes:
            raise ValueError("Framework lock changed before configuration discovery")
        # No package import, sys.path edit or cached pyc: only this small data
        # selector is compiled, after all registered rules passed diagnosis.
        selector = {"__name__": "_himate_doctor_workspace_config"}
        exec(compile(source, str(root / reference), "exec"), selector)
    except Exception as error:
        _doctor_gap(gaps, "RULE_FILE_UNAVAILABLE", str(error), root / "governance/contracts/workspace_config.py", guidance)
        data["status"] = "blocked"
        return data
    try:
        path = selector["select"](root)
        data["path"] = str(path)
        raw = _doctor_read(path)
        config = selector["configuration"](raw, path)
        # Selection supports historical readers; ready diagnosis still names
        # the current workspace contract, without inspecting business assets.
        if config.get("schema_version") != "2.0":
            raise selector["WorkspaceConfigError"]("WORKSPACE_CONFIG_INVALID", "Expected workspace contract 2.0", path)
        if selector["workspace_path"](path.parent, config["knowledge_roots"]["wifi"]).resolve() != root.resolve():
            raise selector["WorkspaceConfigError"]("WORKSPACE_CONFIG_CHANGED", "Selected configuration mapping changed", path)
        if _doctor_read(path) != raw:
            raise selector["WorkspaceConfigError"]("WORKSPACE_CONFIG_CHANGED", "Workspace configuration changed during diagnosis", path)
    except selector["WorkspaceConfigError"] as error:
        codes = {"WORKSPACE_CONFIG_INVALID": "CONFIG_INVALID", "WORKSPACE_CONFIG_AMBIGUOUS": "CONFIG_AMBIGUOUS",
                 "WORKSPACE_CONFIG_CHANGED": "CONFIG_CHANGED", "UNSAFE_WORKSPACE_PATH": "CONFIG_KNOWLEDGE_ROOT_MISMATCH",
                 "WORKSPACE_LINKED_PATH": "CONFIG_KNOWLEDGE_ROOT_MISMATCH", "PATH_CASE_ALIAS": "CONFIG_KNOWLEDGE_ROOT_MISMATCH"}
        code = codes.get(error.code, "CONFIG_KNOWLEDGE_ROOT_MISMATCH" if error.path else "CONFIG_UNAVAILABLE")
        data["path"] = error.path or data["path"]
        _doctor_gap(gaps, code, error.message, error.path or root, guidance)
        data["status"] = "blocked"
        return data
    except (OSError, ValueError) as error:
        _doctor_gap(gaps, "CONFIG_INVALID", str(error), data["path"] or root, guidance)
        data["status"] = "blocked"
        return data
    data["knowledge_root"] = str(root.resolve())
    data["status"] = "verified"
    return data


def doctor(root, manifest):
    gaps, dependencies = [], []
    for line in (root / "runtime/requirements.lock.txt").read_text(encoding="utf-8").splitlines():
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
        dependencies.append({"name": name, "expected": expected, "actual": actual})
        if actual != expected:
            gaps.append({"code": "DEPENDENCY_UNAVAILABLE", "message": name + " requires " + expected})
    yaml_available = any(row["name"].casefold() == "pyyaml" and row["actual"] == row["expected"]
                         for row in dependencies)
    if not yaml_available:
        _doctor_gap(gaps, "YAML_PARSER_UNAVAILABLE", "Pinned PyYAML is required to inspect rule/configuration data",
                    root / "runtime/requirements.lock.txt", "Prepare the pinned dependencies on this execution host and rerun doctor")
    rules = _doctor_rules(root, yaml_available, gaps)
    configuration = _doctor_configuration(root, yaml_available, gaps, rules)
    data = {"executor": "knowledge-cli", "knowledge_root": str(root), "hostname": socket.gethostname(),
            "platform": platform.system(), "python": sys.executable, "python_version": platform.python_version(),
            "runtime_version": manifest["version"], "dependencies": dependencies, "config_path": configuration["path"],
            "rules_lock": str(root / "governance/framework.lock.yaml"),
            "rules": rules, "rules_digest": rules["digest"], "rules_version": rules["tool_version"],
            "configuration": configuration,
            "execution_location": "current_host", "content_checked": False,
            "next_step": "Resolve the reported dependency, rule or workspace configuration gaps on this execution host and rerun doctor"
                         if gaps else "Choose a knowledge task"}
    return envelope("blocked" if gaps else "ok", "blocked" if gaps else "ready", data, gaps), 3 if gaps else 0
