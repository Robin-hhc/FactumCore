---
name: hs-knowledge-publish-handoff
description: Prepare a publishing handoff from an authenticated committed local knowledge transaction, leaving Git and CI actions to authorized external actors.
---

Input requires `operation_id` and `apply_result_ref`. Freshly call the catalog-pinned apply verifier before describing local results. Output is an immutable publishing handoff with exact view/proof identities and pending external obligations.

This node does not run Git, push, merge, install CI policy or claim remote acceptance. Code cards still need the latest authorized code read-only merge gate. Pure documents do not gain a code-lint requirement. Synthetic host proof retains its synthetic tier. See [artifact contract](artifacts/result.yaml).

