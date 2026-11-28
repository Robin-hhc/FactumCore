---
name: hs-knowledge-patrol-prepare
description: 固定已有卡的引用证据和维护范围，区分程序定位修复与语义维护，用于 L3。
---

# 准备关联卡维护材料

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

使用 L2 交接的完整来源 ID 作为 `knowledge_maintain_prepare` 的 `source`。使用 CLI 时运行 `knowledge maintain prepare --source <source_id> --json`。采用回执根据正式来源登记与引用确定的任务，不自行选择另一来源或扩大卡片范围。

- `mechanical_prepared`：核对 `.build/task.json` 的 `task_type: card_maintenance`、`maintenance_id`、`mode: mechanical`、固定 `affected_cards` 和逐卡 `evidence_states`。采用程序生成的计划及定位候选，连同 `mechanical_check_ref` 指向的机械检查入口直接交 L6；本步不改候选，不调用内容检查伪造 L5 通过。
- `prepared`：核对同一任务身份、`mode: semantic`（旧任务可缺省）、实际来源观察及 `affected_cards`。有 `evidence_states` 时按其读取本卡需要判断的 changed、unresolved 或 unversioned 引用；文档删除任务按实际缺失事实和材料处理。原卡见各项 `original_ref`，历史材料可用时按任务入口读取。连同实际缺口和定位候选交 L4。同一卡混合多种状态时采用程序固定的语义任务，不把其中 relocated 引用另拆成机械发布。
- `unchanged`：如实交接本来源暂无维护待办，由 Workflow 重新选择。
- `blocked` 或调用失败：报告具体材料、定位或执行缺口，保留待办。

unversioned 或兼容的 baseline_missing 表示引用尚无已核验证据版本，不能据此将代码当作尚未全文入库的文档。缺版本、编码或权限等错误均不自行改成 mechanical_prepared；采用工具的实际 phase。当前与历史材料的可用性分开说明，无法恢复的旧版本不能冒充已读。原件及正式卡在本步保持只读，evidence_version 由程序管理。
