# 维护候选格式

`.build/plan.md` 以 YAML frontmatter 开始，`cards` 只列本批实际需要修改的已有卡 ID 和原正式路径。未改卡不列，零改卡写 `cards: []`。本任务没有文档全文阅读覆盖，不填 `source_units` 或 `source_pages`。

```markdown
---
cards:
  - id: scan-timing
    path: knowledge/rules/scan-timing.md
---

逐卡说明原结论是否仍成立、实际核对的代码版本与位置、需要修订的部分及保留内容。
```

候选位置是将原路径的 `knowledge/` 前缀替换成 `.build/cards/`。例如上述卡写入 `.build/cards/rules/scan-timing.md`。保留原卡的有效正文和卡头，写完整最终卡，不写补丁文本，不在卡头新增 `path`。无候选时保持候选目录为空。不要创建删除清单。

维护 `code_ref` 时使用已经登记的 `code_id` 和实际核实的 `line_start/line_end`，符号引用还须与完整符号范围对应。同名符号按实际模块、版本和上下文区分。引用位置是证据入口，不能单凭位置合法就判断结论正确。evidence_version 由检查/发布程序生成，不自行计算或把旧版本复制给新依据；未改引用已有版本继续保留。必要时通过 `knowledge source resolve` 核对真实历史版本，无法恢复的内容保留具体缺口。

保留仍有效的 `doc_ref`、快照定位、锚点和入链。来源删除不自动使历史依据无效，也不自动授权删除引用或退役整卡。必要标签须为非空且唯一的字符串，数字或布尔形式需加引号。

计划正文应覆盖任务中的每张关联卡，说明修改或不修改的依据；独立新主题单列实际位置，仅供汇总。零改卡也须交 L5 独立复核，不能直接登记成功。
