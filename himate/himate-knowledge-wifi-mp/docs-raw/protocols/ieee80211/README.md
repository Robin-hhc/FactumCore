# IEEE 802.11 相关资料来源清单

取得日期：2026-10-30。这里只列原件来源、版本和边界，不作为独立知识正文。
原件保留下载字节。本适配分支提供下列原件及 SHA-256，不携带取得机器的下载日志。以下版本与勘误状态记录于 2026-10-30，需要最新状态时核对官方入口。

| 文件 | 官方来源 | 文档性质和版本 | 重要边界 |
|---|---|---|---|
| [ieee-p80211-1996-d3-mac-tutorial.pdf](ieee-p80211-1996-d3-mac-tutorial.pdf) | [IEEE 工作组原PDF](https://www.ieee802.org/11/Tutorial/MAC.pdf)、[教程目录](https://www.ieee802.org/11/Tutorial/index.html) | 1996年3月，IEEE P802.11-96/49C，基于D3.0草案的MAC教程；22个PDF页 | 历史教学资料，原文明确为未批准草案内容，不能冒充完整正式标准，也不能当作现代安全或QoS要求。 |
| [rfc8325.txt](rfc8325.txt) | [RFC Editor原TXT](https://www.rfc-editor.org/rfc/rfc8325.txt)、[当前信息页](https://www.rfc-editor.org/info/rfc8325/) | RFC 8325，2018年2月，Standards Track / Proposed Standard | 讨论Diffserv与802.11映射；已由RFC 8622、RFC 9956更新，应结合更新和勘误使用，不是完整802.11规范。 |
| [rfc1042.txt](rfc1042.txt) | [RFC Editor原TXT](https://www.rfc-editor.org/rfc/rfc1042.txt)、[当前信息页](https://www.rfc-editor.org/info/rfc1042/) | RFC 1042 / STD 43，1988年2月，Internet Standard | IEEE 802网络上的IP/ARP与LLC/SNAP背景；不是完整802.11标准或所有以太类型桥接规则。 |
| [rfc8622.txt](rfc8622.txt) | [RFC Editor原TXT](https://www.rfc-editor.org/rfc/rfc8622.txt)、[当前信息页](https://www.rfc-editor.org/info/rfc8622/) | RFC 8622，2019年6月，Standards Track / Proposed Standard | Lower-Effort PHB；更新RFC 8325相关DSCP建议，需在对应业务范围内使用。 |
| [rfc9956.txt](rfc9956.txt) | [RFC Editor原TXT](https://www.rfc-editor.org/rfc/rfc9956.txt)、[当前信息页](https://www.rfc-editor.org/info/rfc9956/) | RFC 9956，2026年5月，Standards Track / Proposed Standard | Non-Queue-Building PHB；更新RFC 8325针对该codepoint的映射，不构成完整无线实现要求。 |

## RFC 8325 的更新与勘误

其官方信息页目前列出RFC 8622和RFC 9956为更新文件，本目录一并保存两份官方原文。
[官方勘误入口](https://www.rfc-editor.org/errata/rfc8325)当前跳转到[记录页](https://errata.rfc-editor.org/search/?rfc_number=8325&presentation=records)。
本次记录页列有3项Verified勘误：7588、8112、8113，以及1项Held for Document Update：7520；后者的状态与Verified不同，此清单不把其视为已生效修改。
特别是部分映射和引用章节存在勘误，原RFC下载文件本身不会为此改写。
本适配分支不包含取得机器的勘误页面缓存；上面的记录描述当时所见状态，不能作为最新勘误状态接口。

## SHA-256

| 文件 | SHA-256 |
|---|---|
| ieee-p80211-1996-d3-mac-tutorial.pdf | `c9ddad95f5b96c599c20880aa9e3bf4ddb94accfbafcb00caa6b367b3ac12335` |
| rfc8325.txt | `6a059ababe36062810b17a5d0f44424d783c9f77b8fd6c36e362d816d3b9e031` |
| rfc1042.txt | `e8737abe7f7b80ae2e84b8cada0ea02d8cc3c4ad2414e902cc055e6953a01c55` |
| rfc8622.txt | `d45ac4c6af99cc83cf36da8c1fcadfc985e0f8f93880d3186398fe397c506f13` |
| rfc9956.txt | `555732d09155816f3dc9ac1f80c474c1767858f7de138480c2a28622e0eb32ef` |

## 完整标准的取得状态

已核对IEEE官方[GET项目说明](https://standards.ieee.org/products-programs/ieee-get-program/)和[IEEE 802 GET目录](https://ieeexplore.ieee.org/browse/standards/get-program/page/series?id=68)。
该项目要求在取得标准PDF前接受使用条款；本次自动访问目录返回418，没有取得完整IEEE 802.11标准PDF。
本目录没有使用镜像、绕过登录或付费限制，也不把教程/RFC冒充完整标准。
