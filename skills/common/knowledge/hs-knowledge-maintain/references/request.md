# Requests

`register-source-change`: `operation_id`, `bundle_ref`. Derives changes from the actual source lock and fixed bundle. `register-code-change` also verifies the current configured source bytes and path before recording a code change. A source ID cannot migrate to another repo/path. Repeated identical transitions are idempotent.

`status`: `operation_id`. Reports the actual recorded restrictions and unfinished source events.

`advance`: `operation_id`. Compares actual cards/Claims and exact current source references to clear resolved mechanical freshness restrictions. No apply, query, active-generation or passing-review ticket is required. Unknown or changed code/config scope remains restricted; a matching byte hash does not prove semantics or applicability. It never labels a Claim independently reviewed merely because a restriction was cleared. OpenFlow handles the content-review process.

`recover-events`: `operation_id`. Completes exact sealed source events retained in pending state. Pending restrictions and epoch remain durable before event publication; repeated source versions carry exact snapshot identities. Cooperating writer locks and before/after file checks prevent concurrent state corruption.

## Explicit read-only code-reference audit

`audit-references`: `operation_id`, optional `lint_report_ref` relative to the actual K, confined to `.build/`, `logs/` or `artifacts/`. A supplied report must pass the existing fixed-check report validator, use the current rules, select formal/full mode, and bind this exact K. Its `object.files_digest` is compared with a fresh read of the formal file set without rerunning fixed checks. Unavailable, invalid or differently timed fixed results remain explicit gaps.

Output phase is `reported`. `data` contains `audit_ref` (sealed `artifact_manifest`, `purpose: code_reference_audit`), `report_ref` (Markdown), `complete`, `status` (`passed/needs_review/incomplete`) and `counts`. Both artifacts live under this operation's `.build/operations/<operation_id>/`; sibling public read-only `resolve-source` requests and responses use the same subtree. Reuse the returned exact references; a generated report is not content approval.

The JSON retains the accepted fixed report, coverage gaps and per-code-reference observations: card path/ID/hash, adopting Claim IDs/usages (possibly empty), evidence/source/snapshot identity, configured repo/path, old locator/hash, current hash/match, recoverable old fragment, difference, usage-specific effect and suggestion. Entire-file hashes detect inserted lines as well as changed referenced text. Missing and inaccessible sources are distinct. Only actual authorized module paths are read; unsafe or unknown mappings remain gaps. Historical references retain their historical purpose; guidance drift requests navigation review rather than asserting a semantic contradiction.

The Markdown combines the actual fixed-check results and these observations and includes a copyable manual ingest prompt. Neither artifact clears restrictions, changes knowledge, source locks, events, watermarks or active generations, captures new sources, nor calls an ingest Workflow. Existing actions keep their previous behavior.

Text display is bounded: old fragments use at most 20 lines / 4096 characters; a whole-file diff uses at most 60 lines / 8192 characters. `old_fragment_truncated` and `diff_truncated` disclose omissions. When either file exceeds 256 KiB, text display is omitted (`content_omitted_reason`) while exact hashes and the old locator remain; omitted text never means no difference. Repeated identical file differences use `difference_ref` instead of repeating the diff. OpenFlow must resolve the returned `report_ref` on the execution host and explicitly supply the artifact instance `location.path`; no fixed default filename replaces this output.
