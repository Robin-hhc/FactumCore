"""Real Git ownership simulation and explicit historical code encodings.

Repositories here are isolated synthetic test inputs, never production sources.
Git itself evaluates ownership via GIT_TEST_ASSUME_DIFFERENT_OWNER; no Git result
is mocked or replaced.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("wifi_real_compat", DOMAIN / "governance/contracts/__init__.py", submodule_search_locations=[str(DOMAIN / "governance/contracts")])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from wifi_real_compat import source_resources, validation as v  # noqa: E402


def test_exact_configured_git_original_survives_different_repository_owner(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    knowledge = repository / "himate/himate-knowledge-wifi-mp"
    raw_path = knowledge / "docs-raw/protocols/input.txt"
    knowledge_relative = knowledge.relative_to(repository).as_posix()
    raw_relative = raw_path.relative_to(repository).as_posix()
    raw_path.parent.mkdir(parents=True)
    raw = b"Immutable registered original.\n"
    raw_path.write_bytes(raw)
    (repository / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": knowledge_relative}}), encoding="utf-8")

    def git(*arguments):
        return subprocess.check_output(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(repository), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("add", "config.yml", raw_relative)
    git("-c", "user.name=Isolated fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Isolated original fixture")
    head = git("rev-parse", "HEAD")
    forced = dict(os.environ, GIT_TEST_ASSUME_DIFFERENT_OWNER="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    refused = subprocess.run(["git", "-C", str(repository), "rev-parse", "HEAD"], env=forced, capture_output=True)
    assert refused.returncode != 0 and b"dubious ownership" in refused.stderr

    # The stricter Git test flag is preserved, while config/path injection
    # variables remain sanitized. Every command executes real Git objects.
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    snapshot = {"snapshot_id": "raw:fixture", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "recovery": {"kind": "git", "commit": head, "path": raw_relative}}
    assert source_resources.recover_snapshot(knowledge, snapshot, allow_local_fallback=False) == raw
    assert raw_path.read_bytes() == raw
    # Exact Git root checks still reject a configured directory inside a repo.
    nested = repository / "nested"
    nested.mkdir()
    (repository / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": knowledge_relative}, "repos": [{"repo_id": "nested", "root": str(nested)}]}), encoding="utf-8")
    snapshot["recovery"].update(repo_id="nested", path="input.txt")
    with pytest.raises(v.ContractError):
        source_resources.recover_snapshot(knowledge, snapshot, allow_local_fallback=False)


def test_fixed_gb18030_line_reference_validates_original_bytes_without_cache():
    raw = b"// \xbd\xd3\xca\xd5\xbe\xdb\xba\xcf\xd6\xa1\nint receive(void) { return 1; }\n"
    text = "// 接收聚合帧\nint receive(void) { return 1; }\n"
    addresses = [{"kind": "lines", "start": 1, "end": 1, "text": "// 接收聚合帧"},
                 {"kind": "lines", "start": 2, "end": 2, "text": "int receive(void) { return 1; }"}]
    snapshot = {"source_id": "code", "snapshot_id": "code:gb", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "extraction": {"extractor": "code-gb18030:1", "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                               "locator_sha256": hashlib.sha256(v.canonical_bytes({"locators": addresses})).hexdigest()}}
    lock = {"resources": [{"source_id": "code", "kind": "code"}], "snapshots": [snapshot]}
    ref = {"evidence_ref": "e1", "source_id": "code", "snapshot_id": "code:gb", "locator": {"kind": "lines", "start": 1, "end": 2}}
    assert source_resources.validate_reference(ref, lock, lambda _: raw)["snapshot_id"] == "code:gb"
    snapshot["extraction"]["text_sha256"] = "0" * 64
    with pytest.raises(v.ContractError, match="fingerprint"):
        source_resources.validate_reference(ref, lock, lambda _: raw)
