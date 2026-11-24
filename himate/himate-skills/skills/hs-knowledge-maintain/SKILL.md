---
name: hs-knowledge-maintain
description: 检查正式知识的来源引用与定位问题；用于独立审计，不承担巡检编排。
---

# 只读来源审计

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

运行 `knowledge maintain audit --json`，检查正式卡与登记来源的引用及定位。报告实际问题和涉及的卡、文件，不自动修卡或修改来源。

文档新增或变更使用 ingest Workflow；已有代码引用的持续复核及修复使用 lint Workflow。独立审计不清理 `.build`，不触发同步，不推进文件成功处理版本。
