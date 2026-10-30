---
name: hs-knowledge-patrol-plan
description: 固定本轮 raw、登记代码及知识库的实际变化，生成材料待办和对应处理分支。
---

# L2 生成巡检待办

在数据所在 K 用新 `operation_id` 启动 CLI，重新加载同步后的实际实现、配置和规则：

```text
python K/knowledge.py patrol plan --input REQUEST.json --json
```

读取本次 `plan_ref/plan_digest`、`scan_ref`、`source_request`、统计及报告。脚本比较 raw、直接登记代码与成功基线；保留实际用途、材料缺口和历史降级说明，不另行猜测影响范围。

| 实际 phase | 交接 |
|---|---|
| `needs_ingest` | 完整 `source_request` 交 P1 的 `source prepare`，再走 P2—P6 |
| `needs_index` | 原 `plan_ref` 交 L3 巡检索引修复 |
| `unchanged` | 原 `plan_ref` 交 L4 完成核验，尚未推进成功基线 |
| `blocked` | 结束本轮并报告原因及确切续办请求；续办交明确修复任务 |

`source_request` 保留新增／未完成 raw、待修卡来源和代码目标的并集，包括明确空 `unit_ids`。不改跑 `source run`、丢弃选择字段或伪造 raw 单元。输入漂移保留原固定计划；已发布内容不能另起操作重复发布。

已变且可读代码中的部分解析问题可作为待审事项交 ingest；引用仍保留 `unavailable` 和实际原因，不代表已修复。其它基础故障按实际 `blocked` 处理。
