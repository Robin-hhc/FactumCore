# Public P7 actions

All references are relative to the actual knowledge root. Every request has an explicit `operation_id`. The installed CLI accepts `--input`, `--output`, `--knowledge-root` and optional `--rules-digest`; existing response-path retry rules remain in force.

| Action | Business input | Result and effects |
|---|---|---|
| `batch` | Exact `view_ref`, its `input_snapshot`, and the pending `ingest_record_ref` for a v3 batch; optional actual code contexts or shared publication inputs | Frozen identical-byte publication and postwrite content verification, formal processing facts/evidence, actual index and frozen queries, original-baseline activation, then bounded owned-stage cleanup |
| `index-build` | Formal shared assets and actual material contexts; optional local/shared channel and repository snapshot data | A fully verified immutable candidate generation and its original `expected_active`; does not write knowledge or activate |
| `index-verify` | Exact `generation_ref` | Verify schema, complete rows, database and card blobs, plus applicable shared publication data; does not activate |
| `index-activate` | Exact `generation_ref` and original `expected_active` | Verify, then check writer barriers, actual indexed inputs and baseline under the writer lock; CAS activate and save the actual pointer observation |
| `regression` | Exact `generation_ref`, original `expected_active`, and nonempty `cases`; a batch view/apply result may supply the cases as optional business data | Check declared card/Claim expectations, no truncation, and same-generation reads; failed cases never activate; passing cases use the original CAS baseline |
| `regression-verify` | Exact `report_ref`, optionally the same original generation/cases/baseline | Re-execute the report's original assertions without activating; callers cannot replace the original case set or generation |
| `prepare-submission` | Exact formal publication or selected legacy `view_ref`, optionally its actual `apply_result_ref` | Read actual selected local files/deletions and processing record, return `commit_files`; does not commit, push, merge or certify CI |
| `verify-submission` | The same selected bytes and exact `commit_sha` | Read actual HEAD Git blobs/deletions and changed-file scope; only then report `submitted`; never performs a Git write |

Cases retain `id`, `query`, `purpose`, `context`, `top_k`, required/forbidden card IDs, explicit expected order and optional expected/forbidden `card#claim` IDs. `expected_order: []` is a meaningful declared empty result. An empty case set or a case with no expected behavior is rejected. A failed query cannot be repaired by changing purpose, loosening assertions or replacing `expected_active`.

`batch` always uses the query expectations frozen in the selected view. A request cannot replace those cases. Batch success means publication, applicable observed retrieval activation and eligible owned-stage cleanup completed; it does not mean P5, CI, Git submission or merge has been independently proved. `committed` alone only describes the transaction.

## Recovery

New transactions use `.build/operations/<operation_id>/transaction/journal.json`, `apply-result.json` and `backups/`. The stable cooperative writer lock is `.build/runtime/writer.lock` and is excluded from cleanup. Old actual `logs/operations/<operation_id>/journal.json` transactions remain explicit compatibility inputs; conflicting old/new journals for one operation are refused. New batch transactions explicitly record the checks actually performed. Existing `run` keeps full-check semantics; only the new batch's internal call selects its safety-only path. Request JSON is never a bypass flag.

Batch intent, built-generation reference/original active baseline, and completion are saved separately under `.build/operations/<operation_id>/batch-intent.json`, `batch-build.json` and `batch-complete.json`. They are business observations, not upstream authorization tickets. Missing producer-private records do not create obligations for another clean checkout.

After an interrupted write, resume or roll back the original journal and preserve external edits. A pending legacy transaction must use its matching entry/version. After a committed write, retrying the batch rechecks actual installed bytes and continues index/query/activation without applying again. After a lost activation response, inspect the actual pointer and stored activation observation; do not replace the original baseline or blindly replay activation.

Activation history is rooted in the actual active pointer and its immutable predecessor links under `artifacts/indexes/<channel>/activations/`. A standalone `.build` observation does not prove activation. Completed published batches retain formal completion bindings to their actual generation, write/query execution and original baseline; normal historical result/status reads do not require producer-private files to remain. Another activated generation cannot stand in for this batch execution. An explicitly supplied baseline is frozen in the first batch intent even when a retry omits it.

The prewrite snapshot describes the old formal tree. After application the candidate captures a separate postwrite snapshot including this batch's files. Process-local index verification can be reused only while the actual generation fingerprints still match. A restarted process fully verifies the generation again; a JSON `passed` field cannot serve as that in-memory observation.

Only record-only batches finish without indexing. Their records retain unresolved/deferred facts and do not claim content completion. Once committed, content corrections use a new operation rather than undoing history or deleting formal records.

## Formal publication and cleanup

P1–P6 new ingest business payloads, reports, checked code/material copies and request/response files stay in the current operation stage. P4/P5 freeze final references and exact stage-to-final hashes; P7 copies identical bytes without rematerializing reviewed cards or replacing source addresses. Necessary formal evidence is published under `logs/evidence/published/`; the content manifest and final completion are `logs/publications/<op>/manifest.json` and `completion.json`. Formal successful ingest records are written only after corresponding content publication and validation. Applicable index/query/activation then finish before cleanup.

Cleanup deletes only explicitly owned, eligible files of this operation. Borrowed previous materials, protected/known-use/unknown-use files remain with reasons; runtime locks, formal evidence, other operations and development environments are excluded. A final tiny CLI envelope may remain in `.build`. Eligible deletion failure keeps `published/content_applied` true and reports `cleanup_pending` with `batch_complete=false`; a retry verifies the formal binding and only retries missing tail/cleanup, never reapplies published bytes or rebuilds an already completed index. A retained file is distinct from a deletion failure.

Result reads, `verify-result`, target status and submission preparation/verification use the exact formal publication closure after stage cleanup. Actual Git HEAD/commit/blob/deletion/scope checks remain mandatory for submitted claims; publication alone is not Git submission. New Workflows do not discover or adopt old draft operations. Explicit current Workflow continuation and matching old transaction recovery preserve their safety gates. Rare P7 partial multi-file repair, whole-directory atomic switching and abandoned-stage periodic GC are outside this cleanup contract.
