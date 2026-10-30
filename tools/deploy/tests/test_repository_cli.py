"""Repository runtime distribution and instruction-only Skill migration."""

from __future__ import annotations

import json

import pytest

from test_deploy import (
    DOMAIN, all_target_bytes, assert_no_targets, cli, invoke, put, tree,
    write_runtime, write_runtime_manifest,
)


def test_repository_cli_and_runtime_are_distributed_but_skill_scripts_are_not(source, targets):
    files = write_runtime(source)
    put(source / DOMAIN, "runtime/__pycache__/private.pyc", b"do not distribute")
    put(source / DOMAIN, "runtime/.env", b"DO_NOT_SHIP")
    put(source, "skills/common/knowledge/hs-knowledge-query/references/helper.py", b"do not execute")
    code, result = cli(source, targets)
    assert (code, result["status"]) == (0, "deployed")
    installed = tree(targets["project_root"] / DOMAIN)
    for name, data in files.items():
        assert installed[name] == data
    assert "runtime/manifest.json" in installed
    assert "runtime/.env" not in installed
    assert "runtime/__pycache__/private.pyc" not in installed
    for name in result["packages"]["skills"]:
        package = tree(targets["skills_root"] / name)
        assert "SKILL.md" in package
        assert not any(p.startswith("scripts/") or p.startswith("requirements") for p in package)
        assert "references/helper.py" not in package


@pytest.mark.parametrize("problem", ["missing", "changed", "escape", "duplicate"])
def test_runtime_manifest_errors_block_before_any_target_write(source, targets, problem):
    write_runtime(source)
    root = source / DOMAIN
    manifest_path = root / "runtime/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if problem == "missing":
        (root / "runtime/himate_knowledge/cli.py").unlink()
    elif problem == "changed":
        put(root, "runtime/himate_knowledge/cli.py", b"changed after lock\n")
    elif problem == "escape":
        manifest["files"]["../outside.py"] = {"sha256": "0" * 64}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        manifest_path.write_text('{"schema_version":"1.0","version":"0.0.1","files":{},"files":{}}', encoding="utf-8")
    code, result = cli(source, targets)
    assert (code, result["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_runtime_lock_replaces_obsolete_skill_dependency_lock(source, targets):
    write_runtime(source)
    for package in (source / "skills/common/knowledge").iterdir():
        for path in package.glob("requirements*.txt"):
            path.unlink()
    code, result = cli(source, targets)
    assert (code, result["status"]) == (0, "deployed")
    assert result["environment"]["status"] == "ready"


@pytest.mark.parametrize("asset", ["references/request.md", "artifacts/templates/result.md"])
def test_nontext_instruction_resources_cannot_be_distributed(source, targets, asset):
    put(source / "skills/common/knowledge/hs-knowledge-query", asset, b"\xff\x00binary resource")
    code, result = cli(source, targets)
    assert (code, result["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_distribution_without_runtime_manifest_cannot_claim_repository_cli_readiness(source, targets):
    (source / DOMAIN / "runtime/manifest.json").unlink()
    code, result = cli(source, targets)
    assert (code, result["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_unverified_runtime_cannot_install_dependencies_before_manifest_checks(
    backend, monkeypatch, capsys, source, targets,
):
    import subprocess

    put(source / DOMAIN, "runtime/himate_knowledge/cli.py", b"not the pinned runtime\n")
    monkeypatch.setattr(backend.importlib.metadata, "version", lambda name: "0.synthetic")
    commands = []

    def forbidden(command, **kwargs):
        commands.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backend.subprocess, "run", forbidden)
    code, result = invoke(backend, capsys, source, targets, "--install-dependencies")
    assert (code, result["status"]) == (3, "failed")
    assert commands == []
    assert_no_targets(targets)


@pytest.mark.parametrize("fail", [False, True])
def test_repository_runtime_upgrade_prunes_stale_code_and_rolls_back_exact_bytes(
    backend, monkeypatch, capsys, source, targets, fail,
):
    source_root = source / DOMAIN
    put(source_root, "runtime/himate_knowledge/retired.py", b"old runtime module\n")
    write_runtime_manifest(source)
    assert cli(source, targets)[0] == 0
    installed_root = targets["project_root"] / DOMAIN
    put(installed_root, "docs-raw/sources/dbox.local.yml", b"path: /personal/local\n")
    put(targets["skills_root"], "hs-knowledge-query/scripts/cli.py", b"old installed skill\n")
    before = all_target_bytes(targets)
    (source_root / "runtime/himate_knowledge/retired.py").unlink()
    put(source_root, "runtime/himate_knowledge/cli.py", b"new repository runtime\n")
    write_runtime_manifest(source)
    selected = installed_root / "runtime/himate_knowledge/cli.py"
    if fail:
        real_write = backend._write_atomic
        injected = False

        def interrupted(path, data, *args):
            nonlocal injected
            real_write(path, data, *args)
            if path == selected and not injected:
                injected = True
                raise OSError("Synthetic failure after repository runtime update")

        monkeypatch.setattr(backend, "_write_atomic", interrupted)
    code, result = invoke(backend, capsys, source, targets)
    if fail:
        assert injected
        assert (code, result["status"], result["rolled_back"]) == (3, "failed", True)
        assert all_target_bytes(targets) == before
    else:
        assert (code, result["status"]) == (0, "deployed")
        assert not (installed_root / "runtime/himate_knowledge/retired.py").exists()
        assert not (targets["skills_root"] / "hs-knowledge-query/scripts").exists()
        assert selected.read_bytes() == b"new repository runtime\n"
        assert (installed_root / "docs-raw/sources/dbox.local.yml").read_bytes() == b"path: /personal/local\n"
        assert cli(source, targets)[1]["write_count"] == 0
