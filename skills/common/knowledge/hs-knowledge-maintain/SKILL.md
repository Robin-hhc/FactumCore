---
name: hs-knowledge-maintain
description: Register exact source-change events, block affected Claims and advance review state only from verified applied and activated evidence.
---

首次使用或缺项目入口信息时，先用已安装的 `hs-knowledge-explore` 运行 setup 并读取项目 `config.yml`；已具备上下文就直接复用。默认使用实际执行机器已有的全局 Python，缺依赖时再由 setup 补齐。

跨机器连接信息放在该 Skill 的 `config.env`，由 Agent/harness 按提示通过 SSH 到服务器执行并检查结果，不要求复制工具或另建 runner。请求、稿件和结果继续放实际知识根已有的 `.build/`、`logs/`、`artifacts/`。

本 Skill 可由人工单独调用。只校验本次业务输入、实际文件及输出，不检查 Workflow 顺序或上游通过凭证。流程顺序、角色分工与交棒合法性由 OpenFlow 的 Workflow 管理；人工测试时由人选择顺序。

Use `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K  --action inspect-context|register-source-change|register-code-change|recover-events|status|advance`. All event changes use the domain cooperative writer lock. [Request details](references/request.md) explain the proof requirements.

`inspect-context` 在 ingest 开始时只读比较实际来源、代码/配置和规则身份，输出受影响 Claim、依赖和缺口，不要求先登记本机变化事件。未知上下文保留限制；P2—P5 修订、P6 记录和 P7 收尾后才能解除。query 另按相同当前引用和确切资格判断过滤，不因 raw 未变而信任旧代码。

Source capture may register new events and blocks; it never clears them. `advance` requires public apply verification, a verified activated generation and exact current card bytes. An index rollback cannot undo live blocks. User data, URLs, model assertions and old successful test records never authorize clearing a block.

The [artifact contract](artifacts/result.yaml) requires the actual per-attempt CLI manifest.
