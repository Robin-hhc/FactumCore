# One-pass authored candidate

## Produce: run

Normal request: `operation_id`, `semantic_plan_ref`, optional `material_ref` (otherwise from that plan), authored `decisions`, and actual current `context_ref` when needed. `bundle_ref` can come from the material. A legacy authored `bundle_ref/decisions` request can be moved directly here; no sibling plan verification runs.

When the material or its captured bundle already fixes a context, the request cannot substitute another `context_ref`; any declared `context_digest` must match the actual loaded project context. Use new materials for a changed adopted context.

Each decision has `candidate_id/decision/reason/card_inputs`, plus explicit `replaces`, `claim_mapping`, `retired_claim_ids`, `related_card_inputs`, or defer owner/next-step where applicable. Safe destination, distinct identity and write cardinality are production invariants. Six actions remain create/update/merge/split/deprecate/defer. Full Claim destination, preservation and impact-closure checks belong to P5.

Every registered code `sources[]` item on an active (non-deprecated) card requires `code_ref`, following K's card specification. Pure-document cards need no invented code links; P5 reviews whether actual content omits a necessary entry point. Use supported symbols, never file/range fallbacks. Historical source recovery and deprecated cards retain the original four-field contract. Keep evidence_ref/source_id/snapshot_id/locator and Claim.source_refs unchanged. P4 preserves the complete metadata and freezes it in the card/view bytes; it does not infer symbols, relocate historical locators or certify navigation. No new card-level reference field or snapshot payload is required.

Simple create/update/defer may use `cards: {CardID: draft_ref}` or a list of card inputs with semantic actions. Merge/split/retirement need explicit decisions. Existing Card IDs retain their path; new IDs cannot overwrite other cards or control files. Drafts remain under `.build/`.

Result phase ready: `plan_ref/plan_digest`, `view_ref/view_digest/review_mode`, `batch_kind`, `disposition_preview_ref`, `summary_ref`. The view also freezes `material_ref/material_digest`, and revisions preserve `previous_view_ref/previous_view_digest`, actual reason and original scan identity. The card byte plan and complete view are frozen once. Navigation/source-lock writes occur only in content batches. A record-only batch has an empty write set, review_mode record_only and the exact disposition preview; it does not claim content quality passed.

The view embeds `input_snapshot`: rules identity, complete formal file membership/hashes, business records, adopted originals/old cards and selected current files. It is business binding, not a passing report or role credential. P5/P7 independently compare observed inputs. The postwrite index uses its own new formal baseline.

`disposition-preview.json` copies the semantic plan's exact source/maintenance units, including fixed `record_action/card_refs/claim_refs`, binds its semantic digest, and retains every actual card decision (including mapping/retirement details); P6 mechanically transcribes. `view-summary.json` describes exact source set, baseline and limitations. Neither qualifies Workflow handoff.

## Revise: revise

Add `previous_view_ref` and nonempty `revision_reason`, use a NEW operation_id, and provide new authored/material inputs as for run. Old view is read-only linkage, never current approval. The same assembler saves the candidate and revision_ref. It does not silently recapture sources, inherit an old code context or replay an applied operation.

For a P4-only return, the new candidate may explicitly adopt the exact unchanged semantic plan and material bound by `previous_view_ref`; the new view and P5 review remain distinct. Returns to P2/P3 first freeze their new material/plan versions under the new operation. All paths preserve the original scan and processing-unit identities, record `origin_scan_operation_id`, and require P5 to review the actual new view. P6 transcribes into the new operation's pending record while binding that real original scan.

## Describe: describe

Request: operation_id and saved view_ref. Returns existing references, source set, baseline and limitations; no writes or quality checking. Missing/misbound views are errors. Caller names the view's actual business operation; no author/reviewer identity or upstream passing status is inspected.

Identical run reentry checks saved input/display binding and returns existing outputs without rederiving a plan. Changed requests or observed inputs require a new operation. P5 independently reviews content; P7 protects actual writes.

Staging boundary: requests, responses and new business payloads stay under this operation's `.build/operations/<op>/`. Follow the exact returned material/view references; never discover a latest private operation. Final evidence references and stage-to-final hashes are fixed before P5 and may not be rewritten by P7. Explicit revision/adoption preserves old immutable inputs, which are not this operation's owned cleanup set.
