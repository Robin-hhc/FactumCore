"""Active code sources require symbols at the fixed-check boundary only."""

from support.library import library
import base64
import hashlib
import importlib.util
from pathlib import Path

import yaml
import pytest


_spec = importlib.util.spec_from_file_location(
    "code_ref_required_support", Path(__file__).parents[1] / "support/contracts.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
checks = _helper.module("checks")
records = _helper.module("records")
resources = _helper.module("source_resources")
validation = _helper.module("validation")




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
    assert report["findings"][0]["path"] == "knowledge/ready.md"
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
