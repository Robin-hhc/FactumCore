"""P4-only query evaluation over a fully checked, private candidate database.

The observation is an in-process object, never an input request credential.
Ranking, qualifications, source recovery and read behavior remain query_runtime's.
"""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from . import query_runtime
from .runtime import NodeError, digest, fixed_bytes, safe, sha, write_bytes


@dataclass(frozen=True)
class CandidateQuery:
    root: Path
    rules_digest: str
    database: Path
    database_observation: object
    cards: tuple
    bundle: dict
    state: dict
    manifest: dict
    generation_ref: str
    fingerprint: str

    def _identity(self):
        return digest({"cards": {card["metadata"]["id"]: sha(card["raw"]) for card in self.cards},
                       "bundle": self.bundle, "state": self.state, "manifest": self.manifest})

    def verify(self, ctx, *, full=True):
        if self.root != ctx.root.resolve() or self.rules_digest != ctx.args.rules_digest:
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate query inputs changed after validation")
        database_ref = self.database.relative_to(ctx.root).as_posix()
        if sha(fixed_bytes(ctx.root, database_ref, [ctx.operation_root])) != self.database_observation.database_digest:
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate database changed after full verification")
        if not full:
            return
        if self._identity() != self.fingerprint:
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate query inputs changed after validation")
        ctx.modules["indexing"].reuse_database(list(self.cards), self.rules_digest,
                                              self.database, self.database_observation)
        for row in self.manifest["documents"].values():
            if sha(fixed_bytes(ctx.root, row["blob_ref"], [ctx.operation_root])) != row["sha256"]:
                raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate card changed after validation", row["path"])
        for entry in self.bundle.get("staged_objects", []):
            ctx.modules["staging"].read_bytes(ctx.root, entry["final_ref"], self.bundle["staged_objects"],
                expected_sha=entry["sha256"], expected_size=entry["bytes"])

    def load_generation(self, ctx, request, search_receipt):
        if request.get("evaluation") is not True or search_receipt is not None:
            raise NodeError("INVALID_CANDIDATE_QUERY", "Private candidates support evaluation only, never formal receipt reads")
        if request.get("generation_ref") != self.generation_ref or request.get("channel", "local") != "local":
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate generation identity differs")
        self.verify(ctx, full=False)
        ctx.generation_verification_tier = "candidate_query_evaluation"
        return self.generation_ref, self.manifest, self.database, None

    def card_bytes(self, ctx, card_id):
        row = self.manifest["documents"][card_id]
        raw = fixed_bytes(ctx.root, row["blob_ref"], [ctx.operation_root])
        if sha(raw) != row["sha256"]:
            ctx._candidate_input_unavailable = True
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Candidate card bytes changed", row["path"])
        return raw

    def event_state(self, ctx):
        return deepcopy(self.state)


def _prepare(ctx, view, cards, lock, files, database, observed, state, code_contexts):
    name = str(database)
    database = Path("\\\\" + name[8:] if name.startswith("\\\\?\\UNC\\")
                    else name[4:] if name.startswith("\\\\?\\") else name)
    values = list(cards.values())
    ctx.modules["indexing"].reuse_database(values, ctx.args.rules_digest, database, observed)
    entries = ctx.modules["staging"].validate_entries(ctx.root, view.get("staged_objects", []))
    bundle = {**deepcopy(lock), "staged_objects": entries}
    contexts = ctx.modules["index_runtime"].code_contexts(ctx, values, {"code_contexts": code_contexts or {}})
    matches = {}
    references = [ref for card in values for claim in card["claims"] for ref in claim["source_records"]]
    for reference in references:
        key = reference["source_id"], reference["snapshot_id"]
        if key not in matches:
            result = ctx.modules["source_operations"].resolve_source(ctx, reference, bundle)
            matches[key] = result.get("current_source_matches") is True
    if state is None:
        previous = query_runtime.event_state(ctx)
        for proposal in view.get("publication_plan", {}).get("event_proposals", []):
            key = proposal["source_id"], proposal["new_snapshot_id"]
            if key in matches:
                continue
            snapshot = next(row for row in lock["snapshots"] if (row["source_id"], row["snapshot_id"]) == key)
            resource = next(row for row in lock["resources"] if row["source_id"] == key[0])
            operations = ctx.modules["source_operations"]
            raw = operations.recovered_bytes(ctx, snapshot, staged_objects=entries)
            operations.snapshot_text(ctx, snapshot, resource, raw, staged_objects=entries)
            current = (operations.current_code_hash(ctx, resource) if resource["kind"] == "code"
                       else sha(fixed_bytes(ctx.root, resource["path"], ["docs-raw"])))
            matches[key] = current == snapshot["sha256"]
        state = ctx.modules["maintenance"].project_state(view, lock, cards, previous,
                                                       current_source_matches=matches)
    state = deepcopy(state)
    state["processing_digest"] = digest(state.get("blocked_claims", []))
    documents = {}
    parent = database.parent
    for card in values:
        if files.get(card["path"]) != card["raw"]:
            raise NodeError("CANDIDATE_QUERY_CHANGED", "Parsed card does not match the checked candidate", card["path"])
        target = parent / "cards" / (card["sha256"] + ".md")
        relative = target.relative_to(ctx.root).as_posix()
        safe(ctx.root, relative, [ctx.operation_root])
        write_bytes(ctx.root, relative, card["raw"])
        documents[card["metadata"]["id"]] = {"path": card["path"], "sha256": card["sha256"], "blob_ref": relative}
    manifest = {"generation_id": "candidate-" + digest({"view": view["digest"], "database": observed.database_digest})[:24],
                "channel": "local", "database_digest": observed.database_digest, "documents": documents,
                "code_contexts": contexts, "qualifications": {}}
    manifest["digest"] = digest(manifest)
    reference = (parent / "candidate.json").relative_to(ctx.root).as_posix()
    observation = CandidateQuery(ctx.root.resolve(), ctx.args.rules_digest, database, observed,
        tuple(deepcopy(values)), bundle, state, manifest, reference, "")
    return CandidateQuery(**{**observation.__dict__, "fingerprint": observation._identity()})


def run(ctx, view, cards, lock, files, database, observed, cases, *, state=None, code_contexts=None):
    """Evaluate original frozen cases; the caller owns the already checked DB lifetime."""
    from .query_regression import _cases
    cases = _cases({"cases": cases}, view)
    initial_formal_state = query_runtime.event_state(ctx)
    try:
        candidate = _prepare(ctx, view, cards, lock, files, database, observed, state, code_contexts)
    except (ValueError, OSError, KeyError) as exc:
        return {"status": "incomplete", "passed": False, "cases_digest": digest(cases), "outcomes": [],
                "error": {"code": getattr(exc, "code", "QUERY_INPUT_UNAVAILABLE"), "reason": str(exc)}}
    candidate.verify(ctx)
    outcomes = []
    for case in cases:
        expected = {key: deepcopy(case[key]) for key in (
            "required", "forbidden", "expected_order", "expected_claim_ids", "forbidden_claim_ids") if key in case}
        outcome = {"case_id": case["id"], "purpose": case.get("purpose", "current"),
                   "expected": expected, "actual": [], "actual_claim_ids": [], "same_generation_reads": [], "gaps": []}
        try:
            payload = {"operation_id": ctx.operation, "generation_ref": candidate.generation_ref, "evaluation": True,
                       "channel": "local", "query": case["query"], "context": case.get("context", {}),
                       "purpose": case.get("purpose", "current"), "top_k": case.get("top_k", 5)}
            result = query_runtime.search(ctx, payload, candidate=candidate)
            unavailable = not result["candidate_inputs_complete"]
            outcome["gaps"].extend(result["gaps"])
            ids = [row["card_id"] for row in result["matches"]]
            claims = {hit["card_id"] + "#" + claim for hit in result["matches"] for claim in hit["claim_ids"]}
            passed = (not result["candidate_scan_truncated"]
                and set(case.get("required", [])) <= set(ids)
                and not set(case.get("forbidden", [])) & set(ids)
                and ("expected_order" not in case or ids == case["expected_order"])
                and set(case.get("expected_claim_ids", [])) <= claims
                and not set(case.get("forbidden_claim_ids", [])) & claims)
            for hit in result["matches"]:
                body = query_runtime.read(ctx, {**payload, "card_id": hit["card_id"]}, candidate=candidate)
                unavailable = unavailable or not body["candidate_inputs_complete"]
                outcome["gaps"].extend(body["gaps"])
                same = (body["generation_ref"] == candidate.generation_ref
                        and body["card_digest"] == hit["card_digest"]
                        and {row["id"] for row in body["claims"]} == set(hit["claim_ids"]))
                passed = passed and same
                outcome["same_generation_reads"].append({"card_id": hit["card_id"], "passed": same})
            outcome.update(passed=bool(passed), actual=ids, actual_claim_ids=sorted(claims),
                           candidate_scan_truncated=result["candidate_scan_truncated"])
            outcome["passed"] = bool(passed and not unavailable)
            outcome["status"] = "incomplete" if unavailable else "passed" if passed else "failed"
        except (ValueError, OSError, KeyError) as exc:
            outcome.update(passed=False, status="incomplete", error={"code": getattr(exc, "code", "QUERY_INPUT_UNAVAILABLE"),
                                                                    "reason": str(exc)})
        outcomes.append(outcome)
    candidate.verify(ctx)
    if query_runtime.event_state(ctx) != initial_formal_state:
        return {"status": "incomplete", "passed": False, "cases_digest": digest(cases), "outcomes": outcomes,
                "error": {"code": "VALIDITY_CHANGED", "reason": "Formal maintenance state changed during candidate evaluation"}}
    if view.get("input_snapshot"):
        observation = ctx.modules["input_snapshot"].compare_inputs(ctx, view["input_snapshot"])
        if not observation.get("unchanged"):
            raise NodeError("CANDIDATE_INPUT_CHANGED", "Candidate inputs changed during query evaluation")
    states = {row["status"] for row in outcomes}
    status = "failed" if "failed" in states else "incomplete" if "incomplete" in states else "passed"
    return {"status": status, "passed": status == "passed", "cases_digest": digest(cases),
            "generation_id": candidate.manifest["generation_id"], "outcomes": outcomes}
