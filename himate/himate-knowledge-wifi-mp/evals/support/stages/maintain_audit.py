"""Public read-only audit over isolated module files, not real Target QA."""
import hashlib
import json
import subprocess

import yaml

import importlib.util
from pathlib import Path

_fixture_spec = importlib.util.spec_from_file_location("maintain_fixture_helpers", Path(__file__).with_name("maintain.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
operation_context = _fixture.operation_context
public_module = _fixture.public_module

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def hashed(raw):
    return hashlib.sha256(raw).hexdigest()


def code_fixture(harness, usages=("current",), source_bytes=None):
    code = harness.base / "main/shared"
    code.mkdir(parents=True)
    raw = source_bytes if source_bytes is not None else b"int selected_fixture(void) { return 1; }\n"
    (code / "file.c").write_bytes(raw)
    config = {"schema_version": "2.0", "workspace_id": "audit-fixture", "knowledge_roots": {"wifi": harness.root.name},
              "code_root": "main", "modules": [{"path": "shared", "chips": ["chip12"], "sides": ["host"]}]}
    config_path = harness.base / "config.yml"
    config_path.write_bytes(canonical(config))
    repo_id = "repo-" + hashed(b"main/shared")[:16]
    captured = harness.run("source", {"operation_id": "captured", "kind": "code", "repo_id": repo_id,
                                            "relative_path": "file.c", "source_id": "selected-code"}, action="capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    # Establish an explicitly published old-source fixture before registering
    # its formal lock/cards. Capture itself is stage-only; audit must never
    # discover producer-private stage after the working source changes.
    for entry in bundle["staged_objects"]:
        raw_object = (harness.root / entry["stage_ref"]).read_bytes()
        assert hashed(raw_object) == entry["sha256"] and len(raw_object) == entry["bytes"]
        harness.write(entry["final_ref"], raw_object)
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"], "snapshots": bundle["snapshots"]}).encode())
    for usage in usages:
        _, header, body = harness.card("audit-" + usage, bundle, lifecycle="stable").decode().split("---", 2)
        meta = yaml.safe_load(header)
        meta["review_mode"] = "code_gate"
        meta["scope"] = {"applicability": "constrained", "contexts": [{"context_id": "host", "target_id": "chip12-host", "chip": "chip12", "side": "host",
            "build_profile": None, "features_all": [], "features_none": [], "protocol_versions": [], "revision_policy": "revalidate", "revision": None}]}
        meta["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 1}
        meta["sources"][0]["code_ref"] = {"kind": "function", "name": "selected_fixture", "scope": [],
                                           "parameter_types": [], "role": "definition"}
        meta["claims"][0].update(usage=usage, evidence_kind="implementation", context_ids=["host"])
        harness.write("knowledge/rules/audit-" + usage + ".md", ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body).encode())
    checkout = {"configuration": str(config_path), "config_digest": hashed(config_path.read_bytes()), "repos": {repo_id: {"root": str(code)}}}
    return code / "file.c", raw, bundle, checkout


def lint_report(harness, checkout=None, name="fixed"):
    incoming = harness.base / (name + "-input.json")
    incoming.write_bytes(canonical({"inputs": {"code_checkout": checkout}} if checkout else {}))
    ref = ".build/reports/" + name + ".json"
    completed = subprocess.run([*harness.command("lint"),
        "--knowledge-root", str(harness.root), "--input", str(incoming), "--output", str(harness.root / ref)], capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode in (0, 1, 2), completed.stderr
    report = harness.record(ref)
    assert report.get("digest") and report.get("checks"), report
    return ref


def protected_bytes(harness):
    return {str(path.relative_to(harness.base)): hashed(path.read_bytes()) for path in harness.base.rglob("*")
            if path.is_file() and (path.is_relative_to(harness.root / "knowledge") or path.is_relative_to(harness.root / "governance")
            or path.is_relative_to(harness.root / "logs") or path.is_relative_to(harness.root / "artifacts")
            or path.is_relative_to(harness.base / "main") or path == harness.base / "config.yml")}
