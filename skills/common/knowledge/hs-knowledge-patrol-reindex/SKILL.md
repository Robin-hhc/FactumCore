---
name: hs-knowledge-patrol-reindex
description: 从正式卡和来源登记重建关系及检索索引；用于巡检L3。
---

# 刷新巡检索引

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 执行

运行 `knowledge patrol reindex --json`。`reindexed` 后交 L4。

只重建数据库关系与检索索引，不修改知识结论或原件，不把索引重建当作代码／文档内容已处理。失败报告具体问题。
