"""Active code sources require symbols at the fixed-check boundary only."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import yaml
import pytest


_spec = importlib.util.spec_from_file_location(
    "code_ref_required_support", Path(__file__).parents[1] / "contract_test_support.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
checks = _helper.module("checks")
records = _helper.module("records")
resources = _helper.module("source_resources")
validation = _helper.module("validation")


def library(tmp_path, *, lifecycle="stable", review_mode="manual_document", kind="code"):
    """Synthetic rules are explicitly loaded from the development checkout."""
    root = tmp_path / "knowledge-root"
    (root / "governance").mkdir(parents=True)
    (root / "knowledge").mkdir()
    raw = b"int ready(void) { return 1; }\n"
    source = {"evidence_ref": "entry", "source_id": "source", "snapshot_id": "v1",
              "locator": {"kind": "lines", "start": 1, "end": 1}}
    lock = {"schema_version": "2.0", "resources": [
        {"source_id": "source", "kind": kind, "path": "src/ready.c"}],
        "snapshots": [{"source_id": "source", "snapshot_id": "v1",
                       "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                       "recovery": {"method": "evidence_object", "path": "logs/evidence/old.bin"}}]}
    (root / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    metadata = {"schema_version": "2.0", "id": "ready-card", "profile": "flow", "title": "Ready",
                "summary": "Documented ready flow", "lifecycle": lifecycle, "review_mode": review_mode,
                "owner": "fixture", "scope": {"applicability": "unknown", "contexts": []}, "aliases": [],
                "sources": [source], "claims": [{"id": "ready-claim", "text_ref": "#ready-claim",
                    "evidence_kind": "design", "source_refs": ["entry"], "context_ids": [],
                    "usage": "guidance", "verification_requirements": []}], "relations": []}
    body = "# Ready\n\n<a id=\"ready-claim\"></a>\nDocumented ready flow.\n"
    for heading in ("起终点", "步骤", "调用与消息", "异常", "条件", "证据"):
        body += "\n## " + heading + "\n\nDocumented scope.\n"
    card_bytes = ("---\n" + yaml.safe_dump(metadata) + "---\n" + body).encode("utf-8")
    (root / "knowledge/ready.md").write_bytes(card_bytes)
    (root / "knowledge/index.md").write_text("# Knowledge\n\n[Ready](ready.md)\n", encoding="utf-8")
    governance = Path(__file__).parents[2] / "governance"
    rules = {"knowledge_root": root, "rules_digest": "0" * 64,
             "profiles": yaml.safe_load((governance / "schemas/profiles.yaml").read_bytes()),
             "registries": yaml.safe_load((governance / "schemas/registries.yaml").read_bytes()),
             "schemas": {key: json.loads((governance / "schemas" / (name + ".schema.json")).read_bytes())
                         for key, name in (("card", "frontmatter"), ("sources", "sources"),
                                           ("workspace", "workspace"), ("record", "records"))}}
    return root, raw, source, lock, rules


def test_active_document_mode_code_source_requires_symbol(tmp_path):
    root, raw, _, _, rules = library(tmp_path)
    report = checks.run(checks.prepare_view(root), rules, inputs={"source_objects": {"v1": raw}}, scope="full")
    assert report["status"] == "failed"
    assert any(row["code"] == "CODE_REF_REQUIRED" and row["path"] == "knowledge/ready.md"
               for row in report["findings"])


@pytest.mark.parametrize("mode", ["formal", "candidate", "ci"])
@pytest.mark.parametrize("review_mode", ["manual_document", "code_gate"])
@pytest.mark.parametrize("lifecycle", ["draft", "stable"])
def test_all_active_code_sources_require_symbols_at_each_fixed_check_entry(tmp_path, mode, review_mode, lifecycle):
    root, raw, _, lock, rules = library(tmp_path, lifecycle=lifecycle, review_mode=review_mode)
    candidate = None
    if mode == "candidate":
        card_path = root / "knowledge/ready.md"
        card_bytes = card_path.read_bytes()
        card_path.unlink()
        candidate = records.seal({"schema_version": "2.0", "record_kind": "final_view",
            "operation_id": "required-symbol", "writes": [{"path": "knowledge/ready.md",
                "bytes_b64": base64.b64encode(card_bytes).decode("ascii"), "expected_old_digest": None,
                "final_digest": hashlib.sha256(card_bytes).hexdigest()}], "deletes": [],
            "source_refs": lock["snapshots"],
            "source_set_digest": hashlib.sha256(validation.canonical_bytes(lock["snapshots"])).hexdigest()})
    report = checks.run(checks.prepare_view(root, candidate, mode=mode), rules,
                        inputs={"source_objects": {"v1": raw}}, scope="full")
    assert report["status"] == "failed"
    assert [row["code"] for row in report["findings"]] == ["CODE_REF_REQUIRED"]
    assert next(row for row in report["checks"] if row["check_id"] == "source.references")["status"] == "failed"


@pytest.mark.parametrize("kind,lifecycle", [("raw", "stable"), ("code", "deprecated")])
def test_document_only_and_deprecated_cards_do_not_require_new_symbols(tmp_path, kind, lifecycle):
    root, raw, _, _, rules = library(tmp_path, kind=kind, lifecycle=lifecycle)
    report = checks.run(checks.prepare_view(root), rules, inputs={"source_objects": {"v1": raw}}, scope="full")
    assert report["status"] == "passed", report["findings"]


def test_unused_code_metadata_source_still_requires_a_symbol(tmp_path):
    root, raw, source, lock, rules = library(tmp_path, kind="raw")
    code_source = {**source, "evidence_ref": "unused-code", "source_id": "code", "snapshot_id": "code-v1"}
    lock["resources"].append({"source_id": "code", "kind": "code", "path": "src/unused.c"})
    lock["snapshots"].append({**lock["snapshots"][0], "source_id": "code", "snapshot_id": "code-v1"})
    (root / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    path = root / "knowledge/ready.md"
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["sources"].append(code_source)
    path.write_text("---\n" + yaml.safe_dump(metadata) + "---" + body, encoding="utf-8")
    report = checks.run(checks.prepare_view(root), rules,
                        inputs={"source_objects": {"v1": raw, "code-v1": raw}}, scope="full")
    assert [row["code"] for row in report["findings"]] == ["CODE_REF_REQUIRED"]
    assert "unused-code" in report["findings"][0]["reason"]


def test_historical_source_recovery_keeps_the_original_four_field_contract(tmp_path):
    _, raw, source, lock, _ = library(tmp_path)
    assert resources.validate_source_ref(source, lock)["snapshot_id"] == "v1"
    recovered = resources.validate_reference(source, lock, lambda _: raw)
    assert recovered["locator"] == {"kind": "lines", "start": 1, "end": 1}
    assert "code_ref" not in recovered
