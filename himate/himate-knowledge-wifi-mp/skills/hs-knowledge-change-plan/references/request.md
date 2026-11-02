# 六决策与短计划

| 决策 | 采用条件 |
|---|---|
| create | 有独立知识主题，查重后没有合适旧卡 |
| update | 原主题职责不变，融合新增或修正结论；保留原生命周期，改变状态须明确决定 |
| merge | 同主题多卡重复，明确主卡和旧卡替代入口 |
| split | 一卡混装独立主题，明确旧结论去向 |
| deprecate | 整卡职责已失效，保留原因和替代入口；局部历史或设计参考不自动整卡退役 |
| defer | 必要依据不足，说明需要补什么 |

`.build/plan.md` 必须以 YAML frontmatter 开始，`cards` 列出本轮完整候选的唯一 `id` 和正式 `path`；路径相对知识根，使用 `knowledge/...md`。更新沿用原路径，新卡按 `knowledge/index.md` 类型导航选目录。未改卡和仅删除的旧文件不列入 `cards`；无完整候选时仍写 `cards: []`。

存在的 raw PDF 必填实际 `source_pages: [[start, end]]`，每轮一个连续的原件物理页闭区间。start 等于 `task.pdf_review.start_page`，end 不超过候选上限 `task.pdf_review.end_page`。P2 按上下文、图表、条款和产卡量自由缩短结束位置；候选字量不是必读量，80k token 只是软目标。不能跳过起点，选定范围须全部评估，包括经核实无增量的目录、空白或参考页；不要用产卡证据页段替代。非 PDF 和已删除来源不要求该字段。

```markdown
---
cards:
  - id: radio-flow
    path: knowledge/concepts/flows/radio-flow.md
---
# 本轮计划

- create radio-flow：沉淀本次文档的收发流程，保留其适用条件和来源；查重后无合适旧卡。
```

PDF 示例可在上述 frontmatter 的 cards 同级添加 `source_pages: [[1, 8]]`，实际页码须符合本轮 task；不要原样套用。小 PDF 也须声明实际物理页段，无卡时同时写 `cards: []` 和实际范围。

frontmatter 后说明本轮评估范围、必要补读及逐卡“动作、改哪些结论、条件和依据、保留什么”。同一文件可产生多个动作。本批范围完整评估后无增量写简短理由即可，不逐条重复未变结论。计划 ID/路径与候选须一一对应，P4/P5 还机械核对 PDF 版本及候选边界。卡片 doc_ref 可引用补读前文、跨章或其它来源，不据此增加已评估页。

文档变更不自动覆盖冲突来源；先判断条件、版本和依据差异。旧原文按需取，设计要求不能仅因链接到代码就变成实现事实。字段和旧卡正文迁移规则以知识根 `governance/specs/cards.md` 为准，状态规则见同目录 `lifecycle.md`。
