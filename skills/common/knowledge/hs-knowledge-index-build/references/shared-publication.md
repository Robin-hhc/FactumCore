# Shared publication receipt

This optional shared-channel contract follows human publication of the knowledge
repository. Its Git checks concern published knowledge assets, not discovery or
management of business code repositories. Local ingest/query with `code_root` /
`modules` uses file/hash evidence and does not require these publishing inputs.

New shared builds use a trusted signed publication payload containing
`rules_digest`, exact `knowledge_commit`, `card_digests` and
`acceptance_records: {"logs/ingest/<batch>.yaml": "<sha256>"}`. The adapter's
trust key comes from the installed catalog. Actual Git objects must contain
the exact cards, rules, source lock and records; dirty local summaries are
rejected. Each record carries P7-derived applied progress and acceptance of
the exact view, card hashes, review modes, Claim IDs and proof fingerprints.
This replaces dependence on the producer machine's private execution files
for the portable path. A local self-sealed digest is not repository acceptance.

Both local and shared generations use the shared `contracts/indexing.py`
format (index schema 3.0, tokenizer 2.0). Verification recomputes all SQL table
sets and values, schema, versions and frozen bodies, in addition to file hashes.
Old generations must be rebuilt under the new pinned rules; no silent fallback.

The legacy publication path below remains compatible only with its original
local proof prerequisites. Fixed CI uses `check.py`, not the legacy semantic
merge-check Skill.

This is an explicit local mechanism interface. It does not deploy a CI policy,
publish Git objects or prove real external access control.

Build accepts `channel: shared` and `publication_receipt_ref` under K/logs. The
receipt has `adapter_id`, `payload`, and an Ed25519 `signature_b64` over sorted
compact UTF-8 canonical JSON. The private installed catalog supplies
`publication_trust[adapter_id].public_key_b64`. Synthetic keys are accepted only
when that entry declares `synthetic: true`, its `fixture_root` is this exact K,
and K/.isolated-knowledge-fixture contains `HIMATE_SYNTHETIC_FIXTURE_V2`.

The payload fixes:

- `rules_digest`: exact framework-lock bytes SHA-256.
- `knowledge_commit`: a full 40- or 64-hex commit ID in W's actual Git repository.
- `card_digests`: exact K-relative card path → SHA-256 for all indexed cards.
- `merge_check_refs`: card ID → exact authenticated merge proof for every code
  card; `{}` when every card is a manually reviewed document.

The implementation reads actual immutable Git blobs for every card, the
framework lock and the publication's sources lock. Card references must resolve
against that committed sources lock; unrelated current source-lock additions do
not invalidate the authenticated generation. No diff/filter/hook-capable Git commands or
network operations run. A signature, arbitrary commit string or nonempty proof
array is insufficient. The publication signer is trusted to attest the actual
external CI/committer event; real remote merge acceptance remains separate.

Code proofs must be `mode: merge`, `status: passed` and bind the same final-view
digest as authenticated application provenance. Their current exact-content
qualification is checked through apply's public `verify-result` API; no copied
checker or private cross-Skill import is used. Local builds can optionally set
`current_code_proof_refs: {card_id: proof_ref}`; each generated qualification
stores `current_code_proof_ref`. Historical provenance always checks exact
`historical_files` through apply. Current reads reverify current proof; historical
reads authenticate historical bytes rather than claiming old code is current.

The manifest stores both the exact publication receipt and its source reference.
Shared verify/activation and shared query reauthenticate publication and actual
Git contents. For historical consumption, the signed historical publication
identity and application provenance do not claim current code support. Current
shared consumption also revalidates the current merge proof. Both build and
activation hold the apply writer lock and refuse any nonterminal operation
journal before snapshotting or switching the active pointer.
