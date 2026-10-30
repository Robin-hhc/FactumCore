---
name: hs-knowledge-query
description: 按问题用途和适用范围检索正式知识，使用搜索回执精读同代 Claim，并在需要时沿来源核对答案。
---

# 检索、精读与回源

## 目标与输入

根据用户问题取得合格知识与可追溯依据。输入是问题、已知用途和真实适用范围；交付答案、卡／Claim 引用以及尚未解决的缺口。

K 是已确认的实际知识根，在数据所在执行端调用仓内 CLI；入口不明时先用 `hs-knowledge-explore` 定位。

## 执行

1. 选择 `purpose`：机制／设计背景用 `guidance`，当前适用结论用 `current`，当前实现事实用 `implementation`，旧版本用 `historical`。按问题与已核材料填写 `context`，不为凑命中猜条件或照抄卡的适用范围。
2. 用明确关键词搜索。下面以背景问题为例，其他用途按第 1 步选择：

   ```text
   python K/knowledge.py search "问题关键词" --purpose guidance --json
   ```

3. 选择与问题相关的命中，用原搜索的 `receipt_ref` 和命中的 `card_id` 精读：

   ```text
   python K/knowledge.py read CARD_ID --receipt SEARCH_RECEIPT --json
   ```

   用实际命中的 ID 和返回的搜索回执替换占位符。`read` 沿用原搜索的用途、范围和代次，只读取该次合格 Claim；不能因直接打开卡文件而扩大引用范围。需要复杂范围时用 `--input` 提供 `query`、`purpose`、`context`，详见[搜索与精读 API](references/public-api.md)。
4. 问题需要原文、代码行为，或相关卡缺少答题要点时，再沿 `source_links` 查相应章节。按声明的路径基准核对材料，区分旧证据和当前入口；新增原文发现另注明，不当作卡中已有结论。代码实现结论须核实际源码及条件。CodeGraph 可辅助定位，普通查询不初始化图谱。

## 空结果与缺口

空 `matches` 时，先检查本次用途、已知范围、`gaps` 和截断／错误诊断，再有依据地调整关键词。`gaps: []` 不证明全库没有相关资料；必要范围不明时说明缺口或询问用户，不反复猜芯片、特性组合。

缺索引、规则不兼容、来源超时等运行问题保持真实失败，不能解释成有效空命中。查询不自动触发入库、全库检查或重建索引。

## 交付

用精读取得的合格正文回答，附卡／Claim、原回执和必要来源链接；区分已阅读材料与仅返回的链接。背景或历史知识按原用途说明，不能充当当前实现证明。未覆盖的问题明确列出已查范围与缺口。

- 请求、用途与同代精读规则：[公开 API](references/public-api.md#搜索请求)。
- 来源路径与当前代码入口：[来源地址](references/public-api.md#来源地址与代码入口)。
- 展示格式：[结果写作指南](references/results/writing-guide.md)。
