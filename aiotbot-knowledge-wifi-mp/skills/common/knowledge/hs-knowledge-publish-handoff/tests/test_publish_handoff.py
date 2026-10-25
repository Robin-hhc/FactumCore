import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class PublishTests(unittest.TestCase):
    def test_agent_record_alone_cannot_claim_published(self):
        from publish import publish_handoff
        from support import Context, Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-publish-handoff")
            record = ctx.record(
                "apply_result", "op", status="committed", view_digest="a" * 64
            )
            ctx.save("logs/operations/op/apply-result.json", record)
            with self.assertRaises(Blocked):
                publish_handoff(
                    ctx,
                    {
                        "operation_id": "op",
                        "apply_result_ref": "logs/operations/op/apply-result.json",
                    },
                )


if __name__ == "__main__":
    unittest.main()
