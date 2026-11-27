---
name: hs-knowledge-maintain
description: 检查正式卡已引用登记来源的路径能否解析、文件是否存在；用于独立只读审计，不承担巡检编排。
---

# 只读来源审计

沿用本轮已确认的知识根和执行端。当前会话确实提供 `knowledge_maintain_audit` 时，调用它并沿用其绑定的知识根；普通会话未提供此工具时，按下文使用 CLI，本 Skill 不以安装 MCP 为前提。采用 MCP 后，调用被拒、失败或返回 `blocked` 时按实际诊断处理，不改用 CLI 绕过原绑定或授权。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 执行

使用 CLI 时运行 `knowledge maintain audit --knowledge-root <知识根绝对路径> --json`。检查范围是正式卡已引用的登记来源：路径能否解析、对应文件是否存在。按本次 `findings` 报告实际问题和涉及的来源文件、已知关联卡，不自动修卡或修改来源。

`phase=passed`、`findings=[]` 仅说明上述范围未发现问题，不证明文件内容可读取、代码符号或行号正确、卡片结论仍成立，也不能确认未被正式卡引用的原件已入库。

文档新增或变更使用 ingest Workflow；已有代码引用的持续复核及修复使用 lint Workflow。独立审计不清理 `.build`，不触发同步，不推进文件成功处理版本。
