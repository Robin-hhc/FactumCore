---
name: hs-knowledge-query
description: 用于知识库里的项目术语、模块、能力、实际实现和依据查询，包括只问一个术语的短问题。
---

# 搜索、精读与回源

问题涉及已绑定项目的术语、模块或实际实现时，先查正式知识卡。即使用户只问「MLO 是啥」这类项目领域的术语，也先查库内用法和实现边界。明确只问通用概念时，按用户要求回答。

沿用本轮已确认的知识根和执行端。尚未确认时，以用户给出的目录或当前工作区内唯一可核实的知识根为候选，仍有歧义时询问用户。当前会话提供本步骤所需的 Knowledge MCP 工具时，调用该工具并沿用已确认的绑定。采用 MCP 时，缺少工具则报告工具名，调用被拒、失败或返回 `blocked` 时按实际诊断处理，不改用 CLI 绕过原绑定或授权。

没有 Knowledge MCP 时，按下文直接使用 CLI；本 Skill 不以安装 MCP 为前提。远端通过当前 harness 已有且获准的 SSH 工具或 `ssh` 连接，在已确认的主机执行 CLI，并传远端的绝对知识根。主机、知识根或命令入口仍不明确时，核实已有信息后一次说明缺项，不猜路径，也不把远端请求交给本机 CLI。

沿用已确认的执行端直接查询和读卡。自检或只读调用明确返回 `KNOWLEDGE_CLI_NOT_FOUND`、`KNOWLEDGE_REMOTE_CLI_NOT_FOUND`，或确认缺少启动入口、基础依赖时，用 `hs-knowledge-setup` 修复同一知识根的实际执行端。复查通过后继续使用原来的调用方式。环境仍阻塞时报告安装器回执。正式检索和读卡以知识工具的结果为准。绑定不明、权限、连接以及业务诊断按实际错误处理。

采用 CLI 时，从知识根运行该执行端已确认的 `knowledge` 入口，每次传入同一 `--knowledge-root`。首次单独使用 CLI 时，先读取知识根的 `AGENTS.md` 和 `config.yml`，运行 `knowledge doctor --knowledge-root <知识根绝对路径> --json` 核对目标和版本。命令找不到、启动入口有明确缺项或诊断仅表明缺运行依赖时，加载 `hs-knowledge-setup`，在同一执行端补齐并复查。得到与知识根匹配的就绪回执后继续原任务。

## 检索

从问题提取少量准确关键词，例如缩写、模块名或代码标识符，作为 `query`。通常先试一到三个关键词，保留用户明确指定的标签。检索成功但空命中时，缩短关键词，或按已知线索换用同义术语、标识符再查。读卡时仍按用户问的版本和适用条件核对。

当前会话提供 `knowledge_search` 和 `knowledge_read` 时，用 `knowledge_search` 查询，传入 `query` 和所需的 `tags`。选出相关卡后调用 `knowledge_read`，传入 `card_id` 和搜索返回的 `view_revision`。采用 CLI 时用已核实的命令入口执行。若 Setup 回执给出了 `knowledge.argv`，用它替换示例里的 `knowledge`。

```sh
knowledge search "关键词" --knowledge-root "<知识根绝对路径>" --json
knowledge read CARD_ID --knowledge-root "<知识根绝对路径>" --json
```

搜索返回完整卡的相关候选，不认证当前适用或已实现。CLI 需要标签时用 `--input`；普通 CLI `search` 的 `--include-deprecated` 可额外检索整卡退役资料，MCP 的发布视图搜索不支持此选项。CLI 需要按同一发布版本搜索、精读时，用 `library search/read`；请求和结果字段见[公开 API](references/public-api.md)。

先搜索，再读相关卡与必要来源，按问题核对正文条件、版本、依据性质及缺口。设计要求保持设计属性，代码行为和测量结论须有对应实际依据；卡片命中、stable 状态或代码定位不代替证明。

日常回答引用支撑结论的卡片，标明来源和未解决的缺口。找到直接支持结论的段落后，原样复制回执中对应段落的完整 `citation_markdown`。引用整卡或没有可用的段落引用时，复制整卡的 `citation_markdown`。旧回执只提供 `openflow_link` 时，优先选对应段落链接，整卡链接可作回退。用卡片标题作为 Markdown 链接文字，原样保留链接目标。宿主未提供链接时，用卡 ID 和来源标明依据。`path` 仅用于定位文件。用户明确要求只给简短结论时，按其格式答复，引用可省略。

需要核对当前登记代码时，从 `code_ref.code_id` 或对应 `sources[].source_id` 取得来源 ID，调用 `knowledge_source_resolve`，当前版本请求不附 `hash/commit/snapshot_id`，读取本次返回的 `text_ref` 或 `original_ref`。这些材料路径相对同一绑定知识根，沿用已确认的执行端；基准仍不明确时先核实宿主绑定信息，无法确认则报告缺口或询问，不按会话 cwd 拼接。只解释已读卡而不需要回源的回答，不必额外解析所有代码来源。

`sources[].path` 的基准来自绑定库配置，不由当前工作区或同名目录决定。确需直接打开登记原文件时，先核实该知识根的 `config.yml` 所确定的代码工作区、模块或仓库映射；具体规则见[公开 API](references/public-api.md)。指纹或内容冲突时先辨明是否同一登记来源，再判断当前代码与卡片依据的版本差异，不能把另一副本直接当成绑定库当前源码。

需要补查登记来源时使用 `knowledge_source_list`。比较历史版本时，才按同一 `source_id` 和卡片已有的 `hash/commit/snapshot_id` 调用 `knowledge_source_resolve`，将历史材料与当前材料分别标明；历史缺失保留诊断。CLI 对应 `source list/resolve`。

需要解析 PDF/Office/图片时用 `knowledge_source_extract`，CLI 对应 `source extract --input FILE.json --json`。实际打开相关图片并结合 OCR 和结构判断。任何来源回执带 `read_id` 时，包括 `resolve` 返回的阅读材料，仍需阅读则用本次 ID 调用 `knowledge_source_renew`，读完调用 `knowledge_source_release`；CLI 分别为 `knowledge source renew --input FILE.json --json` 和 `knowledge source release --input FILE.json --json`。仅在回源返回 `PARSER_DEPENDENCIES_REQUIRED`、默认模型的 `PARSER_MODELS_REQUIRED` 或 `LIBREOFFICE_MISSING` 时，分别用 `hs-knowledge-setup` 的 `documents`、`ocr` 或 `libreoffice` 能力补齐同一执行端，复查后沿用原来源和参数继续回源。外部图片链接、自定义模型或 LibreOffice 命令配置缺口，以及未解析范围按回执说明。

指定 PDF 物理页范围可取得 `role: page_preview`，逐页生成到像素和字节预算。按实际回执查看图片，需要时缩小范围补读。

调整关键词后仍找不到相关卡时，核对显式筛选、退役状态、截断和诊断，说明库内依据缺口。旧 draft 可按 ID 阅读，不自动升为正式可搜状态。运行失败不能当作有效空结果。

使用本次返回值。CLI 返回 `report_ref` 时，报告保存在 `artifacts/query/`，显式指定报告输出也使用该目录。查询材料与入库 `.build` 独立。

用户明确要求把本轮技术结论沉淀到组库时，使用 `hs-knowledge-capture`，交接本轮已核实的结论、适用条件和依据。

[公开 API](references/public-api.md)说明查询字段、旧参数错误及来源路径。
