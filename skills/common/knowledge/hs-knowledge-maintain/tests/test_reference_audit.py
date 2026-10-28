"""Public read-only audit over isolated module files, not real Target QA."""
import hashlib
import json
import subprocess
import sys

import pytest
import yaml

import importlib.util
from pathlib import Path

_fixture_spec = importlib.util.spec_from_file_location("maintain_fixture_helpers", Path(__file__).with_name("conftest.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
operation_context = _fixture.operation_context
public_module = _fixture.public_module

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def hashed(raw):
    return hashlib.sha256(raw).hexdigest()


def code_fixture(harness, usages=("current",), source_bytes=None):
    code = harness.base / "main/shared"
    code.mkdir(parents=True)
    raw = source_bytes if source_bytes is not None else b"int selected_fixture(void) { return 1; }\n"
    (code / "file.c").write_bytes(raw)
    config = {"schema_version": "2.0", "workspace_id": "audit-fixture", "knowledge_roots": {"wifi": harness.root.name},
              "code_root": "main", "modules": [{"path": "shared", "chips": ["chip12"], "sides": ["host"]}]}
    config_path = harness.base / "config.yml"
    config_path.write_bytes(canonical(config))
    repo_id = "repo-" + hashed(b"main/shared")[:16]
    captured = harness.run("source-prepare", {"operation_id": "captured", "kind": "code", "repo_id": repo_id,
                                            "relative_path": "file.c", "source_id": "selected-code"}, action="capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"], "snapshots": bundle["snapshots"]}).encode())
    for usage in usages:
        _, header, body = harness.card("audit-" + usage, bundle, lifecycle="stable").decode().split("---", 2)
        meta = yaml.safe_load(header)
        meta["review_mode"] = "code_gate"
        meta["scope"] = {"applicability": "constrained", "contexts": [{"context_id": "host", "target_id": "chip12-host", "chip": "chip12", "side": "host",
            "build_profile": None, "features_all": [], "features_none": [], "protocol_versions": [], "revision_policy": "revalidate", "revision": None}]}
        meta["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 1}
        meta["sources"][0]["code_ref"] = {"kind": "function", "name": "selected_fixture", "scope": [],
                                           "parameter_types": [], "role": "definition"}
        meta["claims"][0].update(usage=usage, evidence_kind="implementation", context_ids=["host"])
        harness.write("knowledge/rules/audit-" + usage + ".md", ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body).encode())
    checkout = {"configuration": str(config_path), "config_digest": hashed(config_path.read_bytes()), "repos": {repo_id: {"root": str(code)}}}
    return code / "file.c", raw, bundle, checkout


def lint_report(harness, checkout=None, name="fixed"):
    incoming = harness.base / (name + "-input.json")
    incoming.write_bytes(canonical({"inputs": {"code_checkout": checkout}} if checkout else {}))
    ref = ".build/reports/" + name + ".json"
    completed = subprocess.run([sys.executable, str(harness.packages / "hs-knowledge-lint/scripts/cli.py"),
        "--knowledge-root", str(harness.root), "--input", str(incoming), "--output", str(harness.root / ref)], capture_output=True, text=True)
    assert completed.returncode in (0, 1, 2), completed.stderr
    report = harness.record(ref)
    assert report.get("digest") and report.get("checks"), report
    return ref


def protected_bytes(harness):
    return {str(path.relative_to(harness.base)): hashed(path.read_bytes()) for path in harness.base.rglob("*")
            if path.is_file() and (path.is_relative_to(harness.root / "knowledge") or path.is_relative_to(harness.root / "governance")
            or path.is_relative_to(harness.root / "logs") or path.is_relative_to(harness.root / "artifacts")
            or path.is_relative_to(harness.base / "main") or path == harness.base / "config.yml")}


@pytest.mark.parametrize("change", ["changed", "inserted", "missing"])
def test_public_audit_reports_actual_code_drift_without_writing_assets(harness, change):
    source, raw, _, checkout = code_fixture(harness)
    if change == "missing":
        source.unlink()
    else:
        source.write_bytes(b"// inserted line\n" + raw if change == "inserted" else raw.replace(b"1", b"2"))
    fixed = lint_report(harness, checkout)
    before = protected_bytes(harness)
    response = harness.run("maintain", {"operation_id": "audit", "lint_report_ref": fixed}, "audit-references")
    assert response["phase"] == "reported"
    audit = harness.record(response["data"]["audit_ref"])
    assert audit["purpose"] == "code_reference_audit"
    row = audit["references"][0]
    assert row["old_sha256"] == hashed(raw)
    assert row["current_source_matches"] is False
    assert row["observation"] == ("missing" if change == "missing" else "changed")
    assert row["claim_ids"] == ["audit-current-claim"]
    assert row["old_fragment"].strip() == raw.decode().strip()
    assert row["effect"] == "current_reference_needs_review"
    assert row["difference"]
    report = (harness.root / response["data"]["report_ref"]).read_text(encoding="utf-8")
    assert "ingest" in report and "knowledge/rules/audit-current.md" in report
    assert protected_bytes(harness) == before
    assert not (harness.root / "logs/events").exists()


@pytest.mark.parametrize("change", ["body", "symbol"])
def test_audit_keeps_guidance_and_historical_uses_distinct(harness, change):
    source, raw, _, checkout = code_fixture(harness, ("current", "guidance", "historical"))
    source.write_bytes(raw.replace(b"1", b"3") if change == "body"
                       else raw.replace(b"selected_fixture", b"renamed_fixture"))
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "usages", "lint_report_ref": fixed}, "audit-references")
    rows = harness.record(result["data"]["audit_ref"])["references"]
    effects = {row["claims"][0]["usage"]: row["effect"] for row in rows}
    assert effects == {"current": "current_reference_needs_review",
                       "guidance": "guidance_navigation_resolved" if change == "body" else "guidance_navigation_needs_review",
                       "historical": "historical_reference"}
    guidance = next(row for row in rows if row["claims"][0]["usage"] == "guidance")
    assert guidance["code_navigation"]["status"] == ("resolved" if change == "body" else "missing")
    assert guidance["current_source_matches"] is False


def test_empty_library_audit_is_complete_only_with_actual_fixed_report(harness):
    fixed = lint_report(harness)
    result = harness.run("maintain", {"operation_id": "empty", "lint_report_ref": fixed}, "audit-references")
    assert result["data"]["complete"] is True
    assert result["data"]["counts"]["code_references"] == 0
    missing = harness.run("maintain", {"operation_id": "missing-report"}, "audit-references")
    assert missing["data"]["complete"] is False
    assert any(gap["code"] == "LINT_REPORT_NOT_PROVIDED" for gap in harness.record(missing["data"]["audit_ref"])["gaps"])


@pytest.mark.parametrize("fixed_status", ["failed", "incomplete"])
def test_audit_retains_actual_failed_or_incomplete_formal_report_status(harness, fixed_status):
    _, _, _, checkout = code_fixture(harness)
    harness.write("knowledge/rules/index.md", b"# Rules\n\n- [audit-current](audit-current.md)\n")
    if fixed_status == "failed":
        path = harness.root / "knowledge/rules/audit-current.md"
        _, header, body = path.read_text(encoding="utf-8").split("---", 2)
        metadata = yaml.safe_load(header)
        metadata["summary"] = ""
        path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
    else:
        # An unreadable local writer journal is a real unavailable check input;
        # preserve the actual incomplete report through the read-only audit.
        harness.write("logs/operations/unreadable/journal.json", b'{"status":')
    fixed = lint_report(harness, checkout)
    original = harness.record(fixed)
    assert original["status"] == fixed_status
    before = protected_bytes(harness)
    response = harness.run("maintain", {"operation_id": "summarize-" + fixed_status,
        "lint_report_ref": fixed}, "audit-references")
    assert response["phase"] == "reported"
    report = harness.record(response["data"]["audit_ref"])
    assert report["lint_report"] == original
    assert report["status"] == "incomplete" and report["complete"] is False
    assert protected_bytes(harness) == before


@pytest.mark.parametrize("alter", ["wrong_root", "tampered", "local", "stale_files", "missing"])
def test_audit_reports_unusable_or_stale_lint_input_as_gap(harness, alter):
    _, _, _, checkout = code_fixture(harness)
    fixed = lint_report(harness, checkout)
    report = harness.record(fixed)
    if alter == "missing":
        (harness.root / fixed).unlink()
    elif alter == "stale_files":
        path = harness.root / "knowledge/rules/audit-current.md"
        path.write_bytes(path.read_bytes() + b"\nchanged after lint\n")
    else:
        if alter == "wrong_root":
            report["object"]["root"] = str(harness.base)
        elif alter == "local":
            report["scope"] = {"kind": "local", "paths": ["knowledge"]}
        report.pop("digest")
        report["digest"] = hashed(canonical(report)) if alter != "tampered" else "0" * 64
        harness.write(fixed, canonical(report))
    result = harness.run("maintain", {"operation_id": "input-gap", "lint_report_ref": fixed}, "audit-references")
    assert result["data"]["complete"] is False
    assert harness.record(result["data"]["audit_ref"])["gaps"]


def test_default_inspect_context_result_stays_unchanged(harness):
    before = harness.run("maintain", {"operation_id": "default-before"})["data"]
    harness.run("maintain", {"operation_id": "separate-audit"}, "audit-references")
    after = harness.run("maintain", {"operation_id": "default-after"}, "inspect-context")["data"]
    assert before == after


@pytest.mark.parametrize("change", ["body", "symbol"])
def test_audit_includes_unadopted_metadata_reference(harness, change):
    source, raw, _, checkout = code_fixture(harness)
    path = harness.root / "knowledge/rules/audit-current.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(header)
    meta["sources"].append({**meta["sources"][0], "evidence_ref": "unused"})
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body, encoding="utf-8")
    source.write_bytes(raw.replace(b"1", b"4") if change == "body"
                       else raw.replace(b"selected_fixture", b"renamed_fixture"))
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "metadata", "lint_report_ref": fixed}, "audit-references")
    rows = harness.record(result["data"]["audit_ref"])["references"]
    unused = next(row for row in rows if row["evidence_ref"] == "unused")
    assert unused["claims"] == []
    assert unused["effect"] == ("unadopted_navigation_resolved" if change == "body" else "unadopted_reference_needs_review")
    assert unused["code_navigation"]["status"] == ("resolved" if change == "body" else "missing")
    assert unused["current_source_matches"] is False


def test_unreadable_location_and_unauthorized_mapping_are_not_reported_as_missing(harness):
    source, _, _, checkout = code_fixture(harness)
    source.unlink()
    source.mkdir()
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "non-file", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert row["observation"] == "unavailable" and row["current_source_matches"] is None
    assert row["gaps"][0]["code"] == "CODE_FILE_UNREADABLE"
    config_path = harness.base / "config.yml"
    config = json.loads(config_path.read_bytes())
    config["modules"] = []
    config_path.write_bytes(canonical(config))
    result = harness.run("maintain", {"operation_id": "unauthorized", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert row["observation"] == "unavailable" and row["current_sha256"] is None
    assert row["gaps"][0]["code"] == "CODE_PATH_UNAUTHORIZED"


def test_missing_old_object_is_a_gap_but_current_byte_difference_remains_visible(harness):
    source, raw, bundle, checkout = code_fixture(harness)
    source.write_bytes(raw.replace(b"1", b"5"))
    fixed = lint_report(harness, checkout)
    recovery = bundle["snapshots"][0]["recovery"]
    (harness.root / recovery["path"]).unlink()
    result = harness.run("maintain", {"operation_id": "old-gap", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert result["data"]["complete"] is False
    assert row["current_source_matches"] is False and row["observation"] == "changed"
    assert row["old_fragment"] is None and row["gaps"]


@pytest.mark.parametrize("override", ["other.c", "../outside.c"])
def test_locator_path_override_uses_same_authorized_precedence_as_query(harness, override):
    source, raw, _, checkout = code_fixture(harness)
    (source.parent / "other.c").write_bytes(raw.replace(b"1", b"9"))
    (source.parent.parent / "outside.c").write_bytes(b"outside authorization")
    path = harness.root / "knowledge/rules/audit-current.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(header)
    meta["sources"][0]["locator"]["path"] = override
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body, encoding="utf-8")
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "override", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert row["path"] == override
    if override == "other.c":
        assert row["observation"] == "changed" and row["current_sha256"] == hashed((source.parent / override).read_bytes())
    else:
        assert row["observation"] == "unavailable" and row["current_sha256"] is None
        assert row["gaps"][0]["code"] == "CODE_PATH_UNAUTHORIZED"


@pytest.mark.parametrize("moment", ["during_read", "after_resolve"])
def test_source_change_during_observation_is_not_accepted_as_matching(harness, moment, monkeypatch):
    source, _, _, _ = code_fixture(harness)
    audit = public_module("reference_audit")
    context = operation_context(harness, {"operation_id": "race"}, "audit-references")
    if moment == "during_read":
        original = audit.fixed_bytes

        def race(root, ref, prefixes=None):
            data = original(root, ref, prefixes)
            if ref == "file.c":
                source.write_bytes(data + b"// changed while observing\n")
            return data

        monkeypatch.setattr(audit, "fixed_bytes", race)
    else:
        sources = public_module("source_operations")
        resolve = sources.resolve_source

        def after_resolve(*args, **kwargs):
            result = resolve(*args, **kwargs)
            source.write_bytes(source.read_bytes() + b"// changed after resolution\n")
            return result

        monkeypatch.setattr(sources, "resolve_source", after_resolve)
    result, phase = audit.audit_references(context)
    assert phase == "reported"
    row = harness.record(result["audit_ref"])["references"][0]
    assert row["current_source_matches"] is None and row["observation"] == ("unavailable" if moment == "during_read" else "unstable")
    assert row["gaps"][0]["code"] == "CODE_CHANGED_DURING_AUDIT"
    if moment == "after_resolve":
        assert row["current_sha256"] is None and row["effect"] == "current_reference_needs_review"



def test_large_current_file_reports_explicit_bounded_text_omission(harness):
    source, raw, _, checkout = code_fixture(harness)
    source.write_bytes(raw + b"// large fixture only\n" * 15000)
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "bounded", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert row["current_source_matches"] is False
    assert row["old_fragment"] is None and row["old_fragment_truncated"] and row["diff_truncated"]
    assert "256 KiB" in row["content_omitted_reason"]


def test_fragments_and_shared_file_diffs_are_bounded_and_explicit(harness):
    # Active code cards bind an actual definition while retaining 100 lines of
    # source material for the original fragment/diff truncation assertions.
    old = b"int selected_fixture(void) { return 1; }\n" + b"".join(
        ("/* old fixture line " + str(index) + " " + "x" * 100 + " */\n").encode() for index in range(99))
    source, raw, _, checkout = code_fixture(harness, ("current", "guidance"), source_bytes=old)
    for usage in ("current", "guidance"):
        path = harness.root / ("knowledge/rules/audit-" + usage + ".md")
        _, header, body = path.read_text(encoding="utf-8").split("---", 2)
        meta = yaml.safe_load(header)
        meta["sources"][0]["locator"]["end"] = 100
        path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body, encoding="utf-8")
    source.write_bytes(raw.replace(b"old", b"new"))
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "truncated", "lint_report_ref": fixed}, "audit-references")
    rows = harness.record(result["data"]["audit_ref"])["references"]
    assert all(row["old_fragment_truncated"] and len(row["old_fragment"]) <= 4096 and len(row["old_fragment"].splitlines()) <= 20 for row in rows)
    assert rows[0]["diff_truncated"] and len(rows[0]["difference"].split("\n", 1)[1]) <= 8192
    assert rows[1]["difference_ref"] == rows[0]["card_path"] + "#e1"


def test_locator_repo_override_selects_the_other_authorized_module(harness):
    source, raw, _, checkout = code_fixture(harness)
    other = source.parent.parent / "other"
    other.mkdir()
    (other / "other.c").write_bytes(raw.replace(b"1", b"7"))
    config_path = harness.base / "config.yml"
    config = json.loads(config_path.read_bytes())
    config["modules"].append({"path": "other", "chips": ["chip12"], "sides": ["host"]})
    config_path.write_bytes(canonical(config))
    repo_id = "repo-" + hashed(b"main/other")[:16]
    checkout["config_digest"] = hashed(config_path.read_bytes())
    checkout["repos"][repo_id] = {"root": str(other)}
    path = harness.root / "knowledge/rules/audit-current.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(header)
    meta["sources"][0]["locator"].update(repo_id=repo_id, path="other.c")
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body, encoding="utf-8")
    fixed = lint_report(harness, checkout)
    result = harness.run("maintain", {"operation_id": "other-module", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(result["data"]["audit_ref"])["references"][0]
    assert row["repo_id"] == repo_id and row["path"] == "other.c"
    assert row["current_source_matches"] is False and row["current_sha256"] == hashed((other / "other.c").read_bytes())
