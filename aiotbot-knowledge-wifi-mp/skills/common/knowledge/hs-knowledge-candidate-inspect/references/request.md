# Candidate technical inspection

Request: `operation_id`, `view_ref`. Checks record identity, exact displayed files, baseline, source lock, profile paths and complete Card/Claim/relationship closure. It invokes public plan verification and public materialization to reproduce the exact view. Differently resealed bytes cannot silently keep the old plan identity.

Returns `manual_ready` for manual_document, `code_ready` for code_gate, or `recovery_required` with the actual nonterminal operation. Raw documents never invoke local/merge code lint. Technical readiness is not semantic approval; future confirmation/local-check nodes supply the required proof.
