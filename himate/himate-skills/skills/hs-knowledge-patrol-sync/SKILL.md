---
name: hs-knowledge-patrol-sync
description: 按明确配置执行工作区同步；用于巡检L1。
---

# 同步工作区

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 执行

配置同步时，只使用控制端明确提供的 `sync.argv/cwd`，在已确认执行端运行 `knowledge patrol sync --input SYNC.json --json`。未配置同步时，当前会话提供 `knowledge_patrol_sync` 就调用它（无参数）确认跳过。采用 CLI 时运行 `knowledge patrol sync --json`。回执 `data.synchronized: false` 表示未执行同步。

内部 Git-MM 在实际工作区根执行 `git mm sync`；具体参数由内部适配填写，不猜测 `git mm log` 等命令。子仓版本读取使用原生 Git。

成功 `synced` 或未配置同步时交 L2。同步后沿用本轮知识根、执行端和版本。下一步使用同步后的配置与源码。同步失败时保留具体错误并结束本轮。请求示例见[同步请求](references/request.md)。
