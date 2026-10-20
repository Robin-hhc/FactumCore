---
name: hs-knowledge-merge-check
description: Recheck code-card Claims against the protected latest authorized code ref through the same signed evidence engine, without changing cards, locks, links or source.
---

Invoke for a code_gate view before external merge acceptance. Input includes `operation_id`, `view_ref`, a fresh fixed code context and signed semantic report for merge mode. The installed catalog's code_policy authorizes the actual ref/root and must agree with the registered config. A pending view cannot authorize its own code ref.

The node calls the catalog-pinned public local-check engine in merge mode and preserves passed, failed or incomplete status. Changed latest code may be revalidated using an independently signed checked_snapshot associated with the original immutable evidence, stored with proof/evidence rather than rewriting the source lock. Missing latest evidence stays incomplete. Pure documents reject this code gate. See [artifact contract](artifacts/result.yaml).

This node never runs Git merge/push, repairs approved content or installs a CI policy. CI/committer acceptance remains a separate external obligation.

