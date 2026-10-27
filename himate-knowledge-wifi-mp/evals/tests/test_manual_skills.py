"""Manual public Skill calls without a workflow, registry or passed-step tickets."""

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import yaml


SPEC = importlib.util.spec_from_file_location(
    "manual_pipeline_fixture", Path(__file__).parents[1] / "pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class ManualPipeline(FIXTURE.Pipeline):
    def call(self, slug, request, action=None, expected=0):
        self.sequence += 1
        incoming = self.base / f"manual-in-{self.sequence}.json"
        outgoing = self.base / f"manual-out-{self.sequence}.json"
        # Harness metadata is irrelevant to the business CLI, even if malformed.
        incoming.write_bytes(FIXTURE.canonical({**request, "workflow": "host-owned"}))
        command = [
            sys.executable, str(self.skills / ("hs-" + slug) / "scripts/cli.py"),
            "--input", str(incoming), "--output", str(outgoing),
            "--knowledge-root", str(self.root),
        ]
        if action:
            command += ["--action", action]
        process = subprocess.run(command, capture_output=True, timeout=180)
        response = json.loads(outgoing.read_bytes())
        assert process.returncode == expected, (response, process.stderr.decode(errors="replace"))
        assert "artifact_manifest_ref" not in response.get("data", {})
        return response


def test_manual_document_scan_record_apply_index_query_keeps_business_checks(tmp_path):
    p = ManualPipeline(tmp_path)
    p.catalog_path.unlink()
    (p.root / ".isolated-knowledge-fixture").unlink()
    original = b"# Source\nCapture marker is a documented rule.\n"
    p.write("docs-raw/specs/raw-source.md", original)
    scan_ref = p.call("knowledge-source-scan", {"operation_id": "manual"}, "scan")["data"]["scan_ref"]
    scan = p.record(scan_ref)
    bundle_ref = p.call("knowledge-source-capture", {
        "operation_id": "manual", "source_path": "docs-raw/specs/raw-source.md",
        "source_id": scan["units"][0]["source_id"],
    })["data"]["bundle_ref"]
    bundle = p.record(bundle_ref)
    view_ref = p.view("manual", bundle_ref, "manual-rule", p.card("manual-rule", bundle))
    unit = scan["units"][0]
    record_ref = p.call("knowledge-source-scan", {
        "operation_id": "manual", "scan_ref": scan_ref, "view_ref": view_ref,
        "dispositions": [{
            "unit_id": unit["unit_id"], "action": "create", "reason": "Manual test",
            "observed_fingerprint": unit["observed_fingerprint"],
            "adopted_fingerprint": unit["observed_fingerprint"],
            "progress": "completed", "card_refs": ["manual-rule"],
            "claim_refs": ["manual-rule#c1"],
        }],
    }, "record")["data"]["ingest_record_ref"]
    assert "lint_ref" not in p.record(record_ref)
    applied = p.call("knowledge-apply", {
        "operation_id": "manual", "view_ref": view_ref, "ingest_record_ref": record_ref,
    })
    assert applied["phase"] == "committed"
    assert "acceptance" not in p.record("logs/ingest/manual.yaml")
    assert "proof_ref" not in p.record(applied["data"]["apply_result_ref"])
    built = p.call("knowledge-index-build", {"operation_id": "build-manual"})["data"]
    checked = p.call("knowledge-query-regression", {
        "operation_id": "query-manual", "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "find-manual", "query": "capture", "required": ["manual-rule"]}],
    })
    assert checked["data"]["activated"]
    result = p.call("knowledge-query", {"operation_id": "search-manual", "query": "capture"}, "search")["data"]
    assert [row["card_id"] for row in result["matches"]] == ["manual-rule"]
    read = p.call("knowledge-query", {
        "operation_id": "read-manual", "receipt_ref": result["receipt_ref"], "card_id": "manual-rule",
    }, "read")["data"]
    assert read["card_digest"] == result["matches"][0]["card_digest"]
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == original
    assert not (p.root / "logs/workflows").exists()
    assert p.call("knowledge-lint", {})["status"] == "passed"
    status = p.call("knowledge-source-scan", {
        "operation_id": "manual-status", "target_operation_id": "manual",
    }, "status")["data"]["operations"]
    assert len(status) == 1 and status[0]["gaps"] == []
    assert {fact["stage"] for fact in status[0]["facts"]} >= {"scan", "record_formal", "apply"}
    repeated = p.call("knowledge-source-scan", {"operation_id": "manual-repeat"}, "scan")
    assert p.record(repeated["data"]["scan_ref"])["units"][0]["change"] == "unchanged"
    original_record = (p.root / "logs/ingest/manual.yaml").read_bytes()
    correction_scan_ref = p.call("knowledge-source-scan", {
        "operation_id": "manual-correction",
    }, "scan")["data"]["scan_ref"]
    correction_scan = p.record(correction_scan_ref)
    corrected_bundle_ref = p.call("knowledge-source-capture", {
        "operation_id": "manual-correction", "source_path": unit["path"], "source_id": unit["source_id"],
    })["data"]["bundle_ref"]
    correction_view = p.view("manual-correction", corrected_bundle_ref, "manual-rule", p.card(
        "manual-rule", p.record(corrected_bundle_ref), "Capture marker has an explicit user-requested correction.",
    ), decision="update")
    corrected_unit = correction_scan["units"][0]
    correction_record = p.call("knowledge-source-scan", {
        "operation_id": "manual-correction", "scan_ref": correction_scan_ref, "view_ref": correction_view,
        "dispositions": [{
            "unit_id": corrected_unit["unit_id"], "action": "update", "reason": "User requested a content correction",
            "observed_fingerprint": corrected_unit["observed_fingerprint"],
            "adopted_fingerprint": corrected_unit["observed_fingerprint"],
            "progress": "completed", "card_refs": ["manual-rule"], "claim_refs": ["manual-rule#c1"],
        }],
    }, "record")["data"]["ingest_record_ref"]
    corrected = p.call("knowledge-apply", {
        "operation_id": "manual-correction", "view_ref": correction_view, "ingest_record_ref": correction_record,
    })
    assert corrected["phase"] == "committed"
    rebuilt = p.call("knowledge-index-build", {"operation_id": "manual-correction-index"})["data"]
    assert p.call("knowledge-query-regression", {
        "operation_id": "manual-correction-query", "generation_ref": rebuilt["generation_ref"],
        "expected_active": rebuilt["expected_active"],
        "cases": [{"id": "find-correction", "query": "capture", "required": ["manual-rule"]}],
    })["data"]["activated"]
    corrected_match = p.call("knowledge-query", {
        "operation_id": "manual-corrected-search", "query": "capture",
    }, "search")["data"]["matches"][0]
    assert corrected_match["card_digest"] != read["card_digest"]
    assert (p.root / "logs/ingest/manual.yaml").read_bytes() == original_record
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == original
    # Format/reference lint remains independently callable and rejects bad content.
    card = p.root / "knowledge/rules/manual-rule.md"
    card.write_bytes(card.read_bytes().replace(b"lifecycle: stable", b"lifecycle: invalid-state"))
    request = p.base / "lint.json"
    output = p.base / "lint-result.json"
    request.write_text("{}", encoding="utf-8")
    lint = subprocess.run([
        sys.executable, str(p.skills / "hs-knowledge-lint/scripts/cli.py"),
        "--knowledge-root", str(p.root), "--input", str(request), "--output", str(output),
    ], capture_output=True, timeout=180)
    assert lint.returncode != 0
    assert json.loads(output.read_bytes())["status"] != "passed"


def test_manual_code_check_apply_material_index_and_query_without_registration(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "manual_code_fixture",
        FIXTURE.REPO / "skills/common/knowledge/hs-knowledge-local-check/tests/test_public_code_gate.py",
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    monkeypatch.setenv("HIMATE_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests(methodName="test_signed_positive_support_then_apply_and_verify")
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
        checked = p.call("knowledge-local-check", {
            "operation_id": "op", "view_ref": environment.view_ref,
            "context_ref": environment.context_ref, "semantic_report_ref": environment.report_ref,
        })
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
