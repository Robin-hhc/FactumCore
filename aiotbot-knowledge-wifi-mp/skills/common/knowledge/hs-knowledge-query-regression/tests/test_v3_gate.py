from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


class PublicFixture:
    operation = "op"
    base = ".build/operations/op"
    args = SimpleNamespace(action="run")

    def __init__(self):
        self.request = {"operation_id": "op", "v3_required": True, "apply_result_ref": "applied",
                        "generation_ref": "generation", "cases": [{"id": "forged", "query": "anything", "required": ["wrong"]}]}
        self.values = {"applied": {"record_kind": "apply_result", "digest": "apply", "view_ref": "view", "view_digest": "view-digest"},
                       "view": {"record_kind": "final_view", "digest": "view-digest", "target_queries": [
                           {"id": "actual", "query": "timeout", "required": ["timeout"]}]}}

    def record(self, ref, kind=None):
        return self.values[ref]

    def call(self, name, request, action=None):
        if name == "hs-knowledge-apply":
            return {"data": {"result_verified": True, "view_ref": "view", "view_digest": "view-digest"}}
        raise AssertionError("Rejected before query or activation")


def test_v3_cases_cannot_replace_authored_batch_queries():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    # A separate interpreter prevents the repository's intentionally isolated
    # Skill support modules from sharing a global import cache in pytest.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from node import execute

    try:
        execute(PublicFixture())
    except Exception as error:
        assert getattr(error, "code", None) == "BATCH_QUERY_PLAN_MISMATCH", error
    else:
        raise AssertionError("Caller queries replaced the authored batch plan")
