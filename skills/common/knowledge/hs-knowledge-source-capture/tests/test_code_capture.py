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
            "skill": "hs-workspace-explore",
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
        "source-capture",
        {
            "operation_id": "code-op",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
    )
    bundle = harness.record(result["data"]["bundle_ref"])
    snapshot = bundle["snapshots"][0]
    assert snapshot["sha256"] == hashlib.sha256(actual).hexdigest()
    assert (harness.root / snapshot["recovery"]["path"]).read_bytes() == actual
    assert snapshot["code_identity"]["checked_file_dirty"] is (True if git else None)
    assert bool(snapshot["code_identity"]["revision"]) is git
    assert bundle["resources"][0]["path"] == "sample.c"
    assert str(repo) not in canonical(bundle["resources"]).decode()
    assert (repo / "sample.c").read_bytes() == actual
    assert not (repo / "fsmonitor-executed.txt").exists()


def test_payload_context_cannot_authorize_a_different_code_root(harness):
    _, context_ref = setup_code(harness)
    context = harness.record(context_ref)
    context["repos"]["code"]["root"] = str(harness.base / "not-authorized")
    context.pop("digest")
    context["digest"] = hashlib.sha256(canonical(context)).hexdigest()
    harness.write(context_ref, canonical(context))
    result = harness.run(
        "source-capture",
        {
            "operation_id": "escape",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context_ref,
        },
        expected=3,
    )
    assert result["status"] == "blocked"
    assert not (harness.root / "logs/evidence").exists()


def test_code_selection_cannot_escape_authorized_repository(harness):
    _, context = setup_code(harness)
    result = harness.run(
        "source-capture",
        {
            "operation_id": "escape",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "../secret.txt",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
        expected=2,
    )
    assert result["diagnostics"][0]["code"] == "UNSAFE_PATH"


def test_code_resolver_replays_frozen_bytes_after_change_or_removed_authorization(
    harness,
):
    repo, context = setup_code(harness)
    original = (repo / "sample.c").read_bytes()
    captured = harness.run(
        "source-capture",
        {
            "operation_id": "historical-code",
            "kind": "code",
            "repo_id": "code",
            "relative_path": "sample.c",
            "source_id": "synthetic-code",
            "context_ref": context,
        },
    )
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
    resolved = harness.run("source-capture", request, "resolve-source")["data"]
    assert resolved["text"] == original.decode()
    assert resolved["source_kind"] == "code"
    assert resolved["resource"]["repo_id"] == "code"
    assert resolved["current_source_matches"] is False
    catalog = json.loads(harness.catalog.read_text())
    catalog.pop("code_policy")
    harness.catalog.write_bytes(canonical(catalog))
    request["operation_id"] = "resolve-without-root"
    historical = harness.run("source-capture", request, "resolve-source")["data"]
    assert historical["text"] == original.decode()
    assert historical["current_source_matches"] is None
    assert any("historical" in gap for gap in historical["limitations"])
