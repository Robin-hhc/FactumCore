---
name: hs-knowledge-apply
description: Apply an exact reviewed knowledge view using complete-write-set CAS, a cooperative writer lock, durable backups and one recovery journal.
---

Input requires `operation_id`, `view_ref`, `proof_ref`. Pure-document views require authenticated exact-view human consent; code views require a trusted local-check proof with positive Claim evidence. Apply never changes approved bytes or originals and never repairs failed checks.

The current ingest sets `v3_required:true` and also supplies `ingest_record_ref`, `lint_report_ref`, `content_review_ref`. A mixed view supplies `proof_set:{manual_document:<proof>,code_gate:<proof>}`. P7 verifies the final full-view lint, independent final-content review, portable exact originals and applicable signed evidence; the shared record joins the existing CAS/journal as an additional controlled entry without altering any reviewed card, navigation or source-lock byte. Its acceptance summary derives from verified cards/proofs and is only local evidence until the repository actually admits it.

A `record_only` ingest record omits `view_ref/proof_ref`; all content writes are forbidden, the fixed record contract remains mandatory, and substantive skip still needs its risk sample. Failed/defer unit states remain unfinished. `batch_kind` distinguishes this branch in the committed result. A transaction's `committed` phase means local application, not a Git commit. Index/query and authorized submission are subsequent P7 obligations.

The public CLI supports `run`, `inspect`, `resume`, `rollback` through `--action`. Use the recover Skill for workflow recovery. An interrupted operation requires an explicit recovery action; external edits produce a conflict and remain untouched. Committed reentry returns its prior result; a committed change is undone through a newly reviewed operation.

The OS lock coordinates cooperating writers; it does not make directories an access-control boundary. See [artifact contract](artifacts/result.yaml) for durable output. Fault injection is available only in catalog-pinned synthetic fixture roots.

`--action verify-result` verifies signed content eligibility. With `purpose: historical`, it checks the original exact view and retained evidence, returns only `historical_files`, and never promotes old content to current. The current path also requires actual card bytes; a fresh `current_code_proof_ref` may supply a verified latest local/merge code check without rewriting the original card or source lock. Actual apply always requires a current local proof, regardless of a payload purpose field.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
