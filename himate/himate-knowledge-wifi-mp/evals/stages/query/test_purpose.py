"""Retrieval intent is validated at the real public query entry point."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "query_purpose_fixture", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/pipeline.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
INVALID_PURPOSES = ["gudiance", "", None, 17, ["guidance"]]


@pytest.mark.parametrize("purpose", INVALID_PURPOSES)
def test_public_query_rejects_invalid_purpose_before_loading_missing_index(tmp_path, purpose):
    pipeline = FIXTURE.Pipeline(tmp_path)
    result = pipeline.call(
        "knowledge-query",
        {"operation_id": "invalid-purpose", "query": "capture", "purpose": purpose},
        "search",
        expected=2,
    )
    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "INVALID_PURPOSE"
    assert isinstance(result["diagnostics"][0]["message"], str)
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()


@pytest.fixture(scope="module")
def indexed_purposes(tmp_path_factory):
    pipeline = FIXTURE.Pipeline(tmp_path_factory.mktemp("query-purpose-indexes"))
    empty = pipeline.call("knowledge-index-build", {"operation_id": "purpose-empty-build"})["data"]
    bundle_ref, bundle = pipeline.capture("purpose-create", b"# Fixture\nCapture query intent.\n")
    view_ref = pipeline.view("purpose-create", bundle_ref, "purpose-rule", pipeline.card("purpose-rule", bundle))
    pipeline.apply("purpose-create", view_ref)
    populated = pipeline.call("knowledge-index-build", {"operation_id": "purpose-populated-build"})["data"]
    pipeline.call(
        "knowledge-index-build",
        {"operation_id": "purpose-activate", "generation_ref": populated["generation_ref"],
         "expected_active": populated["expected_active"]},
        "activate",
    )
    return pipeline, empty["generation_ref"], populated["generation_ref"]


@pytest.mark.parametrize("purpose", INVALID_PURPOSES)
@pytest.mark.parametrize("state", ["empty-index", "no-lexical-candidates", "matching-candidate"])
def test_public_search_rejects_invalid_purpose_for_every_candidate_state(indexed_purposes, purpose, state):
    pipeline, empty, populated = indexed_purposes
    result = pipeline.call(
        "knowledge-query",
        {"operation_id": "invalid-purpose-" + str(pipeline.sequence), "purpose": purpose,
         "generation_ref": empty if state == "empty-index" else populated, "evaluation": True,
         "query": "absentmarker" if state == "no-lexical-candidates" else "capture"},
        "search",
        expected=2,
    )
    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "INVALID_PURPOSE"
    assert isinstance(result["diagnostics"][0]["message"], str)
    assert result["data"] == {}


def test_public_default_current_and_guidance_receipt_inheritance_remain_valid(indexed_purposes):
    pipeline, empty, populated = indexed_purposes
    for generation, query in ((empty, "capture"), (populated, "absentmarker")):
        result = pipeline.call(
            "knowledge-query",
            {"operation_id": "valid-empty-" + str(pipeline.sequence), "generation_ref": generation,
             "evaluation": True, "query": query},
            "search",
        )["data"]
        assert result["matches"] == []
    for purpose in (None, "guidance"):
        request = {"operation_id": "valid-purpose-" + str(pipeline.sequence), "query": "capture"}
        if purpose is not None:
            request["purpose"] = purpose
        search = pipeline.call("knowledge-query", request, "search")["data"]
        assert [row["card_id"] for row in search["matches"]] == ["purpose-rule"]
        expected_purpose = "current" if purpose is None else "guidance"
        assert pipeline.record(search["receipt_ref"])["request_binding"]["purpose"] == expected_purpose
        read_request = {"operation_id": "inherit-purpose-" + str(pipeline.sequence),
                        "receipt_ref": search["receipt_ref"], "card_id": "purpose-rule"}
        read = pipeline.call("knowledge-query", read_request, "read")["data"]
        assert read["generation_ref"] == search["generation_ref"]
        assert read["card_digest"] == search["matches"][0]["card_digest"]
        assert pipeline.record(read["receipt_ref"])["request_binding"]["purpose"] == expected_purpose
        if purpose == "guidance":
            for override in ["current", *INVALID_PURPOSES]:
                refused = pipeline.call(
                    "knowledge-query",
                    {**read_request, "operation_id": "override-purpose-" + str(pipeline.sequence),
                     "purpose": override},
                    "read",
                    expected=2,
                )
                assert refused["diagnostics"][0]["code"] == "SEARCH_RECEIPT_SCOPE_MISMATCH"
