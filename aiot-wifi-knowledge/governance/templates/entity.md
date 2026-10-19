---
schema_version: '1.0'
id: "{{card_id}}"
profile: entity
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

## 职责

写明对象负责什么、对外提供什么能力。

## 边界

写明对象不承担的职责及未知条件。

## 接口

记录实际接口和输入输出；文档声明与实现证据分开。

## 依赖

记录必要依赖和条件，不因同名推断等价。

## 证据

绑定固定原件快照与章节/行定位，保留资料批准状态。

