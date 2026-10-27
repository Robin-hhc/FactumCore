---
name: hs-knowledge-maintain
description: Register exact source-change events, block affected Claims and advance review state only from verified applied and activated evidence.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Use `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K  --action inspect-context|audit-references|register-source-change|register-code-change|recover-events|status|advance`. All event changes use the domain cooperative writer lock. [Request details](references/request.md) explain the proof requirements.

`inspect-context` 在 ingest 开始时只读比较实际来源、代码/配置和规则身份，输出受影响 Claim、依赖和缺口，不要求先登记本机变化事件。未知上下文保留限制；P2—P5 修订、P6 记录和 P7 收尾后才能解除。query 另按相同当前引用和确切资格判断过滤，不因 raw 未变而信任旧代码。

Source capture may register new events and blocks; it never clears them. `advance` requires public apply verification, a verified activated generation and exact current card bytes. An index rollback cannot undo live blocks. User data, URLs, model assertions and old successful test records never authorize clearing a block.

The [artifact contract](artifacts/result.yaml) requires the actual per-attempt CLI manifest.

## 只读引用巡检

`audit-references` 是独立显式动作，不替换 `inspect-context`、`status` 或 ingest 的既有节点。输入 `operation_id`，可附实际知识根 K 内的 `lint_report_ref`；报告须为 `.build/`、`logs/` 或 `artifacts/` 中原 lint Skill 生成的正式全库报告。核对摘要、规则、知识根及 `object.files_digest`；报告缺失、局部／候选、损坏、规则不同或正式文件已变化时，明确列出缺口，不代跑检查，也不把旧报告当作当前通过。

本动作读取正式卡全部代码来源引用，包括未被 Claim 采用的元数据引用；在实际配置允许的路径内比较整文件字节，列出卡／Claim／用途、旧快照与定位、旧／当前指纹、可恢复的旧片段、差异及修订建议。`guidance` 变化列为导航待复核；`historical` 保持固定历史用途，不因当前代码改变就宣称历史结论失效。缺失文件、不可读或未授权路径分别报告；源文件／配置在观察期间变化时保守列缺口。匹配指纹不证明知识语义。

只在本操作 `.build/operations/<operation_id>/` 新建 JSON、Markdown 及只读解析的请求／响应。返回 `phase: reported`、`data.audit_ref/report_ref/complete/status/counts`；`data.status` 为 `passed`、`needs_review` 或 `incomplete`，CLI 的成功仅表示实际报告已生成。新 [巡检产物契约](artifacts/audit-result.yaml) 与旧节点结果分开。报告附手动进入 ingest 的提示词，本动作不调用 ingest Workflow、不改源码、卡、来源锁、事件、水位或活动索引，不运行 apply／advance，也不捕获新来源。
