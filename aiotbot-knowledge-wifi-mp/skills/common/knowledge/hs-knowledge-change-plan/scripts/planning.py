"""Explicit Agent-authored six-decision planning; this code generates no semantic claims."""

from __future__ import annotations

import base64
import copy
from pathlib import PurePosixPath

import yaml

from support import NodeError, digest, fixed_bytes, identifier, load_yaml, safe, sha

PROFILES = {
    "entity": "concepts/entities",
    "flow": "concepts/flows",
    "protocol": "concepts/protocols",
    "rule": "rules",
    "command": "commands",
    "runbook": "runbooks",
    "glossary": "glossaries",
}
DECISIONS = {"create", "update", "merge", "split", "deprecate", "defer"}


def encode_card(card, *, lifecycle=None, replacement=None, reason=None):
    metadata = copy.deepcopy(card["metadata"])
    if lifecycle:
        metadata["lifecycle"] = lifecycle
    if replacement is not None:
        metadata["replacement"] = replacement
    if reason:
        metadata["deprecation_reason"] = reason
    return (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n"
        + card["body"]
    ).encode("utf-8")


def cards_in_root(context):
    cards = {}
    knowledge = safe(context.root, "knowledge")
    if not knowledge.exists():
        return cards
    for path in sorted(knowledge.rglob("*.md")):
        if path.name in {"AGENTS.md", "index.md"}:
            continue
        ref = path.relative_to(context.root).as_posix()
        card = context.modules["knowledge"].parse_card(
            fixed_bytes(context.root, ref), ref, context.rules
        )
        identity = card["metadata"]["id"]
        if identity in cards:
            raise NodeError(
                "DUPLICATE_CARD_ID", "Existing Card ID is duplicated", identity
            )
        cards[identity] = card
    return cards


def merged_sources(context, bundle):
    path = safe(context.root, "governance/sources.lock.yaml")
    lock = (
        load_yaml(path.read_bytes())
        if path.exists()
        else {"schema_version": "2.0", "resources": [], "snapshots": []}
    )
    result = copy.deepcopy(lock)
    for key, id_key in (("resources", "source_id"), ("snapshots", "snapshot_id")):
        items = {item[id_key]: item for item in result.get(key, [])}
        if len(items) != len(result.get(key, [])):
            raise NodeError(
                "DUPLICATE_SOURCE_ID", "Source lock contains duplicate identities"
            )
        for item in bundle[key]:
            previous = items.get(item[id_key])
            if previous and previous != item and key == "snapshots":
                old_content = {k: v for k, v in previous.items() if k not in {"recovery", "local_recovery"}}
                new_content = {k: v for k, v in item.items() if k not in {"recovery", "local_recovery"}}
                old_git = previous.get("recovery", {}).get("kind") == "git"
                new_git = item.get("recovery", {}).get("kind") == "git"
                if old_content == new_content and (old_git or new_git):
                    # Recovery location is not a new semantic source version.
                    # Retain an existing exact Git original; never downgrade it.
                    candidate_snapshot = previous if old_git else item
                    context.modules["source_resources"].recover_snapshot(context.root, candidate_snapshot, allow_local_fallback=False)
                    item = candidate_snapshot
                else:
                    raise NodeError(
                        "SOURCE_IDENTITY_CONFLICT",
                        "Immutable snapshot changed",
                        item[id_key],
                    )
            items[item[id_key]] = item
        result[key] = [items[key] for key in sorted(items)]
    result["schema_version"] = "2.0"
    context.modules["validation"].validate_shape("sources", result, context.rules)
    return result


def candidate(context, value, existing):
    ref = value if isinstance(value, str) else value["path"]
    raw = fixed_bytes(context.root, ref, [".build"])
    card = context.modules["knowledge"].parse_card(raw, ref, context.rules)
    metadata = card["metadata"]
    identity = identifier(metadata["id"])
    target = value.get("target_path") if isinstance(value, dict) else None
    if not target:
        target = (
            existing[identity]["path"]
            if identity in existing
            else ("knowledge/" + PROFILES[metadata["profile"]] + "/" + identity + ".md")
        )
    safe(context.root, target, ["knowledge/" + PROFILES[metadata["profile"]]])
    if PurePosixPath(target).name.casefold() in {
        "agents.md",
        "index.md",
    } or not target.endswith(".md"):
        raise NodeError(
            "UNSAFE_CARD_PATH", "Candidate cannot overwrite a control file", target
        )
    if identity not in existing and safe(context.root, target).exists():
        raise NodeError(
            "TARGET_EXISTS", "A new Card ID cannot overwrite another card path", target
        )
    if identity in existing and target != existing[identity]["path"]:
        raise NodeError(
            "CARD_PATH_CHANGED",
            "Existing Card path moves require an explicit separate migration",
            target,
        )
    card["path"] = target
    return card, ref, sha(raw)


def validate_complete(context, cards, source_lock):
    rules = {**context.rules, "source_lock": source_lock}
    for card in cards.values():
        context.modules["knowledge"].validate_card(card, None, rules)
    context.modules["knowledge"].validate_relations(cards)


def claim_identity(reference, available):
    if "#" in reference:
        identity = tuple(reference.split("#", 1))
        if identity in available:
            return identity
    else:
        matches = [pair for pair in available if pair[1] == reference]
        if len(matches) == 1:
            return matches[0]
    raise NodeError(
        "INVALID_CLAIM_MAPPING", "Use an unambiguous CardID#ClaimID", reference
    )


def execute(context):
    request = context.request
    if context.args.action in {"plan", "review"}:
        from plan_v3 import author_plan, content_review

        return (author_plan if context.args.action == "plan" else content_review)(context, request)
    if context.args.action == "verify":
        plan = context.record(request["plan_ref"], "change_plan")
        if plan["operation_id"] != context.operation:
            raise NodeError("OPERATION_MISMATCH", "Plan belongs to another operation")
        for ref, expected in plan["baseline"].items():
            path = safe(context.root, ref)
            if (sha(path.read_bytes()) if path.exists() else None) != expected:
                raise NodeError("BASELINE_CHANGED", "Plan baseline changed", ref)
        for ref, expected in plan["input_digests"].items():
            if sha(fixed_bytes(context.root, ref, [".build"])) != expected:
                raise NodeError("CANDIDATE_CHANGED", "Agent candidate changed", ref)
        context.call(
            "hs-knowledge-source-capture",
            {"operation_id": context.operation, "bundle_ref": plan["bundle_ref"]},
            "resolve",
        )
        if digest(plan["request"]) != plan["request_digest"]:
            raise NodeError(
                "PLAN_CHANGED", "Original authored request differs from frozen digest"
            )
        reproduced = context.call(context.package.name, plan["request"], "rederive")
        if (
            reproduced["data"].get("plan_ref") != request["plan_ref"]
            or reproduced["data"].get("plan_digest") != plan["digest"]
        ):
            raise NodeError(
                "PLAN_CHANGED",
                "Plan is not reproducible from its exact authored request",
            )
        return {"plan_ref": request["plan_ref"], "plan": plan}, "verified"
    bundle = context.call(
        "hs-knowledge-source-capture",
        {"operation_id": context.operation, "bundle_ref": request["bundle_ref"]},
        "resolve",
    )["data"]["bundle"]
    if bundle["operation_id"] != context.operation:
        raise NodeError(
            "OPERATION_MISMATCH", "Capture and plan must belong to the same operation"
        )
    semantic_plan = None
    if request.get("v3_required"):
        from plan_v3 import bind_plan

        semantic_plan = bind_plan(context, request)
    existing = cards_in_root(context)
    source_lock = merged_sources(context, bundle)
    decisions = request.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise NodeError(
            "DECISIONS_REQUIRED",
            "Every enumerated candidate needs an explicit disposition",
        )
    ids = [identifier(d.get("candidate_id")) for d in decisions]
    if len(ids) != len(set(ids)):
        raise NodeError(
            "DUPLICATE_DISPOSITION", "Candidate has more than one disposition"
        )
    enumerated = request.get("candidate_ids", ids)
    if len(enumerated) != len(set(enumerated)) or set(enumerated) != set(ids):
        raise NodeError(
            "DISPOSITION_COVERAGE", "Enumerated candidates and dispositions differ"
        )
    proposed, input_digests, replaced, dispositions = {}, {}, set(), []
    for decision in decisions:
        normalized_mapping, normalized_retired = {}, []
        action, reason = decision.get("decision"), decision.get("reason")
        if action not in DECISIONS or not isinstance(reason, str) or not reason.strip():
            raise NodeError(
                "INVALID_DECISION",
                "Supported decision and explicit reason are required",
            )
        replaces = decision.get("replaces", [])
        if len(replaces) != len(set(replaces)) or any(
            i not in existing for i in replaces
        ):
            raise NodeError(
                "INVALID_REPLACES",
                "Replacement IDs must identify distinct existing cards",
            )
        authored = [
            candidate(context, value, existing)
            for value in decision.get("card_inputs", [])
        ]
        card_ids = [card["metadata"]["id"] for card, _, _ in authored]
        if len(card_ids) != len(set(card_ids)):
            raise NodeError("DUPLICATE_CARD_ID", "Decision has duplicate Card IDs")
        if action == "defer":
            if authored or replaces:
                raise NodeError("INVALID_DEFER", "Defer cannot carry official changes")
            dispositions.append(
                {
                    "candidate_id": decision["candidate_id"],
                    "decision": action,
                    "reason": reason,
                    "next_step": decision.get("next_step", "unknown"),
                    "owner": decision.get("owner", "unknown"),
                }
            )
            continue
        if action in {"create", "update"} and (len(authored) != 1 or replaces):
            raise NodeError(
                "INVALID_CARDINALITY", "Create/update requires exactly one card"
            )
        if action == "create" and card_ids[0] in existing:
            raise NodeError(
                "TARGET_EXISTS", "Create cannot overwrite an existing Card ID"
            )
        if action == "update" and card_ids[0] not in existing:
            raise NodeError("TARGET_MISSING", "Update must retain an existing Card ID")
        if action == "merge" and (len(authored) != 1 or not replaces):
            raise NodeError(
                "INVALID_CARDINALITY",
                "Merge needs one canonical card and replaced cards",
            )
        if action == "split" and (
            len(authored) < 2
            or len(replaces) != 1
            or any(i in existing for i in card_ids)
        ):
            raise NodeError(
                "INVALID_CARDINALITY", "Split needs one old card and distinct new cards"
            )
        if action == "deprecate" and (authored or not replaces):
            raise NodeError(
                "INVALID_CARDINALITY",
                "Deprecate selects existing cards without new content",
            )
        if action in {"merge", "split"}:
            old_claims = {
                (old, c["id"])
                for old in replaces
                if old not in card_ids
                for c in existing[old]["metadata"]["claims"]
            }
            new_claims = {
                (card["metadata"]["id"], claim["id"])
                for card, _, _ in authored
                for claim in card["metadata"]["claims"]
            }
            mapping, retired = (
                decision.get("claim_mapping", {}),
                decision.get("retired_claim_ids", []),
            )
            mapped_pairs = {
                claim_identity(key, old_claims): targets
                for key, targets in mapping.items()
            }
            retired_pairs = {claim_identity(key, old_claims) for key in retired}
            if (
                set(mapped_pairs) | retired_pairs != old_claims
                or set(mapped_pairs) & retired_pairs
            ):
                raise NodeError(
                    "CLAIM_DESTINATION_REQUIRED",
                    "Every replaced Claim needs a destination or explicit retirement",
                )
            for old_pair, targets in mapped_pairs.items():
                if not targets:
                    raise NodeError(
                        "INVALID_CLAIM_MAPPING", "Mapped Claim needs a destination"
                    )
                normalized_mapping["#".join(old_pair)] = [
                    "#".join(claim_identity(t, new_claims)) for t in targets
                ]
            normalized_retired = sorted("#".join(pair) for pair in retired_pairs)
        for card, ref, content_digest in authored:
            identity = card["metadata"]["id"]
            if identity in proposed:
                raise NodeError(
                    "DUPLICATE_WRITE",
                    "Multiple decisions write the same Card ID",
                    identity,
                )
            proposed[identity] = encode_card(card, lifecycle="stable")
            input_digests[ref] = content_digest
        for identity in replaces:
            if identity in card_ids:
                continue
            if identity in proposed or identity in replaced:
                raise NodeError(
                    "DUPLICATE_WRITE", "Card is replaced more than once", identity
                )
            proposed[identity] = encode_card(
                existing[identity],
                lifecycle="deprecated",
                replacement=card_ids,
                reason=reason,
            )
            replaced.add(identity)
        for value in decision.get("related_card_inputs", []):
            card, ref, content_digest = candidate(context, value, existing)
            identity = card["metadata"]["id"]
            if identity not in existing or identity in proposed:
                raise NodeError(
                    "INVALID_IMPACT_WRITE",
                    "Related edit must update one distinct existing card",
                )
            proposed[identity] = encode_card(card, lifecycle="stable")
            input_digests[ref] = content_digest
        dispositions.append(
            {
                "candidate_id": decision["candidate_id"],
                "decision": action,
                "reason": reason,
                "card_ids": card_ids,
                "replaces": replaces,
                "claim_mapping": normalized_mapping,
                "retired_claim_ids": normalized_retired,
            }
        )
    complete = dict(existing)
    writes = []
    for identity, raw in proposed.items():
        parsed = next(
            (
                c
                for d in decisions
                for value in d.get("card_inputs", [])
                for c, _, _ in [candidate(context, value, existing)]
                if c["metadata"]["id"] == identity
            ),
            existing.get(identity),
        )
        if parsed is None:
            # related edits have an existing destination.
            raise NodeError(
                "INVALID_TARGET", "Card destination is not resolvable", identity
            )
        target = parsed["path"]
        if any(w["path"].casefold() == target.casefold() for w in writes):
            raise NodeError("DUPLICATE_WRITE", "Card destinations overlap", target)
        final = context.modules["knowledge"].parse_card(raw, target, context.rules)
        captured_ids = {snapshot["snapshot_id"] for snapshot in bundle["snapshots"]}
        for source in final["metadata"]["sources"]:
            resolution = {"operation_id": context.operation, "source_ref": source}
            if source["snapshot_id"] in captured_ids:
                resolution["bundle_ref"] = request["bundle_ref"]
            context.call("hs-knowledge-source-capture", resolution, "resolve-source")
        complete[identity] = final
        prior = safe(context.root, target)
        expected = sha(prior.read_bytes()) if prior.exists() else None
        writes.append(
            {
                "path": target,
                "expected_old_digest": expected,
                "final_digest": sha(raw),
                "bytes_b64": base64.b64encode(raw).decode(),
            }
        )
    for card in complete.values():
        if card["metadata"]["lifecycle"] != "stable":
            continue
        for relation in card["metadata"].get("relations", []):
            if (
                relation["type"] in {"requires", "replacement"}
                and relation["target_card_id"] in replaced
            ):
                raise NodeError(
                    "IMPACT_CLOSURE_REQUIRED",
                    "Stable dependency still points to a replaced card",
                    card["metadata"]["id"],
                )
    validate_complete(context, complete, source_lock)
    if semantic_plan:
        declared = {row["card_id"]: row for row in semantic_plan["card_actions"]}
        if set(proposed) != set(declared):
            raise NodeError("PLAN_WRITE_COVERAGE", "Draft targets differ from the authored card plan")
        for decision in dispositions:
            for card_id in decision.get("card_ids", []):
                if declared[card_id]["decision"] != decision["decision"]:
                    raise NodeError("PLAN_ACTION_MISMATCH", "Draft card action differs from authored plan", card_id)
        for change in semantic_plan["claim_changes"]:
            if change["action"] in {"create", "update"} and change["claim_id"] not in {
                c["id"] for c in complete[change["card_id"]]["claims"]
            }:
                raise NodeError("PLAN_CLAIM_MISSING", "Planned Claim is absent from the final draft")
            if change["action"] == "preserve":
                identity, claim_id = change["card_id"], change["claim_id"]
                before = next((claim for claim in existing.get(identity, {}).get("claims", []) if claim["id"] == claim_id), None)
                after = next((claim for claim in complete.get(identity, {}).get("claims", []) if claim["id"] == claim_id), None)
                if not before or not after or {k: v for k, v in before.items() if k != "span"} != {k: v for k, v in after.items() if k != "span"}:
                    raise NodeError("PRESERVED_CLAIM_CHANGED", "A preserved Claim's content, scope or reference changed without a new judgment", identity + "#" + claim_id)
        for identity, action in declared.items():
            if action["decision"] == "update" and identity in existing:
                judged = {row["claim_id"] for row in semantic_plan["claim_changes"] if row["card_id"] == identity}
                if not {row["id"] for row in existing[identity]["claims"]} <= judged:
                    raise NodeError("OLD_CLAIM_JUDGMENT_REQUIRED", "Every old Claim needs an explicit preserve/change/retire judgment", identity)
    modes = {c["metadata"]["review_mode"] for i, c in complete.items() if i in proposed}
    review_requirements = {
        mode: [c["path"] for i, c in complete.items() if i in proposed and c["metadata"]["review_mode"] == mode]
        for mode in sorted(modes)
    }
    baseline = {p["path"]: p["expected_old_digest"] for p in writes}
    for write in writes:
        index_ref = str(PurePosixPath(write["path"]).parent / "index.md")
        index = safe(context.root, index_ref)
        baseline[index_ref] = sha(index.read_bytes()) if index.exists() else None
    lock = safe(context.root, "governance/sources.lock.yaml")
    baseline["governance/sources.lock.yaml"] = (
        sha(lock.read_bytes()) if lock.exists() else None
    )
    plan = context.seal(
        {
            "bundle_ref": request["bundle_ref"],
            "bundle_digest": bundle["digest"],
            "context_ref": request.get("context_ref", bundle.get("context_ref")),
            "decisions": dispositions,
            "candidate_ids": ids,
            "writes": sorted(writes, key=lambda p: p["path"]),
            "deletes": [],
            "baseline": baseline,
            "input_digests": input_digests,
            "source_lock": source_lock,
            "review_mode": "mixed" if len(modes) > 1 else next(iter(modes), "manual_document"),
            "review_requirements": review_requirements,
            **({"v3_required": True, "semantic_plan_ref": request["semantic_plan_ref"],
                "semantic_plan_digest": semantic_plan["digest"], "scan_ref": semantic_plan["scan_ref"],
                "material_ref": semantic_plan["material_ref"], "target_queries": semantic_plan["target_queries"]}
               if semantic_plan else {}),
            "request_digest": digest(request),
            "request": request,
        },
        "change_plan",
    )
    ref = context.save(context.base + "/plan.json", plan)
    return {
        "plan_ref": ref,
        "plan_digest": plan["digest"],
        "dispositions": dispositions,
    }, ("deferred" if not writes else "planned")
