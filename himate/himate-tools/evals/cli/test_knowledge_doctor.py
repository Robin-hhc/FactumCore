"""Doctor loads only the verified workspace metadata selector, no business engines."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture
def knowledge(tmp_path):
    workspace = tmp_path / "doctor workspace"
    root = workspace / "himate-knowledge-synthetic"
    root.mkdir(parents=True)
    shutil.copytree(SOURCE / "runtime", root / "runtime",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv"))
    shutil.copyfile(SOURCE / "knowledge.py", root / "knowledge.py")
    (root / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: doctor-fixture\n"
        "code_root: ../main\nmodules: []\n",
        encoding="utf-8",
    )
    (root / "docs-raw").mkdir()
    (root / "governance").mkdir()
    (root / "governance/sources.lock.yaml").write_text(
        "schema_version: '2.0'\nresources: []\nsnapshots: []\n", encoding="utf-8"
    )
    return root


def observe(root, *, no_site=False, site_packages=None, python=sys.executable):
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    command = [str(python), "-B"] + (["-S"] if no_site else [])
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    environment.pop("PYTHONPATH", None)
    arguments = [str(root / "knowledge.py"), "doctor", "--knowledge-root", str(root), "--json"]
    if site_packages is not None:
        launcher = ("import runpy, sys; sys.path.append(sys.argv[1]); "
                    "sys.argv = sys.argv[2:]; runpy.run_path(sys.argv[0], run_name='__main__')")
        arguments = ["-c", launcher, str(site_packages), *arguments]
    result = subprocess.run([*command, *arguments],
                            cwd=root, capture_output=True, encoding="utf-8", env=environment, timeout=60)
    assert "Traceback" not in result.stderr, result.stderr
    report = json.loads(result.stdout)
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not (root / ".build").exists()
    return result.returncode, report


def blocked(root, code):
    status, report = observe(root)
    assert status == 3, report
    assert report["status"] == "blocked"
    assert code in {row["code"] for row in report["diagnostics"]}, report
    assert report["data"]["next_step"] != "Choose a knowledge task"
    return report


def mutate_lock(root, update):
    path = root / "runtime/governance/framework.lock.yaml"
    lock = yaml.safe_load(path.read_bytes())
    update(lock)
    path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    seal_rules(root)


def seal_rules(root):
    """Model an issued lock when testing the framework's own diagnostics."""
    path = root / "runtime/governance/framework.lock.yaml"
    manifest_path = root / "runtime/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["assets"]["runtime/governance/framework.lock.yaml"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_doctor_ready_includes_verified_rule_version_and_exact_workspace(knowledge):
    # Business data is intentionally invalid. Doctor must not load or parse it.
    (knowledge / "knowledge").mkdir()
    (knowledge / "knowledge/broken.md").write_text("not a card", encoding="utf-8")
    (knowledge / "docs-raw/unreadable-as-yaml.md").write_bytes(b"\xff\x00")
    status, report = observe(knowledge)
    assert status == 0, report
    rules = yaml.safe_load((knowledge / "runtime/governance/framework.lock.yaml").read_bytes())
    data = report["data"]
    assert Path(data["rules_lock"]) == knowledge / "runtime/governance/framework.lock.yaml"
    assert data["rules"]["status"] == "verified"
    assert data["rules"]["tool_version"] == rules["tool_version"]
    assert data["rules"]["schema_version"] == rules["schema_version"]
    assert data["rules"]["contract_family"] == rules["contract_family"]
    assert data["rules_digest"] == hashlib.sha256((knowledge / "runtime/governance/framework.lock.yaml").read_bytes()).hexdigest()
    assert data["rules"]["files_verified"] == len(rules["files"])
    assert data["config_path"] == str(knowledge / "config.yml")
    assert data["configuration"]["knowledge_root"] == str(knowledge.resolve())
    assert data["content_checked"] is False
    assert not (knowledge.parent / "main").exists()


@pytest.mark.parametrize("selection", ["base", "legacy", "explicit", "linked"])
def test_doctor_uses_the_invoked_python(knowledge, selection):
    (knowledge / ".install.json").write_text('{"package":"@himate/knowledge-cli"}', encoding="utf-8")
    base_python = Path(sys._base_executable)
    legacy = knowledge / ".venv"
    executable = Path("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if selection == "legacy":
        subprocess.run([str(base_python), "-I", "-m", "venv", "--without-pip", str(legacy)],
                       check=True, capture_output=True, timeout=30)

    invoked = base_python
    if selection in {"explicit", "linked"}:
        external = knowledge.parent / "explicit-venv"
        subprocess.run([str(base_python), "-I", "-m", "venv", "--without-pip", str(external)],
                       check=True, capture_output=True, timeout=30)
        if selection == "explicit":
            invoked = external / executable
        else:
            try:
                legacy.symlink_to(external, target_is_directory=True)
            except OSError as error:
                pytest.skip(f"Directory symlinks are unavailable: {error}")

    _, report = observe(knowledge, python=invoked)

    assert Path(report["data"]["python"]) == invoked
    if selection == "explicit":
        assert "YAML_PARSER_UNAVAILABLE" in {row["code"] for row in report["diagnostics"]}
    assert legacy.exists() == (selection in {"legacy", "linked"})


@pytest.mark.parametrize("domain", ["bluetooth", "embedded-audio"])
def test_doctor_uses_local_config_regardless_of_domain_directory(knowledge, domain):
    renamed = knowledge.with_name(domain)
    knowledge.rename(renamed)

    status, report = observe(renamed)

    assert status == 0, report
    assert report["data"]["config_path"] == str(renamed / "config.yml")
    assert report["data"]["configuration"]["knowledge_root"] == str(renamed.resolve())


def test_doctor_rejects_project_mapping_in_the_local_config(knowledge):
    config = knowledge / "config.yml"
    value = yaml.safe_load(config.read_bytes())
    value["knowledge_roots"] = {"bluetooth": knowledge.name}
    config.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    blocked(knowledge, "CONFIG_INVALID")


def test_doctor_blocks_missing_governance_lock(knowledge):
    (knowledge / "runtime/governance/framework.lock.yaml").unlink()
    blocked(knowledge, "RULE_LOCK_UNAVAILABLE")


def test_doctor_rejects_a_framework_lock_changed_since_release(knowledge):
    with (knowledge / "runtime/governance/framework.lock.yaml").open("ab") as stream:
        stream.write(b"\n# local change\n")
    blocked(knowledge, "RULE_LOCK_DIGEST_MISMATCH")


@pytest.mark.parametrize("raw", ["files: [broken\n", "schema_version: '2.0'\nschema_version: '2.0'\n"])
def test_doctor_blocks_malformed_or_duplicate_lock(knowledge, raw):
    (knowledge / "runtime/governance/framework.lock.yaml").write_text(raw, encoding="utf-8")
    seal_rules(knowledge)
    blocked(knowledge, "RULE_LOCK_INVALID")


@pytest.mark.parametrize("key,value", [("schema_version", "99.0"), ("contract_family", "other-group"),
                                       ("tool_version", "")])
def test_doctor_and_business_command_reject_incompatible_rule_metadata(knowledge, key, value):
    mutate_lock(knowledge, lambda lock: lock.update({key: value}))
    assert_rule_diagnostic(knowledge, "RULE_CONTRACT_UNSUPPORTED")


def assert_rule_diagnostic(knowledge, code):
    blocked(knowledge, code)
    result = subprocess.run([sys.executable, "-B", str(knowledge / "knowledge.py"), "maintain", "reindex",
                             "--knowledge-root", str(knowledge), "--json"], cwd=knowledge,
                            capture_output=True, encoding="utf-8", timeout=60)
    report = json.loads(result.stdout)
    assert result.returncode == 2, report
    assert report["diagnostics"][0]["code"] == code, report
    assert not (knowledge / ".build").exists()


def test_doctor_blocks_missing_registered_rule(knowledge):
    (knowledge / "runtime/governance/contracts/knowledge.py").unlink()
    blocked(knowledge, "RULE_FILE_UNAVAILABLE")


def test_doctor_does_not_execute_mismatched_governance(knowledge):
    marker = knowledge.parent / "unverified-domain-executed"
    (knowledge / "runtime/governance/contracts/__init__.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n", encoding="utf-8")
    blocked(knowledge, "RULE_FILE_DIGEST_MISMATCH")
    assert not marker.exists()


def test_doctor_never_executes_a_metadata_selector_with_unverified_bytes(knowledge):
    marker = knowledge.parent / "unverified-selector-executed"
    (knowledge / "runtime/governance/contracts/workspace_config.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n", encoding="utf-8")
    report = blocked(knowledge, "RULE_FILE_DIGEST_MISMATCH")
    assert report["data"]["configuration"]["status"] == "not_checked"
    assert not marker.exists()


def test_doctor_blocks_empty_rule_manifest(knowledge):
    mutate_lock(knowledge, lambda lock: lock.update(files={}))
    blocked(knowledge, "RULE_LOCK_INCOMPLETE")


def test_doctor_and_business_command_reject_unregistered_domain_dependency(knowledge):
    mutate_lock(knowledge, lambda lock: lock["files"].pop("contracts/panel.py"))
    assert_rule_diagnostic(knowledge, "RULE_LOCK_INCOMPLETE")


def test_doctor_blocks_unsupported_rule_capability(knowledge):
    mutate_lock(knowledge, lambda lock: lock["capabilities"].update(checks="99.0"))
    blocked(knowledge, "RULE_CAPABILITY_UNSUPPORTED")


def test_doctor_does_not_use_ancestor_configuration_when_local_config_is_missing(knowledge):
    (knowledge / "config.yml").unlink()
    (knowledge.parent / "config.yml").write_text(
        f"schema_version: '2.0'\nknowledge_roots:\n  wifi: {knowledge.name}\n", encoding="utf-8")
    blocked(knowledge, "CONFIG_UNAVAILABLE")


def test_doctor_skips_invalid_ancestor_configuration(knowledge):
    (knowledge.parent / "config.yml").write_text("knowledge_roots: [broken\n", encoding="utf-8")
    status, report = observe(knowledge)
    assert status == 0, report
    assert report["data"]["config_path"] == str(knowledge / "config.yml")


def test_doctor_blocks_missing_configuration(knowledge):
    (knowledge / "config.yml").unlink()
    blocked(knowledge, "CONFIG_UNAVAILABLE")


@pytest.mark.parametrize("raw", ["knowledge_roots: [broken\n", "schema_version: '2.0'\nknowledge_roots: {}\nknowledge_roots: {}\n"])
def test_doctor_blocks_bad_or_duplicate_configuration(knowledge, raw):
    (knowledge / "config.yml").write_text(raw, encoding="utf-8")
    blocked(knowledge, "CONFIG_INVALID")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
def test_doctor_rejects_nonregular_local_configuration(knowledge):
    config = knowledge / "config.yml"
    config.unlink()
    os.mkfifo(config)
    blocked(knowledge, "CONFIG_INVALID")


def test_doctor_without_site_packages_still_reports_pinned_dependencies(knowledge):
    status, report = observe(knowledge, no_site=True)
    assert status == 3, report
    assert report["status"] == "blocked"
    assert "DEPENDENCY_UNAVAILABLE" in {row["code"] for row in report["diagnostics"]}
    assert any(row["name"].casefold() == "pyyaml" and row["actual"] is None for row in report["data"]["dependencies"])
    assert report["data"]["rules"]["status"] == "not_checked"


def nested_knowledge(knowledge):
    workspace = knowledge.parent
    target = workspace / "himate/domain"
    target.parent.mkdir()
    shutil.move(str(knowledge), str(target))
    config = target / "config.yml"
    config.write_text(config.read_text(encoding="utf-8").replace(
        "code_root: ../main", "code_root: ../../main").replace(
        "modules: []", "modules:\n- path: wifi\n  chips: []\n  sides: []\n  features: []"), encoding="utf-8")
    code = workspace / "main/wifi/config.c"
    code.parent.mkdir(parents=True)
    code.write_text("int selected_config(void) { return 7; }\n", encoding="utf-8")
    return target, config




def test_doctor_chooses_nested_knowledge_configuration_over_legacy_mapping(knowledge):
    root, config = nested_knowledge(knowledge)
    (root.parent / "config.yml").write_text(
        "schema_version: '2.0'\nknowledge_roots:\n  wifi: domain\n", encoding="utf-8")
    status, report = observe(root)
    assert status == 0, report
    assert report["data"]["config_path"] == str(config)


def test_doctor_uses_local_config_in_a_non_git_manifest(knowledge):
    root, config = nested_knowledge(knowledge)
    original = config.read_bytes()
    assert not (root.parents[1] / ".git").exists()
    assert not (root / ".git").exists()

    status, report = observe(root)

    assert status == 0, report
    assert report["data"]["config_path"] == str(config)
    assert config.read_bytes() == original


@pytest.mark.parametrize("state,doctor_code", [
    ("invalid", "CONFIG_INVALID"),
    ("duplicate", "CONFIG_INVALID"),
    ("unsafe", "CONFIG_KNOWLEDGE_ROOT_MISMATCH"),
    ("case_alias", "CONFIG_KNOWLEDGE_ROOT_MISMATCH"),
    ("missing", "CONFIG_UNAVAILABLE"),
])
def test_doctor_fails_closed_on_bad_nested_discovery(knowledge, state, doctor_code):
    root, config = nested_knowledge(knowledge)
    original = config.read_text(encoding="utf-8")
    if state == "invalid":
        config.write_text("modules: [broken\n", encoding="utf-8")
    elif state == "duplicate":
        config.write_text(original + "modules: []\n", encoding="utf-8")
    elif state == "unsafe":
        config.write_text(original.replace("../../main", "../../main/../outside"), encoding="utf-8")
    elif state == "case_alias":
        config.rename(config.with_name("CONFIG.yml"))
    else:
        config.unlink()
    blocked(root, doctor_code)


@pytest.mark.parametrize("version", [None, "99.0"])
def test_doctor_cannot_mark_a_noncurrent_workspace_contract_ready(knowledge, version):
    config = knowledge / "config.yml"
    value = yaml.safe_load(config.read_bytes())
    if version is None:
        value.pop("schema_version")
    else:
        value["schema_version"] = version
    config.write_text(yaml.safe_dump(value), encoding="utf-8")
    blocked(knowledge, "CONFIG_INVALID")


def test_doctor_never_imports_the_governance_package_even_when_its_bytes_are_locked(knowledge):
    # Explicit synthetic rule version: metadata selection must not run this
    # package initializer or load any business engine, even after verification.
    marker = knowledge.parent / "governance-package-imported"
    package = knowledge / "runtime/governance/contracts/__init__.py"
    package.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n", encoding="utf-8")
    mutate_lock(knowledge, lambda lock: lock["files"]["contracts/__init__.py"].update(
        sha256=hashlib.sha256(package.read_bytes()).hexdigest()))
    status, report = observe(knowledge)
    assert status == 0, report
    assert not marker.exists()


def test_doctor_checks_only_dependencies_for_the_current_python_and_platform(knowledge):
    lock = knowledge / "runtime/requirements.lock.txt"
    with lock.open("a", encoding="utf-8") as stream:
        stream.write('\nnonexistent-other-platform-dependency==1.0 ; python_version < "2.0"\n')
    # The fixture explicitly installs a new, trusted runtime release containing
    # the synthetic dependency condition. The command must still be read-only.
    manifest_path = knowledge / "runtime/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["requirements.lock.txt"]["sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    status, report = observe(knowledge)
    assert status == 0, report
    assert all(row["name"] != "nonexistent-other-platform-dependency" for row in report["data"]["dependencies"])


@pytest.mark.parametrize("version,ready", [
    ("1.2.3+cpu", True), ("1.2.3+vendor.7", True),
    ("1.2.4", False), ("not-a-version", False),
])
def test_doctor_matches_installed_distribution_versions_like_pip(knowledge, version, ready):
    # A real distribution metadata record is sufficient; no package code is
    # imported or installed to test the execution host's version matching.
    site = knowledge.parent / "synthetic-site-packages"
    distribution = site / "sample_library-0.dist-info"
    distribution.mkdir(parents=True)
    (distribution / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: sample-library\nVersion: " + version + "\n",
        encoding="utf-8",
    )
    lock = knowledge / "runtime/requirements.lock.txt"
    with lock.open("a", encoding="utf-8") as stream:
        stream.write("\nsample-library==1.2.3\n")
    manifest_path = knowledge / "runtime/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["requirements.lock.txt"]["sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    status, report = observe(knowledge, site_packages=site)
    dependency = next(row for row in report["data"]["dependencies"] if row["name"] == "sample-library")
    assert dependency == {"name": "sample-library", "expected": "1.2.3", "actual": version}
    assert status == (0 if ready else 3), report
    assert report["status"] == ("ok" if ready else "blocked"), report
    if not ready:
        assert {"code": "DEPENDENCY_UNAVAILABLE", "message": "sample-library requires 1.2.3"} in report["diagnostics"]
