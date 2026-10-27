"""Real public CLI relocation over isolated fixtures, without host acceptance claims.

The project fixture has no capability source folders. Real Skill packages live in
separate Agent directories; development tests and dev locks are deliberately absent.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[4]
DOMAIN = REPO / "himate-knowledge-wifi-mp"
INSTALLER = DOMAIN / "tools/deploy/install_catalog.py"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def deployed(tmp_path):
    project = tmp_path / "business project"
    knowledge = project / "himate-knowledge-wifi-mp"
    knowledge.mkdir(parents=True)
    shutil.copytree(DOMAIN / "governance", knowledge / "governance",
                    ignore=shutil.ignore_patterns("__pycache__"))
    config = {
        "schema_version": "2.0", "workspace_id": "relocation-fixture",
        "knowledge_roots": {"wifi": "himate-knowledge-wifi-mp"},
        "code_root": "main", "modules": [],
    }
    (project / "config.yml").write_bytes(canonical(config))
    (project / "main").mkdir()
    (project / "AGENTS.md").write_text("Synthetic project fixture rules.\n", encoding="utf-8")
    (knowledge / "AGENTS.md").write_text("Synthetic domain fixture rules.\n", encoding="utf-8")
    (knowledge / "knowledge").mkdir()
    for name in ("conventions", "chips", "storys", "specs", "protocols"):
        (knowledge / "docs-raw" / name).mkdir(parents=True)
    (knowledge / "docs-raw/specs/relocation.md").write_text(
        "# Relocation fixture\nRead-only original input.\n", encoding="utf-8")

    skills = tmp_path / "agent capability directory"
    skills.mkdir()
    packages = sorted(path for path in (REPO / "skills/common/knowledge").glob("hs-*")
                      if (path / "SKILL.md").is_file())
    for package in packages:
        shutil.copytree(package, skills / package.name,
                        ignore=shutil.ignore_patterns("tests", "requirements-dev.lock.txt",
                                                      "__pycache__", ".pytest_cache", ".ruff_cache"))
    workflows = tmp_path / "separate workflow directory"
    workflows.mkdir()
    shutil.copytree(REPO / "workflows/common/knowledge/hs-knowledge-ingest",
                    workflows / "hs-knowledge-ingest")
    elsewhere = tmp_path / "unrelated cwd"
    elsewhere.mkdir()
    return {"base": tmp_path, "project": project, "knowledge": knowledge,
            "skills": skills, "workflows": workflows, "cwd": elsewhere}


def register(layout, destination, *, python=None, skills=True, workflows=True, extra=()):
    command = [sys.executable, str(INSTALLER), "--register-existing",
               "--workspace-config", str(layout["project"] / "config.yml"),
               "--python", str(python or sys.executable), "--destination", str(destination)]
    if skills:
        command += ["--skills-root", str(layout["skills"])]
    if workflows:
        command += ["--workflows-root", str(layout["workflows"])]
    command += list(extra)
    return subprocess.run(command, cwd=layout["cwd"], capture_output=True, timeout=90)


def call(layout, catalog_path, skill, operation, *, request=None, python=None, skill_root=None):
    catalog = json.loads(catalog_path.read_bytes())
    entry = catalog["skills"][skill]
    incoming = layout["base"] / (operation + "-request.json")
    outgoing = layout["base"] / (operation + "-response.json")
    incoming.write_bytes(canonical({"operation_id": operation, **(request or {})}))
    command = [str(python or entry["python"]),
               str((skill_root or Path(entry["root"])) / "scripts/cli.py"),
               "--input", str(incoming), "--output", str(outgoing),
               "--knowledge-root", str(layout["knowledge"]),
               "--rules-digest", catalog["workspaces"]["relocation-fixture"]["rules_digest"],
               "--catalog", str(catalog_path)]
    result = subprocess.run(command, cwd=layout["cwd"], capture_output=True, timeout=90)
    response = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
    if response:
        assert response["digest"] == hashlib.sha256(canonical(
            {key: value for key, value in response.items() if key != "digest"})).hexdigest()
    return result, response


def assert_scan_succeeded(layout, catalog_path, operation, *, expected_change="new", **kwargs):
    process, result = call(layout, catalog_path, "hs-knowledge-source-scan", operation, **kwargs)
    assert process.returncode == 0, (result, process.stderr.decode(errors="replace"))
    assert result["status"] == "ok" and result["phase"] == "scanned", result
    inventory = json.loads((layout["knowledge"] / result["data"]["scan_ref"]).read_bytes())
    assert inventory["complete"] is True
    assert any(unit["path"] == "docs-raw/specs/relocation.md" and unit["change"] == expected_change
               for unit in inventory["units"])
    # scan uses Context.call to execute the real maintain public CLI in another process.
    children = [json.loads(path.read_bytes()) for path in
                (layout["knowledge"] / ".build/operations" / operation / "calls").rglob("response.json")]
    assert any(child["status"] == "ok" and
               child["tool_identity"]["skill"] == "hs-knowledge-maintain" for child in children)


def test_nested_domain_uses_registered_workspace_for_capture_and_scan(deployed):
    layout = deployed
    nested = layout["project"] / "himate/himate-knowledge-wifi-mp"
    assert nested.resolve().is_relative_to(layout["project"].resolve())
    nested.parent.mkdir()
    layout["knowledge"].rename(nested)
    layout["knowledge"] = nested
    config_path = layout["project"] / "config.yml"
    config = json.loads(config_path.read_bytes())
    config["knowledge_roots"]["wifi"] = "himate/himate-knowledge-wifi-mp"
    config["modules"] = [{"path": "device", "chips": ["chip12"], "sides": ["device"]}]
    config_path.write_bytes(canonical(config))
    module = layout["project"] / "main/device"
    module.mkdir()
    source = module / "source.c"
    source.write_bytes(b"int nested_fixture(void) { return 1; }\n")
    destination = layout["base"] / "nested-registration"
    registered = register(layout, destination)
    assert registered.returncode == 0, registered.stderr.decode(errors="replace")
    catalog_path = destination / "catalog.json"
    process, result = call(layout, catalog_path, "hs-workspace-explore", "nested-e0",
                           request={"target_path": str(source)})
    assert process.returncode == 0, result
    context_ref = result["data"]["context_ref"]
    context = json.loads((nested / context_ref).read_bytes())
    assert Path(context["workspace_root"]) == layout["project"]
    repo_id = next(iter(context["repos"]))
    process, result = call(layout, catalog_path, "hs-knowledge-source-capture", "nested-code",
                           request={"kind": "code", "repo_id": repo_id, "relative_path": "source.c",
                                    "source_id": "nested-code", "context_ref": context_ref})
    assert process.returncode == 0, result
    assert_scan_succeeded(layout, catalog_path, "nested-scan")


@pytest.mark.parametrize("keep_dev_lock", [False, True])
def test_existing_agent_packages_work_without_project_capability_folders(deployed, keep_dev_lock):
    layout = deployed
    if keep_dev_lock:
        for package in layout["skills"].iterdir():
            development_lock = REPO / "skills/common/knowledge" / package.name / "requirements-dev.lock.txt"
            if development_lock.is_file():
                shutil.copyfile(development_lock, package / "requirements-dev.lock.txt")
    before_skills, before_workflows = fingerprint(layout["skills"]), fingerprint(layout["workflows"])
    assert not (layout["project"] / "skills").exists()
    assert not (layout["project"] / "workflows").exists()
    assert any(path.name == "requirements-dev.lock.txt" for path in layout["skills"].rglob("*")) == keep_dev_lock
    assert not any(path.name == "tests" for path in layout["skills"].rglob("*"))
    destination = layout["base"] / "registered"
    registered = register(layout, destination)
    assert registered.returncode == 0, registered.stderr.decode(errors="replace")
    catalog_path = destination / "catalog.json"
    catalog = json.loads(catalog_path.read_bytes())
    assert len(catalog["skills"]) == 19
    assert all(Path(entry["root"]) == layout["skills"] / identity
               for identity, entry in catalog["skills"].items())
    assert not (destination / "config/skills").exists()

    process, result = call(layout, catalog_path, "hs-workspace-explore", "external-e0",
                           request={"target_path": str(layout["project"] / "main")})
    assert process.returncode == 0, result
    assert result["status"] == "ok" and result["phase"] == "context_loaded", result
    context = json.loads((layout["knowledge"] / result["data"]["context_ref"]).read_bytes())
    assert Path(context["workspace_root"]) == layout["project"]
    assert Path(context["knowledge_root"]) == layout["knowledge"]
    assert_scan_succeeded(layout, catalog_path, "external-scan")
    assert fingerprint(layout["skills"]) == before_skills
    assert fingerprint(layout["workflows"]) == before_workflows


def test_instruction_skill_registers_final_paths_and_binds_reference_changes(deployed):
    layout = deployed
    package = layout["skills"] / "hs-codegraph-setup"
    before = fingerprint(layout["skills"])
    first = layout["base"] / "instruction-first-registration"
    result = register(layout, first)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    entry = json.loads((first / "catalog.json").read_bytes())["skills"][package.name]
    assert entry["kind"] == "instructions" and entry["entry"] == "SKILL.md"
    assert Path(entry["root"]) == package
    assert "python" not in entry
    assert fingerprint(layout["skills"]) == before
    reference = package / "references/codegraph.md"
    reference.write_bytes(reference.read_bytes() + b"\nAdditional fixture reference.\n")
    changed = fingerprint(layout["skills"])
    second = layout["base"] / "instruction-second-registration"
    result = register(layout, second)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    updated = json.loads((second / "catalog.json").read_bytes())["skills"][package.name]
    assert entry["package_digest"] != updated["package_digest"]
    assert fingerprint(layout["skills"]) == changed


def test_instruction_skill_is_not_callable_as_a_workflow_cli(deployed):
    """The existing dispatch gate rejects instruction entries before execution."""
    import importlib.util
    from types import SimpleNamespace

    layout = deployed
    destination = layout["base"] / "instruction-dispatch-registration"
    result = register(layout, destination)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    support = layout["skills"] / "hs-workspace-explore/scripts/support.py"
    spec = importlib.util.spec_from_file_location("instruction_dispatch_support", support)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = object.__new__(module.Context)
    context.args = SimpleNamespace(catalog=destination / "catalog.json")
    with pytest.raises(module.NodeError, match="fixed public scripts/cli.py"):
        context.call("hs-codegraph-setup", {})


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-extra.txt"])
def test_existing_package_additional_requirement_files_bind_actual_runtime_identity(deployed, filename):
    layout = deployed
    extra = layout["skills"] / "hs-knowledge-maintain" / filename
    extra.write_text("# Agent-owned metadata; no dependency installation.\n", encoding="utf-8")
    before = fingerprint(layout["skills"])
    first = layout["base"] / "extra-file-registration"
    registered = register(layout, first)
    assert registered.returncode == 0, registered.stderr.decode(errors="replace")
    first_catalog = first / "catalog.json"
    assert_scan_succeeded(layout, first_catalog, "extra-initial")
    assert fingerprint(layout["skills"]) == before

    extra.write_text("# Agent changed this identity-bound file.\n", encoding="utf-8")
    failed, response = call(layout, first_catalog, "hs-knowledge-source-scan", "extra-stale")
    assert failed.returncode != 0
    assert any(item["code"] == "PACKAGE_DIGEST_MISMATCH" for item in response.get("diagnostics", [])), response
    changed = fingerprint(layout["skills"])
    second = layout["base"] / "extra-file-new-registration"
    registered = register(layout, second)
    assert registered.returncode == 0, registered.stderr.decode(errors="replace")
    second_catalog = second / "catalog.json"
    first_entry = json.loads(first_catalog.read_bytes())["skills"]["hs-knowledge-maintain"]
    second_entry = json.loads(second_catalog.read_bytes())["skills"]["hs-knowledge-maintain"]
    assert first_entry["package_digest"] != second_entry["package_digest"]
    assert_scan_succeeded(layout, second_catalog, "extra-refreshed", expected_change="unfinished")
    assert fingerprint(layout["skills"]) == changed


@pytest.mark.parametrize("missing", ["skills", "workflows", "both"])
def test_existing_registration_requires_explicit_roots_without_source_fallback(deployed, missing):
    layout = deployed
    destination = layout["base"] / ("missing-" + missing)
    result = register(layout, destination, skills=missing not in {"skills", "both"},
                      workflows=missing not in {"workflows", "both"},
                      extra=("--source-root", str(REPO)))
    assert result.returncode != 0
    assert not (destination / "catalog.json").exists()


@pytest.mark.parametrize("relative", ["scripts/loose.pyc", "scripts/.pytest_cache/state.txt"])
def test_existing_registration_rejects_unpublishable_identity_files_without_catalog(deployed, relative):
    layout = deployed
    extra = layout["skills"] / "hs-knowledge-maintain" / relative
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"Isolated non-runtime fixture bytes")
    before = fingerprint(layout["skills"])
    destination = layout["base"] / "unpublishable-registration"
    result = register(layout, destination)
    assert result.returncode != 0
    assert b"UNPUBLISHABLE_PACKAGE_FILE" in result.stderr
    assert not destination.exists()
    assert fingerprint(layout["skills"]) == before


@pytest.mark.parametrize("root_name", ["skills", "workflows", "project"])
def test_existing_registration_rejects_overlapping_catalog_output(deployed, root_name):
    layout = deployed
    destination = layout[root_name] / "must-not-create"
    result = register(layout, destination)
    assert result.returncode != 0
    assert not destination.exists()


def test_moved_agent_packages_need_new_catalog(deployed):
    layout = deployed
    first = layout["base"] / "old-package-registration"
    result = register(layout, first)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    before = fingerprint(layout["skills"])
    old_root = layout["skills"]
    new_root = layout["base"] / "moved agent capabilities"
    assert old_root.parent == new_root.parent == layout["base"]
    old_root.rename(new_root)
    layout["skills"] = new_root

    failed, envelope = call(layout, first / "catalog.json", "hs-knowledge-source-scan", "stale-package",
                            python=sys.executable, skill_root=new_root / "hs-knowledge-source-scan")
    assert failed.returncode != 0 and envelope.get("phase") != "scanned"
    second = layout["base"] / "new-package-registration"
    result = register(layout, second)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert_scan_succeeded(layout, second / "catalog.json", "new-package")
    assert fingerprint(new_root) == before


def test_moved_interpreter_needs_new_catalog(deployed):
    layout = deployed
    old_runtime = layout["base"] / "runtime-old"
    built = subprocess.run([sys.executable, "-m", "venv", "--copies", "--without-pip", str(old_runtime)],
                           capture_output=True, timeout=90)
    assert built.returncode == 0, built.stderr.decode(errors="replace")
    relative_python = Path("Scripts/python.exe" if os.name == "nt" else "bin/python")
    old_python = old_runtime / relative_python
    purelib = subprocess.check_output([str(old_python), "-c",
                                      "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True).strip()
    # Fixture-only dependency reuse; this tests interpreter relocation, not package installation.
    Path(purelib, "fixture-runtime.pth").write_text(
        "\n".join(path for path in site.getsitepackages() if Path(path).is_dir()) + "\n", encoding="utf-8")
    first = layout["base"] / "old-runtime-registration"
    result = register(layout, first, python=old_python)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    new_runtime = layout["base"] / "runtime-new"
    assert old_runtime.parent == new_runtime.parent == layout["base"]
    old_runtime.rename(new_runtime)
    new_python = new_runtime / relative_python
    failed, envelope = call(layout, first / "catalog.json", "hs-knowledge-source-scan", "stale-runtime",
                            python=new_python)
    assert failed.returncode != 0 and envelope.get("phase") != "scanned"
    assert any(item["code"] == "MISSING_RUNTIME" for item in envelope.get("diagnostics", [])), envelope
    second = layout["base"] / "new-runtime-registration"
    result = register(layout, second, python=new_python)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert_scan_succeeded(layout, second / "catalog.json", "new-runtime")
