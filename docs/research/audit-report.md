# 架构研究证据终审报告

审计日期：2026-08-14

审计基线：`fca7a8c90c79a2716711f9a3b30cdc608c01295e`

## 1. 审计结论

本轮证据终审通过，保留两条不阻断提交的 deferred minor 供最终审查。当前结论是两个待测主骨架和四个变体，不是唯一产品选型；没有运行 WiFiDemo 或候选工具实验，也没有新增本地测量。正文、证据矩阵和链接合同没有把 MCP 可调用性、架构容纳或第一方案例升级为 WiFi MAC 效果证明。

审计独立重算来源、状态、类型、数字行、候选角色和 Benchmark，没有复用上一版审计报告的 `S001–S036`、三架构短名单或 24 profile 计数。旧审计中的三族编号已随旧文本被替换；当前研究结论和证据矩阵均不再使用该分类。

## 2. 独立重算结果

| 项目 | 实际数量 | 重算口径 |
|---|---:|---|
| 来源记录 | 40 | `source-ledger.md` 中 `### S001` 至 `### S040`，编号连续 |
| `claim-verified` | 14 | 只计来源记录内精确的 `- 状态：claim-verified`；不计状态说明或汇总表 |
| `primary-read` | 26 | 只计来源记录内精确的 `- 状态：primary-read` |
| 论文材料 | 15 | 按来源记录的非互斥类型和原始材料逐条复核 |
| AI 公司官方材料 | 5 | 按 `公司官方实践`/`AI 公司官方实践` 的来源记录复核；Microsoft Research 的论文伴随页不重复作为公司工程实践 |
| 开源项目材料 | 30 | 按官方仓库、项目文档、公开实验代码/Benchmark 伴随材料逐条复核 |
| 标准记录 | 1 | S029；一个记录组包含 SWHID、PROV-O 与 SARIF |
| 正文数字扫描命中行 | 9 | `research.md` 第 90、92、94、96、116、130、132、134、136 行 |
| 含效果或对照数字的行 | 8 | 上述 9 行中第 92 行只报告样本/标注规模，不含效果数字 |
| 逐项目档案 | 28 | R01–R09 共 9、A01–A12 共 12、H01–H07 共 7 |
| 核心架构族 | 2 | A Agent 原生的联邦语义服务骨架；B Target-specific CPG 主骨架 |
| 待测变体 | 4 | A0、A1、B0、B1；0/1 是查询模式，不是第三个主骨架 |
| 排除为完整方案的对象组 | 5 | `solution-inventory.md` 第 17 章角色表；局部能力可保留 |
| 架构参考组 | 8 | 同一角色表，以逗号分隔的对象组计数 |
| 通用组件候选组 | 7 | 同一角色表“组件候选”行 |
| 可进入两主骨架的程序事实/Agent 接口组件组 | 7 | 同一角色表单列，不能与通用组件候选相加成互斥总数 |
| Benchmark | 15 | B01–B15 连续，共 15 项 |

来源类型是非互斥分布，不能相加为 40。带论文和官方仓库的同一 S 记录可以同时进入论文与开源项目材料分组，但来源总数仍只计一次。

`research.md` 第 14.1 节另有 6 条“排除为完整代码事实核心/完整方案”的显式说明；第 6 条把 Graphify/Understand Anything 作为一组排除出代码事实核心，但它们在 inventory 中仍归“架构参考”。因此角色表的 5 个“排除为完整方案”对象组与正文 6 条排除说明是不同口径，不应混算。

brief 给出的 `rg -c '核验状态：`claim-verified`'` 与当前 ledger schema 不一致：实际记录字段为 `- 状态：claim-verified`。字面命令无匹配，使用 record-level 锚定命令后得到 14；不能把说明段和汇总表中的三个额外 `claim-verified` 字符串计入来源状态。

## 3. 数字、样本、基线与限制审计

数字扫描共命中 9 行。每行均有 S 编号和直接原始 URL；相关 ledger 记录保存样本、模型/Agent、对照、指标、数字语境和外推限制。

| `research.md` 行 | 来源 | 审计判断 |
|---:|---|---|
| 90 | S001 | 427 样本与 27%–35% 漏检均限定为文件检索，不外推程序语义或 WiFi Target |
| 92 | S002、S003 | 只报告查询、标注、任务、仓库、语言和 Agent 样本规模；不计效果数字行 |
| 94 | S005、S006 | 83%/92%、Token/调用倍数保留 31 仓第一方语境；当前 README 能力不与论文快照混写 |
| 96 | S007 | 88%/53%/62%/44%/80% 保留 7 仓、每臂 4 次、第一方架构问答语境；不解释为调用边准确率 |
| 116 | S039、S040 | 8,000 是单案例规模；53.4% 对 10% 限定为 176 CVE、111 个 Java 项目的作者对照 |
| 130 | S022、S023 | Wiki 数字保留多跳问答、LLM-as-judge 和非代码任务限制 |
| 132 | S024、S025 | S024 的约 90% 是 10-Skill 示例算术而非效果实验；S025 是未公开样本量的 GitHub 第一方 A/B |
| 134 | S026、S027 | 5G/Skill 结果保留任务类型、版本与负收益语境，不外推 WiFiDemo |
| 136 | S028、S030 | RepoMem 限定 Python bug localization；108,000 行/283 sessions 只是观察性案例规模 |

S024 为 `primary-read`，其约 90% 只用于否定“示例算术等于受控效果”的错误解释，不作为性能结论；其余效果/对照数字均由相应 `claim-verified` 记录支撑。

## 4. Agent 证据三字段审计

正文已把 `Agent evidence`、`Producer relation`、`Review status` 分成三个可组合字段，并明确 A/B/C/D 与架构 A/B 属于不同命名空间。项目地图逐行保留三字段：

- Serena：B；project first-party；project self-test + official docs。约 20 项任务是 Agent 自评，不是固定受控 Benchmark。
- Sourcegraph MCP / SCIP：D；产品为 company first-party、协议为 project first-party；均是 official docs。MCP 和开放协议只证明接口存在。
- Codebase-Memory：A；author/project first-party；preprint + official docs。31 仓对照不是独立复现。
- CodeGraph：A；project first-party；project self-test + official docs。7 仓、每臂 4 次的第一方结果不证明调用边精度。
- Joern / codebadger：B；Joern project first-party、codebadger author first-party；official docs + preprint。三个案例不是 aggregate accuracy。
- CodeQL / QLCoder：A；CodeQL company first-party、QLCoder author first-party；official docs + preprint。受控结果限定在 Java/CVE/CodeQL。

正文明确写出“高层任务工具相对 raw DSL”只是 B10 待验证原则。MCP、LSP、CPG、开放协议和产品功能均未被描述为 Agent 效果证明。

## 5. 身份、权限、生命周期与 Host/Device 边界

`code-domain-linkage.md` 已覆盖以下终审门槛：

1. 代码主体按 `Repository`、`RepositoryRevision`、`SourceArtifact`、`CodeEntity`、`TargetProfile`、`TargetOccurrence`、TU 和 source span 分离；领域来源另用 `SourceRevision`/`source_revision_id`。
2. `EXTRACTED`、`RULE_DERIVED`、`INFERRED_CANDIDATE`、`CURATED` 是唯一四种 `machine_status`。Agent 只能创建 `INFERRED_CANDIDATE`，不能自行升级权限。
3. Assertion 最小字段含 producer、method version、provenance、confidence、review state、repository/source revision、Target、source span、lifecycle 和 invalidation reason。
4. `active`、`stale`、`contradicted`、`invalid`、`superseded` 是生命周期而非第五种事实权限；代码、Target、规则、来源或模型变化触发有界重建/重验。
5. Host 与 Device 保持独立编译视角，只通过 `Event`/`Message` 断言及分段证据连接；正文和链接合同均禁止制造跨二进制 `CALLS` edge。

## 6. 候选范围、旧文档与越界措辞

范围词扫描在 `research.md` 与 `evidence-matrix.md` 中没有命中“最终选型”“唯一方案”“一定优于”“已经证明…WiFi”“必须采用”或“直接替代”。旧三族编号和旧三方案措辞也没有出现在当前候选结论中。

`docs/superpowers/specs/2026-08-13-wifi-mac-knowledge-architecture-research-design.md` 是历史设计文档，未修改；它已被 `docs/superpowers/specs/2026-08-14-research-synthesis-and-candidate-reassessment-design.md` 取代。当前研究只以 2026-08-14 spec 的两个主骨架、两种查询模式和四个待测变体为现行设计。

## 7. 新增 URL 与本地交叉引用

逐个打开 `research.md` 中 S037–S040 的 8 个新增唯一 URL：

- S037：Serena 官方 GitHub 与官方 evaluation 文档；均可访问，分别支持 MCP/LSP 接口和“Agent 自评”语境。
- S038：Sourcegraph MCP 官方产品页可访问；SCIP 官方 GitHub 链接重定向到 `scip-code/scip`，仍是官方仓库。没有搜索页或转载页。
- S039：arXiv 原文与 codebadger 官方 GitHub 均可访问；论文摘要明确是三个案例。
- S040：arXiv 原文与 QLCoder 官方 GitHub 均可访问；论文摘要明确 176 CVE、111 个 Java 项目、53.4% 对 10%。

`research.md` 的 6 个本地研究附录链接均存在：source ledger、solution inventory、WiFiDemo workload casebook、code-domain linkage、evidence matrix 和 benchmark backlog。没有悬空的 `docs/research/*.md` 路径。

## 8. 未解决问题与 deferred minor

本审计通过不等于候选实验通过。以下问题仍须由 B01–B15 裁决：

- Target frontend 是否忠实消费真实编译命令、宏、include、生成物和 active source set；
- 函数指针/ops、alias、dataflow 与 slice 的 precision/recall 和候选规模；
- SourceEntity/TargetOccurrence 稳定 ID、跨 Target/跨 revision merge-split 行为；
- assertion invalidation、repair、revalidation 的 precision/recall 与错误沿用率；
- 最终 Agent 正确性、证据完整率、错误引用、拒答、raw DSL fallback 和成本；
- 逐组件许可、依赖/模型/容器再分发、离线复现和替代路径。

两条 deferred minor：

1. S038 的 Sourcegraph MCP 产品许可、自托管和部署边界仍为 `unknown`；开放 SCIP 协议不能替代产品许可审计。
2. `research.md` 结论仍使用“先导出八层骨架……当前范围因此缩小为两个主骨架”的推导措辞。正文已有“当前范围”“尚未确定唯一赢家”“架构推断偏差”和 Benchmark 可推翻条件，因此没有宣称候选空间完备；最终审查仍应判断该句是否可能被读成穷尽性结论。本任务未获授权修改 `research.md`。

## 9. 最终检查

占位符扫描、`git diff --check`、暂存区空白检查和工作树范围检查必须在提交前重新执行。计划内 Git 修改只允许 `docs/research/audit-report.md`；Task 6 执行报告写入 `.superpowers/sdd/.../task-6-report.md`，不纳入研究文档提交。
