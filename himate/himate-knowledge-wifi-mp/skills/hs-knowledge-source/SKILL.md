---
name: hs-knowledge-source
description: 按本次入库范围或巡检选定来源准备一批变化、PDF续办材料及关联卡；用于P1。
---

# 单文件来源准备

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。复用 Workflow 首节点或宿主已确认的知识根与执行端。独立使用时先确认这两项，再读取该知识根的 `AGENTS.md` 和 `config.yml`。

## 执行

运行 `knowledge ingest scan --json`；指定来源时加 `--source` 和实际路径或来源 ID。该命令初始化本轮 `.build`，以内容 hash 和正式处理进度找一份新增、修改、删除或尚未评估完的来源，并通过数据库反查关联卡。

独立 ingest Workflow 首次进入时交接任务原始范围，各批保持：未指定来源时每次运行普通 scan，不把上一批 `source_id` 当作后续扫描范围；指定文件、目录或来源 ID 时每批采用该范围。沿用已验证的 CLI 命令前缀、`parser`、`review_text_budget` 和 `review_page_budget` 配置，避免续办时退回默认解析方式或预算。

- `prepared`：交接 task、文件副本、来源 ID 和关联卡。有 `task.pdf_review` 时交接起点、候选结束页、`packet_ref` 和 `page_index_ref`；P2 按需分段读取候选包，自选实际结束页，不要求一次读完。完整 `source.parsed` 用于核对结构、图表及必要补读。非 PDF 继续交接阅读稿、结构 JSON、图片及缺口；来源删除沿用原有交接。连同实际执行端、知识根及已验证的 CLI 命令前缀进入 P2。
- `unchanged`：独立 ingest 的原始范围无待办，汇总各批实际结果并结束；巡检仅说明 L2 本次选定来源无待办，回 L2 重新选择，不据此宣称整轮无待办。
- 读取或运行失败：说明具体错误，不能当作无变化或删除。

巡检已选文件时完整采用本次 L2 交接的 `source_id`，不改成另一个来源。巡检每批完成后由 L2 选择下一来源；独立 ingest 每批成功后按原始范围回 P1 继续扫描。P5 失败后留在 P5 重试，不重新扫描或清暂存；P2 暂缓则按所属 Workflow 报告阻塞和未完成来源，不立即重扫同一来源。原件只读。

PDF 默认按 400000 等效字符准备宽候选，无默认页数帽；需要时可显式设字量或页数预算，计量和字段见[来源操作](references/materials.md)。候选量不是本轮必读量，P2 按上下文与材料复杂度截断；起点固定为最早未评估页。PDF 解析缓存位于 `artifacts/ingest/parsed/`，可删重建；累计进度在正式来源登记，清 `.build` 不清进度。非 PDF 解析仍随本轮 `.build/materials/parsed` 清理。

不默认导出所有整页图片。native 解析不做 OCR；扫描件需要已准备本地模型和显式 standard 配置，业务步骤不安装或下载模型。转换状态和 OCR 文本不证明图片已被理解。用户要求重新评估未改来源时，用具体已登记 ID 和 `reprocess: true` 的 JSON 请求，仅首次 P1 使用；PDF 将从第 1 页开始新一轮评估，P5 首批成功前保留旧成功事实。后续 P1 按同一范围普通续办，不再传 `reprocess: true`，也不手工清空成功 hash。

新增主题由 P2 判断；脚本反查只提供已有引用候选。需要来源登记、关系查询或旧版时，读[来源操作](references/materials.md)。
