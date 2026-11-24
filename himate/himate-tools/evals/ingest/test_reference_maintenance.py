"""Existing-card maintenance is distinct from document ingestion."""

import hashlib
import json
from pathlib import Path
import subprocess
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
    code.write_text("int wait_reply(void) {\n    return 5;\n}\n", encoding="utf-8")
    (root / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "synthetic", "code_root": "../../code",
        "modules": [{"path": "wifi", "chips": ["chip12"], "sides": ["host"]}],
    }), encoding="utf-8")
    document = root / "docs-raw/design.md"
    document.write_text("# Waiting\n\nWait for a reply.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
        catalog.register("code", "code/wifi/wait.c", source_id="code-wait")
        catalog.mark_processed("doc-design", hashlib.sha256(document.read_bytes()).hexdigest())
        # Legacy whole-code processing is deliberately not a reference review.
        catalog.mark_processed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest())
    (root / "knowledge/waiting.md").write_bytes(card("waiting", referenced=True))
    (root / "knowledge/independent.md").write_bytes(card("independent"))
    return root, code


def card(identity, *, referenced=False, body="Wait for a reply."):
    metadata = {"id": identity, "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
                "code_ref": ([{"code_id": "code-wait", "line_start": 1, "line_end": 3,
                               "symbol": "wait_reply"}] if referenced else [])}
    return ("---\n" + yaml.safe_dump(metadata) + "---\n# " + identity + "\n\n" + body + "\n").encode()


def prepare(root):
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    return task


def save_history(root):
    project = root.parents[1]
    for arguments in (["init"], ["config", "core.autocrlf", "false"], ["add", "."],
                      ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Synthetic retained history"]):
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", str(project), *arguments], check=True, capture_output=True)


def test_legacy_processed_code_requires_reference_baseline_and_uses_l_chain(tmp_path):
    root, _ = fixture(tmp_path)
    result, phase = module("library").patrol(root, "plan", {})
    assert phase == "needs_maintenance"
    assert result["next_file"]["change"] == "baseline_missing"
    assert result["next_file"]["task_type"] == "card_maintenance"
    task = prepare(root)
    assert task["task_type"] == "card_maintenance"
    assert [item["id"] for item in task["affected_cards"]] == ["waiting"]


@pytest.mark.parametrize("remove_markers", [False, True])
def test_legacy_code_scan_cannot_create_unrelated_card_even_without_markers(tmp_path, remove_markers):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    task, phase = ingest.scan(root, {"source": "code-wait"})
    assert phase == "prepared"
    assert task["task_type"] == "card_maintenance"
    if remove_markers:
        path = root / ".build/task.json"
        edited = json.loads(path.read_text())
        for key in ("task_type", "code_review", "maintenance_id"):
            edited.pop(key, None)
        edited["affected_cards"].append({"id": "new-topic", "path": "knowledge/new-topic.md"})
        path.write_text(json.dumps(edited))
    write_plan(root, [("new-topic", "knowledge/new-topic.md")])
    (root / ".build/cards/new-topic.md").write_bytes(card("new-topic"))
    result, phase = ingest.check(root, {})
    assert phase == "failed"
    assert any(item["code"] in {"MAINTENANCE_SCOPE", "MAINTENANCE_TASK_CHANGED"} for item in result["findings"])
    with pytest.raises(ingest.ContractError):
        ingest.commit(root, {})
    assert not (root / "knowledge/new-topic.md").exists()


def test_no_change_maintenance_records_review_without_completing_code_ingestion(tmp_path):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    with module("catalog").Catalog(root) as catalog:
        before = catalog.get_file("code-wait")["processed_at"]
    task = prepare(root)
    write_plan(root, [])
    assert ingest.maintenance_check(root, {})[1] == "passed"
    receipt, phase = ingest.maintenance_commit(root, {"reason": "Current reference and documented requirement hold."})
    assert phase == "completed" and receipt["maintenance_complete"] is True
    assert receipt["reviewed_card_ids"] == ["waiting"] and receipt["card_ids"] == []
    assert "source_complete" not in receipt and "processed_hash" not in receipt
    with module("catalog").Catalog(root) as catalog:
        source = catalog.get_file("code-wait")
        assert source["processed_at"] == before
        assert source["reference_review"]["source_sha256"] == task["source"]["hash"]
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


def test_changed_formal_card_or_source_cannot_be_overwritten(tmp_path):
    root, code = fixture(tmp_path)
    ingest = module("ingest")
    prepare(root)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    (root / ".build/cards/waiting.md").write_bytes(card("waiting", referenced=True, body="Reviewed text."))
    assert ingest.maintenance_check(root, {})[1] == "passed"
    (root / "knowledge/waiting.md").write_bytes(card("waiting", referenced=True, body="Another author's edit."))
    with pytest.raises(ingest.ContractError, match="MAINTENANCE_CARD_CHANGED"):
        ingest.maintenance_commit(root, {})
    assert "Another author" in (root / "knowledge/waiting.md").read_text()
    prepare(root)
    write_plan(root, [])
    assert ingest.maintenance_check(root, {})[1] == "passed"
    code.write_text("int wait_reply(void) {\n    return 8;\n}\n")
    with pytest.raises(ingest.ContractError, match="SOURCE_CHANGED"):
        ingest.maintenance_commit(root, {"reason": "Unchanged documented requirement."})


def test_deleted_document_routes_to_maintenance_while_ingest_skips_it(tmp_path):
    root, code = fixture(tmp_path)
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    (root / "docs-raw/design.md").unlink()
    result, phase = module("library").patrol(root, "plan", {})
    assert phase == "needs_maintenance" and result["next_file"]["change"] == "deleted"
    assert module("ingest").scan(root, {})[1] == "unchanged"
    result, phase = module("ingest").maintenance_prepare(root, {"source": "doc-design"})
    assert phase == "prepared" and result["source"]["exists"] is False


@pytest.mark.parametrize("changed", [False, True], ids=["same-hash", "changed-hash"])
def test_restored_document_reopens_ingest_then_later_deletion_is_maintenance(tmp_path, changed):
    root, code = fixture(tmp_path)
    ingest, library = module("ingest"), module("library")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    document = root / "docs-raw/design.md"
    original = document.read_bytes()
    save_history(root)
    document.unlink()
    assert ingest.maintenance_prepare(root, {"source": "doc-design"})[1] == "prepared"
    write_plan(root, [])
    assert ingest.maintenance_check(root, {})[1] == "passed"
    assert ingest.maintenance_commit(root, {"reason": "Retain documented historical knowledge."})[1] == "completed"
    document.write_bytes(original + (b"\nAn additional design constraint.\n" if changed else b""))
    selection, phase = library.patrol(root, "plan", {})
    assert phase == "needs_ingest", selection
    assert selection["next_file"]["source_id"] == "doc-design"
    task, phase = ingest.scan(root, {"source": "doc-design"})
    assert phase == "prepared" and task["task_type"] == "document_ingest", task
    write_plan(root, [])
    assert ingest.check(root, {})[1] == "passed"
    receipt, phase = ingest.commit(root, {"reason": "Reassessed the restored document."})
    assert phase == "completed" and receipt["source_complete"] is True, receipt
    with module("catalog").Catalog(root) as catalog:
        assert "reference_review" not in catalog.get_file("doc-design")
        assert catalog.get_file("code-wait")["reference_review"]["exists"] is True
    document.unlink()
    selection, phase = library.patrol(root, "plan", {})
    assert phase == "needs_maintenance", selection
    assert selection["next_file"]["source_id"] == "doc-design"
    assert selection["next_file"]["change"] == "deleted"


@pytest.mark.parametrize("kind", ["code", "doc"])
@pytest.mark.parametrize("legacy_label", [False, True], ids=["no-label", "unregistered-legacy-label"])
def test_deleted_source_without_history_cannot_complete_zero_change_review(tmp_path, kind, legacy_label):
    root, code = fixture(tmp_path)
    ingest = module("ingest")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    source_id = "code-wait" if kind == "code" else "doc-design"
    if legacy_label:
        for path in (root / "knowledge").glob("*.md"):
            _, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
            metadata = yaml.safe_load(frontmatter)
            for reference in metadata[kind + "_ref"]:
                if reference[kind + "_id"] == source_id:
                    reference["snapshot_id"] = "legacy-version-label"
            path.write_text("---\n" + yaml.safe_dump(metadata) + "---" + body, encoding="utf-8")
    (code if kind == "code" else root / "docs-raw/design.md").unlink()
    assert ingest.maintenance_prepare(root, {"source": source_id})[1] == "prepared"
    write_plan(root, [])
    result, phase = ingest.maintenance_check(root, {})
    assert phase == "failed", result
    assert any(item["code"] in {"OLD_SOURCE_UNAVAILABLE", "GIT_SOURCE_UNAVAILABLE", "SOURCE_INPUT_UNAVAILABLE"}
               for item in result["findings"])
    with pytest.raises(ingest.ContractError):
        ingest.maintenance_commit(root, {"reason": "An explanation cannot replace missing historical evidence."})
    selection, phase = module("library").patrol(root, "plan", {})
    assert phase == "needs_maintenance" and selection["next_file"]["source_id"] == source_id


def test_registered_snapshot_from_another_source_cannot_be_treated_as_legacy_label(tmp_path):
    root, _ = fixture(tmp_path)
    registry_file = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(registry_file.read_bytes())
    registry["snapshots"].append({"snapshot_id": "wrong-owner", "source_id": "doc-design",
                                  "sha256": "a" * 64, "bytes": 1,
                                  "recovery": {"method": "evidence_object", "path": "artifacts/evidence/objects/missing.bin"}})
    registry_file.write_text(yaml.safe_dump(registry), encoding="utf-8")
    path = root / "knowledge/waiting.md"
    _, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    metadata["code_ref"][0]["snapshot_id"] = "wrong-owner"
    path.write_text("---\n" + yaml.safe_dump(metadata) + "---" + body, encoding="utf-8")
    prepare(root)
    write_plan(root, [])
    result, phase = module("ingest").maintenance_check(root, {})
    assert phase == "failed", result
    assert any(item["code"] == "SOURCE_SNAPSHOT_MISMATCH" for item in result["findings"])


@pytest.mark.parametrize("kind", ["code", "doc"])
@pytest.mark.parametrize("history", ["git", "snapshot"])
def test_deleted_source_zero_change_uses_actual_history_or_retained_snapshot(tmp_path, kind, history):
    root, code = fixture(tmp_path)
    ingest = module("ingest")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    source_id = "code-wait" if kind == "code" else "doc-design"
    original = code if kind == "code" else root / "docs-raw/design.md"
    if history == "git":
        save_history(root)
    else:
        content = original.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        reference = "artifacts/evidence/objects/" + digest + ".bin"
        retained = root / reference
        retained.parent.mkdir(parents=True)
        retained.write_bytes(content)
        registry_file = root / "governance/sources.lock.yaml"
        registry = yaml.safe_load(registry_file.read_bytes())
        registry["snapshots"].append({"snapshot_id": "retained-original", "source_id": source_id,
                                      "sha256": digest, "bytes": len(content),
                                      "recovery": {"method": "evidence_object", "path": reference}})
        registry_file.write_text(yaml.safe_dump(registry), encoding="utf-8")
        for path in (root / "knowledge").glob("*.md"):
            _, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
            metadata = yaml.safe_load(frontmatter)
            for ref in metadata[kind + "_ref"]:
                if ref[kind + "_id"] == source_id:
                    ref["snapshot_id"] = "retained-original"
            path.write_text("---\n" + yaml.safe_dump(metadata) + "---" + body, encoding="utf-8")
    original.unlink()
    assert ingest.maintenance_prepare(root, {"source": source_id})[1] == "prepared"
    write_plan(root, [])
    result, phase = ingest.maintenance_check(root, {})
    assert phase == "passed", result
    receipt, phase = ingest.maintenance_commit(root, {"reason": "Verified each retained historical source reference."})
    assert phase == "completed" and receipt["maintenance_complete"] is True, receipt
    result, phase = ingest.check(root, {"formal": True})
    assert phase == "passed", result


@pytest.mark.parametrize("tamper", ["current-text", "current-pointer", "previous-text", "previous-pointer"])
def test_maintenance_rejects_changed_text_material_or_handoff_pointer(tmp_path, tamper):
    root, _ = fixture(tmp_path)
    save_history(root)
    task = prepare(root)
    field = "previous_text_ref" if tamper.startswith("previous") else "text_ref"
    if tamper.endswith("text"):
        (root / task["source"][field]).write_bytes(b"Invented source text.\n")
    else:
        alternate = ".build/materials/alternate.txt"
        (root / alternate).write_bytes((root / task["source"][field]).read_bytes())
        task["source"][field] = alternate
        (root / ".build/task.json").write_text(json.dumps(task))
    write_plan(root, [])
    result, phase = module("ingest").maintenance_check(root, {})
    assert phase == "failed", result
    assert any(item["code"] == "MAINTENANCE_MATERIAL_CHANGED" for item in result["findings"])


@pytest.mark.parametrize("tamper", ["original-card-pointer", "omitted-card"])
def test_maintenance_keeps_the_original_card_handoff_fixed(tmp_path, tamper):
    root, _ = fixture(tmp_path)
    task = prepare(root)
    if tamper == "omitted-card":
        task["affected_cards"] = []
    else:
        task["affected_cards"][0]["original_ref"] = task["source"]["text_ref"]
    (root / ".build/task.json").write_text(json.dumps(task))
    write_plan(root, [])
    result, phase = module("ingest").maintenance_check(root, {})
    assert phase == "failed", result
    assert any(item["code"] == "MAINTENANCE_SCOPE" for item in result["findings"])


@pytest.mark.parametrize("operation", ["new-card", "unrelated", "move", "delete"])
def test_fixed_scope_rejects_other_writes_despite_edited_task_list(tmp_path, operation):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    task = prepare(root)
    path = root / ".build/task.json"
    task["affected_cards"].extend([
        {"id": "independent", "path": "knowledge/independent.md"},
        {"id": "new", "path": "knowledge/new.md"},
    ])
    path.write_text(json.dumps(task))
    if operation == "delete":
        write_plan(root, [])
        (root / ".build/changes.json").write_text(json.dumps({"delete": ["knowledge/waiting.md"]}))
    else:
        identity, destination = (("new", "new.md") if operation == "new-card" else
                                 ("independent", "independent.md") if operation == "unrelated" else
                                 ("waiting", "moved.md"))
        write_plan(root, [(identity, "knowledge/" + destination)])
        (root / ".build/cards" / destination).write_bytes(card(identity))
    result, phase = ingest.maintenance_check(root, {})
    assert phase == "failed" and any(item["code"] == "MAINTENANCE_SCOPE" for item in result["findings"])
    with pytest.raises(ingest.ContractError, match="MAINTENANCE_SCOPE"):
        ingest.maintenance_commit(root, {"reason": "Attempt to expand scope."})


def test_same_batch_retry_after_card_copy_does_not_lose_fixed_scope(tmp_path, monkeypatch):
    root, _ = fixture(tmp_path)
    ingest, library = module("ingest"), module("library")
    task = prepare(root)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    proposed = card("waiting", body="Retain the historical design requirement without the code navigation link.")
    (root / ".build/cards/waiting.md").write_bytes(proposed)
    assert ingest.maintenance_check(root, {})[1] == "passed"
    original_build = library.build_search
    def interrupted(*args, **kwargs):
        raise OSError("Synthetic interruption after copying the card")
    monkeypatch.setattr(library, "build_search", interrupted)
    with pytest.raises(OSError, match="Synthetic interruption"):
        ingest.maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == proposed
    assert (root / ".build/task.json").is_file()
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("code-wait").get("reference_review") is None
        assert catalog.maintenance_input()["maintenance_id"] == task["maintenance_id"]
    monkeypatch.setattr(library, "build_search", original_build)
    result, phase = ingest.maintenance_commit(root, {})
    assert phase == "completed" and result["card_ids"] == ["waiting"]
    assert not (root / ".build/task.json").exists()


def test_candidates_changed_after_check_need_a_fresh_check(tmp_path):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    prepare(root)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    candidate = root / ".build/cards/waiting.md"
    candidate.write_bytes(card("waiting", referenced=True, body="Reviewed revision."))
    assert ingest.maintenance_check(root, {})[1] == "passed"
    candidate.write_bytes(card("waiting", referenced=True, body="Changed after the check."))
    with pytest.raises(ingest.ContractError, match="MAINTENANCE_NOT_CHECKED"):
        ingest.maintenance_commit(root, {})


def test_editable_task_cannot_change_review_provenance(tmp_path):
    root, _ = fixture(tmp_path)
    ingest = module("ingest")
    original = prepare(root)
    task = dict(original)
    task["source"] = {**task["source"], "source_commit": "f" * 40}
    (root / ".build/task.json").write_text(json.dumps(task))
    write_plan(root, [])
    assert ingest.maintenance_check(root, {})[1] == "passed"
    assert ingest.maintenance_commit(root, {"reason": "No card change after actual reference review."})[1] == "completed"
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("code-wait")["reference_review"]["source_commit"] == original["source"]["source_commit"]


def test_reference_review_survives_catalog_rebuild_without_changing_ingest_fact(tmp_path):
    root, code = fixture(tmp_path)
    with module("catalog").Catalog(root) as catalog:
        before = catalog.get_file("code-wait")["processed_at"]
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    with module("catalog").Catalog(root) as catalog:
        catalog.rebuild()
        source = catalog.get_file("code-wait")
        assert source["reference_review"]["source_sha256"] == hashlib.sha256(code.read_bytes()).hexdigest()
        assert source["processed_at"] == before


@pytest.mark.parametrize("source_hash,exists", [("invalid", True), (None, True), ("a" * 64, False)])
def test_invalid_reference_review_cannot_be_persisted(tmp_path, source_hash, exists):
    root, _ = fixture(tmp_path)
    before = (root / "governance/sources.lock.yaml").read_bytes()
    with module("catalog").Catalog(root) as catalog:
        with pytest.raises(module("ingest").ContractError, match="INVALID_REFERENCE_REVIEW"):
            catalog.mark_reference_reviewed("code-wait", source_hash, exists)
    assert (root / "governance/sources.lock.yaml").read_bytes() == before


def test_unreferenced_code_is_not_scheduled_or_ingested(tmp_path):
    root, _ = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card("waiting"))
    assert module("ingest").scan(root, {"source": "code-wait"})[1] == "unchanged"
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}
    assert not (root / ".build/task.json").exists()


def test_legacy_card_identity_is_not_used_as_a_filesystem_name(tmp_path):
    root, _ = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card("waiting:legacy", referenced=True))
    task = prepare(root)
    assert task["affected_cards"][0]["id"] == "waiting:legacy"
    assert (root / task["affected_cards"][0]["original_ref"]).is_file()


def test_trusted_history_yields_unique_location_advice_without_semantic_verdict(tmp_path):
    root, code = fixture(tmp_path)
    project = root.parents[1]
    for arguments in (["init"], ["config", "core.autocrlf", "false"], ["add", "."],
                      ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Synthetic baseline"]):
        subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    code.write_bytes(b"// New header\n" + code.read_bytes())
    task = prepare(root)
    assert task["source"]["previous_sha256"]
    proposals = json.loads((root / task["location_candidates_ref"]).read_bytes())["candidates"]
    assert len(proposals) == 1
    assert proposals[0]["proposed_reference"]["line_start"] == 2
    assert proposals[0]["same_fragment"] is True
    assert proposals[0]["requires_context_review"] is True
    assert not list((root / ".build/cards").iterdir())


def test_deleted_reviewed_code_can_retain_its_actual_historical_reference(tmp_path):
    root, code = fixture(tmp_path)
    registry_file = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(registry_file.read_bytes())
    resource = next(row for row in registry["resources"] if row["source_id"] == "code-wait")
    for field in ("processed_hash", "processed_exists", "processed_at", "source_commit"):
        resource.pop(field, None)
    registry_file.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_reference_reviewed("code-wait", hashlib.sha256(code.read_bytes()).hexdigest(), True)
    project = root.parents[1]
    for arguments in (["init"], ["config", "core.autocrlf", "false"], ["add", "."],
                      ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Reviewed source history"]):
        subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
    code.unlink()
    prepare(root)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    (root / ".build/cards/waiting.md").write_bytes(card(
        "waiting", referenced=True, body="Historical requirement and implementation reference; current source was removed."))
    result, phase = module("ingest").maintenance_check(root, {})
    assert phase == "passed", result
    receipt, phase = module("ingest").maintenance_commit(root, {})
    assert phase == "completed", receipt
    with module("catalog").Catalog(root) as catalog:
        source = catalog.get_file("code-wait")
        assert source["reference_review"]["exists"] is False
        assert source["reference_review"]["source_sha256"] is None
        assert source["reference_review"]["last_present_sha256"]
        assert source["processed_hash"] is None
        catalog.rebuild()
    checked, phase = module("ingest").check(root, {"formal": True})
    assert phase == "passed", checked
