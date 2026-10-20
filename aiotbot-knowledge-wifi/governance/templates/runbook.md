---
schema_version: '1.0'
id: "{{card_id}}"
profile: runbook
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

## 现象

记录可观察现象及上下文。

## 信号

列区分不同分支的日志/状态/现象。

## 分支

按条件列排查分支，不以经验猜测替代确定根因。

## 步骤

逐项记录动作、预期观察及退出条件。

## 根因状态

明确已确认、候选原因和未知项。

## 解法

分别描述适用解法与限制。

## 验证

列真实修复结果或待执行验证，保持两者区别。

## 证据

列复盘原件、附件和当时环境的固定定位。
