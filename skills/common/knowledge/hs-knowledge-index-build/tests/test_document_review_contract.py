"""Document admission uses Agent review; obsolete human event shapes cannot authorize it."""

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[5]


class DocumentReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (ROOT / "aiotbot-knowledge-wifi-mp/governance/schemas/records.schema.json").read_bytes()
        )
        cls.validator = Draft202012Validator(cls.schema)

    def record(self, kind, **fields):
        return {
            "schema_version": "2.0", "record_kind": kind, "operation_id": "op",
            "rules_digest": "1" * 64, "digest": "2" * 64,
            "tool_identity": {"skill": "hs-knowledge-apply", "package_digest": "3" * 64,
                              "runtime": "fixture", "requirements_digest": "4" * 64},
            **fields,
        }

    def test_old_human_confirmation_record_types_are_not_current_contracts(self):
        for kind in ("manual_review", "confirmation_display", "display", "display_receipt", "host_event", "confirmation_review"):
            with self.subTest(kind=kind):
                record = self.record(
                    kind, status="approved", view_ref="view.json", view_digest="5" * 64,
                    display_ref="display.json", display_digest="6" * 64, host_event={},
                    verification_tier="authenticated_host", challenge="unused", display_text="unused",
                    created_at=1, expires_at=2, writes=[], deletes=[], payload={}, signature_b64="obsolete",
                )
                self.assertTrue(list(self.validator.iter_errors(record)))

    def test_record_only_admission_has_a_technical_record_shape(self):
        record = self.record(
            "admission_record", status="passed", batch_kind="record_only", view_digest="5" * 64,
            ingest_record_ref=".build/operations/op/ingest-record.json", ingest_record_digest="6" * 64,
            verification_tier="record_only_fixed_validation",
        )
        self.validator.validate(record)
        for missing in ("view_digest", "ingest_record_ref", "ingest_record_digest"):
            incomplete = {key: value for key, value in record.items() if key != missing}
            with self.subTest(missing=missing):
                self.assertTrue(list(self.validator.iter_errors(incomplete)))

    def test_content_review_does_not_wait_for_a_human(self):
        self.validator.validate(self.record("content_review", status="passed"))
        self.assertTrue(list(self.validator.iter_errors(self.record("content_review", status="awaiting_human"))))


if __name__ == "__main__":
    unittest.main()
