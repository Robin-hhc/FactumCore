---
id: rfc9956-wifi-nqb-mapping
profile: protocol
title: RFC 9956 的 NQB Wi-Fi 映射与 Default 隔离边界
summary: DSCP 45 请求 NQB 的独立浅队列；Wi-Fi 的 UP 0、3、5 选择取决于分队能力，旧设备互通不等于完整 PHB 支持。
aliases: [RFC9956, RFC 9956, NQB, Non-Queue-Building, DSCP 45]
tags: [wifi, qos, diffserv, nqb, dscp, protocol-background]
scope:
  applicability: unknown
  contexts: []
doc_ref:
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 185
    line_end: 190
    evidence_ref: service-limits
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 274
    line_end: 323
    evidence_ref: service-role
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 377
    line_end: 448
    evidence_ref: sender-eligibility
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 480
    line_end: 580
    evidence_ref: primary-requirements
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 609
    line_end: 644
    evidence_ref: traffic-protection
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 667
    line_end: 718
    evidence_ref: protection-conditions
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 783
    line_end: 790
    evidence_ref: ecn-treatment
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 813
    line_end: 829
    evidence_ref: unsupported-nqb
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 905
    line_end: 977
    evidence_ref: unmanaged-domain
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 1129
    line_end: 1173
    evidence_ref: wifi-support
  - doc_id: doc-a6b34e0d1a4e5e1c7d96
    line_start: 1253
    line_end: 1339
    evidence_ref: wifi-rfc8325-update
  - doc_id: doc-17ac18e24a7dd8586d31
    line_start: 1266
    line_end: 1277
    evidence_ref: rfc8325-passthrough-baseline
code_ref: []
claims:
  - id: nqb-eligibility-isolation
    text_ref: '#nqb-eligibility-isolation'
    evidence_kind: normative
    usage: guidance
    source_refs: [service-limits, service-role, sender-eligibility, primary-requirements, traffic-protection, protection-conditions, ecn-treatment]
    context_ids: []
    verification_requirements: []
  - id: wifi-mapping-update
    text_ref: '#wifi-mapping-update'
    evidence_kind: normative
    usage: guidance
    source_refs: [wifi-support, wifi-rfc8325-update, primary-requirements]
    context_ids: []
    verification_requirements: []
  - id: passthrough-domain-boundaries
    text_ref: '#passthrough-domain-boundaries'
    evidence_kind: normative
    usage: guidance
    source_refs: [rfc8325-passthrough-baseline, wifi-rfc8325-update, unsupported-nqb, unmanaged-domain]
    context_ids: []
    verification_requirements: []
relations:
  - type: related_to
    target_card_id: rfc8325-diffserv-up-ac-boundaries
    context_ids: []
  - type: related_to
    target_card_id: rfc8622-lower-effort-phb
    context_ids: []
---
# RFC 9956 的 NQB Wi-Fi 映射与 Default 隔离边界

本卡提炼 RFC 9956（2026 年 5 月）的 Wi-Fi NQB 映射、对 RFC 8325 的更新及必要的符合性前提。它是规范背景，不是完整 NQB 实施指南或产品支持声明。

<a id="nqb-eligibility-isolation"></a>
## DSCP 45 的含义与分队前提

NQB 是与 Default 深队列 best-effort 服务互补的独立浅队列服务，目的是隔离符合发送行为的低速、平滑微流，避免与容量探测、突发流共享队列造成的排队时延和丢包。NQB 与 Default **SHOULD** 有同等转发偏好；它不承诺最低速率，也不提供超出浅缓冲界限的时延保证。其服务定位与[拥塞时让位于 BE 的 LE](rfc8622-lower-effort-phb.md)不同。

应用 **RECOMMENDED** 用 DSCP **45**（二进制 `101101`）标记合格 NQB 微流。资格按单向微流判断：速率由应用限制，约不超过“典型”路径容量的 1%，且须平滑发送，使任意时段 `T` 内的 IP 字节数不超过 `R × T + MTU`，其中 `R` 以字节/秒表示上述速率上界。原文的 500 kbps 是典型路径约 50 Mbps 情境下的示例，不是所有路径的固定门槛。超出该速率公式的流量 **MUST NOT** 标 NQB；应用仍须检测并适当响应容量不足，不能因标记低速流就免除拥塞响应责任。

仅把 DSCP 映射到 UP 不能证明 PHB 支持。RFC 9956 §5 的关键门槛包括：

- 节点 **MUST** 给 NQB 提供与 Default 分开的队列；NQB 缓冲 **MUST** 显著小于 Default 缓冲，按共享 NQB/Default 出口速率折算不超过 10 ms 是 **RECOMMENDED** 配置。
- 节点 **SHOULD** 使两类流量平等共享链路；Default 的限额或保证也 **SHOULD** 平等地由两类共享。**SHOULD NOT** 单独限制 NQB 聚合速率，向非 DS 域发送的特定保护情形除外；这不禁止逐微流保护。
- 默认 **SHOULD** 将 DSCP 45 分类进 NQB 队列，且节点 **MUST** 支持配置该分类使用的 DSCP。节点 **MUST** 提供可检测滥用的统计；服务多个用户的设备 **SHOULD** 支持按用户配置资源，并对每用户的 NQB/QB 合计流量执行相应限额。
- 节点 **SHOULD** 支持按实际微流行为识别不合格流量并重分类到 QB 或丢弃的 traffic protection；其判断 **SHOULD NOT** 基于端口或源/目的 IP 等构造。若实现该功能，**MUST** 避免微流状态耗尽导致节点失败。没有有效保护时，错标 QB 仍可能使浅队列拥塞并损害合格 NQB。
- NQB 的 traffic protection 及为保护非托管网络而设置的重标记/限速功能，对 NQB 标记报文 **MUST** 不因 ECN 字段不同而区别处理；这条义务的对象是这些 NQB 网络功能。

<a id="wifi-mapping-update"></a>
## Wi-Fi 映射的能力分支

RFC 9956 §7.3 及 §7.3.2 对 RFC 8325 §4.2.9/Figure 1 的更新，依赖**是否真正与 Default 分队**：

| 设备能力/条件 | 标记与队列选择 | 规范强度 |
|---|---|---|
| 能在 Default 所在 AC_BE 内提供独立 NQB 队列 | 优先提供独立 UP 0 队列，将 NQB 放入其中 | 同一 AC 内分队是 SHOULD/RECOMMENDED；独立 UP 0 是 RECOMMENDED |
| 因硬件等限制不能提供独立 UP 0 队列 | 可映射到 UP 3；仍要检查它是否与 Default 分队 | MAY |
| UP 0、UP 3 都不能提供与 Default 分开的队列 | 改用 UP 5，进入 AC_VI | RECOMMENDED；采用 RFC 8325 而无法提供独立 AC_BE 队列的系统为 SHOULD |

因此，UP 0、3、5 不是可任意互换的三种同等配置。使用默认“取 DSCP 高三位”时，45 会落到 UP 5/AC_VI；旧设备的默认 EDCA 通常又让 AC_VI 获得高于 AC_BE 的统计优先级。RFC 将这种场景作为既有 Wi-Fi **互通**讨论，不能据此宣称具备完整 NQB PHB 支持。

为使 AC_VI 与 AC_BE 的转发偏好相同，Wi-Fi 系统 **MAY** 将两者 EDCA 参数配置一致；但并非所有 AP 都允许这样配置，还须结合跨域保护条件。映射表中出现 AC_VI 也不把 NQB 变成申请高优先服务的业务类别。

<a id="passthrough-domain-boundaries"></a>
## 透传例外与跨域边界

RFC 9956 向 RFC 8325 §5.3 首段添加 **NQB DSCP 45 的例外**：原段一般不推荐透传未认证/未授权设备的 DSCP，而 NQB 45 编码的是 best-effort 服务。这个具体例外不改变发送资格，也不取消下述跨域保护条件。

普通不支持 NQB PHB 的网络/节点，**RECOMMENDED** 按 Default 处理 NQB 标记报文，且 **SHOULD NOT** 改写其 DSCP，以便后续节点仍可提供 NQB。但在没有相应协议的前提下，若下游已知不支持 Diffserv，或下游的流量管理能力未知，则要另外应用 §6.4.1 的保护建议：

- 上游运营者 **RECOMMENDED** 在交付前选择保护措施。其一是改标 Default/其它 Class Selector；为此场景设计的设备默认 **SHOULD** 将 NQB 改标 DSCP 0，并 **SHOULD** 允许改变或禁用这一行为。代价是更后续域也失去 NQB 标记。
- 另一种选择是 traffic protection 或整形/限速，减轻下游可能给 DSCP 45 高优先级的影响。若选择 traffic protection，它对违规流量 **MUST** 改标 DSCP 0/其它 Class Selector 或丢弃；该方法只有在设备确为路径瓶颈等条件下才可能保护后续跳，并非通用充分条件。

一般保留标记与面向非 DS/未知域的保护是不同部署条件，不能用其中一句覆盖所有网络边界。具体整形/限速参数需回读 §6.4.1，本卡不复制全部参数。

## 标准版本与产品支持边界

[RFC 8325 层次/策略卡](rfc8325-diffserv-up-ac-boundaries.md)及 LE 卡的有效结论与来源继续保留；这里仅补充 NQB 更新，不代表取得完整现代 IEEE 802.11 规范。

当前项目的芯片、固件、构建、DSCP 分类、独立队列、缓冲、EDCA 可配置性、traffic protection 与运行符合性均为 **unknown**。本卡没有据代码、编译、测量或硬件验证产品支持 NQB。

## 证据

[RFC 9956 本地原文](../../../docs-raw/protocols/ieee80211/rfc9956.txt)及 [RFC 8325 §5.3 原始上下文](../../../docs-raw/protocols/ieee80211/rfc8325.txt)。卡头使用已存在的真实文档 ID 和实际文本行号；新增 NQB 规则由 RFC 9956 支持。
