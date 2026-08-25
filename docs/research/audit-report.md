# 知识图谱建立策略研究终审报告

审计日期：2026-08-25

审计内容基线：`931909f`（论文正文提交；本报告提交前）

## 1. 审计结论

现行研究已经从内部实现层和预设完整方案，重组为三个面向 Agent 的知识建立类别：

1. 代码知识；
2. 文档与领域知识；
3. 代码—文档双向链接。

正文首先以代码检索、程序分析、文档/Wiki 和跨项目链接证据论证三项能力，再分别比较市面方案。CodeGraph、Serena/SCIP、Joern/codebadger 位于同一个代码知识类别，只区分导航与程序分析深度；Graphify、Understand Anything、RepoDoc 按实际能力跨类别出现；LLM-Wiki/WiCER 只作为文档知识管理方法。

本轮没有运行 WiFiDemo 构建、候选工具或 Agent 效果实验，也没有宣布最终赢家。C0–C4 和 B01–B15 只是后续可证伪的实验条件与问题。效果相近时才以开放许可证、离线复现和适配成本作为 tie-break。

## 2. 独立重算结果

以下数字均从当前文件重新计算，没有沿用上一版报告：

| 项目 | 实际数量 | 重算口径 |
|---|---:|---|
| 来源记录 | 42 | `source-ledger.md` 中 `### S001` 至 `### S042`；连续性检查为 `True` |
| `claim-verified` | 16 | 精确匹配 `状态：claim-verified` |
| `primary-read` | 26 | 精确匹配 `状态：primary-read` |
| 论文材料 | 17 | 来源记录中的非互斥类型统计 |
| AI 公司官方材料 | 5 | 来源记录中的非互斥类型统计 |
| 开源项目材料 | 31 | 来源记录中的非互斥类型统计 |
| Benchmark 问题 | 15 | `benchmark-backlog.md` 中恰好 15 行 `B01`–`B15` |
| 本地 Markdown 链接 | 10 | 对 `docs/research/*.md` 的相对链接逐项解析 |
| 本地链接缺失 | 0 | `Test-Path -LiteralPath` 检查 |

来源类型非互斥，不能把 17、5、31 相加为 42。一个来源记录可能同时包含论文与官方开源仓库。

## 3. “2+1”能力桥接论证审计

正文第 2 章具备计划要求的完整推导链：

| 论证步骤 | 正文证据 | 审计判断 |
|---|---|---|
| 检索证据 → 代码知识 | Agent Retrieval Bench、CORE-Bench、ContextBench | 明确区分候选召回、实际使用上下文和程序事实 |
| 结构图/程序分析 → 行为边界 | CodeGraph、Codebase-Memory、Joern、codebadger、QLCoder、RIG | 轻量导航与深度分析属于同一连续谱；均不自动产生领域意图 |
| 文档/Wiki → 领域解释与信息损失 | UA、Graphify、RepoDoc、LLM-Wiki、WiCER | 原始文档、生成资产和 Wiki 分开；生成文本不替代代码证据 |
| 跨项目证据 → 双向链接 | Graphify、UA、RepoDoc、RIG | 显式引用、语义映射、影响传播和构建锚定被分别说明 |
| 结论性质 | 正文第 2.4 节 | 明确标为本文的跨来源研究综合，不写成单篇论文的充分必要定理 |

因此“三项能力是必要能力集合”在措辞上有证据边界；“三项能力存在就一定准确”仍被明确否定。

## 4. 跨类别项目与排除项审计

### 4.1 代表项目覆盖

| 项目 | 代码知识 | 文档/领域知识 | 链接 | 两类问答过程 | 审计结果 |
|---|---:|---:|---:|---:|---|
| CodeGraph | 是 | 否 | 源码/结构回链 | 是 | 轻量代码图代表，不被包装成完整方案 |
| Joern/codebadger | 是 | 否 | 分析路径回源码 | 是 | 深度程序分析代表，不被预设为赢家 |
| Graphify | 是 | 是 | 是 | 是 | 在各适用类别重复分析 |
| Understand Anything | 是 | 是 | 是 | 是 | 在各适用类别重复分析 |
| RepoDoc | 是 | 是 | 是 | 是 | 在各适用类别重复分析 |
| GitNexus | 是 | 部分 | 部分 | 是 | 代码 context/impact 为主，领域能力不夸大 |
| LLM-Wiki/WiCER | 否 | 是 | 必须外接 | 是 | 只作为文档知识组织方法 |
| RIG | 构建/测试知识 | 部分架构说明 | 构建证据 | 是 | 只补强 Target/组件事实 |

### 4.2 现行分类中已移除的内容

主论文、方案清单、证据矩阵和 Benchmark 不再使用旧的实现层、双主干或四变体作为市场方案分类。通用上下文装载、提示模板和对话记忆没有被列为独立知识图谱产品；只有它们与代码/文档实体建立可核验链接时，相关机制才可能作为局部接口或实验控制。

历史 design specs 和 plans 保持原样，不纳入现行分类术语扫描。

## 5. 数字、来源所有权与限制审计

正文共有 9 个包含样本或效果数字的实质性段落：

| 正文当前行 | 来源 | 所有权与审计边界 |
|---:|---|---|
| 46 | S001 | 独立检索实验；427 样本、25 仓、308 快照和 27%–35% 漏检只适用于文件检索 |
| 48 | S002、S003 | 独立基准；报告查询/标注/任务/仓库/语言/模型/Agent 样本规模，不外推 WiFi C |
| 56 | S022、S023 | 作者文档 QA 实验；F1、dangling links、catastrophic rate 和恢复质量不作为代码效果 |
| 62 | S041 | RepoDoc 作者评估；24 仓、8 语言及覆盖/完整性/成本数字不证明 Target 或领域事实正确 |
| 90 | S007 | CodeGraph 第一方 7 仓、每臂 4 次架构问答；效率变化不等于调用边准确率 |
| 92 | S005 | Codebase-Memory 作者 31 仓实验；83% vs 92% 与 Token/调用权衡不外推 WiFi C |
| 98 | S039 | codebadger 作者三案例；8,000 methods 是单案例规模，不是 aggregate accuracy |
| 102 | S040 | QLCoder 作者 176 CVE、111 Java 项目对照；53.4% vs 10% 只限查询合成 |
| 108 | S042 | RIG 作者 8 仓、每仓 30 问、3 Agent 对照；只覆盖构建/测试架构 |

上述 S 记录均为 `claim-verified`，并保存样本、模型/Agent、基线、指标、数字语境、第一方/独立属性和限制。不同任务和指标没有合并为总分，也没有直接形成产品排名。

## 6. 链接与新鲜度审计

`code-domain-linkage.md` 已从完整 schema 设计缩减为可观察策略比较，但仍保留可靠答案必需的最小合同：

- 关系含义；
- code revision、Target、symbol 和 `file:line`；
- document revision、具体位置和原始来源；
- parser/compiler、固定规则、人工或模型产生方式；
- active、candidate、stale、contradicted 或 superseded 状态。

领域到代码和代码到解释均有步骤化链路。显式引用、结构图驱动生成、模型语义映射、影响传播和构建工件锚定分别记录优势、失效方式与代表项目。LLM/embedding 只能产生候选，不能自行升级为确定性事实。

## 7. WiFi MAC 约束与实验边界

现行文档一致保留以下硬门槛：

1. repository revision、Target 和 `file:line` 可定位；
2. 生效宏、active branch 和 source occurrence 以真实编译工件为准；
3. direct/indirect call 分开，未解析候选不隐藏；
4. Host/Device 以 Event/Message 和两侧证据连接，不制造跨二进制 `CALLS`；
5. 代码/文档变化能触发 stale detection 与重新验证；
6. 事实准确性、检索效率与最终 Agent 正确率分别报告。

C0–C4 比较普通导航、轻量图、深度分析、图+原始文档、图+生成文档+双向链接。B01–B15 连续且每个 ID 只对应一项预注册问题。外部案例允许 Zephyr、RIOT、Contiki-NG 及其他结构相邻的开放 C 项目。

## 8. 历史注意事项完整性

历史原始文件与现行归档文件的 Git blob identity 一致：

```text
3015105de36e55e8fc7041e0a256f98476964382:目标代码仓注意事项.md
  -> d01d7cb0a9145a71db8be073aabe6e84e68c05f5

HEAD:docs/research/wifi-mac-repository-design-considerations.md
  -> d01d7cb0a9145a71db8be073aabe6e84e68c05f5
```

因此本轮没有改写历史注意事项的内容，只调整和新增现行研究文档。

## 9. 终审命令与结果

| 检查 | 结果 |
|---|---|
| 来源计数与连续性 | 42；S001–S042 连续 |
| `claim-verified` / `primary-read` | 16 / 26 |
| Benchmark 行数 | 15 |
| 现行四文档旧分类术语 | 0 命中 |
| `research.md` / 旧中文路径引用 | 0 命中 |
| 本地 Markdown 链接 | 10 个已检查，0 缺失 |
| 历史注意事项 blob | 两端同为 `d01d7cb0...c05f5` |
| `git diff --check` | 本报告提交前复跑；应为 0 error |

本终审证明文档结构、来源边界、链接与历史材料完整性符合本轮要求，不证明任何候选已经通过 WiFiDemo 实验。最终选型仍为 `unknown / Benchmark required`。
