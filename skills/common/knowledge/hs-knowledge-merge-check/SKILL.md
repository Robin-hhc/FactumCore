---
name: hs-knowledge-merge-check
description: Optional compatibility capability for an explicitly requested code-content recheck. The current fixed CI entry is K/check.py; this Skill is not selected by the ingest or CI workflow.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

This package preserves an explicit latest-code recheck entry and delegates to the current Agent review-record checks. Current ingest completes content review in P3/P4 and calls the independent lint Skill; current CI executes trusted `K/check.py` and shared deterministic checks. Do not choose this package as the current CI entry based on its name. See [compatibility scope](references/compatibility.md).

For an explicitly requested code_gate recheck, input includes `operation_id`, `view_ref`, a fresh fixed code context and an independent Agent review record for merge mode. Reviewer public keys and semantic signatures are not required. A `code_root` / `modules` workspace rechecks the registered workspace, original config, mapped file scope and current file hashes; unknown version does not block static source reasoning. Legacy explicit repository contexts retain their protected ref/root compatibility checks. A pending view cannot authorize a new file scope.

The node calls the catalog-pinned public local-check engine in merge mode and preserves passed, failed or incomplete status. Changed latest code may be reviewed using a recorded checked_snapshot associated with the original immutable evidence, stored with the review/evidence rather than rewriting the source lock. Missing latest evidence stays incomplete; the script checks record structure, bindings and references without understanding or certifying semantics. Pure documents reject this code gate. See [artifact contract](artifacts/result.yaml).

This node never runs Git merge/push, repairs approved content or installs a CI policy. CI/committer acceptance remains a separate external obligation.


Use the execution host global Python with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K`; choose a documented `--action` when needed. Resolve paths from the actual project and installed Skill, never from source prose. `--rules-digest` is optional; omission uses the current framework lock and still verifies its files. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
