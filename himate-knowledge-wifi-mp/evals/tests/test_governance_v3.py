"""V3 public deterministic checks against synthetic, isolated data only."""
import importlib.util
from pathlib import Path
import sys
import hashlib
import shutil
import yaml
import pytest

DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("wifi_v3", DOMAIN / "governance/contracts/__init__.py", submodule_search_locations=[str(DOMAIN / "governance/contracts")])
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)
from wifi_v3 import records, source_resources, validation as v  # noqa: E402

_repository_spec = importlib.util.spec_from_file_location(
    "test_governance_v3_repository_runtime_fixture",
    Path(__file__).resolve().parents[3] / "himate-knowledge-wifi-mp/evals/contract_test_support.py",
)
_repository_fixture = importlib.util.module_from_spec(_repository_spec)
_repository_spec.loader.exec_module(_repository_fixture)


@pytest.fixture
def rules(tmp_path):
    shutil.copytree(DOMAIN / "governance", tmp_path / "governance")
    _repository_fixture.copy_runtime(tmp_path)
    lock_path = tmp_path / "governance/framework.lock.yaml"
    return v.load_rules(tmp_path, hashlib.sha256(lock_path.read_bytes()).hexdigest())


def scan():
    return records.seal({"schema_version": "2.0", "record_kind": "source_inventory", "operation_id": "op", "scope": ["docs-raw/specs"], "full_scan": True, "complete": True, "units": [{"unit_id": "u1", "path": "docs-raw/specs/a.md", "source_id": "s1", "observed_fingerprint": "a" * 64, "previous_fingerprint": None, "change": "new", "read_error": None, "progress": None}]})


def test_ingest_record_requires_exact_fixed_scan_unit_coverage():
    inventory = scan()
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "dispositions": []})
    with pytest.raises(v.ContractError, match="coverage"):
        records.validate_ingest_record(record, inventory)


def test_observed_version_cannot_be_claimed_as_completed_without_adoption():
    inventory = scan()
    item = {"unit_id": "u1", "action": "update", "reason": "new source", "observed_fingerprint": "a" * 64, "adopted_fingerprint": None, "progress": "completed", "card_refs": [], "claim_refs": []}
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory, "dispositions": [item]})
    with pytest.raises(v.ContractError, match="adopt"):
        records.validate_ingest_record(record)


def test_markdown_links_keep_real_line_and_resolve_duplicate_headings():
    parsed = v.markdown_structure(b"# Title\n[real](b.md#part) ` [fake](bad.md)`\n```md\n[fake](bad.md)\n```\n## Part\n## Part\n")
    assert [(item["target"], item["line"]) for item in parsed["links"]] == [("b.md#part", 2)]
    assert {"title", "part", "part-1"}.issubset(parsed["anchors"])


def test_source_reference_rejects_out_of_range_locator_on_exact_bytes():
    import hashlib
    data = b"one\ntwo\n"
    lock = {"resources": [{"source_id": "s1"}], "snapshots": [{"source_id": "s1", "snapshot_id": "raw:one", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}]}
    ref = {"evidence_ref": "e1", "source_id": "s1", "snapshot_id": "raw:one", "locator": {"kind": "lines", "start": 1, "end": 3}}
    with pytest.raises(v.ContractError, match="locator"):
        source_resources.validate_reference(ref, lock, lambda snapshot: data)


def test_formal_checks_collect_format_and_link_findings_without_catalog(rules):
    from wifi_v3 import checks
    view = {"mode": "formal", "root": rules["knowledge_root"], "files": {"knowledge/concepts/a.md": b"---\nbad: true\n---\n# Card\n", "knowledge/index.md": b"[missing](lost.md#part)"}, "identity": {"fixture": "formal"}}
    report = checks.run(view, rules)
    assert report["exit_code"] == 1
    assert {row["group"] for row in report["checks"] if row["status"] == "failed"} >= {"format", "relation"}
    assert report["scope"]["kind"] == "full"
    assert checks.validate_report(report)["status"] == "failed"


def test_lint_public_cli_needs_no_catalog_and_preserves_formal_tree(rules, tmp_path):
    import json
    import subprocess
    cli = DOMAIN.parent / "skills/common/knowledge/hs-knowledge-lint/scripts/cli.py"
    output = tmp_path / "logs/report.json"
    before = {str(path): path.read_bytes() for path in (rules["knowledge_root"] / "governance").rglob("*") if path.is_file()}
    result = subprocess.run([sys.executable, str(cli), "--knowledge-root", str(rules["knowledge_root"]), "--rules-digest", rules["rules_digest"], "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_bytes())
    assert report["status"] == "passed" and report["complete"]
    assert report["code_check_status"] == "not_applicable"
    assert all(path.read_bytes() == raw for name, raw in before.items() for path in [Path(name)])


def test_ci_uses_trusted_rules_and_never_imports_candidate_program(rules, tmp_path):
    import json
    import subprocess
    candidate = tmp_path / "candidate"
    (candidate / "governance/contracts").mkdir(parents=True)
    (candidate / "governance/contracts/validation.py").write_text("raise AssertionError('candidate code executed')", encoding="utf-8")
    shutil.copyfile(rules["knowledge_root"] / "governance/sources.lock.yaml", candidate / "governance/sources.lock.yaml")
    output = tmp_path.parent / (tmp_path.name + "-ci-report.json")
    result = subprocess.run([sys.executable, str(DOMAIN / "check.py"), "--trusted-root", str(rules["knowledge_root"]), "--candidate-root", str(candidate), "--rules-digest", rules["rules_digest"], "--commit", "fixture-commit", "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_bytes())
    assert report["mode"] == "ci" and report["object"]["commit"] == "fixture-commit"
    assert report["rules_digest"] == rules["rules_digest"]


def test_report_cannot_hide_an_error_finding_behind_passed_checks(rules):
    from wifi_v3 import checks
    report = checks.run({"mode": "formal", "root": rules["knowledge_root"], "files": {}}, rules)
    report["findings"].append({"check_id": "format.cards", "code": "BAD", "severity": "error", "path": "knowledge/a.md", "line": 1, "reason": "bad"})
    report["digest"] = v.digest_payload(report)
    with pytest.raises(v.ContractError, match="report|Report"):
        checks.validate_report(report)


def test_completed_record_cannot_invent_card_reference():
    inventory = scan()
    item = {"unit_id": "u1", "action": "update", "reason": "adopted", "observed_fingerprint": "a" * 64, "adopted_fingerprint": "a" * 64, "progress": "completed", "card_refs": ["missing-card"], "claim_refs": []}
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory, "dispositions": [item]})
    with pytest.raises(v.ContractError, match="card|Card"):
        records.validate_ingest_record(record, view={"writes": []})


def test_code_fixed_check_does_not_accept_a_truthy_checkout_label(rules):
    card = {"metadata": {"sources": [], "scope": {"contexts": []}}}
    with pytest.raises(v.ContractError, match="configuration|checkout"):
        source_resources.validate_code_references(card, {"resources": [], "snapshots": []}, "latest", rules)


def test_current_code_identity_requires_the_complete_protected_context(rules):
    with pytest.raises(v.ContractError, match="identity|context"):
        source_resources.validate_current_code_identity({}, "absent-config.yml", "a" * 64, rules, {})


def test_unreadable_scan_unit_cannot_be_finished_by_substantive_skip():
    inventory = scan()
    inventory["units"][0].update(change="read_failed", read_error="Access denied")
    inventory = records.seal(inventory)
    item = {"unit_id": "u1", "action": "skip", "reason": "not read", "observed_fingerprint": "a" * 64, "adopted_fingerprint": None, "progress": "skipped", "card_refs": [], "claim_refs": [], "skip_sample": {"independent": True, "reviewer": "reviewer", "reason": "sampled"}}
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory, "dispositions": [item]})
    with pytest.raises(v.ContractError, match="unread|Unread|incomplete|Incomplete"):
        records.validate_ingest_record(record)


def test_record_cannot_drop_maintenance_claims_when_raw_has_no_changes():
    inventory = scan()
    inventory["units"] = []
    inventory["current_context"] = {"affected_claims": [{"card_id": "card", "claim_id": "c1", "reason": "code_changed"}]}
    inventory = records.seal(inventory)
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory, "dispositions": []})
    with pytest.raises(v.ContractError, match="[Mm]aintenance"):
        records.validate_ingest_record(record)


def test_shared_record_without_fixed_inventory_cannot_skip_unit_coverage():
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "scan_ref": ".build/from-another-machine.json", "scan_digest": "a" * 64, "dispositions": []})
    with pytest.raises(v.ContractError, match="inventory|[Ss]can"):
        records.validate_ingest_record(record)


def test_existing_malformed_source_lock_fails_even_when_library_is_empty(rules):
    from wifi_v3 import checks
    report = checks.run({"mode": "formal", "root": rules["knowledge_root"], "files": {"governance/sources.lock.yaml": b"schema_version: '2.0'\nresources: []\nsnapshots: broken\n"}}, rules)
    assert report["exit_code"] == 1
    assert next(row for row in report["checks"] if row["group"] == "source")["status"] == "failed"


def test_deprecated_code_card_checks_its_exact_original_without_current_checkout(rules):
    from wifi_v3 import checks
    card_spec = importlib.util.spec_from_file_location("retired_card_fixture", DOMAIN / "evals/tests/test_contracts.py")
    card_fixture = importlib.util.module_from_spec(card_spec)
    card_spec.loader.exec_module(card_fixture)
    original = b"old code\nretired implementation\n"
    lock = {"schema_version": "2.0", "resources": [{"source_id": "s1", "kind": "code"}], "snapshots": [{"source_id": "s1", "snapshot_id": "raw:one", "sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original), "recovery": {"path": "logs/evidence/old.bin"}}]}
    card = card_fixture.card_data(lifecycle="deprecated", review_mode="code_gate", deprecation_reason="Implementation removed", replacement=[])
    view = {"mode": "formal", "root": rules["knowledge_root"], "files": {"knowledge/concepts/entities/a.md": card, "knowledge/concepts/entities/index.md": b"[Old card](a.md)\n", "governance/sources.lock.yaml": json_bytes(lock)}}
    report = checks.run(view, rules, inputs={"source_objects": {"raw:one": original}})
    assert report["exit_code"] == 0
    assert report["code_check_status"] == "not_applicable"


def json_bytes(value):
    import json
    return json.dumps(value).encode()


def test_current_code_check_projects_claim_sources_and_keeps_current_version_strict(rules, tmp_path):
    import os
    import subprocess
    from wifi_v3 import checks
    knowledge_root = tmp_path / "wiki"
    knowledge_root.mkdir()
    rules = dict(rules, knowledge_root=knowledge_root)
    code = tmp_path / "code"
    code.mkdir()
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(code), *args], capture_output=True, check=True).stdout.decode().strip()
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("remote", "add", "origin", "fixture-origin")
    old = b"int projected_fixture(void) { return 1; }\n"
    current = b"int projected_fixture(void) { return 2; }\n"
    (code / "source.c").write_bytes(old)
    git("add", "source.c")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "old")
    (code / "source.c").write_bytes(current)
    git("add", "source.c")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "current")
    commit = git("rev-parse", "HEAD")
    normalized = v.normalize_workspace(yaml.safe_load((DOMAIN.parent / "config.yml").read_bytes()), DOMAIN.parent)
    legacy_fields = ("schema_version", "workspace_id", "knowledge_roots", "repos", "architecture",
                     "wiki_entities", "symbol_aliases", "targets", "pairs", "query")
    config = {field: normalized[field] for field in legacy_fields}
    config["knowledge_roots"] = {"wifi": "wiki"}
    config["repos"] = [{"repo_id": "fixture", "kind": "git", "root": str(code), "expected_identity": "fixture-origin"}]
    config["architecture"] = [{"binding_id": "fixture-code", "repo_id": "fixture", "module_root": ".",
                               "knowledge_domain": "wifi", "override_nested": False}]
    configuration = tmp_path / "config.yml"
    configuration.write_bytes(yaml.safe_dump(config).encode())
    card_spec = importlib.util.spec_from_file_location("mixed_code_card_fixture", DOMAIN / "evals/tests/test_contracts.py")
    card_fixture = importlib.util.module_from_spec(card_spec)
    card_spec.loader.exec_module(card_fixture)
    _, front, body = card_fixture.card_data(review_mode="code_gate").decode().split("---", 2)
    meta = yaml.safe_load(front)
    meta["sources"] = [{
        "evidence_ref": "e-" + label, "source_id": "s-" + label, "snapshot_id": "code:" + label,
        "locator": {"kind": "lines", "repo_id": "fixture", "path": "source.c", "start": 1, "end": 1},
        "code_ref": {"kind": "function", "name": "projected_fixture", "scope": [],
                     "parameter_types": [], "role": "definition"},
    } for label in ("old", "current")]
    now = dict(meta["claims"][0], id="now", source_refs=["e-current"], usage="current", evidence_kind="implementation")
    history = dict(meta["claims"][0], id="old", text_ref="#old", source_refs=["e-old"], usage="historical", evidence_kind="implementation")
    meta["claims"] = [now, history]
    card = ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body + '\n<a id="old"></a>\nOld historical implementation.\n').encode()
    lock = {"schema_version": "2.0", "resources": [{"source_id": "s-" + label, "kind": "code"} for label in ("old", "current")], "snapshots": [{"source_id": "s-" + label, "snapshot_id": "code:" + label, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "recovery": {"path": "logs/evidence/" + label}} for label, raw in (("old", old), ("current", current))]}
    files = {"knowledge/concepts/entities/a.md": card, "knowledge/concepts/entities/index.md": b"[Card](a.md)\n", "governance/sources.lock.yaml": json_bytes(lock)}
    view = {"mode": "formal", "root": rules["knowledge_root"], "files": files}
    inputs = {"source_objects": {"code:old": old, "code:current": current}, "code_checkout": {"configuration": str(configuration), "config_digest": hashlib.sha256(configuration.read_bytes()).hexdigest(), "repos": {"fixture": {"root": str(code), "commit": commit}}}}
    report = checks.run(view, rules, inputs=inputs)
    assert report["exit_code"] == 0, report["findings"]
    lock["snapshots"][1].update(sha256=hashlib.sha256(old).hexdigest(), bytes=len(old))
    files["governance/sources.lock.yaml"] = json_bytes(lock)
    inputs["source_objects"]["code:current"] = old
    denied = checks.run(view, rules, inputs=inputs)
    assert denied["exit_code"] == 1
    assert "CODE_FINGERPRINT_MISMATCH" in {item["code"] for item in denied["findings"]}


def test_shared_pending_rebuilds_a_block_without_a_local_event():
    inventory = scan()
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "record_id": "deferred", "batch_kind": "record_only", "status": "recorded", "progress": {"apply": {"status": "recorded", "operation_id": "op"}}, "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory,
        "dispositions": [{"unit_id": "u1", "action": "defer", "reason": "Needs investigation", "observed_fingerprint": "a" * 64, "adopted_fingerprint": None, "progress": "blocked", "card_refs": [], "claim_refs": []}], "pending": [{"card_id": "card", "claim_id": "c1", "outcome": "defer", "reason": "Unresolved assumption"}]})
    rebuilt = records.rebuild_restrictions([record])
    assert rebuilt["complete"] is True
    assert {(item["card_id"], item["claim_id"]) for item in rebuilt["blocked_claims"]} == {("card", "c1")}


def test_partial_source_progress_does_not_invalidate_an_already_reviewed_claim():
    inventory = scan()
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "record_id": "partial", "batch_kind": "content", "status": "applied", "progress": {"apply": {"status": "applied", "operation_id": "op"}}, "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory,
        "dispositions": [{"unit_id": "u1", "action": "update", "reason": "This Claim is reviewed; other source sections remain", "observed_fingerprint": "a" * 64, "adopted_fingerprint": "a" * 64, "progress": "partial", "card_refs": ["card"], "claim_refs": [{"card_id": "card", "claim_id": "c1"}]}]})
    rebuilt = records.rebuild_restrictions([record])
    assert rebuilt["complete"] is True
    assert rebuilt["blocked_claims"] == []


def maintenance_record(name, claim="c1", outcome="defer", parent=None, sample=None):
    inventory = scan()
    inventory.update(operation_id=name, units=[], current_context={"affected_claims": [{"card_id": "card", "claim_id": claim, "reason": "review"}]})
    inventory = records.seal(inventory)
    content = outcome == "content"
    status = "applied" if content else "recorded"
    row = {"unit_id": "maintenance:card#" + claim, "card_id": "card", "claim_id": claim, "outcome": outcome, "reason": "Explicit same-Claim review"}
    value = {"schema_version": "2.0", "record_kind": "ingest_record", "record_id": name, "operation_id": name, "rules_digest": "a" * 64, "batch_kind": "content" if content else "record_only", "status": status, "progress": {"apply": {"status": status, "operation_id": name}}, "scan_ref": ".build/scan.json", "scan_digest": inventory["digest"], "inventory": inventory, "dispositions": [], "maintenance_dispositions": [row], "prior_record_digests": [parent["digest"]] if parent else []}
    if content:
        value["content_view_digest"] = "d" * 64
        value["progress"]["apply"]["view_digest"] = "d" * 64
        value["acceptance"] = {"content_view_digest": "d" * 64, "rules_digest": "a" * 64, "proof_digests": ["b" * 64], "cards": [{"path": "knowledge/rules/card.md", "card_id": "card", "sha256": "c" * 64, "review_mode": "manual_document", "review_result": "supported", "claim_ids": [claim]}]}
    if sample:
        value["skip_sample"] = sample
    return records.seal(value)


def test_document_admission_summary_uses_agent_support_instead_of_human_approval():
    reviewed = maintenance_record("reviewed", outcome="content")
    records.validate_ingest_record(reviewed)
    reviewed["acceptance"]["cards"][0]["review_result"] = "approved"
    with pytest.raises(v.ContractError, match="INVALID_ACCEPTANCE"):
        records.validate_ingest_record(records.seal(reviewed))


def test_same_claim_disposition_clears_recorded_pending_without_process_credentials():
    pending = maintenance_record("pending")
    unrelated = maintenance_record("other", claim="c2", outcome="content", parent=pending)
    assert records.rebuild_restrictions([pending, unrelated])["blocked_claims"][0]["claim_id"] == "c1"
    resolved = maintenance_record("resolved", outcome="content", parent=pending)
    assert records.rebuild_restrictions([pending, resolved])["blocked_claims"] == []
    skip = maintenance_record("skip", outcome="skip", parent=pending)
    unverified = records.rebuild_restrictions([pending, skip])
    assert unverified["complete"] and not unverified["blocked_claims"]
    resolved.pop("acceptance")
    resolved = records.seal(resolved)
    assert records.rebuild_restrictions([pending, resolved])["blocked_claims"] == []
    reviewed = maintenance_record("skip-reviewed", outcome="skip", parent=pending, sample={"independent": True, "reviewer": "independent", "report_digest": "f" * 64, "reason": "Exact independent review"})
    assert records.rebuild_restrictions([pending, reviewed])["blocked_claims"] == []


def test_missing_shared_predecessor_never_silently_clears_a_restriction():
    pending = maintenance_record("pending")
    resolved = maintenance_record("resolved", outcome="content", parent=pending)
    resolved["prior_record_digests"].append("0" * 64)
    result = records.rebuild_restrictions([pending, records.seal(resolved)])
    assert not result["complete"] and result["blocked_claims"]
    assert result["gaps"][0]["code"] == "PROCESSING_PARENT_UNAVAILABLE"


def test_shared_resolution_must_bind_the_actually_applied_content_view():
    pending = maintenance_record("pending")
    resolved = maintenance_record("resolved", outcome="content", parent=pending)
    resolved["progress"]["apply"]["view_digest"] = "e" * 64
    result = records.rebuild_restrictions([pending, records.seal(resolved)])
    assert not result["complete"] and result["blocked_claims"]


def test_pending_requires_structured_objects_before_record_application():
    record = maintenance_record("pending")
    record["pending"] = ["review this later"]
    with pytest.raises(v.ContractError, match="[Pp]ending"):
        records.validate_ingest_record(records.seal(record))


@pytest.mark.parametrize("path_archive", [False, True])
def test_fixed_ci_rejects_phantom_formal_record_refs_without_python_callback(rules, tmp_path, path_archive):
    import json
    import os
    import subprocess
    workspace = tmp_path / "candidate-workspace"
    candidate = workspace / "himate-knowledge-wifi-mp"
    (candidate / "governance").mkdir(parents=True)
    (candidate / "logs/ingest").mkdir(parents=True)
    (candidate / "docs-raw/specs").mkdir(parents=True)
    raw = b"Existing unprocessed original.\n"
    (candidate / "docs-raw/specs/a.md").write_bytes(raw)
    (candidate / "governance/sources.lock.yaml").write_bytes(b"schema_version: '2.0'\nresources: []\nsnapshots: []\n")
    tool = {"skill": "hs-fixture", "package_digest": "a" * 64, "runtime": "synthetic", "requirements_digest": "b" * 64}
    inventory = scan()
    inventory.update(rules_digest=rules["rules_digest"], tool_identity=tool)
    inventory["units"][0]["observed_fingerprint"] = hashlib.sha256(raw).hexdigest()
    inventory = records.seal(inventory)
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "record_id": "phantom", "rules_digest": rules["rules_digest"], "tool_identity": tool,
        "batch_kind": "record_only", "status": "recorded", "progress": {"apply": {"status": "recorded", "operation_id": "op"}}, "scan_ref": ".build/old-machine/scan.json", "scan_digest": inventory["digest"], "inventory": inventory,
        "dispositions": [{"unit_id": "u1", "action": "defer", "reason": "Unresolved original", "observed_fingerprint": hashlib.sha256(raw).hexdigest(), "adopted_fingerprint": None, "progress": "blocked", "card_refs": ["phantom"], "claim_refs": [{"card_id": "phantom", "claim_id": "c1"}]}]})
    job_input = None
    if path_archive:
        record["dispositions"][0].update(card_refs=[{"path": "knowledge/rules/phantom.md"}], claim_refs=[])
        record = records.seal(record)
        fixture_spec = importlib.util.spec_from_file_location("unrelated_card_fixture", DOMAIN / "evals/tests/test_contracts.py")
        fixture = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixture)
        unrelated = fixture.card_data(id="unrelated", lifecycle="stable")
        archive = tmp_path.parent / (tmp_path.name + "-unrelated.md")
        archive.write_bytes(unrelated)
        job_input = tmp_path / "job-input.json"
        job_input.write_bytes(json_bytes({"inputs": {"historical_card_objects": {hashlib.sha256(unrelated).hexdigest(): str(archive)}}}))
    (candidate / "logs/ingest/phantom.yaml").write_bytes(json_bytes(record))
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(workspace), *args], capture_output=True, check=True).stdout.decode().strip()
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "formal record has no historical card at any version")
    output = tmp_path.parent / (tmp_path.name + "-phantom-ci.json")
    command = [sys.executable, str(DOMAIN / "check.py"), "--trusted-root", str(rules["knowledge_root"]), "--candidate-root", str(candidate), "--rules-digest", rules["rules_digest"], "--commit", git("rev-parse", "HEAD"), "--output", str(output)]
    if job_input:
        command += ["--input", str(job_input)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(output.read_bytes())
    assert "DANGLING_CARD_RECORD" in {row["code"] for row in report["findings"]}


@pytest.mark.parametrize("provide_history,expected", [(True, 0), (False, 2), ("tampered", 1), ("phantom_claim", 1)])
def test_lint_json_recovers_exact_old_record_card_after_current_card_update(rules, tmp_path, provide_history, expected):
    import json
    import subprocess
    fixture_spec = importlib.util.spec_from_file_location("history_card_fixture", DOMAIN / "evals/tests/test_contracts.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    old = fixture.card_data(lifecycle="stable")
    new = old.replace("职责说明。".encode(), "更新后的职责说明。".encode())
    old_sha = hashlib.sha256(old).hexdigest()
    raw = b"Original source\nSecond line\n"
    source = tmp_path / "docs-raw/specs/a.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(raw)
    card_path = "knowledge/concepts/entities/a.md"
    (tmp_path / card_path).parent.mkdir(parents=True)
    (tmp_path / card_path).write_bytes(new)
    (tmp_path / "knowledge/concepts/entities/index.md").write_bytes(b"[Card](a.md)\n")
    source_sha = hashlib.sha256(raw).hexdigest()
    lock = {"schema_version": "2.0", "resources": [{"source_id": "s1", "kind": "raw"}], "snapshots": [{"source_id": "s1", "snapshot_id": "raw:one", "sha256": source_sha, "bytes": len(raw), "recovery": {"path": "logs/evidence/source"}}]}
    (tmp_path / "governance/sources.lock.yaml").write_bytes(json_bytes(lock))
    tool = {"skill": "hs-fixture", "package_digest": "a" * 64, "runtime": "synthetic", "requirements_digest": "b" * 64}
    inventory = scan()
    inventory.update(rules_digest=rules["rules_digest"], tool_identity=tool)
    inventory["units"][0]["observed_fingerprint"] = source_sha
    inventory = records.seal(inventory)
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op", "record_id": "historical", "rules_digest": rules["rules_digest"], "tool_identity": tool,
        "batch_kind": "content", "status": "applied", "content_view_digest": "d" * 64, "progress": {"apply": {"status": "applied", "operation_id": "op", "view_digest": "d" * 64}}, "scan_ref": ".build/old/scan.json", "scan_digest": inventory["digest"], "inventory": inventory,
        "dispositions": [{"unit_id": "u1", "action": "update", "reason": "Original adopted version", "observed_fingerprint": source_sha, "adopted_fingerprint": source_sha, "progress": "completed", "card_refs": [{"card_id": "card-a", "sha256": old_sha}], "claim_refs": [{"card_id": "card-a", "claim_id": "missing" if provide_history == "phantom_claim" else "c1"}]}],
        "acceptance": {"content_view_digest": "d" * 64, "rules_digest": rules["rules_digest"], "proof_digests": ["b" * 64], "cards": [{"path": card_path, "card_id": "card-a", "sha256": old_sha, "review_mode": "manual_document", "review_result": "supported", "claim_ids": ["c1"]}]}})
    formal = tmp_path / "logs/ingest/history.yaml"
    formal.parent.mkdir(parents=True)
    formal.write_bytes(json_bytes(record))
    inputs = {"source_objects": {"raw:one": str(source)}}
    if provide_history:
        archive = tmp_path.parent / (tmp_path.name + "-old.md")
        archive.write_bytes(old + b"\n" if provide_history == "tampered" else old)
        inputs["historical_card_objects"] = {old_sha: str(archive)}
    request = tmp_path / "logs/request.json"
    request.write_bytes(json_bytes({"mode": "formal", "inputs": inputs}))
    output = tmp_path / "logs/result.json"
    result = subprocess.run([sys.executable, str(DOMAIN.parent / "skills/common/knowledge/hs-knowledge-lint/scripts/cli.py"), "--knowledge-root", str(tmp_path), "--rules-digest", rules["rules_digest"], "--input", str(request), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr
    if not provide_history:
        report = json.loads(output.read_bytes())
        assert "RECORD_HISTORY_UNAVAILABLE" in {row["code"] for row in report["findings"]}


def test_lint_recovers_the_record_version_from_real_git_without_archive_input(rules, tmp_path):
    import os
    import subprocess
    workspace = tmp_path / "workspace"
    domain = workspace / "himate-knowledge-wifi-mp"
    shutil.copytree(tmp_path / "governance", domain / "governance")
    _repository_fixture.copy_runtime(domain)
    test_lint_json_recovers_exact_old_record_card_after_current_card_update({**rules, "knowledge_root": domain}, domain, True, 0)
    path = domain / "knowledge/concepts/entities/a.md"
    current = path.read_bytes()
    old = (workspace / (domain.name + "-old.md")).read_bytes()
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(workspace), *args], capture_output=True, check=True).stdout.decode().strip()
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    path.write_bytes(old)
    git("add", domain.name + "/knowledge", domain.name + "/logs/ingest", domain.name + "/governance/sources.lock.yaml", domain.name + "/docs-raw")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "original card adopted by fixed record")
    path.write_bytes(current)
    git("add", domain.name + "/knowledge")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "current card updated without rewriting old record")
    request = domain / "logs/git-request.json"
    request.write_bytes(json_bytes({"mode": "formal", "inputs": {"source_objects": {"raw:one": str(domain / "docs-raw/specs/a.md")}}}))
    output = domain / "logs/git-result.json"
    result = subprocess.run([sys.executable, str(DOMAIN.parent / "skills/common/knowledge/hs-knowledge-lint/scripts/cli.py"), "--knowledge-root", str(domain), "--rules-digest", rules["rules_digest"], "--input", str(request), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def adopted_card_versions(rules, tmp_path):
    """A real old adoption without an acceptance/card-hash extension."""
    from wifi_v3 import knowledge
    fixture_spec = importlib.util.spec_from_file_location("adoption_card_fixture", DOMAIN / "evals/tests/test_contracts.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    path = "knowledge/concepts/entities/a.md"
    old_source, new_source = hashlib.sha256(b"old source").hexdigest(), hashlib.sha256(b"new source").hexdigest()
    lock = {"resources": [{"source_id": "s1", "kind": "raw"}], "snapshots": [
        {"source_id": "s1", "snapshot_id": "raw:one", "sha256": old_source},
        {"source_id": "s1", "snapshot_id": "raw:two", "sha256": new_source}]}
    old = knowledge.parse_card(fixture.card_data(lifecycle="stable"), path, rules)
    new_raw = fixture.card_data(lifecycle="stable", sources=[{**old["metadata"]["sources"][0], "snapshot_id": "raw:two"}])
    current = knowledge.parse_card(new_raw, path, rules)
    inventory = scan()
    tool = {"skill": "hs-fixture", "package_digest": "a" * 64, "runtime": "synthetic", "requirements_digest": "b" * 64}
    inventory.update(rules_digest=rules["rules_digest"], tool_identity=tool)
    inventory["units"][0]["observed_fingerprint"] = old_source
    inventory = records.seal(inventory)
    disposition = {"unit_id": "u1", "action": "update", "reason": "Adopted the original source version",
        "observed_fingerprint": old_source, "adopted_fingerprint": old_source, "progress": "completed",
        "card_refs": ["card-a"], "claim_refs": ["card-a#c1"]}
    record = records.seal({"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "op",
        "record_id": "old-adoption", "rules_digest": rules["rules_digest"], "tool_identity": tool,
        "batch_kind": "content", "status": "applied", "content_view_digest": "d" * 64,
        "progress": {"apply": {"status": "applied", "operation_id": "op", "view_digest": "d" * 64}},
        "scan_ref": ".build/original/scan.json", "scan_digest": inventory["digest"], "inventory": inventory,
        "dispositions": [disposition]})
    return fixture, {**rules, "source_lock": lock}, record, old, current


@pytest.mark.parametrize("reference", ["card-a", {"path": "knowledge/concepts/entities/a.md"}])
def test_unpinned_adoption_selects_old_source_version_even_with_current_card_in_view(rules, tmp_path, reference):
    from wifi_v3 import checks
    _, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    record["dispositions"][0]["card_refs"] = [reference]
    record = records.seal(record)
    archive = tmp_path / "old-card.md"
    archive.write_bytes(old["raw"])
    resolver = checks._record_resolver({"card-a": current}, rules,
        {"historical_card_objects": {old["sha256"]: str(archive)}}, tmp_path, {})
    assert records.validate_ingest_record(record, view={"current": current}, rules=rules, version_resolver=resolver) == record


def test_old_source_archive_precedes_same_id_current_card_with_other_sources(rules, tmp_path):
    from wifi_v3 import checks, knowledge
    fixture, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    current = knowledge.parse_card(fixture.card_data(lifecycle="stable", sources=[
        {**current["metadata"]["sources"][0], "source_id": "s2"}]), current["path"], rules)
    archive = tmp_path / "old-card.md"
    archive.write_bytes(old["raw"])
    resolver = checks._record_resolver({"card-a": current}, rules,
        {"historical_card_objects": {old["sha256"]: str(archive)}}, tmp_path, {})
    records.validate_ingest_record(record, rules=rules, version_resolver=resolver)


@pytest.mark.parametrize("fault,code", [
    ("missing", "RECORD_HISTORY_UNAVAILABLE"),
    ("different_source_version", "RECORD_HISTORY_UNAVAILABLE"),
    ("different_id", "RECORD_HISTORY_UNAVAILABLE"),
    ("changed_archive", "HISTORICAL_CARD_CHANGED"),
    ("snapshot_owner", "RECORD_HISTORY_UNAVAILABLE"),
    ("claim_only_in_current", "RECORD_HISTORY_UNAVAILABLE"),
    ("exact_sha_current", "ADOPTION_SOURCE_MISMATCH"),
])
def test_unpinned_history_cannot_use_latest_or_relax_exact_bindings(rules, tmp_path, fault, code):
    from wifi_v3 import checks, knowledge
    fixture, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    raw, expected = old["raw"], old["sha256"]
    if fault == "different_source_version":
        raw, expected = current["raw"], current["sha256"]
    elif fault == "different_id":
        raw = fixture.card_data(id="another-card", lifecycle="stable")
        expected = hashlib.sha256(raw).hexdigest()
    elif fault == "changed_archive":
        raw += b"\n"
    elif fault == "snapshot_owner":
        rules["source_lock"]["snapshots"][0]["source_id"] = "s2"
    elif fault == "claim_only_in_current":
        claim = {**current["metadata"]["claims"][0], "id": "c2", "text_ref": "#c2"}
        raw_current = fixture.card_data(lifecycle="stable", sources=current["metadata"]["sources"],
            claims=[*current["metadata"]["claims"], claim]) + b'\n<a id="c2"></a>\nA new Claim.\n'
        current = knowledge.parse_card(raw_current, current["path"], rules)
        record["dispositions"][0]["claim_refs"] = ["card-a#c2"]
    elif fault == "exact_sha_current":
        record["dispositions"][0]["card_refs"] = [{"card_id": "card-a", "sha256": current["sha256"]}]
    archive = tmp_path / "declared-card.md"
    archive.write_bytes(raw)
    inputs = {} if fault == "missing" else {"historical_card_objects": {expected: str(archive)}}
    resolver = checks._record_resolver({"card-a": current}, rules, inputs, tmp_path, {})
    with pytest.raises(v.ContractError) as caught:
        records.validate_ingest_record(records.seal(record), view={"current": current}, rules=rules, version_resolver=resolver)
    assert caught.value.code == code


@pytest.mark.parametrize("compatible_body", [False, True])
def test_one_historical_card_body_must_satisfy_all_completed_source_units(rules, tmp_path, compatible_body):
    from wifi_v3 import checks, knowledge
    fixture, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    old_b, new_b = hashlib.sha256(b"old b").hexdigest(), hashlib.sha256(b"new b").hexdigest()
    rules["source_lock"]["snapshots"] += [
        {"source_id": "s2", "snapshot_id": "raw:b-old", "sha256": old_b},
        {"source_id": "s2", "snapshot_id": "raw:b-new", "sha256": new_b}]
    unit = {**record["inventory"]["units"][0], "unit_id": "u2", "source_id": "s2",
        "path": "docs-raw/specs/b.md", "observed_fingerprint": old_b}
    record["inventory"]["units"].append(unit)
    record["inventory"] = records.seal(record["inventory"])
    record["scan_digest"] = record["inventory"]["digest"]
    record["dispositions"].append({**record["dispositions"][0], "unit_id": "u2",
        "observed_fingerprint": old_b, "adopted_fingerprint": old_b})
    objects = {}
    # Each fractured version satisfies a different unit. They cannot be spliced
    # together into a card body that has never existed.
    versions = [("raw:one", "raw:b-new"), ("raw:two", "raw:b-old")]
    if compatible_body:
        versions.append(("raw:one", "raw:b-old"))
    for number, (source_a, source_b) in enumerate(versions):
        sources = [{**old["metadata"]["sources"][0], "snapshot_id": source_a},
                   {**old["metadata"]["sources"][0], "evidence_ref": "e2", "source_id": "s2", "snapshot_id": source_b}]
        raw = fixture.card_data(lifecycle="stable", sources=sources,
            claims=[{**old["metadata"]["claims"][0], "source_refs": ["e1", "e2"]}])
        archive = tmp_path / ("card-version-" + str(number) + ".md")
        archive.write_bytes(raw)
        objects[hashlib.sha256(raw).hexdigest()] = str(archive)
    # Include both sources in current, otherwise it would be an unrelated-card
    # association and the collective adoption check would supply the constraint.
    current_raw = fixture.card_data(lifecycle="stable", sources=[
        {**old["metadata"]["sources"][0], "snapshot_id": "raw:two"},
        {**old["metadata"]["sources"][0], "evidence_ref": "e2", "source_id": "s2", "snapshot_id": "raw:b-new"}],
        claims=[{**old["metadata"]["claims"][0], "source_refs": ["e1", "e2"]}])
    current = knowledge.parse_card(current_raw, current["path"], rules)
    resolver = checks._record_resolver({"card-a": current}, rules, {"historical_card_objects": objects}, tmp_path, {})
    record = records.seal(record)
    if compatible_body:
        records.validate_ingest_record(record, rules=rules, version_resolver=resolver)
    else:
        with pytest.raises(v.ContractError, match="RECORD_HISTORY_UNAVAILABLE"):
            records.validate_ingest_record(record, rules=rules, version_resolver=resolver)


def test_adoption_remains_a_collective_card_set_check(rules, tmp_path, monkeypatch):
    from wifi_v3 import checks, knowledge
    fixture, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    rules["source_lock"]["resources"].append({"source_id": "s2", "kind": "raw"})
    rules["source_lock"]["snapshots"].append({"source_id": "s2", "snapshot_id": "raw:unrelated",
        "sha256": hashlib.sha256(b"unrelated source").hexdigest()})
    supporting = knowledge.parse_card(fixture.card_data(id="supporting", lifecycle="stable", sources=[
        {**old["metadata"]["sources"][0], "source_id": "s2", "snapshot_id": "raw:unrelated"}]),
        "knowledge/concepts/entities/supporting.md", rules)
    record["dispositions"][0]["card_refs"].append("supporting")
    record["dispositions"][0]["claim_refs"].append("supporting#c1")
    archive = tmp_path / "old-card.md"
    archive.write_bytes(old["raw"])
    resolver = checks._record_resolver({"card-a": current, "supporting": supporting}, rules,
        {"historical_card_objects": {old["sha256"]: str(archive)}}, tmp_path, {})
    def unexpected_git(*args, **kwargs):
        raise AssertionError("Declared adopted bodies and unrelated current associations do not require Git history")
    monkeypatch.setattr(checks.subprocess, "run", unexpected_git)
    records.validate_ingest_record(records.seal(record), rules=rules, version_resolver=resolver)


@pytest.mark.parametrize("metadata_only", [False, True])
def test_two_argument_python_record_resolver_keeps_its_call_contract(rules, tmp_path, metadata_only):
    _, rules, record, old, current = adopted_card_versions(rules, tmp_path)
    calls = []
    def resolve(reference, fixed_record):
        calls.append((reference, fixed_record["digest"]))
        return old["metadata"] if metadata_only else old
    records.validate_ingest_record(record, view={"current": current}, rules=rules, version_resolver=resolve)
    assert calls == [("card-a", record["digest"])]


@pytest.mark.parametrize("complete_archive", [True, False])
def test_same_source_version_needs_one_body_with_all_recorded_claims(rules, tmp_path, complete_archive):
    from wifi_v3 import checks, knowledge
    fixture, rules, record, old, _ = adopted_card_versions(rules, tmp_path)
    c1 = old["metadata"]["claims"][0]
    c2 = {**c1, "id": "c2", "text_ref": "#c2"}
    current_raw = fixture.card_data(lifecycle="stable", claims=[c2]).replace(b'id="c1"', b'id="c2"')
    current = knowledge.parse_card(current_raw, old["path"], rules)
    record["dispositions"][0]["claim_refs"] = ["card-a#c1", "card-a#c2"]
    raw = (fixture.card_data(lifecycle="stable", claims=[c1, c2]) + b'\n<a id="c2"></a>\nSecond original Claim.\n') if complete_archive else old["raw"]
    archive = tmp_path / "old-claims.md"
    archive.write_bytes(raw)
    resolver = checks._record_resolver({"card-a": current}, rules,
        {"historical_card_objects": {hashlib.sha256(raw).hexdigest(): str(archive)}}, tmp_path, {})
    record = records.seal(record)
    if complete_archive:
        records.validate_ingest_record(record, rules=rules, version_resolver=resolver)
    else:
        # c1 and c2 exist in separate bodies with the same source hash. Their
        # existence cannot be combined into the one body named by this record.
        with pytest.raises(v.ContractError, match="RECORD_HISTORY_UNAVAILABLE"):
            records.validate_ingest_record(record, rules=rules, version_resolver=resolver)


def test_record_resolver_typeerror_is_not_retried_or_hidden(rules, tmp_path):
    _, rules, record, _, _ = adopted_card_versions(rules, tmp_path)
    calls = []
    def resolve(reference, fixed_record):
        calls.append(reference)
        raise TypeError("resolver body failed")
    with pytest.raises(TypeError, match="resolver body failed"):
        records.validate_ingest_record(record, rules=rules, version_resolver=resolve)
    assert calls == ["card-a"]


@pytest.mark.parametrize("metadata_only", [False, True])
def test_python_resolver_cannot_splice_two_versions_of_one_card(rules, tmp_path, metadata_only):
    from wifi_v3 import knowledge
    fixture, rules, record, old, _ = adopted_card_versions(rules, tmp_path)
    old_b = hashlib.sha256(b"old b").hexdigest()
    rules["source_lock"]["snapshots"].append({"source_id": "s2", "snapshot_id": "raw:b", "sha256": old_b})
    other = knowledge.parse_card(fixture.card_data(lifecycle="stable", sources=[
        {**old["metadata"]["sources"][0], "source_id": "s2", "snapshot_id": "raw:b"}]), old["path"], rules)
    record["inventory"]["units"].append({**record["inventory"]["units"][0], "unit_id": "u2", "source_id": "s2",
        "path": "docs-raw/specs/b.md", "observed_fingerprint": old_b})
    record["inventory"] = records.seal(record["inventory"])
    record["scan_digest"] = record["inventory"]["digest"]
    record["dispositions"].append({**record["dispositions"][0], "unit_id": "u2",
        "observed_fingerprint": old_b, "adopted_fingerprint": old_b})
    versions = iter([old, other])
    def resolve(reference, fixed_record):
        version = next(versions)
        return version["metadata"] if metadata_only else version
    with pytest.raises(v.ContractError, match="CARD_VERSION_MISMATCH"):
        records.validate_ingest_record(records.seal(record), rules=rules, version_resolver=resolve)
