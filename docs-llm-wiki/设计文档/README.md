# 设计文档入口与状态

更新日期：2026-10-19。

## 当前设计入口

本轮总体设计以用户确认的 [AIoTBot 最终设计](aibot.md) 为准，知识子系统的具体实现按 [知识库详细设计](知识库详细设计.md) 展开。代码相关卡保留两道门禁：本地通过即 stable 并落入 `knowledge/`，上库后按最新业务代码只读二次检查，失败回本地修订。纯文档卡由人工更新确认，不要求两道门禁；首发只读取 `docs-raw/` 五类材料目录内已落地的原件，`sources/` 链接更新、dbox 仓外映射、wiki 网页获取及 3ms 接入均延后。

首版仅 WiFi，覆盖 chip12/chip08/chip07c 的 Host/Device 六个逻辑 Target。详设按主设计 §5.3 与第 11 章展开：第 2 章完整文件树，第 3 章逐文件职责、开发要求与验收，第 4 章三条链路，第 5 章开发顺序与验收。生产/治理 Workflow 见 §3.4；CANNBot 固定版本及改造边界见附录 A。

本项目自有 Skill 与 Workflow Skill 统一使用 `hs-common-` 前缀，全局入口为 `hs-common-workspace-explore`；具体路径和调用名以详设为准，分类目录与第三方原始引用不改名。

| 文档 | 定位 |
|---|---|
| [aibot.md](aibot.md) | AIoTBot 最终总体设计 |
| [知识库详细设计.md](知识库详细设计.md) | 目录和逐文件开发设计，串联生产、治理、消费；保留本地 stable、代码双门禁及 raw 文档人工确认；接口尚待实现 |
| [Wi-Fi 知识库架构设计.md](Wi-Fi%20知识库架构设计.md) | 此前总体设计，保留追溯；不覆盖本轮最终设计及明确修正 |

## 当前开发入口

知识库 v1 已进入 SDD 开发。按用户后续部署决议，现统一在 FactumCore 单仓维护：根目录 `skills/`、`workflows/`、`config.yml` 与 `aiot-wifi-knowledge/`，原 `docs/` 整体迁移为 `docs-llm-wiki/`。[SDD 实施入口](../sdd/knowledge-v1/README.md) 包含需求、九模块的 spec/design/tasks、28 张依赖任务及 149 路径与 E01–E34 追踪矩阵。WiFi 领域根是普通目录，不含嵌套 Git；原有 `aiot-knowledge/` 与历史隔离开发目录保持原身份，不搬迁或覆盖。

首批 T01 声明契约与 CLI、T02 项目发现和入口实际读取已有验证记录；当前按 T03→T05→T06→T07 开发 raw 文档到人工确认后 stable 的闭环，完成后逐模块合入并推送用户指定的 FactumCore 远端。完整生产、代码双门禁、索引、维护及部署按后续任务推进。宿主隐式触发、真实六 Target/三 pair 和外部权限验证分别保留待验，不能用基础测试或单仓迁移通过代替。

## 历史细化稿与实现入口

本目录的 01–04 来自此前远端提交，是旧版细化稿，保留原文供追溯，尚未按当前架构同步。其中 `raw0/raw1`、旧卡契约、查询与治理约定，以及“工具功能等价、可随时替换”的表述，不作为当前实施依据。05（落地路线与评测）已于 2026-10-09 自设计文档归档目录并入本目录；架构主文档已由 `docs/架构设计.md` 改名《Wi-Fi 知识库架构设计.md》收口于本目录，原 v0.1 讨论稿同名文件由此取代。

以下实现入口保留供维护知识仓时查阅；具体能力需进入独立 [aiot-knowledge](https://github.com/Robin-hhc/aiot-knowledge) 核验，不能把本轮设计接口视为已经实现：

- [安装与使用](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/installation_and_usage.md)
- [知识契约](https://github.com/Robin-hhc/aiot-knowledge/blob/main/governance/specs/okf.md)
- [治理与消费流程](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/workflows/governance-and-consumption.md)

旧版细化稿：

| 文档 | 当前阅读方式 |
|---|---|
| [01-代码图谱部署](01-代码图谱部署.md) | 历史部署与评测记录；工具覆盖、替换成本及实际效果仍需按试点基线验证 |
| [02-LLM-Wiki构建](02-LLM-Wiki构建.md) | 历史目录、卡片和摄入设计；当前以知识仓现行契约与流程为准 |
| [03-治理机制](03-治理机制.md) | 历史治理设想；已实现检查与待实现自动化按现行入口区分 |
| [04-消费与问答](04-消费与问答.md) | 历史查询与编排设计；当前检索及证据核对按现行消费流程执行 |
| [05-落地路线与评测](05-落地路线与评测.md) | 历史落地路线与依赖清单；本轮知识子系统实施顺序见《知识库详细设计》第 5 章 |

本次未取得 01 中 HWDL 评测的原始运行资料，也未复测，不对其历史结果重新判分；不能据此证明工具等价或对所有产品场景普遍有效。
