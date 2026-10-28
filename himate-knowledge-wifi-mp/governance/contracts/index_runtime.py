"""Immutable SQLite generations with content checks and writer-lock/CAS activation."""

from __future__ import annotations
import base64
from contextlib import contextmanager
from dataclasses import dataclass
import os
import tempfile
import re
import subprocess
from pathlib import Path
from .runtime import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
    read_json,
    safe,
    sha,
    write_index_bytes as write_bytes,
)
from . import input_snapshot


@dataclass(frozen=True)
class VerifiedGeneration:
    """A process-local observation, never an input credential or serialized cache."""

    root: Path
    rules_digest: str
    generation_ref: str
    manifest: dict
    cards: tuple
    database_path: Path
    file_fingerprints: tuple


def _read_document(ctx, raw, row, card_id):
    if sha(raw) != row["sha256"]:
        raise NodeError("INDEX_BODY_MISMATCH", "Frozen body fingerprint differs", row["path"])
    card = ctx.modules["knowledge"].decode_card(raw, row["path"], ctx.rules)
    if card["metadata"]["id"] != card_id:
        raise NodeError("INDEX_CARD_ID_MISMATCH", "Frozen body has another card ID", row["path"])
    return card


def reuse_generation(ctx, ref, observed):
    """Reuse full verification only while every observed generation byte still agrees."""
    if (not isinstance(observed, VerifiedGeneration)
            or observed.root != ctx.root.resolve()
            or observed.rules_digest != ctx.args.rules_digest
            or observed.generation_ref != ref):
        raise NodeError("INVALID_GENERATION_OBSERVATION", "A matching process-local observation is required")
    for path, expected in observed.file_fingerprints:
        if sha(fixed_bytes(ctx.root, path, ["artifacts/indexes", "logs"])) != expected:
            raise NodeError("INDEX_CHANGED", "Verified generation bytes changed", path)
    current = ctx.record(ref, "index_manifest")
    if current != observed.manifest:
        raise NodeError("INDEX_CHANGED", "Verified manifest changed", ref)
    if current["channel"] == "shared":
        # Source lineage can change without modifying an immutable generation.
        publication = validate_publication(ctx, {
            "publication_receipt_ref": current.get("publication_receipt_ref"),
            "knowledge_commit": (current.get("publication") or {}).get("payload", {}).get("knowledge_commit"),
        }, observed.cards, current.get("qualifications", {}))
        ctx.publication_verification_tier = publication["verification_tier"]
    return current


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
    validate_pointer(ctx, value, channel)
    return value


def validate_pointer(ctx, value, channel):
    ctx.modules["records"].verify(value)
    ctx.modules["validation"].validate_shape("index_manifest", value, ctx.rules)
    if (value.get("record_kind") != "index_manifest" or value.get("channel") != channel
            or value.get("generation_ref") != f"artifacts/indexes/{channel}/{value.get('generation_id')}/manifest.json"
            or not re.fullmatch(r"[0-9a-f]{64}", value.get("manifest_digest", ""))
            or (value.get("previous_active_digest") is not None
                and not re.fullmatch(r"[0-9a-f]{64}", value["previous_active_digest"]))):
        raise NodeError("INVALID_ACTIVE_POINTER", "Active pointer identity or predecessor differs")


def activation_path(channel, pointer_digest):
    return f"artifacts/indexes/{channel}/activations/{pointer_digest}.json"


def activated_pointer(ctx, channel, generation_ref, manifest_digest, expected_active, *, execution_binding=None):
    """Only the real active control plane roots an immutable activation history."""
    pointer, seen = active(ctx, channel), set()
    while pointer is not None:
        validate_pointer(ctx, pointer, channel)
        identity = pointer["digest"]
        if identity in seen:
            raise NodeError("INVALID_ACTIVATION_HISTORY", "Activation predecessor cycle")
        seen.add(identity)
        if (pointer["generation_ref"], pointer["manifest_digest"]) == (generation_ref, manifest_digest):
            if execution_binding is not None and pointer.get("execution_binding") != execution_binding:
                return None
            if ("previous_active_digest" in pointer
                    and pointer["previous_active_digest"] != expected_active):
                raise NodeError("ACTIVE_CHANGED", "Activation history replaces the original baseline", blocked=True)
            return pointer
        previous = pointer.get("previous_active_digest")
        if previous is None:
            return None
        path = safe(ctx.root, activation_path(channel, previous), ["artifacts/indexes"])
        if not path.exists():
            return None
        pointer = read_json(path)
        if pointer.get("digest") != previous:
            raise NodeError("INVALID_ACTIVATION_HISTORY", "Activation predecessor digest differs")
    return None


def expected_baseline(ctx, manifest, request, *, current=False):
    if ("expected_active" not in manifest or "expected_active" not in request
            or request["expected_active"] != manifest.get("expected_active")):
        raise NodeError("ACTIVE_CHANGED", "Request replaces the generation's original active baseline", blocked=True)
    if current:
        pointer = active(ctx, manifest["channel"])
        if (pointer["digest"] if pointer else None) != manifest["expected_active"]:
            raise NodeError("ACTIVE_CHANGED", "Expected active generation differs", blocked=True)


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
            "The requested snapshot commit is not available in the workspace Git repository",
            blocked=True,
        )
    return process.stdout


def publication_workspace(ctx, catalog=None):
    """Locate the actual enclosing Git repository without machine registration."""
    workspace = Path(git_read(ctx.root, ["rev-parse", "--show-toplevel"]).decode("utf-8").strip()).resolve()
    if not ctx.root.resolve().is_relative_to(workspace):
        raise NodeError("PUBLICATION_REPOSITORY_MISMATCH", "Knowledge root escapes the actual snapshot repository")
    return workspace


def validate_publication(ctx, request, cards, qualifications=None, purpose="current"):
    receipt_ref = request.get("publication_receipt_ref")
    receipt = read_json(safe(ctx.root, receipt_ref, ["logs"])) if receipt_ref else {}
    payload = receipt.get("payload", {})
    if not isinstance(payload, dict):
        raise NodeError("INVALID_REPOSITORY_SNAPSHOT", "Snapshot payload must be an object")
    if receipt_ref:
        catalog_path = getattr(ctx.args, "catalog", None)
        catalog = read_json(catalog_path) if catalog_path else {}
        trust = catalog.get("publication_trust", {}).get(receipt.get("adapter_id"))
        fixture = safe(ctx.root, ".isolated-knowledge-fixture")
        synthetic_allowed = bool(
            trust and trust.get("synthetic") and trust.get("fixture_root")
            and Path(trust["fixture_root"]).resolve() == ctx.root
            and fixture.is_file()
            and fixture.read_text(encoding="utf-8").strip() == "HIMATE_SYNTHETIC_FIXTURE_V2"
        )
        if not trust or (trust.get("synthetic") and not synthetic_allowed):
            raise NodeError("UNTRUSTED_PUBLICATION", "Explicit publication receipt has no trusted adapter identity")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(trust["public_key_b64"], validate=True)).verify(
                base64.b64decode(receipt["signature_b64"], validate=True), canonical(payload)
            )
        except Exception as exc:
            raise NodeError("PUBLICATION_SIGNATURE_INVALID", "Explicit publication receipt signature is invalid") from exc
    commit = request.get("knowledge_commit") or payload.get("knowledge_commit")
    required = {card["path"]: card["sha256"] for card in cards}
    if (
        not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", str(commit or ""))
        or (payload.get("knowledge_commit") and payload["knowledge_commit"] != commit)
        or ("card_digests" in payload and payload["card_digests"] != required)
        or ("rules_digest" in payload and payload["rules_digest"] != ctx.args.rules_digest)
    ):
        raise NodeError("PUBLICATION_CONTENT_MISMATCH", "Exact repository snapshot identity differs or is missing")
    workspace = publication_workspace(ctx)
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
            "Snapshot must name an exact commit in this workspace repository",
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
                "Actual Git snapshot differs from the indexed card or rules digest",
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
                raise NodeError("SOURCE_LINEAGE_MISMATCH", "Referenced source identity differs from the exact Git source lock", source["source_id"])
    return {
        "verification_tier": ("synthetic_publication_identity" if synthetic_allowed else "trusted_publication_identity") if receipt_ref else "repository_snapshot",
        **({"adapter_id": receipt["adapter_id"]} if receipt_ref else {}),
        "payload": {"knowledge_commit": commit, "rules_digest": ctx.args.rules_digest,
                    "card_digests": required},
    }


def code_contexts(ctx, cards, request):
    """Validate direct code/build materials; no workflow result is required."""
    contexts = request.get("code_contexts", request.get("code_evidence", {}))
    if ("code_contexts" in request and "code_evidence" in request
            and request["code_contexts"] != request["code_evidence"]):
        raise NodeError("CODE_CONTEXT_CONFLICT", "Code material aliases differ")
    known = {card["metadata"]["id"]: card for card in cards}
    if not isinstance(contexts, dict) or not set(contexts) <= set(known):
        raise NodeError("INVALID_CODE_CONTEXTS", "Code contexts must name cards in this generation")
    if not contexts:
        return contexts
    configuration = ctx.modules["validation"].workspace_config_path(ctx.root)
    declaration = ctx.modules["validation"].load_yaml(configuration.read_bytes())
    for card_id, context in contexts.items():
        if not isinstance(context, dict):
            raise NodeError("INVALID_CODE_CONTEXT", "Each code context must be an object", card_id)
        identity = context.get("code_identity")
        ctx.modules["source_resources"].validate_current_code_identity(
            identity, configuration, context.get("config_digest"), ctx.rules, declaration.get("code_policy")
        )
        evidence = context.get("claim_evidence", {})
        claims = {claim["id"] for claim in known[card_id]["claims"]}
        if not isinstance(evidence, dict) or not set(evidence) <= claims:
            raise NodeError("INVALID_CLAIM_EVIDENCE", "Material evidence must name this card's Claims", card_id)
        for rows in evidence.values():
            if not isinstance(rows, list) or any(
                    not isinstance(row, dict) or row.get("requirement") not in {"build-support", "runtime-support"}
                    or identity["build_files"].get(row.get("path")) != row.get("sha256")
                    or row.get("sha256") is None for row in rows):
                raise NodeError("INVALID_CLAIM_EVIDENCE", "Claim materials must bind actual code-context artifact hashes", card_id)
    return contexts


def verify_generation(ctx, ref, purpose="current", *, verified_database=None):
    manifest_bytes = fixed_bytes(ctx.root, ref, ["artifacts/indexes"])
    manifest = ctx.record(ref, "index_manifest")
    prefix = f"artifacts/indexes/{manifest['channel']}/{manifest['generation_id']}"
    if ref != prefix + "/manifest.json":
        raise NodeError("INVALID_GENERATION_PATH", ref)
    fingerprints = {ref: sha(manifest_bytes), manifest["database_ref"]: manifest["database_digest"]}
    fingerprints.update({row["blob_ref"]: row["sha256"] for row in manifest["documents"].values()})
    if manifest.get("publication_receipt_ref"):
        receipt_ref = manifest["publication_receipt_ref"]
        fingerprints[receipt_ref] = sha(fixed_bytes(ctx.root, receipt_ref, ["logs"]))
    if (
        sha(fixed_bytes(ctx.root, manifest["database_ref"], [prefix]))
        != manifest["database_digest"]
    ):
        raise NodeError("INDEX_CHANGED", "Database digest differs")
    cards = [
        _read_document(ctx, fixed_bytes(ctx.root, row["blob_ref"], [prefix]), row, card_id)
        for card_id, row in manifest["documents"].items()
    ]
    database_path = safe(ctx.root, manifest["database_ref"], [prefix])
    summary = (ctx.modules["indexing"].reuse_database(cards, ctx.args.rules_digest, database_path, verified_database)
               if verified_database is not None else
               ctx.modules["indexing"].verify_database(cards, ctx.args.rules_digest, database_path))
    if manifest.get("index_verification") != summary:
        raise NodeError("INDEX_VERIFICATION_CHANGED", "Full collection verification differs")
    if manifest["channel"] == "shared":
        publication = validate_publication(
            ctx,
            {"publication_receipt_ref": manifest.get("publication_receipt_ref"),
             "knowledge_commit": manifest.get("publication", {}).get("payload", {}).get("knowledge_commit")},
            cards,
            manifest.get("qualifications", {}),
            "historical" if purpose == "historical" else "current",
        )
        ctx.publication_verification_tier = publication["verification_tier"]
        stored_payload = (manifest.get("publication") or {}).get("payload", {})
        if any(stored_payload.get(key) != value for key, value in publication["payload"].items()):
            raise NodeError(
                "PUBLICATION_CHANGED",
                "Generation repository snapshot differs from its declared input",
            )
        if (manifest.get("publication_receipt_ref")
                and manifest.get("publication", {}).get("adapter_id") is not None
                and manifest.get("publication", {}).get("adapter_id") != publication.get("adapter_id")):
            raise NodeError("PUBLICATION_CHANGED", "Publication adapter identity changed")
    observed = VerifiedGeneration(
        ctx.root.resolve(), ctx.args.rules_digest, ref, manifest, tuple(cards),
        safe(ctx.root, manifest["database_ref"], [prefix]),
        tuple(sorted(fingerprints.items())),
    )
    # Detect modifications while the expensive logical verification was running.
    reuse_generation(ctx, ref, observed)
    return observed


def verify(ctx, ref, purpose="current", *, verified_generation=None):
    if verified_generation is not None:
        return reuse_generation(ctx, ref, verified_generation)
    return verify_generation(ctx, ref, purpose).manifest


def execute(ctx, *, verified_generation=None, verified_regression=None):
    request, action = ctx.request, ctx.args.action or "build"
    channel = request.get("channel", "local")
    if channel not in ("local", "shared"):
        raise NodeError("INVALID_CHANNEL", channel)
    if action in ("verify", "activate"):
        ref = request["generation_ref"]
        observed = verified_generation or verify_generation(ctx, ref, request.get("purpose", "current"))
        ctx.verified_generation = observed
        manifest = reuse_generation(ctx, ref, observed)
        if action == "activate":
            expected_baseline(ctx, manifest, request)
            execution = None
            if verified_regression is not None:
                from .query_regression import reuse_regression
                execution = reuse_regression(ctx, ref, manifest, verified_regression)
            with writer(ctx):
                check_transactions(ctx)
                manifest = reuse_generation(ctx, ref, observed)
                current = active(ctx, manifest["channel"])
                actual = current["digest"] if current else None
                if request["expected_active"] != actual:
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
                if manifest.get("input_snapshot"):
                    comparison = input_snapshot.compare_inputs(ctx, manifest["input_snapshot"], stage="postwrite")
                    if not comparison["unchanged"]:
                        raise NodeError("GENERATION_STALE", "Business inputs changed before activation", blocked=True)
                pointer = ctx.seal(
                    {
                        "channel": manifest["channel"],
                        "generation_id": manifest["generation_id"],
                        "generation_ref": ref,
                        "manifest_digest": manifest["digest"],
                        "previous_active_digest": actual,
                        **({"execution_binding": execution} if execution is not None else {}),
                    },
                    "index_manifest",
                )
                if current is not None:
                    write_bytes(ctx.root, activation_path(manifest["channel"], current["digest"]), canonical(current))
                # A history file without a path from the real active pointer is
                # merely a prepared write, never proof of an activation.
                write_bytes(ctx.root, activation_path(manifest["channel"], pointer["digest"]), canonical(pointer))
                write_bytes(
                    ctx.root,
                    f"artifacts/indexes/{manifest['channel']}/active.json",
                    canonical(pointer),
                    immutable=False,
                )
                # The query report precedes this CAS. Preserve the successful
                # local activation even when a later generation becomes active.
                actual_pointer = read_json(safe(ctx.root, f"artifacts/indexes/{manifest['channel']}/active.json"))
                if actual_pointer != pointer:
                    raise NodeError("ACTIVE_CHANGED", "Active pointer changed before observation", blocked=True)
                observed = ctx.seal({
                    "purpose": "index_activation_observation", "generation_ref": ref,
                    "manifest_digest": manifest["digest"], "expected_active": request["expected_active"],
                    "active_digest": pointer["digest"], "active_pointer": pointer,
                }, "artifact_manifest")
                observation_ref = ctx.base + "/activation/" + observed["digest"] + ".json"
                ctx.save(observation_ref, observed)
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
            **({"activation_observation_ref": observation_ref} if action == "activate" else {}),
            "verification_tier": ctx.publication_verification_tier if manifest["channel"] == "shared" else "content_index",
        }, "activated" if action == "activate" else "verified"
    if action != "build":
        raise NodeError("INVALID_ACTION", action)
    with writer(ctx):
        check_transactions(ctx)
        files = baseline(ctx)
        epoch = state(ctx)["validity_epoch"]
        previous = active(ctx, channel)
        if ("expected_active" in request
                and request["expected_active"] != (previous["digest"] if previous else None)):
            raise NodeError("ACTIVE_CHANGED", "Index build replaces the original active baseline", blocked=True)
        captured_inputs = request.get("input_snapshot") or input_snapshot.capture_inputs(ctx, stage="postwrite")
        comparison = input_snapshot.compare_inputs(ctx, captured_inputs, stage="postwrite")
        if not comparison["unchanged"]:
            raise NodeError("KNOWLEDGE_CHANGED", "Index inputs differ from their postwrite snapshot", blocked=True)
        cards = []
        for path in files:
            if not path.startswith("knowledge/") or Path(path).name in (
                "AGENTS.md",
                "index.md",
            ):
                continue
            card = ctx.modules["knowledge"].decode_card(
                fixed_bytes(ctx.root, path), path, ctx.rules
            )
            if card["metadata"]["lifecycle"] not in ("stable", "deprecated"):
                continue
            cards.append(card)
        if len({card["metadata"]["id"] for card in cards}) != len(cards):
            raise NodeError("DUPLICATE_CARD_ID", "An index requires unique document IDs")
        # Qualifications in older manifests are provenance metadata. Building an
        # index checks the current cards and source lock, not prior workflow runs.
        qualifications = {}
        contexts = code_contexts(ctx, cards, request)
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
                "code_contexts": contexts,
                "publication": publication,
                "input_snapshot_digest": captured_inputs["snapshot_digest"],
            }
        )[:24]
    )
    prefix = f"artifacts/indexes/{channel}/{generation}"
    manifest_ref = prefix + "/manifest.json"
    if safe(ctx.root, manifest_ref).exists():
        observed = verify_generation(ctx, manifest_ref)
        ctx.verified_generation = observed
        manifest = observed.manifest
        if "expected_active" in request:
            expected_baseline(ctx, manifest, request)
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
        database_observation = ctx.modules["indexing"].build_database(cards, ctx.args.rules_digest, db_name, verified=True)
        verification = dict(database_observation.summary)
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
    code_contexts(ctx, cards, {"code_contexts": contexts})
    manifest = ctx.seal(
        {
            "generation_id": generation,
            "channel": channel,
            "database_ref": database_ref,
            "database_digest": sha(database),
            "documents": documents,
            "qualifications": qualifications,
            "code_contexts": contexts,
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
            "input_snapshot": captured_inputs,
        },
        "index_manifest",
    )
    ctx.save(manifest_ref, manifest)
    ctx.verified_generation = verify_generation(ctx, manifest_ref, verified_database=database_observation)
    return {
        "generation_ref": manifest_ref,
        "generation_id": generation,
        "expected_active": manifest["expected_active"],
    }, "built"
