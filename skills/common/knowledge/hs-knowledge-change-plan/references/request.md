# Explicit six-decision plan

## P3 before drafts

`--action plan`: `operation_id`, `scan_ref`, `material_ref`, `author_id`, `units`, `claim_changes`, `card_actions`, `target_queries`. Each frozen scan unit has one outcome (`content/skip/defer/failed/uncovered`) and reason. Each Claim comparison names `unit_ids/card_id/claim_id/action/before/after/conditions/evidence/preserved/reason`; each final rewritten card names `card_id/decision/author_id/unit_ids/reason`, including retired cards. Return `semantic_plan_ref`, phase `content_planned`.

Every new `target_queries` case should explicitly declare `purpose`: `guidance` for design/specification background, `historical` for fixed historical evidence, or `current`/`implementation` with the required actual scope and evidence. Invalid values are rejected before a semantic plan is saved. For API compatibility an omitted value still means `current`; omission never makes guidance-only Claims eligible. For example: `{"id":"design-background","query":"frame flow","purpose":"guidance","required":["frame-flow"]}`. Preserve the declared purpose through P7; do not rewrite an existing plan or silently fall back to a broader purpose after a miss.

When `scan.current_context.affected_claims` contains code/configuration maintenance work, add `maintenance_units` separately from raw units. Each exact affected `card_id/claim_id` has canonical `unit_id:"maintenance:<card>#<claim>"`, explicit `outcome/reason`; Claim/card comparisons can reference these IDs. No fake raw file or source disposition is created. Queries cover every applicable changed card; deprecation asserts current exclusion or explicit historical behavior. Multiple sources for one Claim must be fused into one judgment.

Queries use `{id,query,required:[card_id],forbidden?:[card_id],context?:{},expected_claim_ids?:["card#claim"],forbidden_claim_ids?:[...]}`. Content plans require nonempty expectations.

`--action review`: `semantic_plan_ref`, a different `reviewer_id`, `independent_context`, `sampled_unit_ids`, `unreviewed_unit_ids`, risk `reason`, `findings` (explicitly empty when none). Findings name `unit_id/return_to/reason/evidence`. Add `view_ref` for P4 final-content review. Return `content_review_ref/skip_sample`, phase `reviewed` or `needs_revision`; unselected units are not reviewed-pass.

## P4 authored cards

The default Workflow sends `v3_required:true,semantic_plan_ref` alongside the request below. All final written Card IDs must occur in the authored plan. Mixed views retain separate manual-document and code-gate requirements.

An updated old card explicitly judges every old Claim. A planned `preserve` keeps its body, text reference, effective scope, sources and verification fields unchanged; changes require a revised judgment. A silent omission cannot retire a Claim.

Request: `operation_id`, `bundle_ref`, `decisions`; optional complete `candidate_ids`, `context_ref`. Every enumerated candidate must have exactly one decision with `candidate_id`, `decision`, `reason`, `card_inputs`, and `replaces` where applicable. Card content is Agent authored; this node checks/freezes bytes and generates no semantic claims.

A card input is a `.build` file reference or `{path,target_path}`. Paths must match the card profile; existing IDs retain their existing path. Creates cannot overwrite other IDs or control files. `create` and `update` each take one card. `merge` takes one canonical card plus replaced IDs. `split` takes at least two new cards and one old ID. `deprecate` takes existing IDs without new authored content. `defer` takes no official changes and keeps owner/next_step/reason in its disposition.

Merge/split require `claim_mapping` and/or `retired_claim_ids` for every replaced Claim. Canonical keys use `CardID#ClaimID`; plain Claim IDs are accepted only when unambiguous in their old/new sets. Different cards may share a local Claim ID. New content and old deprecated cards remain in the complete validation view. `related_card_inputs` supplies explicit edits to incoming dependencies; a stable requires edge to a deprecated replacement is refused.

`--action verify` takes `operation_id` and `plan_ref`, rechecks original/candidate/baseline bytes through public source resolution, and returns the fixed plan. Production writes only operation artifacts; no human approval or official asset changes occur here.
