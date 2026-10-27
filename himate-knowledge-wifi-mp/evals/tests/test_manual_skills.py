"""Manual public Skill calls without a workflow, registry or passed-step tickets."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


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
        # OpenFlow metadata is irrelevant to the business CLI, even if malformed.
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
