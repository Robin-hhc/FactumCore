---
name: hs-knowledge-publish-handoff
description: Prepare a publishing handoff from an authenticated committed local knowledge transaction, leaving Git and CI actions to authorized external actors.
---

Input requires `operation_id` and `apply_result_ref`. Freshly call the catalog-pinned apply verifier before describing local results. Output is an immutable publishing handoff with exact view/proof identities and pending external obligations.

The current ingest sends `v3_required:true,apply_result_ref,query_report_ref`. The node rechecks the actual applied batch and calls the pinned public query-regression verifier, which fully verifies its index and reruns the plan-bound target searches and same-generation reads. Passing returns `ready_to_submit` and exact `commit_files`; record-only batches return `record_only_ready` without index/query. Changed batch bytes block readiness. Readiness does not mean a Git commit exists.

An authorized host commits only `commit_files`, then calls `--action verify-submission` with the exact `commit_sha`. The node rechecks readiness and actual HEAD Git blobs, deletions and changed-file scope, and returns `submitted` only for that real scoped commit. It never performs Git writes, push or merge, installs CI policy or claims remote acceptance. The fixed CI separately checks submitted data. Synthetic proof retains its synthetic tier; no node turns a model report into human consent.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
