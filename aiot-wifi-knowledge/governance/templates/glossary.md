---
schema_version: '1.0'
id: "{{card_id}}"
profile: glossary
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

## 定义

写明术语在当前语境的定义。

## 别名

只列原文支持的别名，保留精确符号大小写。

## 歧义

区分同名多义及不同对象。

## 范围

记录适用领域/芯片/侧别和未知项。

## 证据

绑定定义来源及固定原件定位。

