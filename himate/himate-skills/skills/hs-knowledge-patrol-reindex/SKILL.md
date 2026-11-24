---
name: hs-knowledge-patrol-reindex
description: 从正式卡和来源登记刷新关系及检索索引，用于巡检 L7。
---

# 刷新巡检索引

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

运行 `knowledge patrol reindex --json`。已有索引时增量更新，首次生成完整索引。收到 `reindexed` 后交 L2。

索引刷新更新派生数据，知识结论、原件和已处理的来源版本沿用正式资料。失败报告具体问题。
