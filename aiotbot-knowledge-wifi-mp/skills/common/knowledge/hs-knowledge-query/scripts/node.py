"""Claim-qualified lexical retrieval and same-generation reads. No FTS or vector service."""

from __future__ import annotations
from contextlib import closing
import re
import sqlite3
import unicodedata
from support import (
    NodeError,
    digest,
    fixed_bytes,
    read_json,
    safe,
    sha,
)

WEIGHTS = {"title": 5, "aliases": 4, "search_terms": 3, "summary": 2, "body": 1}


def term_groups(text):
    normalized = unicodedata.normalize("NFKC", text)
    result = []
    for match in re.finditer(
        r"[\u3400-\u9fff]+|[^\W\u3400-\u9fff]+", normalized, re.UNICODE
    ):
        word = match.group()
        if re.fullmatch(r"[\u3400-\u9fff]+", word):
            chunks = (
                [word]
                if len(word) == 1
                else [word[i : i + 2] for i in range(len(word) - 1)]
            )
            result.extend([{c} for c in chunks])
        else:
            result.append({word.casefold(), "=" + word})
    unique = {tuple(sorted(group)) for group in result}
    return [set(group) for group in sorted(unique)]


def tokens(text):
    return set().union(*term_groups(text)) if text else set()


def score_card(card, groups, eligible, tokenizer=tokens):
    """Partial eligibility suppresses all unbound card-level header fields."""
    meta, claims = card["metadata"], card["claims"]
    active = [c for c in claims if c["id"] in eligible]
    fields = {
        "body": set().union(*(set(tokenizer(c["text"])) for c in active)) if active else set()
    }
    fields["search_terms"] = set(tokenizer(
        " ".join(term for c in active for term in c.get("search_terms", []))
    ))
    complete = len(active) == len(claims) and bool(active)
    if complete:
        fields.update(
            title=set(tokenizer(meta["title"])),
            summary=set(tokenizer(meta["summary"])),
            aliases=set(tokenizer(" ".join(meta.get("aliases", [])))),
        )
        fields["search_terms"] |= set(tokenizer(" ".join(meta.get("search_terms", []))))
    score = sum(
        weight
        for name, weight in WEIGHTS.items()
        for group in groups
        if group & fields.get(name, set())
    )
    return score, complete


def event_state(ctx):
    path = safe(ctx.root, "logs/events/state.json")
    value = {"validity_epoch": 0, "blocked_claims": []}
    if path.exists():
        value = read_json(path)
        ctx.modules["records"].verify(value)
        if value.get("record_kind") != "maintenance_state":
            raise NodeError("INVALID_EVENT_STATE", "Wrong validity-state identity")
    records = []
    directory = safe(ctx.root, "logs/ingest")
    if directory.exists():
        for entry in sorted(directory.iterdir()):
            if entry.suffix not in {".yaml", ".yml", ".json"}:
                continue
            ref = entry.relative_to(ctx.root).as_posix()
            records.append(ctx.modules["validation"].load_yaml(fixed_bytes(ctx.root, ref, ["logs/ingest"])))
    shared = ctx.modules["records"].rebuild_restrictions(records, ctx.rules, cards=getattr(ctx, "processing_cards", None))
    if not shared["complete"]:
        raise NodeError("PROCESSING_STATE_UNAVAILABLE", str(shared["gaps"]), blocked=True)
    return {**value, "blocked_claims": value.get("blocked_claims", []) + shared["blocked_claims"],
            "processing_digest": digest({"records": sorted(row["digest"] for row in records), "blocks": shared["blocked_claims"]})}


def validity_observation(state):
    return state["validity_epoch"], state.get("processing_digest")


def blocked(
    claim,
    card_id,
    state,
    context,
    scope_matcher,
    current_code_verified=False,
    code_sources=(),
):
    for entry in state.get("blocked_claims", []):
        if entry.get("card_id") not in (card_id, "*") or entry.get("claim_id") not in (
            claim["id"],
            "*",
        ):
            continue
        old = set(entry.get("old_snapshot_ids", []))
        references = claim.get("source_records", [])
        if (
            old
            and references
            and not old.intersection(source["snapshot_id"] for source in references)
        ):
            continue
        changed_sources = (
            {entry["source_id"]}
            if entry.get("source_id")
            else {
                source["source_id"]
                for source in references
                if source["snapshot_id"] in old
            }
        )
        if (
            current_code_verified
            and changed_sources
            and changed_sources.issubset(code_sources)
            and entry.get("reason")
            in {"source_changed", "code_changed", "code_source_changed"}
        ):
            # A new bound independently reviewed same-view proof can supersede stale code
            # identity, never a raw-source or arbitrary semantic block.
            continue
        conditions = entry.get("conditions") or {}
        if "applicability" in conditions:
            matches = conditions["applicability"] == "unknown" or scope_matcher(
                {"usage": "current", "scope": conditions}, context, "current"
            )
        else:
            matches = all(
                context.get(key) == value for key, value in conditions.items()
            )
        if matches:
            return True
    return False


def read_search_binding(ctx, request):
    """Receipt integrity/lineage only; live application proofs remain mandatory."""
    receipt = ctx.record(request["receipt_ref"], "search_receipt")
    binding, result = receipt.get("request_binding"), receipt.get("result")
    if (
        not isinstance(binding, dict)
        or not isinstance(result, dict)
        or receipt.get("result_status") != "ok"
        or binding.get("action") != "search"
        or receipt.get("evaluation") is not False
        or binding.get("evaluation") is not False
        or receipt.get("request_digest") != digest(binding)
        or receipt.get("result_digest") != digest(result)
        or not isinstance(binding.get("query"), str)
        or not binding["query"].strip()
        or result.get("query") != binding["query"]
        or receipt.get("tool_identity", {}).get("skill") != "hs-knowledge-query"
    ):
        raise NodeError(
            "INVALID_SEARCH_RECEIPT",
            "A successful formal search record with intact request/result bindings is required",
        )
    for key, value in (
        ("channel", receipt.get("channel")),
        ("generation_ref", receipt.get("generation_ref")),
    ):
        if binding.get(key) != value:
            raise NodeError(
                "INVALID_SEARCH_RECEIPT", "Search generation/channel binding differs"
            )
    effective = dict(request)
    for key in ("channel", "generation_ref", "purpose", "context"):
        if key not in binding:
            raise NodeError(
                "INVALID_SEARCH_RECEIPT",
                "Search lacks an explicit effective binding",
                key,
            )
        if key in request and digest(request[key]) != digest(binding[key]):
            raise NodeError(
                "SEARCH_RECEIPT_SCOPE_MISMATCH",
                "Read must keep the original search generation/channel/purpose/context",
                key,
            )
        effective[key] = binding[key]
    if request.get("evaluation") not in (None, False):
        raise NodeError(
            "SEARCH_RECEIPT_SCOPE_MISMATCH",
            "Formal receipt reads cannot change evaluation mode",
        )
    effective["evaluation"] = False
    rows = [
        row
        for row in result.get("matches", [])
        if row.get("card_id") == request.get("card_id")
    ]
    if len(rows) != 1:
        raise NodeError(
            "CARD_NOT_IN_SEARCH", "Read card must be an original search hit"
        )
    hit = rows[0]
    original = hit.get("claim_ids")
    selected = request.get("claim_ids", original)
    if (
        not isinstance(original, list)
        or not original
        or len(original) != len(set(original))
        or not isinstance(selected, list)
        or not selected
        or len(selected) != len(set(selected))
        or not set(selected).issubset(original)
        or not re.fullmatch(r"[0-9a-f]{64}", str(hit.get("card_digest", "")))
    ):
        raise NodeError(
            "INVALID_SEARCH_CLAIMS",
            "Read claims must be a nonempty subset of the exact original hit",
        )
    effective["claim_ids"] = selected
    return effective, receipt, hit


def request_binding(request, action, generation_ref):
    context = request.get("context", {})
    if not isinstance(context, dict):
        raise NodeError("INVALID_QUERY_CONTEXT", "Query context must be an object")
    binding = {
        "action": action,
        "channel": request.get("channel", "local"),
        "purpose": request.get("purpose", "current"),
        "context": context,
        "evaluation": bool(request.get("evaluation")),
        "generation_ref": generation_ref,
    }
    if action in ("search", "receipt"):
        binding.update(
            query=request.get("query"),
            top_k=request.get("top_k", 5),
            scan_limit=request.get("scan_limit", 10000),
        )
    else:
        binding.update(
            card_id=request.get("card_id"),
            claim_ids=request.get("claim_ids"),
            receipt_ref=request.get("receipt_ref"),
        )
    return binding


def load_generation(ctx, request, search_receipt=None):
    channel = request.get("channel", "local")
    if channel not in ("local", "shared"):
        raise NodeError("INVALID_CHANNEL", channel)
    explicit = request.get("generation_ref")
    if explicit and not request.get("evaluation") and search_receipt is None:
        raise NodeError(
            "UNACTIVATED_GENERATION", "Explicit candidate generation is evaluation-only"
        )
    active = None
    if search_receipt is not None:
        active = search_receipt.get("active_pointer_observation")
        if not isinstance(active, dict):
            raise NodeError(
                "INVALID_SEARCH_RECEIPT",
                "Formal search must retain its actual active-pointer observation",
            )
        ctx.modules["records"].verify(active)
        if (
            active.get("record_kind") != "index_manifest"
            or active.get("rules_digest") != ctx.args.rules_digest
        ):
            raise NodeError(
                "INVALID_SEARCH_RECEIPT",
                "Active observation has the wrong rule or record identity",
            )
    elif not explicit:
        active_ref = f"artifacts/indexes/{channel}/active.json"
        active = ctx.record(active_ref, "index_manifest")
        explicit = active["generation_ref"]
    manifest = ctx.record(explicit, "index_manifest")
    if active and (
        active.get("generation_ref") != explicit
        or active.get("generation_id") != manifest.get("generation_id")
        or active.get("channel") != channel
        or active.get("manifest_digest") != manifest.get("digest")
    ):
        raise NodeError(
            "GENERATION_LINEAGE_MISMATCH",
            "Active-pointer observation differs from the exact generation manifest",
        )
    if search_receipt is not None and (
        search_receipt.get("generation_manifest_digest") != manifest.get("digest")
        or search_receipt.get("generation_id") != manifest.get("generation_id")
    ):
        raise NodeError(
            "GENERATION_LINEAGE_MISMATCH", "Original search generation content changed"
        )
    if manifest.get("channel") != channel or not explicit.startswith(
        f"artifacts/indexes/{channel}/"
    ):
        raise NodeError(
            "GENERATION_CHANNEL_MISMATCH", "Generation is outside selected channel"
        )
    if channel == "shared":
        verified = ctx.call(
            "hs-knowledge-index-build",
            {
                "operation_id": ctx.operation,
                "generation_ref": explicit,
                "purpose": request.get("purpose", "current"),
            },
            "verify",
        )["data"]
        if (
            verified.get("verified") is not True
            or verified.get("generation_ref") != explicit
        ):
            raise NodeError(
                "PUBLICATION_NOT_VERIFIED",
                "Shared publication was not authenticated",
                blocked=True,
            )
    db = safe(ctx.root, manifest["database_ref"], [f"artifacts/indexes/{channel}"])
    if sha(db.read_bytes()) != manifest["database_digest"]:
        raise NodeError("INDEX_CHANGED", "Frozen database differs from manifest")
    ctx.processing_cards = [{"path": row["path"], "metadata": {"id": card_id}} for card_id, row in manifest["documents"].items()]
    return explicit, manifest, db, active


def load_card(ctx, manifest, card_id, purpose="current"):
    row = manifest["documents"].get(card_id)
    if not row:
        raise NodeError("CARD_NOT_IN_GENERATION", card_id)
    raw = fixed_bytes(ctx.root, row["blob_ref"], ["artifacts/indexes"])
    if sha(raw) != row["sha256"]:
        raise NodeError("CARD_BLOB_CHANGED", card_id)
    proof = manifest.get("qualifications", {}).get(card_id)
    if not proof:
        raise NodeError(
            "CARD_PROOF_MISSING",
            "Generation lacks authenticated card qualification",
            card_id,
            blocked=True,
        )
    if proof.get("kind") == "accepted_repository":
        if manifest.get("channel") != "shared" or not manifest.get("publication"):
            raise NodeError("ACCEPTED_REPOSITORY_REQUIRED", "Portable qualification needs authenticated shared publication")
        # load_generation has revalidated the trusted publication signature,
        # exact commit blobs and acceptance summaries through index-build verify.
        card = ctx.modules["indexing"].read_document(raw, row["path"], ctx.rules, card_id=card_id, sha256=row["sha256"])
        code_current = True
        if card["metadata"]["review_mode"] == "code_gate" and purpose != "historical":
            config = ctx.root.parent / "config.yml"
            try:
                catalog = read_json(ctx.args.catalog)
                ctx.modules["source_resources"].validate_current_code_identity(
                    proof.get("code_identity"), config, proof.get("config_digest"),
                    ctx.rules, catalog.get("code_policy"),
                )
            except (ValueError, OSError, KeyError) as exc:
                code_current = False
                card["_context_gaps"] = [{"code": "CURRENT_CODE_CONTEXT_CHANGED_OR_UNKNOWN", "card_id": card_id, "reason": str(exc)}]
        card["_portable_context_current"] = code_current
        card["_portable_qualification"] = True
        card["_current_code_verified"] = code_current and card["metadata"]["review_mode"] == "code_gate"
        return card
    verification_purpose = "historical" if purpose == "historical" else "current"
    response = ctx.call(
        "hs-knowledge-apply",
        {
            "operation_id": proof["operation_id"],
            "apply_result_ref": proof["apply_result_ref"],
            "card_path": row["path"],
            "card_digest": row["sha256"],
            "purpose": verification_purpose,
            **(
                {"current_code_proof_ref": proof["current_code_proof_ref"]}
                if verification_purpose == "current"
                and proof.get("current_code_proof_ref")
                else {}
            ),
        },
        "verify-result",
    )
    if not response["data"].get("result_verified") or not any(
        f["path"] == row["path"] and f["sha256"] == row["sha256"]
        for f in response["data"].get(
            "historical_files"
            if verification_purpose == "historical"
            else "eligible_files",
            [],
        )
    ):
        raise NodeError(
            "CARD_PROOF_INVALID",
            "Content is no longer qualified",
            card_id,
            blocked=True,
        )
    card = ctx.modules["indexing"].read_document(
        raw, row["path"], ctx.rules, card_id=card_id, sha256=row["sha256"]
    )
    if card["metadata"]["id"] != card_id:
        raise NodeError(
            "GENERATION_CARD_ID_MISMATCH",
            "Generation key differs from exact card identity",
            card_id,
        )
    card["_current_code_verified"] = (
        verification_purpose == "current"
        and card["metadata"]["review_mode"] == "code_gate"
    )
    return card


def qualified_claims(ctx, card, request, state, code_sources=()):
    purpose, context = request.get("purpose", "current"), request.get("context", {})
    if purpose not in ("current", "implementation", "guidance", "historical"):
        raise NodeError("INVALID_PURPOSE", purpose)
    if card["metadata"]["lifecycle"] == "deprecated" and purpose != "historical":
        return set()
    if purpose in {"current", "implementation"} and card.get("_portable_context_current") is False:
        return set()
    return {
        claim["id"]
        for claim in card["claims"]
        if ctx.modules["knowledge"].match_scope(claim, context, purpose)
        and (
            purpose not in ("current", "implementation")
            or not blocked(
                claim,
                card["metadata"]["id"],
                state,
                context,
                ctx.modules["knowledge"].match_scope,
                card.get("_current_code_verified", False),
                code_sources,
            )
        )
    }


def qualify_sources(ctx, card, eligible, purpose, cache, code_sources=()):
    accepted, resolutions, gaps = set(), {}, []
    for claim in card["claims"]:
        if claim["id"] not in eligible:
            continue
        usable = True
        for source in claim["source_records"]:
            key = digest(source)
            if key not in cache:
                try:
                    cache[key] = ctx.call(
                        "hs-knowledge-source-capture",
                        {"operation_id": ctx.operation, "source_ref": source},
                        "resolve-source",
                    )["data"]
                except (ValueError, OSError) as exc:
                    cache[key] = {
                        "source_ref": source,
                        "unavailable": True,
                        "limitations": [str(exc)],
                    }
            result = cache[key]
            resolutions[key] = result
            if result.get("unavailable") or (
                purpose in ("current", "implementation")
                and result.get("current_source_matches") is not True
                and not (
                    source["source_id"] in code_sources
                    and card.get("_current_code_verified") is True
                    and not card.get("_portable_qualification")
                )
            ):
                usable = False
                gaps.append(
                    {
                        "code": "SOURCE_NOT_CURRENT",
                        "card_id": card["metadata"]["id"],
                        "claim_id": claim["id"],
                        "source_ref": source,
                    }
                )
        if usable:
            accepted.add(claim["id"])
    selected_keys = {
        digest(source)
        for claim in card["claims"]
        if claim["id"] in accepted
        for source in claim["source_records"]
    }
    return (
        accepted,
        [
            {
                **resolutions[key],
                "current_code_verified": bool(
                    card.get("_current_code_verified")
                    and resolutions[key]["source_ref"]["source_id"] in code_sources
                    and not card.get("_portable_qualification")
                ),
            }
            for key in sorted(selected_keys)
        ],
        gaps,
    )


def refresh_sources(ctx, sources, purpose, code_sources=()):
    result = []
    for source in sources:
        fresh = ctx.call(
            "hs-knowledge-source-capture",
            {"operation_id": ctx.operation, "source_ref": source["source_ref"]},
            "resolve-source",
        )["data"]
        if (
            fresh.get("snapshot_digest") != source.get("snapshot_digest")
            or fresh.get("current_source_sha256") != source.get("current_source_sha256")
            or (
                purpose in ("current", "implementation")
                and fresh.get("current_source_matches") is not True
                and not (
                    source["source_ref"]["source_id"] in code_sources
                    and source.get("current_code_verified") is True
                )
            )
        ):
            raise NodeError(
                "SOURCE_CHANGED_DURING_QUERY",
                "A source changed after candidate qualification; retry",
                blocked=True,
            )
        result.append(fresh)
    return result


class EligibilityEvaluator:
    """One immutable generation, context and live epoch; dependencies are not lexical candidates."""

    def __init__(self, ctx, manifest, request, state):
        self.ctx, self.manifest, self.request, self.state = (
            ctx,
            manifest,
            request,
            state,
        )
        self.purpose = request.get("purpose", "current")
        self.context = request.get("context", {})
        lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
        self.code_sources = {
            row["source_id"] for row in lock["resources"] if row["kind"] == "code"
        }
        self.cache, self.visiting, self.sources = {}, set(), {}

    def relation_applies(self, card, relation):
        ids = relation.get("context_ids", [])
        if not ids:
            return True
        contexts = [
            row
            for row in card["metadata"]["scope"]["contexts"]
            if row["context_id"] in ids
        ]
        return self.ctx.modules["knowledge"].match_scope(
            {
                "usage": "current",
                "scope": {"applicability": "constrained", "contexts": contexts},
            },
            self.context,
            "current",
        )

    def evaluate(self, card_id):
        if card_id in self.cache:
            return self.cache[card_id]
        if card_id in self.visiting or len(self.visiting) >= 256:
            return (
                None,
                set(),
                [],
                [{"code": "DEPENDENCY_CYCLE_OR_DEPTH", "card_id": card_id}],
            )
        self.visiting.add(card_id)
        try:
            card = load_card(self.ctx, self.manifest, card_id, self.purpose)
            eligible = qualified_claims(
                self.ctx, card, self.request, self.state, self.code_sources
            )
            eligible, sources, gaps = qualify_sources(
                self.ctx, card, eligible, self.purpose, self.sources, self.code_sources
            )
            gaps.extend(card.get("_context_gaps", []))
            if self.purpose in {"guidance", "historical"}:
                pending = [row for row in self.state.get("blocked_claims", []) if row.get("reason") == "shared_pending_review"]
                for claim in card["claims"]:
                    if claim["id"] in eligible and blocked(claim, card_id, {"blocked_claims": pending}, self.context, self.ctx.modules["knowledge"].match_scope):
                        gaps.append({"code": "SHARED_PENDING_REVIEW", "card_id": card_id, "claim_id": claim["id"], "purpose": self.purpose})
            for relation in card["metadata"]["relations"]:
                if relation["type"] not in {
                    "requires",
                    "derived_from",
                } or not self.relation_applies(card, relation):
                    continue
                target_id = relation["target_card_id"]
                target, target_claims, target_sources, target_gaps = self.evaluate(
                    target_id
                )
                claim_id = relation.get("target_claim_id")
                relevant = (
                    {
                        claim["id"]
                        for claim in target["claims"]
                        if self.ctx.modules["knowledge"].match_scope(
                            claim, self.context, self.purpose
                        )
                    }
                    if target
                    else set()
                )
                required = {claim_id} if claim_id else relevant
                if not required or not required.issubset(target_claims):
                    eligible.clear()
                    gaps.append(
                        {
                            "code": "DEPENDENCY_NOT_QUALIFIED",
                            "card_id": card_id,
                            "target_card_id": target_id,
                            "target_claim_id": claim_id,
                        }
                    )
                else:
                    sources.extend(target_sources)
                gaps.extend(target_gaps)
            result = (
                card,
                eligible,
                list({digest(row["source_ref"]): row for row in sources}.values()),
                gaps,
            )
        except (ValueError, OSError, KeyError) as exc:
            result = (
                None,
                set(),
                [],
                [
                    {
                        "code": "CARD_NOT_QUALIFIED",
                        "card_id": card_id,
                        "reason": str(exc),
                    }
                ],
            )
        finally:
            self.visiting.remove(card_id)
        self.cache[card_id] = result
        return result


def execute(ctx):
    request = ctx.request
    action = ctx.args.action or "search"
    search_receipt, original_hit = None, None
    if action == "read" and request.get("receipt_ref"):
        request, search_receipt, original_hit = read_search_binding(ctx, request)
    generation_ref, manifest, db, active_observation = load_generation(
        ctx, request, search_receipt
    )
    binding = request_binding(request, action, generation_ref)
    initial_state = event_state(ctx)
    epoch = initial_state["validity_epoch"]
    observation = validity_observation(initial_state)
    matches, truncated = [], False
    source_gaps = []
    evaluator = EligibilityEvaluator(ctx, manifest, request, initial_state)
    if action in ("search", "receipt"):
        query = request.get("query", "")
        if not isinstance(query, str) or not query.strip():
            raise NodeError("QUERY_REQUIRED", "Nonempty query required")
        groups = ctx.modules["indexing"].term_groups(query)
        terms = sorted(set().union(*groups)) if groups else []
        top_k = request.get("top_k", 5)
        scan_limit = request.get("scan_limit", 10000)
        if (
            not isinstance(top_k, int)
            or not 1 <= top_k <= 100
            or not isinstance(scan_limit, int)
            or not 1 <= scan_limit <= 100000
        ):
            raise NodeError("INVALID_QUERY_BUDGET", "Invalid top_k or scan_limit")
        with closing(
            sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True)
        ) as connection:
            ids = (
                []
                if not terms
                else [
                    r[0]
                    for r in connection.execute(
                        "SELECT DISTINCT card_id FROM postings WHERE token IN ("
                        + ",".join("?" for _ in terms)
                        + ") ORDER BY card_id",
                        terms,
                    )
                ]
            )
        if len(ids) > scan_limit:
            ids, truncated = ids[:scan_limit], True
        for card_id in ids:
            card, eligible, sources, gaps = evaluator.evaluate(card_id)
            source_gaps.extend(gaps)
            if card is None:
                continue
            score, complete = score_card(card, groups, eligible, ctx.modules["indexing"].lexical)
            if eligible and score:
                matches.append(
                    {
                        "card_id": card_id,
                        "score": score,
                        "claim_ids": sorted(eligible),
                        "title": card["metadata"]["title"] if complete else card_id,
                        "summary": card["metadata"]["summary"] if complete else None,
                        "path": manifest["documents"][card_id]["path"],
                        "card_digest": manifest["documents"][card_id]["sha256"],
                    }
                )
        matches.sort(key=lambda row: (-row["score"], row["card_id"]))
        matches = matches[:top_k]
        if validity_observation(event_state(ctx)) != observation:
            raise NodeError(
                "VALIDITY_CHANGED", "Validity changed during ranking", blocked=True
            )
        fresh = EligibilityEvaluator(ctx, manifest, request, event_state(ctx))
        for match in matches:
            _, current_claims, sources, _ = fresh.evaluate(match["card_id"])
            if current_claims != set(match["claim_ids"]):
                raise NodeError(
                    "QUALIFICATION_CHANGED",
                    "Card or dependency qualification changed before output; retry",
                    blocked=True,
                )
            match["sources"] = refresh_sources(
                ctx, sources, request.get("purpose", "current"), fresh.code_sources
            )
        data = {
            "matches": matches,
            "candidate_scan_truncated": truncated,
            "gaps": (["candidate_scan_truncated"] if truncated else []) + source_gaps,
            "query": query,
        }
    elif action == "read":
        if original_hit is not None:
            row = manifest["documents"].get(request.get("card_id"), {})
            if row.get("sha256") != original_hit["card_digest"] or row.get(
                "path"
            ) != original_hit.get("path"):
                raise NodeError(
                    "SEARCH_CARD_CHANGED",
                    "Original search hit differs from same-generation exact card bytes",
                )
        card, eligible, sources, gaps = evaluator.evaluate(request.get("card_id", ""))
        authorized_claims = (
            set(request["claim_ids"]) if search_receipt is not None else None
        )
        if authorized_claims is not None:
            eligible &= authorized_claims
        if not eligible:
            raise NodeError(
                "NO_ELIGIBLE_CLAIMS", "Card has no eligible claims", blocked=True
            )
        selected_source_keys = {
            digest(source)
            for claim in card["claims"]
            if claim["id"] in eligible
            for source in claim["source_records"]
        }
        sources = [
            source
            for source in sources
            if digest(source["source_ref"]) in selected_source_keys
        ]
        gaps = [
            gap
            for gap in gaps
            if not isinstance(gap, dict)
            or not gap.get("claim_id")
            or gap["claim_id"] in eligible
        ]
        data = {
            "card_id": card["metadata"]["id"],
            "claims": [
                {
                    "id": c["id"],
                    "text": c["text"],
                    "span": c["span"],
                    "usage": c["usage"],
                }
                for c in card["claims"]
                if c["id"] in eligible
            ],
            "sources": refresh_sources(
                ctx, sources, request.get("purpose", "current"), evaluator.code_sources
            ),
            "gaps": gaps,
            "card_digest": card["sha256"],
        }
        fresh = EligibilityEvaluator(ctx, manifest, request, event_state(ctx))
        fresh_claims = fresh.evaluate(card["metadata"]["id"])[1]
        if authorized_claims is not None:
            fresh_claims &= authorized_claims
        if fresh_claims != eligible:
            raise NodeError(
                "QUALIFICATION_CHANGED",
                "Card or dependency qualification changed before read output",
                blocked=True,
            )
        if search_receipt is not None:
            data["source_search_receipt_ref"] = request["receipt_ref"]
    else:
        raise NodeError("INVALID_ACTION", action)
    if validity_observation(event_state(ctx)) != observation:
        raise NodeError(
            "VALIDITY_CHANGED", "Validity changed before output", blocked=True
        )
    receipt = ctx.seal(
        {
            "generation_ref": generation_ref,
            "generation_id": manifest["generation_id"],
            "channel": manifest["channel"],
            "validity_epoch": epoch,
            "processing_digest": initial_state.get("processing_digest"),
            "evaluation": bool(request.get("evaluation")),
            "result_status": "ok",
            "request_binding": binding,
            "request_digest": digest(binding),
            "result_digest": digest(data),
            "result": data,
            "generation_manifest_digest": manifest["digest"],
            "active_pointer_observation": active_observation,
        },
        "search_receipt",
    )
    receipt_ref = ctx.base + "/receipts/" + receipt["digest"] + ".json"
    ctx.save(receipt_ref, receipt)
    data.update(
        receipt_ref=receipt_ref,
        generation_ref=generation_ref,
        generation_id=manifest["generation_id"],
        validity_epoch=epoch,
        processing_digest=initial_state.get("processing_digest"),
        evaluation=bool(request.get("evaluation")),
    )
    return data, "evaluated" if request.get("evaluation") else "queried"
