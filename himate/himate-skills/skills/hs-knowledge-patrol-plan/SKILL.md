---
name: hs-knowledge-patrol-plan
description: 发现一个待处理raw或被正式卡引用的已登记代码文件，并判断是否仅需重建索引；用于L2。
---

# 选择巡检待办

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

运行 `knowledge patrol plan --json`，让脚本比较来源内容 hash 和各文件的成功处理版本。

- `needs_ingest`：交接 `data.next_file` 的真实 `source_id/kind/path`，进入 P1，用该来源 ID 准备本轮材料。
- `needs_reindex`：无内容待办且索引需刷新，进入 L3。
- `unchanged`：进入 L4 报告剩余事项。

本步不创建 `.build`，不让 Agent 阅读全库处置表。代码只追踪已登记且被正式卡引用的文件；不扩大到未登记的间接依赖。失败说明具体缺口。
