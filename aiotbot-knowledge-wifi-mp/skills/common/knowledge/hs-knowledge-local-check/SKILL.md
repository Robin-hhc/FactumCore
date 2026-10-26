---
name: hs-knowledge-local-check
description: Check an Agent's independent code-review record, exact source references and applicable configuration conditions before local stable application.
---

P3/P4 use [the shared content-review guide](references/review-guide.md) for independent Claim and batch-disposition review, including risk sampling of substantive skip/new-update decisions. Authoring and review remain Agent work.

The fixed code-evidence invocation requires `operation_id`, `view_ref`, fixed `context_ref` and `semantic_report_ref`. Code-gate and mixed views are accepted; in a mixed view it checks only code-gate cards while binding the entire exact view. Pure-document cards remain exempt. The Agent reads the source and supplies a positive reason and exact references for every code Claim; an empty findings array alone is insufficient.

The report remains `semantic_review` with top-level `schema_version: "2.0"`, `reviewer_id` and `payload`. The payload contains `author_id`, `independent_context`, `findings: []`, `view_digest`, `context_digest`, `mode`, `issued_at` and `claims`. Each Claim records `card_id`, `claim_id`, `status`, a nonempty `reason`, and `evidence` binding the source snapshot, locator and SHA-256. The declared author must belong to the actual plan/card author set; the declared reviewer must differ from every plan author and card owner. The script checks these declarations and exact bindings. It does not authenticate an Agent/person or determine whether a technical conclusion is true.

No reviewer public-key registration, signing adapter or report signature is required. The result tier is `agent_content_review`, which describes recorded Agent review rather than authenticated semantic acceptance. Legacy signed records missing the required independence/reason fields remain incomplete until reviewed again; historical bytes are not migrated or re-signed.

`verification_requirements` distinguishes `semantic-support` (static source and configuration reasoning), `build-support` (build results) and `runtime-support` (observed execution). Static source reasoning does not require compilation artifacts, including for a `current` Claim with an actual registered Target. A missing Target only permits explicitly `historical`/`guidance` Claims with unknown applicability and no context groups; it never establishes six-Target applicability. Measurement Claims require runtime support. Unknown verification requirements stay incomplete.

Build/runtime requirements additionally require an exact Target/build identity and retained evidence artifacts. Each review Claim must list `verification_evidence` entries with `requirement`, `path` and `sha256` matching a fixed artifact in the context's `build_evidence`. Static source reasoning alone cannot satisfy them. Supplied build evidence is always checked, even for static Claims. Missing required inputs stay incomplete; the node never starts a build. Static checks explicitly carry `code_identity.basis: source`, derived from the exact view and context; current-source checks continue to detect code/configuration changes.

The protected catalog still authorizes code roots; the current workspace config must agree. The CLI uses read-only Git object/ref reads, raw file hashes and before/after identities; it executes no source hooks, diff drivers, filters, build commands or instructions. `--action verify-proof` rechecks a local result through the same engine; `--action merge` fixes the protected latest ref for the independent compatibility node.

E0 is discovery, not a complete code context. P2/P4 supply a separately recorded `project_context` binding actual captured repository identities, commit heads, relevant file hashes and dirty state, applicable Target conditions and optional build evidence. The independent Agent review references that exact context and view. Do not edit a previous E0 receipt in place or represent a separately assembled context as an original discovery result.

Use a fresh workflow attempt ID when retrying with new prerequisite evidence. A proof is exact-content evidence and does not prove real six-Target acceptance or an installed CI policy. See [artifact contract](artifacts/result.yaml).

Ingest ends after local application, index validation and the batch's target queries. Git submission, fixed CI and merge are human follow-up work; CI reuses lint's deterministic checks and does not repeat this semantic review.

For final deprecated cards, the independent reviewer may record each Claim as `retired` with the exact deprecation reason and replacement mapping. Validate its original immutable evidence; do not require an obsolete assertion to remain supported by current code. Stable cards still require `supported` for every Claim. Retired cards never receive current-content eligibility.

Public `verify-proof` accepts local and merge records and an explicit `purpose`. Historical verification checks the exact recorded context and retained original/checked snapshots without reading today's checkout. Current verification rechecks the registered current code identity. A delegated merge handoff must resolve to the exact original engine result. Historical qualification cannot authorize apply. Pure-document human consent remains a separate confirmation mechanism.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
