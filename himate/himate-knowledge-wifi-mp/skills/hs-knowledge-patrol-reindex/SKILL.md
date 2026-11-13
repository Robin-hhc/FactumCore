---
name: hs-knowledge-patrol-reindex
description: 从正式卡和来源登记重建关系及检索索引；用于巡检L3。
---

# 刷新巡检索引

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。复用 Workflow 首节点或宿主已确认的知识根与执行端。独立使用时先确认这两项，再读取该知识根的 `AGENTS.md` 和 `config.yml`。

## 执行

运行 `knowledge patrol reindex --json`。`reindexed` 后交 L4。

只重建数据库关系与检索索引，不修改知识结论或原件，不把索引重建当作代码／文档内容已处理。失败报告具体问题。
