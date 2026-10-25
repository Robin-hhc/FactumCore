# Immutable governance handoff

Request: `operation_id`, `view_ref`. The node calls public candidate-inspect and retains manual_ready/code_ready/mixed_ready views. The persisted handoff binds view, plan, source set, baseline, context and rules/tool identities. Its target is P4 continuation in `hs-knowledge-ingest`, followed by P5 lint; lint is not a Workflow.

Phase `handed_off` records the P4 stopping point. It does not create consent, apply cards, activate an index or publish a Git change. A recovery state must be resolved first. Workflow run/node/attempt is included when supplied by the host.
