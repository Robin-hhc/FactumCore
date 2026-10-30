"""Manual public Skill calls without a workflow, registry or passed-step tickets."""

from support import pipeline as FIXTURE
from support.manual import ManualPipeline
import base64
import json
import subprocess

import yaml






def test_manual_document_scan_record_apply_index_query_keeps_business_checks(tmp_path):
    p = ManualPipeline(tmp_path)
    p.catalog_path.unlink()
    (p.root / ".isolated-knowledge-fixture").unlink()
    original = b"# Source\nCapture marker is a documented rule.\n"
    source_path = "docs-raw/specs/wifi/raw-source.md"
    p.write(source_path, original)
    p.write("knowledge/index.md", "# Knowledge\n\n当前正式业务卡为空。保留项目根说明。\n".encode())
    p.write("knowledge/rules/index.md", "# Rules\n\n当前没有已落位的正式业务卡。保留类型说明。\n".encode())

    def formal_state():
        return {path.relative_to(p.root).as_posix(): FIXTURE.sha(path.read_bytes())
                for path in p.root.rglob("*") if path.is_file()
                and path.relative_to(p.root).parts[0] != ".build"}

    baseline = formal_state()
    public_call, staged_calls = p.call, []

    def staged_call(slug, request, action=None, expected=0):
        response = public_call(slug, request, action, expected)
        assert formal_state() == baseline, (slug, action)
        staged_calls.append((slug, action))
        return response

    # Each real P1-P5 public call may write only the disposable stage tree.
    p.call = staged_call
    prepared = p.call("knowledge-source", {"operation_id": "manual"}, "run")
    assert prepared["phase"] == "prepared"
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    scan = p.record(scan_ref)
    bundle_ref = p.record(material_ref)["bundle_ref"]
    bundle = p.record(bundle_ref)
    view_ref = p.view("manual", bundle_ref, "manual-rule", p.card("manual-rule", bundle),
        scan_ref=scan_ref, material_ref=material_ref,
        queries=[{"id": "find-manual", "query": "capture", "required": ["manual-rule"]}])
    p.review("manual", view_ref)
    unit = scan["units"][0]
    record_ref = p.call("knowledge-record", {
        "operation_id": "manual", "view_ref": view_ref,
    })["data"]["ingest_record_ref"]
    assert "lint_ref" not in p.record(record_ref)
    assert {slug for slug, _ in staged_calls} >= {"knowledge-source",
        "knowledge-change-plan", "knowledge-view-materialize", "knowledge-review"}
    assert ("knowledge-record", None) in staged_calls
    # A new operation cannot mistake the pending P5 record for published work.
    fresh = p.call("knowledge-source", {"operation_id": "fresh-before-p7"}, "scan")["data"]
    fresh_unit = p.record(fresh["scan_ref"])["units"][0]
    assert fresh_unit["path"] == source_path and fresh_unit["change"] == "new"
    assert fresh["actionable_unit_ids"] == [fresh_unit["unit_id"]]
    assert fresh["execution_history"] == {"status": "not_inspected"}
    p.call = public_call
    applied = p.call("knowledge-apply", {
        "operation_id": "manual", "view_ref": view_ref, "ingest_record_ref": record_ref,
    }, "batch")
    assert applied["phase"] == "completed" and applied["data"]["activated"] is True
    assert applied["data"]["published"] is True and applied["data"]["batch_complete"] is True
    assert (p.root / "knowledge/rules/manual-rule.md").is_file()
    root_nav = (p.root / "knowledge/index.md").read_text(encoding="utf-8")
    rule_nav = (p.root / "knowledge/rules/index.md").read_text(encoding="utf-8")
    assert "当前正式业务卡为空。" not in root_nav and "保留项目根说明。" in root_nav
    assert "当前没有已落位的正式业务卡。" not in rule_nav and "保留类型说明。" in rule_nav
    assert "manual-rule.md" in rule_nav
    assert not (p.root / view_ref).exists()
    assert "acceptance" not in p.record("logs/ingest/manual.yaml")
    assert "proof_ref" not in p.record(applied["data"]["apply_result_ref"])
    result = p.call("knowledge-query", {"operation_id": "search-manual", "query": "capture"}, "search")["data"]
    assert result["generation_ref"] == applied["data"]["generation_ref"]
    assert p.record("artifacts/indexes/local/active.json")["generation_ref"] == result["generation_ref"]
    assert [row["card_id"] for row in result["matches"]] == ["manual-rule"]
    read = p.call("knowledge-query", {
        "operation_id": "read-manual", "receipt_ref": result["receipt_ref"], "card_id": "manual-rule",
    }, "read")["data"]
    assert read["card_digest"] == result["matches"][0]["card_digest"]
    assert (p.root / source_path).read_bytes() == original
    assert not (p.root / "logs/workflows").exists()
    assert p.call("knowledge-lint", {})["status"] == "passed"
    status = p.call("knowledge-source", {
        "operation_id": "manual-status", "target_operation_id": "manual",
    }, "status")["data"]["operations"]
    assert len(status) == 1 and status[0]["gaps"] == []
    assert {fact["stage"] for fact in status[0]["facts"]} == {"publication", "publication_completion"}
    assert status[0]["completion"]["status"] == "complete"
    assert status[0]["completion"]["published"] is True
    assert status[0]["completion"]["batch_complete"] is True
    manifest = p.record(applied["data"]["publication_ref"])
    assert manifest["processing_record"]["path"] == "logs/ingest/manual.yaml"
    assert manifest["apply_result"]["status"] == "committed"
    assert any(row["path"] == "knowledge/rules/manual-rule.md" for row in manifest["files"])
    assert p.record("logs/ingest/manual.yaml")["status"] == "applied"
    repeated = p.call("knowledge-source", {"operation_id": "manual-repeat"}, "scan")
    assert p.record(repeated["data"]["scan_ref"])["units"][0]["change"] == "unchanged"
    original_record = (p.root / "logs/ingest/manual.yaml").read_bytes()
    correction_scan_ref = p.call("knowledge-source", {
        "operation_id": "manual-correction",
    }, "scan")["data"]["scan_ref"]
    correction_scan = p.record(correction_scan_ref)
    correction_material_ref = p.call("knowledge-source", {
        "operation_id": "manual-correction", "scan_ref": correction_scan_ref,
        "unit_ids": [unit["unit_id"]], "candidate_card_ids": ["manual-rule"],
    }, "prepare")["data"]["material_ref"]
    corrected_bundle_ref = p.record(correction_material_ref)["bundle_ref"]
    correction_view = p.view("manual-correction", corrected_bundle_ref, "manual-rule", p.card(
        "manual-rule", p.record(corrected_bundle_ref), "Capture marker has an explicit user-requested correction.",
    ), decision="update", scan_ref=correction_scan_ref, material_ref=correction_material_ref,
        queries=[{"id": "find-correction", "query": "capture", "required": ["manual-rule"]}])
    p.review("manual-correction", correction_view)
    corrected_unit = correction_scan["units"][0]
    assert corrected_unit["change"] == "unchanged"
    correction_record = p.call("knowledge-record", {
        "operation_id": "manual-correction", "view_ref": correction_view,
    })["data"]["ingest_record_ref"]
    corrected = p.call("knowledge-apply", {
        "operation_id": "manual-correction", "view_ref": correction_view, "ingest_record_ref": correction_record,
    }, "batch")
    assert corrected["phase"] == "completed" and corrected["data"]["activated"] is True
    corrected_result = p.call("knowledge-query", {
        "operation_id": "manual-corrected-search", "query": "capture",
    }, "search")["data"]
    assert corrected_result["generation_ref"] == corrected["data"]["generation_ref"]
    assert p.record("artifacts/indexes/local/active.json")["generation_ref"] == corrected_result["generation_ref"]
    assert [row["card_id"] for row in corrected_result["matches"]] == ["manual-rule"]
    corrected_match = corrected_result["matches"][0]
    assert corrected_match["card_digest"] != read["card_digest"]
    assert (p.root / "logs/ingest/manual.yaml").read_bytes() == original_record
    assert (p.root / source_path).read_bytes() == original
    # Format/reference lint remains independently callable and rejects bad content.
    card = p.root / "knowledge/rules/manual-rule.md"
    card.write_bytes(card.read_bytes().replace(b"lifecycle: stable", b"lifecycle: invalid-state"))
    request = p.base / "lint.json"
    output = p.base / "lint-result.json"
    request.write_text("{}", encoding="utf-8")
    lint = subprocess.run([
        *p.command("knowledge-lint"),
        "--knowledge-root", str(p.root), "--input", str(request), "--output", str(output),
    ], capture_output=True, timeout=180)
    assert lint.returncode != 0
    assert json.loads(output.read_bytes())["status"] != "passed"


def test_manual_code_check_apply_material_index_and_query_without_registration(tmp_path, monkeypatch):
    from support.stages import lint_code as fixture
    monkeypatch.setenv("HIMATE_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests()
    environment.setUp()
    try:
        # Reuse only the isolated Git/source/material fixture. All task calls
        # below use the unregistered public manual CLI rather than its harness.
        p = ManualPipeline.__new__(ManualPipeline)
        p.base, p.root, p.skills = environment.workspace, environment.root, fixture.SKILLS
        p.sequence = 0
        environment.catalog_path.unlink()
        (p.root / ".isolated-knowledge-fixture").unlink()
        materials = {
            "logs/evidence/build.bin": b"synthetic fixture build only\n",
            "logs/evidence/runtime.log": b"synthetic manual runtime observation\n",
        }
        for relative, raw in materials.items():
            p.write(relative, raw)
        context = p.record(environment.context_ref)
        context["build_evidence"]["artifacts"] = [
            {"path": relative, "sha256": fixture.digest(raw)} for relative, raw in materials.items()
        ]
        environment.save(environment.context_ref, fixture.seal(context))
        context = p.record(environment.context_ref)
        row = environment.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["build-support", "runtime-support"]
        card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(card).decode(), final_digest=fixture.digest(card))
        environment.view = fixture.seal(environment.view)
        environment.save(environment.view_ref, environment.view)
        material_evidence = [
            {"requirement": requirement, "path": relative, "sha256": fixture.digest(materials[relative])}
            for requirement, relative in (("build-support", "logs/evidence/build.bin"),
                                          ("runtime-support", "logs/evidence/runtime.log"))
        ]
        environment.evidence[0]["verification_evidence"] = material_evidence
        environment.sign_report("local")
        checked = p.call("knowledge-lint", {
            "operation_id": "op", "view_ref": environment.view_ref,
            "context_ref": environment.context_ref, "semantic_report_ref": environment.report_ref,
        }, "code-check")
        assert checked["data"]["check_status"] == "passed"
        proof = p.record(checked["data"]["local_check_ref"])
        inputs = {"code_checkout": {
            "configuration": str(environment.workspace / "config.yml"),
            "config_digest": context["config_digest"],
            "repos": {"wifi-code": {"root": str(environment.code), "commit": environment.head}},
        }}
        assert p.call("knowledge-lint", {"view_ref": environment.view_ref, "inputs": inputs})["status"] == "passed"
        applied = p.call("knowledge-apply", {
            "operation_id": "op", "view_ref": environment.view_ref, "check_inputs": inputs,
        })
        assert applied["phase"] == "committed"
        assert (environment.code / "src/wifi.c").read_bytes() == environment.source
        # An index consumes the actual material snapshot, not a passed report.
        code_context = {"config_digest": context["config_digest"], "code_identity": proof["code_identity"],
                        "claim_evidence": {"c1": material_evidence}}
        for relative in (environment.context_ref, environment.report_ref, checked["data"]["local_check_ref"]):
            (p.root / relative).unlink()
        built = p.call("knowledge-index-build", {
            "operation_id": "manual-code-index", "code_contexts": {"fixture-code-flow": code_context},
        })["data"]
        manifest = p.record(built["generation_ref"])
        assert manifest["code_contexts"] == {"fixture-code-flow": code_context}
        assert manifest["qualifications"] == {}
        regression = p.call("knowledge-query-regression", {
            "operation_id": "manual-code-regression", "generation_ref": built["generation_ref"],
            "expected_active": built["expected_active"],
            "cases": [{"id": "manual-code", "query": "Fixture", "purpose": "implementation",
                       "context": context["target"], "required": ["fixture-code-flow"]}],
        })
        assert regression["data"]["activated"]
        request = {"operation_id": "manual-code-query", "query": "Fixture", "purpose": "implementation",
                   "context": context["target"]}
        searched = p.call("knowledge-query", request, "search")["data"]
        assert searched["matches"][0]["card_id"] == "fixture-code-flow"
        read = p.call("knowledge-query", {
            "operation_id": "manual-code-read", "receipt_ref": searched["receipt_ref"],
            "card_id": "fixture-code-flow",
        }, "read")["data"]
        assert read["card_digest"] == searched["matches"][0]["card_digest"]
        p.write("logs/evidence/runtime.log", b"changed runtime observation\n")
        changed = p.call("knowledge-query", request, "search")["data"]
        assert changed["matches"] == []
        assert not environment.catalog_path.exists() and not (p.root / "logs/workflows").exists()
    finally:
        environment.doCleanups()
