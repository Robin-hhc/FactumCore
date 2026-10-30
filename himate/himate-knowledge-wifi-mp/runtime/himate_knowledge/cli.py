"""Human/Agent command interface. Content decisions remain with the Agent."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import socket
import subprocess
import sys
import uuid


STAGES = ("explore", "source", "change-plan", "view-materialize", "lint", "apply", "query", "maintain")
COMMANDS = (*STAGES, "record", "review", "search", "read", "patrol", "status", "doctor", "install-command")


class CommandError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class CommandParser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError("INVALID_ARGUMENT", message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CommandError("DUPLICATE_KEY", "Repeated JSON key: " + key)
        value[key] = item
    return value


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=object_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(CommandError("INVALID_JSON", "Non-finite JSON value: " + x)))


def parser():
    result = CommandParser(description=__doc__)
    result.add_argument("command", choices=COMMANDS)
    result.add_argument("arguments", nargs="*")
    for option in ("action", "input", "output", "knowledge-root", "rules-digest", "catalog", "registry",
                   "operation-id", "source", "path", "receipt", "purpose", "channel", "bin-dir"):
        result.add_argument("--" + option)
    result.add_argument("--json", action="store_true", help="Print one structured result on stdout")
    result.add_argument("--top-k", type=int)
    result.add_argument("--add-path", action="store_true", help="Register the command directory on the Windows user PATH")
    result.add_argument("--legacy-transport", action="store_true", help=argparse.SUPPRESS)
    return result


def envelope(status, phase, data=None, diagnostics=None):
    value = {"schema_version": "2.0", "record_kind": "result", "status": status,
             "phase": phase, "data": data or {}, "diagnostics": diagnostics or []}
    value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def safe_output(root, output, operation=None, *, stage_report=False):
    output = Path(os.path.abspath(output))
    inside = output.is_relative_to(root)
    if inside:
        relative = output.relative_to(root)
        allowed = (".build", "operations", operation) if operation else (".build",)
        accepted = (relative.parts[0] == ".build"
                    if stage_report else relative.parts[:len(allowed)] == allowed)
        if relative.parts[:2] == (".build", "operations"):
            accepted = accepted and len(relative.parts) >= 3 and relative.parts[2] == operation
        if not accepted:
            raise CommandError("OUTPUT_OUTSIDE_OPERATION", "Output must stay in this operation's .build directory")
    for part in (output, *output.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise CommandError("LINKED_OUTPUT", "Linked output paths are not allowed")
        if not inside and (part / "governance/framework.lock.yaml").is_file():
            raise CommandError("OUTPUT_OUTSIDE_OPERATION", "A report cannot write into another knowledge repository")
    if output.exists():
        raise CommandError("OUTPUT_EXISTS", "Choose a fresh result path")
    return output


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
                    ("__init__", "validation", "knowledge", "source_resources", "records", "indexing", "checks")}
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


def _doctor_configuration(root, yaml_available, gaps):
    """Check the nearest declaration points to this K; never skip a wrong one."""
    from pathlib import PurePosixPath

    data = {"path": None, "status": "not_checked", "knowledge_root": None,
            "verification": "knowledge_root_mapping_only"}
    path = None
    guidance = "Provide the intended workspace config.yml with knowledge_roots.wifi mapped to this knowledge root"
    for parent in (root, *root.parents):
        candidate = parent / "config.yml"
        if os.path.lexists(candidate):
            path = candidate
            break
    if path is None:
        _doctor_gap(gaps, "CONFIG_UNAVAILABLE", "Workspace config.yml was not found", root, guidance)
        data["status"] = "blocked"
        return data
    data["path"] = str(path)
    if not yaml_available:
        return data
    try:
        raw = _doctor_read(path)
        config = _doctor_yaml(raw)
    except Exception as error:
        _doctor_gap(gaps, "CONFIG_INVALID", "Cannot read workspace configuration: " + str(error), path, guidance)
        data["status"] = "blocked"
        return data
    roots = config.get("knowledge_roots")
    reference = roots.get("wifi") if isinstance(roots, dict) else None
    if (config.get("schema_version") != "2.0" or not isinstance(roots, dict) or set(roots) != {"wifi"}
            or not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference
            or reference.startswith("/")):
        _doctor_gap(gaps, "CONFIG_KNOWLEDGE_ROOT_MISMATCH", "Expected one relative knowledge_roots.wifi mapping in workspace contract 2.0", path, guidance)
        data["status"] = "blocked"
        return data
    parts = PurePosixPath(reference).parts
    valid = "/".join(parts) == reference and not any(part in {".", ".."} for part in parts)
    mapped = path.parent
    for part in parts:
        mapped /= part
        if mapped.is_symlink() or (os.path.lexists(mapped) and getattr(mapped.lstat(), "st_file_attributes", 0) & 0x400):
            valid = False
    data["knowledge_root"] = str(mapped.resolve())
    if not valid or mapped.resolve() != root.resolve():
        _doctor_gap(gaps, "CONFIG_KNOWLEDGE_ROOT_MISMATCH", "Nearest configuration points to a different or unsafe knowledge root", path, guidance)
        data["status"] = "blocked"
        return data
    try:
        unchanged = _doctor_read(path) == raw
    except (OSError, ValueError):
        unchanged = False
    if not unchanged:
        _doctor_gap(gaps, "CONFIG_CHANGED", "Workspace configuration changed during diagnosis", path, guidance)
        data["status"] = "blocked"
        return data
    data["status"] = "verified"
    return data


def doctor(root, manifest):
    gaps, dependencies = [], []
    for line in (root / "runtime/requirements.lock.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise CommandError("INVALID_RUNTIME_LOCK", "Expected exact runtime dependency pins")
        name, expected = match.groups()
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
    configuration = _doctor_configuration(root, yaml_available, gaps)
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


def _set(request, name, value):
    if value is None:
        return
    if name in request and request[name] != value:
        raise CommandError("ARGUMENT_CONFLICT", "Argument conflicts with JSON field: " + name)
    request[name] = value


def request_for(args, root):
    if args.input:
        source_bytes = None if args.input == "-" else Path(args.input).read_bytes()
        raw = sys.stdin.read() if args.input == "-" else source_bytes.decode("utf-8-sig")
        request = strict_json(raw)
        if not isinstance(request, dict):
            raise CommandError("INVALID_REQUEST", "A JSON object is required")
        args.original_request = canonical(request)
        args.original_bytes = source_bytes
    else:
        request = {}
    command, action, words = args.command, args.action, args.arguments
    stage = "query" if command in {"query", "search", "read"} else command
    if command == "record":
        if words or action not in (None, "record"):
            raise CommandError("INVALID_ACTION", "record accepts its request and options only")
        # The public task has its own name while the original P5 engine and
        # persisted identity remain shared with source --action record.
        stage, action = "source", "record"
    elif command == "review":
        if words or action not in (None, "review"):
            raise CommandError("INVALID_ACTION", "review accepts its request and options only")
        # P4 has a clear task entry while the lint engine and saved identity stay shared.
        stage, action = "lint", "review"
    elif command == "patrol":
        if len(words) != 1 or words[0] not in {"sync", "plan", "reindex", "complete"}:
            raise CommandError("INVALID_ACTION", "Use patrol sync, plan, reindex or complete")
        stage, selected = "maintain", "patrol-" + words[0]
        if action is not None and action != selected:
            raise CommandError("ARGUMENT_CONFLICT", "Patrol action differs")
        action = selected
    elif command == "status":
        if len(words) != 1:
            raise CommandError("INVALID_ACTION", "Use status <operation-id>")
        if action is not None and action != "status":
            raise CommandError("ARGUMENT_CONFLICT", "Status action differs")
        stage, action = "source", "status"
        _set(request, "target_operation_id", words[0])
    elif command == "read":
        if len(words) != 1:
            raise CommandError("INVALID_ACTION", "Use read <card-id> --receipt <search-receipt>")
        if action is not None and action != "read":
            raise CommandError("ARGUMENT_CONFLICT", "Read action differs")
        action = "read"
        _set(request, "card_id", words[0])
        _set(request, "receipt_ref", args.receipt)
        if not request.get("receipt_ref"):
            raise CommandError("SEARCH_RECEIPT_REQUIRED", "Use --receipt with the exact search receipt")
    elif command in {"query", "search"}:
        if words:
            _set(request, "query", " ".join(words))
        action = action or "search"
    elif words:
        if len(words) != 1:
            raise CommandError("INVALID_ACTION", "Pass one stage action or use --input")
        if action is not None and action != words[0]:
            raise CommandError("ARGUMENT_CONFLICT", "Positional action differs from --action")
        action = words[0]
    if stage not in STAGES:
        raise CommandError("INVALID_COMMAND", "Unknown stage")
    for key in ("operation_id", "source", "path", "purpose", "channel", "top_k"):
        _set(request, "target_path" if stage == "explore" and key == "path" else key, getattr(args, key))
    if args.receipt and command != "read":
        _set(request, "receipt_ref", args.receipt)
    if "operation_id" not in request:
        request["operation_id"] = "cli-" + uuid.uuid4().hex
    if not isinstance(request["operation_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", request["operation_id"]):
        raise CommandError("INVALID_ID", "Expected a safe operation ID")
    if stage == "explore" and "target_path" not in request:
        request["target_path"] = str(root)
    return stage, action, request


def execute(args, root):
    from .stage_dispatch import run_stage

    stage, action, request = request_for(args, root)
    operation = request["operation_id"]
    call_id = uuid.uuid4().hex
    base = root / ".build/operations" / operation / "cli"
    original = (args.input and args.input != "-" and
                args.original_request == canonical(request))
    incoming = Path(args.input).absolute() if original else safe_output(root, base / (call_id + ".request.json"), operation)
    outgoing = safe_output(root, args.output or base / (call_id + ".result.json"), operation,
                           stage_report=bool(args.output))
    if original:
        if incoming.read_bytes() != args.original_bytes:
            raise CommandError("INPUT_CHANGED", "Request changed while being read")
    else:
        incoming.parent.mkdir(parents=True, exist_ok=True)
        with incoming.open("xb") as stream:
            stream.write(canonical(request))
    arguments = ["--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(root)]
    for name, value in (("action", action), ("rules-digest", args.rules_digest),
                        ("catalog", args.catalog), ("registry", args.registry if stage == "explore" else None)):
        if value is not None:
            arguments += ["--" + name, value]
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = run_stage(stage, arguments)
    if outgoing.is_file():
        result = strict_json(outgoing.read_text(encoding="utf-8"))
    else:
        lines = [line for line in captured.getvalue().splitlines() if line.strip()]
        try:
            result = strict_json(lines[-1])
        except (ValueError, IndexError) as error:
            raise CommandError("RESULT_UNAVAILABLE", "Stage did not return a readable result; exit=" + str(code)) from error
    if not isinstance(result, dict):
        raise CommandError("INVALID_RESULT", "Stage result must be an object")
    # The persisted stage record remains unchanged. The CLI presentation binds
    # that record to exact transport paths, without asserting completion itself.
    result = dict(result)
    result["cli_transport"] = {
        "stage_result_digest": result.get("digest"),
        "request_ref": incoming.relative_to(root).as_posix() if incoming.is_relative_to(root) else str(incoming),
        "result_ref": outgoing.relative_to(root).as_posix() if outgoing.is_relative_to(root) else str(outgoing),
        "knowledge_root": str(root), "executor": "knowledge-cli",
    }
    result.pop("digest", None)
    result["digest"] = hashlib.sha256(canonical(result)).hexdigest()
    return result, code


def install_command(args, root):
    if args.arguments:
        raise CommandError("INVALID_ACTION", "install-command takes options only")
    if args.add_path and os.name != "nt":
        raise CommandError("PATH_REGISTRATION_UNAVAILABLE", "Add the command directory to your shell PATH explicitly")
    destination = Path(args.bin_dir).expanduser().absolute() if args.bin_dir else (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HiMate/bin" if os.name == "nt"
        else Path.home() / ".local/bin")
    if destination.resolve().is_relative_to(root):
        raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the machine command outside the knowledge repository")
    for path in (destination, *destination.parents):
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
            raise CommandError("LINKED_OUTPUT", "Command directory must not be linked")
        if (path / "governance/framework.lock.yaml").is_file():
            raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the machine command outside every knowledge repository")
    destination.mkdir(parents=True, exist_ok=True)
    dispatcher = destination / "knowledge-dispatch.py"
    dispatch = '''"""Machine command shim; selects the current repository, never a fixed group."""
import sys
def normalized(value):
    value = value.replace("\\\\", "/").rstrip("/")
    return value.casefold() if sys.platform == "win32" else value
prefixes = tuple(normalized(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix} if p)
sys.path[:] = [p for p in sys.path if p and any(normalized(p) == base or normalized(p).startswith(base + "/") for base in prefixes)]
import os
from pathlib import Path
import subprocess
for directory in (Path.cwd(), *Path.cwd().parents):
    entry = directory / "knowledge.py"
    if entry.is_file() and (directory / "governance/framework.lock.yaml").is_file():
        raise SystemExit(subprocess.call([sys.executable, "-B", str(entry), *sys.argv[1:]]))
print('{"status":"error","phase":"invalid","diagnostics":[{"code":"KNOWLEDGE_ROOT_NOT_FOUND","message":"Run knowledge inside the intended knowledge directory"}]}')
raise SystemExit(2)
'''
    if os.name == "nt":
        launcher = destination / "knowledge.cmd"
        command = '@echo off\r\n"' + sys.executable + '" -B "%~dp0knowledge-dispatch.py" %*\r\nexit /b %errorlevel%\r\n'
    else:
        launcher = destination / "knowledge"
        command = "#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' -B "$(dirname -- "$0")/knowledge-dispatch.py" "$@"\n'
    payload = {dispatcher: dispatch.encode("utf-8"), launcher: command.encode("utf-8")}
    for path in payload:
        if path.exists() or path.is_symlink():
            raise CommandError("COMMAND_EXISTS", "Existing command files are preserved: " + str(path))
    for path, raw in payload.items():
        with path.open("xb") as stream:
            stream.write(raw)
    if os.name != "nt":
        launcher.chmod(0o755)
    if args.add_path:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            if str(destination).casefold() not in {p.rstrip("\\/").casefold() for p in current.split(";")}:
                winreg.SetValueEx(key, "Path", 0, kind, current.rstrip(";") + (";" if current else "") + str(destination))
    return envelope("ok", "command_installed", {"command": str(launcher), "bin_dir": str(destination),
                    "path_registered": args.add_path, "next_step": "Open a new terminal with this directory on PATH"}), 0


def emit(value, as_json):
    if as_json:
        print(canonical(value).decode("utf-8"))
    else:
        print(value.get("status", "unknown") + ": " + value.get("phase", value.get("status", "unknown")))
        for diagnostic in value.get("diagnostics", value.get("findings", [])):
            print(str(diagnostic.get("code", "")) + ": " + str(diagnostic.get("message", diagnostic.get("reason", ""))))
        print(json.dumps(value.get("data", {}), ensure_ascii=False, indent=2))
        for name, reference in value.get("cli_transport", {}).items():
            if name in {"request_ref", "result_ref", "knowledge_root"}:
                print(name + ": " + str(reference))


def main(argv=None, *, knowledge_root=None, manifest=None):
    root = Path(knowledge_root).resolve(strict=True)
    selected_root = root
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = None
    try:
        args = parser().parse_intermixed_args(arguments)
        if args.knowledge_root:
            selected_root = Path(os.path.abspath(args.knowledge_root))
            target = selected_root.resolve(strict=True)
            if target != root:
                entry = target / "knowledge.py"
                if not entry.is_file():
                    raise CommandError("KNOWLEDGE_ROOT_UNAVAILABLE", "The selected knowledge root has no repository CLI")
                return subprocess.call([sys.executable, "-B", str(entry), *arguments])
        if args.legacy_transport:
            if args.command not in STAGES or args.arguments:
                raise CommandError("INVALID_ARGUMENT", "Legacy transport requires one existing stage")
            from .stage_dispatch import run_stage
            forwarded = list(arguments)
            forwarded.remove(args.command)
            forwarded.remove("--legacy-transport")
            # This is a development compatibility seam only. It keeps the old
            # stage's exact ownership, retries and ASCII lint stdout contract.
            return run_stage(args.command, forwarded)
        if args.command == "doctor":
            if args.arguments or args.input or args.action:
                raise CommandError("INVALID_ACTION", "doctor accepts no business request or action")
            value, code = doctor(root, manifest)
        elif args.command == "install-command":
            value, code = install_command(args, root)
        else:
            value, code = execute(args, root)
        emit(value, args.json)
        return code
    except Exception as error:
        value = envelope("error", "invalid", diagnostics=[{"code": getattr(error, "code", "INVALID_INPUT"), "message": str(error)}])
        if args and args.output:
            try:
                output = safe_output(root, args.output, args.operation_id)
                if selected_root != root and (
                    output.is_relative_to(selected_root)
                    or output.is_relative_to(selected_root.resolve(strict=False))
                ):
                    raise CommandError("OUTPUT_ROOT_UNAVAILABLE", "An unavailable target cannot own a diagnostic file")
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    stream.write(canonical(value))
            except (OSError, CommandError):
                pass
        emit(value, args.json if args else "--json" in arguments)
        return 2
