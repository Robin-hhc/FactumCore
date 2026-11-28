"""Public contract regression for captured evidence and two maintenance lanes."""

import hashlib
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


def fixture(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/library"
    for name in ("docs-raw", "knowledge", "governance"):
        (root / name).mkdir(parents=True)
    code = project / "code/wifi/wait.c"
    code.parent.mkdir(parents=True)
    code.write_bytes(b"int wait_reply(void) {\n    return 5;\n}\n")
    (root / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "evidence-fixture", "code_root": "../../code",
        "modules": [{"path": "wifi", "chips": ["chip12"], "sides": ["host"]}],
    }), encoding="utf-8")
    document = root / "docs-raw/design.md"
    document.write_text("# Waiting\n\nWait for a reply.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
        catalog.register("code", "code/wifi/wait.c", source_id="code-wait")
        catalog.mark_processed("doc-design", hashlib.sha256(document.read_bytes()).hexdigest())
    (root / "knowledge/waiting.md").write_bytes(card())
    return root, code


def card(body="Wait for a reply.", references=None):
    metadata = {"id": "waiting", "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
                "code_ref": references if references is not None else [
                    {"code_id": "code-wait", "line_start": 1, "line_end": 3, "symbol": "wait_reply"}]}
    return ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n# Waiting\n\n" + body + "\n").encode()


def parsed(root):
    return module("cards_v3").parse_card((root / "knowledge/waiting.md").read_bytes(), "knowledge/waiting.md")


def confirm(root):
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    write_plan(root, [])
    checked, phase = ingest.maintenance_check(root, {})
    assert phase == "passed", checked
    receipt, phase = ingest.maintenance_commit(root, {"reason": "Actual current code and the card were independently checked."})
    assert phase == "completed", receipt
    return parsed(root)["code_ref"][0]["evidence_version"]


def test_semantic_zero_body_change_establishes_reference_version(tmp_path):
    root, _ = fixture(tmp_path)
    body = parsed(root)["body"]
    version = confirm(root)
    assert version and parsed(root)["body"] == body
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


def test_ingest_captures_checked_code_version_without_extra_governance(tmp_path):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    task, phase = ingest.scan(root, {"source": "doc-design", "reprocess": True})
    assert phase == "prepared", task
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    (root / ".build/cards/waiting.md").write_bytes(card())
    checked, phase = ingest.check(root, {})
    assert phase == "passed", checked
    assert ingest.commit(root, {})[1] == "completed"
    assert parsed(root)["code_ref"][0]["evidence_version"]
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


def test_ingest_rejects_code_changed_after_p4_before_any_card_write(tmp_path):
    root, code = fixture(tmp_path)
    ingest = module("ingest")
    ingest.scan(root, {"source": "doc-design", "reprocess": True})
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    (root / ".build/cards/waiting.md").write_bytes(card("A reviewed replacement."))
    assert ingest.check(root, {})[1] == "passed"
    original = (root / "knowledge/waiting.md").read_bytes()
    code.write_bytes(code.read_bytes().replace(b"return 5", b"return 8"))
    with pytest.raises(ingest.ContractError, match="CODE_EVIDENCE_CHANGED|SOURCE_CHANGED"):
        ingest.commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_unrelated_file_content_does_not_create_semantic_work(tmp_path):
    root, code = fixture(tmp_path)
    confirm(root)
    code.write_bytes(code.read_bytes() + b"\nint unrelated = 3;\n")
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


def test_relocated_reference_uses_mechanical_lane_without_semantic_marker(tmp_path):
    root, code = fixture(tmp_path)
    version = confirm(root)
    original_body = parsed(root)["body"]
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "mechanical_prepared", task
    assert task["mode"] == "mechanical"
    assert not (root / ".build/maintenance-review-check.json").exists()
    assert (root / task["mechanical_check_ref"]).is_file()
    receipt, phase = ingest.maintenance_commit(root, {})
    assert phase == "completed" and receipt["mode"] == "mechanical"
    result = parsed(root)
    assert result["body"] == original_body
    assert result["code_ref"][0]["line_start"] == 3
    assert result["code_ref"][0]["line_end"] == 5
    assert result["code_ref"][0]["evidence_version"] == version


def test_mechanical_lane_cannot_modify_body_even_with_rebuilt_marker(tmp_path):
    root, code = fixture(tmp_path)
    confirm(root)
    code.write_bytes(b"// header\n" + code.read_bytes())
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "mechanical_prepared", task
    draft = root / ".build/cards/waiting.md"
    draft.write_bytes(draft.read_bytes().replace(b"Wait for a reply.", b"Unreviewed semantic replacement."))
    original = (root / "knowledge/waiting.md").read_bytes()
    with pytest.raises(ingest.ContractError, match="MECHANICAL|MAINTENANCE"):
        ingest.maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_changed_fragment_requires_semantic_lane_and_new_confirmation(tmp_path):
    root, code = fixture(tmp_path)
    before = confirm(root)
    code.write_bytes(code.read_bytes().replace(b"return 5", b"return 8"))
    after = confirm(root)
    assert after != before
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


def test_defer_does_not_confirm_changed_evidence(tmp_path):
    root, code = fixture(tmp_path)
    before = confirm(root)
    code.write_bytes(code.read_bytes().replace(b"return 5", b"return 8"))
    ingest = module("ingest")
    ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert ingest.maintenance_commit(root, {"defer": True, "reason": "Missing applicability evidence."})[1] == "deferred"
    assert parsed(root)["code_ref"][0]["evidence_version"] == before
    assert module("library").patrol(root, "plan", {})[1] == "needs_maintenance"
