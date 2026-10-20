---
name: hs-knowledge-confirmation-record
description: Record a real human approval or rejection from a trusted host event bound to the complete exact document display.
---

Run only after confirmation-prepare. Input requires `operation_id`, `display_ref` and a host-produced `host_event_ref`. The installed catalog supplies trusted adapter Ed25519 public keys; request/source content cannot register an adapter. Output provides a sealed `manual_review_ref` with approved or rejected status.

When a trusted adapter or event is absent, stop in awaiting state. Silence, timeout, tty state, model assertions and Agent-written unsigned JSON never approve. Synthetic adapters require an explicitly pinned isolated fixture root and marker and are labelled synthetic_host; they do not demonstrate real-human acceptance. Never generate a production consent event or private key. See [artifact contract](artifacts/result.yaml).

