---
name: hs-knowledge-patrol-complete
description: 汇总本轮实际处理结果及剩余待办；用于巡检 L8。
---

# 报告巡检结果

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 执行

调用 `knowledge_patrol_complete`，使用 CLI 时运行 `knowledge patrol complete --json`。结合本轮各次 P5、L6 和 L7 回执，报告文档已入库范围、代码巡检修订或确认有效的卡片、索引刷新、剩余事项和实际错误。按实际回执区分程序定位修复和经独立审阅的语义维护，不把机械发布描述成 L5 内容通过。列出代码巡检发现的独立新主题及证据位置，注明这些主题未立卡。

`completed` 表示完成本轮统计，不代表所有来源都已消除欠账；按返回的剩余数量和原因说明。文件成功标记已由各次 P5 或 L6 保存，本步不另建全库水位或通过凭据。
