---
name: hs-knowledge-patrol-complete
description: 用原巡检计划及真实发布结果核验完成情况，按实际 CAS 结果报告成功基线或剩余欠账。
---

# L4 核验巡检完成

复用已知知识根和执行端；缺位置时读当前工作区 `AGENTS.md`、`config.yml`，必要时询问用户。首次读知识根 `AGENTS.md`；以下在该目录执行，POSIX 用 `sh ./knowledge.sh`。

```powershell
.\knowledge.cmd patrol complete --input REQUEST.json --json
```

请求提供原 `plan_ref`；处理过入库时另给实际 `batch_operation_id`、`publication_ref` 或 `completion_ref`。脚本核原扫描覆盖、真实发布闭包、当前输入、限制、索引及清理，不采信请求自报的 passed。

- `completed`：核验成功且 CAS 已保存本轮成功基线，报告实际范围和引用。
- `pending`：结束本轮，交付原因与报告；欠账、漂移、P6／清理未完或并发基线变化均不能当作完成。

只按实际结果报告，不手改水位或再执行内容修订。续办交明确修复任务处理，不假定 Workflow 自动跳到 apply；已发布内容只续办原批次，不重新发布。原巡检观察 `logs/patrol/` 和本机状态 `.build/runtime/patrol-state.json` 不交给生产者清理，也不提交 Git。
