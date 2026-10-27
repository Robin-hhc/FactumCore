---
name: hs-knowledge-local-check
description: Check an Agent's independent code-review record, exact source references and applicable configuration conditions before local stable application.
---

先读取本机部署工具副本中的 `DEPLOY_LOCAL/EXECUTION.md`；`DEPLOY_LOCAL` 是调用端本机磁盘上的完整 `tools/deploy/` 副本目录，准备方法与私有配置按该说明执行。下文 `scripts/cli.py` 示例只描述实际执行端接口，不授权在共享盘直接启动节点。

项目实际位于另一台服务器或通过远程共享挂载访问时，整个公开节点必须从本机磁盘上的 `DEPLOY_LOCAL/run_node.py --config-env ABS_PRIVATE_CONFIG_ENV --skill hs-knowledge-local-check --input ABS_LOCAL_REQUEST --output NEW_ABS_LOCAL_OUTPUT` 发起，私有配置固定 `EXECUTION_MODE=ssh`；仅按本包公开协议追加 `--action`。子 CLI 留在同一服务器，使用当地已登记的 Python、catalog、规则和原生路径。服务器上的 Linux Agent，以及项目确实位于本机磁盘的 Windows 部署，可直接使用当地已登记 CLI；Linux 跨主机访问项目同样走 SSH，不要求服务器本机做 loopback SSH。

不得从 UNC／映射盘启动 Python、runner 或项目 CLI，不经 Samba 遍历或读取原件、知识卡、索引与源码，也不镜像知识根 K 到本机绕过服务器执行约定。读取远端证据或源码时，经已授权 SSH 获取明确输出或所需的必要文件；不把映射盘路径传给 Linux，不从原件选择执行端。此执行策略不以性能报告或 case 收益为前提，SSH 不可用就保留前置缺口，不回退 Samba。

同一 ingest 固定远端、原生路径及配套身份，同时最多一个写者；并发 query 各用独立 operation_id、Workflow 运行身份及本机输出路径。远端报告、view、apply 与 receipt 引用始终按远端知识根解释，本机响应副本不替代它们；read 保持原 search receipt 的代次和用途。SSH 断连或失败后先核对原远端进程、操作记录、journal 与活动索引，再决定续办，不自动重复调用、切换执行端或重放已入库写入。

P3/P4 use [the shared content-review guide](references/review-guide.md) for independent Claim and batch-disposition review, including risk sampling of substantive skip/new-update decisions. Authoring and review remain Agent work.

The fixed code-evidence invocation requires `operation_id`, `view_ref`, fixed `context_ref` and `semantic_report_ref`. Code-gate and mixed views are accepted; in a mixed view it checks only code-gate cards while binding the entire exact view. Pure-document cards remain exempt. The Agent reads the source and supplies a positive reason and exact references for every code Claim; an empty findings array alone is insufficient.

The report remains `semantic_review` with top-level `schema_version: "2.0"`, `reviewer_id` and `payload`. The payload contains `author_id`, `independent_context`, `findings: []`, `view_digest`, `context_digest`, `mode`, `issued_at` and `claims`. Each Claim records `card_id`, `claim_id`, `status`, a nonempty `reason`, and `evidence` binding the source snapshot, locator and SHA-256. The declared author must belong to the actual plan/card author set; the declared reviewer must differ from every plan author and card owner. The script checks these declarations and exact bindings. It does not authenticate an Agent/person or determine whether a technical conclusion is true.

No reviewer public-key registration, signing adapter or report signature is required. The result tier is `agent_content_review`, which describes recorded Agent review rather than authenticated semantic acceptance. Legacy signed records missing the required independence/reason fields remain incomplete until reviewed again; historical bytes are not migrated or re-signed.

`verification_requirements` distinguishes `semantic-support` (static source and configuration reasoning), `build-support` (build results) and `runtime-support` (observed execution). Static source reasoning does not require compilation artifacts, including for a `current` Claim with its actual mapped Target and conditions. In a module workspace, version/revision may remain unknown while exact file hashes bind current static evidence. A missing Target only permits explicitly `historical`/`guidance` Claims with unknown applicability and no context groups; it never establishes product applicability. Measurement Claims require runtime support. Unknown verification requirements stay incomplete.

Build/runtime requirements additionally require an exact Target/build identity and retained evidence artifacts. Each review Claim must list `verification_evidence` entries with `requirement`, `path` and `sha256` matching a fixed artifact in the context's `build_evidence`. Static source reasoning alone cannot satisfy them. Supplied build evidence is always checked, even for static Claims. Missing required inputs stay incomplete; the node never starts a build. Static checks explicitly carry `code_identity.basis: source`, derived from the exact view and context; current-source checks continue to detect code/configuration changes.

For `code_root` / `modules`, the installed catalog registers the workspace and rules; the fixed original config and common module mapping determine the allowed file scope. No Git URL or duplicate `catalog.code_policy` is required. The CLI checks actual file bytes/hashes and before/after consistency; separate build and runtime claims require their actual evidence. Legacy explicit repository contexts retain their original compatibility checks. `--action verify-proof` rechecks a local result through the same engine; the optional compatibility merge action rechecks the corresponding current evidence and never performs a merge.

E0 is discovery, not a complete code context. P2/P4 supply a separately recorded `project_context` binding the original config bytes, logical module scope, actual selected file hashes, applicable Target conditions and optional build evidence. In a module workspace, repository identity, commit and dirty state remain unknown; they are not inferred or required for static file evidence. Module feature tags do not prove enabled macros, protocol compatibility or successful builds. The independent Agent review references that exact context and view. Do not edit a previous E0 receipt in place or represent a separately assembled context as an original discovery result.

Optional version labels must have explicit source material and provenance. Preserve the observed label type, leave unsupported identity or state unknown, and keep current-file hashes mandatory regardless of the label.

Use a fresh workflow attempt ID when retrying with new prerequisite evidence. A proof is exact-content evidence and does not prove real six-Target acceptance or an installed CI policy. See [artifact contract](artifacts/result.yaml).

Ingest ends after local application, index validation and the batch's target queries. Git submission, fixed CI and merge are human follow-up work; CI reuses lint's deterministic checks and does not repeat this semantic review.

For final deprecated cards, the independent reviewer may record each Claim as `retired` with the exact deprecation reason and replacement mapping. Validate its original immutable evidence; do not require an obsolete assertion to remain supported by current code. Stable cards still require `supported` for every Claim. Retired cards never receive current-content eligibility.

Public `verify-proof` accepts local and merge records and an explicit `purpose`. Historical verification checks the exact recorded context and retained original/checked snapshots without reading today's files. Current verification rechecks the configured file scope, config and actual source hashes. A delegated merge handoff must resolve to the exact original engine result. Historical qualification cannot authorize apply. Document-only views use the existing independent content review and final full-view lint.


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
