---
name: hs-knowledge-source
description: 按指定文档范围准备同版材料、图片和关联旧卡，支持长文续办，用于 P1。
---

# 准备文档材料

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理，不改用 CLI 绕过原绑定或授权。

没有 Knowledge MCP 时，按下文使用 CLI，本 Skill 不要求先安装 MCP。远端使用当前 harness 已有且获准的 SSH 工具或 `ssh`，在已确认主机执行相同 CLI 并传远端绝对知识根。主机、知识根或命令入口不明时，核实已有信息后一起说明缺项，不猜路径，也不在本机替代远端执行。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 执行

当前会话提供 `knowledge_ingest_scan` 时使用它，按实际 schema 传入 `source` 和本次使用的转换选项。使用 CLI 时运行 `knowledge ingest scan --json`，指定文档、目录或来源 ID 时加 `--source`。采用本次任务的原始范围，每批保留解析配置和阅读预算。未限定来源时不把上一批来源 ID 变成后续扫描范围。巡检已选中文档时，仅扫描交接的来源。

有宿主提供的 `upload_ingest` 时，先按[上传批次约定](references/upload-batch.md)核对执行端、当前文件哈希和批次位置。其余文档材料字段及旧 PDF 兼容见[来源操作](references/materials.md)。

- `prepared`：核对 task 的 `task_type: document_ingest`，再交接实际 task、固定原件和关联旧卡。PDF、DOCX、XLSX 使用 `task.document_review` 的 `packet_ref`、`index_ref`、`markdown_ref`。图片相对路径从完整 `markdown_ref` 所在目录解析，连同同版材料入口交 P2。返回维护任务时报告应使用 lint 的维护分支，不按文档交给 P2。
- `blocked`：先看顶层 `diagnostics`，按下文处理明确的文档能力缺项。仍有阻塞时，报告 `data.gaps` 中的解析、图片或原件缺口及具体位置，保留当前来源待办。
- `unchanged`：只确认本次扫描范围暂无待办，由 Workflow 决定继续选源或结束。
- 调用或读取失败：保留真实错误，不能据此判断无变化或原件已删除。

原件只读。P5 失败时保留当前已审批次，不重新扫描或清暂存。对未改文档重评时，首批使用具体已登记 ID 和 `reprocess: true`，后续按原范围普通续办。

三种转换格式会备好全文 Markdown、原图及适用的离线 OCR，按最早未评估单元续办。顶层 `diagnostics` 明确返回 `PARSER_DEPENDENCIES_REQUIRED`、默认模型的 `PARSER_MODELS_REQUIRED` 或 `LIBREOFFICE_MISSING` 时，分别用 `hs-knowledge-setup` 的 `documents`、`ocr` 或 `libreoffice` 能力补齐同一执行端。自定义模型路径或 LibreOffice 命令配置错误按诊断处理。

复查通过后，在同一执行端沿用原调用方式、解析选项、阅读预算和其他请求参数重试。有 `upload_ingest` 时，保留 `upload_ingest_position` 中的批次和索引，按清单约定重新核对知识根、当前项路径和 SHA-256。核对通过后，将 `upload_ingest.sources[source_index].path` 的完整 `docs-raw/…` 路径传给 MCP 的 `source` 或 CLI 的 `--source`。原件或位置不符时按上传批次约定走 `blocked`，保留当前索引。

普通扫描将阻塞回执的 `data.source.source_id` 传给 `source` 或 `--source`，原请求未限定来源时也按该 ID 重试。若同一缺项复查后仍出现，报告实际回执并保留待办。准备成功后正常交 P2。已备批次处理完成后，上传批次继续核对清单当前项，普通扫描恢复原范围。累计进度保存在来源登记。新增知识主题由 P2 判断，脚本反查的旧卡仅提供引用候选。
