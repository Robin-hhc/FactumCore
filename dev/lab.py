#!/usr/bin/env python3
"""Manage reusable test resources and owned acceptance runs; never sweep old data."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from uuid import uuid4

SOURCE = Path(__file__).resolve().parents[1]
REQUIREMENTS = SOURCE / "himate/himate-tools/runtime/requirements.lock.txt"
RUNNER = SOURCE / "himate/himate-tools/evals/run_acceptance.py"
SCHEMA = 1
DIRECTORIES = ("envs", "fixtures", "hosts", "runs", "reports")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def no_links(path):
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked managed paths are not accepted: " + str(part))


def json_write(path, value):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main_repository():
    try:
        common = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "--git-common-dir"],
                                         text=True, stderr=subprocess.DEVNULL).strip()
        directory = Path(common)
        return (SOURCE / directory if not directory.is_absolute() else directory).resolve().parent
    except (OSError, subprocess.CalledProcessError):
        return SOURCE


def root_path(value):
    raw = value or os.environ.get("FACTUM_TEST_ROOT")
    root = Path(raw) if raw else main_repository().with_name(main_repository().name + "-Test")
    if not root.is_absolute():
        raise ValueError("Test root must be an absolute path")
    root = Path(os.path.abspath(root))
    if root == Path(root.anchor) or root == main_repository() or root in main_repository().parents:
        raise ValueError("Test root must be separate from the source root and its ancestors")
    no_links(root)
    return root


def load_lab(root):
    no_links(root / "lab.json")
    data = json.loads((root / "lab.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA or not data.get("owner_id"):
        raise ValueError("Unrecognized lab registry")
    if Path(data.get("project_root", "")).resolve() != main_repository():
        raise ValueError("Lab belongs to another project")
    for name in DIRECTORIES:
        no_links(root / name)
    return data


@contextmanager
def registry_lock(root):
    path = root / ".lab.lock"
    no_links(path)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError("Lab registry is being updated; inspect .lab.lock if its owner exited") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


def initialize(root):
    root.mkdir(parents=True, exist_ok=True)
    with registry_lock(root):
        if (root / "lab.json").exists():
            return load_lab(root)
        for name in DIRECTORIES:
            no_links(root / name)
            (root / name).mkdir(exist_ok=True)
        data = {"schema_version": SCHEMA, "owner_id": uuid4().hex,
                "project_root": str(main_repository()), "resources": {}, "defaults": {}}
        json_write(root / "lab.json", data)
        return data


def python_environment():
    # Use the same import/home/site selection for probes and acceptance children.
    selectors = {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONNOUSERSITE", "PYTHONSAFEPATH",
                 "PYTHONSTARTUP", "PYTHONPLATLIBDIR", "PYTHONEXECUTABLE", "PYTHONCASEOK",
                 "__PYVENV_LAUNCHER__", "_PYTHON_SYSCONFIGDATA_NAME", "_PYTHON_PROJECT_BASE"}
    return {**{key: value for key, value in os.environ.items() if key.upper() not in selectors},
            "PYTHONDONTWRITEBYTECODE": "1"}


def run_json(command, environment=None):
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=45,
                               env=environment)
    if completed.returncode:
        raise ValueError("Resource probe failed: " + completed.stderr.strip()[-700:])
    return json.loads(completed.stdout)


def probe_python(executable):
    code = """
import importlib.metadata, json, pathlib, platform, sys
from packaging.requirements import Requirement
issues=[]
for line in pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    line=line.strip()
    if not line or line.startswith('#'): continue
    requirement=Requirement(line)
    if requirement.marker and not requirement.marker.evaluate(): continue
    try: actual=importlib.metadata.version(requirement.name)
    except importlib.metadata.PackageNotFoundError: actual=None
    if actual is None or not requirement.specifier.contains(actual, prereleases=True):
        issues.append({'package':requirement.name,'actual':actual,'expected':str(requirement.specifier)})
paths=sorted({str(pathlib.Path(p).resolve()) for p in [sys.prefix,sys.base_prefix,*sys.path]
              if p and pathlib.Path(p).is_absolute() and pathlib.Path(p).exists()})
print(json.dumps({'version':platform.python_version(),'platform':sys.platform,'arch':platform.machine(),
                  'prefix':sys.prefix,'base_prefix':sys.base_prefix,'external_paths':paths,'issues':issues}))
"""
    data = run_json([str(executable), "-B", "-c", code, str(REQUIREMENTS)], python_environment())
    if tuple(map(int, data["version"].split(".")[:2])) not in [(3, 10), (3, 11), (3, 12)]:
        raise ValueError("Prepared Python must be 3.10, 3.11 or 3.12")
    if data["issues"]:
        raise ValueError("Python does not satisfy requirements lock: " + json.dumps(data["issues"]))
    return {**data, "kind": "python", "executable": str(executable),
            "requirements_sha256": digest(REQUIREMENTS), "owned": False, "read_only": True}


def probe_node(site, executable):
    lock = json.loads((site / "package-lock.json").read_text(encoding="utf-8"))
    package = json.loads((site / "package.json").read_text(encoding="utf-8"))
    modules = (site / "node_modules").resolve(strict=True)
    for name in {**package.get("dependencies", {}), **package.get("devDependencies", {})}:
        expected = lock.get("packages", {}).get("node_modules/" + name, {}).get("version")
        installed = modules / name / "package.json"
        if not expected or not installed.is_file() or json.loads(installed.read_text(encoding="utf-8")).get("version") != expected:
            raise ValueError("Node dependencies do not match package-lock: " + name)
    installed_lock = modules / ".package-lock.json"
    installed_packages = json.loads(installed_lock.read_text(encoding="utf-8")).get("packages", {})
    if not installed_packages:
        raise ValueError("Node installation lock is missing or empty")
    for name, installed in installed_packages.items():
        expected = lock.get("packages", {}).get(name)
        if expected is None or installed.get("version") != expected.get("version") or (
                installed.get("integrity") and expected.get("integrity") and installed["integrity"] != expected["integrity"]):
            raise ValueError("Node installation lock differs from source package-lock: " + name)
    data = run_json([str(executable), "-p", "JSON.stringify({version:process.version,abi:process.versions.modules,platform:process.platform,arch:process.arch})"])
    return {**data, "kind": "node", "executable": str(executable), "site": str(site),
            "node_modules": str(modules), "package_lock_sha256": digest(site / "package-lock.json"),
            "installed_lock_sha256": digest(installed_lock),
            "owned": False, "read_only": True}


def register(root, resource, make_default):
    lock = resource.get("requirements_sha256") or resource["package_lock_sha256"]
    identity = "-".join([resource["kind"], resource["platform"], resource["arch"], resource["version"], lock[:12]])
    with registry_lock(root):
        data = load_lab(root)
        previous = data["resources"].get(identity)
        if previous and any(previous[k] != value for k, value in resource.items() if k in previous):
            raise ValueError("Resource key already describes a different path; keep existing resources stable")
        data["resources"][identity] = resource
        if make_default or resource["kind"] not in data["defaults"]:
            data["defaults"][resource["kind"]] = identity
        json_write(root / "lab.json", data)
    return {"resource_id": identity, **resource}


def checked_id(value):
    if not RUN_ID.fullmatch(value):
        raise ValueError("Run id must be one safe directory name (letters/digits, dot, dash or underscore)")
    return value


def run_paths(root, identity):
    identity = checked_id(identity)
    run, report = root / "runs" / identity, root / "reports" / identity
    no_links(run)
    no_links(report)
    return run, report


def read_run(root, data, identity):
    run, report = run_paths(root, identity)
    no_links(run / "run.json")
    manifest = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA or manifest.get("owner_id") != data["owner_id"] or manifest.get("run_id") != identity:
        raise ValueError("Run ownership is not verified")
    if manifest.get("run_dir") != str(run) or manifest.get("report_dir") != str(report):
        raise ValueError("Run paths differ from the managed layout")
    return run, report, manifest


def code_revision():
    head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(SOURCE), "status", "--porcelain=v1"], text=True).splitlines()
    return {"head": head, "worktree_status": status, "runner_sha256": digest(RUNNER)}


def accept(root, args):
    data = load_lab(root)
    key = args.python or data["defaults"].get("python")
    resource = data["resources"].get(key, {})
    if resource.get("kind") != "python" or resource.get("requirements_sha256") != digest(REQUIREMENTS):
        raise ValueError("Register a prepared Python for the current requirements lock first")
    current = probe_python(Path(resource["executable"]))
    if any(current.get(k) != resource.get(k) for k in ["version", "platform", "arch", "external_paths"]):
        raise ValueError("Registered Python environment changed; register a new resource")
    identity = args.run or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    run, report = run_paths(root, identity)
    if run.exists() or report.exists():
        raise ValueError("Run id already exists; existing evidence is retained")
    run.mkdir()
    manifest = {"schema_version": SCHEMA, "owner_id": data["owner_id"], "run_id": identity,
                "run_dir": str(run), "report_dir": str(report), "status": "running", "pid": os.getpid(),
                "pinned": args.keep_temp, "resource_id": key, "resource": resource,
                "code_revision": code_revision(), "created_at": datetime.now(timezone.utc).isoformat()}
    json_write(run / "run.json", manifest)
    command = [resource["executable"], str(RUNNER), "--output-dir", str(report), "--temp-dir", str(run / "work"),
               "--cleanup-temp", "never" if args.keep_temp else "on-success", "--profile", args.profile, "--jobs", str(args.jobs)]
    for name in ["baseline", "capabilities_root"]:
        if getattr(args, name): command += ["--" + name.replace("_", "-"), str(getattr(args, name))]
    if args.groups: command += ["--groups", *args.groups]
    code, error, summary = 2, None, {}
    try:
        code = subprocess.run(command, cwd=SOURCE, env=python_environment()).returncode
        summary = json.loads((report / "summary.json").read_text(encoding="utf-8"))
        if not isinstance(summary.get("passed"), bool) or "storage" not in summary:
            raise ValueError("Runner did not produce a managed storage result")
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        code, error = 2, str(exc) or "Run interrupted"
    finally:
        passed = code == 0 and summary.get("passed") is True
        if not passed and code == 0:
            code = 2
        manifest.update(status="passed" if passed else "failed", pid=None, error=error,
                        process_cleanup_confirmed=error is None and "storage" in summary and not any(
                            g.get("timed_out") or g.get("cleanup_unconfirmed") for g in summary.get("groups", [])),
                        completed_at=datetime.now(timezone.utc).isoformat(), storage=summary.get("storage"))
        report.mkdir(exist_ok=True)
        json_write(run / "run.json", manifest)
        json_write(report / "environment.json", manifest)
    return code


def windows_process_api():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel, ctypes.get_last_error


def windows_pid_alive(pid):
    import ctypes
    from ctypes import wintypes
    kernel, last_error = windows_process_api()
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return last_error() != 87  # ERROR_INVALID_PARAMETER means no such process; otherwise retain.
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


def pid_alive(pid):
    if pid is None: return False
    try:
        pid = int(pid)
        if pid <= 0 or pid > 0xFFFFFFFF: return True
        if os.name == "nt": return windows_pid_alive(pid)
        os.kill(pid, 0)
        return True
    except (TypeError, ValueError):
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def pin_run(root, identity, release):
    with registry_lock(root):
        data = load_lab(root)
        run, report, row = read_run(root, data, identity)
        if row.get("status") == "running" or pid_alive(row.get("pid")):
            raise ValueError("Use run --keep-temp before launch; running runs cannot be pinned or released")
        row["pinned"] = not release
        json_write(run / "run.json", row)
        if report.exists(): json_write(report / "environment.json", row)
        return {"run_id": identity, "pinned": row["pinned"]}


def clean(root, identity, apply):
    with registry_lock(root):
        return clean_owned_run(root, identity, apply)


def clean_owned_run(root, identity, apply):
    data = load_lab(root)
    run, report, manifest = read_run(root, data, identity)
    if manifest.get("pinned") or manifest.get("status") == "running" or pid_alive(manifest.get("pid")):
        raise ValueError("Pinned or active runs cannot be cleaned")
    if not manifest.get("process_cleanup_confirmed"):
        raise ValueError("Process cleanup was not confirmed; inspect this run manually")
    for resource in data["resources"].values():
        paths = [resource.get(k) for k in ["executable", "node_modules", "site", "prefix", "base_prefix"]]
        paths += resource.get("external_paths", [])
        for value in filter(None, paths):
            path = Path(value).resolve()
            if path == run or run in path.parents or path in run.parents:
                raise ValueError("Run overlaps a registered resource; resources are never cleanup targets")
    todo, total = [run], 0
    while todo:
        directory = todo.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                no_links(Path(entry.path))
                if entry.is_dir(follow_symlinks=False): todo.append(Path(entry.path))
                else: total += entry.stat(follow_symlinks=False).st_size
    result = {"run_id": identity, "path": str(run), "bytes": total, "applied": apply, "report_retained": str(report)}
    if apply:
        report.mkdir(exist_ok=True)
        json_write(report / "cleanup.json", result)
        shutil.rmtree(run)
    return result


def status(root):
    data = load_lab(root)
    runs = []
    unmanaged = 0
    for path in sorted((root / "runs").iterdir()):
        try:
            no_links(path / "run.json")
            if not path.is_dir() or not (path / "run.json").is_file():
                unmanaged += 1
                continue
            row = json.loads((path / "run.json").read_text(encoding="utf-8"))
            if not isinstance(row, dict) or row.get("owner_id") != data["owner_id"]:
                unmanaged += 1
                continue
            _, _, row = read_run(root, data, path.name)
            runs.append({k: row.get(k) for k in ["run_id", "status", "pinned", "resource_id"]})
        except (OSError, ValueError):
            unmanaged += 1
    disk = shutil.disk_usage(root)
    hosts = []
    for directory in sorted((root / "hosts").iterdir()):
        configuration = directory / "launch.json"
        try:
            no_links(configuration)
            if not configuration.is_file(): continue
            host = json.loads(configuration.read_text(encoding="utf-8"))
            if isinstance(host, dict) and host.get("schemaVersion") == 1:
                hosts.append({"name": directory.name, "configuration": str(configuration),
                              "port": host.get("port"), "pinned": host.get("pinned", False)})
        except (OSError, ValueError):
            continue
    return {"root": str(root), "project_root": data["project_root"], "resources": data["resources"],
            "defaults": data["defaults"], "runs": runs, "hosts": hosts, "unmanaged_run_entries": unmanaged, "free_bytes": disk.free,
            "directories": {name: str(root / name) for name in DIRECTORIES}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Absolute test root, or FACTUM_TEST_ROOT; default is the main repository's sibling")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("status")
    python = commands.add_parser("register-python")
    python.add_argument("--executable", type=Path, required=True)
    python.add_argument("--default", action="store_true")
    node = commands.add_parser("register-node")
    node.add_argument("--site", type=Path, required=True)
    node.add_argument("--executable", type=Path)
    node.add_argument("--default", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("--run")
    run.add_argument("--python", help="Registered resource id; default uses the default Python")
    run.add_argument("--groups", nargs="+")
    run.add_argument("--profile", choices=("quick", "full"), default="full")
    run.add_argument("--jobs", type=int, choices=(1, 2, 3), default=3)
    run.add_argument("--baseline", type=Path)
    run.add_argument("--capabilities-root", type=Path)
    run.add_argument("--keep-temp", action="store_true")
    cleanup = commands.add_parser("clean")
    cleanup.add_argument("--run", required=True)
    cleanup.add_argument("--apply", action="store_true")
    pin = commands.add_parser("pin")
    pin.add_argument("--run", required=True)
    pin.add_argument("--release", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = root_path(args.root)
        if args.command == "init": result = initialize(root)
        elif args.command == "status": result = status(root)
        elif args.command == "register-python":
            if not args.executable.is_absolute(): raise ValueError("Python executable must be absolute")
            result = register(root, probe_python(args.executable.resolve(strict=True)), args.default)
        elif args.command == "register-node":
            executable = args.executable or Path(shutil.which("node") or "")
            if not args.site.is_absolute() or not executable.is_absolute(): raise ValueError("Node site and executable must be absolute")
            result = register(root, probe_node(args.site.resolve(strict=True), executable.resolve(strict=True)), args.default)
        elif args.command == "run": return accept(root, args)
        elif args.command == "clean": result = clean(root, args.run, args.apply)
        else: result = pin_run(root, args.run, args.release)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
