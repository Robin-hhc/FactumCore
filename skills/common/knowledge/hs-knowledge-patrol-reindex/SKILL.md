---
name: hs-knowledge-patrol-reindex
description: 处理巡检 needs_index 分支，构建并核验派生索引、查询和活动代，不修改知识内容。
---

# L3 修复巡检索引

仅在本轮计划为 `needs_index`、没有内容修订待办时使用。

复用已知知识根和执行端；缺位置时读当前工作区 `AGENTS.md`、`config.yml`，必要时询问用户。首次读知识根 `AGENTS.md`；以下在该目录执行，POSIX 用 `sh ./knowledge.sh`。

```powershell
.\knowledge.cmd patrol reindex --input REQUEST.json --json
```

请求提供原 `plan_ref`，可选 `plan_digest`、实际 `index_inputs` 和 `cases`。脚本构建并完整校验索引，执行适用查询、同代读取和激活；读取本次实际结果及引用。

`indexed` 后将原计划和实际索引结果交 L4 完成核验。存在性查询仅说明机械检索可用；索引完成不表示内容修订或成功基线已完成。

输入漂移、缺输入或运行失败时保留原计划与诊断，不自行补报通过。内容问题交入库处理，不能以重建索引代替改卡。本步只维护派生索引，不改来源或知识正文。
