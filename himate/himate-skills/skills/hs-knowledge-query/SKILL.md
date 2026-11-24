---
name: hs-knowledge-query
description: 按关键词和可选标签检索正式知识卡，精读正文并沿来源核对答案。
---

# 搜索、精读与回源

OpenFlow 提供知识库 MCP 时，查询使用宿主已绑定的知识根。工具拒绝、失败或返回 `blocked` 时，报告实际诊断。独立部署复用 Workflow 已确认的知识根、执行端和 CLI。首次使用时读取该根的 `AGENTS.md`、`config.yml`，在知识根运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。下文 CLI 示例都沿用同一 `--knowledge-root`。

## 检索

OpenFlow 用 `knowledge_search` 查询，传入 `query` 和需要的 `tags`。选相关卡后，用 `knowledge_read` 传入 `card_id` 和搜索返回的 `view_revision`。回答时以卡片标题为链接文字，原样使用返回的 `openflow_link`，并说明对应来源和未解决的缺口。独立部署用 CLI。

```sh
knowledge search "关键词" --json
knowledge read CARD_ID --json
```

搜索返回完整卡的相关候选，不认证当前适用或已实现。需要标签时用 `--input`，检索整卡退役资料时用 `--include-deprecated`；请求和结果字段见[公开 API](references/public-api.md)。

先搜索，再读相关卡与必要来源，按问题核对正文条件、版本、依据性质及缺口。设计要求保持设计属性，代码行为和测量结论须有对应实际依据；卡片命中、stable 状态或代码定位不代替证明。回答附卡 ID、来源和未解决缺口。

读取当前来源时，采用 `read` 返回的 `sources` 及其实际路径基准。需要补查登记来源时使用 `knowledge_source_list`，需要确认历史版本时使用 `knowledge_source_resolve`，按 `source_id` 和已有版本参数回源。独立部署的 `source list/resolve` 参数见公开 API。

需要解析 PDF/Office/图片时用 `knowledge_source_extract`，独立部署用 `source extract --input FILE.json --json`。实际打开相关图片并结合 OCR 和结构判断。用本次回执的 `read_id` 调用 `knowledge_source_renew` 延长阅读，完成后调用 `knowledge_source_release`。独立部署对应 `source renew/release`。外部图片链接、缺模型及未解析范围保留为缺口。

指定 PDF 物理页范围可取得 `role: page_preview`，逐页生成到像素和字节预算。按实际回执查看图片，需要时缩小范围补读。

空命中时检查关键词、显式标签、退役状态、截断和诊断，再有依据地调整检索。旧 draft 可按 ID 阅读，不自动升为正式可搜状态。运行失败不能当作有效空结果。

使用本次返回值。CLI 返回 `report_ref` 时，报告保存在 `artifacts/query/`，显式指定报告输出也使用该目录。查询材料与入库 `.build` 独立。

用户明确要求把本轮技术结论沉淀到组库时，使用 `hs-knowledge-capture`，交接本轮已核实的结论、适用条件和依据。

[公开 API](references/public-api.md)说明查询字段、旧参数错误及来源路径。
