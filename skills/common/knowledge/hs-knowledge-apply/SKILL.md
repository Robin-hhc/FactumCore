---
name: hs-knowledge-apply
description: 将通过P4的本轮候选复制入正式库，刷新双向关系与检索索引并保存文件处理hash；用于P5。
---

# 入库并更新索引

在实际知识根执行命令，Linux 使用 `sh ./knowledge.sh`，Windows 使用 `.\knowledge.cmd`；已注册入口可直接用 `knowledge`。位置由 Workflow 首节点确认，独立使用时从当前工作区 `AGENTS.md`、`config.yml` 获取。

## 入库

确认本轮已经完成 P4，运行：

```sh
knowledge ingest commit --json
```

命令依次复制覆盖候选、应用明确删除清单、更新数据库关系和检索索引、保存触发文件的成功 hash，最后清暂存。使用 P1 保存的来源版本，不把其它关联文件顺便标成已处理。

失败保留 `.build` 和错误，修正执行问题后直接重试同一个 P5；不要先运行 P1。重复覆盖及数据库更新由命令处理。需要改稿则回 P3，再经 P4。

无需产卡但已完整处理时，将 `{"reason":"实际不改卡理由"}` 写入 `.build/commit.json`，再运行 `knowledge ingest commit --input .build/commit.json --json`。暂缓／失败不能标成完成。

成功后依据命令回执交付；需要复核时读 `artifacts/ingest/latest.json`，不再用 `scan` 验证，它会开启下一轮。Git 提交、推送与合入由用户另行授权。
