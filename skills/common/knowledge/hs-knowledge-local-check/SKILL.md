---
name: hs-knowledge-local-check
description: Check exact code-card Claims against registered code, Target/build evidence and a trusted signed semantic review before stable application.
---

Input requires `operation_id`, `view_ref`, the fixed `context_ref` and a trusted `semantic_report_ref`. Only code_gate views are accepted; pure documents are exempt. Unknown repository, build, feature, revision or positive semantic evidence produces incomplete, never passed. A model's zero findings is insufficient.

The protected catalog registers semantic reviewer keys and code authorization; the current workspace config must agree. Synthetic reviewers are limited to explicitly isolated fixtures. The CLI uses read-only Git object/ref reads, raw file hashes and before/after identities; it executes no source hooks, diff drivers, filters, build commands or instructions. `--action verify-proof` rechecks a local proof through the same engine; `--action merge` fixes the protected latest ref for the merge node.

Use a fresh workflow attempt ID when retrying with new prerequisite evidence. A proof is exact-content evidence and does not prove real six-Target acceptance or an installed CI policy. See [artifact contract](artifacts/result.yaml).

