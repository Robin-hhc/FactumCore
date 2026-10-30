"""Deployment behavior against isolated synthetic sources and destinations.

No test reads business inputs, connects to SSH, or installs real packages.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "tools" / "deploy" / "deploy.py"
DOMAIN = "himate-knowledge-wifi-mp"


def put(root: Path, name: str, data: str | bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    return path


def tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def write_lock(source: Path, entries: dict | None = None) -> None:
    governance = source / DOMAIN / "governance"
    if entries is None:
        entries = {}
        for relative in ("governance/contracts/example.py", "governance/schemas/example.schema.json"):
            entries[relative.removeprefix("governance/")] = {
                "path": relative,
                "sha256": hashlib.sha256((source / DOMAIN / relative).read_bytes()).hexdigest(),
            }
    put(
        governance,
        "framework.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "contract_family": "synthetic-deployment",
                "tool_version": "0.0.1",
                "files": entries,
            },
            sort_keys=False,
        ),
    )


def make_source(root: Path, skill_count: int = 8) -> Path:
    """Use deliberately unfamiliar names to exercise active-package discovery."""
    root.mkdir()
    put(root, "AGENTS.md.example", "# Business project entry\n")
    put(
        root,
        "config.yml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "workspace_id": "synthetic",
                "knowledge_roots": {"wifi": DOMAIN},
                "code_root": "main",
                "modules": [],
            },
            sort_keys=False,
        ),
    )
    pins = "PyYAML==" + importlib.metadata.version("PyYAML") + "\n"
    names = ["hs-knowledge-explore", "hs-knowledge-query"] + [
        "hs-knowledge-new-" + str(i) for i in range(skill_count - 2)
    ]
    for name in names:
        package = root / "skills/common/knowledge" / name
        put(package, "SKILL.md", f"---\nname: {name}\n---\nSynthetic skill.\n")
        put(package, "scripts/cli.py", "print('synthetic')\n")
        put(package, "references/request.md", "Synthetic request.\n")
        put(package, "artifacts/result.yaml", "version: 1\n")
        put(package, "artifacts/templates/result.md", "# Synthetic result\n")
        put(package, "requirements.lock.txt", pins)
        put(package, "requirements-dev.lock.txt", "# Kept as a distributed file\n")
        put(package, "tests/private.txt", b"do not distribute tests")
        put(package, "config.env", b"DO_NOT_SHIP=synthetic")
        put(package, ".env", b"DO_NOT_SHIP=synthetic-dotenv")
        put(package, "scripts/settings.env", b"DO_NOT_SHIP=nested-env")
        put(package, "artifacts/credentials/token.txt", b"DO_NOT_SHIP=nested-credentials")
        put(package, "scripts/__pycache__/cli.pyc", b"do not distribute cache")
    put(root, "skills/common/knowledge/hs-knowledge-retired/scripts/old.py", "obsolete\n")
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        package = root / "workflows/common/knowledge" / name
        put(
            package,
            "workflow.yaml",
            f"version: 1\nid: {name}\nnodes: []\n",
        )
        put(package, "layouts.yaml", "version: 1\npositions: {}\n")
        put(package, "README.md", f"# {name}\nSynthetic workflow.\n")
    knowledge = root / DOMAIN
    for name in ("AGENTS.md", "README.md", "CONTRIBUTING.md", "check.py", "check.sh"):
        put(knowledge, name, f"Shared synthetic {name}\n")
    for name in (
        "AGENTS.md",
        "README.md",
        "使用说明.md",
        "HiMate知识库架构设计.md",
        "知识库详细设计.md",
        "知识库关键点.md",
    ):
        put(knowledge / "docs-llm-wiki", name, f"# Shared synthetic {name}\n")
    put(knowledge, "governance/AGENTS.md", "# Synthetic governance\n")
    put(knowledge, "governance/contracts/example.py", "VALUE = 'locked'\n")
    put(knowledge, "governance/schemas/example.schema.json", '{"type":"object"}\n')
    put(knowledge, "governance/sources.lock.yaml", "sources: [private-source]\n")
    put(knowledge, "governance/local-runtime.json", b"synthetic business data: local governance state")
    put(knowledge, "docs-raw/AGENTS.md", "# Raw input rules\n")
    put(knowledge, "docs-raw/sources/dbox.example.yml", "schema_version: '1.0'\npath: ''\n")
    put(knowledge, "docs-raw/sources/.gitignore", "/dbox.local.yml\n")
    put(knowledge, "docs-raw/sources/dbox.local.yml", "path: /PRIVATE_DBOX_DO_NOT_SHIP\n")
    put(knowledge, "docs-raw/sources/unregistered-source.txt", "PRIVATE_DBOX_DO_NOT_SHIP\n")
    put(knowledge, "knowledge/AGENTS.md", "# Card rules\n")
    for name in (
        "docs-raw/specs/private.md",
        "knowledge/entity/private-card.md",
        "knowledge/indexes/private-nav.md",
        "logs/ingest/private.json",
        "logs/evidence/published/private-source.bin",
        "docs-llm-wiki/task.md",
        "docs-llm-wiki/sdd/private.md",
        ".build/private.json",
        "artifacts/private.json",
        "evals/gold/private.txt",
    ):
        put(knowledge, name, b"synthetic business data: must never be shipped")
    write_lock(root)
    return root


@pytest.fixture
def source(tmp_path):
    return make_source(tmp_path / "source")


@pytest.fixture
def targets(tmp_path):
    return {
        "skills_root": tmp_path / "output-skills",
        "workflows_root": tmp_path / "output-workflows",
        "project_root": tmp_path / "output-project",
    }


@pytest.fixture
def backend(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("factum_deploy_tests", BACKEND)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))
    return module


def argv(source: Path, targets: dict, *extra: str) -> list[str]:
    result = ["--source-root", str(source)]
    for key, value in targets.items():
        result += ["--" + key.replace("_", "-"), str(value)]
    return result + list(extra)


def cli(source: Path, targets: dict, *extra: str, timeout=30):
    completed = subprocess.run(
        [sys.executable, str(BACKEND), *argv(source, targets, *extra)],
        check=False,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env={**os.environ, "TMP": str(source.parent), "TEMP": str(source.parent)},
        timeout=timeout,
    )
    try:
        report = json.loads(completed.stdout)
    except ValueError as exc:
        raise AssertionError(
            f"Non-JSON CLI output (exit {completed.returncode}): "
            f"{completed.stdout!r}; stderr={completed.stderr!r}"
        ) from exc
    return completed.returncode, report


def invoke(backend, capsys, source: Path, targets: dict, *extra: str):
    result = backend.main(argv(source, targets, *extra))
    captured = capsys.readouterr()
    return result, json.loads(captured.out)


def all_target_bytes(targets: dict) -> dict:
    return {key: tree(path) for key, path in targets.items()}


def assert_no_targets(targets: dict) -> None:
    assert all(not path.exists() for path in targets.values())


def test_plan_is_read_only_and_reports_selected_targets(source, targets):
    before = tree(source)
    code, report = cli(source, targets, "--plan")
    assert (code, report["status"]) == (0, "planned")
    assert_no_targets(targets)
    assert tree(source) == before
    serialized = json.dumps(report).replace("\\\\", "\\")
    assert all(str(value) in serialized for value in targets.values())


def test_dbox_template_is_distributed_without_local_mapping_or_source_tree(source, targets):
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    knowledge = targets["project_root"] / DOMAIN
    assert (knowledge / "docs-raw/sources/dbox.example.yml").read_bytes() == (
        source / DOMAIN / "docs-raw/sources/dbox.example.yml"
    ).read_bytes()
    assert (knowledge / "docs-raw/sources/.gitignore").read_bytes() == b"/dbox.local.yml\n"
    assert not (knowledge / "docs-raw/sources/dbox.local.yml").exists()
    assert not (knowledge / "docs-raw/sources/unregistered-source.txt").exists()
    assert all(b"PRIVATE_DBOX_DO_NOT_SHIP" not in value for value in tree(knowledge).values())
    assert report["source_setup"] == {
        "status": "pending_execution_host", "source": "dbox", "action": "configure",
        "config_ref": "docs-raw/sources/dbox.local.yml", "configuration_checked": False,
    }
    assert report["remote_checked"] is False


@pytest.mark.parametrize("template", [
    "schema_version: '1.0'\npath: /PRIVATE_PATH\n",
    "schema_version: 1.0\npath: ''\n",
    "schema_version: '1.0'\npath: ''\npath: /PRIVATE_PATH\n",
])
def test_dbox_template_with_private_or_ambiguous_mapping_cannot_be_distributed(source, targets, template):
    put(source / DOMAIN, "docs-raw/sources/dbox.example.yml", template)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_dbox_nested_knowledge_preserves_private_config_and_appends_ignore_once(source, targets):
    project = targets["project_root"]
    relative = "nested/domain"
    original_config = b"knowledge_roots: {wifi: nested/domain}\nmodules: []\n"
    put(project, "config.yml", original_config)
    knowledge = project / relative
    private = b"# Personal server path\r\nschema_version: '1.0'\r\npath: /server/private/dbox\r\n"
    put(knowledge, "docs-raw/sources/dbox.local.yml", private)
    custom_ignore = b"# Existing team rules\r\n*.cache\r\n!/dbox.local.yml"
    ignore = put(knowledge, "docs-raw/sources/.gitignore", custom_ignore)
    for _ in range(2):
        code, report = cli(source, targets)
        assert (code, report["status"]) == (0, "deployed")
        assert (knowledge / "docs-raw/sources/dbox.local.yml").read_bytes() == private
        assert ignore.read_bytes() == custom_ignore + b"\r\n/dbox.local.yml\r\n"
        assert (project / "config.yml").read_bytes() == original_config
        assert report["source_setup"]["configuration_checked"] is False
    assert (knowledge / "docs-raw/sources/dbox.example.yml").is_file()


def test_dbox_plan_proposes_ignore_update_without_writing_local_state(source, targets):
    knowledge = targets["project_root"] / DOMAIN
    ignore = put(knowledge, "docs-raw/sources/.gitignore", b"# Existing\n*.tmp\n")
    private = put(knowledge, "docs-raw/sources/dbox.local.yml", b"path: /private/root\n")
    before = all_target_bytes(targets)
    code, report = cli(source, targets, "--plan")
    assert (code, report["status"]) == (0, "planned")
    assert all_target_bytes(targets) == before
    assert any(row["path"] == str(ignore) and row["action"] == "write" for row in report["files"])
    assert all(row["path"] != str(private) for row in report["files"])
    assert report["source_setup"]["status"] == "pending_execution_host"


def test_dbox_concurrent_ignore_edit_is_preserved_before_deployment(
    backend, monkeypatch, capsys, source, targets
):
    knowledge = targets["project_root"] / DOMAIN
    ignore = put(knowledge, "docs-raw/sources/.gitignore", b"# Original\n")
    concurrent = b"# Concurrent team edit\n*.temporary\n"
    original_archive = backend._archive
    changed = False

    def edit_while_packaging(payload):
        nonlocal changed
        result = original_archive(payload)
        if not changed:
            changed = True
            ignore.write_bytes(concurrent)
        return result

    monkeypatch.setattr(backend, "_archive", edit_while_packaging)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert ignore.read_bytes() == concurrent
    assert not (knowledge / "docs-raw/sources/dbox.example.yml").exists()
    assert all("dbox.local.yml" not in row.get("path", "") for row in report.get("files", []))


@pytest.mark.parametrize("skill_count", [3, 8])
def test_actual_cli_discovers_active_packages_and_preserves_distribution_files(
    tmp_path, targets, skill_count
):
    source = make_source(tmp_path / "source", skill_count)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    skills = targets["skills_root"]
    expected_names = {
        path.parent.name
        for path in (source / "skills/common/knowledge").glob("*/SKILL.md")
    }
    assert {path.name for path in skills.iterdir() if path.is_dir()} == expected_names
    for name in expected_names:
        actual = tree(skills / name)
        for relative in (
            "SKILL.md",
            "scripts/cli.py",
            "references/request.md",
            "artifacts/result.yaml",
            "artifacts/templates/result.md",
            "requirements.lock.txt",
            "requirements-dev.lock.txt",
        ):
            assert actual[relative] == (
                source / "skills/common/knowledge" / name / relative
            ).read_bytes()
        assert not any(
            part in {"tests", "__pycache__", "config.env", ".env"}
            for relative in actual
            for part in Path(relative).parts
        )
        assert all(b"DO_NOT_SHIP" not in data for data in actual.values())
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        for filename in ("workflow.yaml", "layouts.yaml", "README.md"):
            assert (targets["workflows_root"] / name / filename).read_bytes() == (
                source / "workflows/common/knowledge" / name / filename
            ).read_bytes()
    published = tree(targets["project_root"] / DOMAIN)
    assert published["governance/contracts/example.py"] == b"VALUE = 'locked'\n"
    assert "docs-llm-wiki/使用说明.md" in published
    assert all(b"synthetic business data" not in value for value in published.values())
    assert b"private-source" not in b"".join(published.values())


def test_cli_repeat_update_preserves_project_and_business_bytes(source, targets):
    assert cli(source, targets)[0] == 0
    project = targets["project_root"]
    keep = {
        "AGENTS.md": b"# Existing project rules\r\n",
        "config.yml": b"knowledge_roots:\n  wifi: himate-knowledge-wifi-mp\n",
        f"{DOMAIN}/governance/sources.lock.yaml": b"sources: [existing-business]\n",
        f"{DOMAIN}/docs-raw/specs/customer.md": b"raw original\x00",
        f"{DOMAIN}/knowledge/entity/customer.md": b"customer card\r\n",
        f"{DOMAIN}/knowledge/indexes/overview.md": b"customer navigation\n",
        f"{DOMAIN}/logs/ingest/customer.json": b'{"business":true}',
    }
    for name, data in keep.items():
        put(project, name, data)
    put(targets["skills_root"], "unrelated-package/custom.txt", b"other package")
    put(targets["skills_root"], "hs-knowledge-query/local-helper.txt", b"unknown file")
    before = all_target_bytes(targets)
    assert cli(source, targets)[0] == 0
    assert all_target_bytes(targets) == before
    replacement = b"print('updated without deleting unknown files')\n"
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", replacement)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert (targets["skills_root"] / "hs-knowledge-query/scripts/cli.py").read_bytes() == replacement
    assert all((project / name).read_bytes() == data for name, data in keep.items())
    assert (targets["skills_root"] / "unrelated-package/custom.txt").read_bytes() == b"other package"
    assert (targets["skills_root"] / "hs-knowledge-query/local-helper.txt").read_bytes() == b"unknown file"


def test_existing_yaml_nested_knowledge_root_is_used_without_overwrite(source, targets):
    project = targets["project_root"]
    config = b"# Existing YAML, not a text-pattern config\nknowledge_roots: {wifi: nested/domain}\nmodules: []\n"
    put(project, "config.yml", config)
    put(project, "AGENTS.md", b"existing entry")
    put(project, "nested/domain/knowledge/custom.md", b"customer knowledge")
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert (project / "config.yml").read_bytes() == config
    assert (project / "AGENTS.md").read_bytes() == b"existing entry"
    assert (project / "nested/domain/governance/contracts/example.py").is_file()
    assert (project / "nested/domain/knowledge/custom.md").read_bytes() == b"customer knowledge"
    assert not (project / DOMAIN).exists()


@pytest.mark.parametrize("config", ["[broken", "knowledge_roots: {}", "knowledge_roots: {wifi: ../outside}", "knowledge_roots: {wifi: 'nested/../../outside'}"])
def test_invalid_or_escaping_existing_config_cannot_publish(source, targets, config):
    put(targets["project_root"], "config.yml", config)
    before = all_target_bytes(targets)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert all_target_bytes(targets) == before
    assert not targets["skills_root"].exists()
    assert not targets["workflows_root"].exists()


@pytest.mark.parametrize("corruption", ["hash", "second-hash", "missing", "traversal"])
def test_all_source_rule_hashes_and_paths_are_checked_before_any_write(
    source, targets, corruption
):
    if corruption == "hash":
        put(source, f"{DOMAIN}/governance/contracts/example.py", "TAMPERED\n")
    elif corruption == "second-hash":
        put(source, f"{DOMAIN}/governance/schemas/example.schema.json", "TAMPERED\n")
    elif corruption == "missing":
        (source / DOMAIN / "governance/contracts/example.py").unlink()
    else:
        put(source, "outside.py", "outside contract\n")
        write_lock(
            source,
            {"outside": {"path": "../outside.py", "sha256": hashlib.sha256(b"outside contract\n").hexdigest()}},
        )
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


@pytest.mark.parametrize("relationship", ["equal", "nested", "project-nested", "source-contained"])
def test_overlapping_source_or_destination_roots_are_rejected(source, targets, relationship):
    if relationship == "equal":
        targets["workflows_root"] = targets["skills_root"]
    elif relationship == "nested":
        targets["workflows_root"] = targets["skills_root"] / "nested"
    elif relationship == "project-nested":
        targets["skills_root"] = targets["project_root"] / "skills"
    else:
        targets["project_root"] = source / "output"
    before = tree(source)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert tree(source) == before
    assert_no_targets(targets)


def test_entire_write_set_is_preflighted_before_updating_early_files(source, targets):
    assert cli(source, targets)[0] == 0
    selected = source / "skills/common/knowledge/hs-knowledge-explore/SKILL.md"
    selected.write_bytes(selected.read_bytes() + b"new early bytes\n")
    blocked = targets["workflows_root"] / "hs-knowledge-lint/README.md"
    blocked.unlink()
    blocked.mkdir()
    put(blocked, "owned.txt", b"preserve conflicting directory")
    before = all_target_bytes(targets)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert all_target_bytes(targets) == before


def test_missing_dependencies_return_without_creating_targets(
    backend, monkeypatch, capsys, source, targets
):
    calls = []

    def unavailable(source_root, install_dependencies=False):
        calls.append(install_dependencies)
        return {
            "status": "missing_dependencies",
            "python": sys.executable,
            "version": "3.11.0",
            "supported": True,
            "missing": [{"name": "synthetic-missing", "required": "1", "installed": None}],
        }

    monkeypatch.setattr(backend, "runtime_report", unavailable)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (2, "missing_dependencies")
    assert calls == [False]
    assert_no_targets(targets)


def test_unsupported_python_fails_without_publication(backend, monkeypatch, capsys, source, targets):
    monkeypatch.setattr(backend.sys, "version_info", (3, 13, 0, "final", 0))
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_dependency_install_failure_cannot_publish(backend, monkeypatch, capsys, source, targets):
    calls = []

    def failed_install(source_root, install_dependencies=False):
        calls.append(install_dependencies)
        assert install_dependencies
        raise backend.DeploymentError("Synthetic dependency installer failed")

    monkeypatch.setattr(backend, "runtime_report", failed_install)
    code, report = invoke(backend, capsys, source, targets, "--install-dependencies")
    assert (code, report["status"]) == (3, "failed")
    assert calls == [True]
    assert_no_targets(targets)


def test_real_dependency_installer_failure_uses_selected_python_and_cannot_publish(
    backend, monkeypatch, capsys, source, targets
):
    commands = []
    supplied_locks = []
    monkeypatch.setattr(backend.importlib.metadata, "version", lambda name: "0.synthetic")

    def fail(command, **kwargs):
        commands.append(command)
        supplied_locks.append(Path(command[command.index("-r") + 1]).read_bytes())
        raise subprocess.CalledProcessError(27, command)

    monkeypatch.setattr(backend.subprocess, "run", fail)
    code, report = invoke(backend, capsys, source, targets, "--install-dependencies")
    assert (code, report["status"]) == (3, "failed")
    assert len(commands) == 1
    assert commands[0][:3] == [sys.executable, "-m", "pip"]
    assert supplied_locks == [
        (source / "skills/common/knowledge/hs-knowledge-explore/requirements.lock.txt").read_bytes()
    ]
    assert_no_targets(targets)


def test_plan_cannot_install_dependencies_even_with_install_flag(
    backend, monkeypatch, capsys, source, targets
):
    monkeypatch.setattr(backend.importlib.metadata, "version", lambda name: "0.synthetic")

    def forbidden(*args, **kwargs):
        pytest.fail("A read-only plan attempted dependency installation")

    monkeypatch.setattr(backend.subprocess, "run", forbidden)
    code, report = invoke(backend, capsys, source, targets, "--plan", "--install-dependencies")
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


@pytest.mark.parametrize("member", ["../escape.py", "C:/escape.py", "nested\\escape.py", "CON"])
def test_invalid_zip_entries_are_rejected_before_publication(
    backend, monkeypatch, capsys, source, targets, member
):
    real_archive = backend._archive

    def poisoned(payload):
        stream = io.BytesIO(real_archive(payload))
        with zipfile.ZipFile(stream, "a") as archive:
            archive.writestr(member, b"injected ZIP member")
        return stream.getvalue()

    monkeypatch.setattr(backend, "_archive", poisoned)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_changed_zip_on_project_share_cannot_publish_final_assets(
    backend, monkeypatch, capsys, source, targets
):
    real_copy = backend.shutil.copyfile

    def changed_on_share(source_file, target_file, *args, **kwargs):
        result = real_copy(source_file, target_file, *args, **kwargs)
        if Path(target_file).name == "knowledge.zip":
            Path(target_file).write_bytes(b"changed after copy")
        return result

    monkeypatch.setattr(backend.shutil, "copyfile", changed_on_share)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert not targets["skills_root"].exists()
    assert not targets["workflows_root"].exists()
    assert not (targets["project_root"] / DOMAIN).exists()
    assert report["stage_cleanup_pending"] is True
    assert (Path(report["stage"]) / "knowledge.zip").read_bytes() == b"changed after copy"


@pytest.mark.parametrize("problem", ["skill-name", "workflow-id", "unknown-skill"])
def test_invalid_host_metadata_or_skill_reference_cannot_publish(source, targets, problem):
    if problem == "skill-name":
        put(source, "skills/common/knowledge/hs-knowledge-query/SKILL.md", "---\nname: incorrect-name\n---\n")
    else:
        workflow = {"version": 1, "id": "hs-knowledge-lint", "nodes": []}
        if problem == "workflow-id":
            workflow["id"] = "incorrect-workflow-id"
        else:
            workflow["nodes"] = [{"id": "unknown", "type": "skill", "skill": "hs-knowledge-not-installed"}]
        put(source, "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml", yaml.safe_dump(workflow))
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


@pytest.mark.parametrize("already_deployed", [False, True])
def test_mid_write_failure_restores_existing_bytes_and_removes_new_files(
    backend, monkeypatch, capsys, source, targets, already_deployed
):
    if already_deployed:
        assert cli(source, targets)[0] == 0
        for name in ("hs-knowledge-explore", "hs-knowledge-query"):
            selected = source / "skills/common/knowledge" / name / "SKILL.md"
            selected.write_bytes(selected.read_bytes() + b"changed bytes\n")
        put(targets["skills_root"], "unrelated-package/private.bin", b"owned by another task")
    before = all_target_bytes(targets)
    real_write = backend._write_atomic
    calls = 0

    def interrupted(path, data, *args, **kwargs):
        nonlocal calls
        calls += 1
        real_write(path, data, *args, **kwargs)
        if calls == 2:
            raise OSError("Synthetic interruption after the second real write")

    monkeypatch.setattr(backend, "_write_atomic", interrupted)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert calls >= 2
    assert all_target_bytes(targets) == before


def test_readback_mismatch_cannot_be_reported_as_deployed(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    selected = targets["skills_root"] / "hs-knowledge-query/scripts/cli.py"
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"new expected bytes\n")
    real_write = backend._write_atomic

    def replaced_after_write(path, data, *args, **kwargs):
        real_write(path, data, *args, **kwargs)
        if Path(path) == selected:
            Path(path).write_bytes(b"potential concurrent owner bytes")

    monkeypatch.setattr(backend, "_write_atomic", replaced_after_write)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert selected.read_bytes() == b"potential concurrent owner bytes"
    assert "rollback" in json.dumps(report).lower()


def test_detected_readback_failure_restores_verified_batch_bytes(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    before = all_target_bytes(targets)
    selected = targets["skills_root"] / "hs-knowledge-query/scripts/cli.py"
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"updated script\n")
    real_write = backend._write_atomic
    real_current = backend._current
    armed = False
    injected = False

    def written(path, data, *args, **kwargs):
        nonlocal armed
        real_write(path, data, *args, **kwargs)
        if Path(path) == selected:
            armed = True

    def one_bad_read(path):
        nonlocal injected
        actual = real_current(path)
        if Path(path) == selected and armed and not injected:
            injected = True
            return b"synthetic failed readback"
        return actual

    monkeypatch.setattr(backend, "_write_atomic", written)
    monkeypatch.setattr(backend, "_current", one_bad_read)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert injected
    assert report["rolled_back"] is True
    assert all_target_bytes(targets) == before


def make_link(link: Path, target: Path, *, directory=False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlink creation unavailable on this host: {exc}")


def test_source_symlink_is_rejected_before_writes(source, targets, tmp_path):
    external = put(tmp_path, "external.py", b"external source bytes")
    package = source / "skills/common/knowledge/hs-knowledge-query/scripts"
    make_link(package / "external.py", external)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert external.read_bytes() == b"external source bytes"
    assert_no_targets(targets)


def test_target_ancestor_symlink_is_rejected(source, targets, tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    link = tmp_path / "linked-parent"
    make_link(link, external, directory=True)
    targets["skills_root"] = link / "skills"
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert tree(external) == {}
    assert not (external / "skills").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction safety")
def test_windows_target_junction_is_rejected(source, targets, tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    link = tmp_path / "junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(external)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("Windows junction creation unavailable")
    try:
        targets["skills_root"] = link / "skills"
        code, report = cli(source, targets)
        assert (code, report["status"]) == (3, "failed")
        assert tree(external) == {}
        assert not (external / "skills").exists()
    finally:
        os.rmdir(link)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction safety")
def test_windows_source_junction_is_rejected(source, targets, tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    put(external, "private.py", b"outside source")
    link = source / "skills/common/knowledge/hs-knowledge-query/scripts/junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(external)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("Windows junction creation unavailable")
    try:
        code, report = cli(source, targets)
        assert (code, report["status"]) == (3, "failed")
        assert tree(external) == {"private.py": b"outside source"}
        assert_no_targets(targets)
    finally:
        os.rmdir(link)


@pytest.mark.parametrize("name", ["CON", "NUL.txt", "LPT1", "COM9.log"])
def test_windows_device_names_in_destinations_are_rejected(source, targets, tmp_path, name):
    targets["skills_root"] = tmp_path / name / "skills"
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


@pytest.mark.skipif(os.name != "nt", reason="Windows unmapped-drive anchor safety")
def test_unavailable_drive_anchor_fails_promptly_without_directory_creation(source, targets):
    import ctypes

    mapped = ctypes.windll.kernel32.GetLogicalDrives()
    letters = "ABDFGHIJKLMNOPQRSTUVWXZ"
    letter = next((name for name in letters if not mapped & (1 << (ord(name) - ord("A")))), None)
    if letter is None:
        pytest.skip("Every candidate Windows drive letter is registered")
    targets["skills_root"] = Path(letter + ":/factum-deploy-test/skills")
    code, report = cli(source, targets, timeout=5)
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_first_user_site_install_is_verified_by_fresh_python_and_becomes_visible(source, tmp_path):
    """The user site is absent at process startup; fake pip only writes metadata."""
    put(source, "skills/common/knowledge/hs-knowledge-explore/requirements.lock.txt", "factum-fresh-probe-only==1.2.3\n")
    userbase = tmp_path / "isolated-userbase"
    environment = {**os.environ, "PYTHONUSERBASE": str(userbase), "TMP": str(tmp_path), "TEMP": str(tmp_path)}
    environment.pop("PYTHONNOUSERSITE", None)
    environment.pop("PYTHONPATH", None)
    script = r'''
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import site
import subprocess
import sys

spec = importlib.util.spec_from_file_location("fresh_site_deployment", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
usersite = Path(site.getusersitepackages())
initial_exists = usersite.exists()
pip_commands, fresh_commands = [], []
real_run = subprocess.run

def fake_pip(command, *args, **kwargs):
    if command[1:3] == ["-m", "pip"]:
        pip_commands.append(command)
        metadata = usersite / "factum_fresh_probe_only-1.2.3.dist-info" / "METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text("Metadata-Version: 2.1\nName: factum-fresh-probe-only\nVersion: 1.2.3\n", encoding="utf-8")
        (usersite / "factum_fresh_probe_marker.py").write_text("VALUE = 'fresh user site'\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)
    fresh_commands.append(command)
    return real_run(command, *args, **kwargs)

module.subprocess.run = fake_pip
report = module.runtime_report(Path(sys.argv[2]), install_dependencies=True)
try:
    visible_version = importlib.metadata.version("factum-fresh-probe-only")
except importlib.metadata.PackageNotFoundError:
    visible_version = None
try:
    import factum_fresh_probe_marker
    import_visible = factum_fresh_probe_marker.VALUE
except ImportError:
    import_visible = None
print(json.dumps({"report": report, "initial_exists": initial_exists,
                  "enabled": site.ENABLE_USER_SITE, "pip_commands": pip_commands,
                  "fresh_commands": fresh_commands, "visible_version": visible_version,
                  "import_visible": import_visible}))
'''
    completed = subprocess.run(
        [getattr(sys, "_base_executable", sys.executable), "-B", "-c", script, str(BACKEND), str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["initial_exists"] is False
    assert result["enabled"] is True
    assert result["report"]["status"] == "ready"
    assert result["visible_version"] == "1.2.3"
    assert result["import_visible"] == "fresh user site"
    assert len(result["pip_commands"]) == 1
    assert "--user" in result["pip_commands"][0]
    assert result["fresh_commands"]
    assert all("-I" not in command and "-c" in command for command in result["fresh_commands"])


def test_virtual_environment_install_uses_its_interpreter_without_user_site(
    backend, monkeypatch, capsys, source, targets, tmp_path
):
    monkeypatch.setattr(backend.sys, "prefix", str(tmp_path / "active-venv"))
    monkeypatch.setattr(backend.sys, "base_prefix", str(tmp_path / "base-python"))
    original_version = backend.importlib.metadata.version
    original_run = backend.subprocess.run
    installed = False
    commands = []

    def version(name):
        return original_version(name) if installed else "0.synthetic"

    def fake_pip(command, *args, **kwargs):
        nonlocal installed
        if command[1:3] == ["-m", "pip"]:
            commands.append(command)
            installed = True
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(backend.importlib.metadata, "version", version)
    monkeypatch.setattr(backend.subprocess, "run", fake_pip)
    code, report = invoke(backend, capsys, source, targets, "--install-dependencies")
    assert (code, report["status"]) == (0, "deployed")
    assert len(commands) == 1
    assert commands[0][:3] == [sys.executable, "-m", "pip"]
    assert "--user" not in commands[0]


@pytest.mark.parametrize("enabled", [False, None])
def test_global_install_with_unavailable_user_site_fails_without_pip_or_publication(
    backend, monkeypatch, capsys, source, targets, tmp_path, enabled
):
    monkeypatch.setattr(backend.sys, "prefix", str(tmp_path / "global-python"))
    monkeypatch.setattr(backend.sys, "base_prefix", str(tmp_path / "global-python"))
    monkeypatch.setattr(backend.site, "ENABLE_USER_SITE", enabled)
    monkeypatch.setattr(backend.importlib.metadata, "version", lambda name: "0.synthetic")

    def forbidden(*args, **kwargs):
        pytest.fail("An unavailable user site must not invoke pip")

    monkeypatch.setattr(backend.subprocess, "run", forbidden)
    code, report = invoke(backend, capsys, source, targets, "--install-dependencies")
    assert (code, report["status"]) == (3, "failed")
    assert_no_targets(targets)


def test_concurrent_bytes_inserted_immediately_before_writer_are_preserved(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    selected = targets["skills_root"] / "hs-knowledge-query/scripts/cli.py"
    original = selected.read_bytes()
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"new deployment bytes\n")
    before = all_target_bytes(targets)
    real_write = backend._write_atomic
    injected = False

    def raced(path, data, *args, **kwargs):
        nonlocal injected
        if Path(path) == selected and not injected:
            injected = True
            selected.write_bytes(b"concurrent owner bytes")
        return real_write(path, data, *args, **kwargs)

    monkeypatch.setattr(backend, "_write_atomic", raced)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert injected
    assert selected.read_bytes() == b"concurrent owner bytes"
    before["skills_root"]["hs-knowledge-query/scripts/cli.py"] = b"concurrent owner bytes"
    assert all_target_bytes(targets) == before
    assert str(selected) in report["rollback_conflicts"]
    assert original in tree(Path(report["backup_directory"])).values()


def test_rollback_writer_cannot_replace_bytes_changed_after_rollback_check(
    backend, monkeypatch, capsys, source, targets
):
    assert cli(source, targets)[0] == 0
    selected = targets["skills_root"] / "hs-knowledge-query/scripts/cli.py"
    original = selected.read_bytes()
    put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"new deployment bytes\n")
    real_write = backend._write_atomic
    calls = 0

    def race_in_rollback(path, data, *args, **kwargs):
        nonlocal calls
        if Path(path) == selected:
            calls += 1
            if calls == 1:
                real_write(path, data, *args, **kwargs)
                raise OSError("Synthetic failure to enter rollback")
            if calls == 2:
                selected.write_bytes(b"concurrent rollback owner bytes")
        return real_write(path, data, *args, **kwargs)

    monkeypatch.setattr(backend, "_write_atomic", race_in_rollback)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert calls == 2
    assert selected.read_bytes() == b"concurrent rollback owner bytes"
    assert str(selected) in report["rollback_conflicts"]
    assert original in tree(Path(report["backup_directory"])).values()


@pytest.mark.parametrize("already_deployed", [False, True])
def test_keyboard_interrupt_after_first_write_is_failed_and_restores_original_bytes(
    backend, monkeypatch, capsys, source, targets, already_deployed
):
    if already_deployed:
        assert cli(source, targets)[0] == 0
        put(source, "skills/common/knowledge/hs-knowledge-query/scripts/cli.py", b"new deployment bytes\n")
    before = all_target_bytes(targets)
    real_write = backend._write_atomic
    interrupted = False

    def controlled_interrupt(path, data, *args, **kwargs):
        nonlocal interrupted
        real_write(path, data, *args, **kwargs)
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt("Synthetic controlled cancellation after first write")

    monkeypatch.setattr(backend, "_write_atomic", controlled_interrupt)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert interrupted
    assert report["rolled_back"] is True
    assert all_target_bytes(targets) == before
    if not already_deployed:
        assert_no_targets(targets)


def test_fresh_knowledge_attributes_preserve_bytes_and_existing_policy(source, targets):
    assert cli(source, targets)[0] == 0
    attributes = targets["project_root"] / DOMAIN / ".gitattributes"
    assert attributes.read_bytes() == b"* -text\n"
    custom = b"# Existing project policy\r\n*.md text eol=crlf\r\n"
    attributes.write_bytes(custom)
    assert cli(source, targets)[0] == 0
    assert attributes.read_bytes() == custom


@pytest.mark.skipif(os.name != "nt", reason="Windows same-session deployment mutex")
def test_same_target_mutex_blocks_other_process_and_plan_remains_read_only(backend, source, targets):
    with backend._deployment_mutex([targets["skills_root"]]) as protection:
        assert protection == "same_windows_session_named_mutex"
        code, report = cli(source, targets, "--plan", timeout=5)
        assert (code, report["status"]) == (0, "planned")
        assert_no_targets(targets)
        code, report = cli(source, targets, timeout=5)
        assert (code, report["status"]) == (3, "failed")
        assert_no_targets(targets)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert report["concurrency_protection"] == "same_windows_session_named_mutex"


@pytest.mark.parametrize("location", ["config", "nested-config", "framework", "skill", "workflow"])
def test_duplicate_yaml_keys_cannot_choose_ambiguous_paths_or_host_identity(source, targets, location):
    if location in {"config", "nested-config"}:
        duplicate = (
            f"knowledge_roots: {{wifi: {DOMAIN}}}\nknowledge_roots: {{wifi: {DOMAIN}}}\n"
            if location == "config"
            else f"knowledge_roots:\n  wifi: {DOMAIN}\n  wifi: {DOMAIN}\n"
        )
        put(targets["project_root"], "config.yml", duplicate)
    elif location == "framework":
        lock = source / DOMAIN / "governance/framework.lock.yaml"
        lines = lock.read_text(encoding="utf-8").splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if line.lstrip().startswith("path:"))
        lines.insert(index, lines[index])
        lock.write_text("".join(lines), encoding="utf-8")
    elif location == "skill":
        put(source, "skills/common/knowledge/hs-knowledge-query/SKILL.md", "---\nname: hs-knowledge-query\nname: hs-knowledge-query\n---\n")
    else:
        put(source, "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml", "version: 1\nid: hs-knowledge-lint\nid: hs-knowledge-lint\nnodes: []\n")
    before = all_target_bytes(targets)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert all_target_bytes(targets) == before
    assert not targets["skills_root"].exists()
    assert not targets["workflows_root"].exists()
