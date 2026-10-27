"""Run a registered public node locally or through an explicit Linux SSH profile.

Profiles are trusted deployment data, separate from project/source material.
Transport failures never trigger automatic retries or changes of execution host.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import uuid


class ExecutionError(ValueError):
    def __init__(self, code, *, blocked=False):
        super().__init__(code)
        self.code, self.blocked = code, blocked


def require_native_storage(value):
    """Reject Windows network paths before any filesystem inspection."""
    if not isinstance(value, str):
        raise ExecutionError("INVALID_EXECUTION_PATH")
    windows = value.replace("/", "\\")
    if windows.startswith("\\\\") and not re.match(r"^\\\\\?\\[A-Za-z]:\\", windows):
        raise ExecutionError("REMOTE_FILESYSTEM_REQUIRES_SSH")
    if os.name == "nt":
        root = PureWindowsPath(os.path.abspath(value)).anchor
        try:
            classify = ctypes.windll.kernel32.GetDriveTypeW
            classify.argtypes, classify.restype = [ctypes.c_wchar_p], ctypes.c_uint
            kind = classify(root)
        except (OSError, AttributeError, ValueError) as exc:
            raise ExecutionError("EXECUTION_STORAGE_TYPE_UNAVAILABLE") from exc
        if kind == 4:  # DRIVE_REMOTE
            raise ExecutionError("REMOTE_FILESYSTEM_REQUIRES_SSH")
        if kind not in (2, 3, 5, 6):
            raise ExecutionError("EXECUTION_STORAGE_TYPE_UNAVAILABLE")
        # Inspect from the volume root, so a local junction cannot cause the
        # next child inspection to traverse a remote directory first.
        path = Path(os.path.abspath(value))
        for part in (*reversed(path.parents), path):
            try:
                metadata = part.lstat()
            except FileNotFoundError:
                break
            if getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ExecutionError("INVALID_EXECUTION_PATH")


# Refuse a network bootstrap before loading its sibling implementation.
try:
    for _runtime_path in (__file__, sys.executable, sys.prefix, sys.base_prefix):
        require_native_storage(_runtime_path)
    _helper_path = Path(__file__).with_name("install_catalog.py")
    require_native_storage(str(_helper_path))
except ExecutionError as _bootstrap_error:
    if __name__ == "__main__":
        sys.stderr.write(_bootstrap_error.code + "\n")
        raise SystemExit(2)
    raise
_spec = importlib.util.spec_from_file_location("execution_install_catalog", _helper_path)
_installer = importlib.util.module_from_spec(_spec)
exec(compile(Path(_spec.origin).read_bytes(), _spec.origin, "exec"), _installer.__dict__)


def require_native_catalog(catalog):
    """A local entry must keep child CLI and registered-project I/O local too."""
    if (not isinstance(catalog, dict) or not isinstance(catalog.get("skills"), dict)
            or not isinstance(catalog.get("workspaces", {}), dict)):
        raise ExecutionError("INVALID_CATALOG")
    for row in catalog.get("skills", {}).values():
        if isinstance(row, dict):
            for key in ("root", "python"):
                if key in row:
                    require_native_storage(row[key])
                    if not Path(row[key]).is_absolute():
                        raise ExecutionError("INVALID_EXECUTION_PATH")
    for row in catalog.get("workspaces", {}).values():
        if isinstance(row, dict) and "config" in row:
            require_native_storage(row["config"])
            if not Path(row["config"]).is_absolute():
                raise ExecutionError("INVALID_EXECUTION_PATH")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ExecutionError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(_):
        raise ExecutionError("NONFINITE_JSON_VALUE")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)


def pinned(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def absolute(value, *, exists=True):
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        raise ExecutionError("INVALID_EXECUTION_PATH")
    require_native_storage(value)
    try:
        return _installer.absolute(value, exists=exists)
    except (OSError, ValueError) as exc:
        raise ExecutionError("INVALID_EXECUTION_PATH") from exc


def caller_path(value, *, exists=True):
    require_native_storage(str(value))
    return absolute(str(Path(value).expanduser().absolute()), exists=exists)


ENV_KEYS = {"EXECUTION_MODE", "PROJECT_ROOT", "CATALOG", "KNOWLEDGE_ROOT", "RULES_DIGEST",
            "SSH_HOST", "SSH_USER", "SSH_PORT", "SSH_IDENTITY_FILE", "REMOTE_PROJECT_ROOT",
            "REMOTE_CATALOG", "REMOTE_PYTHON", "EXPECTED_CATALOG"}


def parse_config_env(raw):
    """Parse an explicitly selected data file; never source/eval or expand it."""
    values = {}
    for line in raw.decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if (not separator or key not in ENV_KEYS or key in values
                or any(token in value for token in ("$(", "${", "`"))
                or any(ord(char) < 32 for char in value)):
            raise ExecutionError("INVALID_CONFIG_ENV_DATA")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0] or value[0] in value[1:-1]:
                raise ExecutionError("INVALID_CONFIG_ENV_QUOTING")
            value = value[1:-1]
        values[key] = value
    return values


def registered_workspace(catalog, workspace, *, posix=False):
    path = PurePosixPath(workspace) if posix else Path(workspace)
    expected = str(path / "config.yml")
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "2.0":
        raise ExecutionError("INVALID_CATALOG")
    entries = catalog.get("workspaces", {})
    if not isinstance(entries, dict):
        raise ExecutionError("INVALID_CATALOG")
    matches = [row for row in entries.values() if isinstance(row, dict) and row.get("config") == expected]
    if len(matches) != 1 or not pinned(matches[0].get("rules_digest")):
        raise ExecutionError("REGISTERED_PROJECT_REQUIRED")
    return matches[0]


def catalog_python(catalog, skill=None):
    skills = catalog.get("skills")
    if not isinstance(skills, dict):
        raise ExecutionError("INVALID_CATALOG")
    entries = [catalog_entry(catalog, skill)] if skill else [row for row in skills.values()
        if isinstance(row, dict) and row.get("entry") == "scripts/cli.py"]
    values = {row.get("python") for row in entries}
    if len(values) != 1 or not isinstance(next(iter(values), None), str):
        raise ExecutionError("EXPLICIT_REMOTE_PYTHON_REQUIRED")
    return next(iter(values))


def registered_local_profile(workspace, catalog_path, rules_digest=None, *, skill=None, expected_catalog_digest=None):
    workspace, catalog_path = absolute(str(workspace)), absolute(str(catalog_path))
    catalog_bytes = catalog_path.read_bytes()
    if expected_catalog_digest is not None and sha(catalog_bytes) != expected_catalog_digest:
        raise ExecutionError("CATALOG_CHANGED")
    catalog = strict_json(catalog_bytes)
    require_native_catalog(catalog)
    registered = registered_workspace(catalog, str(workspace))
    expected_rules = registered["rules_digest"]
    if rules_digest is not None and rules_digest != expected_rules:
        raise ExecutionError("REGISTERED_RULES_MISMATCH")
    config = absolute(str(workspace / "config.yml"))
    before = config.read_bytes()
    value = _installer.parse_yaml_data(absolute(catalog_python(catalog, skill)),
                                       {"config": before.decode("utf-8")})["config"]
    roots = value.get("knowledge_roots") if isinstance(value, dict) else None
    if not isinstance(value, dict) or value.get("schema_version") != "2.0" or not isinstance(roots, dict) or set(roots) != {"wifi"}:
        raise ExecutionError("INVALID_WORKSPACE_MAPPING")
    relative = roots["wifi"]
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or relative.startswith("/") or str(PurePosixPath(relative)) != relative
            or any(part in {".", ".."} for part in relative.split("/"))):
        raise ExecutionError("INVALID_WORKSPACE_MAPPING")
    root = absolute(str(workspace.joinpath(*PurePosixPath(relative).parts)))
    if not root.is_relative_to(workspace):
        raise ExecutionError("INVALID_WORKSPACE_MAPPING")
    lock = absolute(str(root / "governance/framework.lock.yaml"))
    if sha(lock.read_bytes()) != expected_rules:
        raise ExecutionError("REGISTERED_RULES_MISMATCH")
    if catalog_path.read_bytes() != catalog_bytes or config.read_bytes() != before:
        raise ExecutionError("EXECUTION_CONFIGURATION_CHANGED")
    return {"schema_version": "1.0", "mode": "local", "knowledge_root": str(root),
            "catalog": str(catalog_path), "rules_digest": expected_rules}


def load_configuration(path, *, config_env=False, skill=None):
    path = caller_path(path)
    raw = path.read_bytes()
    if not config_env:
        return validate_profile(strict_json(raw))
    values = parse_config_env(raw)

    def local_path(key):
        value = values.get(key, "")
        if not value:
            raise ExecutionError("CONFIG_ENV_FIELD_REQUIRED")
        require_native_storage(value)
        file = Path(value).expanduser()
        return absolute(str(file if file.is_absolute() else path.parent / file))

    rules = values.get("RULES_DIGEST") or None
    if rules is not None and not pinned(rules):
        raise ExecutionError("INVALID_RULES_DIGEST")
    mode = values.get("EXECUTION_MODE")
    if mode == "local":
        if set(values) - {"EXECUTION_MODE", "PROJECT_ROOT", "CATALOG", "KNOWLEDGE_ROOT", "RULES_DIGEST"}:
            raise ExecutionError("CONFIG_ENV_MODE_FIELDS")
        profile = registered_local_profile(local_path("PROJECT_ROOT"), local_path("CATALOG"), rules, skill=skill)
        if values.get("KNOWLEDGE_ROOT") and str(local_path("KNOWLEDGE_ROOT")) != profile["knowledge_root"]:
            raise ExecutionError("REGISTERED_KNOWLEDGE_ROOT_MISMATCH")
    elif mode == "ssh":
        if set(values) & {"PROJECT_ROOT", "CATALOG", "KNOWLEDGE_ROOT"}:
            raise ExecutionError("CONFIG_ENV_MODE_FIELDS")
        expected_catalog = local_path("EXPECTED_CATALOG")
        catalog = strict_json(expected_catalog.read_bytes())
        workspace = values.get("REMOTE_PROJECT_ROOT", "")
        registered = registered_workspace(catalog, workspace, posix=True)
        if rules is not None and rules != registered["rules_digest"]:
            raise ExecutionError("REGISTERED_RULES_MISMATCH")
        target = values.get("SSH_HOST", "")
        if values.get("SSH_USER"):
            target = values["SSH_USER"] + "@" + target
        # This is a trusted launcher, which may drop privileges before Python.
        # The actual public node interpreter still comes from the pinned catalog.
        python = values.get("REMOTE_PYTHON") or catalog_python(catalog, skill)
        profile = {"schema_version": "1.0", "mode": "ssh", "target": target,
                   "remote_workspace": workspace, "remote_catalog": values.get("REMOTE_CATALOG", ""),
                   "remote_python": python,
                   "expected_catalog": str(expected_catalog), "rules_digest": registered["rules_digest"]}
        if values.get("SSH_PORT"):
            if not values["SSH_PORT"].isascii() or not values["SSH_PORT"].isdigit():
                raise ExecutionError("INVALID_SSH_PORT")
            profile["port"] = int(values["SSH_PORT"])
        if values.get("SSH_IDENTITY_FILE"):
            profile["identity_file"] = str(local_path("SSH_IDENTITY_FILE"))
    else:
        raise ExecutionError("INVALID_EXECUTION_MODE")
    if path.read_bytes() != raw:
        raise ExecutionError("EXECUTION_CONFIGURATION_CHANGED")
    return validate_profile(profile)


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("schema_version") != "1.0":
        raise ExecutionError("INVALID_EXECUTION_PROFILE")
    common = {"schema_version", "mode", "rules_digest"}
    local = common | {"knowledge_root", "catalog"}
    remote = common | {"target", "remote_python", "expected_catalog"} | (
        {"remote_workspace", "remote_catalog"} if "remote_workspace" in profile else
        {"remote_runner", "remote_profile", "remote_profile_digest"})
    mode = profile.get("mode")
    expected = local if mode == "local" else remote if mode == "ssh" else set()
    optional = {"port", "identity_file"} if mode == "ssh" else set()
    if set(profile) - optional != expected or not pinned(profile.get("rules_digest")):
        raise ExecutionError("INVALID_EXECUTION_PROFILE")
    if mode == "local":
        absolute(profile["knowledge_root"])
        absolute(profile["catalog"])
    else:
        if not isinstance(profile.get("target"), str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:@[A-Za-z0-9][A-Za-z0-9_.-]*)?", profile["target"]):
            raise ExecutionError("INVALID_SSH_TARGET")
        remote_paths = ("remote_python", "remote_workspace", "remote_catalog") if "remote_workspace" in profile else (
            "remote_python", "remote_runner", "remote_profile")
        for key in remote_paths:
            value = profile.get(key)
            if (not isinstance(value, str) or not value.startswith("/")
                    or value.startswith("//") or "\\" in value
                    or ".." in PurePosixPath(value).parts
                    or any(ord(char) < 32 for char in value)):
                raise ExecutionError("INVALID_REMOTE_PATH")
        if "remote_workspace" not in profile and not pinned(profile.get("remote_profile_digest")):
            raise ExecutionError("INVALID_REMOTE_PROFILE_DIGEST")
        if "port" in profile and (type(profile["port"]) is not int or not 1 <= profile["port"] <= 65535):
            raise ExecutionError("INVALID_SSH_PORT")
        if "identity_file" in profile and not absolute(profile["identity_file"]).is_file():
            raise ExecutionError("INVALID_SSH_IDENTITY_FILE")
        absolute(profile["expected_catalog"])
    return profile


def selection(skill, action, request):
    if skill not in _installer.SKILLS:
        raise ExecutionError("UNKNOWN_EXECUTABLE_SKILL")
    if action is not None and (not isinstance(action, str)
                               or not re.fullmatch(r"[a-z][a-z0-9-]*", action)):
        raise ExecutionError("INVALID_NODE_ACTION")
    if not isinstance(request, dict):
        raise ExecutionError("REQUEST_OBJECT_REQUIRED")
    if not isinstance(request.get("operation_id"), str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", request["operation_id"]):
        raise ExecutionError("EXECUTION_OPERATION_ID_REQUIRED")


def catalog_entry(catalog, skill):
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "2.0":
        raise ExecutionError("INVALID_CATALOG")
    entries = catalog.get("skills")
    entry = entries.get(skill) if isinstance(entries, dict) else None
    if (not isinstance(entry, dict) or entry.get("entry") != "scripts/cli.py"
            or not pinned(entry.get("package_digest"))):
        raise ExecutionError("INVALID_CATALOG_ENTRY")
    return entry


def verify_response(response, code, skill, entry, rules_digest, request=None):
    if (not isinstance(response, dict) or response.get("digest") != sha(canonical(
                {key: value for key, value in response.items() if key != "digest"}))
            or response.get("rules_digest") != rules_digest):
        raise ExecutionError("UNVERIFIED_NODE_RESPONSE")
    if request is not None:
        if ("operation_id" in response and response["operation_id"] != request["operation_id"]
                or "request_digest" in response and response["request_digest"] != sha(canonical(request))):
            raise ExecutionError("NODE_REQUEST_BINDING_MISMATCH")
    if skill == "hs-knowledge-lint":
        # The public lint CLI validates governance's complete CheckReport before
        # writing it. Keep that protocol; it has no result/tool_identity fields.
        # The caller has separately checked the exact CLI package before/after.
        checks = response.get("checks")
        if (response.get("report_version") != "1.0" or not isinstance(checks, list)
                or not checks or any(not isinstance(row, dict) or row.get("status") not in
                    {"passed", "failed", "incomplete", "not_applicable"} for row in checks)):
            raise ExecutionError("UNVERIFIED_CHECK_REPORT")
        states = {row["status"] for row in checks}
        status = "failed" if "failed" in states else "incomplete" if "incomplete" in states else "passed"
        if (code not in (0, 1, 2) or response.get("exit_code") != code
                or code != {"passed": 0, "failed": 1, "incomplete": 2}[status]
                or response.get("status") != status or response.get("phase") != status
                or response.get("complete") != ("incomplete" not in states)):
            raise ExecutionError("CHECK_REPORT_EXIT_STATUS_MISMATCH")
        return
    if (response.get("schema_version") != "2.0" or response.get("record_kind") != "result"
            or response.get("tool_identity", {}).get("skill") != skill
            or response.get("tool_identity", {}).get("package_digest") != entry["package_digest"]):
        raise ExecutionError("UNVERIFIED_NODE_RESPONSE")
    if code not in (0, 2, 3) or response.get("status") != {0: "ok", 2: "error", 3: "blocked"}[code]:
        raise ExecutionError("NODE_EXIT_STATUS_MISMATCH")


def execute_local(profile, skill, request, action, *, expected_catalog_digest=None):
    catalog_path = absolute(profile["catalog"])
    catalog_bytes = catalog_path.read_bytes()
    if expected_catalog_digest is not None and sha(catalog_bytes) != expected_catalog_digest:
        raise ExecutionError("CATALOG_CHANGED")
    catalog = strict_json(catalog_bytes)
    require_native_catalog(catalog)
    entry = catalog_entry(catalog, skill)
    package, python = absolute(entry.get("root")), absolute(entry.get("python"))
    if package.name != skill or not python.is_file():
        raise ExecutionError("INVALID_CATALOG_ENTRY")
    expected = entry["package_digest"]

    def package_identity():
        return _installer.package_digest(_installer.package_files(package, runtime_only=True))

    if package_identity() != expected:
        raise ExecutionError("PACKAGE_DIGEST_MISMATCH")
    cli = absolute(str(package / "scripts/cli.py"))
    root = absolute(profile["knowledge_root"])
    directory = root / ".build/operations" / request["operation_id"] / "execution" / uuid.uuid4().hex
    _installer.no_links(directory)
    directory.mkdir(mode=0o700, parents=True)
    _installer.no_links(directory)
    incoming, outgoing = directory / "request.json", directory / "response.json"
    with incoming.open("xb") as stream:
        stream.write(canonical(request))
    command = [str(python), "-B", str(cli), "--input", str(incoming), "--output", str(outgoing),
               "--knowledge-root", str(root), "--rules-digest", profile["rules_digest"],
               "--catalog", str(catalog_path)]
    if action is not None:
        command += ["--action", action]
    completed = subprocess.run(command, capture_output=True, check=False)
    if not outgoing.is_file():
        raise ExecutionError("NODE_RESULT_UNAVAILABLE", blocked=True)
    raw = outgoing.read_bytes()
    verify_response(strict_json(raw), completed.returncode, skill, entry, profile["rules_digest"], request)
    if catalog_path.read_bytes() != catalog_bytes or package_identity() != expected:
        raise ExecutionError("EXECUTION_IDENTITY_CHANGED")
    return completed.returncode, raw


def make_packet(profile, skill, request, action):
    catalog_bytes = absolute(profile["expected_catalog"]).read_bytes()
    catalog_entry(strict_json(catalog_bytes), skill)
    packet = {"schema_version": "1.0", "skill": skill, "action": action, "request": request,
              "catalog_digest": sha(catalog_bytes), "request_digest": sha(canonical(request)),
              "rules_digest": profile["rules_digest"]}
    if "remote_workspace" in profile:
        registered = registered_workspace(strict_json(catalog_bytes), profile["remote_workspace"], posix=True)
        if registered["rules_digest"] != profile["rules_digest"]:
            raise ExecutionError("REGISTERED_RULES_MISMATCH")
        packet["execution_binding"] = {"workspace_root": profile["remote_workspace"],
            "catalog": profile["remote_catalog"], "rules_digest": profile["rules_digest"]}
    else:
        packet["remote_profile_digest"] = profile["remote_profile_digest"]
    return packet


def worker_response(profile, packet, code, raw):
    result = {"schema_version": "1.0", "record_kind": "node_execution", "exit_code": code,
              "skill": packet["skill"], "action": packet["action"],
              "request_digest": packet["request_digest"], "catalog_digest": packet["catalog_digest"],
              "response": strict_json(raw), "tool_identity": {"skill": packet["skill"],
              "package_digest": catalog_entry(strict_json(absolute(profile["catalog"]).read_bytes()),
                                               packet["skill"])["package_digest"]}}
    result.update({key: packet[key] for key in ("remote_profile_digest", "execution_binding") if key in packet})
    result["digest"] = sha(canonical(result))
    return code, canonical(result)


def worker(profile_path, packet):
    profile_bytes = absolute(str(profile_path)).read_bytes()
    if (not isinstance(packet, dict) or set(packet) != {"schema_version", "skill", "action", "request",
            "remote_profile_digest", "catalog_digest", "request_digest", "rules_digest"}
            or packet["schema_version"] != "1.0"):
        raise ExecutionError("INVALID_REMOTE_REQUEST")
    if sha(profile_bytes) != packet["remote_profile_digest"]:
        raise ExecutionError("REMOTE_PROFILE_CHANGED")
    profile = validate_profile(strict_json(profile_bytes))
    if profile["mode"] != "local":
        raise ExecutionError("REMOTE_LOCAL_PROFILE_REQUIRED")
    if profile["rules_digest"] != packet["rules_digest"]:
        raise ExecutionError("REMOTE_RULES_MISMATCH")
    selection(packet["skill"], packet["action"], packet["request"])
    if packet["request_digest"] != sha(canonical(packet["request"])):
        raise ExecutionError("REMOTE_REQUEST_CHANGED")
    code, raw = execute_local(profile, packet["skill"], packet["request"], packet["action"],
                              expected_catalog_digest=packet["catalog_digest"])
    if absolute(str(profile_path)).read_bytes() != profile_bytes:
        raise ExecutionError("REMOTE_PROFILE_CHANGED")
    return worker_response(profile, packet, code, raw)


def workspace_worker(binding, packet):
    if (not isinstance(binding, dict) or set(binding) != {"workspace_root", "catalog", "rules_digest"}
            or not isinstance(packet, dict) or set(packet) != {"schema_version", "skill", "action", "request",
                "execution_binding", "catalog_digest", "request_digest", "rules_digest"}
            or packet.get("schema_version") != "1.0" or packet["execution_binding"] != binding
            or packet["rules_digest"] != binding["rules_digest"]):
        raise ExecutionError("INVALID_WORKSPACE_EXECUTION_BINDING")
    selection(packet["skill"], packet["action"], packet["request"])
    if packet["request_digest"] != sha(canonical(packet["request"])):
        raise ExecutionError("REMOTE_REQUEST_CHANGED")
    config = absolute(str(Path(binding["workspace_root"]) / "config.yml"))
    before = config.read_bytes()
    profile = registered_local_profile(binding["workspace_root"], binding["catalog"], binding["rules_digest"],
                                       skill=packet["skill"], expected_catalog_digest=packet["catalog_digest"])
    code, raw = execute_local(profile, packet["skill"], packet["request"], packet["action"],
                              expected_catalog_digest=packet["catalog_digest"])
    if config.read_bytes() != before:
        raise ExecutionError("EXECUTION_CONFIGURATION_CHANGED")
    return worker_response(profile, packet, code, raw)


WORKSPACE_BOOTSTRAP = """import hashlib,io,json,pathlib,sys,yaml
def require(condition):
    if not condition: raise ValueError('WORKSPACE_BOOTSTRAP_BINDING_INVALID')
class Unique(yaml.SafeLoader): pass
def mapping(loader,node):
    result={}
    for k,v in node.value:
        key=loader.construct_object(k)
        if key in result: raise ValueError('duplicate configuration key')
        result[key]=loader.construct_object(v)
    return result
Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
workspace=pathlib.Path(sys.argv[1]).resolve(strict=True)
config=workspace/'config.yml'
raw=sys.stdin.buffer.read()
packet=json.loads(raw)
catalog_path=pathlib.Path(sys.argv[2]).resolve(strict=True)
catalog_bytes=catalog_path.read_bytes()
require(hashlib.sha256(catalog_bytes).hexdigest()==packet['catalog_digest'])
binding={'workspace_root':str(workspace),'catalog':str(catalog_path),'rules_digest':sys.argv[3]}
require(packet['execution_binding']==binding and packet['rules_digest']==sys.argv[3])
catalog=json.loads(catalog_bytes)
matches=[row for row in catalog.get('workspaces',{}).values() if isinstance(row,dict) and row.get('config')==str(config)]
require(len(matches)==1 and matches[0].get('rules_digest')==sys.argv[3])
value=yaml.load(config.read_bytes(),Loader=Unique)
require(isinstance(value,dict) and value.get('schema_version')=='2.0')
roots=value.get('knowledge_roots')
require(isinstance(roots,dict) and set(roots)=={'wifi'})
relative=roots['wifi']
require(isinstance(relative,str) and relative and not relative.startswith('/') and '\\\\' not in relative and ':' not in relative)
parts=relative.split('/')
require(all(part not in ('','.','..') for part in parts))
runner=workspace.joinpath(*parts,'tools','deploy','run_node.py')
require(runner.resolve(strict=True).is_relative_to(workspace))
require(not any(path.is_symlink() for path in (runner,*runner.parents,config)))
require(hashlib.sha256(workspace.joinpath(*parts,'governance','framework.lock.yaml').read_bytes()).hexdigest()==sys.argv[3])
sys.argv=[str(runner),'--worker','--workspace',str(workspace),'--catalog',sys.argv[2],'--rules-digest',sys.argv[3]]
sys.stdin=io.TextIOWrapper(io.BytesIO(raw),encoding='utf-8')
exec(compile(runner.read_bytes(),str(runner),'exec'),{'__name__':'__main__','__file__':str(runner)})
"""


def dispatch(profile, skill, request, action=None):
    validate_profile(profile)
    selection(skill, action, request)
    if profile["mode"] == "local":
        return execute_local(profile, skill, request, action)
    packet = make_packet(profile, skill, request, action)
    if "remote_workspace" in profile:
        remote_command = shlex.join([profile["remote_python"], "-B", "-c", WORKSPACE_BOOTSTRAP,
            profile["remote_workspace"], profile["remote_catalog"], profile["rules_digest"]])
    else:
        remote_command = shlex.join([profile["remote_python"], "-B", profile["remote_runner"],
                                     "--worker", "--profile", profile["remote_profile"]])
    command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3"]
    if "port" in profile:
        command += ["-p", str(profile["port"])]
    if "identity_file" in profile:
        command += ["-i", profile["identity_file"]]
    command += ["--", profile["target"], remote_command]
    completed = subprocess.run(command, input=canonical(packet), capture_output=True, check=False)
    if completed.returncode not in (0, 1, 2, 3):
        raise ExecutionError("SSH_RESULT_UNAVAILABLE_REMOTE_STATE_UNKNOWN", blocked=True)
    try:
        value = strict_json(completed.stdout)
    except (ValueError, UnicodeError) as exc:
        raise ExecutionError("SSH_RESULT_UNAVAILABLE_REMOTE_STATE_UNKNOWN", blocked=True) from exc
    if (not isinstance(value, dict) or value.get("schema_version") != "1.0"
            or value.get("record_kind") != "node_execution"
            or value.get("skill") != skill or value.get("action") != action
            or value.get("digest") != sha(canonical({key: row for key, row in value.items() if key != "digest"}))
            or any(value.get(key) != packet[key] for key in
                   ("request_digest", "catalog_digest"))
            or any(value.get(key) != packet[key] for key in
                   ("remote_profile_digest", "execution_binding") if key in packet)
            or value.get("exit_code") != completed.returncode):
        raise ExecutionError("UNVERIFIED_SSH_RESULT", blocked=True)
    catalog_bytes = absolute(profile["expected_catalog"]).read_bytes()
    if sha(catalog_bytes) != packet["catalog_digest"]:
        raise ExecutionError("CATALOG_CHANGED")
    entry = catalog_entry(strict_json(catalog_bytes), skill)
    if value.get("tool_identity") != {"skill": skill, "package_digest": entry["package_digest"]}:
        raise ExecutionError("UNVERIFIED_SSH_NODE_IDENTITY", blocked=True)
    verify_response(value.get("response"), completed.returncode, skill, entry, profile["rules_digest"], request)
    return completed.returncode, canonical(value["response"])


def publish_new(path, data):
    require_native_storage(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    _installer.no_links(path)
    descriptor, name = tempfile.mkstemp(prefix=".execution-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def caller_output_boundary(output, profile):
    """Protect caller-side governed data in both local and SSH modes.

    Marker discovery only restricts writes; it never loads candidate rules or
    grants authority. Check every enclosing root, including nested domains.
    """
    require_native_storage(str(output))
    roots = {absolute(profile["knowledge_root"])} if profile["mode"] == "local" else set()
    for ancestor in output.parents:
        marker = ancestor / "governance/framework.lock.yaml"
        if marker.is_file():
            _installer.no_links(marker)
            roots.add(ancestor)
    for root in roots:
        if output.is_relative_to(root):
            parts = output.relative_to(root).parts
            if parts[0] != ".build" and parts[:2] != ("logs", "execution"):
                raise ExecutionError("OUTPUT_OUTSIDE_RUNTIME_AREA")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    configurations = parser.add_mutually_exclusive_group()
    configurations.add_argument("--profile")
    configurations.add_argument("--config-env")
    parser.add_argument("--skill")
    parser.add_argument("--action")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workspace", help=argparse.SUPPRESS)
    parser.add_argument("--catalog", help=argparse.SUPPRESS)
    parser.add_argument("--rules-digest", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    output = None
    publish_errors = False
    try:
        if args.worker:
            if any((args.skill, args.action, args.input, args.output, args.config_env)):
                raise ExecutionError("INVALID_WORKER_ARGUMENTS")
            packet = strict_json(sys.stdin.buffer.read())
            if args.profile and not any((args.workspace, args.catalog, args.rules_digest)):
                code, raw = worker(args.profile, packet)
            elif not args.profile and all((args.workspace, args.catalog, args.rules_digest)):
                code, raw = workspace_worker({"workspace_root": args.workspace, "catalog": args.catalog,
                                               "rules_digest": args.rules_digest}, packet)
            else:
                raise ExecutionError("INVALID_WORKER_ARGUMENTS")
            sys.stdout.buffer.write(raw + b"\n")
            return code
        if any((args.workspace, args.catalog, args.rules_digest)) or not (args.profile or args.config_env):
            raise ExecutionError("EXECUTION_CONFIGURATION_REQUIRED")
        if not args.skill or not args.input or not args.output:
            raise ExecutionError("NODE_ARGUMENTS_REQUIRED")
        output = caller_path(args.output, exists=False)
        if output.exists():
            raise ExecutionError("OUTPUT_EXISTS_USE_UNIQUE_ATTEMPT")
        profile_path = caller_path(args.profile or args.config_env)
        profile_bytes = profile_path.read_bytes()
        profile = load_configuration(profile_path, config_env=bool(args.config_env), skill=args.skill)
        caller_output_boundary(output, profile)
        publish_errors = True
        request = strict_json(caller_path(args.input).read_bytes())
        code, raw = dispatch(profile, args.skill, request, args.action)
        if absolute(str(profile_path)).read_bytes() != profile_bytes:
            raise ExecutionError("CALLER_PROFILE_CHANGED_INSPECT_EXECUTION", blocked=True)
        publish_new(output, raw + b"\n")
        return code
    except (ExecutionError, OSError, ValueError, TypeError, KeyError) as exc:
        code = 3 if getattr(exc, "blocked", False) else 2
        issue = getattr(exc, "code", "EXECUTION_UNAVAILABLE")
        result = {"schema_version": "1.0", "record_kind": "execution_error",
                  "status": "blocked" if code == 3 else "error", "diagnostics": [{"code": issue}],
                  "remote_state": "unknown" if args.worker or issue.startswith("SSH_") else "not_confirmed"}
        result["digest"] = sha(canonical(result))
        if publish_errors and output is not None:
            try:
                require_native_storage(str(output))
                if not output.exists():
                    publish_new(output, canonical(result) + b"\n")
            except (ExecutionError, OSError):
                pass
        sys.stderr.write(issue + "\n")
        return code


if __name__ == "__main__":
    sys.exit(main())
