---
name: hs-knowledge-record
description: 根据本次候选视图转写已定处置，生成待发布的来源处理记录；用于入库和巡检的P5记录节点。
---

# 转写处理记录

## 目标与输入

把作者已经确定的来源／维护处置转成待发布记录。正常输入为本次 `operation_id` 和 `view_ref`；CLI 从该视图读取实际计划、扫描和处置预览。

K 是实际执行端的知识根。已有上下文直接复用；入口不明时用 `hs-knowledge-explore` 定位，远端数据在远端原生 K 执行。

## 执行

```text
python K/knowledge.py record --input REQUEST.json --json
```

正常请求只传本次 `operation_id/view_ref`。读取返回的真实引用，不重新抄写整套摘要或处置列表，不用请求覆盖作者既定判断。需要可选字段时读[正常 P5](references/request.md#正常-p5)，明确独立登记时才读[独立记录](references/request.md#独立记录)。

## 完成与失败

- `recorded`：把实际 `ingest_record_ref` 和本次 `view_ref` 交 P6。它仍是暂存记录，尚未正式发布。
- 调用失败：保留诊断。引用或转写输入有误时核对本次请求；作者判断或稿件需要改变时，暂停当前记录，交明确修订任务或由宿主重排；P5 不自行跳转上游阶段或改已审内容。

本步不扫描来源、不决定新建／跳过、不审阅内容、不发布卡片或重建索引。`defer/failed/uncovered` 如实保留欠账；可选检查材料只记录实际发生的事实，不以通过票据代替真实输入绑定。
