---
name: hs-knowledge-query
description: 按关键词和可选标签检索正式知识卡，精读正文并沿来源核对答案。
---

# 搜索、精读与回源

沿用本轮已确认的知识根和执行端。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用其绑定的知识根。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。

## 检索

当前会话提供 `knowledge_search` 和 `knowledge_read` 时，用 `knowledge_search` 查询，传入 `query` 和所需的 `tags`。选出相关卡后调用 `knowledge_read`，传入 `card_id` 和搜索返回的 `view_revision`。采用 CLI 时用下面的命令。

```sh
knowledge search "关键词" --json
knowledge read CARD_ID --json
```

搜索返回完整卡的相关候选，不认证当前适用或已实现。需要标签时用 `--input`，检索整卡退役资料时用 `--include-deprecated`；请求和结果字段见[公开 API](references/public-api.md)。

先搜索，再读相关卡与必要来源，按问题核对正文条件、版本、依据性质及缺口。设计要求保持设计属性，代码行为和测量结论须有对应实际依据；卡片命中、stable 状态或代码定位不代替证明。回答附卡 ID、来源和未解决缺口。工具返回可用的卡片链接时（例如 `openflow_link`），以卡片标题为链接文字，原样引用。

读取当前来源时，采用 `read` 返回的 `sources` 及其实际路径基准。需要补查登记来源时使用 `knowledge_source_list`，需要确认历史版本时使用 `knowledge_source_resolve`，按 `source_id` 和已有版本参数回源。CLI 的 `source list/resolve` 参数见公开 API。

需要解析 PDF/Office/图片时用 `knowledge_source_extract`，CLI 对应 `source extract --input FILE.json --json`。实际打开相关图片并结合 OCR 和结构判断。用本次回执的 `read_id` 调用 `knowledge_source_renew` 延长阅读，完成后调用 `knowledge_source_release`。CLI 对应 `source renew/release`。外部图片链接、缺模型及未解析范围保留为缺口。

指定 PDF 物理页范围可取得 `role: page_preview`，逐页生成到像素和字节预算。按实际回执查看图片，需要时缩小范围补读。

空命中时检查关键词、显式标签、退役状态、截断和诊断，再有依据地调整检索。旧 draft 可按 ID 阅读，不自动升为正式可搜状态。运行失败不能当作有效空结果。

使用本次返回值。CLI 返回 `report_ref` 时，报告保存在 `artifacts/query/`，显式指定报告输出也使用该目录。查询材料与入库 `.build` 独立。

用户明确要求把本轮技术结论沉淀到组库时，使用 `hs-knowledge-capture`，交接本轮已核实的结论、适用条件和依据。

[公开 API](references/public-api.md)说明查询字段、旧参数错误及来源路径。
