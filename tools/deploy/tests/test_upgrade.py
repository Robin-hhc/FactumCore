"""Exact framework upgrades preserve business state and restore failed changes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test_deploy import (
    DOMAIN, all_target_bytes, cli, invoke, put, tree, write_lock,
)

def snapshots(targets):
    return {
        "files": all_target_bytes(targets),
        "directories": {
            key: {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()}
            for key, root in targets.items()
        },
    }


def add_template(source, name="hs-knowledge-temporary"):
    root = source / "workflows/common/knowledge" / name
    put(root, "workflow.yaml", f"version: 1\nid: {name}\nnodes: []\n")
    put(root, "layouts.yaml", "version: 1\npositions: {}\n")
    put(root, "README.md", "# Temporary deployed workflow\n")
    return root


def remove_fixture_tree(path, source):
    assert path.resolve().is_relative_to(source.resolve())
    shutil.rmtree(path)


@pytest.mark.parametrize("fail", [False, True])
def test_file_directory_layout_changes_and_failure_restore_original_shapes(
    backend, monkeypatch, capsys, source, targets, fail
):
    package = source / "skills/common/knowledge/hs-knowledge-query"
    put(package, "scripts/becomes-dir", b"old file")
    put(package, "scripts/becomes-file/old.txt", b"old nested file")
    assert cli(source, targets)[0] == 0
    target = targets["skills_root"] / package.name
    (target / "scripts/becomes-file/empty/child").mkdir(parents=True)
    before = snapshots(targets)
    (package / "scripts/becomes-dir").unlink()
    put(package, "scripts/becomes-dir/new.txt", b"new nested file")
    (package / "scripts/becomes-file/old.txt").unlink()
    (package / "scripts/becomes-file").rmdir()
    put(package, "scripts/becomes-file", b"new file")
    if fail:
        real_write = backend._write_atomic
        injected = False

        def interrupted(path, data, *args):
            nonlocal injected
            real_write(path, data, *args)
            if path == target / "scripts/becomes-file" and not injected:
                injected = True
                raise OSError("Synthetic failure after both layout conversions")

        monkeypatch.setattr(backend, "_write_atomic", interrupted)
    code, report = invoke(backend, capsys, source, targets)
    if fail:
        assert injected
        assert (code, report["status"], report["rolled_back"]) == (3, "failed", True)
        assert snapshots(targets) == before
    else:
        assert (code, report["status"]) == (0, "deployed")
        assert (target / "scripts/becomes-dir/new.txt").read_bytes() == b"new nested file"
        assert (target / "scripts/becomes-file").read_bytes() == b"new file"
        assert cli(source, targets)[1]["write_count"] == 0


def test_second_receipt_failure_restores_both_receipts_and_retired_packages(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    before = snapshots(targets)
    remove_fixture_tree(source / "skills/common/knowledge/hs-knowledge-new-0", source)
    add_template(source)
    last_receipt = targets["workflows_root"] / ".factum-knowledge-deploy.json"
    first_receipt = targets["skills_root"] / ".factum-knowledge-deploy.json"
    real_replace = backend.os.replace
    injected = False

    def interrupted(source_path, target_path):
        nonlocal injected
        real_replace(source_path, target_path)
        if Path(target_path) == last_receipt and not injected:
            injected = True
            assert first_receipt.read_bytes() != before["files"]["skills_root"][first_receipt.name]
            raise OSError("Synthetic failure after second receipt replacement")

    monkeypatch.setattr(backend.os, "replace", interrupted)
    code, report = invoke(backend, capsys, source, targets)
    assert injected
    assert (code, report["status"], report["rolled_back"]) == (3, "failed", True)
    assert snapshots(targets) == before


def test_upgrade_mirrors_owned_packages_and_repeat_has_no_changes(source, targets):
    retired_source = add_template(source)
    assert cli(source, targets)[0] == 0
    remove_fixture_tree(retired_source, source)
    skills, workflows = targets["skills_root"], targets["workflows_root"]
    # Workflow ownership must survive removal of both source and target markers.
    (workflows / "hs-knowledge-temporary/workflow.yaml").unlink()
    stale_files = [
        put(skills, "hs-knowledge-query/local-helper.txt", b"old helper"),
        put(skills, "hs-knowledge-source-scan/scripts/old.py", b"known retired skill without marker"),
        put(workflows, "hs-knowledge-ingest/old-prompts/prompt.md", b"old prompt"),
        workflows / "hs-knowledge-temporary/README.md",
        workflows / "hs-knowledge-temporary/layouts.yaml",
    ]
    stale_directories = [
        skills / "hs-knowledge-query/empty/child",
        skills / "hs-knowledge-source-prepare/nested",
        workflows / "hs-knowledge-ingest/unused/child",
        workflows / "hs-knowledge-temporary/empty/nested",
    ]
    for path in stale_directories:
        path.mkdir(parents=True)
    unrelated = []
    for root in (skills, workflows):
        for name in ("other-package", "hs-knowledge-custom", "hs-codegraph-setup", "hs-workspace-explore"):
            unrelated.append(put(root, name + "/private.bin", name.encode()))
            marker = "SKILL.md" if root == skills else "workflow.yaml"
            unrelated.append(put(root, name + "/" + marker, b"other owner's package marker"))
            (root / name / "empty/child").mkdir(parents=True)
        (root / "other-empty/child").mkdir(parents=True)
    unrelated_bytes = {path: path.read_bytes() for path in unrelated}

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert all(not path.exists() for path in stale_files + stale_directories)
    assert not (skills / "hs-knowledge-source-scan").exists()
    assert not (skills / "hs-knowledge-source-prepare").exists()
    assert not (workflows / "hs-knowledge-temporary").exists()
    for root in (skills, workflows):
        assert (root / "other-empty/child").is_dir()
        for name in ("other-package", "hs-knowledge-custom", "hs-codegraph-setup", "hs-workspace-explore"):
            assert (root / name / "empty/child").is_dir()
    assert all(path.read_bytes() == original for path, original in unrelated_bytes.items())
    assert {str(path) for path in stale_files} <= {
        row["path"] for row in report["files"] if row["action"] == "delete"
    }
    assert report["delete_count"] == len(stale_files)
    assert report["remove_directory_count"] >= len(stale_directories)
    assert {str(path) for path in stale_directories} <= {
        row["path"] for row in report["directories"] if row["action"] == "remove"
    }

    code, repeated = cli(source, targets)
    assert (code, repeated["status"]) == (0, "deployed")
    assert (repeated["write_count"], repeated["delete_count"], repeated["remove_directory_count"]) == (0, 0, 0)


def test_all_fixed_legacy_packages_are_removed_without_markers(source, targets):
    assert cli(source, targets)[0] == 0
    retired = (
        "source-scan", "source-prepare", "candidate-inspect", "candidate-revise",
        "governance-handoff", "index-build", "local-check", "merge-check", "publish-handoff",
        "query-regression", "recover", "source-capture", "confirmation-prepare", "confirmation-record",
    )
    packages = [targets["skills_root"] / ("hs-knowledge-" + name) for name in retired]
    for package in packages:
        put(package, "old.txt", b"old package with its marker already removed")
        (package / "empty/deep").mkdir(parents=True)

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert all(not package.exists() for package in packages)
    assert report["delete_count"] == len(retired)


@pytest.mark.parametrize("kind", ["skill", "workflow"])
def test_removed_source_package_is_removed_from_its_previous_receipt(source, targets, kind):
    if kind == "skill":
        relative, target = "skills/common/knowledge/hs-knowledge-new-0", targets["skills_root"] / "hs-knowledge-new-0"
    else:
        relative, target = "workflows/common/knowledge/hs-knowledge-temporary", targets["workflows_root"] / "hs-knowledge-temporary"
        add_template(source)
    assert cli(source, targets)[0] == 0
    assert target.is_dir()
    remove_fixture_tree(source / relative, source)

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert not target.exists()
    assert any(Path(row["path"]).is_relative_to(target) and row["action"] == "delete" for row in report["files"])
    assert any(Path(row["path"]) == target and row["action"] == "remove" for row in report["directories"])


def test_removed_skill_source_file_and_subtree_do_not_survive_upgrade(source, targets):
    package = source / "skills/common/knowledge/hs-knowledge-query"
    put(package, "scripts/legacy/deep/tool.py", b"old distributed tool")
    assert cli(source, targets)[0] == 0
    (package / "references/request.md").unlink()
    remove_fixture_tree(package / "scripts/legacy", source)
    destination = targets["skills_root"] / package.name

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert not (destination / "references/request.md").exists()
    assert not (destination / "scripts/legacy").exists()
    assert (destination / "scripts/cli.py").read_bytes() == b"print('synthetic')\n"
    assert report["delete_count"] == 2


def test_framework_removed_files_and_empty_directories_follow_the_new_lock(source, targets):
    knowledge = source / DOMAIN
    removed = [
        "governance/contracts/legacy/old.py", "governance/schemas/legacy/old.json",
        "governance/specs/legacy/old.md", "governance/templates/legacy/old.md",
    ]
    for relative in removed:
        put(knowledge, relative, b"old framework bytes")
    entries = {
        relative: {"path": relative, "sha256": hashlib.sha256((knowledge / relative).read_bytes()).hexdigest()}
        for relative in ["governance/contracts/example.py", "governance/schemas/example.schema.json", *removed]
    }
    write_lock(source, entries)
    assert cli(source, targets)[0] == 0
    target = targets["project_root"] / DOMAIN
    for relative in removed:
        remove_fixture_tree((knowledge / relative).parent, source)
    write_lock(source)
    for folder in ("contracts", "schemas", "specs", "templates"):
        (target / "governance" / folder / "empty/deep").mkdir(parents=True)
    put(target, "governance/local-runtime.json", b"preserve outside framework subtrees")

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert all(not (target / relative).exists() for relative in removed)
    assert all(not (target / "governance" / folder / "empty").exists() for folder in ("contracts", "schemas", "specs", "templates"))
    assert (target / "governance/framework.lock.yaml").read_bytes() == (knowledge / "governance/framework.lock.yaml").read_bytes()
    assert (target / "governance/contracts/example.py").read_bytes() == b"VALUE = 'locked'\n"
    assert (target / "governance/local-runtime.json").read_bytes() == b"preserve outside framework subtrees"
    assert report["delete_count"] == len(removed)


def test_upgrade_preserves_all_business_files_and_empty_directories(source, targets, tmp_path):
    project = targets["project_root"]
    put(project, "config.yml", b"# Existing mapping\nknowledge_roots: {wifi: live/wifi}\nmodules: []\n")
    knowledge = project / "live/wifi"
    external = tmp_path / "external-dbox"
    originals = {
        "AGENTS.md": b"# Existing business project\r\n",
        "code/device.c": b"int business_code;\n",
    }
    protected = [
        "governance/sources.lock.yaml", "governance/local-runtime.json", "index.md",
        ".gitignore", ".gitattributes", "docs-raw/AGENTS.md", "docs-raw/index.md",
        "docs-raw/specs/customer.bin", "docs-raw/sources/dbox.local.yml", "docs-raw/sources/user-extra.yml",
        "knowledge/AGENTS.md", "knowledge/index.md", "knowledge/rules/index.md", "knowledge/rules/card.md",
        "logs/ingest/record.yaml", "logs/events/state.json", "logs/events/event.json",
        "logs/publications/op/manifest.json", "logs/publications/op/completion.json",
        "logs/evidence/published/objects/source.bin", "logs/evidence/published/cards/old.md",
        "logs/evidence/published/extractions/source.txt", "logs/evidence/published/locators/source.json",
        "logs/evidence/objects/old.bin", "logs/evidence/checked-code/old.c", "logs/evidence/runtime-support.log",
        "logs/evidence/extractions/old.txt", "logs/evidence/locators/old.json",
        "logs/operations/op/journal.json", "logs/patrol/op/plan.json",
        ".build/operations/op/transaction/journal.json", ".build/operations/op/transaction/backups/old.bin",
        ".build/runtime/writer.lock", ".build/runtime/patrol-state.json", ".build/project-context/context.json",
        "artifacts/indexes/local/active.json", "artifacts/indexes/local/generation/index.db",
        "artifacts/indexes/local/generation/manifest.json", "artifacts/receipts/query.json",
        "docs-llm-wiki/task.md", "docs-llm-wiki/sdd/history.md", "docs-llm-wiki/local-notes.md",
    ]
    for index, relative in enumerate(protected):
        originals["live/wifi/" + relative] = f"preserved-{index}\r\n".encode()
    originals["live/wifi/docs-raw/sources/dbox.local.yml"] = f"schema_version: '1.0'\npath: '{external}'\n".encode()
    originals["live/wifi/docs-raw/sources/.gitignore"] = b"# Team patterns\r\n*.cache\r\n/dbox.local.yml\r\n"
    for relative, data in originals.items():
        put(project, relative, data)
    config = (project / "config.yml").read_bytes()
    empty = [
        "docs-raw/specs/empty/nested", "docs-raw/sources/dbox/empty", "knowledge/rules/empty",
        "logs/evidence/published/empty", "logs/events/empty", "logs/operations/empty", "logs/patrol/empty",
        ".build/operations/empty/nested", ".build/runtime/empty", "artifacts/indexes/empty",
        "governance/custom-data/empty", "docs-llm-wiki/sdd/empty",
    ]
    for relative in empty:
        (knowledge / relative).mkdir(parents=True)
    put(external, "source.bin", b"external original")
    (external / "empty").mkdir()
    assert cli(source, targets)[0] == 0
    put(targets["skills_root"], "hs-knowledge-query/obsolete.txt", b"remove framework only")
    put(knowledge, "governance/contracts/obsolete.py", b"remove framework only")

    code, report = cli(source, targets)

    assert (code, report["status"]) == (0, "deployed")
    assert not (targets["skills_root"] / "hs-knowledge-query/obsolete.txt").exists()
    assert not (knowledge / "governance/contracts/obsolete.py").exists()
    assert (project / "config.yml").read_bytes() == config
    assert all((project / relative).read_bytes() == data for relative, data in originals.items())
    assert all((knowledge / relative).is_dir() for relative in empty)
    assert tree(external) == {"source.bin": b"external original"}
    assert (external / "empty").is_dir()


def test_upgrade_plan_reports_file_and_directory_deletes_without_mutating_targets(source, targets):
    assert cli(source, targets)[0] == 0
    stale = put(targets["skills_root"], "hs-knowledge-source-scan/old.py", b"known retired package")
    empty = targets["skills_root"] / "hs-knowledge-query/old/empty"
    empty.mkdir(parents=True)
    before = snapshots(targets)

    code, report = cli(source, targets, "--plan")

    assert (code, report["status"]) == (0, "planned")
    assert snapshots(targets) == before
    assert report["delete_count"] == 1
    assert report["remove_directory_count"] >= 2
    assert any(row["path"] == str(stale) and row["action"] == "delete" for row in report["files"])
    assert any(row["path"] == str(empty) and row["action"] == "remove" for row in report["directories"])


@pytest.mark.parametrize("kind", ["skills_root", "workflows_root"])
@pytest.mark.parametrize("corruption", ["json", "owner", "kind", "packages", "escape", "schema"])
@pytest.mark.parametrize("plan", [False, True])
def test_invalid_ownership_receipt_fails_closed_without_writing(source, targets, kind, corruption, plan):
    assert cli(source, targets)[0] == 0
    receipt = targets[kind] / ".factum-knowledge-deploy.json"
    value = json.loads(receipt.read_bytes())
    if corruption == "json":
        receipt.write_bytes(b"{invalid receipt")
    else:
        if corruption == "owner":
            value["owner"] = "another-project"
        elif corruption == "kind":
            value["kind"] = "another-kind"
        elif corruption == "packages":
            value["packages"] = "not-a-package-list"
        elif corruption == "escape":
            value["packages"] = ["../outside"]
        else:
            key = "schema_version" if "schema_version" in value else "schema"
            value[key] = "unsupported-schema"
        receipt.write_text(json.dumps(value), encoding="utf-8")
    put(targets["skills_root"], "hs-knowledge-query/keep-on-invalid-receipt.txt", b"do not prune on invalid receipt")
    before = snapshots(targets)

    code, report = cli(source, targets, *("--plan",) if plan else ())

    assert (code, report["status"]) == (3, "failed")
    assert snapshots(targets) == before


@pytest.mark.skipif(os.name != "nt", reason="Windows junction pruning safety")
@pytest.mark.parametrize("scope", ["active-skill", "retired-skill", "framework"])
def test_junction_inside_pruning_scope_is_rejected_before_any_change(source, targets, tmp_path, scope):
    assert cli(source, targets)[0] == 0
    external = tmp_path / "outside"
    put(external, "original.bin", b"outside scope")
    if scope == "framework":
        link = targets["project_root"] / DOMAIN / "governance/contracts/obsolete"
    else:
        package = "hs-knowledge-query" if scope == "active-skill" else "hs-knowledge-source-scan"
        link = targets["skills_root"] / package / "obsolete"
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(external)], capture_output=True, check=False)
    if result.returncode:
        pytest.skip("Windows junction creation unavailable")
    installed = targets["skills_root"] / "hs-knowledge-explore/SKILL.md"
    original = installed.read_bytes()
    put(source, "skills/common/knowledge/hs-knowledge-explore/SKILL.md", original + b"new pending version\n")
    try:
        code, report = cli(source, targets)
        assert (code, report["status"]) == (3, "failed")
        assert installed.read_bytes() == original
        assert (external / "original.bin").read_bytes() == b"outside scope"
        assert link.is_dir()
    finally:
        if os.path.lexists(link):
            os.rmdir(link)


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_second_file_delete_failure_restores_first_removed_file_and_all_directories(
    backend, monkeypatch, capsys, source, targets, failure
):
    assert cli(source, targets)[0] == 0
    removed = {
        put(targets["skills_root"], "hs-knowledge-query/obsolete/a.txt", b"first original"),
        put(targets["skills_root"], "hs-knowledge-query/obsolete/z.txt", b"second original"),
    }
    (targets["skills_root"] / "hs-knowledge-query/obsolete/empty/deep").mkdir(parents=True)
    before = snapshots(targets)
    real_unlink, attempts = Path.unlink, []

    def interrupted(path, *args, **kwargs):
        if path in removed:
            attempts.append(path)
            if len(attempts) == 2:
                raise failure("Synthetic failure deleting the second obsolete file")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted)
    code, report = invoke(backend, capsys, source, targets)

    assert (code, report["status"]) == (3, "failed")
    assert len(attempts) >= 2
    assert report["rolled_back"] is True
    assert snapshots(targets) == before


def test_directory_removal_failure_restores_the_original_tree(backend, monkeypatch, capsys, source, targets):
    assert cli(source, targets)[0] == 0
    put(targets["skills_root"], "hs-knowledge-query/obsolete/a.txt", b"original file")
    selected = targets["skills_root"] / "hs-knowledge-query/obsolete/empty/deep"
    selected.mkdir(parents=True)
    before = snapshots(targets)
    real_rmdir, failed = Path.rmdir, False

    def interrupted(path, *args, **kwargs):
        nonlocal failed
        if path == selected and not failed:
            failed = True
            raise OSError("Synthetic obsolete-directory removal failure")
        return real_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rmdir", interrupted)
    code, report = invoke(backend, capsys, source, targets)

    assert (code, report["status"]) == (3, "failed")
    assert failed
    assert report["rolled_back"] is True
    assert snapshots(targets) == before


def test_later_write_failure_restores_deleted_files_empty_directories_and_receipts(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    removed = [
        put(targets["skills_root"], "hs-knowledge-query/obsolete/a.txt", b"deleted original"),
        targets["skills_root"] / "hs-knowledge-query/obsolete/empty/deep",
        targets["skills_root"] / "hs-knowledge-new-0",
    ]
    removed[1].mkdir(parents=True)
    # The failed upgrade would also change package ownership; its receipt must stay old.
    (source / "skills/common/knowledge/hs-knowledge-new-0/SKILL.md").unlink()
    selected = targets["skills_root"] / "hs-knowledge-query/scripts/cli.py"
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"print('new version')\n")
    before = snapshots(targets)
    real_replace, failed, deletion_observed = backend.os.replace, False, False

    def interrupted(source_path, target_path, *args, **kwargs):
        nonlocal failed, deletion_observed
        if Path(target_path) == selected and not failed:
            failed = True
            deletion_observed = all(not path.exists() for path in removed)
            real_replace(source_path, target_path, *args, **kwargs)
            raise OSError("Synthetic interruption after later real replacement")
        return real_replace(source_path, target_path, *args, **kwargs)

    monkeypatch.setattr(backend.os, "replace", interrupted)
    code, report = invoke(backend, capsys, source, targets)

    assert (code, report["status"]) == (3, "failed")
    assert failed and deletion_observed
    assert report["rolled_back"] is True
    assert snapshots(targets) == before
