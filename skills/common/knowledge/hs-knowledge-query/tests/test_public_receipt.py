"""Search-to-read lineage across activation, using real public node CLIs."""

import importlib.util
from pathlib import Path
import copy

import yaml


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "query_receipt_fixture", ROOT / "himate-knowledge-wifi-mp/evals/pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_formal_search_receipt_keeps_generation_and_rejects_changed_scope_or_evaluation(
    tmp_path,
):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture(
        "receipt-create", b"# Fixture\nCapture receipt is a synthetic rule.\n"
    )
    view_ref = p.view(
        "receipt-create", bundle_ref, "receipt-rule", p.card("receipt-rule", bundle)
    )
    p.apply("receipt-create", view_ref)
    first = p.call("knowledge-index-build", {"operation_id": "receipt-first-build"})[
        "data"
    ]
    p.call(
        "knowledge-index-build",
        {
            "operation_id": "receipt-first-activate",
            "generation_ref": first["generation_ref"],
            "expected_active": first["expected_active"],
        },
        "activate",
    )
    search = p.call(
        "knowledge-query",
        {
            "operation_id": "receipt-search",
            "query": "capture",
            "purpose": "current",
            "context": {"side": "host"},
        },
        "search",
    )["data"]
    assert [row["card_id"] for row in search["matches"]] == ["receipt-rule"]
    second = p.call("knowledge-index-build", {"operation_id": "receipt-second-build"})[
        "data"
    ]
    p.call(
        "knowledge-index-build",
        {
            "operation_id": "receipt-second-activate",
            "generation_ref": second["generation_ref"],
            "expected_active": second["expected_active"],
        },
        "activate",
    )
    assert first["generation_ref"] != second["generation_ref"]
    read_request = {
        "operation_id": "read-original-search",
        "receipt_ref": search["receipt_ref"],
        "card_id": "receipt-rule",
    }
    read = p.call("knowledge-query", read_request, "read")["data"]
    assert read["generation_ref"] == first["generation_ref"]
    assert read["evaluation"] is False
    assert read["card_digest"] == search["matches"][0]["card_digest"]
    assert {row["id"] for row in read["claims"]} == set(
        search["matches"][0]["claim_ids"]
    )
    for number, wrong in enumerate(
        (
            {"purpose": "historical"},
            {"context": {"side": "device"}},
            {"channel": "shared"},
            {"generation_ref": second["generation_ref"]},
            {"claim_ids": ["not-an-original-hit"]},
        )
    ):
        refused = p.call(
            "knowledge-query",
            {
                **read_request,
                "operation_id": "wrong-receipt-binding-" + str(number),
                **wrong,
            },
            "read",
            expected=2,
        )
        assert refused["status"] == "error"
    evaluation = p.call(
        "knowledge-query",
        {
            "operation_id": "evaluation-only-search",
            "query": "capture",
            "evaluation": True,
            "generation_ref": second["generation_ref"],
        },
        "search",
    )["data"]
    refused = p.call(
        "knowledge-query",
        {
            **read_request,
            "operation_id": "reject-evaluation-receipt",
            "receipt_ref": evaluation["receipt_ref"],
        },
        "read",
        expected=2,
    )
    assert refused["status"] == "error"
    missing = p.call(
        "knowledge-query",
        {
            **read_request,
            "operation_id": "reject-missing-receipt",
            "receipt_ref": ".build/operations/missing/receipt.json",
        },
        "read",
        expected=2,
    )
    assert missing["status"] == "error"
    for field in ("request_binding", "result"):
        tampered = p.record(search["receipt_ref"])
        tampered[field]["query"] = "not the original effective query"
        tampered["digest"] = FIXTURE.sha(
            FIXTURE.canonical(
                {key: value for key, value in tampered.items() if key != "digest"}
            )
        )
        ref = p.write(
            ".build/operations/tampered-" + field + "/receipt.json",
            FIXTURE.canonical(tampered),
        )
        refused = p.call(
            "knowledge-query",
            {
                **read_request,
                "operation_id": "reject-inner-binding-" + field,
                "receipt_ref": ref,
            },
            "read",
            expected=2,
        )
        assert refused["status"] == "error"
    history_search = p.call(
        "knowledge-query",
        {
            "operation_id": "formal-history-search",
            "query": "capture",
            "purpose": "historical",
        },
        "search",
    )["data"]
    # A real old search receipt cannot override a fresh raw-source block.
    p.capture(
        "receipt-source-changed", b"# Fixture\nA new source version needs review.\n"
    )
    blocked = p.call(
        "knowledge-query",
        {**read_request, "operation_id": "receipt-live-block"},
        "read",
        expected=3,
    )
    assert blocked["status"] == "blocked"
    history_read = p.call(
        "knowledge-query",
        {
            "operation_id": "original-history-read",
            "card_id": "receipt-rule",
            "receipt_ref": history_search["receipt_ref"],
        },
        "read",
    )["data"]
    assert history_read["generation_ref"] == history_search["generation_ref"]
    assert "explicit synthetic rule" in history_read["claims"][0]["text"]


def test_receipt_read_claim_subset_excludes_other_claim_source_text(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    first = p.write(
        "docs-raw/specs/first.md", b"# First\nCapture first synthetic statement.\n"
    )
    second = p.write(
        "docs-raw/specs/second.md", b"# Second\nEXCLUDED_C2_SOURCE_ONLY.\n"
    )
    bundle_ref = p.call(
        "knowledge-source-capture",
        {
            "operation_id": "subset-create",
            "source_path": first,
            "source_id": "first",
            "attachments": [second],
        },
    )["data"]["bundle_ref"]
    bundle = p.record(bundle_ref)
    _, front, body = p.card("two-claims", bundle).decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["lifecycle"] = "stable"
    snapshot = bundle["snapshots"][1]
    metadata["sources"].append(
        {
            "evidence_ref": "e2",
            "source_id": snapshot["source_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "locator": {"kind": "lines", "start": 1, "end": 2},
        }
    )
    second_claim = copy.deepcopy(metadata["claims"][0])
    second_claim.update(id="c2", text_ref="#c2", source_refs=["e2"])
    metadata["claims"].append(second_claim)
    body += '\n<a id="c2"></a>\nExcluded second synthetic statement.\n'
    card_bytes = (
        "---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body
    ).encode()
    # This case checks independent formal query consumption, including exact
    # attachment identities. It needs no author's plan or private transaction.
    p.write("knowledge/rules/two-claims.md", card_bytes)
    p.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": bundle["resources"],
        "snapshots": bundle["snapshots"]}, sort_keys=False).encode())
    generation = p.call("knowledge-index-build", {"operation_id": "subset-build"})[
        "data"
    ]
    p.call(
        "knowledge-index-build",
        {
            "operation_id": "subset-activate",
            "generation_ref": generation["generation_ref"],
            "expected_active": None,
        },
        "activate",
    )
    search = p.call(
        "knowledge-query",
        {"operation_id": "subset-search", "query": "capture"},
        "search",
    )["data"]
    assert set(search["matches"][0]["claim_ids"]) == {"c1", "c2"}
    read = p.call(
        "knowledge-query",
        {
            "operation_id": "subset-read",
            "receipt_ref": search["receipt_ref"],
            "card_id": "two-claims",
            "claim_ids": ["c1"],
        },
        "read",
    )["data"]
    assert {claim["id"] for claim in read["claims"]} == {"c1"}
    assert {source["source_ref"]["source_id"] for source in read["sources"]} == {
        "first"
    }
    assert all(
        "EXCLUDED_C2_SOURCE_ONLY" not in source.get("text", "")
        for source in read["sources"]
    )
