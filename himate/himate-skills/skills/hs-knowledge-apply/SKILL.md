---
name: hs-knowledge-apply
description: 发布通过 P4 的文档候选，更新索引并登记本批实际阅读范围，用于 P5。
---

# 发布文档入库结果

复用 Workflow 已确认的知识根、执行端和 CLI 入口。独立使用时先读取知识根的 `AGENTS.md`、`config.yml`，用实际入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标。下文 `knowledge` 均指该入口，工作目录为知识根，每次调用传入同一 `--knowledge-root`。

确认本批已经通过 P4，调用 `knowledge_ingest_commit`。独立部署运行 `knowledge ingest commit --json`。核对计划、同版材料及候选，写正式卡、执行已审删除并更新索引。PDF、DOCX、XLSX 仅合并本批实际审阅范围，覆盖全文后才登记整份文档完成。

本批无产卡时，将 P4 确认的实际不改卡理由作为 `reason`。独立部署将 `{"reason":"实际不改卡理由"}` 写入 `.build/commit.json`，运行 `knowledge ingest commit --input .build/commit.json --json`。

执行失败时保留 `.build` 和已审稿。可用 `knowledge_ingest_status`（独立部署用 `knowledge ingest status --json`）核对当前任务或最近回执，并确认回执属于本批。修正执行问题后重试原批次。只有确认本批尚未写入正式库且必须修改候选时，才带具体问题交回 P3，再经 P4。已写入或无法确认写入状态时保留现场，完成同批重试或报告失败，不重新扫描。

交接本次命令的实际来源、已评估范围、卡片变动和剩余范围。`completed` 表示本批发布完成，`source_complete: true` 才表示整份文档完成。后续流转由 Workflow 编排，沿用原范围和解析配置。

如返回 `data.receipt_warning`，以本次命令结果为准，`artifacts/ingest/latest.json` 可能仍是上一批。派生缓存和正式进度不随本批清理，暂缓与失败保留未完成事项。
