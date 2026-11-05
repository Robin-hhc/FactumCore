---
id: wifi-wme-tid-ac-mapping-static
profile: rule
title: 两份源码的 WME TID/AC 映射与不可逆边界
summary: TID按组归入AC，AC反向只选择代表TID；默认VO分支不提供输入校验。
aliases: [WLAN_WME_TID_TO_AC, WLAN_WME_AC_TO_TID]
tags: [wifi, wme, static-analysis]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-d8389b4a2a143dce8784
    line_start: 4
    line_end: 28
    evidence_ref: analysis
  - doc_id: doc-d8389b4a2a143dce8784
    line_start: 73
    line_end: 77
    evidence_ref: limits
code_ref:
  - code_id: code-9aeef9167a82ce7ddf1f
    line_start: 186
    line_end: 187
    evidence_ref: host-ac-to-tid
  - code_id: code-9aeef9167a82ce7ddf1f
    line_start: 206
    line_end: 208
    evidence_ref: host-tid-to-ac
  - code_id: code-586b2f16bd894f2bf06a
    line_start: 155
    line_end: 159
    evidence_ref: device-ac-to-tid
  - code_id: code-586b2f16bd894f2bf06a
    line_start: 163
    line_end: 167
    evidence_ref: device-tid-to-ac
claims:
  - id: mapping
    text_ref: '#mapping'
    evidence_kind: implementation
    usage: guidance
    source_refs: [analysis, limits, host-ac-to-tid, host-tid-to-ac, device-ac-to-tid, device-tid-to-ac]
    context_ids: []
    verification_requirements: []
---
# 两份源码的 WME TID/AC 映射与不可逆边界

<a id="mapping"></a>
## 规则对象

本次复制源码中两份 `WLAN_WME_TID_TO_AC` 和 `WLAN_WME_AC_TO_TID` 宏；具体文件与行段见卡头引用。这里只描述静态实现，构建与产品适用条件未知。

## 映射结论

两份实现一致：

| 输入 TID | 返回 AC | AC→TID 选取的代表值 |
|---|---|---|
| 0、3 | `WLAN_WME_AC_BE` | 0 |
| 1、2 | `WLAN_WME_AC_BK` | 1 |
| 4、5 | `WLAN_WME_AC_VI` | 5 |
| 6、7 | `WLAN_WME_AC_VO` | 6 |

AC→TID 只选代表值，不是逆运算；例如 TID 3 经 BE 再转回会得到 0。

## 边界与检查办法

TID→AC 的最后一支是默认 VO，宏本身不校验 0～7；不能认为越界输入会被拒绝。AC→TID 的默认值是 0。排查优先级问题时，分别核对“归类AC”和“选择代表TID”，并检查调用前的输入约束。

本次未检查全部调用点，未编译或上板；这是实现定位指引，不是经批准的产品规则或运行保证。

## 证据

[本轮静态分析记录](../../docs-raw/specs/hi1105-wme-snap-static-analysis.md)，以及卡头引用的两项目宏定义。原件为 GB18030，保留原字节；不凭目录名推断启用条件。
