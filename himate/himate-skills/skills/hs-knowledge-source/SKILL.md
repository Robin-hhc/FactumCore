---
name: hs-knowledge-source
description: 按指定文档范围准备同版材料、图片和关联旧卡，支持长文续办，用于 P1。
---

# 准备文档材料

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 执行

当前会话提供 `knowledge_ingest_scan` 时使用它，按实际 schema 传入 `source` 和本次使用的转换选项。使用 CLI 时运行 `knowledge ingest scan --json`，指定文档、目录或来源 ID 时加 `--source`。采用本次任务的原始范围，每批保留解析配置和阅读预算。未限定来源时不把上一批来源 ID 变成后续扫描范围。巡检已选中文档时，仅扫描交接的来源。

有宿主提供的 `upload_ingest` 时，先按[上传批次约定](references/upload-batch.md)核对执行端、当前文件哈希和批次位置。其余文档材料字段及旧 PDF 兼容见[来源操作](references/materials.md)。

- `prepared`：核对 task 的 `task_type: document_ingest`，再交接实际 task、固定原件和关联旧卡。PDF、DOCX、XLSX 使用 `task.document_review` 的 `packet_ref`、`index_ref`、`markdown_ref`。图片相对路径从完整 `markdown_ref` 所在目录解析，连同同版材料入口交 P2。返回维护任务时报告应使用 lint 的维护分支，不按文档交给 P2。
- `blocked`：报告 `data.gaps` 中的解析、图片或原件缺口及具体位置，保留当前来源待办。
- `unchanged`：只确认本次扫描范围暂无待办，由 Workflow 决定继续选源或结束。
- 调用或读取失败：保留真实错误，不能据此判断无变化或原件已删除。

原件只读。P5 失败时保留当前已审批次，不重新扫描或清暂存。对未改文档重评时，首批使用具体已登记 ID 和 `reprocess: true`，后续按原范围普通续办。

三种转换格式会备好全文 Markdown、原图及适用的离线 OCR，按最早未评估单元续办。明确返回 `PARSER_MODELS_REQUIRED` 且缺的是默认模型时，用 `hs-knowledge-setup` 补齐，按原范围和来源续办。累计进度保存在来源登记。新增知识主题由 P2 判断，脚本反查的旧卡仅提供引用候选。
