---
id: rfc8325-diffserv-up-ac-boundaries
profile: protocol
title: RFC 8325 的 DSCP→UP→AC 层次与策略边界
summary: 区分 IP 标记、无线优先级与竞争类别；默认位映射会失真，上下行及网络部署条件决定策略边界。
aliases: [RFC8325, RFC 8325, Diffserv, DSCP, UP, AC, EDCA]
tags: [wifi, qos, dscp, mapping, protocol-background]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 214
    line_end: 235
    evidence_ref: applicability
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 362
    line_end: 435
    evidence_ref: fields-trust
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 460
    line_end: 523
    evidence_ref: service-deployment
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 530
    line_end: 581
    evidence_ref: default-map
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 609
    line_end: 638
    evidence_ref: reverse-loss
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 687
    line_end: 741
    evidence_ref: capabilities
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 1183
    line_end: 1264
    evidence_ref: upstream-policy
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 1314
    line_end: 1332
    evidence_ref: upstream-control
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 1490
    line_end: 1554
    evidence_ref: up-ac
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 1819
    line_end: 1838
    evidence_ref: edge-control
code_ref: []
claims:
  - id: mapping-layers
    text_ref: '#mapping-layers'
    evidence_kind: normative
    usage: guidance
    source_refs: [fields-trust, default-map, reverse-loss, up-ac, service-deployment]
    context_ids: []
    verification_requirements: []
  - id: capability-conditions
    text_ref: '#capability-conditions'
    evidence_kind: normative
    usage: guidance
    source_refs: [applicability, capabilities, default-map]
    context_ids: []
    verification_requirements: []
  - id: direction-trust-boundaries
    text_ref: '#direction-trust-boundaries'
    evidence_kind: normative
    usage: guidance
    source_refs: [fields-trust, service-deployment, upstream-policy, upstream-control, edge-control]
    context_ids: []
    verification_requirements: []
relations:
  - type: related_to
    target_card_id: wifi-wme-tid-ac-mapping-static
    context_ids: []
---
# RFC 8325 的 DSCP→UP→AC 层次与策略边界

本卡提炼 **RFC 8325（2018 年）** 中的层次和策略边界，供规范背景检索。其映射与透传规则须结合后续更新和勘误使用；本卡不是最新完整映射表，也不是产品实现声明。

<a id="mapping-layers"></a>
## 映射层次

| 层次 | 表达内容 | 不能据此推出的结论 |
|---|---|---|
| DSCP | IP 层 6 位标记；与 IPv4 TOS/IPv6 Traffic Class 中另 2 位 ECN 分开 | 不能仅按数值大小确定无线服务 |
| UP | 无线 MSDU 的 0～7 优先级，由 MAC 以上的层赋予 | UP 数值顺序不等于 AC 的服务顺序 |
| AC | 竞争无线介质所用的类别及相关 EDCA 参数 | 同一 AC 不等于相同的 IP 业务类别，也不恢复原 DSCP |

RFC 所述 UP→AC 对应为：**0/3→AC_BE，1/2→AC_BK，4/5→AC_VI，6/7→AC_VO**。这里 UP 1、2 属于 Background，而 UP 0 属于 Best Effort，不能把 UP 当成简单递增的服务等级。

RFC 将取 DSCP 高三位作为 UP 描述为常见的“默认映射实践”，不代表它是所有产品的固定行为或对所有业务都合适。例如 EF 的位值 `101110` 经此法得到 UP 5，进入 AC_VI，而非语音所期望的 AC_VO。反向以 `UP × 8` 生成 DSCP 只补出三个零位，不能恢复丢失的信息。

该 RFC 对照 IEEE 802.11-2016 指出：介质竞争具有随机性，不能仅靠 AC 归类保证 EF 式严格优先级，或 AF 式最低带宽。规范中的类别关系不构成端到端时延、带宽或产品性能保证。

<a id="capability-conditions"></a>
## 能力与适用条件

适用对象是互联 Diffserv 与 Wi-Fi 基础设施的 IP 网络，可包含边缘 AP、无线回传或 mesh 等部署。不能只因存在 AP 就认定它是 Diffserv 域边界。

RFC 推荐 AP 和终端支持 DSCP/UP 标记与可配置映射；下行建议还以 AP/控制器支持非默认映射、AP 和终端能按 UP 区分排队/出队为前提。文中 per-UP 队列向对应 AC 出队是常见实施模型，不是本项目实现事实，也不能把四个 AC 等同于必有且仅有四个物理队列。RFC 明确允许管理员按部署需要覆盖其建议。

<a id="direction-trust-boundaries"></a>
## 方向、信任与网络角色

“信任”指设备接受报文的 QoS 标记，不是标记本身证明发送方有资格获得该服务。RFC 8325 对上行明确要求 AP **不得根据无线主机设置的 L2 UP 再生成 DSCP**；若业务要求、技术限制或管理策略需要利用主机标记，则推荐利用其 L3 DSCP。该选择仍受策略限制，不是无条件透传授权。

AP 具备所需分类和标记能力时，RFC 推荐由管理员把无线边缘作为策略执行点，按管理策略设置或重设上行 DSCP。CS6/CS7 的处置还要区分角色：

- AP 下游只有终端的 Wi-Fi-at-the-edge 模型中，RFC 推荐将 CS6/CS7 映射到 UP 0；终端操作系统对请求这些标记的报文应重标 DSCP 0 并映射 UP 0。
- 在无线回传、mesh、AP-to-AP 等延伸基础设施的部署中，下游可能有网络设备；RFC 对其网络控制流量推荐 UP 7，不能套用“只有终端”的前提。
- 上行 CS6/CS7 原则上不应透传到有线网络，除非 AP 已由网络管理员或运营者专门配置允许。

## 版本与产品支持边界

本卡仅以本轮 RFC 8325 原文为正式引用。**不覆盖**后续 LE/NQB 更新、未认证来源 DSCP 透传的完整例外、流媒体/广播视频各码点的完整映射或全部勘误修订。决定这些具体策略前须合并对应更新和勘误；不能把旧版默认表或一条安全建议当成当前无例外的总规则。

本项目芯片、构建、实际映射表、队列结构和运行行为均为 **unknown**。[静态 WME TID/AC 卡](../../rules/wifi-wme-tid-ac-mapping-static.md)描述特定源码宏及其不可逆边界；这里的规范关系不替代该卡代码来源，也不证明产品遵循 RFC 8325。

## 证据

[RFC 8325 本地原文](../../../docs-raw/protocols/ieee80211/rfc8325.txt)：卡头按实际文本行号引用 §1.3、§1.6、§2、§3、§4 前提、§5 和 §6.2、§8.2 的相应内容；未引用原件来代证后续更新或勘误文本。
