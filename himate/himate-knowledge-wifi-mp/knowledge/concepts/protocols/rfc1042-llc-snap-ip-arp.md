---
id: rfc1042-llc-snap-ip-arp
profile: protocol
title: RFC 1042 的 IP/ARP LLC/SNAP 头格式与数值表示
summary: RFC 1042 为所述 IEEE 802.3/802.4/802.5 网络规定 IP/ARP 的 8 字节 LLC/SNAP 头；规范背景与产品实现分开。
aliases: [RFC1042, RFC 1042, LLC, SNAP, IP, ARP]
tags: [wifi, llc, snap, encapsulation, protocol-background]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-923012ff8b8e4c62e14d
    line_start: 19
    line_end: 104
    evidence_ref: rfc-scope
  - doc_id: doc-923012ff8b8e4c62e14d
    line_start: 127
    line_end: 149
    evidence_ref: rfc-header
  - doc_id: doc-923012ff8b8e4c62e14d
    line_start: 235
    line_end: 247
    evidence_ref: rfc-ip-arp
  - doc_id: doc-923012ff8b8e4c62e14d
    line_start: 719
    line_end: 743
    evidence_ref: rfc-numbers
code_ref: []
claims:
  - id: llc-snap-format
    text_ref: '#llc-snap-format'
    evidence_kind: normative
    usage: guidance
    source_refs: [rfc-scope, rfc-header, rfc-ip-arp]
    context_ids: []
    verification_requirements: []
  - id: number-representation
    text_ref: '#number-representation'
    evidence_kind: normative
    usage: guidance
    source_refs: [rfc-numbers]
    context_ids: []
    verification_requirements: []
relations:
  - type: related_to
    target_card_id: wifi-snap-encapsulation-static
    context_ids: []
---
# RFC 1042 的 IP/ARP LLC/SNAP 头格式与数值表示

<a id="llc-snap-format"></a>
## 机制与适用范围

RFC 1042（1988 年 2 月）描述 IP 数据报与 ARP 请求/应答在 IEEE 802.3、802.4、802.5 网络上的封装。文中推荐且要求实现支持 802.2 Type 1，后续描述以 Type 1 为前提；同一 IEEE 802 网络内的双方通过 XID 确认彼此支持并达成同意时，可使用 Type 2。本卡的字段表针对 Type 1 UI 封装。

MAC 头之后是 802.2 LLC 头和 SNAP 头，二者合计 **8 字节**。SNAP 的组织码为零时，后续 16 位用 EtherType 标识上层协议。

## 字段

| 层与字段 | 长度 | RFC 1042 中的值 |
|---|---|---|
| LLC DSAP | 1 字节 | 170（十六进制 `AA`） |
| LLC SSAP | 1 字节 | 170（十六进制 `AA`） |
| LLC Control | 1 字节 | 3（十六进制 `03`，Unnumbered Information） |
| SNAP Organization Code | 3 字节 | 0，即 `00 00 00` |
| SNAP EtherType | 2 字节 | IP 为 2048（`0x0800`），ARP 为 2054（`0x0806`） |

原文提到为满足链路最小帧长而补的零字节不属于 IP 数据报，也不计入 IP 头的 total length。不能把链路补齐长度当成 IP 数据报长度。

<a id="number-representation"></a>
## 数值表示

RFC 附录区分 IEEE 按位传输顺序的表示和 Internet 的逐字节 big-endian 表示。同一 UI 控制码在附录 IEEE HEX 列写为 `C0`，在 Internet Binary 列为 `00000011`（十进制 3，即 `03`）；SNAP SAP 在 IEEE HEX 列为 `55`，Internet Binary 为 `10101010`（十进制 170，即 `AA`）。

比较文档数值、抓包字段或代码常量前，应先确认采用哪一种表示。这里的差异涉及**单个字节内的位表示顺序**，不能当成 16 位 EtherType 的主机序/网络序转换规则。

## 标准版本与产品支持边界

以上是 RFC 1042 这份历史规范的要求，来源讨论的是 802.3/802.4/802.5；文件存放在 `ieee80211/` 目录不代表它是完整的 802.11 规范。

当前产品、构建、宏值与运行行为均为 **unknown**。本卡供规范背景检索，不据此断言产品实现符合标准，也不证明 AARP/IPX 的全部 BTEP 例外规则。两份 `mac_set_snap` 的实际分支、参数字节序及偏移接口见[独立静态实现卡](../../rules/wifi-snap-encapsulation-static.md)，其结论仍以该卡的代码来源为依据。

## 证据

[RFC 1042 本地原文](../../../docs-raw/protocols/ieee80211/rfc1042.txt)：卡头定位分别覆盖规范范围与通信类型、Header Format、IP/ARP 通用封装与补齐规则、Appendix on Numbers；均使用实际文本行号。
