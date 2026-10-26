---
name: hs-knowledge-merge-check
description: Optional compatibility capability for an explicitly requested code-content recheck. The current fixed CI entry is K/check.py; this Skill is not selected by the ingest or CI workflow.
---

This package preserves an explicit latest-code recheck entry and delegates to the current Agent review-record checks. Current ingest completes content review in P3/P4 and calls the independent lint Skill; current CI executes trusted `K/check.py` and shared deterministic checks. Do not choose this package as the current CI entry based on its name. See [compatibility scope](references/compatibility.md).

For an explicitly requested code_gate recheck, input includes `operation_id`, `view_ref`, a fresh fixed code context and an independent Agent review record for merge mode. Reviewer public keys and semantic signatures are not required. A `code_root` / `modules` workspace rechecks the registered workspace, original config, mapped file scope and current file hashes without Git/mm/manifest operations; unknown version does not block static source reasoning. Legacy explicit repository contexts retain their protected ref/root compatibility checks. A pending view cannot authorize a new file scope.

The node calls the catalog-pinned public local-check engine in merge mode and preserves passed, failed or incomplete status. Changed latest code may be reviewed using a recorded checked_snapshot associated with the original immutable evidence, stored with the review/evidence rather than rewriting the source lock. Missing latest evidence stays incomplete; the script checks record structure, bindings and references without understanding or certifying semantics. Pure documents reject this code gate. See [artifact contract](artifacts/result.yaml).

This node never runs Git merge/push, repairs approved content or installs a CI policy. CI/committer acceptance remains a separate external obligation.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
