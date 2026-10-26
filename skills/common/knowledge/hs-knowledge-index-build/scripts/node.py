"""Immutable SQLite generations, proof qualification and writer-lock/CAS activation."""

from __future__ import annotations
import base64
from contextlib import contextmanager
import os
import tempfile
import re
import subprocess
from pathlib import Path
from support import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
    read_json,
    safe,
    sha,
    write_bytes,
)


@contextmanager
def writer(ctx):
    path = safe(ctx.root, "logs/operations/.writer.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, 2)
            if not handle.tell():
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def state(ctx):
    path = safe(ctx.root, "logs/events/state.json")
    if not path.exists():
        return {"validity_epoch": 0}
    result = read_json(path)
    ctx.modules["records"].verify(result)
    return result


def baseline(ctx):
    paths = [p for p in (ctx.root / "knowledge").rglob("*.md") if p.is_file()]
    paths += [ctx.root / "governance/sources.lock.yaml"]
    return {
        p.relative_to(ctx.root).as_posix(): sha(
            fixed_bytes(ctx.root, p.relative_to(ctx.root).as_posix())
        )
        for p in sorted(paths)
    }


def active(ctx, channel):
    path = safe(ctx.root, f"artifacts/indexes/{channel}/active.json")
    if not path.exists():
        return None
    value = read_json(path)
    ctx.modules["records"].verify(value)
    return value


def check_transactions(ctx):
    """Caller holds the same writer lock as apply; every operation is a barrier."""
    for path in sorted((ctx.root / "logs/operations").glob("*/journal.json")):
        ref = path.relative_to(ctx.root).as_posix()
        try:
            try:
                journal = ctx.record(ref, "transaction_journal")
            except NodeError as exc:
                if exc.code != "STALE_RULES" or path.parent.name == ctx.operation:
                    raise
                # Only foreign terminal liveness may survive a rules upgrade.
                # This does not supply qualification/proof for any card.
                journal = read_json(safe(ctx.root, ref, ["logs/operations"]))
                ctx.modules["records"].verify(journal)
                ctx.modules["validation"].validate_shape("transaction_journal", journal, ctx.rules)
                if journal.get("operation_id") != path.parent.name:
                    raise ValueError("transaction journal operation/directory mismatch")
                if journal.get("status") not in {"committed", "rolled_back"}:
                    raise ValueError("old-rules transaction journal is not terminal")
            if journal.get("status") in {"committed", "rolled_back"} and journal.get("operation_id") != path.parent.name:
                raise ValueError("transaction journal operation/directory mismatch")
        except (ValueError, OSError, KeyError) as exc:
            raise NodeError(
                "TRANSACTION_PENDING",
                "Unreadable transaction journal prevents a safe snapshot",
                ref,
                blocked=True,
            ) from exc
        if journal.get("status") not in {"committed", "rolled_back"}:
            raise NodeError(
                "TRANSACTION_PENDING",
                "A transaction journal is not terminal; recover it before indexing",
                ref,
                blocked=True,
            )


def qualify(ctx, card, results, current_code_proof_ref=None):
    path, card_sha = card["path"], card["sha256"]
    for result_ref in results:
        try:
            result = ctx.record(result_ref, "apply_result")
            if path not in result.get("writes", []):
                continue
            view = ctx.record(result["view_ref"], "final_view")
            if not any(
                row["path"] == path and row["final_digest"] == card_sha
                for row in view["writes"]
            ):
                continue
            response = ctx.call(
                "hs-knowledge-apply",
                {
                    "operation_id": result["operation_id"],
                    "apply_result_ref": result_ref,
                    "card_path": path,
                    "card_digest": card_sha,
                    "purpose": "historical",
                },
                "verify-result",
            )
            if response["data"].get("result_verified") is True and any(
                row.get("path") == path and row.get("sha256") == card_sha
                for row in response["data"].get("historical_files", [])
            ):
                return {
                    "apply_result_ref": result_ref,
                    "operation_id": result["operation_id"],
                    "view_digest": view["digest"],
                    "verification_tier": response["data"].get("verification_tier"),
                    "current_code_proof_ref": current_code_proof_ref,
                }
        except (ValueError, OSError, KeyError):
            continue
    raise NodeError(
        "CARD_PROOF_MISSING",
        "Stable content has no matching verified admission record",
        path,
        blocked=True,
    )


def git_read(workspace, args):
    if args[0] not in {"rev-parse", "cat-file"}:
        raise NodeError(
            "INVALID_GIT_READ", "Only fixed Git object/ref reads are supported"
        )
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k == "GIT_TEST_ASSUME_DIFFERENT_OWNER"}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
        GIT_PAGER="cat",
        GIT_NO_LAZY_FETCH="1",
    )
    process = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "diff.external=",
            "-c",
            "core.pager=cat",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "safe.directory=" + Path(workspace).resolve().as_posix(),
            "-C",
            str(workspace),
            *args,
        ],
        env=env,
        capture_output=True,
        timeout=30,
    )
    if process.returncode:
        raise NodeError(
            "PUBLICATION_GIT_UNAVAILABLE",
            "The signed publication commit is not available in the workspace Git repository",
            blocked=True,
        )
    return process.stdout


def validate_publication(ctx, request, cards, qualifications=None, purpose="current"):
    ref = request.get("publication_receipt_ref")
    if not ref or not ctx.args.catalog:
        raise NodeError(
            "SHARED_MERGE_PROOF_REQUIRED",
            "Shared generation needs trusted actual publication proof",
            blocked=True,
        )
    receipt = read_json(safe(ctx.root, ref, ["logs"]))
    catalog = read_json(ctx.args.catalog)
    trust = catalog.get("publication_trust", {}).get(receipt.get("adapter_id"))
    fixture = safe(ctx.root, ".isolated-knowledge-fixture")
    synthetic_allowed = bool(
        trust
        and trust.get("synthetic")
        and trust.get("fixture_root")
        and Path(trust["fixture_root"]).resolve() == ctx.root
        and fixture.is_file()
        and fixture.read_text(encoding="utf-8").strip()
        == "AIOTBOT_SYNTHETIC_FIXTURE_V2"
    )
    if not trust or (trust.get("synthetic") and not synthetic_allowed):
        raise NodeError(
            "UNTRUSTED_PUBLICATION",
            "A trusted committer/CI adapter is required; synthetic adapters are fixture-only",
            blocked=True,
        )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    payload = receipt["payload"]
    try:
        Ed25519PublicKey.from_public_bytes(
            base64.b64decode(trust["public_key_b64"], validate=True)
        ).verify(
            base64.b64decode(receipt["signature_b64"], validate=True),
            canonical(payload),
        )
    except Exception as exc:
        raise NodeError(
            "PUBLICATION_SIGNATURE_INVALID", "Publication signature is invalid"
        ) from exc
    required = {c["path"]: c["sha256"] for c in cards}
    if (
        payload.get("card_digests") != required
        or payload.get("rules_digest") != ctx.args.rules_digest
        or not re.fullmatch(
            r"[0-9a-f]{40}(?:[0-9a-f]{24})?", str(payload.get("knowledge_commit", ""))
        )
    ):
        raise NodeError(
            "PUBLICATION_CONTENT_MISMATCH", "Merged content identity differs"
        )
    workspace, commit = ctx.root.parent.resolve(), payload["knowledge_commit"]
    top = Path(
        git_read(workspace, ["rev-parse", "--show-toplevel"]).decode().strip()
    ).resolve()
    if (
        top != workspace
        or git_read(workspace, ["rev-parse", "--verify", commit + "^{commit}"])
        .decode()
        .strip()
        != commit
    ):
        raise NodeError(
            "PUBLICATION_REPOSITORY_MISMATCH",
            "Publication must name an exact commit in this workspace repository",
        )
    prefix = ctx.root.relative_to(workspace).as_posix()
    expected_files = {
        **required,
        "governance/framework.lock.yaml": ctx.args.rules_digest,
    }
    for ref, expected in expected_files.items():
        safe(ctx.root, ref)
        raw = git_read(
            workspace, ["cat-file", "blob", commit + ":" + prefix + "/" + ref]
        )
        if sha(raw) != expected:
            raise NodeError(
                "PUBLICATION_CONTENT_MISMATCH",
                "Actual Git commit content differs from the signed publication digest",
                ref,
            )
    published_sources = load_yaml(
        git_read(
            workspace,
            [
                "cat-file",
                "blob",
                commit + ":" + prefix + "/governance/sources.lock.yaml",
            ],
        )
    )
    ctx.modules["validation"].validate_shape("sources", published_sources, ctx.rules)
    current_sources = ctx.modules["source_resources"].read_source_lock(ctx.root)
    for card in cards:
        for source in card["metadata"].get("sources", []):
            published_snapshot = ctx.modules["source_resources"].validate_source_ref(
                source, published_sources
            )
            current_snapshot = ctx.modules["source_resources"].validate_source_ref(source, current_sources)
            published_resource = next(row for row in published_sources["resources"] if row["source_id"] == source["source_id"])
            current_resource = next(row for row in current_sources["resources"] if row["source_id"] == source["source_id"])
            if canonical((published_resource, published_snapshot)) != canonical((current_resource, current_snapshot)):
                raise NodeError("SOURCE_LINEAGE_MISMATCH", "Referenced source identity differs from the accepted Git source lock", source["source_id"])
    if "acceptance_records" in payload:
        portable = repository_acceptance(ctx, receipt, cards)
        if qualifications:
            if canonical(portable) != canonical(qualifications):
                raise NodeError("ACCEPTANCE_CHANGED", "Published qualification differs from exact accepted records")
        elif qualifications is not None:
            qualifications.update(portable)
        return receipt
    # Legacy signed publications retain their original authenticated local proof
    # requirements. New portable records use the fixed-CI acceptance path above.
    if qualifications is not None and not qualifications and cards:
        results = [path.relative_to(ctx.root).as_posix() for path in sorted((ctx.root / "logs/operations").glob("*/apply-result.json"))]
        qualifications.update({card["metadata"]["id"]: qualify(ctx, card, results) for card in cards})
    code_cards = {
        card["metadata"]["id"]: card
        for card in cards
        if card["metadata"]["review_mode"] == "code_gate"
    }
    merge_refs = payload.get("merge_check_refs", {})
    if not isinstance(merge_refs, dict) or set(merge_refs) != set(code_cards):
        raise NodeError(
            "MERGE_GATE_PROOF_REQUIRED",
            "Every code card needs its exact authenticated current merge proof",
            blocked=True,
        )
    for card_id, card in code_cards.items():
        qualification = (qualifications or {}).get(card_id)
        if not qualification:
            raise NodeError(
                "CARD_PROOF_MISSING",
                "Shared code card has no authenticated application provenance",
                card_id,
                blocked=True,
            )
        proof_ref = merge_refs[card_id]
        retired = card["metadata"].get("lifecycle") == "deprecated"
        proof = ctx.record(proof_ref, "merge_check")
        if (
            proof.get("mode") != "merge"
            or proof.get("status") != "passed"
            or proof.get("view_digest") != qualification["view_digest"]
        ):
            raise NodeError(
                "MERGE_GATE_PROOF_REQUIRED",
                "Publication proof is not a passing merge check for the same exact view",
                card_id,
                blocked=True,
            )
        verified = ctx.call(
            "hs-knowledge-apply",
            {
                "operation_id": qualification["operation_id"],
                "apply_result_ref": qualification["apply_result_ref"],
                "purpose": purpose,
                **(
                    {"current_code_proof_ref": proof_ref}
                    if purpose == "current"
                    else {}
                ),
                **(
                    {}
                    if retired and purpose == "current"
                    else {"card_path": card["path"]}
                ),
                "card_digest": card["sha256"],
            },
            "verify-result",
        )["data"]
        if (
            verified.get("result_verified") is not True
            or (
                purpose == "current"
                and verified.get("current_code_proof_ref") != proof_ref
            )
            or not any(
                item.get("path") == card["path"]
                and item.get("sha256") == card["sha256"]
                for item in verified.get(
                    "historical_files"
                    if purpose == "historical" or retired
                    else "eligible_files",
                    [],
                )
            )
        ):
            raise NodeError(
                "MERGE_GATE_PROOF_REQUIRED",
                "Current merge proof did not authenticate exact published content",
                card_id,
                blocked=True,
            )
        qualification["current_code_proof_ref"] = proof_ref
    return receipt


def repository_acceptance(ctx, receipt, cards):
    """Called only after trusted signature and exact Git card/rule validation."""
    payload = receipt["payload"]
    declared = payload.get("acceptance_records")
    if not isinstance(declared, dict) or not declared:
        raise NodeError("ACCEPTANCE_RECORD_REQUIRED", "Accepted repository summaries are required")
    workspace, commit = ctx.root.parent.resolve(), payload["knowledge_commit"]
    prefix = ctx.root.relative_to(workspace).as_posix()
    available = {}
    for ref, expected in sorted(declared.items()):
        safe(ctx.root, ref, ["logs/ingest"])
        raw = git_read(workspace, ["cat-file", "blob", commit + ":" + prefix + "/" + ref])
        if sha(raw) != expected or fixed_bytes(ctx.root, ref, ["logs/ingest"]) != raw:
            raise NodeError("ACCEPTANCE_CHANGED", "Record must be the exact accepted Git blob", ref)
        record = load_yaml(raw)
        ctx.modules["records"].validate_ingest_record(record, rules=ctx.rules)
        acceptance = record.get("acceptance", {})
        applied = record.get("progress", {}).get("apply", {})
        if (acceptance.get("rules_digest") != ctx.args.rules_digest
                or applied.get("status") != "applied"
                or applied.get("view_digest") != acceptance.get("content_view_digest")
                or not acceptance.get("proof_digests")):
            raise NodeError("ACCEPTANCE_INCOMPLETE", "Summary lacks completed exact-view acceptance", ref)
        for row in acceptance.get("cards", []):
            available.setdefault((row.get("path"), row.get("sha256")), []).append((ref, expected, acceptance, row))
    qualifications = {}
    source_lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
    for card in cards:
        matches = available.get((card["path"], card["sha256"]), [])
        if not matches:
            raise NodeError("ACCEPTANCE_RECORD_REQUIRED", "Card has no exact accepted summary", card["path"])
        ref, record_sha, acceptance, row = sorted(matches, key=lambda item: item[0])[-1]
        mode = card["metadata"]["review_mode"]
        expected_result = "retired" if card["metadata"].get("lifecycle") == "deprecated" else "supported"
        claim_ids = sorted(claim["id"] for claim in card["claims"])
        if (row.get("card_id") != card["metadata"]["id"] or row.get("review_mode") != mode
                or sorted(row.get("claim_ids", [])) != claim_ids or row.get("review_result") != expected_result):
            raise NodeError("ACCEPTANCE_CONTENT_MISMATCH", "Accepted card/Claim scope differs", card["path"])
        qualifications[card["metadata"]["id"]] = {
            "kind": "accepted_repository", "record_ref": ref, "record_sha256": record_sha,
            "knowledge_commit": commit, "view_digest": acceptance["content_view_digest"],
            "rules_digest": acceptance["rules_digest"], "config_digest": acceptance.get("config_digest"),
            "code_identity": acceptance.get("code_identity"),
            "review_mode": mode, "claim_ids": claim_ids, "review_result": expected_result,
            "source_bindings": [{
                "reference": source,
                "resource": next(item for item in source_lock["resources"] if item["source_id"] == source["source_id"]),
                "snapshot": ctx.modules["source_resources"].validate_source_ref(source, source_lock),
            } for source in card["metadata"]["sources"]],
        }
    return qualifications


def verify(ctx, ref, purpose="current"):
    manifest = ctx.record(ref, "index_manifest")
    prefix = f"artifacts/indexes/{manifest['channel']}/{manifest['generation_id']}"
    if ref != prefix + "/manifest.json":
        raise NodeError("INVALID_GENERATION_PATH", ref)
    if (
        sha(fixed_bytes(ctx.root, manifest["database_ref"], [prefix]))
        != manifest["database_digest"]
    ):
        raise NodeError("INDEX_CHANGED", "Database digest differs")
    cards = [
        ctx.modules["indexing"].read_document(
            fixed_bytes(ctx.root, row["blob_ref"], [prefix]), row["path"], ctx.rules,
            card_id=card_id, sha256=row["sha256"],
        )
        for card_id, row in manifest["documents"].items()
    ]
    summary = ctx.modules["indexing"].verify_database(
        cards, ctx.args.rules_digest, safe(ctx.root, manifest["database_ref"], [prefix])
    )
    if manifest.get("index_verification") != summary:
        raise NodeError("INDEX_VERIFICATION_CHANGED", "Full collection verification differs")
    if manifest["channel"] == "shared":
        publication = validate_publication(
            ctx,
            {"publication_receipt_ref": manifest.get("publication_receipt_ref")},
            cards,
            manifest.get("qualifications", {}),
            "historical" if purpose == "historical" else "current",
        )
        if canonical(publication) != canonical(manifest.get("publication")):
            raise NodeError(
                "PUBLICATION_CHANGED",
                "Generation publication receipt differs from its authenticated source",
            )
    return manifest


def execute(ctx):
    request, action = ctx.request, ctx.args.action or "build"
    channel = request.get("channel", "local")
    if channel not in ("local", "shared"):
        raise NodeError("INVALID_CHANNEL", channel)
    if action in ("verify", "activate"):
        ref = request["generation_ref"]
        manifest = verify(ctx, ref, request.get("purpose", "current"))
        if action == "activate":
            with writer(ctx):
                check_transactions(ctx)
                manifest = verify(ctx, ref)
                current = active(ctx, manifest["channel"])
                actual = current["digest"] if current else None
                if (
                    "expected_active" not in request
                    or request["expected_active"] != actual
                ):
                    raise NodeError(
                        "ACTIVE_CHANGED",
                        "Expected active generation differs",
                        blocked=True,
                    )
                if (
                    digest(baseline(ctx)) != manifest["knowledge_baseline"]
                    or state(ctx)["validity_epoch"] != manifest["validity_epoch"]
                ):
                    raise NodeError(
                        "GENERATION_STALE",
                        "Knowledge or validity changed before activation",
                        blocked=True,
                    )
                pointer = ctx.seal(
                    {
                        "channel": manifest["channel"],
                        "generation_id": manifest["generation_id"],
                        "generation_ref": ref,
                        "manifest_digest": manifest["digest"],
                    },
                    "index_manifest",
                )
                write_bytes(
                    ctx.root,
                    f"artifacts/indexes/{manifest['channel']}/active.json",
                    canonical(pointer),
                    immutable=False,
                )
        return {
            "verified": True,
            "activated": action == "activate",
            "manifest_ref": ref,
            "generation_ref": ref,
            "generation_id": manifest["generation_id"],
            "channel": manifest["channel"],
            "validity_epoch": manifest["validity_epoch"],
            "knowledge_baseline": manifest["knowledge_baseline"],
            "complete": True,
            "index_verification": manifest["index_verification"],
        }, "activated" if action == "activate" else "verified"
    if action != "build":
        raise NodeError("INVALID_ACTION", action)
    with writer(ctx):
        check_transactions(ctx)
        files = baseline(ctx)
        epoch = state(ctx)["validity_epoch"]
        previous = active(ctx, channel)
        source_lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
        cards = []
        for path in files:
            if not path.startswith("knowledge/") or Path(path).name in (
                "AGENTS.md",
                "index.md",
            ):
                continue
            card = ctx.modules["knowledge"].parse_card(
                fixed_bytes(ctx.root, path), path, ctx.rules
            )
            if card["metadata"]["lifecycle"] not in ("stable", "deprecated"):
                continue
            ctx.modules["knowledge"].validate_card(
                card, None, {**ctx.rules, "source_lock": source_lock}
            )
            cards.append(card)
        ctx.modules["knowledge"].validate_relations(
            {c["metadata"]["id"]: c for c in cards}
        )
        result_paths = sorted(
            (ctx.root / "logs/operations").glob("*/apply-result.json")
        )
        results = [p.relative_to(ctx.root).as_posix() for p in result_paths]
        current_refs = request.get("current_code_proof_refs", {})
        if not isinstance(current_refs, dict) or not set(current_refs).issubset(
            c["metadata"]["id"] for c in cards
        ):
            raise NodeError(
                "INVALID_CURRENT_PROOF_MAP",
                "Current proof map must name cards in this exact generation",
            )
        qualifications = {} if channel == "shared" else {
            c["metadata"]["id"]: qualify(
                ctx, c, results, current_refs.get(c["metadata"]["id"])
            )
            for c in cards
        }
        publication = (
            validate_publication(ctx, request, cards, qualifications)
            if channel == "shared"
            else None
        )
        if baseline(ctx) != files or state(ctx)["validity_epoch"] != epoch:
            raise NodeError(
                "KNOWLEDGE_CHANGED", "Input changed while snapshotting", blocked=True
            )
    generation = (
        "gen-"
        + digest(
            {
                "files": files,
                "epoch": epoch,
                "channel": channel,
                "operation": ctx.operation,
                "tool": ctx.tool,
            }
        )[:24]
    )
    prefix = f"artifacts/indexes/{channel}/{generation}"
    manifest_ref = prefix + "/manifest.json"
    if safe(ctx.root, manifest_ref).exists():
        manifest = verify(ctx, manifest_ref)
        return {
            "generation_ref": manifest_ref,
            "generation_id": generation,
            "expected_active": manifest["expected_active"],
        }, "built"
    temp_dir = safe(ctx.root, ctx.base + "/index-tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    descriptor, db_name = tempfile.mkstemp(dir=temp_dir, suffix=".sqlite")
    os.close(descriptor)
    documents = {}
    try:
        Path(db_name).unlink()
        verification = ctx.modules["indexing"].build_database(cards, ctx.args.rules_digest, db_name)
        for card in cards:
            card_id = card["metadata"]["id"]
            blob_ref = prefix + "/cards/" + card["sha256"] + ".md"
            write_bytes(ctx.root, blob_ref, card["raw"])
            documents[card_id] = {"path": card["path"], "sha256": card["sha256"], "blob_ref": blob_ref}
        database = Path(db_name).read_bytes()
        database_ref = prefix + "/index.sqlite"
        write_bytes(ctx.root, database_ref, database)
    finally:
        Path(db_name).unlink(missing_ok=True)
    manifest = ctx.seal(
        {
            "generation_id": generation,
            "channel": channel,
            "database_ref": database_ref,
            "database_digest": sha(database),
            "documents": documents,
            "qualifications": qualifications,
            "knowledge_baseline": digest(files),
            "file_baseline": files,
            "validity_epoch": epoch,
            "expected_active": previous["digest"] if previous else None,
            "publication": publication,
            "publication_receipt_ref": request.get("publication_receipt_ref")
            if channel == "shared"
            else None,
            "tokenizer_version": ctx.modules["indexing"].TOKENIZER_VERSION,
            "index_verification": verification,
        },
        "index_manifest",
    )
    ctx.save(manifest_ref, manifest)
    verify(ctx, manifest_ref)
    return {
        "generation_ref": manifest_ref,
        "generation_id": generation,
        "expected_active": manifest["expected_active"],
    }, "built"
