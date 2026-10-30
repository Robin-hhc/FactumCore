"""Repository runtime distribution and instruction-only Skill migration."""

from __future__ import annotations

import json

import pytest

from test_deploy import (
    DOMAIN, all_target_bytes, assert_no_targets, cli, invoke, put, tree,
    write_runtime, write_runtime_manifest,
)


def test_canonical_result_references_materialize_the_host_view(source, targets):
    package = source / "skills/common/knowledge/hs-knowledge-query"
    (package / "artifacts/templates/result.md").unlink(missing_ok=True)
    expected = b"# Canonical result\r\nSingle source.\r\n"
    put(package, "references/results/templates/result.md", expected)
    put(package, "references/results/writing.md", "# Write the actual result\n")
    put(package, "references/results/review.md", "# Review actual evidence\n")
    put(package, "artifacts/result.yaml", (
        "template: templates/result.md\nwriting_guide: writing.md\nreview_guide: review.md\n"
    ))
    code, result = cli(source, targets)
    assert (code, result["status"]) == (0, "deployed")
    installed = targets["skills_root"] / "hs-knowledge-query"
    assert (installed / "artifacts/templates/result.md").is_file()
    assert (installed / "artifacts/templates/result.md").read_bytes() == expected
    assert (installed / "references/results/templates/result.md").read_bytes() == expected
    assert not (package / "artifacts/templates/result.md").exists()


@pytest.mark.parametrize("problem", ["missing", "duplicate", "conflict", "binary", "escape", "absolute", "missing-field"])
def test_invalid_result_resource_cannot_write_targets(source, targets, problem):
    package = source / "skills/common/knowledge/hs-knowledge-query"
    canonical = package / "references/results/templates/result.md"
    if problem == "missing":
        canonical.unlink()
    elif problem in {"duplicate", "conflict"}:
        data = canonical.read_bytes() if problem == "duplicate" else b"conflicting legacy source\n"
        put(package, "artifacts/templates/result.md", data)
    elif problem == "binary":
        canonical.write_bytes(b"\xff\0binary result")
    else:
        import yaml

        path = package / "artifacts/result.yaml"
        value = yaml.safe_load(path.read_bytes())
        if problem == "missing-field":
            value.pop("template")
        else:
            value["template"] = "../outside.md" if problem == "escape" else str(canonical.absolute())
        path.write_text(yaml.safe_dump(value), encoding="utf-8")
    code, result = cli(source, targets)
    assert (code, result["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_shared_result_resources_and_updates_keep_host_declarations_unchanged(source, targets):
    package = source / "skills/common/knowledge/hs-knowledge-query"
    original = (package / "artifacts/result.yaml").read_bytes()
    put(package, "artifacts/another-result.yaml", original)
    before = tree(source / DOMAIN)
    assert cli(source, targets)[0] == 0
    expected = b"# Actual revised result\r\n"
    put(package, "references/results/templates/result.md", expected)
    assert cli(source, targets)[0] == 0
    installed = targets["skills_root"] / "hs-knowledge-query"
    assert (installed / "artifacts/templates/result.md").read_bytes() == expected
    assert (installed / "references/results/templates/result.md").read_bytes() == expected
    assert (installed / "artifacts/result.yaml").read_bytes() == original
    assert (installed / "artifacts/another-result.yaml").read_bytes() == original
    assert tree(source / DOMAIN) == before
    assert cli(source, targets)[1]["write_count"] == 0


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


@pytest.mark.parametrize("asset", ["references/request.md", "references/results/templates/result.md"])
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
