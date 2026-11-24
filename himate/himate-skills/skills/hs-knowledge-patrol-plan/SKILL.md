---
name: hs-knowledge-patrol-plan
description: 从实际变化中选择文档入库、已有卡维护或索引刷新任务，用于 L2。
---

# 选择并分流巡检待办

沿用本轮已确认的知识根、执行端和 CLI 入口。独立使用时先读取该根的 `AGENTS.md`、`config.yml`，运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标。下文 `knowledge` 指实际入口，工作目录为知识根，每次调用传入同一 `--knowledge-root`。

运行 `knowledge patrol plan --json`，采用 CLI 返回的待办和变化类型，不根据文件名或记忆改选来源。

- `needs_ingest`：原样交接 `data.next_file` 的来源身份、路径及变化类型，进入文档 P1。
- `needs_maintenance`：原样交接选定来源及维护任务，进入 L3。已引用代码的缺基线、代码变化或引用问题，以及文档删除属于已有卡维护。
- `needs_reindex`：无内容待办但索引过期，进入 L7。
- `unchanged`：进入 L8 汇总。

代码范围限于已登记且被正式卡直接引用的文件。`baseline_missing` 表示缺复核基线，不表示代码尚未全文入库。任务类型与范围由 CLI 根据实际来源登记和正式引用确定，调用失败报告真实错误。
