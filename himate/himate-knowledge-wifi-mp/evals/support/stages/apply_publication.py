"""Public publication contracts over isolated byte identities, never real assets."""

import base64
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


SPEC = importlib.util.spec_from_file_location("publication_test_helpers", Path(__file__).with_name("apply_helpers.py"))
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


@pytest.fixture
def publication_case(tmp_path):
    root = tmp_path / "k"
    shutil.copytree(HELPER.ROOT / "himate/himate-knowledge-wifi-mp/governance", root / "governance",
                    ignore=shutil.ignore_patterns("__pycache__"))
    modules = {name: HELPER.load_contract(name) for name in ("runtime", "records", "validation", "source_resources")}
    rules_digest = HELPER.sha((root / "governance/framework.lock.yaml").read_bytes())
    # Direct contract tests use the actual record schema while parallel slices
    # are being authored; trusted CLI/lock validation is tested separately.
    rules = {"knowledge_root": root, "schemas": {
        "record": json.loads((root / "governance/schemas/records.schema.json").read_bytes())}}
    ctx = modules["runtime"].OperationContext(root, {"operation_id": "published"}, modules=modules,
        rules=rules, tool={"skill": "hs-fixture", "package_digest": "0" * 64,
                          "requirements_digest": "0" * 64, "runtime": "fixture"}, rules_digest=rules_digest)
    raw = b"exact original evidence\n"
    final = "logs/evidence/published/objects/" + HELPER.sha(raw) + ".bin"
    stage = ctx.base + "/staged/raw/" + HELPER.sha(raw) + ".bin"
    path = root / stage
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    entry = {"stage_ref": stage, "final_ref": final, "kind": "raw", "sha256": HELPER.sha(raw),
             "bytes": len(raw), "owner_operation_id": ctx.operation}
    body = b"fixed payload\n"
    view = {"operation_id": ctx.operation, "review_mode": "manual_document", "batch_kind": "content",
            "writes": [{"path": "knowledge/rules/a.md", "expected_old_digest": None,
                        "final_digest": HELPER.sha(body), "bytes_b64": base64.b64encode(body).decode()}],
            "deletes": [], "source_refs": [], "target_queries": [{"id": "one", "query": "fixed", "required": ["a"]}],
            "staged_objects": [entry], "event_proposals": []}
    return ctx, view, entry, raw


def installed_publication(case, *, record_only=False):
    """Install exact synthetic bytes to test metadata, not P6 semantic checks."""
    ctx, view, entry, raw = case
    publication = HELPER.load_contract("publication")
    if record_only:
        view = {**view, "batch_kind": "record_only", "review_mode": "record_only", "writes": [], "target_queries": []}
    plan = publication.prepare_plan(ctx, view)
    view = ctx.modules["records"].seal({**view, "publication_plan": plan, "content_digest": plan["content_digest"]})
    for row in view["writes"]:
        destination = ctx.root / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(row["bytes_b64"]))
    destination = ctx.root / entry["final_ref"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    manifest = publication.publish_manifest(ctx, view, plan)
    return publication, ctx, manifest, entry
