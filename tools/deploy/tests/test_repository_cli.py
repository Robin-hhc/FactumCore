"""Repository runtime distribution and instruction-only Skill migration."""

from __future__ import annotations

import json
import shutil

import pytest
import yaml

from test_deploy import (
    DOMAIN, all_target_bytes, assert_no_targets, cli, invoke, put, tree,
    write_runtime, write_runtime_manifest,
)


def source_with_combined_record(source):
    """An eight-package synthetic release with record still inside source."""
    packages = source / "skills/common/knowledge"
    package = packages / "hs-knowledge-source"
    assert package.resolve().is_relative_to(source.resolve()) and package.is_dir()
    put(package, "SKILL.md", "---\nname: hs-knowledge-source\ndescription: fixture source and record\n---\n")
    contract = yaml.safe_load((package / "artifacts/result.yaml").read_bytes())
    contract.update(id="hs-knowledge-source-record-result", required=True,
                    applies_to={"node_ids": ["record_ingest"]}, required_on={"exit_ids": ["recorded"]})
    old = yaml.safe_dump(contract).encode()
    put(package, "artifacts/record-result.yaml", old)
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        path = source / "workflows/common/knowledge" / name / "workflow.yaml"
        workflow = yaml.safe_load(path.read_bytes())
        workflow["nodes"] = [{"id": "record_ingest", "type": "skill", "skill": "hs-knowledge-source"}]
        path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    return old


def split_record_package(source):
    packages = source / "skills/common/knowledge"
    source_package = packages / "hs-knowledge-source"
    record_package = packages / "hs-knowledge-record"
    declaration = (source_package / "artifacts/record-result.yaml").read_bytes()
    put(record_package, "SKILL.md", "---\nname: hs-knowledge-record\ndescription: fixture record\n---\nknowledge record\n")
    shutil.copytree(source_package / "references/results", record_package / "references/results")
    put(record_package, "artifacts/result.yaml", declaration)
    (source_package / "artifacts/record-result.yaml").unlink()
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        path = source / "workflows/common/knowledge" / name / "workflow.yaml"
        workflow = yaml.safe_load(path.read_bytes())
        workflow["nodes"][0]["skill"] = "hs-knowledge-record"
        path.write_text(yaml.safe_dump(workflow), encoding="utf-8")


def test_nine_instruction_packages_install_the_record_host_identity(source, targets):
    original = source_with_combined_record(source)
    split_record_package(source)
    code, result = cli(source, targets)
    assert (code, result["status"]) == (0, "deployed")
    assert len(result["packages"]["skills"]) == 9
    installed = targets["skills_root"] / "hs-knowledge-record"
    assert (installed / "artifacts/result.yaml").read_bytes() == original
    assert (installed / "artifacts/templates/result.md").read_bytes() == (installed / "references/results/templates/result.md").read_bytes()
    assert not (targets["skills_root"] / "hs-knowledge-source/artifacts/record-result.yaml").exists()


@pytest.mark.parametrize("fail", [False, True])
def test_eight_to_nine_package_upgrade_moves_record_resources_atomically(
    backend, monkeypatch, capsys, source, targets, fail,
):
    original = source_with_combined_record(source)
    assert cli(source, targets)[0] == 0
    knowledge = targets["project_root"] / DOMAIN
    business = {
        "logs/ingest/keep.yaml": b"synthetic established business record\n",
        "docs-raw/sources/dbox.local.yml": b"synthetic private source configuration\n",
    }
    for name, data in business.items():
        put(knowledge, name, data)
    before = all_target_bytes(targets)
    split_record_package(source)
    destination = targets["skills_root"] / "hs-knowledge-record/artifacts/result.yaml"
    if fail:
        real_write = backend._write_atomic

        def interrupted(path, data, *args):
            real_write(path, data, *args)
            if path == destination:
                raise OSError("Synthetic stop while moving the record declaration")

        monkeypatch.setattr(backend, "_write_atomic", interrupted)
    code, result = invoke(backend, capsys, source, targets)
    if fail:
        assert (code, result["status"], result["rolled_back"]) == (3, "failed", True)
        assert all_target_bytes(targets) == before
    else:
        assert (code, result["status"]) == (0, "deployed")
        assert len(result["packages"]["skills"]) == 9
        assert destination.read_bytes() == original
        assert not (targets["skills_root"] / "hs-knowledge-source/artifacts/record-result.yaml").exists()
        for name, data in business.items():
            assert (knowledge / name).read_bytes() == data
        for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
            installed = targets["workflows_root"] / name / "workflow.yaml"
            assert yaml.safe_load(installed.read_bytes())["nodes"][0]["skill"] == "hs-knowledge-record"
        repeated = cli(source, targets)
        assert repeated[0] == 0
        assert repeated[1]["write_count"] == repeated[1]["delete_count"] == repeated[1]["remove_directory_count"] == 0


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
