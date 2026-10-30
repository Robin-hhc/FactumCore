"""Doctor validates installation metadata without executing domain programs."""

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
    for name in ("governance", "runtime"):
        shutil.copytree(SOURCE / name, root / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        shutil.copyfile(SOURCE / name, root / name)
    (workspace / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: doctor-fixture\n"
        "knowledge_roots:\n  wifi: himate-knowledge-synthetic\ncode_root: main\nmodules: []\n",
        encoding="utf-8",
    )
    return root


def observe(root, *, no_site=False):
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    command = [sys.executable, "-B"] + (["-S"] if no_site else [])
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    environment.pop("PYTHONPATH", None)
    result = subprocess.run([*command, str(root / "knowledge.py"), "doctor", "--json"],
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
    path = root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(path.read_bytes())
    update(lock)
    # An intentionally invalid diagnostic input; no digest is repaired.
    path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")


def test_doctor_ready_includes_verified_rule_version_and_exact_workspace(knowledge):
    # Business data is intentionally invalid. Doctor must not load or parse it.
    (knowledge / "knowledge").mkdir()
    (knowledge / "knowledge/broken.md").write_text("not a card", encoding="utf-8")
    (knowledge / "docs-raw").mkdir()
    (knowledge / "docs-raw/unreadable-as-yaml.md").write_bytes(b"\xff\x00")
    status, report = observe(knowledge)
    assert status == 0, report
    rules = yaml.safe_load((knowledge / "governance/framework.lock.yaml").read_bytes())
    data = report["data"]
    assert data["rules"]["status"] == "verified"
    assert data["rules"]["tool_version"] == rules["tool_version"]
    assert data["rules"]["schema_version"] == rules["schema_version"]
    assert data["rules"]["contract_family"] == rules["contract_family"]
    assert data["rules_digest"] == hashlib.sha256((knowledge / "governance/framework.lock.yaml").read_bytes()).hexdigest()
    assert data["rules"]["files_verified"] == len(rules["files"])
    assert data["config_path"] == str(knowledge.parent / "config.yml")
    assert data["configuration"]["knowledge_root"] == str(knowledge.resolve())
    assert data["content_checked"] is False
    assert not (knowledge.parent / "main").exists()


def test_doctor_blocks_missing_governance_lock(knowledge):
    (knowledge / "governance/framework.lock.yaml").unlink()
    blocked(knowledge, "RULE_LOCK_UNAVAILABLE")


@pytest.mark.parametrize("raw", ["files: [broken\n", "schema_version: '2.0'\nschema_version: '2.0'\n"])
def test_doctor_blocks_malformed_or_duplicate_lock(knowledge, raw):
    (knowledge / "governance/framework.lock.yaml").write_text(raw, encoding="utf-8")
    blocked(knowledge, "RULE_LOCK_INVALID")


@pytest.mark.parametrize("key,value", [("schema_version", "99.0"), ("contract_family", "other-group")])
def test_doctor_blocks_unsupported_contract(knowledge, key, value):
    mutate_lock(knowledge, lambda lock: lock.update({key: value}))
    blocked(knowledge, "RULE_CONTRACT_UNSUPPORTED")


def test_doctor_blocks_missing_registered_rule(knowledge):
    (knowledge / "governance/contracts/knowledge.py").unlink()
    blocked(knowledge, "RULE_FILE_UNAVAILABLE")


def test_doctor_does_not_execute_mismatched_governance(knowledge):
    marker = knowledge.parent / "unverified-domain-executed"
    (knowledge / "governance/contracts/__init__.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n", encoding="utf-8")
    blocked(knowledge, "RULE_FILE_DIGEST_MISMATCH")
    assert not marker.exists()


def test_doctor_blocks_empty_rule_manifest(knowledge):
    mutate_lock(knowledge, lambda lock: lock.update(files={}))
    blocked(knowledge, "RULE_LOCK_INCOMPLETE")


def test_doctor_blocks_unsupported_rule_capability(knowledge):
    mutate_lock(knowledge, lambda lock: lock["capabilities"].update(checks="99.0"))
    blocked(knowledge, "RULE_CAPABILITY_UNSUPPORTED")


def test_doctor_cannot_call_an_ancestor_other_group_configuration_ready(knowledge):
    (knowledge.parent / "config.yml").write_text(
        "schema_version: '2.0'\nknowledge_roots:\n  wifi: another-group\n", encoding="utf-8")
    blocked(knowledge, "CONFIG_KNOWLEDGE_ROOT_MISMATCH")


def test_doctor_does_not_skip_a_nearer_wrong_configuration(knowledge):
    (knowledge / "config.yml").write_text(
        "schema_version: '2.0'\nknowledge_roots:\n  wifi: unrelated\n", encoding="utf-8")
    blocked(knowledge, "CONFIG_KNOWLEDGE_ROOT_MISMATCH")


def test_doctor_blocks_missing_configuration(knowledge):
    (knowledge.parent / "config.yml").unlink()
    status, report = observe(knowledge)
    assert status == 3, report
    # A developer's outer workspace may itself contain another group's config;
    # it is an explicit mismatch, never an implicit fallback to ready.
    assert {row["code"] for row in report["diagnostics"]} & {"CONFIG_UNAVAILABLE", "CONFIG_KNOWLEDGE_ROOT_MISMATCH"}


@pytest.mark.parametrize("raw", ["knowledge_roots: [broken\n", "schema_version: '2.0'\nknowledge_roots: {}\nknowledge_roots: {}\n"])
def test_doctor_blocks_bad_or_duplicate_configuration(knowledge, raw):
    (knowledge.parent / "config.yml").write_text(raw, encoding="utf-8")
    blocked(knowledge, "CONFIG_INVALID")


def test_doctor_without_site_packages_still_reports_pinned_dependencies(knowledge):
    status, report = observe(knowledge, no_site=True)
    assert status == 3, report
    assert report["status"] == "blocked"
    assert "DEPENDENCY_UNAVAILABLE" in {row["code"] for row in report["diagnostics"]}
    assert any(row["name"].casefold() == "pyyaml" and row["actual"] is None for row in report["data"]["dependencies"])
    assert report["data"]["rules"]["status"] == "not_checked"
