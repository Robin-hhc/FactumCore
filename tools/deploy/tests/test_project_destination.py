"""Existing canonical knowledge roots win over stale historical path mappings."""

from pathlib import Path

import pytest
import yaml

from test_deploy import DOMAIN, all_target_bytes, cli, invoke, put


def existing_project(targets, relative=None):
    project = targets["project_root"]
    knowledge = project / DOMAIN
    config = {
        "schema_version": "2.0", "workspace_id": "existing-business",
        "knowledge_roots": {"wifi": relative, "other": "himate/other-domain"},
        "code_root": "main", "modules": [{"path": "wifi/host", "sides": ["host"]}],
    }
    if relative is not None:
        config_text = yaml.safe_dump(config, sort_keys=False).replace(
            "wifi: " + relative + "\n", 'wifi: "' + relative + '" # existing mapping comment\n',
        )
        put(project, "config.yml", ("# Business-owned configuration\n" + config_text).replace("\n", "\r\n"))
    keep = {
        project / "AGENTS.md": b"existing business instructions\r\n",
        project / "main/wifi/host/entry.c": b"int business(void) { return 7; }\n",
        project / "himate/other-domain/owned.txt": b"unrelated group\r\n",
        knowledge / "docs-raw/specs/customer.md": b"original document\r\n",
        knowledge / "knowledge/rules/customer.md": b"existing card\r\n",
        knowledge / "governance/sources.lock.yaml": b"existing source lock\r\n",
        knowledge / "docs-raw/sources/dbox.local.yml": b"path: /private/native/source\r\n",
        knowledge / "logs/publications/customer.json": b"existing publication\r\n",
    }
    if relative is not None and relative != DOMAIN:
        keep[project / relative / "legacy-owned.txt"] = b"legacy bytes are not migrated\r\n"
    for path, data in keep.items():
        put(path.parent, path.name, data)
    put(knowledge, "governance/contracts/example.py", b"VALUE = 'old framework'\n")
    return knowledge, config, keep


@pytest.mark.parametrize("relative", [None, DOMAIN])
def test_project_root_with_existing_nested_knowledge_is_updated_in_place(source, targets, relative):
    knowledge, _, keep = existing_project(targets, relative)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert Path(report["targets"]["knowledge_root"]) == knowledge
    assert (knowledge / "governance/contracts/example.py").read_bytes() == b"VALUE = 'locked'\n"
    assert all(path.read_bytes() == data for path, data in keep.items())
    project = targets["project_root"]
    assert not (project / "himate-knowledge-wifi-mp").exists()
    assert not (project / "himate/himate").exists()
    assert not (project / "knowledge.py").exists()


@pytest.mark.parametrize("relative", [
    "himate-knowledge-wifi-mp", "himate", "himate/himate/himate-knowledge-wifi-mp",
])
def test_existing_canonical_root_corrects_stale_mapping_without_moving_business_data(source, targets, relative):
    knowledge, config, keep = existing_project(targets, relative)
    config_path = targets["project_root"] / "config.yml"
    original_config = config_path.read_bytes()
    before = all_target_bytes(targets)
    code, plan = cli(source, targets, "--plan")
    assert (code, plan["status"]) == (0, "planned")
    assert all_target_bytes(targets) == before
    assert Path(plan["targets"]["knowledge_root"]) == knowledge

    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert Path(report["targets"]["knowledge_root"]) == knowledge
    assert (knowledge / "governance/contracts/example.py").read_bytes() == b"VALUE = 'locked'\n"
    assert all(path.read_bytes() == data for path, data in keep.items())
    actual = yaml.safe_load(config_path.read_bytes())
    expected = {**config, "knowledge_roots": {**config["knowledge_roots"], "wifi": DOMAIN}}
    assert actual == expected
    assert config_path.read_bytes() == original_config.replace(
        ('"' + relative + '"').encode(), ('"' + DOMAIN + '"').encode(), 1,
    )
    assert not (targets["project_root"] / "knowledge.py").exists()
    assert not (targets["project_root"] / relative / "knowledge.py").exists()

    code, repeated = cli(source, targets, "--plan")
    assert (code, repeated["status"]) == (0, "planned")
    assert (repeated["write_count"], repeated["delete_count"], repeated["remove_directory_count"]) == (0, 0, 0)


@pytest.mark.parametrize("relative", [
    "himate", "himate/himate/himate-knowledge-wifi-mp", "himate-knowledge-wifi-mp",
])
def test_stale_alias_with_no_existing_knowledge_creates_the_standard_root(source, targets, relative):
    project = targets["project_root"]
    original_config = ('# Existing project\nknowledge_roots: {wifi: "' + relative
                       + '", other: "himate/other-domain"}\ncode_root: main\nmodules: []\n').encode()
    put(project, "config.yml", original_config)
    other = put(project, "himate/other-domain/owned.txt", b"other group bytes\r\n")
    knowledge = project / DOMAIN
    assert not knowledge.exists()
    before = all_target_bytes(targets)
    code, plan = cli(source, targets, "--plan")
    assert (code, plan["status"]) == (0, "planned")
    assert all_target_bytes(targets) == before
    assert Path(plan["targets"]["knowledge_root"]) == knowledge
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert Path(report["targets"]["knowledge_root"]) == knowledge
    assert (knowledge / "governance/contracts/example.py").read_bytes() == b"VALUE = 'locked'\n"
    assert (project / "config.yml").read_bytes() == original_config.replace(
        ('"' + relative + '"').encode(), ('"' + DOMAIN + '"').encode(), 1,
    )
    assert other.read_bytes() == b"other group bytes\r\n"
    assert not (project / relative / "knowledge.py").exists()
    code, repeated = cli(source, targets, "--plan")
    assert (code, repeated["status"]) == (0, "planned")
    assert (repeated["write_count"], repeated["delete_count"], repeated["remove_directory_count"]) == (0, 0, 0)


@pytest.mark.parametrize("relative", ["himate-knowledge-wifi-mp", "custom/domain"])
def test_existing_flat_or_explicit_custom_root_is_respected(source, targets, relative):
    project = targets["project_root"]
    original_config = ('# Keep explicit configuration\nknowledge_roots: {wifi: "' + relative
                       + '"}\ncode_root: main\nmodules: []\n').encode()
    put(project, "config.yml", original_config)
    knowledge = project / relative
    original = put(knowledge, "docs-raw/specs/customer.md", b"existing raw bytes\r\n")
    card = put(knowledge, "knowledge/rules/customer.md", b"existing card bytes\r\n")
    if relative == "custom/domain":
        put(project / DOMAIN, "README.md", b"separate standard tree is not selected")
    else:
        assert not (project / DOMAIN).exists()
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert Path(report["targets"]["knowledge_root"]) == knowledge
    assert (project / "config.yml").read_bytes() == original_config
    assert original.read_bytes() == b"existing raw bytes\r\n"
    assert card.read_bytes() == b"existing card bytes\r\n"
    assert (knowledge / "governance/contracts/example.py").read_bytes() == b"VALUE = 'locked'\n"
    if relative == "custom/domain":
        assert (project / DOMAIN / "README.md").read_bytes() == b"separate standard tree is not selected"
    else:
        assert not (project / DOMAIN).exists()


def test_path_repair_preserves_utf8_bom_chinese_comments_and_single_quotes(source, targets):
    knowledge, _, keep = existing_project(targets, "himate")
    config_path = targets["project_root"] / "config.yml"
    original = b"\xef\xbb\xbf" + "# 项目配置由业务维护\r\n".encode() + config_path.read_bytes().replace(
        b'wifi: "himate"', b"wifi: 'himate'",
    )
    config_path.write_bytes(original)
    code, report = cli(source, targets)
    assert (code, report["status"]) == (0, "deployed")
    assert Path(report["targets"]["knowledge_root"]) == knowledge
    assert config_path.read_bytes() == original.replace(b"'himate'", ("'" + DOMAIN + "'").encode(), 1)
    assert all(path.read_bytes() == data for path, data in keep.items())


def test_framework_write_failure_rolls_back_the_already_repaired_config(
    backend, monkeypatch, capsys, source, targets,
):
    knowledge, _, keep = existing_project(targets, "himate")
    config_path = targets["project_root"] / "config.yml"
    original = config_path.read_bytes()
    expected = original.replace(b'"himate"', ('"' + DOMAIN + '"').encode(), 1)
    selected = knowledge / "governance/contracts/example.py"
    before = all_target_bytes(targets)
    real_write = backend._write_atomic
    config_updated = False
    injected = False

    def fail_after_repair(path, data, *args, **kwargs):
        nonlocal config_updated, injected
        real_write(path, data, *args, **kwargs)
        if Path(path) == config_path and data == expected:
            config_updated = True
        if Path(path) == selected and not injected:
            injected = True
            assert config_updated
            assert config_path.read_bytes() == expected
            raise OSError("Synthetic framework failure after knowledge path repair")

    monkeypatch.setattr(backend, "_write_atomic", fail_after_repair)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"], report["rolled_back"]) == (3, "failed", True)
    assert config_updated and injected
    assert any("Synthetic framework failure" in line for line in report["diagnostics"])
    assert config_path.read_bytes() == original
    assert all_target_bytes(targets) == before
    assert all(path.read_bytes() == data for path, data in keep.items())


def test_concurrent_config_edit_blocks_path_repair_and_preserves_the_new_owner_value(
    backend, monkeypatch, capsys, source, targets,
):
    _, _, keep = existing_project(targets, "himate")
    config_path = targets["project_root"] / "config.yml"
    before = all_target_bytes(targets)
    concurrent = config_path.read_bytes().replace(b'"himate"', b'"custom/concurrent-root"', 1)
    real_archive = backend._archive
    injected = False

    def edit_before_install(payload):
        nonlocal injected
        result = real_archive(payload)
        if not injected:
            injected = True
            config_path.write_bytes(concurrent)
        return result

    monkeypatch.setattr(backend, "_archive", edit_before_install)
    code, report = invoke(backend, capsys, source, targets)
    assert (code, report["status"]) == (3, "failed")
    assert injected
    assert any("Project configuration changed during deployment" in line for line in report["diagnostics"])
    assert config_path.read_bytes() == concurrent
    before["project_root"]["config.yml"] = concurrent
    assert all_target_bytes(targets) == before
    assert all(path.read_bytes() == data for path, data in keep.items())
