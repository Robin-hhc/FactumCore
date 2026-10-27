"""Public installation boundary over isolated synthetic capability packages."""

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest
import yaml


REPOSITORY = Path(__file__).resolve().parents[4]
SCRIPT = Path(__file__).resolve().parents[1] / "install_catalog.py"
IDS = ["hs-workspace-explore"] + [
    "hs-knowledge-" + name
    for name in (
        "source-capture",
        "change-plan",
        "view-materialize",
        "governance-handoff",
        "candidate-inspect",
        "local-check",
        "candidate-revise",
        "apply",
        "recover",
        "index-build",
        "query-regression",
        "publish-handoff",
        "merge-check",
        "maintain",
        "query",
        "source-scan",
        "lint",
    )
]
INSTRUCTION_IDS = ["hs-codegraph-setup"]


def test_catalog_declares_logical_commands_and_only_one_ingest_workflow(tmp_path):
    source = fixture_source(tmp_path)
    destination = tmp_path / "installed"
    result = install(source, destination)
    assert result.returncode == 0, result.stderr
    catalog = json.loads((destination / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["commands"]["ingest"] == {"kind": "workflow", "target": "hs-knowledge-ingest", "entry_node": "scan_sources"}
    assert catalog["commands"]["lint"]["target"] == "hs-knowledge-lint"
    assert "hs-knowledge-source-scan" in catalog["skills"]
    assert [p.name for p in (destination / "config/workflow-templates").iterdir()] == ["hs-knowledge-ingest"]


def test_current_catalog_omits_human_confirmation_capabilities():
    installer = runpy.run_path(str(SCRIPT))
    assert len(installer["SKILLS"]) == 18
    assert installer["INSTRUCTION_SKILLS"] == tuple(INSTRUCTION_IDS)
    assert "hs-knowledge-confirmation-prepare" not in installer["SKILLS"]
    assert "hs-knowledge-confirmation-record" not in installer["SKILLS"]


def test_current_workflow_reviews_then_lints_without_human_gate():
    package = REPOSITORY / "workflows/common/knowledge/hs-knowledge-ingest"
    workflow = yaml.safe_load((package / "workflow.yaml").read_bytes())
    layout = yaml.safe_load((package / "layouts.yaml").read_bytes())
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert not any(node["type"] == "gate" for node in nodes.values())
    assert not {"prepare_confirmation", "final_view_user_gate", "record_confirmation"} & nodes.keys()
    assert set(layout["canvas"]["nodes"]) == set(nodes)
    routes = {row["id"]: row["target"] for row in nodes["inspect_candidate"]["exits"]}
    assert routes["manual_ready"] == "lint_view"
    assert routes["mixed_ready"] == routes["code_ready"] == "local_check"
    assert nodes["review_content"]["owner"] == "reviewer"
    assert nodes["review_content"]["skill"] == "hs-knowledge-change-plan"
    assert "content_review_ref" in nodes["apply_view"]["prompt"]
    assert "proof_set" not in nodes["apply_view"]["prompt"]
    for node in nodes.values():
        for route in node.get("exits", []):
            assert route["target"] == "__end__" or route["target"] in nodes


def test_installer_validates_additional_native_artifact_contracts(tmp_path):
    source = fixture_source(tmp_path)
    artifacts = source / "skills/common/knowledge/hs-knowledge-source-scan/artifacts"
    contract = yaml.safe_load((artifacts / "result.yaml").read_bytes())
    contract.update(id="hs-knowledge-source-scan-prepare-result", template="../outside.md")
    (artifacts / "prepare-result.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    result = install(source, tmp_path / "installed")
    assert result.returncode != 0
    assert "INVALID_ARTIFACT_REFERENCE" in result.stderr


def fixture_source(tmp_path):
    source = tmp_path / "source workspace"
    for skill in IDS:
        package = source / "skills/common/knowledge" / skill
        files = {
            "SKILL.md": f"---\nname: {skill}\ndescription: fixture only\n---\n# fixture\n",
            "scripts/cli.py": "print('fixture')\n",
            "scripts/support.py": "# fixture\n",
            "tests/test_cli.py": "# fixture\n",
            "requirements.lock.txt": "# stdlib fixture\n",
            "requirements-dev.lock.txt": "# fixture\n",
            "artifacts/result.yaml": yaml.safe_dump(
                {
                    "id": skill + "-result",
                    "title": skill,
                    "required": True,
                    "template": "templates/result.md",
                    "writing_guide": "writing-guide.md",
                    "review_guide": "review-guide.md",
                    "default_location": {"kind": "markdown_file"},
                    "applies_to": {"node_ids": []},
                    "required_on": {"exit_ids": []},
                }
            ),
            "artifacts/templates/result.md": "# Result\n",
            "artifacts/writing-guide.md": "# Write\n",
            "artifacts/review-guide.md": "# Review\n",
        }
        for relative, content in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    for skill in INSTRUCTION_IDS:
        package = source / "skills/common/knowledge" / skill
        (package / "references").mkdir(parents=True)
        (package / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: fixture setup instructions\n---\n"
            "Read [commands](references/codegraph.md).\n", encoding="utf-8")
        (package / "references/codegraph.md").write_text(
            "# Fixture reference\nNo commands are executed during installation.\n", encoding="utf-8")
    for workflow in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        package = source / "workflows/common/knowledge" / workflow
        package.mkdir(parents=True)
        (package / "workflow.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "id": workflow,
                    "kind": "custom",
                    "name": workflow,
                    "entry_node": "bind_project",
                    "nodes": [
                        {
                            "id": "bind_project",
                            "type": "skill",
                            "owner": "coder",
                            "skill": "hs-workspace-explore",
                            "exits": [{"id": "bound", "target": "__end__"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (package / "layouts.yaml").write_text(
            f"template_id: {workflow}\n", encoding="utf-8"
        )
    return source


def install(source, destination, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(source),
            "--destination",
            str(destination),
            "--python",
            sys.executable,
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def test_install_complete_isolated_catalog_without_domain_assets(tmp_path):
    source = fixture_source(tmp_path)
    (source / "private.pem").write_text("PRIVATE KEY", encoding="utf-8")
    raw = source / "aiotbot-knowledge-wifi-mp/docs-raw/specs/private.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("not capability material", encoding="utf-8")
    destination = tmp_path / "installed capabilities"
    result = install(source, destination)
    assert result.returncode == 0, result.stderr
    catalog = json.loads((destination / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["schema_version"] == "2.0"
    assert set(catalog["skills"]) == set(IDS + INSTRUCTION_IDS)
    assert catalog["workspaces"] == {}
    entry = catalog["skills"]["hs-knowledge-apply"]
    assert entry["entry"] == "scripts/cli.py"
    assert Path(entry["python"]).is_absolute()
    assert Path(entry["root"]) == destination / "config/skills/hs-knowledge-apply"
    files = {}
    for path in Path(entry["root"]).rglob("*"):
        if path.is_file() and "tests" not in path.relative_to(entry["root"]).parts:
            files[path.relative_to(entry["root"]).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    canonical = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert entry["package_digest"] == hashlib.sha256(canonical).hexdigest()
    assert not list(destination.rglob("*.pem"))
    assert not (destination / "aiotbot-knowledge-wifi-mp").exists()
    assert (
        len(list((destination / "config/workflow-templates").glob("*/workflow.yaml")))
        == 1
    )


def test_install_refuses_existing_destination_and_preserves_contents(tmp_path):
    source = fixture_source(tmp_path)
    destination = tmp_path / "install"
    destination.mkdir()
    marker = destination / "user-owned"
    marker.write_bytes(b"unchanged")
    result = install(source, destination)
    assert result.returncode != 0
    assert marker.read_bytes() == b"unchanged"
    assert not (destination / "catalog.json").exists()


def test_instruction_skill_distributes_only_text_and_hashes_every_reference(tmp_path):
    source = fixture_source(tmp_path)
    package = source / "skills/common/knowledge/hs-codegraph-setup"
    nested = package / "references/tests/notes.md"
    nested.parent.mkdir()
    nested.write_text("# Reference under a directory named tests\n", encoding="utf-8")
    first = tmp_path / "instruction-install-first"
    result = install(source, first)
    assert result.returncode == 0, result.stderr
    entry = json.loads((first / "catalog.json").read_bytes())["skills"][package.name]
    assert entry["entry"] == "SKILL.md" and entry["kind"] == "instructions"
    assert "python" not in entry
    installed = Path(entry["root"])
    assert not (installed / "scripts").exists()
    assert not (installed / "artifacts").exists()
    hashes = {path.relative_to(installed).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in installed.rglob("*") if path.is_file()}
    expected = hashlib.sha256(json.dumps(hashes, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()
    assert entry["package_digest"] == expected
    nested.write_text("# Changed setup reference\n", encoding="utf-8")
    second = tmp_path / "instruction-install-second"
    result = install(source, second)
    assert result.returncode == 0, result.stderr
    updated = json.loads((second / "catalog.json").read_bytes())["skills"][package.name]
    assert updated["package_digest"] != entry["package_digest"]


@pytest.mark.parametrize("broken,diagnostic", [
    ("SKILL.md", "INCOMPLETE_PACKAGE"),
    ("references/codegraph.md", "INVALID_INSTRUCTION_REFERENCE"),
])
def test_instruction_skill_missing_input_publishes_nothing(tmp_path, broken, diagnostic):
    source = fixture_source(tmp_path)
    (source / "skills/common/knowledge/hs-codegraph-setup" / broken).unlink()
    destination = tmp_path / "missing-instruction"
    result = install(source, destination)
    assert result.returncode != 0 and diagnostic in result.stderr
    assert not destination.exists()


@pytest.mark.parametrize("frontmatter,diagnostic", [
    ("name: wrong\ndescription: fixture", "INVALID_SKILL_METADATA"),
    ("name: hs-codegraph-setup\ndescription: ''", "INVALID_SKILL_METADATA"),
    ("name: hs-codegraph-setup\nname: hs-codegraph-setup\ndescription: fixture", "INVALID_YAML"),
])
def test_instruction_skill_metadata_is_strict(tmp_path, frontmatter, diagnostic):
    source = fixture_source(tmp_path)
    skill = source / "skills/common/knowledge/hs-codegraph-setup/SKILL.md"
    skill.write_text("---\n" + frontmatter + "\n---\n# Instructions\n", encoding="utf-8")
    destination = tmp_path / "invalid-instruction-metadata"
    result = install(source, destination)
    assert result.returncode != 0 and diagnostic in result.stderr
    assert not destination.exists()


@pytest.mark.parametrize("relative", [
    "scripts/setup.py", "references/setup.ps1", "references/secret.bin",
    "requirements.lock.txt", "references/.private.md", "references/secrets.txt",
    "references/config.local.yml",
])
def test_instruction_skill_cannot_smuggle_executables_or_private_files(tmp_path, relative):
    source = fixture_source(tmp_path)
    unexpected = source / "skills/common/knowledge/hs-codegraph-setup" / relative
    unexpected.parent.mkdir(parents=True, exist_ok=True)
    unexpected.write_text("fixture bytes\n", encoding="utf-8")
    destination = tmp_path / "unpublishable-instructions"
    result = install(source, destination)
    assert result.returncode != 0 and "UNPUBLISHABLE" in result.stderr
    assert not destination.exists()


def test_instruction_reference_must_be_text(tmp_path):
    source = fixture_source(tmp_path)
    (source / "skills/common/knowledge/hs-codegraph-setup/references/codegraph.md").write_bytes(b"binary\x00data")
    destination = tmp_path / "binary-instructions"
    result = install(source, destination)
    assert result.returncode != 0 and "NON_TEXT_INSTRUCTION_FILE" in result.stderr
    assert not destination.exists()


@pytest.mark.parametrize(
    "broken",
    ["scripts/cli.py", "artifacts/templates/result.md", "requirements.lock.txt"],
)
def test_missing_package_part_publishes_nothing(tmp_path, broken):
    source = fixture_source(tmp_path)
    (source / "skills/common/knowledge/hs-knowledge-apply" / broken).unlink()
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode != 0
    assert not destination.exists()


def test_wrong_dependency_blocks_without_installing(tmp_path):
    source = fixture_source(tmp_path)
    lock = source / "skills/common/knowledge/hs-knowledge-apply/requirements.lock.txt"
    lock.write_text("factumcore-definitely-absent-fixture==0.0.0\n", encoding="utf-8")
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode != 0
    assert "DEPENDENCY" in result.stderr
    assert not destination.exists()


def test_linked_package_file_rejected(tmp_path):
    source = fixture_source(tmp_path)
    link = source / "skills/common/knowledge/hs-knowledge-apply/scripts/escape.py"
    try:
        link.symlink_to(SCRIPT)
    except OSError:
        pytest.skip("symlink creation unavailable for this user")
    destination = tmp_path / "install"
    assert install(source, destination).returncode != 0
    assert not destination.exists()


def test_workspace_registration_pins_local_paths_and_rule_bytes(tmp_path):
    source = fixture_source(tmp_path)
    workspace = tmp_path / "business workspace"
    config = workspace / "config.yml"
    lock = workspace / "aiotbot-knowledge-wifi-mp/governance/framework.lock.yaml"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"schema_version: '2.0'\n")
    config.write_text(
        "schema_version: '2.0'\nworkspace_id: fixture-wifi\nknowledge_roots:\n  wifi: aiotbot-knowledge-wifi-mp\n",
        encoding="utf-8",
    )
    destination = tmp_path / "install"
    result = install(source, destination, "--workspace-config", str(config))
    assert result.returncode == 0, result.stderr
    catalog = json.loads((destination / "catalog.json").read_bytes())
    assert catalog["workspaces"]["fixture-wifi"] == {
        "config": str(config.resolve()),
        "rules_digest": hashlib.sha256(lock.read_bytes()).hexdigest(),
    }
    registry = json.loads((destination / "workspace-registry.json").read_bytes())
    assert registry["workspaces"][0]["config_path"] == str(config.resolve())


def test_broken_artifact_reference_publishes_nothing(tmp_path):
    source = fixture_source(tmp_path)
    path = source / "skills/common/knowledge/hs-knowledge-apply/artifacts/result.yaml"
    contract = yaml.safe_load(path.read_bytes())
    contract["template"] = "../SKILL.md"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode != 0 and "ARTIFACT_REFERENCE" in result.stderr
    assert not destination.exists()


def test_meaningful_tests_need_not_be_named_test_cli(tmp_path):
    source = fixture_source(tmp_path)
    tests = source / "skills/common/knowledge/hs-knowledge-apply/tests"
    (tests / "test_cli.py").rename(tests / "test_public_governance.py")
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode == 0, result.stderr
    assert (
        destination / "config/skills/hs-knowledge-apply/tests/test_public_governance.py"
    ).is_file()


def test_unicode_metadata_uses_utf8_across_isolated_python(tmp_path):
    source = fixture_source(tmp_path)
    skill = source / "skills/common/knowledge/hs-workspace-explore/SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "fixture only", "从中文路径加载 WiFi 规则"
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "中文安装目录"
    result = install(source, destination)
    assert result.returncode == 0, result.stderr
    assert "中文路径" in (
        destination / "config/skills/hs-workspace-explore/SKILL.md"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("key_type", ["OPENSSH", "EC", "ENCRYPTED"])
def test_private_key_in_an_allowed_text_resource_is_rejected(tmp_path, key_type):
    source = fixture_source(tmp_path)
    path = source / "skills/common/knowledge/hs-knowledge-apply/artifacts/leaked.md"
    path.write_text(
        f"-----BEGIN {key_type} PRIVATE KEY-----\nfixture-only\n", encoding="utf-8"
    )
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode != 0 and "PRIVATE_KEY" in result.stderr
    assert not destination.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction boundary")
@pytest.mark.parametrize("dangling", [False, True], ids=["existing", "dangling"])
@pytest.mark.parametrize("package_path", [
    "hs-knowledge-apply/scripts/escape", "hs-codegraph-setup/references/escape",
])
def test_junction_package_directory_rejected(tmp_path, dangling, package_path):
    import _winapi

    source = fixture_source(tmp_path)
    link = source / "skills/common/knowledge" / package_path
    target = tmp_path / "external"
    target.mkdir()
    (target / "private.py").write_text("# outside\n", encoding="utf-8")
    _winapi.CreateJunction(str(target), str(link))
    if dangling:
        (target / "private.py").unlink()
        target.rmdir()
    installer = runpy.run_path(str(SCRIPT))
    with pytest.raises(installer["InstallError"], match="LINKED_PATH"):
        installer["no_links"](link)
    destination = tmp_path / "install"
    result = install(source, destination)
    assert result.returncode != 0
    if not dangling:
        assert "LINKED_PATH" in result.stderr
    assert not destination.exists()
