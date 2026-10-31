---
name: hs-knowledge-maintain
description: 检查正式知识的来源引用与定位问题；用于独立审计，不承担巡检编排。
---

# 只读来源审计

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 执行

运行 `knowledge maintain audit --json`，检查正式卡与登记来源的引用及定位。报告实际问题和涉及的卡、文件，不自动修卡或修改来源。

需要更新内容时使用 ingest Workflow；需要持续发现 raw 和代码变更时使用 lint Workflow。独立审计不清理 `.build`，不触发同步，不推进文件成功处理版本。
