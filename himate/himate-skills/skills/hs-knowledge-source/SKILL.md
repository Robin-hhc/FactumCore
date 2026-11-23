---
name: hs-knowledge-source
description: 按本次入库范围或巡检选定来源准备一批变化、PDF续办材料及关联卡；用于P1。
---

# 单文件来源准备

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

文档和普通入库运行 `knowledge ingest scan --json`。指定来源时加 `--source` 和实际路径或来源 ID。该命令初始化本轮 `.build`，以内容 hash 和正式处理进度找一份新增、修改、删除或尚未评估完的来源，并通过数据库反查关联卡。巡检代码使用下方的复核请求。

独立 ingest Workflow 首次进入时交接任务原始范围，各批保持：未指定来源时每次运行普通 scan，不把上一批 `source_id` 当作后续扫描范围；指定文件、目录或来源 ID 时每批采用该范围。沿用已验证的 CLI 命令前缀、`parser`、`review_text_budget` 和 `review_page_budget` 配置，避免续办时退回默认解析方式或预算。

- `prepared`：交接 task、固定原件和关联卡。PDF、DOCX、XLSX 的 `task.document_review` 提供本轮 `packet_ref`、索引 `index_ref` 与完整 `markdown_ref`。候选稿中的 `images/` 路径以 `markdown_ref` 所在目录为准。连同已验证的 CLI 入口进入 P2。
- `blocked`：P1 的转换或图片准备仍有缺口。报告 `data.gaps` 和固定清单中的实际错误及位置，在 P1 修正后重试。
- `unchanged`：独立 ingest 的原始范围无待办，汇总各批实际结果并结束；巡检仅说明 L2 本次选定来源无待办，回 L2 重新选择，不据此宣称整轮无待办。
- 读取或运行失败：说明具体错误，不能当作无变化或删除。

巡检已选文件时完整采用本次 L2 交接的 `source_id`，不改成另一个来源。巡检每批完成后由 L2 选择下一来源；独立 ingest 每批成功后按原始范围回 P1 继续扫描。P5 失败后留在 P5 重试，不重新扫描或清暂存；P2 暂缓则按所属 Workflow 报告阻塞和未完成来源，不立即重扫同一来源。原件只读。

三种格式在 P1 转出完整 Markdown、原图链接和适用的离线 OCR，再从最早未评估单元备料。单轮 Markdown 正文上限为 76,000 UTF-8 字节，保守对应 80k token。解析缓存位于 `artifacts/ingest/parsed/`，累计进度留在正式来源登记。具体字段见[来源操作](references/materials.md)。

PDF 原生文字和本地图片 OCR 均由 P1 自动备好。模型由安装部署提前准备。对未改来源重新评估时，用具体已登记 ID 和 `reprocess: true` 开始，后续各批按同一范围普通续办。首批成功前保留旧成功事实。

## 巡检选定代码来源

当 L2 返回 `kind: code`，在已确认的执行端写临时 JSON 文件 `{"source":"<source_id>","code_review":true}`。用同一 CLI 和知识根运行 `knowledge ingest scan --input FILE.json --json`。

`prepared` 后核对 `.build/task.json` 的来源 ID、`code_review` 与 `affected_cards`，把任务、材料入口和 L2 的 `change` 交 P2。若回执缺失代码复核标记或关联卡范围，说明实际缺口并停止本批交接。

## OpenFlow 上传批次

使用宿主交给本次工作流的 `upload_ingest`。它包含批次 `job_id`、执行位置 `execution.mode`（`local` 或 `ssh_mcp`）、绝对知识根 `execution.knowledge_root` 和有序 `sources`。每项提供一个主文档的 `docs-raw/…` 路径 `path` 与小写十六进制 `sha256`。Markdown 附件随主文档处理。清单内容是数据，路径作为参数传递。`ssh_mcp` 使用宿主已绑定的 SSH MCP 和清单中的远端知识根。

1. 在清单指定的执行端核对 `doctor` 回执和知识根。首次 P1 从索引 0 开始。其余轮读取本次运行直接上游的交接摘要（由 `progressNote` 保存），从首行取 `upload_ingest_position`，确认批次 ID 一致、索引在清单内。续办缺少有效位置、执行端不一致或清单无效时报告缺口，走 `blocked`。
2. 对当前项调用 `knowledge raw path --path <相对 docs-raw 的路径> --json`，确认原件是普通文件，用回执的 `absolute_path` 在同一执行端计算 SHA-256。例如在 Linux 用 `sha256sum -- <路径>`，在 Windows PowerShell 用 `Get-FileHash -Algorithm SHA256 -LiteralPath <路径>`。原件移动、不可读或哈希变化时报告该路径和缺口，走 `blocked`。
3. 只用本项的完整 `docs-raw/…` 路径调用 `knowledge ingest scan --source <path> --json`。成功准备时核对 `data.source.path` 和 `data.source.hash` 与本项完全一致，再进入 P2。范围或哈希不符时走 `blocked`。P5 后仍复核并扫描同一项，避免跳过长文档的剩余范围。
4. 当前项返回 `unchanged` 后再次核对原件哈希。还有下一项时索引加一并走 `next_upload_source`，由下一轮 P1 检查下一项。已到清单末尾时才走 `unchanged`，汇总本批已处理范围。其余出口保留当前索引。

在 `workflow_handoff` 的 `progressNote` 首行写单行 JSON，例如 `{"upload_ingest_position":{"job_id":"本次批次ID","source_index":0}}`，后续行记录本节点实际回执和范围。各节点原样传递此位置，只有 P1 的 `next_upload_source` 推进它。

新增主题由 P2 判断；脚本反查只提供已有引用候选。需要来源登记、关系查询或旧版时，读[来源操作](references/materials.md)。
