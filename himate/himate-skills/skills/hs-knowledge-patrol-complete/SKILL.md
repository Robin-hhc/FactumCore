---
name: hs-knowledge-patrol-complete
description: 汇总本轮实际处理结果及剩余待办；用于巡检 L8。
---

# 报告巡检结果

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

调用 `knowledge_patrol_complete`，独立部署运行 `knowledge patrol complete --json`。结合本轮各次 P5、L6 和 L7 回执，报告文档已入库范围、代码巡检修订或确认有效的卡片、索引刷新、剩余事项和实际错误。列出代码巡检发现的独立新主题及证据位置，注明这些主题未立卡。

`completed` 表示完成本轮统计，不代表所有来源都已消除欠账；按返回的剩余数量和原因说明。文件成功标记已由各次 P5 或 L6 保存，本步不另建全库水位或通过凭据。
