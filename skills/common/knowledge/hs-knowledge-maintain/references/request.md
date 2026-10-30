# Requests

`register-source-change`: `operation_id`, `bundle_ref`. Derives changes from the actual source lock and fixed bundle. `register-code-change` also verifies the current configured source bytes and path before recording a code change. A source ID cannot migrate to another repo/path. Repeated identical transitions are idempotent.

`status`: `operation_id`. Reports the actual recorded restrictions and unfinished source events.

`inspect-context`: `operation_id`. Reads exact adopted sources and existing restrictions without advancing state. A `historical` Claim whose exact old source and locator resolve successfully does not acquire a current-maintenance obligation merely because today's source bytes differ or are unavailable. Source-bound `source_changed`, `code_changed` and `code_source_changed` events likewise do not impose current freshness on that recovered history; their durable state is retained. Unrecoverable old evidence, semantic/applicability restrictions and unbound broad restrictions remain affected. Current Claims keep their existing checks. For guidance code sources declaring code_ref, separately inspect actual navigation; pure source drift with resolved navigation does not create a navigation-repair obligation. Real affected cards still propagate through `requires`/`derived_from`, not ordinary links. This uses source facts, never earlier skip or review results. `audit-references` separately retains historical/current byte-difference observations.

For an explicitly deprecated card, exact recovery of its old adopted evidence also removes a pure current-source freshness obligation. Missing or corrupt old evidence, unsafe source mappings and durable semantic/applicability restrictions remain affected. This permits a published retirement to settle on the next unchanged scan without erasing history or treating an unreadable source as a deletion.

For configured dbox documents, `source_observations` separately reports the
logical source and its actual current access status. Missing configuration or an
unreadable root is `source_current_unavailable` with the source diagnostic code;
it is not proof of changed document bytes or lost fixed evidence. An actual byte
change retains `source_changed`, and unavailable fixed evidence retains
`source_unavailable`. Recovered historical Claims do not gain a current-source
restriction solely from local mapping availability. Other existing Claim and
durable restrictions remain in force. This read-only action never registers a
team source-change event merely because the local mapping differs, and its
report does not contain the private physical source path.

An explicit raw scan limits current dbox observation to that scan's selected
logical dbox ranges; selecting only ordinary raw does not read unrelated dbox
configuration or current files. The internal `dbox_observation_scope` is reflected
in coverage, and unobserved sources are not declared current or unavailable.
Existing durable restrictions still apply. Independent `inspect-context` without
that limit keeps its default full observation.

`advance`: `operation_id`. Compares actual cards/Claims and exact current source references to clear resolved mechanical freshness restrictions. No apply, query, active-generation or passing-review ticket is required. Unknown or changed code/config scope remains restricted; a matching byte hash does not prove semantics or applicability. It never labels a Claim independently reviewed merely because a restriction was cleared. OpenFlow handles the content-review process.

`recover-events`: `operation_id`. Completes exact sealed source events retained in pending state. Pending restrictions and epoch remain durable before event publication; repeated source versions carry exact snapshot identities. Cooperating writer locks and before/after file checks prevent concurrent state corruption.

## Explicit read-only code-reference audit

`audit-references`: `operation_id`, optional `lint_report_ref` relative to the actual K, confined to `.build/`, `logs/` or `artifacts/`. A supplied report must pass the existing fixed-check report validator, use the current rules, select formal/full mode, and bind this exact K. Its `object.files_digest` is compared with a fresh read of the formal file set without rerunning fixed checks. Unavailable, invalid or differently timed fixed results remain explicit gaps.

Output phase is `reported`. `data` contains `audit_ref` (sealed `artifact_manifest`, `purpose: code_reference_audit`), `report_ref` (Markdown), `complete`, `status` (`passed/needs_review/incomplete`) and `counts`. Both artifacts live under this operation's `.build/operations/<operation_id>/`. Exact adopted sources are resolved through the locked common source functions in the same process, without sibling Skill CLI requests or responses. Reuse the returned exact references; a generated report is not content approval.

The JSON retains the accepted fixed report, coverage gaps and per-code-reference observations: card path/ID/hash, adopting Claim IDs/usages (possibly empty), evidence/source/snapshot identity, configured repo/path, old locator/hash, current hash/match, recoverable old fragment, difference, usage-specific effect and suggestion. A declared code_ref also has a separate code_navigation observation with resolved/missing/ambiguous/unavailable status and actual matches. Entire-file hashes detect inserted lines as well as changed referenced text; they do not replace symbol resolution. Missing and inaccessible sources are distinct. Only actual authorized module paths are read; unsafe or unknown mappings remain gaps. Historical references retain their historical purpose. Resolved guidance navigation does not require repair merely because source bytes moved or a function body changed; missing/ambiguous navigation and unavailable parsing retain explicit findings/gaps. Current-source restrictions are never cleared by symbol presence.

The Markdown combines the actual fixed-check results and these observations and includes a copyable manual ingest prompt. Neither artifact clears restrictions, changes knowledge, source locks, events, watermarks or active generations, captures new sources, nor calls an ingest Workflow. Existing actions keep their previous behavior.

Text display is bounded: old fragments use at most 20 lines / 4096 characters; a whole-file diff uses at most 60 lines / 8192 characters. `old_fragment_truncated` and `diff_truncated` disclose omissions. When either file exceeds 256 KiB, text display is omitted (`content_omitted_reason`) while exact hashes and the old locator remain; omitted text never means no difference. Repeated identical file differences use `difference_ref` instead of repeating the diff. OpenFlow must resolve the returned `report_ref` on the execution host and explicitly supply the artifact instance `location.path`; no fixed default filename replaces this output.

Ingest stage-only applies to its P1–P6 execution. The independent explicit register/recover-events/advance actions retain their formal event and watermark effects under the shared stable writer lock. This package has no regular ingest-stage cleanup action. Read-only audit may write its own reports, never delete another operation stage.

## Incremental patrol

Each call uses the installed CLI and a fresh output path on the actual execution host.

- `patrol-sync`: `operation_id`, optional `sync: {argv: [executable, ...args], cwd: absolute_workspace_root, timeout_seconds: 600}`. No shell expansion. Missing sync means local-only `skipped`. Nonzero exit or timeout is an actual failure, never a successful empty scan. Start the following plan in a **new CLI process** and reload the post-sync rules digest; do not carry loaded modules across a knowledge-repository update.
- `patrol-plan`: new `operation_id`. Returns `plan_ref`, `plan_digest`, `scan_ref`, exact `source_request`, report, counts, coverage/gaps and phase `needs_ingest/needs_index/unchanged/blocked`. Git examines the range since the last successful baseline plus dirty paths; a missing old commit or non-Git repository falls back to hashing registered files. Unreadable or unauthorized files are explicit gaps. Metadata/config/rules changes force registered-file inspection. Pass source_request verbatim to source.prepare; changed raw and repair-card sources are a union, with explicit code targets for code-only repairs. An operation's immutable observation cannot be overwritten after input drift.
- `patrol-reindex`: exact `plan_ref` (alias `patrol_plan_ref`), optional `plan_digest`, `index_inputs` and actual `cases`. Only an index-only/no-content plan is eligible. Uses the existing local index builder, complete verification, actual existence queries/same-generation reads and activation CAS. Generated existence cases do not certify business semantics. Output phase `indexed`.
- `patrol-complete`: exact original `plan_ref`, optional `plan_digest`; after ingest supply actual `batch_operation_id`, `publication_ref` or `completion_ref`. The original patrol operation is the default producer. The real formal manifest/completion and processing record must cover the fixed original scan; a caller's `passed` or `batch_complete` field is not proof. Pending/deferred/failed/uncovered units, current restrictions, input drift, unfinished publication/retrieval/cleanup, or concurrent baseline changes keep the successful baseline unchanged. Returns `completed` only after actual verification, otherwise `pending` plus reasons and report.

The local immutable plan and inventory live in `logs/patrol/<patrol-operation>/`, outside the producer's stage cleanup. The successful CAS state lives in `.build/runtime/patrol-state.json`; both are machine execution data excluded from Git. Existing formal `logs/ingest`, `logs/publications` and published evidence retain their distribution rules. A discovered unfinished formal publication yields `blocked` with exact producer/manifest/completion/resume_request; resume that original apply.batch, never infer a new apply from an old private stage.

Cross-round Claim debt is rebuilt from formal processing records with the shared same-Claim descendant-resolution rules. Restoring source bytes does not clear a deferred maintenance fact. Completion also rechecks surviving candidate metadata-only code references. When all content/debt checks have passed but a record-only batch left a missing/stale derived local index, completion may use the same real build/query/activation path to finish that derived work in the same round. Other failures remain pending. A later unchanged round may reuse the prior actual verification only after checking its entire byte-fingerprint closure and current metadata/config/rules/active identity; dirty candidate files still get their actual hashes checked.

The Git-MM integration seam is `governance/contracts/patrol_git.py`. Adapt the explicit sync configuration and actual repository mappings internally, retaining argv/no-shell, per-repository errors, NUL parsing, new-process reload, authorized module bounds and completion-based watermarks. No speculative mm history/list commands or indirect semantic dependency expansion are built in.
