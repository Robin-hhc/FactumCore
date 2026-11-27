# 搜索、精读与来源

## 搜索请求

`knowledge search "关键词" --top-k 5 --json` 与 `knowledge query --input FILE.json --json` 使用同一整卡候选搜索能力。

| 请求字段 | 规则 |
|---|---|
| `query` | 必填关键词；NFKC 归一化后确定性分词并忽略大小写，多余分隔空白不影响结果；同一卡须命中全部查询词组，可分布于不同段落 |
| `tags` | 可选字符串数组；标签比较双方均经 NFKC、首尾去空白和 casefold 后按完整字符串 AND 匹配，保留原始展示值；缺省不按标签过滤 |
| `top_k` | 可选整数，1—100，默认 10；CLI 可用 `--top-k` |
| `include_deprecated` | 可选布尔值，默认 false；CLI 可用 `--include-deprecated` 额外包含显式整卡退役卡 |

标签通过 `--input` 提供，不猜宏、芯片或版本。只检索正式 `knowledge/`，不读 `.build/`；旧 draft 不自动升为 stable，也不进入默认搜索。没有用途或 context 资格门，缺适用条件不让相关卡消失。

标题、标签、正文权重分别为 8、5、1；同一归一化词项在同一卡的同一字段只计一次，平分按 card_id 稳定排序。仅改变查询大小写不改变分数、排序和截断结果。标签内部空格和标点仍参与完整值比较，例如 `80211` 不匹配标签 `80211BE`；`80211be` 与 `802.11be` 不自动等价。分数仅表示词项相关性。`matches` 包含 `card_id/path/title/tags/lifecycle/score`，另有 `truncated` 和本次独立 `report_ref`，不返回 Claim 资格集合。

显式传入旧 `--purpose`，或 JSON 中含 `purpose/context`，在搜索或读卡执行前返回 `QUERY_PARAMETERS_REMOVED`、退出码 2，不生成正常命中报告。删除旧字段，改用关键词、可选标签，再通过正文与来源判断适用性；不把旧参数静默忽略。

## 精读

`knowledge read CARD_ID --json` 不要求前序搜索回执，直接读取完整正式卡，允许读取 deprecated 和只读旧 draft。结果保留作者实际声明的原始 metadata、完整 body、规范化 doc_ref/code_ref 及来源入口；系统派生的路径、标题和有效生命周期与原声明区分，不补造 Claim、用途或范围。旧卡的显式条件、历史依据和验证要求继续可见。

命中卡、stable 状态或含 code_ref 都不证明问题已有适用答案。精读正文，分别核对设计要求、代码观察及测量依据，未知条件如实说明；必要时回源检查实际代码和版本。

搜索报告位于 `artifacts/query/`；使用本次返回值，不读取其他查询的报告。显式 `--output` 在知识根内也只能写 `artifacts/query/`，不能覆盖入库暂存或数据库。

`read` 返回的 `sources[].path` 是登记路径，其基准来自同一绑定知识库：普通文档相对知识根，外部目录来源沿用已配置映射；代码未指定仓库时相对配置确定的代码工作区基准（默认布局的 manifest 根），指定仓库时相对对应的已配置仓库。会话 cwd 不自动等于该基准，同名文件也不证明来源相同。直接打开原文件前先根据绑定知识根的 `config.yml` 确认代码根、模块及仓库映射；路径基准未知时先确认，不能按 cwd 猜测。

需要回查当前登记代码时，使用 `knowledge_source_resolve`，请求仅传该代码的实际 `source_id`（来自 `code_ref.code_id` 或对应 `sources` 项），例如 `{"source_id":"code-example"}`。CLI 对应 `knowledge source resolve --input FILE.json --json`。无版本参数时读取当前登记位置的内容，不需要 Git；返回 `hash` 为本次原字节指纹，`original_ref` 和可用的 `text_ref` 相对同一知识根，沿用同一执行端读取。本次材料不能再按其他工作区的 artifacts 目录定位。原件同样可按文档来源 ID 解析，章节、PDF 页和行号按实际卡片定位核对。

只有明确比较历史时才传已有的 `hash`、`commit` 或 `snapshot_id`，分别保留当前与历史的身份和指纹。历史缺失或当前解析受阻时保留诊断，不拿 cwd 下的同名文件补作已确认版本。卡片指纹与某个本地文件不同，应先确认它们是否属于同一登记来源，再判断版本变化；只解释卡片已有内容而无需回源时不要求额外解析代码。

## 文档与图片回源

当前已登记文档可用 `knowledge source extract --input FILE.json --json`。请求示例为 `{"source_id":"doc-example","page_start":10,"page_end":15}`，页范围在实际转换时生效；不需要范围时省略两项。`parser` 可提供明确的本地解析选项，native 不做 OCR，standard 需要预置模型。返回 `read_id`、`expires_at`、原件副本及 `parsed` 阅读稿/JSON/图片入口，目录独立于入库 `.build` 和搜索报告；解析不推进入库成功标记。

PDF 可用 `page_range: [start, end]` 或旧 `page_start` / `page_end` 指定物理页。默认按像素与 PNG 字节配额逐页生成 `role: page_preview`，回执说明未生成范围；`page_preview: false` 仅取提取材料。正式 PDF 引用采用物理页定位。

消费后以 `{"read_id":"本次返回的ID"}` 调用 `knowledge source release --input FILE.json --json`，只释放该阅读目录；仍需继续时用 `source renew`。ready 租约默认 1800 秒，到期入口失效；`source cleanup --json` 只回收过期且没有活跃转换的来源阅读产物。不要猜 ID、不批量删除 artifacts，也不要把临时图像路径写成正式卡唯一依据。图片需通过宿主实际图片工具读取，Markdown 链接本身不证明 Agent 已看图。

空命中先核关键词、显式标签、退役状态、截断和诊断。运行错误保持错误，不能当零命中。需重新入库或索引维护时使用相应入口。
