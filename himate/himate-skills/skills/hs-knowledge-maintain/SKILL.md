---
name: hs-knowledge-maintain
description: 检查正式知识的来源引用与定位问题；用于独立审计，不承担巡检编排。
---

# 只读来源审计

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。

## 执行

当前节点提供 `knowledge_maintain_audit` 时使用它。使用 CLI 时运行 `knowledge maintain audit --json`，检查正式卡与登记来源的引用及定位。报告实际问题和涉及的卡、文件，不自动修卡或修改来源。

文档新增或变更使用 ingest Workflow；已有代码引用的持续复核及修复使用 lint Workflow。独立审计不清理 `.build`，不触发同步，不推进文件成功处理版本。
