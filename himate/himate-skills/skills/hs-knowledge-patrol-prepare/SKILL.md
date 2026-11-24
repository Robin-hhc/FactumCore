---
name: hs-knowledge-patrol-prepare
description: 为巡检选定的已有卡维护任务固定来源版本、关联卡和证据入口，用于 L3。
---

# 准备关联卡维护材料

沿用本轮已确认的知识根、执行端和 CLI 入口。独立使用时先读取该根的 `AGENTS.md`、`config.yml`，运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标。下文 `knowledge` 指实际入口，工作目录为知识根，每次调用传入同一 `--knowledge-root`。

使用 L2 交接的完整来源 ID，运行 `knowledge maintain prepare --source <source_id> --json`。采用 CLI 根据正式来源登记与引用计算的任务，不自行选择另一来源或扩大卡片范围。

- `prepared`：核对 `.build/task.json` 的 `task_type: card_maintenance`、`maintenance_id`、实际来源版本及 `affected_cards`。当前材料见 `source.original_ref/text_ref`，可信旧版可用时见 `source.previous_ref/previous_text_ref`，原卡见各项 `original_ref`。连同实际 `history_gap` 和可用的 `location_candidates_ref` 交给 L4。
- `unchanged`：如实交接本来源暂无维护待办，由 Workflow 重新选择。
- `blocked` 或调用失败：报告具体材料、定位或执行缺口，保留待办。

缺复核基线表示需要核验既有卡，不能据此将代码当作尚未全文入库的文档。当前与历史材料的可用性分开说明，无法恢复的旧版本不能冒充已读。原件及正式卡在本步保持只读。
