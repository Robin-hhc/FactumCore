---
name: hs-knowledge-apply
description: 将通过P4的本轮候选复制入正式库，刷新双向关系与检索索引并登记本批范围或文件完成事实；用于P5。
---

# 入库并更新索引

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 入库

确认本轮已经完成 P4，运行：

```sh
knowledge ingest commit --json
```

命令先机械核对 PDF 本轮页段和 P1 同版材料，再依次复制覆盖候选、应用明确删除清单、更新数据库关系和检索索引，成功后登记处理事实，最后清暂存；不重复 P4 内容质量审阅。PDF 仅合并实际 source_pages，宽候选未选页和补读前文不自动计入；覆盖全文才更新整文成功 hash 并移除 processing。非 PDF 沿用整文件完成登记，只推进 P1 选中来源。

失败保留 `.build` 和错误，修正执行问题后直接重试同一个 P5；不要先运行 P1。重复覆盖及数据库更新由命令处理。需要改稿则回 P3，再经 P4。

本批范围无需产卡但已完整评估时，将 `{"reason":"实际不改卡理由"}` 写入 `.build/commit.json`，再运行 `knowledge ingest commit --input .build/commit.json --json`；PDF 计划仍须有 source_pages。经核实无增量的页也可登记，暂缓／失败不推进覆盖或成功 hash。

成功后依据命令回执交付。`phase: completed` 表示本批发布完成；`source_complete: false` 表示该 PDF 仍有剩余页，说明本批范围和待办，下次普通入库继续，不宣称整文完成。需要复核时读 `artifacts/ingest/latest.json`，不以新 scan 验证上一批；主动开始下一批才重新扫描。P1/P5 清理保留 .build 根 README，PDF 派生缓存及正式进度不随本批清理。Git 提交、推送与合入由用户另行授权。
