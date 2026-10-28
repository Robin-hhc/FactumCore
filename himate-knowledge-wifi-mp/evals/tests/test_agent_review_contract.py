"""The shared record contract accepts Agent review and removes human events."""

import copy
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "agent_review_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)
from agent_review_contract import validation  # noqa: E402


@pytest.fixture
def rules(tmp_path):
    shutil.copytree(DOMAIN / "governance", tmp_path / "governance")
    lock_path = tmp_path / "governance/framework.lock.yaml"
    return validation.load_rules(tmp_path, hashlib.sha256(lock_path.read_bytes()).hexdigest())


def independent_review():
    return {
        "schema_version": "2.0", "record_kind": "semantic_review", "reviewer_id": "independent-reader",
        "payload": {
            "author_id": "original-author", "independent_context": "fresh-reading-context", "findings": [],
            "view_digest": "1" * 64, "context_digest": "2" * 64, "mode": "local", "issued_at": 1.0,
            "claims": [{"card_id": "card-a", "claim_id": "c1", "status": "supported",
                        "reason": "Read the exact definition and its caller.",
                        "evidence": [{"source_id": "code-a", "snapshot_id": "snapshot-a",
                                      "locator": {"kind": "lines", "start": 1, "end": 2}, "sha256": "3" * 64}]}],
        },
    }


def test_unsigned_agent_review_is_valid_in_the_canonical_contract(rules):
    record = independent_review()
    assert "signature_b64" not in record
    validation.validate_shape("semantic_review", record, rules)


@pytest.mark.parametrize("kind", ["host_event", "confirmation_display", "manual_review"])
@pytest.mark.parametrize("signed", [False, True])
def test_removed_human_record_kinds_are_not_admission_contracts(rules, kind, signed):
    record = {"schema_version": "2.0", "record_kind": kind, "payload": {"actor_type": "human"}}
    if signed:
        record["signature_b64"] = "obsolete-fixture"
    with pytest.raises(validation.ContractError):
        validation.validate_shape(kind, record, rules)


@pytest.mark.parametrize("defect", ["author", "reason", "evidence"])
def test_agent_review_metadata_and_positive_evidence_have_a_shared_shape(rules, defect):
    record = copy.deepcopy(independent_review())
    record["signature_b64"] = "legacy-field-does-not-substitute-for-review-data"
    if defect == "author":
        record["payload"]["author_id"] = {"unexpected": "object"}
    elif defect == "reason":
        record["payload"]["claims"][0]["reason"] = ""
    else:
        record["payload"]["claims"][0]["evidence"][0]["sha256"] = "not-a-source-hash"
    with pytest.raises(validation.ContractError, match="SCHEMA_INVALID"):
        validation.validate_shape("semantic_review", record, rules)


def test_shared_shape_keeps_incomplete_claim_coverage_and_findings_for_node_diagnostics(rules):
    record = independent_review()
    record["payload"]["claims"] = []
    record["payload"]["findings"] = [{"reason": "Missing source branch remains unresolved"}]
    validation.validate_shape("semantic_review", record, rules)
