---
id: wifi-snap-encapsulation-static
profile: rule
title: mac_set_snap 的组织码选择、字节序与偏移接口
summary: AARP/IPX选择BTEP，其余选择RFC1042；两份同名函数的偏移接口不同，EtherType参数原值写入。
aliases: [mac_set_snap, SNAP, BTEP, RFC1042]
tags: [wifi, snap, encapsulation, static-analysis]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-d8389b4a2a143dce8784
    line_start: 30
    line_end: 77
    evidence_ref: analysis
code_ref:
  - code_id: code-faa30bbcd54c6906317c
    line_start: 178
    line_end: 206
    symbol: mac_set_snap
    evidence_ref: host-snap
  - code_id: code-59020d9c0848e0372079
    line_start: 2468
    line_end: 2502
    symbol: mac_set_snap
    evidence_ref: device-snap
claims:
  - id: encapsulation
    text_ref: '#encapsulation'
    evidence_kind: implementation
    usage: guidance
    source_refs: [analysis, host-snap, device-snap]
    context_ids: []
    verification_requirements: []
---
# mac_set_snap 的组织码选择、字节序与偏移接口

<a id="encapsulation"></a>
## 规则对象

本次复制的 Host 与 Device 两份 `mac_set_snap` 函数，分别独立描述其静态实现；构建及产品适用条件未知，不推断二者之间存在调用关系。

## 封装结论

两份函数均将 AARP/IPX 常量经 `oal_byteorder_host_to_net_uint16` 转换后，与传入的 `us_ether_type` 比较。命中时选 `SNAP_BTEP_ORGCODE_0/1/2`，其他分支选 `SNAP_RFC1042_ORGCODE_0/1/2`。

LLC DSAP/SSAP 均写 `SNAP_LLC_LSAP`，控制字段写 `LLC_UI`；SNAP 的 EtherType 字段直接接收参数原值，赋值处没有再转字节序。排查分支不命中时，应检查传入值与比较常量的字节序是否一致。

## 接口差异

| 实现 | SNAP 写入位置相对 netbuf_data 的偏移 | 写完后的 pull 参数 |
|---|---|---|
| Host | `ETHER_HDR_LEN - SNAP_LLC_FRAME_LEN` | 同一表达式 |
| Device | 调用者传入的 `uc_offset` | `uc_offset` |

两份同名函数的参数不能机械互换；比较封装位置时，应检查各自接口和调用者准备缓冲区的方式。

## 边界与检查办法

组织码这里只确认使用哪个宏，不把注释当成最终数值证明。尚未验证调用者的实际 offset、头部空间、完整发送路径、编译或硬件行为；`RFC1042` 是源码分支命名，不构成标准符合性结论。

## 证据

[本轮静态分析记录](../../docs-raw/specs/hi1105-wme-snap-static-analysis.md)及卡头两份函数引用。代码来源已按 GB18030 登记，未转写原文件。
