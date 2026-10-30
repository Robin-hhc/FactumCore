"""New optional publication fields are strict without migrating old records."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest


SCHEMA = json.loads((Path(__file__).parents[2] / "governance/schemas/records.schema.json").read_bytes())
LEGACY = {"schema_version": "2.0", "record_kind": "result", "status": "ok", "phase": "ready",
          "data": {}, "diagnostics": [], "rules_digest": "0" * 64,
          "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
                            "requirements_digest": "0" * 64, "runtime": "fixture"}}


def test_legacy_result_does_not_need_new_publication_fields():
    Draft202012Validator(SCHEMA).validate(LEGACY)


@pytest.mark.parametrize("field,value", [
    ("staged_objects", [{"stage_ref": ".build/operations/batch/x"}]),
    ("event_proposals", [{"source_id": "s", "old_snapshot_ids": [], "new_snapshot_id": "x", "source_lock_digest": "wrong"}]),
    ("owned_files", [{"path": ".build/operations/batch/x", "sha256": "0" * 64, "bytes": -1, "owner_operation_id": "batch"}]),
    ("publication_plan", {}), ("content_digest", "wrong"),
])
def test_new_fields_reject_missing_or_invalid_identities(field, value):
    assert list(Draft202012Validator(SCHEMA).iter_errors(
        {**LEGACY, field: value}))
