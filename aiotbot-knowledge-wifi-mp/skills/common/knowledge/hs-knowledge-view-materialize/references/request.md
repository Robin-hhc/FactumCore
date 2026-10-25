# Exact final view

Request: `operation_id`, `plan_ref`. The node invokes public change-plan verification, then produces the exact complete card, navigation and source-lock write set. Stable/deprecated bytes, expected-old SHA or absent, final SHA and base64 bytes are fixed before governance. The formal card, index and lock remain unchanged.

Result: `view_ref`, `view_digest`, `review_mode`, phase `ready`; all-deferred plans return `deferred` without a view. Reentry is immutable and deterministic. Changed baselines or a preexisting differing view require a new operation, not overwrite. Cross-Skill dependencies resolve only through the explicit installed catalog.
