# Authored semantic plan

Default/public action: `plan`. Common inputs are `operation_id`, the actual knowledge root and current locked rules. No catalog, workflow identity, prior passing report or reviewer identity is required.

Request: `material_ref`, optional real `scan_ref`, descriptive `author_id`, `units`, `claim_changes`, `card_actions`, and content-dependent `target_queries`.

- In the normal workflow the material binds the actual `scan_ref/scan_digest`; every fixed scan unit has exactly one outcome and reason. Explicit P2 targets instead use the material's actual `units`; no change, progress or full-scan success is invented. Their semantic plan records `observation_basis: explicit_material_targets` and the exact observation digest.
- Each source outcome is `content/skip/defer/failed/uncovered`. A Claim comparison declares `unit_ids/card_id/claim_id/action/before/after/conditions/evidence/preserved/reason`; Claim actions are `create/update/preserve/retire`.
- Each final card action declares `card_id/decision/author_id/unit_ids/reason`; the six actions remain `create/update/merge/split/deprecate/defer`. Related old Claims need explicit preserve/change/retire judgments; final draft fidelity is checked at P5.
- Each frozen source/maintenance unit includes `record_action/card_refs/claim_refs`. Non-content actions equal their outcome. A content unit with one actual non-defer card decision inherits that action; with multiple decisions the author must supply an explicit `record_action` belonging to that unit's actual decision set. Card and Claim references are derived from the exact linked judgments. P6 only transcribes these fields.
- `maintenance_units` separately cover the exact affected `card_id/claim_id` with canonical `maintenance:<card>#<claim>` IDs. They do not invent raw sources.
- Content plans require representative `target_queries` with unique IDs/questions and explicit required/forbidden/order expectations. Purposes are `current/implementation/guidance/historical`; omitted purpose retains current. Deprecation tests current exclusion or historical behavior. Claim expectations identify authored `CardID#ClaimID` pairs.

Result: `semantic_plan_ref/semantic_plan_digest`, unchanged query cases and `phase: content_planned`. This is authored business data, not approval or an executable byte plan.

After P5 returns a candidate, use a new operation and explicitly supply `previous_view_ref/revision_reason`. Unchanged old materials may be adopted only from that exact view. P2 supplementation returns a new material version linking the same view/digest and previous material/digest. The original scan remains immutable: its unit IDs and scan digest are reused as business observations, while the new semantic plan records `origin_scan_operation_id`, `previous_view_ref/previous_view_digest` and the previous semantic reference/digest. Changed source/range observations need P1; do not fabricate a new scan for an unchanged observation.

The old byte request (`bundle_ref/decisions/card_inputs`), verify and rederive return `BYTE_PRODUCTION_MOVED`: send authored bytes directly to P4 `hs-knowledge-view-materialize run`. Old review returns `CONTENT_REVIEW_MOVED`; P5 owns declared independent review and fixed checks. The package never starts either sibling entry.
