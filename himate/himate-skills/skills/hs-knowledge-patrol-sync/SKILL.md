---
name: hs-knowledge-patrol-sync
description: 按明确配置执行工作区同步；用于巡检L1。
---

# 同步工作区

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

配置同步时，只使用控制端明确提供的 `sync.argv/cwd`，在已确认执行端运行 `knowledge patrol sync --input SYNC.json --json`。未配置同步时，用 OpenFlow 提供的 `knowledge_patrol_sync`（无参数）确认跳过；独立部署可运行 `knowledge patrol sync --json`。回执 `data.synchronized: false` 表示未执行同步。

内部 Git-MM 在实际工作区根执行 `git mm sync`；具体参数由内部适配填写，不猜测 `git mm log` 等命令。子仓版本读取使用原生 Git。

成功 `synced` 或未配置同步时交 L2。同步后沿用本轮工具入口和版本，新起 CLI 读取当时的知识库配置与源码；失败保留具体错误，本轮不继续。请求示例见[同步请求](references/request.md)。
