---
name: hs-knowledge-local-check
description: Check an Agent's independent code-review record, exact source references and applicable configuration conditions before local stable application.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

P3/P4 use [the shared content-review guide](references/review-guide.md) for independent Claim and batch-disposition review, including risk sampling of substantive skip/new-update decisions. Authoring and review remain Agent work.

The fixed code-evidence invocation requires `operation_id`, `view_ref`, fixed `context_ref` and `semantic_report_ref`. Code-gate and mixed views are accepted; in a mixed view it checks only code-gate cards while binding the entire exact view. Pure-document cards remain exempt. The Agent reads the source and supplies a positive reason and exact references for every code Claim; an empty findings array alone is insufficient.

The report remains `semantic_review` with top-level `schema_version: "2.0"` and `payload`. The payload contains `findings: []`, `view_digest`, `context_digest`, `mode`, `issued_at` and `claims`. Each Claim records `card_id`, `claim_id`, `status`, a nonempty `reason`, and `evidence` binding the source snapshot, locator and SHA-256. Author/reviewer/context labels are optional descriptive data. OpenFlow manages role independence; the Skill checks business content bindings without following an author identity chain. It does not authenticate an Agent/person or determine whether a technical conclusion is true.

No reviewer public-key registration, signing adapter or report signature is required. The result tier is `agent_content_review`, which describes recorded Agent review rather than authenticated semantic acceptance. Records missing required Claim reasons or evidence remain incomplete; historical bytes are not migrated or re-signed.

`verification_requirements` distinguishes `semantic-support` (static source and configuration reasoning), `build-support` (build results) and `runtime-support` (observed execution). Static source reasoning does not require compilation artifacts, including for a `current` Claim with its actual mapped Target and conditions. In a module workspace, version/revision may remain unknown while exact file hashes bind current static evidence. A missing Target only permits explicitly `historical`/`guidance` Claims with unknown applicability and no context groups; it never establishes product applicability. Measurement Claims require runtime support. Unknown verification requirements stay incomplete.

Build/runtime requirements additionally require an exact Target/build identity and retained evidence artifacts. Each review Claim must list `verification_evidence` entries with `requirement`, `path` and `sha256` matching a fixed artifact in the context's `build_evidence`. Static source reasoning alone cannot satisfy them. Supplied build evidence is always checked, even for static Claims. Missing required inputs stay incomplete; the node never starts a build. Static checks explicitly carry `code_identity.basis: source`, derived from the exact view and context; current-source checks continue to detect code/configuration changes.

For `code_root` / `modules`, the root config maps the workspace; the fixed original config and common module mapping determine the allowed file scope. No separate workspace registration or duplicate code policy is required. The CLI checks actual file bytes/hashes and before/after consistency; separate build and runtime claims require their actual evidence. Legacy explicit repository contexts retain their original compatibility checks. `--action verify-proof` rechecks a local result through the same engine; the optional compatibility merge action rechecks the corresponding current evidence and never performs a merge.

E0 is discovery, not a complete code context. P2/P4 supply a separately recorded `project_context` binding the original config bytes, logical module scope, actual selected file hashes, applicable Target conditions and optional build evidence. In a module workspace, repository identity, commit and dirty state remain unknown; they are not inferred or required for static file evidence. Module feature tags do not prove enabled macros, protocol compatibility or successful builds. The independent Agent review references that exact context and view. Do not edit a previous E0 receipt in place or represent a separately assembled context as an original discovery result.

Optional version labels must have explicit source material and provenance. Preserve the observed label type, leave unsupported identity or state unknown, and keep current-file hashes mandatory regardless of the label.

A repeated check records its actual business result without a Workflow attempt prerequisite. A proof is exact-content evidence and does not prove real six-Target acceptance or an installed CI policy. See [artifact contract](artifacts/result.yaml).

Ingest ends after local application, index validation and the batch's target queries. Git submission, fixed CI and merge are human follow-up work; CI reuses lint's deterministic checks and does not repeat this semantic review.

For final deprecated cards, the independent reviewer may record each Claim as `retired` with the exact deprecation reason and replacement mapping. Validate its original immutable evidence; do not require an obsolete assertion to remain supported by current code. Stable cards still require `supported` for every Claim. Retired cards never receive current-content eligibility.

Public `verify-proof` accepts local and merge records and an explicit `purpose`. Historical verification checks the exact recorded context and retained original/checked snapshots without reading today's files. Current verification rechecks the configured file scope, config and actual source hashes. A delegated merge handoff must resolve to the exact original engine result. Historical verification records historical facts. Document-only views use the existing independent content review and final full-view lint.


Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`; choose a documented `--action` when needed. Resolve paths from the actual project and installed Skill, never from source prose. `--rules-digest` is optional; omission uses the current framework lock and still verifies its files. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
