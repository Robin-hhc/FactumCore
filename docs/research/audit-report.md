# 架构研究证据终审报告

审计日期：2026-08-14

最终修复基线：`6f4422c62252392d9e6a27c9095f9f6fbfb3879d`

## 1. 审计结论

本轮终审把当前公开证据操作化为 A Agent 原生联邦语义服务与 B Target-specific CPG 两个可归因、可证伪的主实验骨架，以及 A0、A1、B0、B1 四个初始变体。它们不是候选空间穷尽或唯一产品选型；B01–B15 可以因新决策轴、混杂或硬失败要求拆分、增加或重定义实验臂。

本轮关闭了此前的范围措辞、证据 schema、WiFiDemo 浮动 checkout、S024 示例百分比和外部短 hash 问题。没有运行 WiFiDemo 构建、A0/A1/B0/B1、候选工具或性能实验，也没有新增本地测量。源码/配置观察与 compiler-artifact ground truth 已明确分开。

## 2. 独立重算结果

| 项目 | 实际数量 | 重算口径 |
|---|---:|---|
| 来源记录 | 40 | `source-ledger.md` 中 `### S001` 至 `### S040`，编号连续 |
| `claim-verified` | 14 | 只计来源记录内精确的 `- 状态：claim-verified` |
| `primary-read` | 26 | 只计来源记录内精确的 `- 状态：primary-read` |
| 论文材料 | 15 | 按来源记录的非互斥类型和原始材料逐条复核 |
| AI 公司官方材料 | 5 | 按 `公司官方实践`/`AI 公司官方实践` 的来源记录复核 |
| 开源项目材料 | 30 | 按官方仓库、项目文档、公开实验代码/Benchmark 伴随材料逐条复核 |
| 标准记录 | 1 | S029；一个记录组包含 SWHID、PROV-O 与 SARIF |
| 正文数字扫描命中行 | 9 | `research.md` 第 90、92、94、96、116、130、133、135、137 行 |
| 含效果或对照数字的行 | 8 | 上述 9 行中第 92 行只报告样本/标注规模；S024 的第 132 行不在数字扫描内 |
| 逐项目档案 | 28 | R01–R09 共 9、A01–A12 共 12、H01–H07 共 7 |
| 当前主实验骨架 | 2 | A 与 B；是初始实验设计，不是完备候选数 |
| 当前待测变体 | 4 | A0、A1、B0、B1；0/1 是查询模式 |
| Benchmark | 15 | B01–B15 连续，共 15 项 |

来源类型是非互斥分布，不能相加为 40。带论文和官方仓库的同一 S 记录可以同时进入论文与开源项目材料分组，但来源总数仍只计一次。

## 3. 数字、样本、基线与限制审计

正文数字扫描共命中 9 行。每行均有 S 编号和直接原始 URL；相关 ledger 记录保存样本、模型/Agent、对照、指标、数字语境和外推限制。

| `research.md` 行 | 来源 | 审计判断 |
|---:|---|---|
| 90 | S001 | 427 样本与 27%–35% 漏检均限定为文件检索，不外推程序语义或 WiFi Target |
| 92 | S002、S003 | 只报告查询、标注、任务、仓库、语言和 Agent 样本规模；不计效果数字行 |
| 94 | S005、S006 | 83%/92%、Token/调用倍数保留 31 仓第一方语境；当前 README 能力不与论文快照混写 |
| 96 | S007 | 88%/53%/62%/44%/80% 保留 7 仓、每臂 4 次、第一方架构问答语境；不解释为调用边准确率 |
| 116 | S039、S040 | 8,000 是单案例规模；53.4% 对 10% 限定为 176 CVE、111 个 Java 项目的作者对照 |
| 130 | S022、S023 | Wiki 数字保留多跳问答、LLM-as-judge 和非代码任务限制 |
| 133 | S025 | 未公开样本量的 GitHub 第一方 A/B；不外推产品效果 |
| 135 | S026、S027 | 5G/Skill 结果保留任务类型、版本与负收益语境，不外推 WiFiDemo |
| 137 | S028、S030 | RepoMem 限定 Python bug localization；108,000 行/283 sessions 只是观察性案例规模 |

S024 保持 `primary-read`，其台账不再记录精确示例百分比或把示例 token 算术当指标；这不改变 40 来源、14 `claim-verified` 或正文数字行计数。其余效果/对照数字均由相应 `claim-verified` 记录支撑。

## 4. typed evidence、权限与生命周期合同

`code-domain-linkage.md` 及正文现行合同为：

1. 代码主体按 `Repository`、`RepositoryRevision`、`SourceArtifact`、`CodeEntity`、`TargetProfile`、`TargetOccurrence`、TU 和 code source span 分离；领域来源另用 `SourceRevision`/`source_revision_id` 与 `SourceLocation`。
2. `Evidence` 是判别联合。`kind: code` 引用代码 `RepositoryRevision`、`TargetOccurrence`、`SourceArtifact` 和 code source span；`kind: domain` 才引用领域 `SourceRevision`、`SourceLocation` 与 quoted digest。
3. Assertion 使用 `evidence[]`，最低 evidence kind 由 `predicate_class × machine_status` 决定：`code_fact` 需 code，`domain_statement` 需 domain，`code_domain_link` 需两者；纯代码 `EXTRACTED` 不要求也不得伪造领域 citation。
4. `EXTRACTED`、`RULE_DERIVED`、`INFERRED_CANDIDATE`、`CURATED` 仍是唯一四种 `machine_status`。Agent 只能创建 `INFERRED_CANDIDATE`，不能自行升级权限。
5. `active`、`stale`、`contradicted`、`invalid`、`superseded` 仍是 lifecycle 而非第五种权限；代码、Target、规则、领域来源或模型变化按实际 evidence dependency 有界失效。
6. Host 与 Device 保持独立编译视角，只通过 `Event`/`Message` 断言及分段 code/domain evidence 连接；禁止制造跨二进制 `CALLS` edge。

## 5. WiFiDemo 可复现范围

| 字段 | 核验值 |
|---|---|
| 只读仓路径 | `E:/WiFiDemo/WiFiDemo` |
| canonical origin | `https://github.com/Robin-hhc/WiFiDemo.git` |
| full HEAD / `repository_revision` | `8102322afbe5f81ecf6a35601ac4731ed14feb2d` |
| 核验时 branch | `main`；仅描述 checkout，不作为快照身份 |
| dirty 状态 | `clean`；tracked unstaged、tracked staged、untracked 均为空 |
| tracked patch SHA-256 | `not applicable`；clean snapshot 没有 tracked patch |
| untracked manifest SHA-256 / 范围 | `not applicable`；0 path，空范围 |

只读命令为 `git remote get-url origin`、`git rev-parse HEAD`、`git status --porcelain=v1 --untracked-files=all`、`git diff --quiet HEAD --`、`git diff --cached --quiet HEAD --` 和 `git ls-files --others --exclude-standard`；两个 diff 命令退出 0，status/untracked 输出为空。W01–W08 的 CMake/Python/C 路径与行号只是该 revision 的源码/配置观察。未来 B01/B02 ground truth 必须来自成功构建后的 compiler argv、`flags.make`/compilation database、`-dM`/`-E`、对象/符号和生成物；本轮未运行这些步骤。

## 6. 候选范围与现行设计文档

`research.md`、`evidence-matrix.md`、`benchmark-backlog.md` 和 2026-08-14 design spec 均将 A/B 表述为当前证据构造的初始实验 arms，明确不是候选空间穷尽，且允许 Benchmark 拆分、增加或重定义 arms。现行决策文档不再出现旧三族的标识符。

`docs/superpowers/specs/2026-08-13-wifi-mac-knowledge-architecture-research-design.md` 是未修改的历史设计文档；它不属于现行决策扫描范围，也没有被改写成当前结论。

## 7. 外部案例不可变 revision

2026-08-14 对三个官方 GitHub 仓执行 `git ls-remote --tags`，结果为：

| 仓库/ref | ref 类型与 object | 固定 commit |
|---|---|---|
| Zephyr `refs/tags/v4.4.0` | annotated tag object `4f50f0ba8905f27b2f60123d0ee0934fda6fe134` | dereferenced `684c9e8f32e4373a21098559f748f06915f950c9` |
| RIOT `refs/tags/2026.04.01` | annotated tag object `56ab5471996e422657d7fac81bd76da3b07378df` | dereferenced `4a70282b1f1ac6e004138b4ada684a4dc4639653` |
| Contiki-NG `refs/tags/release/v5.1` | lightweight tag；虽含 `/`，不是 branch | direct commit `2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4` |

`source-ledger.md` 同时记录 annotated tag object 与 dereferenced commit；`research.md` 和 `benchmark-backlog.md` 使用完整 commit object ID，不再只写短 hash。

## 8. URL、本地交叉引用与有效性边界

`research.md` 的本地研究附录链接指向 source ledger、solution inventory、WiFiDemo workload casebook、code-domain linkage、evidence matrix 和 benchmark backlog；提交前以 `if exist` 对六个目标逐项复核。新增外部 revision 只来自官方 GitHub remote，不使用搜索页或二手转述。

本终审不等于候选实验通过。B01–B15 仍须裁决 Target frontend、宏/active source、函数指针/ops、alias/dataflow/slice、稳定 ID、断言失效/修复、最终 Agent 正确性、资源、离线复现与逐组件许可。Sourcegraph MCP 产品许可、自托管和部署边界仍为 `unknown`；开放 SCIP 协议不能替代产品许可审计。

## 9. 最终检查记录

提交前和暂存后均须复跑：typed evidence 定向扫描、WiFiDemo snapshot/只读状态、非穷尽措辞、S024 精确示例百分比、三外部 full SHA、40/14/15 计数、现行文档旧标识符、本地链接、`git diff --check`、staged name list，以及主工作区/WiFiDemo 与初始基线对比。实际命令、退出码和最终 commit 记录在 `.superpowers/sdd/2026-08-14-research-synthesis-and-candidate-reassessment/final-fix-report.md`。
