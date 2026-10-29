"""Planned public document nodes in graph order, with synthetic review records.

These are isolated CLI/transition checks, not an OpenFlow host or role-isolation
acceptance. Mid-run card/index/log edits and no-P6 shortcut helpers are excluded.
"""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


class SupportedDocumentFlow:
    """Author fixtures, then call every applicable document node in graph order."""

    def __init__(self, harness, workflow, operation="planned"):
        self.h = harness
        self.workflow = workflow
        self.nodes = {row["id"]: row for row in workflow["nodes"]}
        self.operation = operation
        self.current = workflow["entry_node"]
        self.trace = []
        self.state = {}
        self.h.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement for this workflow.\n")

    def node(self, name):
        assert self.current == name, (self.current, name)
        self.trace.append(name)

    def take(self, exit_id):
        matches = [edge for edge in self.nodes[self.current]["exits"] if edge["id"] == exit_id]
        assert len(matches) == 1, (self.current, exit_id)
        self.current = matches[0]["target"]

    def call(self, slug, request, action=None):
        return self.h.run(slug, {"operation_id": self.operation, **request}, action)

    def lint(self, node):
        request = {
            "semantic_plan_ref": self.state["semantic_plan_ref"], "view_ref": self.state["view_ref"],
            "operation_id": self.operation,
            "reviewer_id": "synthetic-reviewer", "independent_context": "P5-synthetic-fixture",
            "sampled_unit_ids": [self.state["unit"]["unit_id"]], "unreviewed_unit_ids": [],
            "reason": "Synthetic declared review data; this does not establish real host isolation.",
            "findings": [],
        }
        incoming = self.h.write(f".build/operations/{self.operation}/{node}-input.json", json.dumps(request).encode())
        outgoing = f".build/operations/{self.operation}/{node}-report.json"
        completed = subprocess.run([sys.executable, str(self.h.packages / "hs-knowledge-lint/scripts/cli.py"),
            "--knowledge-root", str(self.h.root), "--rules-digest", self.h.rules, "--action", "review",
            "--input", str(self.h.root / incoming), "--output", str(self.h.root / outgoing)], capture_output=True, check=False)
        assert completed.returncode == 0, (completed.stdout, completed.stderr, self.h.record(outgoing))
        report = self.h.record(outgoing)
        assert report["status"] == "passed" and report["complete"]
        assert report["scope"]["kind"] == "full" and report["data"]["full_scope"] is True
        self.state["content_review"] = {"content_review_ref": report["data"]["content_review_ref"]}
        return outgoing

    def produce(self, stop="complete"):
        self.node("prepare_sources")
        prepared = self.call("source", {})
        assert prepared["phase"] == "prepared"
        self.state.update(prepared["data"])
        scan = self.h.record(self.state["scan_ref"])
        assert len(scan["units"]) == 1 and scan["units"][0]["change"] == "new"
        self.state["unit"] = scan["units"][0]
        unit_id = self.state["unit"]["unit_id"]
        material = self.h.record(self.state["material_ref"])
        assert material["scan_ref"] == self.state["scan_ref"]
        assert material["scan_digest"] == scan["digest"]
        assert material["unit_ids"] == [unit_id]
        bundle = self.h.record(material["bundle_ref"])
        self.take("prepared")
        self.node("plan_change")
        self.state.update(self.call("change-plan", {
            "scan_ref": self.state["scan_ref"], "material_ref": self.state["material_ref"], "author_id": "synthetic-author",
            "units": [{"unit_id": unit_id, "outcome": "content", "reason": "New synthetic document rule"}],
            "claim_changes": [{"unit_ids": [unit_id], "card_id": "rule", "claim_id": "rule-claim", "action": "create",
                "before": None, "after": "Synthetic fixture statement.", "conditions": "Synthetic document guidance",
                "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}],
                "preserved": "No previous card", "reason": "New synthetic document rule"}],
            "card_actions": [{"card_id": "rule", "decision": "create", "author_id": "synthetic-author",
                "unit_ids": [unit_id], "reason": "New synthetic document rule"}],
            "target_queries": [{"id": "rule-query", "query": "Synthetic", "purpose": "guidance",
                "required": ["rule"], "expected_claim_ids": ["rule#rule-claim"]}],
        }, "plan")["data"])
        self.take("content_planned")
        self.node("materialize_view")
        candidate = self.h.write(f".build/operations/{self.operation}/authored-rule.md", self.h.card("rule", bundle))
        self.state.update(self.call("view-materialize", {
            "semantic_plan_ref": self.state["semantic_plan_ref"],
            "decisions": [{"candidate_id": unit_id, "decision": "create", "reason": "Planned P4 authoring",
                "card_inputs": [candidate]}],
        })["data"])
        self.take("ready")
        if stop == "materialized":
            return self.state
        self.node("lint_view")
        self.state["lint_ref"] = self.lint("lint_view")
        self.take("passed")
        if stop == "reviewed":
            return self.state
        self.node("record_ingest")
        self.state.update(self.call("source", {
            "scan_ref": self.state["scan_ref"], "material_ref": self.state["material_ref"],
            "semantic_plan_ref": self.state["semantic_plan_ref"], "plan_ref": self.state["plan_ref"],
            "view_ref": self.state["view_ref"], "lint_ref": self.state["lint_ref"],
            "disposition_preview_ref": self.state["disposition_preview_ref"],
        }, "record")["data"])
        self.take("recorded")
        if stop == "recorded":
            return self.state
        return self.finish(stop)

    def finish(self, stop="complete"):
        self.node("apply_view")
        blocker = None
        if stop in {"applied", "built"}:
            blocker = "artifacts/indexes/local" if stop == "applied" else f"logs/publications/{self.operation}/regression"
            self.h.write(blocker, b"Synthetic IO blocker; no valid index or report is modified.")
        request = {"operation_id": self.operation, "view_ref": self.state["view_ref"],
                   "ingest_record_ref": self.state["ingest_record_ref"], "lint_report_ref": self.state["lint_ref"],
                   "content_review_ref": self.state["content_review"]["content_review_ref"]}
        response = self.h.run("apply", request, "batch", expected=2 if blocker else 0)
        if blocker:
            (self.h.root / blocker).unlink()
            journal = self.h.record(f".build/operations/{self.operation}/transaction/journal.json")
            assert journal["status"] == "committed", response
            self.state["apply_result_ref"] = journal["result_ref"]
            if stop == "built":
                built = self.h.record(f".build/operations/{self.operation}/batch-build.json")
                self.state.update({"generation_ref": built["generation_ref"], "expected_active": built["expected_active"]})
            return self.state
        assert response["phase"] == "completed" and response["data"]["batch_complete"] is True, response
        assert response["data"]["passed"] and response["data"]["activated"], response
        self.state.update(response["data"])
        self.state["regression_ref"] = response["data"]["report_ref"]
        self.take("completed")
        assert self.current == "__end__"
        return self.state

    def scan_new_run(self, operation):
        self.current = self.workflow["entry_node"]
        self.node("prepare_sources")
        response = self.h.run("source", {"operation_id": operation})
        assert response["phase"] == "unchanged"
        result = response["data"]
        assert "material_ref" not in result
        inventory = self.h.record(result["scan_ref"])
        return result, inventory

    def protected_bytes(self):
        refs = ["logs/publications/" + self.operation + "/manifest.json",
            "logs/publications/" + self.operation + "/apply-result.json",
            "logs/ingest/" + self.operation + ".yaml", "governance/sources.lock.yaml"]
        refs += [p.relative_to(self.h.root).as_posix() for p in (self.h.root / "knowledge").rglob("*.md")]
        return {ref: (self.h.root / ref).read_bytes() for ref in refs}


PLANNED_DOCUMENT_NODES = [
    "prepare_sources", "plan_change", "materialize_view",
    "lint_view", "record_ingest", "apply_view",
]


@pytest.fixture
def planned_flow(harness):
    # Isolate workspace discovery from the developer's actual business config.
    (harness.base / "config.yml").write_text(yaml.safe_dump({
        "knowledge_roots": {"wifi": harness.root.name}, "repos": [],
    }), encoding="utf-8")
    root = Path(__file__).resolve().parents[5]
    workflow = yaml.safe_load((root / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml").read_bytes())
    return SupportedDocumentFlow(harness, workflow)


def test_complete_planned_document_nodes_then_three_noop_runs(planned_flow):
    flow = planned_flow
    flow.produce()
    assert flow.trace == PLANNED_DOCUMENT_NODES
    assert flow.current == "__end__"
    protected = flow.protected_bytes()
    indexes = {p.relative_to(flow.h.root).as_posix(): p.read_bytes()
               for p in (flow.h.root / "artifacts/indexes").rglob("*") if p.is_file()}
    original_records = sorted((flow.h.root / "logs/ingest").glob("*.yaml"))
    assert len(original_records) == 1
    for attempt in range(3):
        result, inventory = flow.scan_new_run("complete-noop-" + str(attempt))
        assert inventory["complete"] is True
        assert [row["change"] for row in inventory["units"]] == ["unchanged"]
        assert result["actionable_unit_ids"] == []
        assert result["finalization_pending"] == []
        flow.take("unchanged")
        assert flow.current == "__end__"
    assert flow.protected_bytes() == protected
    assert {p.relative_to(flow.h.root).as_posix(): p.read_bytes()
            for p in (flow.h.root / "artifacts/indexes").rglob("*") if p.is_file()} == indexes
    assert sorted((flow.h.root / "logs/ingest").glob("*.yaml")) == original_records


@pytest.mark.parametrize("stop", ["applied", "built"])
def test_explicit_current_p7_stop_resumes_without_p1_history_route(planned_flow, stop):
    next_node, prefix_count = "apply_view", 6
    flow = planned_flow
    flow.produce(stop)
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count]
    assert flow.current == next_node
    protected = flow.protected_bytes()
    journal = flow.h.record(".build/operations/" + flow.operation + "/transaction/journal.json")
    assert journal["status"] == "committed"
    if stop == "built":
        assert flow.state["expected_active"] is None  # no initial generation in this fixture
        assert flow.h.record(flow.state["generation_ref"])["expected_active"] is None
    scan_result = flow.h.run("source", {"operation_id": "resume-check-" + stop}, "scan")["data"]
    assert scan_result["actionable_unit_ids"] == []
    assert scan_result["finalization_pending"] == []
    assert scan_result["execution_history"] == {"status": "not_inspected"}
    details = flow.h.run("source", {"operation_id": "explicit-stop", "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert details["completion"]["published"] is True
    assert details["completion"]["batch_complete"] is False
    assert details["completion"]["next_action"] == "resume_batch"
    # Resume the explicitly known current P7, without a new Workflow adopting it.
    assert flow.current == next_node
    flow.finish()
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count] + ["apply_view"]
    assert flow.trace.count("apply_view") == 2 and flow.trace.count("record_ingest") == 1
    assert flow.protected_bytes() == protected
    status = flow.h.run("source", {"operation_id": "saved-stop-status", "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert {row["stage"] for row in status["facts"]} == {"publication", "publication_completion"}
    assert status["completion"]["retrieval"]["complete"] is True
    assert status["completion"]["cleanup"]["status"] == "done"
