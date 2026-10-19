---
schema_version: '1.0'
id: "{{card_id}}"
profile: flow
title: "{{title}}"
summary: "{{summary}}"
lifecycle: draft
review_mode: manual_document
owner: "{{owner}}"
scope:
  applicability: unknown
  contexts: []
aliases: []
sources:
- "{{snapshot_id}}"
claims:
- id: "{{claim_id}}"
  text_ref: "#{{claim_id}}"
  evidence_kind: design
  source_ids:
  - "{{source_id}}"
  context_ids: []
  usage: guidance
  verification_requirements: []
relations: []
---
# {{title}}

<a id="{{claim_id}}"></a>
{{claim_text}}

## 起终点

明确触发条件、起点和结束状态。

## 步骤

逐步骤记录条件和相应断言；缺侧证据保留片段范围。

## 调用与消息

记录实际调用或消息名称及方向；未知时明确未知。

## 异常

描述已知异常分支和缺口。

## 条件

写明芯片、侧别、构建、宏和版本；不默认跨芯片成立。

## 证据

逐步骤列原件定位；设计消息不冒充实现或运行证明。
