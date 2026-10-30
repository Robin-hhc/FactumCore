---
name: hs-knowledge-change-plan
description: 阅读新旧材料，确定逐Claim结论、来源处置、卡片动作及查询预期；用于入库和巡检的P2内容规划。
---

# 制定内容计划

## 目标与输入

根据本次 `material_ref` 和适用的 `scan_ref`，决定知识应如何新增、修改、保留或暂缓。脚本保存作者判断，不代替阅读与推理。

K 是实际执行端的知识根；已有上下文直接复用，入口不明时用 `hs-knowledge-explore` 定位。只读取本次明确引用的材料。

## 作者判断

1. 阅读实际新原文、采用的旧版本、完整旧卡及必要代码／配置，区分事实变化、条件变化和材料缺口。
2. 对每个来源和维护单元给出 `content/skip/defer/failed/uncovered` 及理由。缺材料先返回 source 补料；已有材料不足以支持结论时保留欠账。
3. 逐 Claim 说明修改前后、条件、依据与保留范围；为相关卡选择新建、更新、合并、拆分、退役或暂缓，保留身份及旧 Claim 去向。
4. 固定代表性查询和明确预期，覆盖本批实际卡片；按目标 Claim 的用途及证据选择 `purpose`，不为获得通过弱化查询。

编写请求前读[计划字段](references/request.md#计划字段)；内容批再读[查询用途与预期](references/request.md#查询用途与预期)。汇总核对完整批次后再提交；`plan` 成功即冻结材料绑定和计划，同一操作不能追加或覆盖。

## 保存与交接

```text
python K/knowledge.py change-plan --input REQUEST.json --json
```

`content_planned` 时将真实 `semantic_plan_ref` 交 P3。计划记录作者决定，不代表已独立审阅或发布。失败时保留诊断；材料变了不能给旧计划换一个材料引用继续。

已有候选的内容重判使用新操作、真实 `previous_view_ref` 和 `revision_reason`，详见[返工](references/request.md#返工)。旧材料、计划和视图保持原字节。

本步不生产完整卡稿、不执行独立审阅或正式发布；P3 按计划成稿，P4 审实际内容。
