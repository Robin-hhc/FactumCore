"""P5 checks the complete frozen mapping, including unreferenced payloads."""

from support import library as fixture

import pytest



checks, records, validation = fixture.checks, fixture.records, fixture.validation
runtime, staging, publication = [fixture._helper.module(name) for name in ("runtime", "staging", "publication")]


def candidate(tmp_path):
    root, raw, _, _, rules = fixture.library(tmp_path, kind="raw")
    ctx = runtime.OperationContext(root, {"operation_id": "batch"},
        modules={"records": records, "validation": validation}, rules=rules, rules_digest=rules["rules_digest"],
        tool={"skill": "hs-synthetic-publication-check", "package_digest": "0" * 64,
              "runtime": "synthetic", "requirements_digest": "0" * 64})
    payload = b"Frozen adopted original.\n"
    entry = staging.stage_bytes(ctx, "logs/evidence/published/objects/" + runtime.sha(payload) + ".bin", payload, kind="original")
    value = {"schema_version": "2.0", "record_kind": "final_view", "operation_id": "batch",
             "tool_identity": ctx.tool, "writes": [], "deletes": [], "staged_objects": [entry],
             "source_refs": [], "source_set_digest": validation.sha256_bytes(validation.canonical_bytes([]))}
    value["publication_plan"] = publication.prepare_plan(ctx, value)
    value["content_digest"] = value["publication_plan"]["content_digest"]
    return root, raw, rules, value


def check(root, raw, rules, value):
    return checks.run(checks.prepare_view(root, records.seal(value), mode="candidate"), rules,
                      inputs={"source_objects": {"v1": raw}}, scope="full")


def test_p5_validates_frozen_publication_with_no_formal_writes(tmp_path):
    root, raw, rules, value = candidate(tmp_path)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
              if p.is_file() and not p.relative_to(root).as_posix().startswith(".build/")}
    result = check(root, raw, rules, value)
    assert result["status"] == "passed", result["findings"]
    assert next(row for row in result["checks"] if row["group"] == "view")["publication_check"] == value["publication_plan"]
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and not p.relative_to(root).as_posix().startswith(".build/")} == before


@pytest.mark.parametrize("tamper", ["final_ref", "payload", "missing_mapping", "missing_plan", "content_digest", "plan_payload"])
def test_p5_rejects_mapping_or_unreferenced_payload_tampering(tmp_path, tamper):
    root, raw, rules, value = candidate(tmp_path)
    if tamper == "final_ref":
        value["staged_objects"][0]["final_ref"] = "logs/evidence/published/objects/other.bin"
    elif tamper == "payload":
        (root / value["staged_objects"][0]["stage_ref"]).write_bytes(b"Changed actual bytes")
    elif tamper == "missing_mapping":
        value["staged_objects"] = []
    elif tamper == "missing_plan":
        value.pop("publication_plan")
    elif tamper == "content_digest":
        value["content_digest"] = "0" * 64
    else:
        value["publication_plan"]["payloads"][0]["sha256"] = "0" * 64
    result = check(root, raw, rules, value)
    assert result["status"] == "failed", result["findings"]
    assert any(row["check_id"] == "view.inputs" and row["code"] in {
        "PUBLICATION_PLAN_CHANGED", "PUBLICATION_PLAN_REQUIRED", "STAGED_OBJECT_CHANGED"}
        for row in result["findings"])
    assert next(row for row in result["checks"] if row["group"] == "index")["status"] == "incomplete"
