"""Current filesystem evidence and CI references without repository commands."""

import base64
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[5]
CONTRACTS = ROOT / "himate-knowledge-wifi-mp/governance/contracts"
package_spec = importlib.util.spec_from_file_location(
    "module_mapping_contracts", CONTRACTS / "__init__.py", submodule_search_locations=[str(CONTRACTS)],
)
package = importlib.util.module_from_spec(package_spec)
sys.modules[package_spec.name] = package
package_spec.loader.exec_module(package)
validation = importlib.import_module(package_spec.name + ".validation")
resources = importlib.import_module(package_spec.name + ".source_resources")
scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
engine_spec = importlib.util.spec_from_file_location("mapped_local_check", scripts / "check.py")
engine = importlib.util.module_from_spec(engine_spec)
engine_spec.loader.exec_module(engine)
sys.path.remove(str(scripts))


def hashed(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(params=["himate-knowledge-wifi-mp", "himate/himate-knowledge-wifi-mp"], ids=["flat", "nested"])
def mapped(tmp_path, monkeypatch, request):
    workspace = tmp_path / "workspace"
    domain = workspace / request.param
    domain.mkdir(parents=True)
    modules = [
        {"path": "host/core", "chips": ["chip12"], "sides": ["host"], "description": "Host source"},
        {"path": "device/core", "chips": ["chip12"], "sides": ["device"], "description": "Device source"},
        {"path": "algorithms/shared", "chips": ["chip12", "chip08"], "sides": ["host", "device"],
         "features": ["FILTER"], "description": "Shared algorithm labels"},
    ]
    data = b"int wifi_ready(void) { return 1; }\n"
    for module in modules:
        path = workspace / "main" / module["path"] / "src/wifi.c"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        # Internal metadata can exist, but this configuration never consumes it.
        (path.parents[1] / ".git").write_text("opaque internal mm metadata", encoding="utf-8")
    config = {"schema_version": "2.0", "workspace_id": "mapped-wifi",
              "knowledge_roots": {"wifi": request.param},
              "code_root": "main", "modules": modules}
    config_path = workspace / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    rules = {"knowledge_root": str(domain), "schemas": {"workspace": json.loads(
        (CONTRACTS.parent / "schemas/workspace.schema.json").read_bytes())}}
    normalized = validation.normalize_workspace(config, workspace)
    repo = next(item for item in normalized["repos"] if item["workspace_path"] == "main/host/core")
    context = {"config_digest": hashed(config_path.read_bytes()),
               "target": {"target_id": "chip12-host", "chip": "chip12", "side": "host",
                          "features": [], "protocol_versions": [], "build_profile": None, "revision": None},
               "repos": {repo["repo_id"]: {**repo, "root": str(workspace / repo["root"]),
                    "identity": None, "head": None, "dirty": None,
                    "files": {"src/wifi.c": hashed(data)}}}}
    ctx = SimpleNamespace(root=domain, domain=validation, rules=rules, rules_digest="0" * 64,
                          catalog={"workspaces": {"mapped-wifi": {"config": str(config_path), "rules_digest": "0" * 64}}},
                          path=lambda relative, prefixes=None: validation.safe_path(domain, relative, prefixes))
    # A single external command, including Git/mm, makes every new-mode test fail.
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("filesystem mode must not execute commands"))
    return SimpleNamespace(workspace=workspace, domain=domain, config=config, config_path=config_path,
                           normalized=normalized, repo=repo, context=context, ctx=ctx, data=data, rules=rules)


def checked(mapped, *, source_only=False, require_build=False):
    config, policy, _ = engine.read_configuration(mapped.ctx, mapped.context)
    return engine.code_identity(mapped.ctx, mapped.context, config, policy, "local", source_only, require_build)


def test_current_static_code_uses_exact_files_without_git_or_manual_policy(mapped):
    identity = checked(mapped)
    row = identity["repos"][mapped.repo["repo_id"]]
    assert row["head"] is None and row["identity"] is None and row["checked_files_dirty"] is None
    assert row["evidence_basis"] == "filesystem"
    assert resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None) == identity
    (mapped.workspace / mapped.repo["root"] / "src/wifi.c").write_bytes(b"changed source\n")
    with pytest.raises(ValueError, match="CODE_BYTES_CHANGED"):
        resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None)


def test_workspace_configuration_is_found_without_install_registration(mapped):
    mapped.ctx.catalog["workspaces"] = {}
    assert checked(mapped)["repos"][mapped.repo["repo_id"]]["files"] == {"src/wifi.c": hashed(mapped.data)}


@pytest.mark.parametrize("field", ["kind", "evidence_basis", "workspace_path"])
def test_local_gate_rejects_missing_mapping_identity_needed_for_historical_replay(mapped, field):
    mapped.context["repos"][mapped.repo["repo_id"]].pop(field)
    with pytest.raises(engine.Incomplete, match="preserve the module mapping identity"):
        checked(mapped)


@pytest.mark.parametrize("field,value", [("head", "f" * 40), ("identity", "a-remote-url"), ("dirty", False)])
def test_filesystem_context_does_not_invent_repository_facts(mapped, field, value):
    mapped.context["repos"][mapped.repo["repo_id"]][field] = value
    with pytest.raises(engine.Incomplete, match="cannot claim Git"):
        checked(mapped)


def test_equal_relative_filename_in_another_side_is_not_host_evidence(mapped):
    repo = next(item for item in mapped.normalized["repos"] if item["workspace_path"] == "main/device/core")
    mapped.context["repos"] = {repo["repo_id"]: {**repo, "root": str(mapped.workspace / repo["root"]),
        "identity": None, "head": None, "dirty": None, "files": {"src/wifi.c": hashed(mapped.data)}}}
    with pytest.raises(engine.Incomplete, match="module/Target range"):
        checked(mapped)


def test_relative_evidence_can_be_rechecked_at_another_deployment_root(mapped, tmp_path):
    identity = checked(mapped)
    relocated = tmp_path / "other-deployment"
    shutil.copytree(mapped.workspace, relocated)
    rules = {**mapped.rules, "knowledge_root": str(relocated / mapped.domain.relative_to(mapped.workspace))}
    assert resources.validate_current_code_identity(identity, relocated / "config.yml", mapped.context["config_digest"], rules, None) == identity


def test_changed_config_is_not_silently_rebound(mapped):
    identity = checked(mapped)
    mapped.config_path.write_bytes(mapped.config_path.read_bytes() + b"# new mapping revision\n")
    with pytest.raises(ValueError, match="CODE_CONFIGURATION_CHANGED"):
        resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None)


def test_historical_filesystem_context_preserves_unknown_revision(mapped):
    local = checked(mapped)
    historical = engine.frozen_identity(mapped.ctx, mapped.context, "local", False, False)
    assert historical == local


def test_module_feature_labels_do_not_replace_actual_context_or_build_material(mapped):
    mapped.context["target"]["features"] = None
    with pytest.raises(engine.Incomplete, match="feature/protocol context"):
        checked(mapped)
    mapped.context["target"]["features"] = []
    with pytest.raises(engine.Incomplete, match="build/macro evidence"):
        checked(mapped, require_build=True)


def test_build_material_is_bound_without_repository_commands(mapped):
    artifact = b"actual retained build evidence\n"
    relative = "logs/evidence/build.bin"
    path = mapped.domain / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(artifact)
    mapped.context["target"].update(build_profile="actual-profile", revision="declared-build-view")
    mapped.context["build_evidence"] = {"profile": "actual-profile", "source_revision": "declared-build-view",
        "macro_digest": "f" * 64, "artifacts": [{"path": relative, "sha256": hashed(artifact)}]}
    identity = checked(mapped, require_build=True)
    assert resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None) == identity
    path.write_bytes(b"changed material")
    with pytest.raises(ValueError, match="CODE_BUILD_CHANGED"):
        resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None)


def test_fixed_ci_code_reference_checks_actual_module_files_without_git(mapped):
    repo_id = mapped.repo["repo_id"]
    ref = {"evidence_ref": "evidence-code", "source_id": "code-source", "snapshot_id": "code-snapshot",
           "locator": {"kind": "lines", "start": 1, "end": 1, "repo_id": repo_id, "path": "src/wifi.c"}}
    lock = {"resources": [{"source_id": "code-source", "kind": "code", "repo_id": repo_id, "path": "src/wifi.c"}],
            "snapshots": [{"source_id": "code-source", "snapshot_id": "code-snapshot", "sha256": hashed(mapped.data), "bytes": len(mapped.data)}]}
    card = {"metadata": {"scope": {"contexts": [{"target_id": "chip12-host", "chip": "chip12", "side": "host"}]}, "sources": [ref]}}
    checkout = {"configuration": str(mapped.config_path), "config_digest": mapped.context["config_digest"],
                "repos": {repo_id: {"root": str(mapped.workspace / mapped.repo["root"]), "files": {"src/wifi.c": hashed(mapped.data)}}}}
    verified = resources.validate_code_references(card, lock, checkout, mapped.rules)
    assert verified[0]["commit"] is None and verified[0]["evidence_basis"] == "filesystem"
    assert resources.git_recovery_for_current(mapped.domain, "docs-raw/specs/source.md", b"original") is None


def test_old_git_recovery_in_new_workspace_uses_retained_object_without_git(mapped):
    ref = "logs/evidence/objects/retained.bin"
    path = mapped.domain / ref
    path.parent.mkdir(parents=True)
    path.write_bytes(mapped.data)
    snapshot = {"snapshot_id": "retained", "sha256": hashed(mapped.data), "bytes": len(mapped.data),
        "recovery": {"kind": "git", "commit": "a" * 40, "repo_id": "legacy-repo", "path": "src/wifi.c"},
        "local_recovery": {"method": "evidence_object", "path": ref}}
    assert resources.recover_snapshot(mapped.domain, snapshot) == mapped.data


@pytest.mark.parametrize("change", ["deleted", "file", "linked"])
def test_historical_recovery_ignores_invalid_current_layout_but_current_checks_reject_it(mapped, change):
    identity = checked(mapped)
    relative = "logs/evidence/objects/retained-after-layout-change.bin"
    retained = mapped.domain / relative
    retained.parent.mkdir(parents=True)
    retained.write_bytes(mapped.data)
    snapshot = {"snapshot_id": "retained", "sha256": hashed(mapped.data), "bytes": len(mapped.data),
        "recovery": {"kind": "git", "commit": "a" * 40, "repo_id": "legacy-repo", "path": "src/wifi.c"},
        "local_recovery": {"method": "evidence_object", "path": relative}}
    module = mapped.workspace / mapped.repo["root"]
    assert module.resolve().is_relative_to(mapped.workspace.resolve())
    shutil.rmtree(module)
    if change == "file":
        module.write_bytes(b"replaced by ordinary file")
    elif change == "linked":
        target = mapped.workspace / "unrelated-directory"
        target.mkdir()
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(target), str(module))
        else:
            module.symlink_to(target, target_is_directory=True)
    assert resources.recover_snapshot(mapped.domain, snapshot) == mapped.data
    with pytest.raises(ValueError):
        resources.validate_current_code_identity(identity, mapped.config_path, mapped.context["config_digest"], mapped.rules, None)


def test_merge_checked_snapshot_reads_authorized_files_without_git(mapped, monkeypatch):
    """Exercise the complete evaluation path, including a checked snapshot."""
    monkeypatch.setattr(engine, "git_read", lambda *args, **kwargs: pytest.fail("merge must not read Git"))
    governance = mapped.domain / "governance"
    shutil.copytree(CONTRACTS.parent, governance, ignore=shutil.ignore_patterns("__pycache__"))
    framework_path = governance / "framework.lock.yaml"
    framework = yaml.safe_load(framework_path.read_bytes())
    for item in framework["files"].values():
        item["sha256"] = hashed((mapped.domain / item["path"]).read_bytes())
    framework_path.write_text(yaml.safe_dump(framework, sort_keys=False), encoding="utf-8")
    rules_digest = hashed(framework_path.read_bytes())
    rules = validation.load_rules(mapped.domain, rules_digest)
    support = sys.modules["support"]
    identity = {"skill": "hs-fixture-producer", "package_digest": "0" * 64,
                "requirements_digest": "0" * 64, "runtime": "fixture"}
    catalog = {"workspaces": {"mapped-wifi": {"config": str(mapped.config_path), "rules_digest": rules_digest}}}
    ctx = support.Context(mapped.domain, rules_digest, identity, catalog, validation, rules)
    repo_id = mapped.repo["repo_id"]
    locator = {"kind": "lines", "start": 1, "end": 1, "repo_id": repo_id, "path": "src/wifi.c"}
    ref = {"evidence_ref": "e1", "source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "locator": locator}
    original_ref = "logs/evidence/original.bin"
    original_path = mapped.domain / original_ref
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(mapped.data)
    source_lock = {"schema_version": "2.0", "resources": [{"source_id": "fixture-code", "kind": "code", "repo_id": repo_id, "path": "src/wifi.c"}],
        "snapshots": [{"source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "sha256": hashed(mapped.data),
            "bytes": len(mapped.data), "recovery": {"path": original_ref}}]}
    template = (governance / "templates/flow.md").read_text(encoding="utf-8")
    for key, value in {"card_id": "fixture-code-flow", "title": "Fixture code", "summary": "Filesystem merge check",
        "owner": "fixture", "evidence_ref": "e1", "source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot",
        "claim_id": "c1", "claim_text": "The exact source function returns one."}.items():
        template = template.replace("{{" + key + "}}", value)
    _, front, body = template.split("---", 2)
    metadata = yaml.safe_load(front)
    metadata.update(lifecycle="stable", review_mode="code_gate", scope={"applicability": "unknown", "contexts": []})
    metadata["sources"] = [ref]
    metadata["claims"][0].update(usage="guidance", context_ids=[], verification_requirements=["semantic-support"])
    card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
    context_ref = ".build/operations/op/context.json"
    context = ctx.record("project_context", "op", state="context_loaded", workspace_id="mapped-wifi",
        workspace_root=str(mapped.workspace), knowledge_root=str(mapped.domain), config_path=str(mapped.config_path),
        config_digest=hashed(mapped.config_path.read_bytes()), entries=[], repos=mapped.context["repos"], target=None)
    ctx.save(context_ref, context)
    source_raw = json.dumps(source_lock, sort_keys=True, separators=(",", ":")).encode()
    writes = [{"path": "knowledge/flows/fixture-code-flow.md", "expected_old_digest": None,
        "final_digest": hashed(card), "bytes_b64": base64.b64encode(card).decode()},
        {"path": "governance/sources.lock.yaml", "expected_old_digest": hashed((governance / "sources.lock.yaml").read_bytes()),
        "final_digest": hashed(source_raw), "bytes_b64": base64.b64encode(source_raw).decode()}]
    view_ref = ".build/operations/op/view.json"
    view = ctx.record("final_view", "op", review_mode="code_gate", context_ref=context_ref,
        writes=writes, deletes=[], source_refs=[], plan_ref=".build/operations/op/fixture-plan.json", plan_digest="0" * 64,
        baseline_digest=support.digest({"files": {row["path"]: row["expected_old_digest"] for row in writes}}))
    ctx.save(view_ref, view)
    checked = {"repo_id": repo_id, "path": "src/wifi.c", "commit": None, "snapshot_id": "checked-source",
        "sha256": hashed(mapped.data), "bytes": len(mapped.data), "locator": {"kind": "lines", "start": 1, "end": 1}}
    report = {"schema_version": "2.0", "record_kind": "semantic_review", "reviewer_id": "independent-reader",
        "payload": {"author_id": "fixture", "independent_context": "fresh-read-context", "findings": [],
        "view_digest": view["digest"], "context_digest": context["digest"], "mode": "merge", "issued_at": time.time(),
        "claims": [{"card_id": "fixture-code-flow", "claim_id": "c1", "status": "supported",
            "reason": "Read the actual source function and its literal return.", "evidence": [{
                "source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "locator": locator,
                "sha256": hashed(mapped.data), "checked_snapshot": checked}]}]}}
    result = engine.evaluate(ctx, {"operation_id": "op", "view_ref": view_ref}, view, "merge",
        report_override=report, record_snapshots=True)
    assert result["code_identity"]["repos"][repo_id]["head"] is None
    retained = result["checked_snapshots"][0]
    assert (mapped.domain / retained["recovery"]["path"]).read_bytes() == mapped.data
