---
name: hs-knowledge-patrol-prepare
description: 为巡检选定的已有卡维护任务固定来源版本、关联卡和证据入口，用于 L3。
---

# 准备关联卡维护材料

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

使用 L2 交接的完整来源 ID 作为 `knowledge_maintain_prepare` 的 `source`。使用 CLI 时运行 `knowledge maintain prepare --source <source_id> --json`。采用回执根据正式来源登记与引用确定的任务，不自行选择另一来源或扩大卡片范围。

- `prepared`：核对 `.build/task.json` 的 `task_type: card_maintenance`、`maintenance_id`、实际来源版本及 `affected_cards`。当前材料见 `source.original_ref/text_ref`，可信旧版可用时见 `source.previous_ref/previous_text_ref`，原卡见各项 `original_ref`。连同实际 `history_gap` 和可用的 `location_candidates_ref` 交给 L4。
- `unchanged`：如实交接本来源暂无维护待办，由 Workflow 重新选择。
- `blocked` 或调用失败：报告具体材料、定位或执行缺口，保留待办。

缺复核基线表示需要核验既有卡，不能据此将代码当作尚未全文入库的文档。当前与历史材料的可用性分开说明，无法恢复的旧版本不能冒充已读。原件及正式卡在本步保持只读。
