"""Test-only adapters preserve old behavior assertions at the new public entries."""

import importlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("_p7_original_pipeline", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/pipeline.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
canonical, sha = original.canonical, original.sha


def map_call(slug, action):
    full = slug.startswith("hs-")
    name = slug.removeprefix("hs-")
    if name == "knowledge-index-build":
        name = "knowledge-apply"
        action = {None: "index-build", "build": "index-build", "verify": "index-verify", "activate": "index-activate"}.get(action, action)
    elif name == "knowledge-query-regression":
        name = "knowledge-apply"
        action = "regression-verify" if action == "verify" else "regression"
    elif name == "knowledge-source-capture":
        name = "knowledge-source"
        action = "capture" if action in {None, "run"} else action
    elif name == "knowledge-publish-handoff":
        name = "knowledge-apply"
        action = "verify-submission" if action == "verify-submission" else "prepare-submission"
    elif name == "knowledge-recover":
        name = "knowledge-apply"
    elif name == "knowledge-source-scan":
        name = "knowledge-source"
        action = action or "scan"
    elif name == "knowledge-source-prepare":
        name = "knowledge-source"
        action = action or "prepare"
    return ("hs-" if full else "") + name, action


class Pipeline(original.Pipeline):
    def command(self, slug):
        # These scenarios explicitly supply trust adapters and isolated fault
        # capabilities as business inputs; no Skill installation is described.
        return [*super().command(slug), "--catalog", str(self.catalog_path)]

    def call(self, slug, request, action=None, expected=0):
        slug, action = map_call(slug, action)
        return super().call(slug, request, action, expected)

    def capture(self, op, text, source_id="raw-source"):
        """Independent source data; do not run the normal merged preparation."""
        path = self.write("docs-raw/specs/" + source_id + ".md", text)
        result = self.call("knowledge-source", {"operation_id": op,
            "source_path": path, "source_id": source_id}, "capture")
        ref = result["data"]["bundle_ref"]
        return ref, self.record(ref)

    def view(self, op, bundle_ref, card_id, card_bytes, decision="create"):
        candidate = self.write(f".build/candidates/{op}/{card_id}.md", card_bytes)
        produced = self.call("knowledge-view-materialize", {"operation_id": op, "bundle_ref": bundle_ref,
            "decisions": [{"candidate_id": card_id, "decision": decision,
                           "reason": "Synthetic pipeline acceptance", "card_inputs": [candidate]}]})
        return produced["data"]["view_ref"]

    def review(self, op, view_ref):
        """Declared document data for independent old-style apply/index tests."""
        view = self.record(view_ref)
        record = load_contract("records").seal({
            "schema_version": "2.0", "record_kind": "content_review", "operation_id": op,
            "rules_digest": self.rules, "tool_identity": view["tool_identity"],
            "status": "passed", "view_digest": view["digest"],
            "plan_ref": view["plan_ref"], "plan_digest": view["plan_digest"],
            "author_id": "fixture-author", "reviewer_id": "fixture-independent-reader",
            "independent_context": "fixture-declared-document-review", "findings": [],
            "verification_tier": "declared_independent_content_review",
        })
        ref = self.write(f".build/operations/{op}/content-review.json", canonical(record))
        return ref, record

    def apply(self, op, view_ref):
        """Run the actual independent legacy apply; never auto-index or activate."""
        ref, review = self.review(op, view_ref)
        applied = self.call("knowledge-apply", {"operation_id": op, "view_ref": view_ref,
            "proof_ref": ref, "content_review_ref": ref}, "run")
        return applied["data"]["apply_result_ref"], review


def load_contract(name):
    namespace = "_p7_public_contract_tests"
    if namespace not in sys.modules:
        contracts = ROOT / "himate/himate-knowledge-wifi-mp/governance/contracts"
        package_spec = importlib.util.spec_from_file_location(namespace, contracts / "__init__.py",
                                                              submodule_search_locations=[str(contracts)])
        package = importlib.util.module_from_spec(package_spec)
        sys.modules[namespace] = package
        package_spec.loader.exec_module(package)
    return importlib.import_module(namespace + "." + name)
