"""Production reentry binds adopted and selected current inputs, without rescans."""
import hashlib
import json

import pytest


def original_request(harness, view):
    return harness.record(harness.record(view)["plan_ref"])["request"]


def test_unchanged_reentry_reuses_exact_outputs_and_ignores_private_reports(harness):
    ref, _ = harness.view()
    view = harness.record(ref)
    plan_before = (harness.root / view["plan_ref"]).read_bytes()
    view_before = (harness.root / ref).read_bytes()
    harness.write("logs/operations/op/arbitrary-private-review.json", b'{"status":"failed"}')
    harness.write("docs-raw/specs/unselected.md", b"Not adopted by this batch")
    result = harness.run("view-materialize", original_request(harness, ref))
    assert result["data"]["view_ref"] == ref and result["data"]["view_digest"] == view["digest"]
    assert (harness.root / view["plan_ref"]).read_bytes() == plan_before
    assert (harness.root / ref).read_bytes() == view_before


@pytest.mark.parametrize("path,raw", [("knowledge/rules/unrelated.md", b"An added formal member"),
                                     ("docs-raw/specs/source.md", b"Selected current original changed")])
def test_bound_formal_membership_and_selected_current_original_cannot_drift(harness, path, raw):
    ref, _ = harness.view()
    request = original_request(harness, ref)
    before = (harness.root / ref).read_bytes()
    harness.write(path, raw)
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "INPUT_CHANGED"
    assert (harness.root / ref).read_bytes() == before


@pytest.mark.parametrize("change", ["group-shape", "entry-shape", "postwrite-stage"])
def test_resealed_malformed_or_wrong_stage_snapshot_is_a_structured_input_error(harness, change):
    ref, _ = harness.view()
    request = original_request(harness, ref)
    view = harness.record(ref)
    snapshot = view["input_snapshot"]
    if change == "group-shape":
        snapshot["current_files"] = []
    elif change == "entry-shape":
        snapshot["current_files"] = {"docs-raw/specs/source.md": {"sha256": "a" * 64}}
    else:
        snapshot["stage"] = "postwrite"
    for value in (snapshot, view):
        value.pop("snapshot_digest" if value is snapshot else "digest")
        value["snapshot_digest" if value is snapshot else "digest"] = hashlib.sha256(json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(ref, json.dumps(view).encode())
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "INVALID_INPUT_SNAPSHOT"
