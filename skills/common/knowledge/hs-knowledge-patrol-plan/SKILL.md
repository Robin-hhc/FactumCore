---
name: hs-knowledge-patrol-plan
description: 发现一个待处理raw或已登记代码文件，并判断是否仅需重建索引；用于L2。
---

# 选择巡检待办

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 执行

运行 `knowledge patrol plan --json`，让脚本比较来源内容 hash 和各文件的成功处理版本。

- `needs_ingest`：交接 `data.next_file` 的真实 `source_id/kind/path`，进入 P1，用该来源 ID 准备本轮材料。
- `needs_reindex`：无内容待办且索引需刷新，进入 L3。
- `unchanged`：进入 L4 报告剩余事项。

本步不创建 `.build`，不让 Agent 阅读全库处置表。代码只追踪已登记文件；不扩大到未登记的间接依赖。失败说明具体缺口。
