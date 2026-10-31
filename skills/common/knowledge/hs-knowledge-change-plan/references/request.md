# 六决策与短计划

| 决策 | 采用条件 |
|---|---|
| create | 有独立知识主题，查重后没有合适旧卡 |
| update | 原主题职责不变，融合新增或修正结论 |
| merge | 同主题多卡重复，明确主卡和旧卡替代入口 |
| split | 一卡混装独立主题，明确旧结论去向 |
| deprecate | 整卡职责已失效，保留原因和替代入口 |
| defer | 必要依据不足，说明需要补什么 |

`.build/plan.md` 必须以 YAML frontmatter 开始，`cards` 列出本轮完整候选的唯一 `id` 和正式 `path`；路径相对知识根，使用 `knowledge/...md`。更新沿用原路径，新卡按 `knowledge/index.md` 类型导航选目录。未改卡和仅删除的旧文件不列入 `cards`；无完整候选时仍写 `cards: []`。

```markdown
---
cards:
  - id: radio-flow
    path: knowledge/concepts/flows/radio-flow.md
---
# 本轮计划

- create radio-flow：沉淀本次文档的收发流程，保留其适用条件和来源；查重后无合适旧卡。
```

frontmatter 后逐卡写“动作、改哪些结论、条件和依据、保留什么”。同一文件可产生多个动作。完整阅读后无增量写简短理由即可，不逐条重复未变结论。计划中的 ID/路径与候选必须一一对应，由 P4 的 `ingest check` 核对。

文档变更不自动覆盖冲突来源；先判断条件、版本或用途差异。旧原文按需取，设计要求不能仅因链接到代码就变成实现事实。
