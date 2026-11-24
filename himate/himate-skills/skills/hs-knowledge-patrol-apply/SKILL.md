---
name: hs-knowledge-patrol-apply
description: 发布已经独立审阅的关联卡维护批次并记录复核结果，用于 L6。
---

# 发布关联卡维护结果

沿用本轮已确认的知识根、执行端和 CLI 入口。独立使用时先读取该根的 `AGENTS.md`、`config.yml`，运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标。下文 `knowledge` 指实际入口，工作目录为知识根，每次调用传入同一 `--knowledge-root`。

确认本批通过 L5 后运行 `knowledge maintain commit --json`。零改卡时，将实际复核理由写入 `.build/commit.json` 的 `reason`，用 `knowledge maintain commit --input .build/commit.json --json` 登记。

以命令回执交接实际修改的 `card_ids`、本批复核的 `reviewed_card_ids`、`reviewed_hash`、`source_exists` 及 `maintenance_complete`。回执表达关联卡维护和来源复核结果，不表达整份代码入库或文档阅读覆盖。出现 `receipt_warning` 时以本次返回值为准，不使用可能陈旧的落盘回执。

执行失败时保留已审批次和 `.build`，修正执行问题后直接重试。确认尚未写入且候选必须改动时退回 L4，再经 L5。输入版本失效仅在确认未发布且可重新备料时回 L3，无法确认写入状态时保留现场并报告失败。`deferred` 保留实际缺口及待办，不宣称维护完成。成功后的后续选择由 Workflow 编排。
