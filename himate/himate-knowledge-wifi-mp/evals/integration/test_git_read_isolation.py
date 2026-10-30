"""Local history reads never invoke repository-configured signature programs."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest
import yaml


DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "wifi_git_read_isolation",
    DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)
from wifi_git_read_isolation import checks, source_resources  # noqa: E402


def historical_card():
    profiles = yaml.safe_load((DOMAIN / "governance/schemas/profiles.yaml").read_bytes())
    metadata = {
        "schema_version": "2.0", "id": "historical-card", "profile": "entity",
        "title": "Synthetic historical card", "summary": "Exact historical bytes",
        "lifecycle": "stable", "review_mode": "manual_document", "owner": "fixture",
        "aliases": [], "scope": {"applicability": "unknown", "contexts": []},
        "sources": [{"evidence_ref": "e1", "source_id": "synthetic",
                     "snapshot_id": "raw:synthetic", "locator": {"kind": "lines", "start": 1, "end": 1}}],
        "claims": [{"id": "c1", "text_ref": "#c1", "evidence_kind": "design",
                    "source_refs": ["e1"], "context_ids": [], "usage": "guidance",
                    "verification_requirements": []}],
        "relations": [],
    }
    body = '<a id="c1"></a>\nSynthetic historical claim.\n'
    body += "\n".join("## " + title + "\nSynthetic section.\n"
                      for title in profiles["profiles"]["entity"]["required_sections"])
    raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n" + body).encode("utf-8")
    rules = {
        "schemas": {"card": json.loads((DOMAIN / "governance/schemas/frontmatter.schema.json").read_bytes())},
        "profiles": profiles,
    }
    return raw, rules


@pytest.fixture
def signed_repository(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    knowledge = repository / "knowledge-root"
    card_path = "knowledge/concepts/entities/historical-card.md"
    card = knowledge / card_path
    card.parent.mkdir(parents=True)
    raw, rules = historical_card()
    card.write_bytes(raw)
    (repository / "config.yml").write_text(
        yaml.safe_dump({"knowledge_roots": {"wifi": knowledge.name}}), encoding="utf-8"
    )
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")

    def git(*arguments, data=None):
        command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                   "-c", "core.hooksPath=" + os.devnull, "-c", "core.pager=cat",
                   "-c", "safe.directory=" + repository.as_posix(), "-C", str(repository), *arguments]
        result = subprocess.run(command, input=data, capture_output=True, env=environment, timeout=15)
        assert result.returncode == 0, result.stderr
        return result.stdout

    git("init", "-b", "main")
    git("config", "core.autocrlf", "false")
    git("add", ".")
    git("-c", "user.name=Synthetic fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgSign=false", "commit", "-m", "Synthetic history")
    # An intentionally invalid signature is sufficient to exercise Git's
    # verifier dispatch; this fixture neither needs keys nor runs real GPG.
    headers, message = git("cat-file", "commit", "HEAD").split(b"\n\n", 1)
    signed = (headers + b"\ngpgsig -----BEGIN PGP SIGNATURE-----\n \n synthetic\n"
              b" -----END PGP SIGNATURE-----\n\n" + message)
    revision = git("hash-object", "-t", "commit", "-w", "--stdin", data=signed).strip().decode("ascii")
    git("update-ref", "HEAD", revision)
    marker = repository / "SIGNATURE_PROGRAM_INVOKED"
    program = repository / ("signature-probe.cmd" if os.name == "nt" else "signature-probe.sh")
    if os.name == "nt":
        program.write_bytes(b'@echo off\r\n> "%~dp0SIGNATURE_PROGRAM_INVOKED" echo invoked\r\nexit /b 1\r\n')
    else:
        program.write_text("#!/bin/sh\nprintf invoked > " + shlex.quote(str(marker)) + "\nexit 1\n", encoding="utf-8")
        program.chmod(0o700)
    git("config", "log.showSignature", "true")
    git("config", "gpg.program", program.as_posix())
    # Positive control proves the harmless external verifier would execute
    # under this exact repository configuration without the read isolation.
    git("log", "--format=%H", "-1")
    assert marker.is_file(), "Synthetic verifier was not exercised by the control"
    marker.unlink()
    return repository, knowledge, card_path, raw, rules, revision, marker


@pytest.mark.parametrize("reader", ["source_history", "record_history"])
def test_history_reads_disable_repository_signature_programs(signed_repository, reader):
    repository, knowledge, card_path, raw, rules, revision, marker = signed_repository
    if reader == "source_history":
        history = source_resources._git_read(
            repository, "log", "--format=%H", "--max-count=1001", "HEAD", "--", "knowledge-root/knowledge"
        )
        assert history.decode("ascii").splitlines() == [revision]
    else:
        # Supply no current card or archive: successful resolution must read
        # the historical Git object and recover the exact requested bytes.
        resolver = checks._record_resolver({}, rules, {}, knowledge, {"commit": revision})
        recovered = resolver({"card_id": "historical-card", "path": card_path,
                              "sha256": hashlib.sha256(raw).hexdigest()}, {})
        assert recovered["raw"] == raw
        assert recovered["path"] == card_path
    assert not marker.exists(), "Read-only history invoked a repository-configured verifier"
