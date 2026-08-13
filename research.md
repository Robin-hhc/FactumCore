# 面向多 Target WiFi MAC 驱动的代码知识架构：成熟路线、证据边界与候选收敛

版本：2026-08-14

## 摘要

本文研究一个限定问题：在结构类似 WiFiDemo 的多芯片、Host/Device 分离、宏与函数指针密集的 C WiFi MAC 驱动仓库中，应如何组织代码事实、领域知识和 Agent 查询能力。本文不复用 FactumCore 的既有实现，不预设图数据库或 Joern，也不在本阶段运行候选工具。证据来自近期论文与公开 Benchmark、AI 公司技术文章、开源项目官方材料，以及仍具时效性的经典论文和标准。

研究得到的主要结论不是某个唯一产品，而是三个可进入实验的架构族：编译器原生分层、Target-specific CPG 分层、轻量结构发现加编译器核验。三者都必须把 Target-specific compilation view、可定位源码证据和不确定性治理作为硬门槛。词法、向量、RepoMap、Tree-sitter 图、CPG、LLVM 分析器、Wiki、Skill 和 memory 分别解决不同问题，任何单项能力都不足以自动成为完整知识架构。开源优先只在正确性、效果、成本和运维没有决定性差异时作为 tie-break。

## 1. 研究问题与贡献

本文回答五个问题：

1. Agent 如何在大仓库中低成本定位相关代码，同时避免把检索相似度写成程序事实？
2. C 编译配置、直接/间接调用、CFG 和 dataflow 应由哪类程序分析提供？
3. Feature、Chip、Side、Event、规范和设计约束如何与代码实体双向链接？
4. 这些链接如何携带 Target、revision、provenance、confidence、冲突、失效和重验证状态？
5. 在不做当前实验的前提下，哪些路线明显不适合作为完整方案，哪些值得进入后续 Benchmark？

本文的交付不是静态“工具排行榜”，而是一套可审计的证据链：详细来源登记在 [source-ledger](docs/research/source-ledger.md)，WiFiDemo 结构案例在 [workload casebook](docs/research/wifidemo-workload-casebook.md)，方案档案在 [solution inventory](docs/research/solution-inventory.md)，代码—领域链接模型在 [linkage study](docs/research/code-domain-linkage.md)，候选状态在 [evidence matrix](docs/research/evidence-matrix.md)，待测问题在 [benchmark backlog](docs/research/benchmark-backlog.md)。

## 2. 方法

### 2.1 范围与时间窗口

检索截止到 2026-08-14。对快速变化的 Agent 检索、memory、Wiki 和 Skill，优先采用 2026 年材料；对 Clang/LLVM、SCIP、Kythe、CodeQL、Joern、Fraunhofer CPG、SVF、Frama-C、PhASAR 和 Semgrep，使用当前官方文档与仓库；对 CPG 定义、PROV-O 等基础概念，允许使用经典且仍有效的论文和标准。

来源仅接受：论文/公开 Benchmark、AI 相关公司发布的技术文章、开源项目官方文档/仓库/发布说明、国际或行业标准。项目第一方效果数据可以引用，但必须标注第一方，不能与独立 Benchmark 混写。搜索摘要只用于发现来源，不作为正文证据。

### 2.2 证据等级

本文用四个状态避免把文档声明当成实测结果：

- `verified`：独立实验、标准正文或已逐项核验的原始结果；
- `claimed`：作者、公司或开源项目材料明确声明，但未在 WiFiDemo 独立复现；
- `unsupported`：材料明确不提供，或方案定位与能力冲突；
- `unknown`：证据不足，不能以缺失信息推断“不支持”。

证据矩阵不计算综合总分，因为 Target 泄漏或失去源码 provenance 这类硬失败不能由更快查询抵消。所有 WiFiDemo 工具效果在本文均为 unknown；本文只读取代码结构示例，没有当前实验数据。

### 2.3 数字证据的解释规则

| 证据 | 原始结果 | 可支持的结论 | 不能外推的结论 |
|---|---|---|---|
| 独立 Agent Retrieval Bench [S001](https://arxiv.org/abs/2607.24882) | 记录的 Agent 轨迹在 27%–35% 样本上未命中 gold file；不同检索族分别赢得不同指标 | 词法、向量、结构检索应作为互补基线；需要 no-gold/abstention | 不证明任一检索族在 WiFi MAC 最优 |
| Codebase-Memory 第一方论文 [S005](https://arxiv.org/abs/2603.27277) | answer quality 为 83%，逐文件对照为 92%；约 10× 少 Token、2.1× 少工具调用 | 轻量结构图可能用一定质量交换探索成本 | 不等于调用边准确率，也不证明 Target 语义 |
| CodeGraph 第一方 Benchmark [S007](https://github.com/colbymchenry/codegraph) | 报告工具调用、时间、处理 Token、成本分别减少 88%、53%、62%、44%，但会话末残留上下文约增加 80% | 本地图和密集返回值得进入成本实验 | 小样本第一方架构问答不能证明普遍 Agent 提升 |
| GitHub Copilot Memory 第一方 A/B [S025](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/) | merge 任务为 90% 对 83%，review 为 77% 对 75%；作者报告显著性检验 | 带引用、反馈和按需验证的 memory 可能提高跨会话任务 | 产品实验不能替代当前代码事实或 WiFi 评测 |
| SWE-Bench 5G [S026](https://arxiv.org/abs/2604.26278) | 规格注入总体由 24% 到 30%，平均增加 12% Token；规格依赖类别增加 16.7–25 points，generic 类别为 0 | 领域知识收益依赖任务，必须 paired A/B 和执行验收 | 5G Core 结果不等于 WiFi MAC 效果 |
| SWE-Skills-Bench [S027](https://arxiv.org/abs/2603.15401) | 平均仅 +1.2%；错误版本 Skill 最多 -10%；Token 最多 +451% 且通过率不变 | Skill 需精确匹配、版本兼容和负收益测试 | 不能因平均收益低而否定所有专门 Skill |
| RepoMem [S028](https://openreview.net/pdf?id=8yjWLJy2eX) | Verified 的 Acc@5 为 76.5% 对 71.6%，resolve 为 40.4% 对 37.0%；稀疏历史组反而由 67.4% 降到 54.3% | 历史 memory 只能作候选，且需判断适用性 | 不能把历史摘要当当前 revision 事实 |

## 3. WiFiDemo 所代表的工作负载

WiFiDemo 当前 checkout 提供八个结构最小案例。它们不是 Benchmark 结果，而是选型必须覆盖的问题形状。

| 案例 | 最小代码形状 | 对知识架构的要求 |
|---|---|---|
| W01 Host 共代码 | `CHIP_SOURCES` 同时加入 chip2/chip8 实现 | Source Entity 与 Target occurrence 分离；目录名不等于芯片事实 |
| W02 Device 互斥源码 | `if(CHIP_TYPE STREQUAL "CHIP2") ... elseif(... "CHIP8")` | 以真实 Target 的源码集合和宏环境建事实 |
| W03 Target 宏 | chip8 Host 才追加 `_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD` | 同一源码在不同 Target 下拥有不同有效函数体/调用边 |
| W04 条件路径 | `#if ... dpa_forward_to_device ... #else ... hcc_tx_queue_put` | 返回 Target-local call/CFG，并把条件作为证据 |
| W05 ops 表 | `g_wlan_chip_ops = g_wlan_chip_ops_chip8` | 间接调用返回候选、赋值来源和选择条件；无法唯一解析时 abstain |
| W06 Host/Device Event | Host send → HCC → Device callback → FRW table | Event/Message 是协议实体，不伪装成跨二进制 `CALLS` |
| W07 公共源码归属 | 同一 `hcc_core.c` 参与两个 Host Target | Source identity、编译存在性与领域归属分别建模 |
| W08 同名函数/日志 | 两个芯片目录都有 `hcc_device_rx_handler` 和同一日志 | 搜索返回消歧候选、Target presence 和源码位置，不自动选一个 |

由此可得三个不可协商的完整方案硬门槛：

1. **Target-specific compilation view**：repository/revision/Target/compile command/macro/include/source occurrence 必须可表达；
2. **可定位源码证据**：任何代码事实和领域声明都能回到 revision、Target、file:line 与生成器；
3. **不确定性治理**：确定性代码事实、规则断言、人工知识和 LLM/embedding 候选分层，支持 provenance、confidence/review、conflict、stale/invalid 和重验证。

## 4. 问题一：代码导航与检索

### 4.1 近期证据否定“单一检索器足够”

独立的 [Agent Retrieval Bench](https://arxiv.org/abs/2607.24882)、[CORE-Bench](https://arxiv.org/abs/2606.11864) 和 [ContextBench](https://arxiv.org/abs/2602.05892) 分别从冻结仓库检索、多层代码检索和 Agent 上下文利用过程说明：传统语义搜索成绩不能直接外推到 issue-to-edit 或 broader context；Agent 可能提高 recall 却降低 precision；被探索内容与最终被使用内容不同。

因此检索层应保留四种互补能力：

- 词法/FTS：宏、日志、枚举、路径和短标识符的可解释入口；
- embedding：自然语言到词面不一致代码的候选召回；
- RepoMap 类结构摘要：在 Token 预算内提供定义和文件关系；[Aider 官方设计](https://aider.chat/docs/repomap.html)证明了这种接口形状，但不提供 C 编译语义；
- 结构图：跨文件调用、引用、继承和 impact 导航，但每条边必须保留生成方式与源码位置。

### 4.2 轻量结构图的合理边界

[Codebase-Memory](https://github.com/DeusData/codebase-memory-mcp) 和 [CodeGraph](https://github.com/colbymchenry/codegraph) 都展示了本地持久图、增量索引和 MCP 查询的成熟工程形态，可作为 L3 的发现层候选。[GitNexus](https://github.com/nxpatterns/gitnexus) 的 allowlist、只读 MCP、响应预算和 cluster/process 多尺度导航值得借鉴，但 PolyForm Noncommercial 许可证以及公开 C/C++ import 支持缺口使其不适合作为当前直接采用候选。[Understand Anything](https://github.com/Egonex-AI/Understand-Anything) 将确定性结构与 LLM 领域解释分层，适合做领域链接设计参考，而不是代码事实核心。

本层明确不提供：真实宏分支、Target occurrence、CFG/dataflow、可靠函数指针 target，以及已验证的 Feature/Event 事实。检索分数只能产生候选，不能产生 `CALLS` 或 `implements_feature`。

## 5. 问题二：语义程序表示与深度分析

### 5.1 CPG 不是精度来源

经典 CPG 将 AST、CFG 和程序依赖关系组织在统一图中，用于联合查询；原始论文在 Linux kernel 漏洞发现上证明了该表示的研究价值 [Yamaguchi et al.](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf)。但图的存在不会自动提高 C frontend、预处理、alias/points-to、external semantics 或 slice 的正确性。CPG 应被评估为表示/查询路线，而不是默认等同于“深度且准确”。

### 5.2 技术中立的能力分层

| 层次 | 成熟路线 | 可提供 | 主要缺口/风险 | 本研究定位 |
|---|---|---|---|---|
| 编译输入与 AST/IR | [Clang compilation database/LibTooling](https://clang.llvm.org/docs/JSONCompilationDatabase.html)、[LLVM IR](https://llvm.org/docs/LangRef.html) | 真实 argv、AST location、CFG/SSA 分析底座 | TU 边界、AST/IR 身份连接、自建服务成本 | L1 基础；L2/L3 的核验源 |
| 语义身份/交叉引用 | [SCIP/scip-clang](https://github.com/sourcegraph/scip-clang)、[Kythe](https://kythe.io/docs/schema-overview.html) | 符号身份、definition/reference、Target/revision 模型 | 不提供深 CFG/dataflow | identity 组件/参考 |
| 可查询代码数据库 | [CodeQL](https://codeql.github.com/docs/codeql-language-guides/advanced-dataflow-scenarios-cpp/) | 声明式 AST/CFG/dataflow/路径查询 | 引擎/CLI 许可边界；非默认开放内核 | 参考与 oracle 候选 |
| CPG | [Joern](https://docs.joern.io/code-property-graph/)、[Fraunhofer CPG](https://fraunhofer-aisec.github.io/cpg/) | 联合图、查询、部分 dataflow/slicing/summary | WiFiDemo 的 compdb、宏、函数指针和 Target 隔离未验证 | L2 可替换核心候选 |
| 深度分析 | [SVF](https://github.com/SVF-tools/SVF)、[PhASAR](https://github.com/secure-software-engineering/phasar)、[Frama-C Eva](https://www.frama-c.com/fc-plugins/eva.html) | points-to/value-flow、LLVM 数据流框架、抽象解释/切片 | 成本、IR→source 映射、摘要和许可证差异 | 按需 provider 候选 |
| 规则检查 | [Semgrep CE](https://github.com/semgrep/semgrep) | 快速语法/规则查询与源码结果 | 开源 CE 与 Pro 深分析边界；不是 Target compiler view | 局部规则组件 |

Joern 在这里与 Fraunhofer CPG、compiler-native、semantic-index 和专门分析器同级比较。当前公开材料支持 Joern 有 CPG、dataflow semantics 和 slicing API，却不足以证明它在 WiFiDemo 的四 Target、真实 GCC/CMake 宏和 ops 间接调用上优于其他路线；这些项必须保留为实验问题。

### 5.3 建议的分析职责边界

编译器产生 Target-local 事实；identity 层把 source entity 与 occurrence 连接；CPG 或深度 provider 回答需要 CFG、dataflow、slice 或函数指针的查询；Agent-facing 查询层只返回带限制、证据和不确定性的结果。不要预计算所有可能的深分析边，也不要让一个通用图 schema 假装所有边具有相同可信度。

## 6. 问题三：代码与领域知识如何链接

### 6.1 链接不是“给函数打标签”

需要区分两类身份：Source Entity 表示某 revision 中的文件、声明、定义或消息结构；Target Occurrence 表示该实体在某 Target、编译命令和宏环境中的存在及语义。Feature、Chip、Side、Event、Flow、DomainRule 和 SpecClause 作为独立领域实体，通过 typed assertion 连接 occurrence 或 source entity。

最小 assertion 形状为：

```text
Assertion {
  subject, predicate, object,
  repository, revision, target,
  evidence_location[], generator,
  provenance_source[], confidence, review_status,
  valid_from, valid_to, state, invalidated_by
}
```

这不是数据库表选型，而是跨实现必须保持的语义契约。稳定软件工件 ID 可参考 [SWHID](https://www.swhid.org/specification/v1.2/0.Introduction/)，派生、活动、责任人与失效可参考 [W3C PROV-O](https://www.w3.org/TR/prov-o/)，扫描 revision、源码 location 和 fingerprint 交换可参考 [SARIF](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html)。这些标准提供词汇，不要求照搬其存储格式。

### 6.2 四类链接及权限

| 链接类型 | 允许来源 | 默认权限 | 例子 |
|---|---|---|---|
| compiler/analyzer fact | compiler、indexer、static analyzer | 可成为 verified-code，但仍记录生成器和输入 digest | occurrence、direct call、CFG edge |
| deterministic rule | 配置、命名、注册表、协议字段规则 | verified-rule 或 pending-review | Event ID → handler table；宏 → Feature candidate |
| manual assertion | 领域专家、ADR、issue、规范映射 | manual-reviewed；依赖证据变化后需复核 | handler implements Feature；Known Edge Case |
| inferred candidate | embedding、LLM、聚类 | 只能是 candidate/inferred；不得覆盖前述事实 | 自然语言概念 → 可能相关函数 |

[Graphify](https://github.com/Graphify-Labs/graphify) 的 EXTRACTED/INFERRED/AMBIGUOUS 分层和 [Understand Anything](https://github.com/Egonex-AI/Understand-Anything) 的 structure/domain/claim/source 设计说明混合图已经是成熟探索方向。但二者公开材料没有证明 Target/revision、置信度校准和失效传播完备，因此只作为架构参考。

### 6.3 Host/Device Event 的专门链接

W06 不能用虚假的跨二进制 `CALLS` 表示。应建立 Event/Message 实体，并分别链接 producer、serialize/send、channel/subtype、receive/dispatch、registration 和 consumer。每一段仍属于自己的 Target view；跨侧导航是领域/协议边。这样既能从 Event 找代码，也能从 handler 返回适用 Event、Side、Target 和证据。

### 6.4 失效、冲突与重验证

原始资料不可静默覆盖；编译输入 digest 变化后重建代码事实；规则/模型版本变化后重算候选；人工 assertion 的 evidence 变化后标 stale 并通知 owner；多来源冲突并存而不是 last-write-wins。改名、移动、宏翻转、Target 删除和 Event ID 变化必须成为后续反事实测试。

## 7. 问题四：领域知识管理与 Agent 上下文

### 7.1 原始知识、编译知识与运行时事实分层

- **原始知识**：规范条款、设计文档、ADR、issue、commit、测试和日志样例；版本化且可引用；
- **编译知识**：Wiki、summary、Skill、查询模板；从原始资料和代码事实生成，可 stale、可重建；
- **运行时事实**：当前 revision/Target 的查询结果，由 compiler/index/analyzer 返回，不长期复制到 Skill 文本。

[LLM-Wiki](https://arxiv.org/abs/2605.25480) 和 [WiCER](https://arxiv.org/abs/2605.07068) 支持把文档视为可评估产物，并揭示盲目注入或过时内容的风险。[Google ADK Skills](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/) 与 [AWS Agent Toolkit Skills](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/skills.html) 展示 metadata → instructions → references/tools 的渐进披露模式；它适合组织 WiFi 分析程序，但 Skill 本身不提供代码 identity。

### 7.2 Memory 必须回到当前代码核验

[GitHub Copilot Memory](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/) 强调 citation、反馈、删除和即时验证；[RepoMem](https://www.microsoft.com/en-us/research/publication/improving-code-localization-with-repository-memory/) 表明历史对部分定位任务有帮助，也会在历史稀疏时干扰。因而 memory 只产生待核验候选；最终答案必须引用当前 revision/Target 的代码或原始领域来源。

### 7.3 Agent 接口应暴露的控制面

查询接口至少接受 `repository/revision/target`、结果上限、证据级别、允许的 inference 状态和分析预算；返回 stable ID、source span、provenance、confidence/review、候选集合和截断信息。Agent 可以先导航 metadata，再按需取源码或运行深分析，不能一次把全图和全部领域文档塞入上下文。

## 8. 候选收敛

### 8.1 排除为完整方案，但可保留局部能力

1. **纯词法、纯向量或 RepoMap**：没有 Target-specific 程序关系和领域生命周期；保留为检索组件。
2. **单独 Tree-sitter 结构图**：没有证据证明真实宏、CFG/dataflow 和函数指针；保留为低成本发现层。
3. **直接采用 GitNexus**：许可证限制、C/C++ import 缺口和效果证据不足；保留安全边界与多尺度导航参考。
4. **CodeQL 作为默认开放核心**：查询库值得学习，但引擎/CLI 许可与开放再分发目标存在边界；保留 oracle/参考角色。
5. **LLM/embedding 直接生成确定性事实**：近期 Wiki、Skill 和 memory 证据均显示错误或不相关知识可能造成负收益；只能生成候选。
6. **任何不绑定 Target/revision/file:line 的图**：不满足 WiFiDemo 的基本正确性要求。

### 8.2 进入 Benchmark 的三个架构族

| 架构族 | 代码事实核心 | 导航与深分析 | 领域链接 | 主要风险 |
|---|---|---|---|---|
| L1 编译器原生分层 | Target registry + compdb + Clang AST/SCIP/Kythe identity | LLVM/SVF/PhASAR/Frama-C 按需；词法/结构摘要辅助 | 独立 assertion layer + Wiki/Skill | 自建查询层多；AST/IR/identity 跨层连接与运维成本 |
| L2 Target-specific CPG 分层 | 每 Target/revision 独立 Joern 或 Fraunhofer CPG | CPG query/slice，缺口由 deep provider 补 | 同一独立 assertion layer；不把领域边混入确定性 CPG | frontend 对宏、compdb、函数指针和共享源码 occurrence 未验证 |
| L3 轻量发现 + 编译器核验 | Codebase-Memory/CodeGraph 只作 discovery，compiler/indexer 作强事实核验 | 命中后调用 compiler/deep provider | assertion layer 保存核验状态与生命周期 | 双系统一致性、核验延迟和维护复杂度可能抵消成本收益 |

三者均满足“设计上可容纳”硬门槛，但尚未“实验上通过”硬门槛。L2 不等于选择 Joern；Joern 与 Fraunhofer CPG 是可替换候选。L1 也不是“只用 Clang”；它需要 identity、查询和领域层。L3 只有在核验闭环可靠时才成立。

### 8.3 开源优先规则

优先 Apache-2.0、MIT、BSD 等可离线复现和可组合实现；LGPL/AGPL、非商业许可证、专有分析引擎和模型权重分别审计。只有当硬门槛、任务效果、资源和维护证据无决定性差异时，才以更开放的许可证、更低替换成本和更强可复现性作最终 tie-break。此规则不把许可证便利写成技术性能。

## 9. 后续 Benchmark 设计

详细的 15 项 backlog 见 [benchmark-backlog](docs/research/benchmark-backlog.md)。主线包括：四 Target occurrence、宏分支、直接调用、ops 间接调用、Host/Device Event、稳定身份、日志/混合检索、领域链接、失效修复和 Agent 端到端任务；跨仓验证使用固定版本的 [Zephyr 4.4.0](https://github.com/zephyrproject-rtos/zephyr/releases/tag/v4.4.0)、[RIOT 2026.04.01](https://github.com/RIOT-OS/RIOT/releases/tag/2026.04.01) 与 [Contiki-NG 5.1](https://github.com/contiki-ng/contiki-ng/releases/tag/release%2Fv5.1)。

实验按四阶段进行：先构造 compiler/build ground truth 并淘汰硬门槛失败的完整方案；再测代码—领域链接、abstention 和 invalidation；随后测最终 Agent 正确率、检索效率和资源；最后做许可证与冷机复现。固定 commit、Target、工具链、模型、prompt、Token、工具、预处理和硬件；每个强结论都配置反事实 patch。

## 10. 有效性威胁

- **当前没有候选工具的 WiFiDemo 实验**：本文只能排除结构上不满足要求的完整方案，不能声称某工具在 WiFi 上效果最好。
- **近期材料快速变化**：多个 Agent/代码图项目在论文与当前 README 间已有能力漂移，后续实验必须固定版本。
- **第一方与独立证据不对称**：代码图的效率数字多为第一方，独立研究主要评估通用检索，不直接覆盖 C 宏和 Target。
- **外部案例差异**：Zephyr、RIOT、Contiki-NG 与 WiFiDemo 结构相邻但不是同一产品；跨仓结果需要按构建系统和任务类型分层。
- **Ground truth 不完美**：compiler artifact 能证明编译存在性，却不能自动证明领域含义；Event/Feature 链接仍需规则、运行证据或人工复核。
- **许可证可能按组件改变**：仓库主许可证不能替代依赖、模型、数据和再分发路径审计。

## 11. 结论

对多 Target WiFi MAC C 驱动，最合理的当前研究结论是一个边界，而不是一个产品名：编译事实必须 Target-aware，程序关系必须由与问题匹配的语义分析产生，代码—领域链接必须是带 provenance 和生命周期的 assertion，Agent 上下文必须按需检索并回到当前源码核验。

成熟方案已足以把范围缩小到 L1、L2、L3 三个架构族，并明确排除纯检索、单独轻量图、许可证不合适的直接采用、以及无来源的 LLM 事实写入。当前证据仍不足以确定唯一方案。下一阶段以 WiFiDemo 为主、三个结构相邻 C 仓为补充，使用事实准确性、检索效率、最终 Agent 正确性和反事实敏感性进行分层实验；若结果接近，再按开源、离线、可维护和可复现性做 tie-break。
