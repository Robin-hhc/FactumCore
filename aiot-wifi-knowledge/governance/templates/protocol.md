---
schema_version: '1.0'
id: "{{card_id}}"
profile: protocol
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

## 机制

说明协议机制及其适用范围。

## 字段与状态

列字段、状态及原文单位/枚举。

## 约束

保留条件、例外和约束之间的关系。

## 标准版本

列可靠的标准版本；未知就写 unknown。

## 产品支持边界

区分标准条款与产品实际支持，不从条款推导已实现。

## 证据

绑定确切条款、页/章节和固定快照。

