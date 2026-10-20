---
name: hs-knowledge-local-check
description: Check exact code-card Claims against registered code, Target/build evidence and a trusted signed semantic review before stable application.
---

Input requires `operation_id`, `view_ref`, the fixed `context_ref` and a trusted `semantic_report_ref`. Only code_gate views are accepted; pure documents are exempt. Unknown repository, build, feature, revision or positive semantic evidence produces incomplete, never passed. A model's zero findings is insufficient.

The protected catalog registers semantic reviewer keys and code authorization; the current workspace config must agree. Synthetic reviewers are limited to explicitly isolated fixtures. The CLI uses read-only Git object/ref reads, raw file hashes and before/after identities; it executes no source hooks, diff drivers, filters, build commands or instructions. `--action verify-proof` rechecks a local proof through the same engine; `--action merge` fixes the protected latest ref for the merge node.

Use a fresh workflow attempt ID when retrying with new prerequisite evidence. A proof is exact-content evidence and does not prove real six-Target acceptance or an installed CI policy. See [artifact contract](artifacts/result.yaml).

For final deprecated cards, a trusted reviewer may sign each Claim as `retired` with the exact deprecation reason and replacement mapping. Validate its original immutable evidence; do not require an obsolete assertion to remain supported by current code. Stable cards still require `supported` for every Claim. Retired cards never receive current-content eligibility.

Public `verify-proof` accepts local and merge proofs and an explicit `purpose`. Historical verification checks the signed original context and retained original/checked snapshots without reading today's checkout. Current verification rechecks the registered current code identity. A delegated merge handoff must resolve to the exact signed engine proof. Historical qualification cannot authorize apply.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
