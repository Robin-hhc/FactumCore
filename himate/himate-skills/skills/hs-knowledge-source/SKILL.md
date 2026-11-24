---
name: hs-knowledge-source
description: 按指定文档范围准备同版材料、图片和关联旧卡，支持长文续办，用于 P1。
---

# 准备文档材料

复用 Workflow 已确认的知识根、执行端和 CLI 入口。独立使用时先读取知识根的 `AGENTS.md`、`config.yml`，用实际入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标。下文 `knowledge` 均指该入口，工作目录为知识根，每次调用传入同一 `--knowledge-root`。

## 执行

运行 `knowledge ingest scan --json`，指定文档、目录或来源 ID 时加 `--source`。采用本次任务的原始范围，每批保留解析配置和阅读预算。未限定来源时不把上一批来源 ID 变成后续扫描范围。巡检已选中文档时，仅扫描交接的来源。

有宿主提供的 `upload_ingest` 时，先按[上传批次约定](references/upload-batch.md)核对执行端、当前文件哈希和批次位置。其余文档材料字段及旧 PDF 兼容见[来源操作](references/materials.md)。

- `prepared`：核对 task 的 `task_type: document_ingest`，再交接实际 task、固定原件和关联旧卡。PDF、DOCX、XLSX 使用 `task.document_review` 的 `packet_ref`、`index_ref`、`markdown_ref`。图片相对路径从完整 `markdown_ref` 所在目录解析，连同同版材料入口交 P2。返回维护任务时报告应使用 lint 的维护分支，不按文档交给 P2。
- `blocked`：报告 `data.gaps` 中的解析、图片或原件缺口及具体位置，保留当前来源待办。
- `unchanged`：只确认本次扫描范围暂无待办，由 Workflow 决定继续选源或结束。
- 调用或读取失败：保留真实错误，不能据此判断无变化或原件已删除。

原件只读。P5 失败时保留当前已审批次，不重新扫描或清暂存。对未改文档重评时，首批使用具体已登记 ID 和 `reprocess: true`，后续按原范围普通续办。

三种转换格式会备好全文 Markdown、原图及适用的离线 OCR，按最早未评估单元续办。模型由部署准备，累计进度保存在来源登记。新增知识主题由 P2 判断，脚本反查的旧卡仅提供引用候选。
