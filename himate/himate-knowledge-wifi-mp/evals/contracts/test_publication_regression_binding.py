"""Persisted retrieval binds a formal publication, without reopening producer drafts."""

import importlib.util
import json
from pathlib import Path

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("publication_regression_contracts", DOMAIN / "evals/support/contracts.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
runtime = SUPPORT.module("runtime")
publication = SUPPORT.module("publication")
regression = SUPPORT.module("query_regression")


def fixture(root):
    ctx = runtime.OperationContext(root, {"operation_id": "batch"},
        modules={"records": SUPPORT.module("records"), "validation": SUPPORT.module("validation")},
        rules={"schemas": {"record": json.loads((DOMAIN / "governance/schemas/records.schema.json").read_bytes())}},
        tool={"skill": "hs-fixture", "package_digest": "0" * 64, "requirements_digest": "0" * 64, "runtime": "fixture"},
        rules_digest="0" * 64)
    cases = [{"id": "rule", "query": "rule", "required": ["rule"]}]
    view = {"target_queries": cases, "writes": [], "deletes": []}
    manifest = ctx.seal({"purpose": "knowledge_publication", "protocol_version": "1.0", "published": True,
        "content_digest": "a" * 64, "publication_plan_digest": "b" * 64, "reviewed_view_digest": "c" * 64,
        "published_view": view, "published_view_digest": runtime.digest(view), "files": [], "deletes": []}, "artifact_manifest")
    reference = publication.manifest_ref("batch")
    ctx.save(reference, manifest)
    generation = {"digest": "d" * 64, "expected_active": None}
    report = ctx.seal({"generation_ref": "artifacts/indexes/local/gen-one/manifest.json", "expected_active": None,
        "cases": cases, "cases_digest": runtime.digest(cases), "outcomes": [{"case_id": "rule", "passed": True}],
        "passed": True, "index_verified": True, "publication_ref": reference,
        "publication_digest": manifest["digest"], "content_digest": manifest["content_digest"]}, "query_regression")
    report_ref = "logs/publications/batch/regression/actual.json"
    ctx.save(report_ref, report)
    return ctx, manifest, reference, generation, report, report_ref


def test_binding_uses_published_identity_without_any_stage_view(tmp_path):
    ctx, manifest, reference, generation, report, report_ref = fixture(tmp_path)
    assert not (tmp_path / ".build").exists()
    binding = regression.persisted_binding(ctx, report["generation_ref"], generation, report_ref,
                                          publication_ref=reference, publication_manifest=manifest)
    assert binding["publication_ref"] == reference
    assert binding["content_digest"] == manifest["content_digest"]
    assert binding["view_ref"] is None


@pytest.mark.parametrize("field", ["publication_digest", "content_digest"])
def test_report_cannot_claim_a_different_publication(tmp_path, field):
    ctx, manifest, reference, generation, report, report_ref = fixture(tmp_path)
    report[field] = "e" * 64
    report = ctx.modules["records"].seal(report)
    (tmp_path / report_ref).write_bytes(runtime.canonical(report))
    with pytest.raises(runtime.NodeError) as error:
        regression.persisted_binding(ctx, report["generation_ref"], generation, report_ref,
                                     publication_ref=reference, publication_manifest=manifest)
    assert error.value.code == "REGRESSION_BINDING_CHANGED"


def test_resealed_report_does_not_replace_publications_frozen_cases(tmp_path):
    ctx, manifest, reference, generation, report, report_ref = fixture(tmp_path)
    report["cases"] = [{"id": "other", "query": "unrelated", "required": ["other"]}]
    report["cases_digest"] = runtime.digest(report["cases"])
    (tmp_path / report_ref).write_bytes(runtime.canonical(ctx.modules["records"].seal(report)))
    with pytest.raises(runtime.NodeError) as error:
        regression.persisted_binding(ctx, report["generation_ref"], generation, report_ref,
                                     publication_ref=reference, publication_manifest=manifest)
    assert error.value.code == "REGRESSION_BINDING_CHANGED"
