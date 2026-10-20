# Immutable governance handoff

Request: `operation_id`, `view_ref`. The node calls public candidate-inspect and only hands off manual_ready/code_ready views. The persisted handoff binds view, plan, source set, baseline, context and rules/tool identities. Its target is `hs-knowledge-lint`.

Phase `handed_off` means the production candidate is complete. It does not start the next template, create consent, apply cards, activate an index or publish a Git change. A recovery state must be resolved first. Workflow run/node/attempt is included when supplied by the host.
