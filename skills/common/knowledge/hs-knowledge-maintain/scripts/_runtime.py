"""Development-only compatibility; installed Skills carry no executable code."""
from pathlib import Path
import hashlib
import importlib
import json
import os
import runpy
import sys


def knowledge_root(script, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = None
    for index, value in enumerate(argv):
        if value == "--knowledge-root" and index + 1 < len(argv):
            explicit = argv[index + 1]
        elif value.startswith("--knowledge-root="):
            explicit = value.split("=", 1)[1]
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if (root / "knowledge.py").is_file():
            return root
        raise RuntimeError("Target knowledge root has no repository CLI; deploy the matching runtime first")
    for ancestor in Path(script).resolve().parents:
        if (ancestor / "knowledge.py").is_file() and (ancestor / "runtime/himate_knowledge").is_dir():
            return ancestor
        root = ancestor / "himate-knowledge-wifi-mp"
        if (root / "knowledge.py").is_file() and (root / "runtime/himate_knowledge").is_dir():
            return root
    raise RuntimeError("Repository knowledge CLI not found; call the actual knowledge root's knowledge.py")


def expose(script, namespace, stage, module):
    root = knowledge_root(script)
    sys.path.insert(0, str(root / "runtime"))
    actual = importlib.import_module("himate_knowledge.stages." + stage + "." + module)
    namespace.update({key: value for key, value in vars(actual).items() if key not in {"__name__", "__file__", "__spec__", "__loader__", "__package__"}})
    sys.modules[namespace["__name__"]] = actual
    return actual


def _argument(argv, name):
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith(name + "="):
            return value.split("=", 1)[1]
    return None


def _external_diagnostic_output(argv):
    """A bootstrap diagnostic may create only a fresh, non-knowledge file."""
    requested = _argument(argv, "--knowledge-root")
    destination = _argument(argv, "--output")
    if not requested or not destination:
        return None
    root = Path(requested).expanduser().resolve()
    output = Path(destination).expanduser().absolute()
    if os.path.lexists(output):
        return None
    for path in (output, *output.parents):
        if path.is_symlink() or (os.path.lexists(path) and
                getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
            return None
    if output.resolve().is_relative_to(root):
        return None
    for parent in output.parents:
        if ((parent / "knowledge.py").is_file()
                or (parent / "governance/framework.lock.yaml").is_file()):
            return None
    return output


def _unavailable(error, argv, stage):
    if stage == "lint" and _argument(argv, "--action") in {None, "lint", "run", "check"}:
        report = {
            "report_version": "1.0", "status": "incomplete", "phase": "incomplete",
            "exit_code": 2, "complete": False, "rules_digest": _argument(argv, "--rules-digest"),
            "checks": [], "findings": [{"code": "LINT_UNAVAILABLE", "severity": "error", "reason": str(error)}],
        }
        # Independent formal lint has always returned this unavailable report
        # only on stdout. Do not publish a report file without its real checks.
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        raise SystemExit(2)
    record = {
        "schema_version": "2.0", "record_kind": "result", "status": "error",
        "phase": "invalid", "data": {},
        "rules_digest": _argument(argv, "--rules-digest"),
        "diagnostics": [{"code": "KNOWLEDGE_RUNTIME_UNAVAILABLE", "message": str(error)}],
    }
    record["digest"] = hashlib.sha256(json.dumps(
        record, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    raw = json.dumps(record, ensure_ascii=True, sort_keys=True)
    try:
        output = _external_diagnostic_output(argv)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if _external_diagnostic_output(argv) is not None:
                with output.open("xb") as stream:
                    stream.write(raw.encode("ascii"))
    except (OSError, ValueError):
        # stdout remains the diagnostic when there is no safe output target.
        pass
    print(raw)
    raise SystemExit(2)


def run_legacy(script, stage):
    original = list(sys.argv[1:])
    try:
        root = knowledge_root(script, original)
    except (OSError, RuntimeError, ValueError) as error:
        _unavailable(error, original, stage)
    sys.argv = [str(root / "knowledge.py"), stage, "--legacy-transport", *sys.argv[1:]]
    runpy.run_path(str(root / "knowledge.py"), run_name="__main__")
