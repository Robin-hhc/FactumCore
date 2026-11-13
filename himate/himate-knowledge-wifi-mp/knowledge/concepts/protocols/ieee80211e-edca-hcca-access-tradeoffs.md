---
id: ieee80211e-edca-hcca-access-tradeoffs
doc_ref:
- doc_id: doc-f1b2902e8bbdf5b03a63
  page_start: 4
  page_end: 13
- doc_id: doc-f1b2902e8bbdf5b03a63
  page_start: 18
  page_end: 24
code_ref: []
tags: [wifi, '802.11e', qos, edca, hcca, txop]
lifecycle: stable
---
# 802.11e 的 EDCA 竞争与 HCCA 调度边界

IEEE 802.11-08/1214-02-00aa 是 2008 年工作组教程。它用 DCF 的分布式争用与 PCF 的集中轮询作背景，分别说明 EDCA 的分类争用和 HCCA 的协调器分配发送机会。依据：doc-f1b2902e8bbdf5b03a63 第 4–6 页。

## EDCA 如何改变争用

四类 AC 按各自的 AIFS、争用窗口和 TXOP 上限参与接入。不同等待和退避参数改变获得信道的相对机会。AP 可公告每个 AC 的参数。教程第 7 页采用展示用的访问类别编号，第 9 页另列参数记录的 ACI 编码，读图时以 AC_BE、AC_BK、AC_VI、AC_VO 的名称对齐。分类与上层映射见 [RFC 8325 的 DSCP→UP→AC](rfc8325-diffserv-up-ac-boundaries.md)。依据：doc-f1b2902e8bbdf5b03a63 第 7–9 页。

同一优先级的流仍争用，普通 EDCA 无法给出确定的接入、带宽、时延或抖动保障。教程的负载示例显示，信道饱和时流之间的吞吐可能不均匀，同类流增多时总吞吐也可能降低。跨设备、跨负载或有重叠 BSS 时需要重新验证。若 AP 对某 AC 启用强制准入，见 [EDCA 准入与 TSPEC](ieee80211e-edca-admission-tspec.md)。依据：doc-f1b2902e8bbdf5b03a63 第 9–13 页。

## HCCA 如何分配发送机会

教程用 QoS CF-Poll 表示协调器向站点授予 TXOP。协调器依据流量描述和 TSPEC 制定服务间隔及分配。教程列出的 HCCA TSPEC 最大服务间隔属于流量约束，接纳响应中的服务间隔则属于调度结果。图示区分按计划间隔轮询与上一个 TXOP 结束后紧接下一次轮询，后者偏向利用率，前者可配合预定省电。效率图的比较条件是高负载、单信道且无重叠 BSS。图中 WMM-SA 一组的吞吐较高。调度复杂度及不同 AP 的重叠调度仍影响实际表现。依据：doc-f1b2902e8bbdf5b03a63 第 18–24 页。

## 适用范围

用于理解 802.11e 的历史机制和读图边界。设备是否实现 HCCA、采用何种队列及参数、实际吞吐和延迟均需按对应版本的规范、源码或测试核实。