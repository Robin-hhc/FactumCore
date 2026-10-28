"""Registered actual-code capture; all repositories and receipts are synthetic."""

import hashlib
import json
import os
import subprocess

import pytest
import yaml


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def setup_code(harness, *, git=False):
    repo = harness.base / "authorized-code"
    repo.mkdir()
    (repo / "sample.c").write_bytes(b"int synthetic(void) { return 1; }\n")
    head = None
    if git:

        def run(*args):
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo), *args],
                capture_output=True,
                check=True,
            )
            return result.stdout.decode().strip()

        run("init", "-b", "main")
        run("config", "user.name", "Synthetic fixture")
        run("config", "user.email", "synthetic@example.invalid")
        run("add", "sample.c")
        run("commit", "-m", "Synthetic code fixture")
        head = run("rev-parse", "HEAD")
        run("config", "core.fsmonitor", "echo unsafe > fsmonitor-executed.txt")
    policy = {"repo_roots": {"code": str(repo)}, "allowed_ref": "refs/heads/main"}
    chips = ["chip12", "chip08", "chip07c"]
    config = {
        "schema_version": "2.0",
        "workspace_id": "synthetic-workspace",
        "knowledge_roots": {"wifi": harness.root.name},
        "repos": [
            {
                "repo_id": "code",
                "kind": "git" if git else "export",
                "root": str(repo),
                "expected_identity": None,
            }
        ],
        "architecture": [
            {
                "binding_id": "synthetic-code",
                "repo_id": "code",
                "module_root": ".",
                "knowledge_domain": "wifi",
                "override_nested": False,
            }
        ],
        "wiki_entities": {},
        "symbol_aliases": {},
        "targets": [
            {
                "target_id": chip + "-" + side,
                "chip": chip,
                "side": side,
                "source_bindings": [],
                "module_roots": [],
                "build_profile": None,
                "required_features": [],
                "protocol_versions": [],
            }
            for chip in chips
            for side in ["host", "device"]
        ],
        "pairs": [
            {
                "pairing_id": chip + "-host-device",
                "host_target": chip + "-host",
                "device_target": chip + "-device",
                "compatibility_policy": "unknown",
            }
            for chip in chips
        ],
        "query": {"default_channel": "local", "allowed_channels": ["local", "shared"]},
        "code_policy": policy,
    }
    raw = yaml.safe_dump(config).encode()
    (harness.root.parent / "config.yml").write_bytes(raw)
    context = {
        "schema_version": "2.0",
        "record_kind": "project_context",
        "operation_id": "context",
        "rules_digest": harness.rules,
        "tool_identity": {
            "skill": "hs-knowledge-explore",
            "package_digest": "0" * 64,
            "runtime": "synthetic-test",
            "requirements_digest": "0" * 64,
        },
        "state": "context_loaded",
        "workspace_id": "synthetic-workspace",
        "knowledge_root": str(harness.root),
        "workspace_root": str(harness.root.parent),
        "config_path": str(harness.root.parent / "config.yml"),
        "config_digest": hashlib.sha256(raw).hexdigest(),
        "entries": [],
        "repos": {
            "code": {
                "repo_id": "code",
                "root": str(repo),
                "head": head,
                "dirty": "unknown",
            }
        },
    }
    context["digest"] = hashlib.sha256(canonical(context)).hexdigest()
    context_ref = harness.write(
        ".build/project-context/synthetic.json", canonical(context)
    )
    catalog = json.loads(harness.catalog.read_text())
    catalog["code_policy"] = policy
    harness.catalog.write_bytes(canonical(catalog))
    return repo, context_ref


@pytest.mark.parametrize("git", [False, True])
def test_registered_export_or_dirty_git_fixes_actual_bytes_without_touching_code(
    harness, git
):
    repo, context = setup_code(harness, git=git)
    actual = b"int synthetic(void) { return 2; }\n"
    (repo / "sample.c").write_bytes(actual)
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "code-op",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
     action="capture")
    bundle = harness.record(result["data"]["bundle_ref"])
    snapshot = bundle["snapshots"][0]
    assert snapshot["sha256"] == hashlib.sha256(actual).hexdigest()
    assert snapshot["recovery"]["method"] == "evidence_object"
    assert (harness.root / snapshot["recovery"]["path"]).read_bytes() == actual
    assert snapshot["code_identity"]["checked_file_dirty"] is (True if git else None)
    assert bool(snapshot["code_identity"]["revision"]) is git
    assert bundle["resources"][0]["path"] == "sample.c"
    assert str(repo) not in canonical(bundle["resources"]).decode()
    assert (repo / "sample.c").read_bytes() == actual
    assert not (repo / "fsmonitor-executed.txt").exists()


def test_committed_code_is_portable_and_resolves_without_first_machine_cache(harness):
    repo, context_ref = setup_code(harness, git=True)
    expected = (repo / "sample.c").read_bytes()
    captured = harness.run("source-prepare", {"operation_id": "portable-code", "kind": "code", "repo_id": "code",
        "relative_path": "sample.c", "source_id": "portable-code", "context_ref": context_ref}, action="capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    snapshot = bundle["snapshots"][0]
    assert snapshot["code_identity"]["checked_file_dirty"] is False
    assert snapshot["recovery"] == {"kind": "git", "method": "git", "repo_id": "code",
        "commit": snapshot["code_identity"]["revision"], "path": "sample.c", "status": "available"}
    # No snapshot pointer is hand-edited. The second machine lacks the retained
    # object, extracted text and locators; only its configured Git objects remain.
    for ref in (snapshot["local_recovery"]["path"], snapshot["extraction"]["text_ref"], snapshot["extraction"]["locator_ref"]):
        (harness.root / ref).unlink()
    resolved = harness.run("source-prepare", {"operation_id": "read-portable-code", "bundle_ref": captured["data"]["bundle_ref"],
        "source_ref": {"evidence_ref": "e1", "source_id": "portable-code", "snapshot_id": snapshot["snapshot_id"],
                       "locator": {"kind": "lines", "start": 1, "end": 1}}}, "resolve-source")
    assert resolved["data"]["text"] == expected.decode()
    assert resolved["data"]["current_source_matches"] is True
    checked = harness.run("source-prepare", {"operation_id": "verify-portable-code", "bundle_ref": captured["data"]["bundle_ref"]}, "resolve")
    assert checked["phase"] == "resolved"
    bundle["snapshots"][0]["extraction"]["extractor"] = "unsupported-future-code-extractor:99"
    bundle.pop("digest")
    bundle["digest"] = hashlib.sha256(canonical(bundle)).hexdigest()
    incompatible_ref = harness.write(".build/operations/portable-code/incompatible-extractor.json", canonical(bundle))
    incompatible = harness.run("source-prepare", {"operation_id": "read-incompatible-code", "bundle_ref": incompatible_ref,
        "source_ref": {"evidence_ref": "e1", "source_id": "portable-code", "snapshot_id": snapshot["snapshot_id"],
                       "locator": {"kind": "lines", "start": 1, "end": 1}}}, "resolve-source", expected=3)
    assert incompatible["diagnostics"][0]["code"] == "SOURCE_EXTRACTION_UNAVAILABLE"


@pytest.mark.parametrize("relative", ["sample.c", "src/sample.c"])
def test_authorized_code_capture_and_git_replay_allow_a_different_owner(harness, monkeypatch, relative):
    repo, context_ref = setup_code(harness, git=True)
    if relative != "sample.c":
        path = repo / relative
        path.parent.mkdir()
        path.write_bytes((repo / "sample.c").read_bytes())
        subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(repo), "add", relative], check=True, capture_output=True)
        subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo), "commit", "-m", "Isolated nested-code fixture"], check=True, capture_output=True)
        context = harness.record(context_ref)
        context["repos"]["code"]["head"] = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
        context.pop("digest")
        context["digest"] = hashlib.sha256(canonical(context)).hexdigest()
        harness.write(context_ref, canonical(context))
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    captured = harness.run("source-prepare", {"operation_id": "other-owner", "kind": "code", "repo_id": "code",
        "relative_path": relative, "source_id": "other-owner", "context_ref": context_ref}, action="capture")
    snapshot = harness.record(captured["data"]["bundle_ref"])["snapshots"][0]
    assert snapshot["recovery"]["method"] == "git"
    assert snapshot["code_identity"]["checked_file_dirty"] is False
    assert not (repo / "fsmonitor-executed.txt").exists()


def test_explicit_gb18030_preserves_original_and_rebuilds_text_from_exact_git(harness):
    repo, context_ref = setup_code(harness, git=True)
    raw = b"// \xbd\xd3\xca\xd5\xbe\xdb\xba\xcf\xd6\xa1\nint receive(void) { return 1; }\n"
    expected_text = "// 接收聚合帧\nint receive(void) { return 1; }\n"
    (repo / "sample.c").write_bytes(raw)
    subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(repo), "add", "sample.c"], check=True, capture_output=True)
    subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo), "commit", "-m", "Isolated GB18030 fixture"], check=True, capture_output=True)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
    context = harness.record(context_ref)
    context["repos"]["code"]["head"] = head
    context.pop("digest")
    context["digest"] = hashlib.sha256(canonical(context)).hexdigest()
    harness.write(context_ref, canonical(context))
    captured = harness.run("source-prepare", {"operation_id": "gb-source", "kind": "code", "repo_id": "code",
        "relative_path": "sample.c", "source_id": "gb-source", "context_ref": context_ref, "text_encoding": "gb18030"}, action="capture")
    snapshot = harness.record(captured["data"]["bundle_ref"])["snapshots"][0]
    assert snapshot["extraction"]["extractor"] == "code-gb18030:1"
    assert snapshot["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (harness.root / snapshot["local_recovery"]["path"]).read_bytes() == raw
    for ref in (snapshot["local_recovery"]["path"], snapshot["extraction"]["text_ref"], snapshot["extraction"]["locator_ref"]):
        (harness.root / ref).unlink()
    response = harness.run("source-prepare", {"operation_id": "gb-replay", "bundle_ref": captured["data"]["bundle_ref"],
        "source_ref": {"evidence_ref": "e1", "source_id": "gb-source", "snapshot_id": snapshot["snapshot_id"],
                       "locator": {"kind": "lines", "start": 1, "end": 2}}}, "resolve-source")
    assert response["data"]["text"] == expected_text
    assert response["data"]["current_source_matches"] is True
    assert (repo / "sample.c").read_bytes() == raw


@pytest.mark.parametrize("encoding", ["auto", "gbk", "utf-16", None, ["gb18030"]])
def test_code_capture_rejects_unknown_or_ambiguous_explicit_encoding(harness, encoding):
    _, context_ref = setup_code(harness)
    result = harness.run("source-prepare", {"operation_id": "bad-codec", "kind": "code", "repo_id": "code",
        "relative_path": "sample.c", "source_id": "bad-codec", "context_ref": context_ref, "text_encoding": encoding}, expected=2, action="capture")
    assert result["diagnostics"][0]["code"] == "INVALID_CODE_ENCODING"
    assert not (harness.root / "logs/evidence").exists()


@pytest.mark.parametrize("encoding,raw", [("gb18030", b"\xff"), ("gb18030", b"//\0\n"), ("utf-8", b"\xff"), ("utf-8", b"//\0\n")])
def test_explicit_code_encoding_rejects_invalid_bytes_and_nul(harness, encoding, raw):
    repo, context_ref = setup_code(harness)
    (repo / "sample.c").write_bytes(raw)
    result = harness.run("source-prepare", {"operation_id": "unreadable-codec", "kind": "code", "repo_id": "code",
        "relative_path": "sample.c", "source_id": "unreadable-codec", "context_ref": context_ref, "text_encoding": encoding}, expected=2, action="capture")
    assert result["diagnostics"][0]["code"] == "UNREADABLE_CODE_TEXT"
    assert not (harness.root / "logs/evidence").exists()


def test_utf8_default_and_explicit_encoding_keep_original_snapshot_identity(harness):
    _, context_ref = setup_code(harness)
    request = {"operation_id": "default-utf8", "kind": "code", "repo_id": "code", "relative_path": "sample.c",
               "source_id": "same-utf8-source", "context_ref": context_ref}
    implicit = harness.run("source-prepare", request, action="capture")
    explicit = harness.run("source-prepare", {**request, "operation_id": "explicit-utf8", "text_encoding": "utf-8"}, action="capture")
    assert harness.record(implicit["data"]["bundle_ref"])["snapshots"] == harness.record(explicit["data"]["bundle_ref"])["snapshots"]


def test_payload_context_cannot_authorize_a_different_code_root(harness):
    _, context_ref = setup_code(harness)
    context = harness.record(context_ref)
    context["repos"]["code"]["root"] = str(harness.base / "not-authorized")
    context.pop("digest")
    context["digest"] = hashlib.sha256(canonical(context)).hexdigest()
    harness.write(context_ref, canonical(context))
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "escape",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context_ref,
        },
        expected=3,
     action="capture")
    assert result["status"] == "blocked"
    assert not (harness.root / "logs/evidence").exists()


def test_code_selection_cannot_escape_authorized_repository(harness):
    _, context = setup_code(harness)
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "escape",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "../secret.txt",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
        expected=2,
     action="capture")
    assert result["diagnostics"][0]["code"] == "UNSAFE_PATH"


def test_code_resolver_uses_config_without_catalog_and_preserves_frozen_bytes(
    harness,
):
    repo, context = setup_code(harness)
    original = (repo / "sample.c").read_bytes()
    captured = harness.run(
        "source-prepare",
        {
            "operation_id": "historical-code",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
     action="capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    source_ref = {
        "evidence_ref": "e1",
        "source_id": "synthetic-code",
        "snapshot_id": bundle["snapshots"][0]["snapshot_id"],
        "locator": {"kind": "lines", "start": 1, "end": 1},
    }
    request = {
        "operation_id": "resolve-code",
        "bundle_ref": captured["data"]["bundle_ref"],
        "source_ref": source_ref,
    }
    (repo / "sample.c").write_bytes(b"int changed(void) { return 3; }\n")
    resolved = harness.run("source-prepare", request, "resolve-source")["data"]
    assert resolved["text"] == original.decode()
    assert resolved["source_kind"] == "code"
    assert resolved["resource"]["repo_id"] == "code"
    assert resolved["current_source_matches"] is False
    catalog = json.loads(harness.catalog.read_text())
    catalog.pop("code_policy")
    harness.catalog.write_bytes(canonical(catalog))
    request["operation_id"] = "resolve-without-catalog-policy"
    without_catalog = harness.run("source-prepare", request, "resolve-source")["data"]
    assert without_catalog["text"] == original.decode()
    assert without_catalog["current_source_matches"] is False
    (harness.root.parent / "config.yml").unlink()
    request["operation_id"] = "resolve-without-config"
    historical = harness.run("source-prepare", request, "resolve-source")["data"]
    assert historical["text"] == original.decode()
    assert historical["current_source_matches"] is None
    assert any("historical" in gap for gap in historical["limitations"])


def test_explicit_code_change_event_blocks_old_claim_idempotently_without_rewriting(
    harness,
):
    repo, context = setup_code(harness)
    request = {
        "operation_id": "old-code",
        "kind": "code",
        "repo_id": "code",
        "relative_path": "sample.c",
        "source_id": "synthetic-code",
        "context_ref": context,
    }
    old_result = harness.run("source-prepare", request, action="capture")
    old = harness.record(old_result["data"]["bundle_ref"])
    card = harness.card("existing", old, lifecycle="stable")
    harness.write("knowledge/rules/existing.md", card)
    locked = yaml.safe_dump(
        {
            "schema_version": "2.0",
            "resources": old["resources"],
            "snapshots": old["snapshots"],
        }
    ).encode()
    harness.write("governance/sources.lock.yaml", locked)
    (repo / "sample.c").write_bytes(b"int changed(void) { return 3; }\n")
    request["operation_id"] = "new-code"
    new = harness.run("source-prepare", request, action="capture")
    assert not (harness.root / "logs/events/state.json").exists()
    registration = {"operation_id": "changed", "bundle_ref": new["data"]["bundle_ref"]}
    (repo / "sample.c").write_bytes(b"int changed_again(void) { return 4; }\n")
    rejected = harness.run("maintain", registration, "register-code-change", expected=3)
    assert rejected["diagnostics"][0]["code"] == "SOURCE_CHANGED"
    assert not (harness.root / "logs/events/state.json").exists()
    (repo / "sample.c").write_bytes(b"int changed(void) { return 3; }\n")
    result = harness.run("maintain", registration, "register-code-change")
    repeated = harness.run("maintain", registration, "register-code-change")
    assert result["data"]["event_refs"] == repeated["data"]["event_refs"]
    state = harness.record("logs/events/state.json")
    assert state["validity_epoch"] == 1
    assert state["blocked_claims"][0]["reason"] == "code_changed"
    assert state["blocked_claims"][0]["card_id"] == "existing"
    assert (harness.root / "knowledge/rules/existing.md").read_bytes() == card
    assert (harness.root / "governance/sources.lock.yaml").read_bytes() == locked


@pytest.mark.parametrize("raw", [b"", b"\xff\x00\x81"])
def test_machine_byte_locator_handles_empty_or_opaque_code_without_interpreted_text(
    harness, raw
):
    repo, context = setup_code(harness)
    (repo / "sample.c").write_bytes(raw)
    response = harness.run(
        "source-prepare",
        {
            "operation_id": "opaque",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "opaque",
            "context_ref": context,
        },
     action="capture")
    bundle = harness.record(response["data"]["bundle_ref"])
    request = {
        "operation_id": "opaque-resolve",
        "bundle_ref": response["data"]["bundle_ref"],
        "source_ref": {
            "evidence_ref": "e1",
            "source_id": "opaque",
            "snapshot_id": bundle["snapshots"][0]["snapshot_id"],
            "locator": {"kind": "bytes", "start": 0, "end": len(raw)},
        },
    }
    resolved = harness.run("source-prepare", request, "resolve-source")["data"]
    assert resolved["text"] is None
    assert resolved["bytes"] == len(raw)
    assert resolved["current_source_matches"] is True
    request["source_ref"]["locator"]["end"] += 1
    invalid = harness.run("source-prepare", request, "resolve-source", expected=2)
    assert invalid["diagnostics"][0]["code"] == "INVALID_SOURCE_LOCATOR"


def rewrite_configuration(harness, context_ref, change):
    config_path = harness.root.parent / "config.yml"
    config = yaml.safe_load(config_path.read_bytes())
    change(config)
    raw = yaml.safe_dump(config).encode()
    config_path.write_bytes(raw)
    receipt = harness.record(context_ref)
    receipt["config_digest"] = hashlib.sha256(raw).hexdigest()
    receipt.pop("digest")
    receipt["digest"] = hashlib.sha256(canonical(receipt)).hexdigest()
    harness.write(context_ref, canonical(receipt))


@pytest.mark.parametrize("field", ["knowledge_root", "binding_domain"])
def test_code_capture_enforces_current_wifi_domain_mapping(harness, field):
    _, context = setup_code(harness)

    def change(config):
        if field == "knowledge_root":
            config["knowledge_roots"]["wifi"] = "another-knowledge"
        else:
            config["architecture"][0]["knowledge_domain"] = "another-domain"

    rewrite_configuration(harness, context, change)
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "wrong-domain",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic",
            "context_ref": context,
        },
        expected=2 if field == "binding_domain" else 3,
     action="capture")
    # Exact workspace authorization now runs before code-policy loading. A
    # mapping to another knowledge root cannot authorize this root at all.
    assert result["diagnostics"][0]["code"] == (
        "SCHEMA_INVALID" if field == "binding_domain" else "CODE_AUTHORIZATION_REQUIRED"
    )
    assert not (harness.root / "logs/evidence").exists()


def test_code_capture_honors_actual_explore_commit_field(harness):
    _, context_ref = setup_code(harness, git=True)
    receipt = harness.record(context_ref)
    receipt["repos"]["code"].pop("head")
    receipt["repos"]["code"]["commit"] = "0" * 40
    receipt.pop("digest")
    receipt["digest"] = hashlib.sha256(canonical(receipt)).hexdigest()
    harness.write(context_ref, canonical(receipt))
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "stale-context",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic",
            "context_ref": context_ref,
        },
        expected=3,
     action="capture")
    assert result["diagnostics"][0]["code"] == "CODE_CONTEXT_STALE"


def test_history_survives_origin_mismatch_and_invalid_current_config(harness):
    repo, context_ref = setup_code(harness, git=True)
    expected_origin = "https://example.invalid/synthetic/code.git"
    subprocess.run(
        ["git", "-C", str(repo), "config", "remote.origin.url", expected_origin],
        check=True,
    )
    rewrite_configuration(
        harness,
        context_ref,
        lambda config: config["repos"][0].update(expected_identity=expected_origin),
    )
    result = harness.run(
        "source-prepare",
        {
            "operation_id": "fixed-code",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic",
            "context_ref": context_ref,
        },
     action="capture")
    bundle = harness.record(result["data"]["bundle_ref"])
    request = {
        "operation_id": "replay-code",
        "bundle_ref": result["data"]["bundle_ref"],
        "source_ref": {
            "evidence_ref": "e1",
            "source_id": "synthetic",
            "snapshot_id": bundle["snapshots"][0]["snapshot_id"],
            "locator": {"kind": "lines", "start": 1, "end": 1},
        },
    }
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "remote.origin.url",
            "https://example.invalid/other.git",
        ],
        check=True,
    )
    mismatched = harness.run("source-prepare", request, "resolve-source")["data"]
    assert mismatched["text"].startswith("int synthetic")
    assert mismatched["current_source_matches"] is None
    (harness.root.parent / "config.yml").write_bytes(b"invalid: true\n")
    unavailable = harness.run("source-prepare", request, "resolve-source")["data"]
    assert unavailable["text"] == mismatched["text"]
    assert unavailable["current_source_matches"] is None
