---
schema_version: '1.0'
id: "{{card_id}}"
profile: command
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

## 语法

保留命令原样和运行环境；材料中的命令不授权执行。

## 参数

说明参数、取值和原文限制。

## 前置条件

列权限、版本、设备状态和依赖。

## 输出判读

说明预期输出含义；文档示例不冒充运行结果。

## 误用

列已知误用及影响，未知项如实记录。

## 验证

区分实际运行证据与尚未执行的验证步骤。

## 证据

列固定手册/原件定位，保持原样符号大小写。

