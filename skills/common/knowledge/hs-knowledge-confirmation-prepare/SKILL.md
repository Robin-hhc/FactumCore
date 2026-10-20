---
name: hs-knowledge-confirmation-prepare
description: Freeze and display every exact document-card write and deletion for real human review after candidate inspection.
---

Use the public CLI with the pinned knowledge root and rules digest. Input requires `operation_id` and `view_ref`; output provides `display_ref`. Review every entry in the persisted `display_text` and exact bytes before passing its digest and challenge to the trusted host adapter. A prepared display is awaiting a human, never approval.

Code-gate views use the local-check node. A changed or partially accepted view needs a new operation, display, and confirmation. Do not ask a model to impersonate the host or fabricate an event. Artifact format and review requirements are in [artifacts/result.yaml](artifacts/result.yaml).

