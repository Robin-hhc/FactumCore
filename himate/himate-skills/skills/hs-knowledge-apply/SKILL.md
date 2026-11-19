---
name: hs-knowledge-apply
description: 将通过P4的本轮候选复制入正式库，刷新双向关系与检索索引并登记本批范围或文件完成事实；用于P5。
---

# 入库并更新索引

复用 Workflow 已确认的知识根、执行端和工具命令前缀。独立使用时从宿主或部署配置确认该执行端的工具入口，读取知识根的 `AGENTS.md` 和 `config.yml`，以知识根为工作目录，用该入口运行 `doctor --knowledge-root <知识根绝对路径> --json` 核对目标和工具版本。后续示例中的 `knowledge` 代表该已确认的入口，每次调用都传入同一 `--knowledge-root`，工作目录为知识根。

## 入库

确认本轮已经完成 P4，运行：

```sh
knowledge ingest commit --json
```

命令先校验计划范围和 P1 同版材料，再写正式候选、应用删除清单并更新索引。PDF、DOCX、XLSX 仅合并本批实际审阅范围，覆盖全文才更新成功 hash 并移除 `processing`。

失败时保留 `.build`、已审稿和错误，修正执行问题后直接重试同一个 P5，重复覆盖及数据库更新由命令处理。只有确认本批尚未写入正式库、确实需要修改候选时才交 `needs_revision`，带具体问题回 P3 再经 P4。已写入或无法确认写入状态时，先用同一已审稿完成或报告本批失败，保留可重试现场。

本批无需产卡时，计划保留实际阅读范围，并将 `{"reason":"实际不改卡理由"}` 写入 `.build/commit.json`，运行 `knowledge ingest commit --input .build/commit.json --json`。已审且无增量的范围也可登记。

成功后交接来源、实际范围、卡片变动和剩余范围。`completed` 指本批发布完成，`source_complete: true` 才表示整份来源入库完成。

按所属 Workflow 继续：独立 ingest 成功后回 P1，按任务原始范围扫描下一批，直到该范围返回 `unchanged` 才正常结束；未限定来源时不把上一批 `source_id` 变为后续范围。巡检成功后回 L2，由 L2 选择下一来源再交 P1，采用其最新 `source_id`。两者沿用已交接的 CLI 命令前缀、`parser` 和页段预算配置；`reprocess: true` 仅首次重评使用，后续普通续办。

本批以 commit 命令返回的结果为准。若返回 `data.receipt_warning`，`artifacts/ingest/latest.json` 可能仍是上一批的回执。下一次 scan 用于选择下一批。P1/P5 清理保留 .build 根 README，PDF 派生缓存及正式进度不随本批清理。暂缓／失败报告实际阻塞和未完成范围，不通过回 P1 反复重扫解决。Git 提交、推送与合入由用户另行授权。
