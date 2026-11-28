---
name: hs-knowledge-apply
description: 发布通过 P4 的文档候选，更新索引并登记本批实际阅读范围，用于 P5。
---

# 发布文档入库结果

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

确认本批已经通过 P4，调用 `knowledge_ingest_commit`。使用 CLI 时运行 `knowledge ingest commit --json`。核对计划、同版材料及候选，写正式卡、执行已审删除并更新索引。code_ref 的 evidence_version 由程序根据本轮实际核验的源码保存，不手工补写；源码已变时按诊断重新核对候选并经 P4，不把发布时的新内容冒充已审版本。PDF、DOCX、XLSX 仅合并本批实际审阅范围，覆盖全文后才登记整份文档完成。

本批无产卡时，将 P4 确认的实际不改卡理由作为 `reason`。使用 CLI 时将 `{"reason":"实际不改卡理由"}` 写入 `.build/commit.json`，运行 `knowledge ingest commit --input .build/commit.json --json`。

执行失败时保留 `.build` 和已审稿。可用 `knowledge_ingest_status`（CLI 对应 `knowledge ingest status --json`）核对当前任务或最近回执，并确认回执属于本批。修正执行问题后重试原批次。只有确认本批尚未写入正式库且必须修改候选时，才带具体问题交回 P3，再经 P4。已写入或无法确认写入状态时保留现场，完成同批重试或报告失败，不重新扫描。

交接本次命令的实际来源、已评估范围、卡片变动和剩余范围。`completed` 表示本批发布完成，`source_complete: true` 才表示整份文档完成。后续流转由 Workflow 编排，沿用原范围和解析配置。

如返回 `data.receipt_warning`，以本次命令结果为准，`artifacts/ingest/latest.json` 可能仍是上一批。派生缓存和正式进度不随本批清理，暂缓与失败保留未完成事项。
