---
name: hs-knowledge-patrol-reindex
description: 从正式卡和来源登记重建关系及检索索引；用于巡检L3。
---

# 刷新巡检索引

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

运行 `knowledge patrol reindex --json`。`reindexed` 后交 L4。

只重建数据库关系与检索索引，不修改知识结论或原件，不把索引重建当作代码／文档内容已处理。失败报告具体问题。
