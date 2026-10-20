# Explicit six-decision plan

Request: `operation_id`, `bundle_ref`, `decisions`; optional complete `candidate_ids`, `context_ref`. Every enumerated candidate must have exactly one decision with `candidate_id`, `decision`, `reason`, `card_inputs`, and `replaces` where applicable. Card content is Agent authored; this node checks/freezes bytes and generates no semantic claims.

A card input is a `.build` file reference or `{path,target_path}`. Paths must match the card profile; existing IDs retain their existing path. Creates cannot overwrite other IDs or control files. `create` and `update` each take one card. `merge` takes one canonical card plus replaced IDs. `split` takes at least two new cards and one old ID. `deprecate` takes existing IDs without new authored content. `defer` takes no official changes and keeps owner/next_step/reason in its disposition.

Merge/split require `claim_mapping` and/or `retired_claim_ids` for every replaced Claim. Canonical keys use `CardID#ClaimID`; plain Claim IDs are accepted only when unambiguous in their old/new sets. Different cards may share a local Claim ID. New content and old deprecated cards remain in the complete validation view. `related_card_inputs` supplies explicit edits to incoming dependencies; a stable requires edge to a deprecated replacement is refused.

`--action verify` takes `operation_id` and `plan_ref`, rechecks original/candidate/baseline bytes through public source resolution, and returns the fixed plan. Production writes only operation artifacts; no human approval or official asset changes occur here.
