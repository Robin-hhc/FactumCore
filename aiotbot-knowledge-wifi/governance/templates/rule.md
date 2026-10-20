---
schema_version: '1.0'
id: "{{card_id}}"
profile: rule
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

## 规则对象

明确受规则约束的对象和范围。

## 约束

逐项写约束，区分强制规则与建议。

## 例外

记录原文明确的例外及条件。

## 批准身份

记录已知批准/草稿身份，未知不编造批准人。

## 检查办法

列建议核查办法；未执行不写验证通过。

## 证据

列规则原件、版本及条款定位。
