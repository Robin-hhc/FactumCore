"""Real node CLIs with an isolated raw/Agent-review fixture and real local Git objects."""

import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import yaml

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "index_pipeline_fixture", ROOT / "himate-knowledge-wifi-mp/evals/pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def applied_pipeline(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("create", b"# Fixture\nPublished capture rule.\n")
    view = p.view("create", bundle_ref, "shared-rule", p.card("shared-rule", bundle))
    p.apply("create", view)
    return p


def test_interrupted_other_operation_blocks_build_and_activate(tmp_path):
    p = applied_pipeline(tmp_path)
    built = p.call("knowledge-index-build", {"operation_id": "before-interrupt"})[
        "data"
    ]
    bundle_ref, bundle = p.capture(
        "other-operation", b"# Fixture\nAnother statement.\n", source_id="another"
    )
    view = p.view(
        "other-operation", bundle_ref, "another-rule", p.card("another-rule", bundle)
    )
    proof, _ = p.review("other-operation", view)
    p.call(
        "knowledge-apply",
        {
            "operation_id": "other-operation",
            "view_ref": view,
            "proof_ref": proof,
            "fault_after": 1,
        },
        expected=3,
    )
    for action, request in [
        ("build", {"operation_id": "after-interrupt"}),
        (
            "activate",
            {
                "operation_id": "activate-interrupted",
                "generation_ref": built["generation_ref"],
                "expected_active": None,
            },
        ),
    ]:
        blocked = p.call("knowledge-index-build", request, action, expected=3)
        assert blocked["diagnostics"][0]["code"] == "TRANSACTION_PENDING"
    assert not (p.root / "artifacts/indexes/local/active.json").exists()


def test_shared_receipt_binds_actual_git_blobs_and_is_rechecked_by_query(tmp_path):
    # This isolated test key signs publication receipts only.
    publication_key = Ed25519PrivateKey.generate()
    p = applied_pipeline(tmp_path)
    workspace = p.root.parent

    def git(*args):
        return (
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=" + os.devnull,
                    "-C",
                    str(workspace),
                    *args,
                ],
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .strip()
        )

    git("init", "--initial-branch=main", "-q")
    git("config", "core.autocrlf", "false")
    git("add", "himate-knowledge-wifi-mp/knowledge", "himate-knowledge-wifi-mp/governance")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "fixture publication objects",
    )
    p.catalog["publication_trust"] = {
        "fixture-publication": {
            "synthetic": True,
            "fixture_root": str(p.root),
            "public_key_b64": base64.b64encode(
                publication_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            ).decode(),
        }
    }
    p.catalog_path.write_bytes(FIXTURE.canonical(p.catalog))
    path = "knowledge/rules/shared-rule.md"
    payload = {
        "rules_digest": p.rules,
        "knowledge_commit": git("rev-parse", "HEAD"),
        "card_digests": {path: FIXTURE.sha((p.root / path).read_bytes())},
        "merge_check_refs": {},
    }
    receipt = {
        "adapter_id": "fixture-publication",
        "payload": payload,
        "signature_b64": base64.b64encode(
            publication_key.sign(FIXTURE.canonical(payload))
        ).decode(),
    }
    ref = p.write("logs/publication/fixture.json", FIXTURE.canonical(receipt))
    built = p.call(
        "knowledge-index-build",
        {
            "operation_id": "shared-build",
            "channel": "shared",
            "publication_receipt_ref": ref,
        },
    )["data"]
    p.call(
        "knowledge-index-build",
        {
            "operation_id": "shared-activate",
            "generation_ref": built["generation_ref"],
            "expected_active": None,
        },
        "activate",
    )
    request = {
        "operation_id": "shared-query",
        "channel": "shared",
        "query": "capture",
        "purpose": "current",
    }
    found = p.call("knowledge-query", request)["data"]
    assert [row["card_id"] for row in found["matches"]] == ["shared-rule"]
    _, unrelated = p.capture(
        "unrelated-source",
        b"# Unrelated\nNot used by the published card.\n",
        source_id="unrelated",
    )
    sources = yaml.safe_load((p.root / "governance/sources.lock.yaml").read_bytes())
    sources["resources"].extend(unrelated["resources"])
    sources["snapshots"].extend(unrelated["snapshots"])
    p.write("governance/sources.lock.yaml", FIXTURE.canonical(sources))
    for purpose in ("current", "historical"):
        unchanged = p.call(
            "knowledge-query",
            {**request, "operation_id": "after-append-" + purpose, "purpose": purpose},
        )["data"]
        assert [row["card_id"] for row in unchanged["matches"]] == ["shared-rule"]
        assert unchanged["generation_ref"] == built["generation_ref"]
    # A self-sealed generation must not bypass the actual receipt signature.
    manifest_path = p.root / built["generation_ref"]
    manifest = p.record(built["generation_ref"])
    manifest["publication"]["payload"]["knowledge_commit"] = "0" * 40
    manifest["digest"] = FIXTURE.sha(
        FIXTURE.canonical({k: v for k, v in manifest.items() if k != "digest"})
    )
    manifest_path.write_bytes(FIXTURE.canonical(manifest))
    refused = p.call(
        "knowledge-query",
        {**request, "operation_id": "forged-shared-query"},
        expected=2,
    )
    assert refused["status"] == "error"
