---
id: ieee80211e-edca-admission-tspec
doc_ref:
- doc_id: doc-f1b2902e8bbdf5b03a63
  page_start: 9
  page_end: 9
- doc_id: doc-f1b2902e8bbdf5b03a63
  page_start: 14
  page_end: 17
code_ref: []
tags: [wifi, '802.11e', qos, edca, acm, addts, tspec]
lifecycle: stable
---
# 802.11e EDCA 准入中的 ACM、ADDTS 与 Medium Time

IEEE 802.11-08/1214-02-00aa 的 2008 年教程把准入控制作为 EDCA 上限制高优先级流数量的手段。启用准入后，已接纳的流仍采用争用接入。依据：doc-f1b2902e8bbdf5b03a63 第 14、17 页。

## 从公告到接纳

AP 在每个访问类别的参数记录中标明 ACM。教程以 Beacon 公告为例。STA 要使用强制准入的类别时，通过 ADDTS Request 提交流量规格 TSPEC；AP 作出准入决定，并通过 ADDTS Response 反馈。第 15 页把标称 MSDU 大小、平均数据速率、最低 PHY 速率和额外带宽裕量（SBA）列为该历史教程中的准入必需参数。教程以正的 Medium Time 表示接纳，第 16 页的表格将其标为接纳后由 AP 返回的值。依据：doc-f1b2902e8bbdf5b03a63 第 9、15–16 页。

## 接纳后的使用时间

在教程描述的 WMM 场景中，STA 按统计周期对照实际使用时间和获准的 Medium Time。教程给出的 WMM 周期为 1 秒。超过获准值时，停止使用该 AC 的 EDCA 参数，可考虑适用且没有 ACM 的类别。准入保护依赖当地 AP 的接纳决策；相邻 BSS 独立分配时仍可能相互竞争。依据：doc-f1b2902e8bbdf5b03a63 第 14–15、17 页。

## 适用范围

本文记录历史教程中的接纳流程。字段编码、当前规范的精确要求和产品支持范围，需要回到具体版本的正式规范和实现核实。