---
id: rfc8622-lower-effort-phb
profile: protocol
title: RFC 8622 的 LE 行为、DSCP 标记与 Wi-Fi 映射更新
summary: LE 在拥塞时让位于 BE，使用 DSCP 1；对 RFC 8325 的更新将 LE 与旧 CS1 低优先级流量均映射到 UP 1/AC_BK。
aliases: [RFC8622, RFC 8622, Lower Effort, LE PHB, scavenger, Low-Priority Data]
tags: [wifi, qos, diffserv, dscp, lower-effort, protocol-background]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 121
    line_end: 218
    evidence_ref: le-purpose-applicability
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 298
    line_end: 328
    evidence_ref: le-phb
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 364
    line_end: 372
    evidence_ref: le-codepoint
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 435
    line_end: 494
    evidence_ref: cross-domain
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 511
    line_end: 519
    evidence_ref: multicast-limits
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 569
    line_end: 602
    evidence_ref: legacy-cs1
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 664
    line_end: 707
    evidence_ref: rfc8325-update
  - doc_id: doc-3a7ef5cc728376f33dea
    line_start: 711
    line_end: 743
    evidence_ref: le-assignment
code_ref: []
claims:
  - id: le-behavior
    text_ref: '#le-behavior'
    evidence_kind: normative
    usage: guidance
    source_refs: [le-purpose-applicability, le-phb]
    context_ids: []
    verification_requirements: []
  - id: le-dscp-wifi-update
    text_ref: '#le-dscp-wifi-update'
    evidence_kind: normative
    usage: guidance
    source_refs: [le-codepoint, legacy-cs1, rfc8325-update, le-assignment]
    context_ids: []
    verification_requirements: []
  - id: cross-domain-limits
    text_ref: '#cross-domain-limits'
    evidence_kind: normative
    usage: guidance
    source_refs: [cross-domain, multicast-limits]
    context_ids: []
    verification_requirements: []
relations:
  - type: related_to
    target_card_id: rfc8325-diffserv-up-ac-boundaries
    context_ids: []
---
# RFC 8622 的 LE 行为、DSCP 标记与 Wi-Fi 映射更新

本卡提炼 RFC 8622（2019 年 6 月）的 Lower-Effort Per-Hop Behavior，供规范背景检索；它描述逐跳行为及特定映射更新，不证明本项目实现支持。

<a id="le-behavior"></a>
## 行为与适用条件

LE 面向对及时转发要求低、能利用剩余容量的流量。其目标是在资源紧张时保护 Default PHB 的 Best-Effort（BE）流量：RFC 规定 LE **SHOULD** 具有比 BE 更低的转发优先级，拥塞时 **SHOULD** 先丢弃 LE，再丢 BE。理想 scavenger 模型只在其它 PHB 没有等待发送的报文时转发 LE；实际调度也可反映运营者避免完全饥饿的策略，不能断言所有 LE 实现都必然完全停发。

LE 可能经历很低吞吐、长期中断甚至完全丢包，不提供最低带宽或交付保证。应用须能容忍这种服务；RFC 推荐 LE 也采用拥塞控制，并能检测饥饿、重试或恢复会话。不能因为报文标为 LE，就省略拥塞控制。RFC 也明确 **SHOULD NOT** 把普通客户互联网流量普遍改为 LE，或用降级至 LE 代替对本应丢弃流量的丢弃，尤其是未授权流量。

实现可以用优先服务 BE 的独立 LE 队列；原文也允许公共 BE/LE 队列内按队长或驻留时间阈值丢弃 LE 的 AQM 方案。因此，规范行为不能简化成“必须有一个独立硬件队列”。

RFC 还规定 LE 报文 **SHOULD** 使用 ECN；LE 实现 **SHOULD** 对已标记为 ECT（ECN-Capable Transport）的报文采用 CE（Congestion Experienced）拥塞标记；LE 使用的传输协议 **SHOULD** 支持并采用 ECN。CE 建议适用于具有 ECT 标记的报文，三项建议均保留 SHOULD 强度。

<a id="le-dscp-wifi-update"></a>
## DSCP 与 RFC 8325 更新

| 标记 | DSCP 二进制 | DSCP 十进制 | RFC 8622 的定位 |
|---|---|---|---|
| LE | `000001` | 1 | 推荐的明确 LE 码点 |
| CS1 | `001000` | 8 | 旧版 Low-Priority Data 标记；建议尽可能迁移到 LE |

CS1 在按原始 Class Selector 语义处理的域中可能比 BE 获得更高优先级，造成与 LE 目的相反的优先级倒置，因此不能把 CS1 和 LE 视为任意网络中行为等价的标记。

RFC 8622 §11 明确更新 RFC 8325 §4.2.10 和 Figure 1：**标为 LE 的 Low-Priority Data，以及使用 legacy CS1 的该类流量，都推荐映射到 UP 1，归入 AC_BK。** 它不是仅保留旧 CS1 表，也不是将任意业务都标为 LE。

DSCP 1 是 IP 层码点，UP 1 是无线优先级；这里的关联来自明确更新条款，不是数值相同就自动等价，也不能由“取 DSCP 高三位”的默认实践替代该推荐映射。

<a id="cross-domain-limits"></a>
## 跨域与资源边界

不支持或不实施 LE PHB 的域，**SHOULD NOT** 仅因 LE 标记就丢包；RFC 推荐将其按 default PHB 转发，同时保留 LE DSCP，使后续域仍有机会按 LE 处理。不推荐把 LE 标记直接漂白为 DSCP 0。仍用旧 CS1 表示 LE 的域，**SHOULD** 在出域到下一 DS 域时改标为 LE `000001`。

按 BE 转发 LE 会让它与原 BE 聚合争资源，因而失去 LE 的 no-harm 属性；这时原文允许对 LE 聚合限速。不能把“已设置 DSCP 1”当成全路径已经保护 BE 的证据。

组播还可能在出端口转发之前，就因路由器内部复制消耗资源而影响其它流量。因此，仅检查输出链路上的低优先调度不足以确认完整资源隔离。

## 标准版本与产品支持边界

本卡只覆盖 RFC 8622 的 LE 规则及其明确的 RFC 8325 更新。[RFC 8325 层次与策略卡](rfc8325-diffserv-up-ac-boundaries.md)保留一般映射层次、方向和部署前提；本卡不替代其有效结论，也不扩张为完整现代 Wi-Fi 或全部 QoS 规则。

当前项目的产品、构建、实际 DSCP/UP 映射、队列/AQM、跨域标记保存及运行效果均为 **unknown**；本卡没有代码、构建或硬件符合性结论。

## 证据

[RFC 8622 本地原文](../../../docs-raw/protocols/ieee80211/rfc8622.txt)：卡头用真实来源 ID 及实际文本行号，分别定位目的/适用条件、逐跳行为、码点、跨域处理、组播限制及 RFC 8325 更新。
