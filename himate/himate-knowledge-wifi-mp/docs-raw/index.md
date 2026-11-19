# 原件目录

## 分支约定

`main` 存放开发内容，供内部迁移。`docs-raw/` 和 `knowledge/` 在该分支保留目录骨架、配套说明和示例配置。

`test` 用于本地测试和 OpenFlow 可视化验收。每次 `main` 合入开发更新后，同步到 `test`，保持同一开发版本。

源文档和随文附件放入 `docs-raw/` 的相应目录，提交到 `test`。入库复核通过后，`knowledge/` 中的正式知识卡与对应的 `governance/sources.lock.yaml` 一起提交到 `test`。执行端的 `sources/dbox.local.yml` 由本机配置。

## 目录分类

| 目录 | 材料 |
|---|---|
| conventions/ | 规则与约定原件 |
| chips/ | 芯片资料原件 |
| stories/ | 需求与场景原件，已登记的 `storys/` 原件沿用原路径 |
| specs/ | 设计与规格原件 |
| protocols/ | 协议资料原件 |
| troubleshooting/ | 问题定位与排查经验原件 |

按材料性质选择目录，再使用入库 Workflow 处理。来源清单可记录原件身份、版本和取得位置。扫描读取实际原件内容，目录页提供导航。

## 本地测试原件

- [两项目WME/SNAP源码静态分析记录](specs/hi1105-wme-snap-static-analysis.md)：描述实际复制代码的有限静态观察。
- [IEEE 802.11相关官方资料及来源清单](protocols/ieee80211/README.md)：保留IEEE历史教程和相关RFC原件、版本及更新关系。

上述材料不证明产品构建、驱动运行或标准符合性。
