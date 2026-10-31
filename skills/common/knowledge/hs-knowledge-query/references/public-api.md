# 搜索、精读与来源

## 搜索请求

`knowledge search "关键词" --top-k 5 --json` 与 `knowledge query --input FILE.json --json` 使用同一整卡候选搜索能力。

| 请求字段 | 规则 |
|---|---|
| `query` | 必填关键词；沿用确定性分词，同一卡须命中全部查询词组，可分布于不同段落 |
| `tags` | 可选字符串数组；多个标签按完整字符串精确 AND 匹配，保留大小写规则；缺省不按标签过滤 |
| `top_k` | 可选整数，1—100，默认 10；CLI 可用 `--top-k` |
| `include_deprecated` | 可选布尔值，默认 false；CLI 可用 `--include-deprecated` 额外包含显式整卡退役卡 |

标签通过 `--input` 提供，不猜宏、芯片或版本。只检索正式 `knowledge/`，不读 `.build/`；旧 draft 不自动升为 stable，也不进入默认搜索。没有用途或 context 资格门，缺适用条件不让相关卡消失。

标题、标签、正文权重分别为 8、5、1；同一 `(token, card_id, field)` 只计一次，平分按 card_id 稳定排序。分数仅表示词项相关性。`matches` 包含 `card_id/path/title/tags/lifecycle/score`，另有 `truncated` 和本次独立 `report_ref`，不返回 Claim 资格集合。

显式传入旧 `--purpose`，或 JSON 中含 `purpose/context`，在搜索或读卡执行前返回 `QUERY_PARAMETERS_REMOVED`、退出码 2，不生成正常命中报告。删除旧字段，改用关键词、可选标签，再通过正文与来源判断适用性；不把旧参数静默忽略。

## 精读

`knowledge read CARD_ID --json` 不要求前序搜索回执，直接读取完整正式卡，允许读取 deprecated 和只读旧 draft。结果保留作者实际声明的原始 metadata、完整 body、规范化 doc_ref/code_ref 及来源入口；系统派生的路径、标题和有效生命周期与原声明区分，不补造 Claim、用途或范围。旧卡的显式条件、历史依据和验证要求继续可见。

命中卡、stable 状态或含 code_ref 都不证明问题已有适用答案。精读正文，分别核对设计要求、代码观察及测量依据，未知条件如实说明；必要时回源检查实际代码和版本。

搜索报告位于 `artifacts/query/`；使用本次返回值，不读取其他查询的报告。显式 `--output` 在知识根内也只能写 `artifacts/query/`，不能覆盖入库暂存或数据库。

当前来源直接按 `read` 返回的 `sources[].path` 读取：普通文档相对知识根，外部目录来源沿用本机已有映射；代码未指定仓库时相对项目配置所在目录，指定仓库时按实际配置映射。读取当前文本不需要 Git，也不调用历史恢复。

只有需要已处理的旧版本时才用 `knowledge source resolve --input FILE.json --json`；JSON 至少包含实际的 `source_id`，例如 `{"source_id":"doc-example"}`，不能把 ID 当位置参数。历史缺失时保留诊断，不能把当前文本冒充旧版。当前代码位置与历史证据分清；章节、PDF 页和文本行号不混用。

空命中先核关键词、显式标签、退役状态、截断和诊断。运行错误保持错误，不能当零命中。需重新入库或索引维护时使用相应入口。
