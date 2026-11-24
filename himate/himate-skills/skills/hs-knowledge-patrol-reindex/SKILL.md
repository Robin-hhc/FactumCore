---
name: hs-knowledge-patrol-reindex
description: 从正式卡和来源登记刷新关系及检索索引，用于巡检 L7。
---

# 刷新巡检索引

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。

## 执行

调用 `knowledge_patrol_reindex`，使用 CLI 时运行 `knowledge patrol reindex --json`。已有索引时增量更新，首次生成完整索引。收到 `reindexed` 后交 L2。

索引刷新更新派生数据，知识结论、原件和已处理的来源版本沿用正式资料。失败报告具体问题。
