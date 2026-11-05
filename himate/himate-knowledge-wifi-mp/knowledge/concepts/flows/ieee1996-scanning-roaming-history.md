---
id: ieee1996-scanning-roaming-history
profile: flow
title: 1996草案教程中的扫描、关联与重关联（历史背景）
summary: 只记录历史教程对被动/主动扫描和关联流程的解释，不作为现行标准或产品实现结论。
aliases: [scanning, roaming, Probe, Reassociation]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-0dadfda943d36584c962
    page_start: 1
    page_end: 1
    evidence_ref: identity
  - doc_id: doc-0dadfda943d36584c962
    page_start: 17
    page_end: 22
    evidence_ref: tutorial-flow
code_ref: []
claims:
  - id: historical-flow
    text_ref: '#historical-flow'
    evidence_kind: design
    usage: historical
    source_refs: [identity, tutorial-flow]
    context_ids: []
    verification_requirements: []
---
# 1996草案教程中的扫描、关联与重关联（历史背景）

<a id="historical-flow"></a>
这份1996年IEEE P802.11-96/49C教程包含未批准草案内容，以下仅供理解历史术语，不用于判定当前设备或现代标准符合性。

## 起终点与步骤

- 被动扫描：监听Beacon发现网络；主动扫描：在信道上发送Probe并等待Probe Response。
- 教程的初始关联示例：扫描取得响应、选择AP、发送Association Request，AP返回Association Response。
- 重关联：站点可扫描或利用以往扫描信息选择新AP，发送Reassociation Request；成功响应后完成迁移，否则继续扫描。教程另描述新AP通知分布系统更新相关信息。

## 范围与缺口

这里只提炼文本中直接可读的历史步骤，未解析图像细节，未建立到本项目代码的实现关系。WEP等历史章节不作为现行安全建议；当前MAC、QoS、安全要求需另查适用正式版本。

## 证据

[原PDF](../../../docs-raw/protocols/ieee80211/ieee-p80211-1996-d3-mac-tutorial.pdf)：第1个PDF页标明草案身份；第17—22个PDF页含幻灯片33—44的漫游、扫描和管理帧说明。定位采用PDF物理页号。
