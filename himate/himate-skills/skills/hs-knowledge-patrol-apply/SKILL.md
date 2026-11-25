---
name: hs-knowledge-patrol-apply
description: 发布已经独立审阅的关联卡维护批次并记录复核结果，用于 L6。
---

# 发布关联卡维护结果

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

确认本批通过 L5 后调用 `knowledge_maintain_commit`。零改卡时传入实际复核理由 `reason`。采用 CLI 时运行 `knowledge maintain commit --json`。零改卡时，将 `reason` 写入 `.build/commit.json`，用 `knowledge maintain commit --input .build/commit.json --json` 登记。

以命令回执交接实际修改的 `card_ids`、本批复核的 `reviewed_card_ids`、`reviewed_hash`、`source_exists` 及 `maintenance_complete`。回执表达关联卡维护和来源复核结果，不表达整份代码入库或文档阅读覆盖。出现 `receipt_warning` 时以本次返回值为准，不使用可能陈旧的落盘回执。

执行失败时保留已审批次和 `.build`，修正执行问题后直接重试。确认尚未写入且候选必须改动时退回 L4，再经 L5。输入版本失效仅在确认未发布且可重新备料时回 L3，无法确认写入状态时保留现场并报告失败。`deferred` 保留实际缺口及待办，不宣称维护完成。成功后的后续选择由 Workflow 编排。
