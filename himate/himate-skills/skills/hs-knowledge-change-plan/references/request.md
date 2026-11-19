# 六决策与短计划

| 决策 | 采用条件 |
|---|---|
| create | 查重后确认是独立知识主题，分配唯一 ID，卡状态写 `stable` |
| update | 融合或修正同主题结论，沿用 ID、正式路径和原生命周期 |
| merge | 保留主卡 ID，迁入有效知识和来源；不用的旧卡写退役原因和替代链接，或明确移除并修复入链 |
| split | 说明各主题、结论及来源分别去哪里；延续旧职责的卡可沿用原 ID，否则退役旧卡并指向替代卡 |
| deprecate | 仅整卡职责失效时改为 `deprecated`，保留原因、历史适用范围和可用的替代入口 |
| defer | 缺少必要依据，报告待补材料并保留待办，不推进本批的完成记录 |

`stable` 表示卡未退役，缺省也按未退役处理；状态不表示运行或测量已经验证。局部结论过时只改正文，来源删除、旧设计参考或历史说明不自动导致整卡退役。修复退役卡的文字、定位或链接时保留退役状态。恢复退役卡，或让旧 `draft` 进入新候选，须在 P2 明确决定新状态，避免普通更新或迁移时意外启用。

`.build/plan.md` 必须以 YAML frontmatter 开始，`cards` 列出本轮完整候选的唯一 `id` 和正式 `path`；路径相对知识根，使用 `knowledge/...md`。更新沿用原路径，新卡按 `knowledge/index.md` 类型导航选目录。未改卡和仅删除的旧文件不列入 `cards`；无完整候选时仍写 `cards: []`。

有 `task.document_review` 时填实际 `source_units: [[start, end]]`。`start` 等于 `start_unit`，`end` 不超过 `end_unit`。沿用旧版 CLI 的 PDF 批次继续使用 `source_pages` 和 `pdf_review`。切换 CLI 版本时，从 P1 重新准备未提交的任务。选定的连续范围须全部评估，包括经核实无增量的目录、空白和参考材料。

```markdown
---
cards:
  - id: radio-flow
    path: knowledge/concepts/flows/radio-flow.md
---
# 本轮计划

- create radio-flow：沉淀本次文档的收发流程，保留其适用条件和来源；查重后无合适旧卡。
```

有 `document_review` 时在 `cards` 同级填实际单元，例如 `source_units: [[1, 8]]`。无卡时同时写 `cards: []` 和实际范围。

frontmatter 后说明本轮评估范围、必要补读及逐卡“动作、改哪些结论、条件和依据、保留什么”。同一文件可产生多个动作。本批范围完整评估后无增量写简短理由即可，不逐条重复未变结论。计划 ID/路径与候选须一一对应，P4/P5 还机械核对 PDF 版本及候选边界。卡片 doc_ref 可引用补读前文、跨章或其它来源，不据此增加已评估页。

文档变更有冲突时先核对条件、版本和依据差异。设计要求的链接可用于回查代码，实现结论仍须有实际证据。旧版影响决定时，准备如 `{"source_id":"doc-example","hash":"实际旧版SHA-256"}` 的 JSON，运行 `knowledge source resolve --input FILE.json --json`（带同一知识根）。按返回的旧版和回源路径核对；缺少旧版且影响决定时暂缓。

普通更新计划应指明旧 `scope`、`claims` 中仍有效的适用条件、结论、历史和验证限制各迁入哪个正文段落。保留真实的卡 ID、旧锚点、入链、历史定位及有效依赖或替代关系；将后两类关系写成正文链接。旧别名和搜索词保留在自然正文或适当标签里。新稿标题用正文 H1，卡头只安排 `id`、`doc_ref`、`code_ref`、可选的 `tags` 和 `lifecycle`，具体稿件格式由 P3 处理。
