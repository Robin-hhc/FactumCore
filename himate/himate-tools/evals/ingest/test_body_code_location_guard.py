"""Visible code locations require author review when a current reference moves."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


_support_spec = importlib.util.spec_from_file_location(
    "_body_location_lifecycle", Path(__file__).with_name("test_code_evidence_lifecycle.py"))
_support = importlib.util.module_from_spec(_support_spec)
_support_spec.loader.exec_module(_support)
card, confirm, fixture, parsed = (_support.card, _support.confirm, _support.fixture, _support.parsed)
from contracts import module, write_plan


def confirm_source(root, source):
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": source})
    assert phase == "prepared", task
    write_plan(root, [])
    result, phase = ingest.maintenance_check(root, {})
    assert phase == "passed", result
    result, phase = ingest.maintenance_commit(root, {"reason": "Checked the current evidence and body."})
    assert phase == "completed", result


def forge_legacy_mechanical_receipt(root, task):
    """Simulate an older prepare receipt; its public digest is not authorization."""
    task = copy.deepcopy(task)
    task.pop("body_location_reviews", None)
    task.update(mode="mechanical", mechanical_check_ref=".build/maintenance-mechanical-check.json")
    with module("catalog").Catalog(root) as catalog:
        catalog.set_maintenance_input(task)
    (root / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    value = parsed(root)
    metadata = copy.deepcopy(value["metadata"])
    metadata["code_ref"][0].update(line_start=3, line_end=5)
    draft = ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
             + "---\n" + value["body"]).encode("utf-8")
    (root / ".build/cards/waiting.md").write_bytes(draft)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    payload = {"input": task, "plan_sha256": sha((root / ".build/plan.md").read_bytes()),
               "cards": [("waiting", "knowledge/waiting.md", sha(draft))], "deleted": []}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    (root / task["mechanical_check_ref"]).write_text(
        json.dumps({"mode": "mechanical", "sha256": sha(encoded)}), encoding="utf-8")


def test_relocated_reference_with_chinese_body_location_requires_semantic_review(tmp_path):
    root, code = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card("Host `code-wait` 第1–3行说明等待行为。"))
    confirm(root)
    original = (root / "knowledge/waiting.md").read_bytes()
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    assert task["evidence_states"]["waiting"][0]["status"] == "relocated"
    assert task["body_location_reviews"]["waiting"][0]["source_id"] == "code-wait"
    assert not (root / ".build/maintenance-mechanical-check.json").exists()
    assert not list((root / ".build/cards").iterdir())
    assert (root / "knowledge/waiting.md").read_bytes() == original


@pytest.mark.parametrize("body", [
    "See code/wifi/wait.c:1-3 for the current implementation.",
    "See `code\\wifi\\wait.c`#L1-L3.",
    "The `wait_reply()` function is at lines 1–3.",
    "`wait_reply` lines 1–3 implement waiting.",
    "{actual_path}:2 is the current return statement.",
    "`code-wait` 第2行返回等待状态。",
    "`code-wait` 第90–92行另有当前源码定位。",
])
def test_explicit_code_locations_conservatively_require_review(tmp_path, body):
    root, code = fixture(tmp_path)
    body = body.replace("{actual_path}", code.resolve().as_posix())
    (root / "knowledge/waiting.md").write_bytes(card(body))
    confirm(root)
    before = parsed(root)["body"]
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    assert task["body_location_reviews"]["waiting"]
    assert parsed(root)["body"] == before


@pytest.mark.parametrize("body", [
    "Wait for a reply; TID 0–7 is a separate value range.",
    "`doc-design` 第1–3行介绍设计，`wait_reply` 返回5。",
    "`wait_reply` 的文档见 `doc-design` 第1–3行。",
    "`wait_reply`: 3 is a value, not an explicit line locator.",
    "`code-waiter` 第1–3行不是本卡代码身份。",
    "`not_wait_reply` lines 1–3 identify a different symbol.",
])
def test_values_and_document_locations_do_not_disable_mechanical_repair(tmp_path, body):
    root, code = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card(body))
    confirm(root)
    before = parsed(root)["body"]
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "mechanical_prepared", task
    receipt, phase = module("ingest").maintenance_commit(root, {})
    assert phase == "completed" and receipt["mode"] == "mechanical", receipt
    assert parsed(root)["body"] == before


def test_real_host_device_chinese_locations_route_whole_card_to_review(tmp_path):
    root, code = fixture(tmp_path)
    host_id, device_id = "code-33c67638996be42e3f22", "code-34da92c8b51a2dc5a1e3"
    host, device = code.with_name("host.h"), code.with_name("device.h")
    host.write_bytes(b"// padding\n" * 472 + b"".join(
        f"#define HOST_VALUE_{i} {i}\n".encode() for i in range(12)))
    device.write_bytes(b"// padding\n" * 152 + b"#define DEVICE_VALUE 3\n")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("code", "code/wifi/host.h", source_id=host_id)
        catalog.register("code", "code/wifi/device.h", source_id=device_id)
    references = [{"code_id": host_id, "line_start": 473, "line_end": 484},
                  {"code_id": device_id, "line_start": 153, "line_end": 153}]
    body = f"Host `{host_id}` 第473–484行；Device `{device_id}` 第153行。"
    (root / "knowledge/waiting.md").write_bytes(card(body, references))
    confirm_source(root, host_id)
    before = (root / "knowledge/waiting.md").read_bytes()
    for source in (host, device):
        source.write_bytes(b"// inserted\n\n" + source.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": host_id})
    assert phase == "prepared" and task["mode"] == "semantic", task
    assert {row["source_id"] for row in task["body_location_reviews"]["waiting"]} == {host_id, device_id}
    assert {row["status"] for row in task["evidence_states"]["waiting"]} == {"relocated"}
    assert (root / "knowledge/waiting.md").read_bytes() == before


@pytest.mark.parametrize("body,expected", [("MAX_RETRY: 3 is the configured retry count.", "mechanical_prepared"),
                                          ("`MAX_RETRY` 第5行定义重试次数。", "prepared")])
def test_macro_selector_needs_a_line_cue_not_just_a_numeric_value(tmp_path, body, expected):
    root, code = fixture(tmp_path)
    code.write_bytes(code.read_bytes() + b"\n#define MAX_RETRY 3\n")
    references = [{"code_id": "code-wait", "line_start": 5, "line_end": 5,
                   "selector": {"kind": "macro", "name": "MAX_RETRY"}}]
    (root / "knowledge/waiting.md").write_bytes(card(body, references))
    confirm(root)
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == expected, task


def test_commit_rechecks_body_boundary_despite_a_valid_legacy_mechanical_receipt(tmp_path):
    root, code = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card("`code-wait` 第1–3行是当前实现。"))
    confirm(root)
    before = (root / "knowledge/waiting.md").read_bytes()
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, _ = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    forge_legacy_mechanical_receipt(root, task)
    with pytest.raises(module("ingest").ContractError, match="MECHANICAL_BODY_LOCATION"):
        module("ingest").maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == before


@pytest.mark.parametrize("body,expected", [("`code-wait` 第2行是等待逻辑。", "prepared"),
                                          ("`code-retry` 第1–3行是重试逻辑。", "mechanical_prepared")])
def test_mixed_fresh_and_relocated_card_uses_only_relocated_body_anchors(tmp_path, body, expected):
    root, code = fixture(tmp_path)
    second = code.with_name("retry.c")
    second.write_bytes(b"int retry_limit(void) {\n    return 3;\n}\n")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("code", "code/wifi/retry.c", source_id="code-retry")
    references = [{"code_id": "code-wait", "line_start": 1, "line_end": 3, "symbol": "wait_reply"},
                  {"code_id": "code-retry", "line_start": 1, "line_end": 3, "symbol": "retry_limit"}]
    (root / "knowledge/waiting.md").write_bytes(card(body, references))
    confirm(root)
    before = parsed(root)["body"]
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == expected, task
    assert {row["status"] for row in task["evidence_states"]["waiting"]} == {"relocated", "fresh"}
    assert [entry["id"] for entry in task["affected_cards"]] == ["waiting"]
    assert parsed(root)["body"] == before


def test_explicit_historical_snapshot_location_does_not_follow_current_file(tmp_path):
    root, code = fixture(tmp_path)
    content = code.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    relative = "artifacts/evidence/objects/" + digest + ".bin"
    retained = root / relative
    retained.parent.mkdir(parents=True)
    retained.write_bytes(content)
    registry_path = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(registry_path.read_bytes())
    registry["snapshots"].append({"snapshot_id": "retained-code", "source_id": "code-wait",
                                  "sha256": digest, "bytes": len(content),
                                  "recovery": {"method": "evidence_object", "path": relative}})
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    references = [{"code_id": "code-wait", "line_start": 1, "line_end": 3, "snapshot_id": "retained-code"}]
    (root / "knowledge/waiting.md").write_bytes(card("历史快照 `code-wait` 第1–3行保留旧实现。", references))
    original = (root / "knowledge/waiting.md").read_bytes()
    code.write_bytes(b"// current file moved\n\n" + content)
    result, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "unchanged", result
    checked, phase = module("ingest").check(root, {"formal": True})
    assert phase == "passed", checked
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_author_cannot_remove_fixed_body_review_reason(tmp_path):
    root, code = fixture(tmp_path)
    (root / "knowledge/waiting.md").write_bytes(card("`code-wait` 第1–3行是当前实现。"))
    confirm(root)
    original = (root / "knowledge/waiting.md").read_bytes()
    code.write_bytes(b"// header\n\n" + code.read_bytes())
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    task = json.loads((root / ".build/task.json").read_bytes())
    task.pop("body_location_reviews")
    (root / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    write_plan(root, [])
    with pytest.raises(module("ingest").ContractError, match="MAINTENANCE_TASK_CHANGED"):
        module("ingest").maintenance_commit(root, {"reason": "Cannot remove fixed review reasons."})
    assert (root / "knowledge/waiting.md").read_bytes() == original
