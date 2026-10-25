---
name: hs-knowledge-merge-check
description: Optional legacy compatibility capability for an explicitly requested signed semantic recheck. The current fixed CI entry is K/check.py; this Skill is not selected by the ingest or CI workflow.
---

This package preserves the previous signed semantic-recheck protocol for explicit compatibility use. Current ingest completes semantic verification in P3/P4 and calls the independent lint Skill; current CI executes trusted `K/check.py` and shared deterministic checks. Do not choose this package as the current CI entry based on its name. See [compatibility scope](references/compatibility.md).

For an explicitly requested legacy code_gate recheck, input includes `operation_id`, `view_ref`, a fresh fixed code context and signed semantic report for merge mode. The installed catalog's code_policy authorizes the actual ref/root and must agree with the registered config. A pending view cannot authorize its own code ref.

The node calls the catalog-pinned public local-check engine in merge mode and preserves passed, failed or incomplete status. Changed latest code may be revalidated using an independently signed checked_snapshot associated with the original immutable evidence, stored with proof/evidence rather than rewriting the source lock. Missing latest evidence stays incomplete. Pure documents reject this code gate. See [artifact contract](artifacts/result.yaml).

This node never runs Git merge/push, repairs approved content or installs a CI policy. CI/committer acceptance remains a separate external obligation.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
