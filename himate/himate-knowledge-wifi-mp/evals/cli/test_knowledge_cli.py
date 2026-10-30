"""Public repository CLI behavior; no installed Skill code is available."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[4]
KNOWLEDGE = REPOSITORY / "himate/himate-knowledge-wifi-mp"


def isolated_knowledge(destination):
    root = destination / "himate-knowledge-synthetic"
    root.mkdir(parents=True)
    (destination / "config.yml").write_text(
        "schema_version: '2.0'\ncode_root: main\nmodules: []\nknowledge_roots:\n  wifi: himate-knowledge-synthetic\n",
        encoding="utf-8",
    )
    shutil.copytree(KNOWLEDGE / "governance", root / "governance",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("knowledge.py", "knowledge.sh", "knowledge.cmd", "runtime"):
        source = KNOWLEDGE / name
        if source.is_dir():
            shutil.copytree(source, root / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif source.is_file():
            shutil.copyfile(source, root / name)
    return root


def call(root, *arguments, cwd=None, stdin=None, environment=None):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env.pop("PYTHONPATH", None)
    if environment:
        env.update(environment)
    return subprocess.run([sys.executable, "-B", str(root / "knowledge.py"), *arguments],
                          cwd=cwd or root, input=stdin, capture_output=True,
                          encoding="utf-8", env=env, timeout=60)


def test_doctor_can_inspect_isolated_knowledge_without_installed_skills(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge workspace")
    result = call(root, "doctor", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["phase"] == "ready"
    assert report["data"]["knowledge_root"] == str(root.resolve())
    assert report["data"]["executor"] == "knowledge-cli"
    assert not (root.parent / "skills").exists()
    assert not (root / ".build").exists()


def test_invalid_command_keeps_the_json_error_contract(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    result = call(root, "does-not-exist", "--json")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["diagnostics"][0]["code"] == "INVALID_ARGUMENT"
    assert not (root / ".build").exists()


def test_read_shortcut_requires_an_exact_search_receipt(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    result = call(root, "read", "example", "--json")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["diagnostics"][0]["code"] == "SEARCH_RECEIPT_REQUIRED"
    assert not (root / ".build").exists()


@pytest.mark.parametrize("raw, code", [
    ('{"operation_id":"one","operation_id":"two"}', "DUPLICATE_KEY"),
    ('{"operation_id":"../../other"}', "INVALID_ID"),
    ('{"query":NaN}', "INVALID_JSON"),
    ('[]', "INVALID_REQUEST"),
])
def test_invalid_request_never_starts_an_operation(tmp_path, raw, code):
    root = isolated_knowledge(tmp_path / "knowledge")
    result = call(root, "source", "scan", "--input", "-", "--json", stdin=raw)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == code
    assert not (root / ".build").exists()


def test_modified_runtime_is_rejected_before_it_can_execute(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    marker = tmp_path / "untrusted-code-executed"
    (root / "runtime/himate_knowledge/cli.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n",
        encoding="utf-8",
    )
    result = call(root, "doctor", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "RUNTIME_UNAVAILABLE"
    assert not marker.exists()


def test_bootstrap_error_cannot_create_a_formal_publication(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    (root / "runtime/manifest.json").write_text("{}", encoding="utf-8")
    formal = root / "logs/publications/other/manifest.json"
    result = call(root, "doctor", "--output", str(formal), "--json")
    assert result.returncode == 2
    assert not formal.exists()


@pytest.mark.parametrize("command, words", [("read", ["example", "--receipt", "x.json"]), ("status", ["example"])])
def test_shortcut_action_conflicts_are_rejected(tmp_path, command, words):
    root = isolated_knowledge(tmp_path / "knowledge")
    result = call(root, command, *words, "--action", "different", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "ARGUMENT_CONFLICT"
    assert not (root / ".build").exists()


def test_command_registration_follows_the_current_knowledge_group(tmp_path):
    first = isolated_knowledge(tmp_path / "WiFi 5X 知识")
    second = isolated_knowledge(tmp_path / "WiFi 0X 知识")
    destination = tmp_path / "machine commands"
    installed = call(first, "install-command", "--bin-dir", str(destination), "--json")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    dispatcher = destination / "knowledge-dispatch.py"
    for root in (first, second):
        nested = root / "docs-llm-wiki/nested"
        nested.mkdir(parents=True)
        result = subprocess.run([sys.executable, str(dispatcher), "doctor", "--json"],
                                cwd=nested, capture_output=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["data"]["knowledge_root"] == str(root.resolve())
    before = {p.name: p.read_bytes() for p in destination.iterdir()}
    repeated = call(first, "install-command", "--bin-dir", str(destination), "--json")
    assert repeated.returncode == 2
    assert json.loads(repeated.stdout)["diagnostics"][0]["code"] == "COMMAND_EXISTS"
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == before


def test_explicit_root_restarts_its_own_runtime(tmp_path):
    first = isolated_knowledge(tmp_path / "first")
    second = isolated_knowledge(tmp_path / "second")
    result = call(first, "doctor", "--knowledge-root", str(second), "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["data"]["knowledge_root"] == str(second.resolve())


def test_output_cannot_replace_an_existing_file(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    original = tmp_path / "existing.json"
    original.write_bytes(b"private original")
    result = call(root, "query", "marker", "--output", str(original), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_EXISTS"
    assert original.read_bytes() == b"private original"


def test_doctor_reports_missing_dependency_without_installing_or_scanning(tmp_path):
    root = isolated_knowledge(tmp_path / "knowledge")
    lock = root / "runtime/requirements.lock.txt"
    lock.write_text("himate-synthetic-missing-dependency==1.0.0\n", encoding="utf-8")
    # This is an intentionally different synthetic runtime, not repair of a
    # failed acceptance candidate. Keep its changed version explicit.
    import hashlib
    manifest = root / "runtime/manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["version"] = "synthetic-missing-dependency"
    value["files"]["requirements.lock.txt"]["sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(value), encoding="utf-8")
    result = call(root, "doctor", "--json")
    assert result.returncode == 3
    report = json.loads(result.stdout)
    assert report["status"] == "blocked"
    assert report["diagnostics"][0]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert report["data"]["dependencies"][0]["actual"] is None
    assert not (root / ".build").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows command launcher")
def test_windows_launcher_uses_the_prepared_interpreter_with_unicode_paths(tmp_path):
    root = isolated_knowledge(tmp_path / "WiFi 5X 知识")
    env = dict(os.environ, HIMATE_KNOWLEDGE_PYTHON=sys.executable,
               PYTHONIOENCODING="cp1252")
    # cmd uses its own /s /c quote rules, rather than the CRT argv convention.
    command = ('"' + os.environ.get("COMSPEC", "cmd.exe") + '" /d /s /c ""' +
               str(root / "knowledge.cmd") + '" doctor --json"')
    result = subprocess.run(command,
                            cwd=root, capture_output=True, encoding="utf-8", env=env, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["data"]["knowledge_root"] == str(root.resolve())


@pytest.mark.parametrize("module, command", [("hashlib", "doctor"), ("yaml", "source")])
def test_unmanifested_adjacent_modules_are_never_executed(tmp_path, module, command):
    root = isolated_knowledge(tmp_path / "workspace")
    marker = tmp_path / "unmanifested-module-executed"
    (root / (module + ".py")).write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\nraise RuntimeError('unmanifested code')\n",
        encoding="utf-8",
    )
    result = call(root, command, *( ["scan"] if command == "source" else []), "--json")
    assert not marker.exists(), result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("reference", [
    ".build/operations/other/cli/new.json",
    "logs/publications/other/manifest.json",
    "artifacts/indexes/local/active.json",
])
def test_new_cli_output_cannot_write_another_operation_or_formal_asset(tmp_path, reference):
    root = isolated_knowledge(tmp_path / "workspace")
    output = root / reference
    result = call(root, "query", "marker", "--operation-id", "current", "--output", str(output), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_OPERATION"
    assert not output.exists()


def test_explicit_external_output_cannot_write_into_another_knowledge_root(tmp_path):
    first = isolated_knowledge(tmp_path / "first")
    second = isolated_knowledge(tmp_path / "second")
    output = second / "knowledge/new-card.json"
    result = call(first, "status", "unknown-operation", "--operation-id", "current",
                  "--output", str(output), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_OPERATION"
    assert not output.exists()


def test_external_output_also_protects_a_legacy_knowledge_root(tmp_path):
    first = isolated_knowledge(tmp_path / "first")
    second = isolated_knowledge(tmp_path / "legacy")
    (second / "knowledge.py").unlink()
    output = second / "knowledge/new-card.json"
    result = call(first, "status", "unknown-operation", "--operation-id", "current",
                  "--output", str(output), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_OPERATION"
    assert not output.exists()


def test_unverified_runtime_only_reports_on_stdout_and_preserves_other_roots(tmp_path):
    first = isolated_knowledge(tmp_path / "first")
    second = isolated_knowledge(tmp_path / "second")
    (first / "runtime/manifest.json").write_text("{}", encoding="utf-8")
    output = second / "knowledge/new-card.json"
    result = call(first, "doctor", "--output", str(output), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "RUNTIME_UNAVAILABLE"
    assert not output.exists()


@pytest.mark.parametrize("reference", ["knowledge", "governance/contracts"])
def test_command_registration_cannot_write_inside_a_knowledge_root(tmp_path, reference):
    root = isolated_knowledge(tmp_path / "workspace")
    destination = root / reference
    result = call(root, "install-command", "--bin-dir", str(destination), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "COMMAND_INSIDE_KNOWLEDGE"
    assert not (destination / "knowledge-dispatch.py").exists()


@pytest.mark.parametrize("legacy", [False, True])
def test_registration_also_protects_other_and_legacy_knowledge_roots(tmp_path, legacy):
    first = isolated_knowledge(tmp_path / "first")
    second = isolated_knowledge(tmp_path / "other")
    if legacy:
        (second / "knowledge.py").unlink()
    destination = second / "tools/bin"
    result = call(first, "install-command", "--bin-dir", str(destination), "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "COMMAND_INSIDE_KNOWLEDGE"
    assert not destination.exists()


def test_human_output_exposes_the_exact_default_transport_paths(tmp_path):
    root = isolated_knowledge(tmp_path / "workspace")
    result = call(root, "status", "unknown-operation", "--operation-id", "show-paths")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "request_ref:" in result.stdout
    assert "result_ref:" in result.stdout
    assert ".build/operations/show-paths/cli/" in result.stdout
