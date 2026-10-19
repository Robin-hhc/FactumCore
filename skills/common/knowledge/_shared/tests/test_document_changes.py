"""Synthetic document operations; no business knowledge or real human approval."""

import json
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml
from _shared import changes, receipts, sources

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def domain(tmp_path):
    root = tmp_path / "K"
    shutil.copytree(ROOT / "aiot-wifi-knowledge/governance", root / "governance")
    raw = root / "docs-raw/specs/sample.md"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"# Synthetic\nThis is test evidence, not WiFi knowledge.\n")
    capture = sources.capture_document(root, "docs-raw/specs/sample.md", source_id="fixture")
    return root, capture


def card(capture, *, title="Synthetic card", claim="Synthetic conclusion."):
    metadata = {
        "schema_version": "1.0",
        "id": "fixture-card",
        "profile": "glossary",
        "title": title,
        "summary": "Synthetic test only",
        "lifecycle": "draft",
        "review_mode": "manual_document",
        "owner": "fixture-author",
        "scope": {"applicability": "unknown", "contexts": []},
        "aliases": [],
        "sources": [capture["snapshots"][0]["snapshot_id"]],
        "relations": [],
        "claims": [
            {
                "id": "fixture-claim",
                "text_ref": "#definition",
                "evidence_kind": "design",
                "source_ids": ["fixture"],
                "context_ids": [],
                "usage": "guidance",
                "verification_requirements": [],
            }
        ],
    }
    body = f'<a id="definition"></a>\n## 定义\n{claim}\n## 别名\n无。\n## 歧义\n合成夹具。\n## 范围\n仅测试。\n## 证据\nfixture\n'
    return (
        "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n" + body
    ).encode()


def plan(root, capture, *, operation_id="fixture-op", decision="create", content=None):
    return changes.create_plan(
        root,
        operation_id=operation_id,
        bundle_ref=capture["bundle_ref"],
        manifest_digest=capture["manifest_digest"],
        decision=decision,
        rationale="Synthetic explicit author decision.",
        target_path="knowledge/glossaries/fixture.md",
        candidate=card(capture) if content is None else content,
    )


def official(root):
    paths = list((root / "knowledge").rglob("*")) if (root / "knowledge").exists() else []
    lock = root / "governance/sources.lock.yaml"
    if lock.exists():
        paths.append(lock)
    return {str(p.relative_to(root)): p.read_bytes() for p in paths if p.is_file()}


def test_plan_materialize_stable_view_and_no_official_writes(domain):
    root, capture = domain
    before = official(root)
    planned = plan(root, capture)
    assert planned["operation_id"] == "fixture-op"
    result = changes.materialize(root, "fixture-op")
    assert result["phase"] == "awaiting_confirmation"
    assert official(root) == before
    view = root / ".build/fixture-op/final-view/knowledge/glossaries/fixture.md"
    assert b"lifecycle: stable" in view.read_bytes()
    assert changes.materialize(root, "fixture-op") == result
    assert (root / ".build/fixture-op/review-package.md").is_file()
    assert result["final_view_digest"] == receipts.digest_json(result["target_file_digests"])


@pytest.mark.parametrize("decision", ["merge", "split", "deprecate", "defer", "no_change"])
def test_explicit_decisions_never_imply_unconfirmed_apply(domain, decision):
    root, capture = domain
    before = official(root)
    result = plan(root, capture, decision=decision)
    assert result["decision"] == decision
    result = changes.materialize(root, "fixture-op")
    assert result["phase"] in {"deferred", "no_change", "planned_only"}
    assert official(root) == before


def test_same_operation_cannot_be_repurposed(domain):
    root, capture = domain
    plan(root, capture)
    with pytest.raises(ValueError, match="OPERATION_CONFLICT"):
        plan(root, capture, content=card(capture, title="Different"))


def test_create_cannot_overwrite_existing_or_escape(domain):
    root, capture = domain
    target = root / "knowledge/glossaries/fixture.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(card(capture))
    with pytest.raises(ValueError, match="TARGET_EXISTS"):
        plan(root, capture)
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        changes.create_plan(
            root,
            operation_id="../escape",
            bundle_ref=capture["bundle_ref"],
            manifest_digest=capture["manifest_digest"],
            decision="create",
            rationale="test",
            target_path="knowledge/glossaries/x.md",
            candidate=card(capture),
        )


def test_materialize_refuses_changed_baseline_or_bundle(domain):
    root, capture = domain
    plan(root, capture)
    (root / "governance/sources.lock.yaml").write_bytes(
        b"schema_version: '1.0'\nresources: []\nsnapshots: []\n"
    )
    with pytest.raises(ValueError, match="BASELINE_CHANGED"):
        changes.materialize(root, "fixture-op")


def test_unknown_source_or_missing_agent_content_is_not_synthesized(domain):
    root, capture = domain
    with pytest.raises(ValueError, match="CANDIDATE_REQUIRED"):
        changes.create_plan(
            root,
            operation_id="empty",
            bundle_ref=capture["bundle_ref"],
            manifest_digest=capture["manifest_digest"],
            decision="create",
            rationale="test",
            target_path="knowledge/glossaries/x.md",
        )


def test_public_cli_uses_same_operation_and_arbitrary_cwd(domain, tmp_path):
    root, capture = domain
    candidate = tmp_path / "candidate.md"
    candidate.write_bytes(card(capture))
    common = [sys.executable, str(ROOT / "skills/common/knowledge/_shared/cli.py"), "ingest"]
    result = subprocess.run(
        common
        + [
            "plan",
            "--knowledge-root",
            str(root),
            "--operation-id",
            "cli-op",
            "--bundle-ref",
            capture["bundle_ref"],
            "--manifest-digest",
            capture["manifest_digest"],
            "--decision",
            "create",
            "--rationale",
            "Synthetic fixture",
            "--target-path",
            "knowledge/glossaries/fixture.md",
            "--candidate",
            str(candidate),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["operation_id"] == "cli-op"
    result = subprocess.run(
        common + ["materialize", "--knowledge-root", str(root), "--operation-id", "cli-op"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["operation_id"] == "cli-op"
    assert not list((root / "knowledge").rglob("fixture.md"))


def test_view_tampering_is_rejected_without_regeneration(domain):
    root, capture = domain
    plan(root, capture)
    changes.materialize(root, "fixture-op")
    target = root / ".build/fixture-op/final-view/knowledge/glossaries/fixture.md"
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.materialize(root, "fixture-op")


def test_concurrent_operation_cannot_be_repurposed(domain, monkeypatch):
    root, capture = domain
    barrier = threading.Barrier(2)
    original = changes.atomic_write

    def concurrent_write(root, relative, data):
        if relative.endswith("candidates/card.md"):
            barrier.wait(timeout=20)
        return original(root, relative, data)

    monkeypatch.setattr(changes, "atomic_write", concurrent_write)

    def create(title):
        try:
            return plan(root, capture, content=card(capture, title=title))
        except changes.ChangeError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(create, ["alpha", "beta"]))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert "OPERATION_CONFLICT" in outcomes
    persisted = changes.load_plan(root, "fixture-op")
    candidate = root / ".build/fixture-op/candidates/card.md"
    assert receipts.digest_file(candidate) == persisted["request"]["candidate_digest"]


def test_navigation_encodes_spaces_and_updates_existing_label(domain):
    root, capture = domain
    changes.create_plan(
        root,
        operation_id="space",
        bundle_ref=capture["bundle_ref"],
        manifest_digest=capture["manifest_digest"],
        decision="create",
        rationale="test",
        target_path="knowledge/glossaries/card name.md",
        candidate=card(capture),
    )
    changes.materialize(root, "space")
    index = root / ".build/space/final-view/knowledge/glossaries/index.md"
    assert b"(card%20name.md)" in index.read_bytes()


def test_version_directory_move_keeps_source_identity_and_history(domain):
    from _shared import sources

    root, old = domain
    lock = {"schema_version": "1.0", "resources": old["resources"], "snapshots": old["snapshots"]}
    (root / "governance/sources.lock.yaml").write_bytes(yaml.safe_dump(lock).encode())
    path = root / "docs-raw/specs/v2/sample.md"
    path.parent.mkdir()
    path.write_bytes(b"# Version 2\nSynthetic update.\n")
    new = sources.capture_document(
        root, "docs-raw/specs/v2/sample.md", source_id="fixture", declared_version="v2"
    )
    result = changes.merged_sources(root, new)
    assert len(result["resources"]) == 1
    assert len(result["snapshots"]) == 2
    assert result["snapshots"][0] == old["snapshots"][0]


def test_unbound_claims_require_defer_instead_of_stable_candidate(domain):
    root, capture = domain
    text = card(capture).decode()
    front, body = text[4:].split("---\n", 1)
    metadata = yaml.safe_load(front)
    metadata["sources"] = []
    metadata["claims"][0]["source_ids"] = []
    candidate = ("---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n" + body).encode()
    with pytest.raises(ValueError, match="EVIDENCE_REQUIRED"):
        plan(root, capture, content=candidate)
    assert not (root / ".build/fixture-op").exists()
