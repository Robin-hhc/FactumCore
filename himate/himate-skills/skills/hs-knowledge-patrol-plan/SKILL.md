---
name: hs-knowledge-patrol-plan
description: 选择一项文档入库或代码关联卡复核待办，并判断索引状态。用于巡检 L2。
---

# 选择巡检待办

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

使用支持代码复核的 knowledge CLI（0.25.0 及以后版本）。执行端版本较旧或待办回执缺少 `change` 时，报告需要在该执行端升级 CLI。

运行 `knowledge patrol plan --json`，采用脚本返回的待办和变化类型。

- `needs_ingest`：原样交接 `data.next_file` 的 `source_id`、`kind`、`path` 和 `change`，进入 P1。 `kind: raw` 按文档入库处理。 `kind: code` 复核已有引用卡，`baseline_missing` 表示缺少复核基线，`modified` 和 `deleted` 表示源码变更与缺失，`reference_invalid` 表示发现已有引用问题。
- `needs_reindex`：无内容待办且索引需刷新，进入 L3。
- `unchanged`：进入 L4 报告剩余事项。

本步仅选择待办。代码范围为已登记且被正式卡直接引用的文件。失败说明具体缺口。
