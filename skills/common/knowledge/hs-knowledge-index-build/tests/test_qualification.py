"""Index provenance/publication seams; signed fixture data never claims real CI."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def load_node():
    scripts = Path(__file__).parents[1] / "scripts"
    previous = sys.modules.get("support")
    spec = importlib.util.spec_from_file_location("support", scripts / "support.py")
    support = importlib.util.module_from_spec(spec)
    sys.modules["support"] = support
    spec.loader.exec_module(support)
    try:
        spec = importlib.util.spec_from_file_location(
            "index_under_test", scripts / "node.py"
        )
        node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node)
    finally:
        if previous is None:
            sys.modules.pop("support", None)
        else:
            sys.modules["support"] = previous
    return node, support


def test_nonterminal_journal_is_a_snapshot_barrier(tmp_path):
    node, _ = load_node()
    journal = tmp_path / "logs/operations/other-op/journal.json"
    journal.parent.mkdir(parents=True)
    journal.write_text('{"status":"recovery_required"}', encoding="utf-8")
    ctx = SimpleNamespace(
        root=tmp_path, record=lambda ref, kind: {"status": "recovery_required"}
    )
    with pytest.raises(ValueError, match="transaction|journal|pending"):
        node.check_transactions(ctx)


def test_publication_git_reads_disable_lazy_fetch_and_protocols(tmp_path, monkeypatch):
    node, _ = load_node()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"fixed bytes")

    monkeypatch.setattr(node.subprocess, "run", run)
    assert (
        node.git_read(tmp_path, ["cat-file", "blob", "1" * 40 + ":card.md"])
        == b"fixed bytes"
    )
    command, kwargs = calls[0]
    assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert "protocol.allow=never" in command and "protocol.file.allow=never" in command
    assert "core.fsmonitor=false" in command
    with pytest.raises(ValueError, match="Git"):
        node.git_read(tmp_path, ["fetch", "untrusted"])


def signed_publication(tmp_path, card_digest="a" * 64):
    node, support = load_node()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    key = Ed25519PrivateKey.generate()
    root = tmp_path / "himate-knowledge-wifi-mp"
    root.mkdir()
    (root / ".isolated-knowledge-fixture").write_text(
        "HIMATE_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
    )
    card = {
        "path": "knowledge/rules/a.md",
        "sha256": card_digest,
        "metadata": {"id": "a", "review_mode": "manual_document"},
    }
    payload = {
        "card_digests": {card["path"]: card_digest},
        "rules_digest": "f" * 64,
        "knowledge_commit": "1" * 40,
    }

    def save_receipt():
        receipt = {
            "adapter_id": "fixture",
            "payload": payload,
            "signature_b64": base64.b64encode(
                key.sign(support.canonical(payload))
            ).decode(),
        }
        path = root / "logs/publication.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(support.canonical(receipt))

    trust = {
        "synthetic": True,
        "fixture_root": str(root),
        "public_key_b64": base64.b64encode(
            key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode(),
    }
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"publication_trust": {"fixture": trust}}), encoding="utf-8"
    )
    ctx = SimpleNamespace(
        root=root,
        args=SimpleNamespace(catalog=str(catalog), rules_digest="f" * 64),
        rules={},
        modules={
            "validation": SimpleNamespace(validate_shape=lambda *args: None),
            "source_resources": SimpleNamespace(
                validate_source_ref=lambda *args: None,
                read_source_lock=lambda *args: {"schema_version": "2.0", "resources": [], "snapshots": []},
            ),
        },
    )
    save_receipt()
    return node, support, ctx, card, payload, save_receipt


def test_receipt_metadata_cannot_substitute_for_a_real_git_commit(tmp_path):
    node, _, ctx, card, _, _ = signed_publication(tmp_path)
    with pytest.raises(ValueError, match="Git|commit|publication"):
        node.validate_publication(
            ctx, {"publication_receipt_ref": "logs/publication.json"}, [card]
        )


@pytest.mark.parametrize("change", ["bad-signature", "unknown-adapter", "missing-trust"])
def test_explicit_publication_receipt_requires_authentic_identity(tmp_path, change):
    node, _, ctx, card, _, _ = signed_publication(tmp_path)
    receipt = ctx.root / "logs/publication.json"
    value = json.loads(receipt.read_bytes())
    if change == "bad-signature":
        value["signature_b64"] = base64.b64encode(b"invalid").decode()
    elif change == "unknown-adapter":
        value["adapter_id"] = "unknown"
    else:
        ctx.args.catalog = None
    receipt.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        node.validate_publication(ctx, {"publication_receipt_ref": "logs/publication.json"}, [card])
    assert getattr(error.value, "code", None) == (
        "PUBLICATION_SIGNATURE_INVALID" if change == "bad-signature" else "UNTRUSTED_PUBLICATION"
    )


def test_repository_snapshot_must_match_actual_committed_card_bytes(tmp_path):
    node, support, ctx, card, payload, save_receipt = signed_publication(tmp_path)

    def git(*args):
        return (
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=" + os.devnull,
                    "-C",
                    str(tmp_path),
                    *args,
                ],
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .strip()
        )

    git("init", "--initial-branch=main", "-q")
    target = ctx.root / card["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"actual committed card\n")
    lock = ctx.root / "governance/framework.lock.yaml"
    lock.parent.mkdir()
    lock.write_bytes(b"fixture rule lock\n")
    sources = lock.with_name("sources.lock.yaml")
    sources.write_bytes(b"schema_version: '2.0'\nresources: []\nsnapshots: []\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "fixture",
    )
    payload["knowledge_commit"] = git("rev-parse", "HEAD")
    payload["rules_digest"] = support.sha(lock.read_bytes())
    ctx.args.rules_digest = payload["rules_digest"]
    save_receipt()
    with pytest.raises(ValueError, match="commit|content|digest|publication"):
        node.validate_publication(
            ctx, {"publication_receipt_ref": "logs/publication.json"}, [card]
        )
    card["sha256"] = support.sha(target.read_bytes())
    payload["card_digests"][card["path"]] = card["sha256"]
    save_receipt()
    result = node.validate_publication(
        ctx, {"publication_receipt_ref": "logs/publication.json"}, [card]
    )
    assert result["payload"]["knowledge_commit"] == payload["knowledge_commit"]
    assert result["verification_tier"] == "synthetic_publication_identity" and result["adapter_id"] == "fixture"
    # Index publication checks actual signed content, not previous Skill runs.
    card["metadata"]["review_mode"] = "code_gate"
    ctx.call = lambda *args: (_ for _ in ()).throw(AssertionError("No workflow verifier"))
    node.validate_publication(
        ctx, {"publication_receipt_ref": "logs/publication.json"}, [card], {}
    )

    ctx.args.catalog = None
    unsigned = node.validate_publication(ctx, {"knowledge_commit": payload["knowledge_commit"]}, [card])
    assert unsigned["verification_tier"] == "repository_snapshot"
    assert unsigned["payload"]["card_digests"] == {card["path"]: card["sha256"]}
