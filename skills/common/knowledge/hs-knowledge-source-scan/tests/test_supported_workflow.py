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
        incoming = self.h.write(f".build/operations/{self.operation}/{node}-input.json",
            json.dumps({"mode": "candidate", "view_ref": self.state["view_ref"]}).encode())
        outgoing = f".build/operations/{self.operation}/{node}-report.json"
        result = subprocess.run([sys.executable, str(self.h.packages / "hs-knowledge-lint/scripts/cli.py"),
            "--knowledge-root", str(self.h.root), "--rules-digest", self.h.rules,
            "--input", str(self.h.root / incoming), "--output", str(self.h.root / outgoing)],
            capture_output=True, timeout=180)
        assert result.returncode == 0, (result.stdout, result.stderr)
        report = self.h.record(outgoing)
        assert report["status"] == "passed" and report["complete"]
        return outgoing

    def review(self, view=False):
        return self.call("change-plan", {
            "semantic_plan_ref": self.state["semantic_plan_ref"],
            **({"view_ref": self.state["view_ref"]} if view else {}),
            "reviewer_id": "synthetic-reviewer", "independent_context": self.current + "-fixture",
            "sampled_unit_ids": [self.state["unit"]["unit_id"]], "unreviewed_unit_ids": [],
            "reason": "Synthetic declared review data; this does not establish real host isolation.",
            "findings": [],
        }, "review")["data"]

    def produce(self, stop="complete"):
        self.node("scan_sources")
        self.state.update(self.call("source-scan", {}, "scan")["data"])
        scan = self.h.record(self.state["scan_ref"])
        assert len(scan["units"]) == 1 and scan["units"][0]["change"] == "new"
        self.state["unit"] = scan["units"][0]
        unit_id = self.state["unit"]["unit_id"]
        self.take("scanned")
        self.node("prepare_material")
        self.state.update(self.call("source-scan", {"scan_ref": self.state["scan_ref"]}, "prepare")["data"])
        material = self.h.record(self.state["material_ref"])
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
        self.take("planned")
        self.node("review_plan")
        self.state["plan_review"] = self.review()
        self.take("reviewed")
        self.node("materialize_view")
        # Authoring the draft and binding it are planned P4 work, not an edit to
        # an existing card, frozen view, source lock, report, journal or index.
        candidate = self.h.write(f".build/operations/{self.operation}/authored-rule.md", self.h.card("rule", bundle))
        self.state.update(self.call("change-plan", {
            "v3_required": True, "semantic_plan_ref": self.state["semantic_plan_ref"], "bundle_ref": material["bundle_ref"],
            "decisions": [{"candidate_id": unit_id, "decision": "create", "reason": "Planned P4 authoring",
                "card_inputs": [candidate]}],
        })["data"])
        self.state.update(self.call("view-materialize", {"plan_ref": self.state["plan_ref"]})["data"])
        self.take("ready")
        self.node("review_content")
        self.state["content_review"] = self.review(view=True)
        self.take("reviewed")
        self.node("lint_preflight")
        self.lint("lint_preflight")
        self.take("passed")
        self.node("inspect_candidate")
        inspected = self.call("candidate-inspect", {"view_ref": self.state["view_ref"]})
        assert inspected["phase"] == "manual_ready", inspected
        self.take("manual_ready")
        self.node("lint_view")
        self.state["lint_ref"] = self.lint("lint_view")
        self.take("passed")
        self.node("record_ingest")
        self.state.update(self.call("source-scan", {
            "scan_ref": self.state["scan_ref"], "material_ref": self.state["material_ref"],
            "semantic_plan_ref": self.state["semantic_plan_ref"], "plan_ref": self.state["plan_ref"],
            "view_ref": self.state["view_ref"], "lint_ref": self.state["lint_ref"],
            "skip_sample": self.state["plan_review"]["skip_sample"],
            "dispositions": [{"unit_id": unit_id, "action": "create", "reason": "Planned source outcome",
                "observed_fingerprint": self.state["unit"]["observed_fingerprint"],
                "adopted_fingerprint": self.state["unit"]["observed_fingerprint"], "progress": "completed",
                "card_refs": ["rule"], "claim_refs": ["rule#rule-claim"]}],
        }, "record")["data"])
        self.take("recorded")
        self.node("apply_view")
        applied = self.call("apply", {"v3_required": True, "view_ref": self.state["view_ref"],
            "ingest_record_ref": self.state["ingest_record_ref"], "lint_report_ref": self.state["lint_ref"],
            "content_review_ref": self.state["content_review"]["content_review_ref"]})
        assert applied["phase"] == "committed", applied
        self.state.update(applied["data"])
        self.take("applied")
        if stop == "applied":
            return self.state
        return self.finish(stop)

    def finish(self, stop="complete"):
        if self.current == "rebuild_index":
            self.node("rebuild_index")
            self.state.update(self.call("index-build", {}, "build")["data"])
            self.take("built")
        if stop == "built":
            return self.state
        self.node("query_regression")
        result = self.call("query-regression", {"v3_required": True,
            "apply_result_ref": self.state["apply_result_ref"], "generation_ref": self.state["generation_ref"],
            "expected_active": self.state["expected_active"]})
        assert result["phase"] == "checked" and result["data"]["passed"] and result["data"]["activated"], result
        self.state["regression_ref"] = result["data"]["report_ref"]
        self.take("checked")
        assert self.current == "__end__"
        return self.state

    def scan_new_run(self, operation):
        self.current = self.workflow["entry_node"]
        self.node("scan_sources")
        result = self.h.run("source-scan", {"operation_id": operation}, "scan")["data"]
        inventory = self.h.record(result["scan_ref"])
        return result, inventory

    def protected_bytes(self):
        refs = ["logs/operations/" + self.operation + "/journal.json", self.state["apply_result_ref"],
            "logs/ingest/" + self.operation + ".yaml", "governance/sources.lock.yaml"]
        refs += [p.relative_to(self.h.root).as_posix() for p in (self.h.root / "knowledge").rglob("*.md")]
        return {ref: (self.h.root / ref).read_bytes() for ref in refs}


PLANNED_DOCUMENT_NODES = [
    "scan_sources", "prepare_material", "plan_change", "review_plan",
    "materialize_view", "review_content", "lint_preflight", "inspect_candidate",
    "lint_view", "record_ingest", "apply_view", "rebuild_index", "query_regression",
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


@pytest.mark.parametrize(("stop", "resume_exit", "next_node", "prefix_count"), [
    ("applied", "resume_index", "rebuild_index", 11),
    ("built", "resume_queries", "query_regression", 12),
])
def test_supported_p7_stop_resumes_existing_exit_without_reapplying(
        planned_flow, stop, resume_exit, next_node, prefix_count):
    flow = planned_flow
    flow.produce(stop)
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count]
    assert flow.current == next_node
    protected = flow.protected_bytes()
    journal = flow.h.record("logs/operations/" + flow.operation + "/journal.json")
    assert journal["status"] == "committed"
    if stop == "built":
        assert flow.state["expected_active"] is None  # no initial generation in this fixture
        assert flow.h.record(flow.state["generation_ref"])["expected_active"] is None
    scan_result, _ = flow.scan_new_run("resume-check-" + stop)
    assert scan_result["actionable_unit_ids"] == []
    pending = next(row for row in scan_result["finalization_pending"] if row["operation_id"] == flow.operation)
    assert pending["next_action"] == ("rebuild_index" if stop == "applied" else "resume_queries")
    # The named exits already existed before this fix; this is a normal saved
    # stop, not a journal edit, an invented route or replay of completed nodes.
    flow.take(resume_exit)
    assert flow.current == next_node
    flow.finish()
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count] + ["scan_sources"] + PLANNED_DOCUMENT_NODES[prefix_count:]
    assert flow.trace.count("apply_view") == flow.trace.count("record_ingest") == 1
    assert flow.trace.count("rebuild_index") == 1
    assert flow.protected_bytes() == protected
    status = flow.h.run("source-scan", {"operation_id": "saved-stop-status", "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert {row["stage"] for row in status["facts"]} >= {"plan", "content_review", "lint", "apply", "index", "regression", "activation"}
