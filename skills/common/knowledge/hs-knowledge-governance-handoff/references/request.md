# Immutable governance handoff

Request: `operation_id`, `view_ref`. Read the actual final-view record and describe its plan, source set, baseline and context. There is no predecessor phase or candidate-inspect approval prerequisite. Target Workflow and next-action fields are continuation hints, not a transition decision.

Phase `handed_off` means the view description was saved. It does not create consent, certify readiness, apply cards, activate an index or publish a Git change. OpenFlow tracks its own run/node/attempt and any recovery sequence; actual writes retain their transaction checks.
