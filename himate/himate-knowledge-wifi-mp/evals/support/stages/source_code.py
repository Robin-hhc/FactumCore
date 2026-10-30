"""Registered actual-code capture; all repositories and receipts are synthetic."""

import hashlib
import json
import os
import subprocess

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
