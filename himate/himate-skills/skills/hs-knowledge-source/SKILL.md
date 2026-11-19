---
name: hs-knowledge-source
description: 按本次入库范围或巡检选定来源准备一批变化、PDF续办材料及关联卡；用于P1。
---

# 单文件来源准备

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 执行

运行 `knowledge ingest scan --json`；指定来源时加 `--source` 和实际路径或来源 ID。该命令初始化本轮 `.build`，以内容 hash 和正式处理进度找一份新增、修改、删除或尚未评估完的来源，并通过数据库反查关联卡。

独立 ingest Workflow 首次进入时交接任务原始范围，各批保持：未指定来源时每次运行普通 scan，不把上一批 `source_id` 当作后续扫描范围；指定文件、目录或来源 ID 时每批采用该范围。沿用已验证的 CLI 命令前缀、`parser`、`review_text_budget` 和 `review_page_budget` 配置，避免续办时退回默认解析方式或预算。

- `prepared`：交接 task、固定原件和关联卡。PDF、DOCX、XLSX 的 `task.document_review` 提供本轮 `packet_ref`、索引 `index_ref` 与完整 `markdown_ref`。候选稿中的 `images/` 路径以 `markdown_ref` 所在目录为准。连同已验证的 CLI 入口进入 P2。
- `blocked`：P1 的转换或图片准备仍有缺口。报告 `data.gaps` 和固定清单中的实际错误及位置，在 P1 修正后重试。
- `unchanged`：独立 ingest 的原始范围无待办，汇总各批实际结果并结束；巡检仅说明 L2 本次选定来源无待办，回 L2 重新选择，不据此宣称整轮无待办。
- 读取或运行失败：说明具体错误，不能当作无变化或删除。

巡检已选文件时完整采用本次 L2 交接的 `source_id`，不改成另一个来源。巡检每批完成后由 L2 选择下一来源；独立 ingest 每批成功后按原始范围回 P1 继续扫描。P5 失败后留在 P5 重试，不重新扫描或清暂存；P2 暂缓则按所属 Workflow 报告阻塞和未完成来源，不立即重扫同一来源。原件只读。

三种格式在 P1 转出完整 Markdown、原图链接和适用的离线 OCR，再从最早未评估单元备料。单轮 Markdown 正文上限为 76,000 UTF-8 字节，保守对应 80k token。解析缓存位于 `artifacts/ingest/parsed/`，累计进度留在正式来源登记。具体字段见[来源操作](references/materials.md)。

PDF 原生文字和本地图片 OCR 均由 P1 自动备好。模型由安装部署提前准备。对未改来源重新评估时，用具体已登记 ID 和 `reprocess: true` 开始，后续各批按同一范围普通续办。首批成功前保留旧成功事实。

新增主题由 P2 判断；脚本反查只提供已有引用候选。需要来源登记、关系查询或旧版时，读[来源操作](references/materials.md)。
