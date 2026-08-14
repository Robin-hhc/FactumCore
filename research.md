# 面向多 Target WiFi MAC 驱动的代码知识架构：从独立证据到两类主骨架与查询模式

版本：2026-08-14

## 摘要

本文研究一个限定问题：对多芯片、多 Target、Host/Device 分离、宏与函数指针密集的 C WiFi MAC 驱动，怎样为 Agent 组织可核验的代码事实、领域原始来源和按需查询能力。研究不沿用 FactumCore 的既有实现，不预设图数据库、MCP、向量库或某一程序分析产品，也不把本轮未运行的候选实验写成结果。

本文先独立考察四条研究线：代码导航与检索、语义程序分析、代码—领域知识链接、领域知识与 Agent 上下文。跨线综合得到八层参考骨架，并把代码事实流与领域来源流限定为只在共同断言层连接。由程序事实主干和查询拓扑两个主决策推出两类完整骨架：A Agent 原生的联邦语义服务骨架与 B Target-specific CPG 主骨架；再由是否增加轻量发现后核验，得到 A0、A1、B0、B1 四个待测变体。共同断言层统一使用 EXTRACTED、RULE_DERIVED、INFERRED_CANDIDATE、CURATED 四种机器权限，代码版本使用 repository_revision，领域来源版本使用 source_revision_id，Host/Device 通过 Event/Message 而非跨二进制 CALLS 连接。

当前结论只把范围缩小到两个主骨架与两种查询模式，尚未确定唯一赢家。四变体都在架构上容纳 WiFiDemo W01–W08，但本轮没有候选工具的 WiFiDemo 实验，实际正确性、Agent 效果、资源、许可与运维均须由 B01–B15 Benchmark 裁决。

## 1. 研究问题与贡献

本文回答六个问题：

1. Agent 如何低成本找到相关代码，同时不把检索相似度升级为程序事实？
2. Target 编译视角、直接/间接调用、CFG、dataflow 与 slice 应由什么程序分析产生？
3. Feature、Flow、Event、Protocol Rule 和 Known Edge Case 如何与当前代码双向链接？
4. 代码版本与领域资料版本如何分别治理 provenance、冲突、失效和重新验证？
5. 哪些项目只提供组件或接口证据，哪些能力可以组成完整架构？
6. 在未运行候选实验时，怎样形成可证伪的 A0/A1/B0/B1 比较，而不是提前宣布产品赢家？

本文的贡献是完整推导链，而不是静态工具排行榜：原始来源登记见 [source-ledger](docs/research/source-ledger.md)，逐项目档案见 [solution inventory](docs/research/solution-inventory.md)，WiFiDemo 结构证据见 [workload casebook](docs/research/wifidemo-workload-casebook.md)，共同链接合同见 [linkage study](docs/research/code-domain-linkage.md)，候选状态见 [evidence matrix](docs/research/evidence-matrix.md)，未来实验见 [benchmark backlog](docs/research/benchmark-backlog.md)。

## 2. 方法与证据边界

### 2.1 范围、时间窗口与纳入规则

检索截止到 2026-08-14。快速变化的 Agent、Wiki、Skill 与 memory 优先采用 2026 年材料；Clang/LLVM、SCIP、Kythe、CodeQL、Joern、Fraunhofer CPG、SVF、Frama-C、PhASAR 与 Semgrep 使用当前官方材料；CPG 定义和 provenance 标准可使用仍有效的经典论文或规范。搜索摘要、营销星数与二手综述只用于发现，不作为正文证据。

来源只接受论文/公开 Benchmark、AI 公司技术文章、开源项目官方材料和标准。项目第一方数字可以引用，但必须紧邻样本、任务、对照与限制。架构推断是本文基于登记证据形成的综合结论，不伪装成来源直接证明。

未来外部案例不要求与 WiFi 产品同域；只要是结构相邻的 C/C++ 项目，能固定 revision、构造编译 ground truth、登记许可证并映射 Target/宏/回调/事件结构，即可进入候选案例集。当前固定的 Zephyr、RIOT 与 Contiki-NG 只用于补充结构多样性，不替代 WiFiDemo。

### 2.2 结论状态、Agent evidence 与来源性质

候选结论只使用四个状态：

- **supported by evidence**：登记证据直接支持该限定范围内的陈述；
- **architecturally accommodated**：架构给出了承载层、接口、事实权限和失效边界，但尚未证明 WiFiDemo 效果；
- **unknown / benchmark required**：证据不足，必须实验裁决；
- **not satisfied**：当前设计未满足该能力或硬门槛。

Agent evidence、证据生产者关系和审阅状态是三个可组合字段，不能压成一个“证据等级”：

| 字段 | 允许标签 | 含义 |
|---|---|---|
| Agent evidence | A / B / C / D | A 为受控实验；B 为正式工作流或真实案例；C 为社区包装；D 为仅有接口、理论上可接入 |
| Producer relation | independent / author first-party / project first-party / company first-party | 描述结果生产者与被评估方法、项目或公司的关系；一个聚合项目行可按来源分别列多个标签 |
| Review status | peer-reviewed / preprint / project self-test / official docs / company technical report | 描述发布与审阅形态，不推断生产者独立性，也不推断 Agent 实验强弱 |

例如 A + project first-party + preprint 仍不是独立复现，B + author first-party + peer-reviewed 也仍不是受控对照。若一行同时引用产品和开放协议，必须像 `Sourcegraph MCP: company first-party/official docs；SCIP: project first-party/official docs` 一样逐项注明，不能用模糊的混合标签。MCP 可调用、协议开放或产品页面有功能，只证明接口或组件存在，不自动证明 Agent 效果。后文的架构 A/B 是程序事实主干名称，与这里的 Agent evidence A–D 是不同命名空间。

### 2.3 数字解释规则

数字按三类分别报告，不能折叠为一个总分：

1. 事实准确性：precision、recall、F1、source-location accuracy、Target leakage、calibration/abstention；
2. 检索效率：Recall@k、MRR、context yield、Token、工具调用、索引/查询时延与资源；
3. 最终 Agent 正确性：答案或补丁通过率、证据完整率、错误引用率与 counterfactual sensitivity。

一个较快但串 Target 的系统仍是硬失败；一个召回 gold file 但最终没有使用正确证据的 Agent 也不能算正确。所有后文数字都保留其来源性质和样本语境。

## 3. WiFiDemo 工作负载与硬门槛

本轮只读取已登记的代码结构案例，没有运行任何候选工具，也没有新增本地测量。W01–W08 的完整源码位置与反例见 [WiFiDemo workload casebook](docs/research/wifidemo-workload-casebook.md)。

| 案例 | 已登记的结构事实 | 架构必须表达 |
|---|---|---|
| W01 Host 共代码 | 一个 Host Target 同时编译 chip2/chip8 实现，运行时选择 ops | Source Entity、Target occurrence 与运行时候选分离 |
| W02 Device 互斥源码 | Device 按 CHIP_TYPE 选择宏文件与互斥源码集合 | 编译输入、宏和 occurrence 必须绑定 Target |
| W03 Host 专用宏 | HOST_TX_OFFLOAD 只在 chip8 Host 生效 | 同一源码在不同 Target 下具有不同有效实体/边 |
| W04 跨模块条件路径 | 同一宏同时改变 HCC 与 HMAC 路径 | Target-local call/CFG 与条件源码证据 |
| W05 ops/规格表 | 函数指针表与规格表按运行时 chip_type 选择 | may-target、赋值来源、条件、候选集与 abstention |
| W06 Host/Device Event | 两侧独立编译，通过消息结构、发送、注册与分发连接 | Event/Message、Side、Target 和分段证据，不造跨二进制 CALLS |
| W07 共享源码身份 | 同一 hcc_core.c 参与两个 Host Target但边不同 | Source identity 与 Target occurrence 分开 |
| W08 同名函数/日志 | 两个芯片目录有同名函数与相同日志 | 候选消歧、Target presence、源码位置，不能自动选一项 |

由此得到三个完整方案硬门槛：

1. **Target-specific compilation view**：repository、repository_revision、Target/build profile、编译命令、宏/include、生成物与 source occurrence 可表达；
2. **可定位源码证据**：代码事实能回到 repository_revision、Target、file:line、生成器和输入 digest，领域声明能回到 source_revision_id 与原始 locator；
3. **不确定性治理**：确定性抽取、规则派生、模型候选和人工知识分权，并支持 provenance、冲突、stale/invalid 与重新验证。

## 4. 四条独立调研主线

### 4.1 代码导航与检索

独立研究首先否定“单一检索器普遍最优”。Agent Retrieval Bench 在 427 个样本、25 个仓库、308 个冻结快照上比较词法、RepoMap、embedding 与 Agent 轨迹：不同方法分别赢得 MRR、Recall@20 和 8K Token context yield，记录的 Agent 轨迹仍在 27%–35% 样本中漏掉全部 gold file；这些数字只测文件检索，不测程序语义或 WiFi Target 正确性。[[S001](https://arxiv.org/abs/2607.24882)]

CORE-Bench 使用超过 180,000 个查询和 106,000 个 broader-context 标注，显示传统代码搜索中的 embedding 表现不能直接外推到 issue-to-edit 与 broader-context 任务；其通用开源样本也不证明 C 宏和领域链接。[[S002](https://arxiv.org/abs/2606.11864)] ContextBench 在 1,136 个任务、66 个仓库、8 种语言、4 个模型和 5 个 Agent 上进一步区分 explored 与 utilized context：Agent 倾向提高 recall 而牺牲 precision，复杂 scaffold 的增益有限；这仍是 issue-resolution 证据，不是 WiFi 实验。[[S003](https://arxiv.org/abs/2602.05892)]

工程项目给出互补接口形状。Aider RepoMap 用符号摘要、文件关系和 Token 预算组织上下文，但不提供 C 编译语义。[[S004](https://aider.chat/docs/repomap.html)] Codebase-Memory 的第一方论文在 31 仓报告 83% answer quality，对照逐文件探索为 92%，同时约少 10 倍 Token、少 2.1 倍工具调用；当前 README 又声明 15 个 MCP 工具和增强的 C/C++ 解析，但论文快照、当前实现和 WiFiDemo 之间都存在范围差。[[S005](https://arxiv.org/abs/2603.27277)] [[S006](https://github.com/DeusData/codebase-memory-mcp/blob/main/README.md)]

CodeGraph 的第一方实验只有 7 仓、7 语言、每臂 4 次，报告工具调用、时间、处理 Token、成本分别减少 88%、53%、62%、44%，但会话末残留上下文约增加 80%；这些是架构问答探索成本，不是调用边 precision。[[S007](https://github.com/colbymchenry/codegraph)] GitNexus 的只读 MCP、allowlist、响应预算和多尺度导航值得借鉴，但 PolyForm Noncommercial 许可及公开 C/C++ import 缺口阻止其直接成为当前采用候选。[[S008](https://github.com/nxpatterns/gitnexus)]

Serena 通过 LSP/clangd 类后端向 Agent 提供 symbol、declaration 与 reference 高层操作；官方约 20 项日常任务属于项目第一方自评，没有固定样本总数、准确率或成本统计，且 MCP/LSP 不证明真实宏、Target occurrence 或函数指针正确。[[S037](https://github.com/oraios/serena)] Sourcegraph MCP 暴露跨仓 search/read/definition/reference/diff/history，SCIP 提供开放的 definition/reference/implementation 索引交换；公开材料没有可用于本研究排序的 Agent 正确率，Sourcegraph 产品边界也不能与开放 SCIP 协议混写。[[S038](https://sourcegraph.com/mcp)] [[S038/SCIP](https://github.com/sourcegraph/scip)]

因此导航层保留词法、向量、RepoMap、语义索引和轻量结构发现，但它们只能产生候选、排序、摘要或可定位引用，不能单独写入 CALLS、CFG、dataflow、implements_feature 或 Target active-branch 事实。

### 4.2 语义程序表示与深度程序分析

深分析必须按问题拆开：

| 职责 | 已登记路线与直接证据 | 能提供什么 | 不能自动证明什么 |
|---|---|---|---|
| 编译输入、AST/IR | Clang compilation database、LibTooling 与 LLVM IR [[S010](https://clang.llvm.org/docs/JSONCompilationDatabase.html)] | 一文件多编译命令、AST location、CFG/SSA/alias 底座 | 跨 Target 统一身份、领域含义、现成 Agent 服务 |
| occurrence/xref | scip-clang/SCIP [[S011](https://github.com/sourcegraph/scip-clang)]；Kythe compilation unit/schema [[S012](https://kythe.io/docs/kythe-compilation-database.html)] | 可定位 symbol/occurrence/reference；Kythe 原生 target/revision 字段 | CFG、taint、slice；WiFi 四 Target 抽取效果 |
| 可查询代码数据库 | CodeQL C/C++ query/dataflow [[S013](https://github.com/github/codeql)] | 声明式 query、CFG/dataflow/taint、path explanation | 开放 engine；对闭源自动化使用的许可自由；领域治理 |
| 联合图表示 | 经典 CPG 定义 [[S014](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf)]；Joern [[S015](https://github.com/joernio/joern)]；Fraunhofer CPG [[S016](https://fraunhofer-aisec.github.io/cpg/)] | AST/CFG/数据依赖的联合查询，overlay/slice/扩展 pass | frontend、宏、alias、external semantics 与 Target 正确性 |
| 专门分析 provider | SVF [[S017](https://github.com/SVF-tools/SVF)]；Frama-C/Eva/Slicing [[S018](https://frama-c.com/)]；Semgrep CE [[S019](https://github.com/semgrep/semgrep)]；PhASAR [[S020](https://github.com/secure-software-engineering/phasar)] | points-to/value-flow、抽象解释、slice、规则检查或 IFDS/IDE | 通用 Agent 导航、领域 KB；全部预计算的成本合理性 |

CPG 是表示和查询组织方式，不是精度来源。函数指针、dataflow 与 slice 的质量来自 frontend、真实构建输入、alias/points-to 算法、外部函数摘要与预算；把边放进图不会自动提高正确性。经典 CPG 论文证明联合表示的研究价值，当前 Joern/Fraunhofer 材料证明实现能力，但都没有证明 WiFiDemo 四 Target、真实宏和 ops 表效果。[[S014](https://ieeexplore.ieee.org/document/6956589)] [[S015](https://docs.joern.io/code-property-graph/)] [[S016](https://fraunhofer-aisec.github.io/cpg/CPG/impl/language/)]

Agent 包装同样不能改变底层事实范围。codebadger 把既有 Joern CPG 封装成高层 MCP 程序分析操作，论文只报告 GGML、libtiff、libxml2 三个作者案例，其中 8,000 是首个案例的方法规模，不是 aggregate accuracy；它没有覆盖多 Target 宏、Host/Device 或领域问答。[[S039](https://arxiv.org/abs/2603.24837)] QLCoder 在 176 个 CVE、111 个 Java 项目上，以“漏洞版本检出且修复版本不检出”为正确条件，作者评估报告 53.4% 正确查询，对照 Claude Code 为 10%；其价值是受约束 DSL、LSP 语法反馈、检索和延迟完整执行闭环，不能外推为 WiFi C 理解精度，也不解除 CodeQL 许可边界。[[S040](https://arxiv.org/abs/2511.08462)]

### 4.3 代码与领域知识链接

Graphify 把代码、文档、ADR/RFC 放入 typed graph，并在项目术语中区分 EXTRACTED、INFERRED、AMBIGUOUS；公开设计适合借鉴边来源和双向 path/explain，但 Tree-sitter/LLM 混合结果缺少 WiFi 所需的 Target occurrence、代码 revision 与完整 assertion lifecycle。[[S021](https://github.com/Graphify-Labs/graphify)]

Understand Anything 明确分离确定性结构与 LLM 生成的 architecture/process/domain/claim/source 资产；这支持“生成知识不污染代码事实层”，但官方材料没有代码—领域链接 precision、Target isolation、stale repair 或独立 Agent Benchmark。[[S009](https://github.com/Egonex-AI/Understand-Anything/blob/main/README.md)]

稳定工件、provenance 和静态结果交换已有可借鉴标准：SWHID 为内容、目录、revision 提供 intrinsic ID，PROV-O 区分 Entity/Activity/Agent、derivation/revision/invalidation，SARIF 保存扫描 revision、源码 location 与 fingerprint；它们提供词汇，不单独解决符号重命名、多 Target occurrence 或 WiFi ontology。[[S029/SWHID](https://www.swhid.org/specification/v1.2/0.Introduction/)] [[S029/PROV-O](https://www.w3.org/TR/prov-o/)] [[S029/SARIF](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html)]

独立调研因此不把“代码与文档在同一数据库”当作已链接。可靠链接必须是一等 typed assertion：两端有稳定身份，边有 producer、方法版本、作用域、证据、权限和生命周期，并能从代码反查领域，也能从领域返回当前 Target 下的代码。

### 4.4 领域知识、Wiki、Skill 与 memory

LLM-Wiki 的作者实验在 HotpotQA、MuSiQue、2WikiMultiHopQA 三组各前 500 个样本和 AuthTrace 上统一使用 GLM-5.1；它显示多文档综合收益，但 AuthTrace 单文档问题比 HippoRAG 2 低 2.3 accuracy points，这不是代码任务结论。[[S022](https://arxiv.org/abs/2605.25480)] WiCER 的作者实验覆盖 17 个 RepLiQA 领域、每种条件合计 6,800 个问题，另有 30 篇 Policygenius 文章；blind Wiki compilation 的 catastrophic rate 为 53%–60%，1–2 次 refinement 恢复约 80% 丢失质量，而 80 文档时 full-context 还因 attention dilution 低于 RAG。评估依赖 LLM-as-judge，且不存在代码实体、Target 或编译语义。[[S023](https://arxiv.org/abs/2605.07068)] 这些数字说明 Wiki 是可评估、有损、可重编译的派生资产，而不是原始真源。

Google ADK 与 AWS Agent Toolkit 展示 metadata → instructions → references/tools 的 progressive disclosure；Google 的约 90% baseline context reduction 是 10-Skill 示例算术，不是正确率实验。[[S024/Google](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/)] [[S024/AWS](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/skills.html)] GitHub Copilot Memory 的第一方 A/B 报告 PR merge 90% 对 83%、review positive feedback 77% 对 75%、p<0.00001，但没有公开样本量与任务构成；可借鉴的是 citation、scope、删除和读时核验，不是产品效果外推。[[S025](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/)]

领域上下文的收益具有任务条件。SWE-Bench 5G 的 50 项 paired A/B 中，平均约 350-token 的 3GPP context 使 Claude Sonnet 4 resolve 从 24% 到 30%，Token 平均增加 12%；规格依赖类提升，六类 generic nil/crash 防御任务均无提升。[[S026](https://arxiv.org/abs/2604.26278)] SWE-Skills-Bench 约 565 项任务中，39/49 Skills 没有 pass-rate 提升，平均仅 +1.2%；三个版本不匹配 Skill 最多降低 10%，结果不变时 Token 最高增加 451%。[[S027](https://arxiv.org/abs/2603.15401)]

RepoMem 的同行评审作者实验包含 SWE-bench Verified 500 项/12 个 Python 仓和 SWE-bench Live 子集 130 项/62 个仓，以 LocAgent 为主要对照：Verified Acc@5 为 76.5% 对 71.6%，下游 resolve 为 40.4% 对 37.0%，Live Acc@5 为 66.2% 对 63.1%；但历史稀疏的 `others` 分组从 67.4% 降到 54.3%，即下降 13.1 points。它测的是 Python bug localization，固定最多 7,000 commits/200 files，不能外推到新仓、C 语义或领域事实；历史只能用于定位，必须回到当前代码核验。[[S028](https://openreview.net/pdf?id=8yjWLJy2eX)] Codified Context 在一个 108,000 行 C# 系统、283 sessions 上展示 hot conventions、domain agents 与按需规格三层工作流，但没有随机对照，规模数字不是因果收益。[[S030](https://arxiv.org/abs/2602.20478)]

因此 Wiki、Skill 与 memory 都必须保留 raw source、版本、适用性与 abstain/not-applicable；它们不能替代当前代码分析或原始领域来源。

## 5. 跨主线的共同规律与待验证设计原则

四条独立调研线支持四条共同规律，并提出一条必须由 B10 验证的设计原则：

1. **确定性入口**：Agent 先从词法、LSP、编译索引、AST/CPG 等可定位结构或语义工具进入代码；生成摘要只作导航。独立检索证据和现有工具都支持多入口而非单一检索器。[[S001](https://agent-retrieval-bench.github.io/)] [[S010](https://clang.llvm.org/docs/LibTooling.html)]
2. **低成本发现与高成本核验分工**：词法、向量、RepoMap、轻量结构图缩小候选，Target-local compiler/CPG/deep provider 承担强事实核验；是否值得增加独立发现层仍需比较净收益。[[S005](https://arxiv.org/abs/2603.27277)] [[S017](https://svf-tools.github.io/SVF/)]
3. **source-grounded 与 progressive disclosure**：结果应携带源码或原始资料位置、revision、Target 和生成器；Agent 按 metadata、摘要、证据、源码/深分析逐步展开。[[S024](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/)] [[S029](https://www.w3.org/TR/prov-o/)]
4. **派生知识不替代真源**：Wiki、Skill、memory、embedding 与 LLM 关系都可能过时或负迁移，必须回到当前代码和原始领域来源核验。[[S022](https://arxiv.org/abs/2605.25480)] [[S023](https://arxiv.org/abs/2605.07068)] [[S027](https://github.com/GeniusHTX/SWE-Skills-Bench)] [[S028](https://www.microsoft.com/en-us/research/publication/improving-code-localization-with-repository-memory/)]

**待验证设计原则，而非共同规律**：高层任务工具可能降低 Agent 的工具选择与查询构造负担。Serena 只有约 20 项项目第一方自评，codebadger 只有三个作者案例，QLCoder 的受控对照限定在 Java/CVE/CodeQL；这些来源支持 symbol navigation、trace_event、verify_candidate 或受约束 DSL + 执行反馈作为可测接口形状，不支持“跨任务普遍优于原始 DSL”。B10 必须在同一预算下比较工具选择正确率、无效调用、DSL fallback、truncation、最终答案正确率与成本；验证前 raw DSL 只是有审计的回退假设。[[S037](https://oraios.github.io/serena/04-evaluation/000_evaluation-intro.html)] [[S039](https://github.com/lekssays/codebadger)] [[S040](https://github.com/neuralprogram/qlcoder)]

## 6. 关键差异：只比较真正改变架构的轴

成熟项目覆盖的层不同，但只有下列差异会改变知识架构：

| 差异轴 | 要回答的问题 | 不能混入的替代分类 |
|---|---|---|
| 程序事实主干 | 以 occurrence/identity/index 和可替换 provider 为中心，还是以 Target-local CPG 作为常用事实主干？ | 数据库品牌、图可视化 |
| 查询拓扑 | Agent 直接查询主骨架，还是先经独立轻量发现再到主骨架核验？ | “是否有搜索框”、是否叫 hybrid |
| 分析时机 | ingest 时物化哪些稳定事实，query 时再运行哪些昂贵 points-to/dataflow/slice？ | 把所有分析器堆成产品清单 |
| 断言层物理组织 | 代码事实、领域来源、软候选和验证记录同库分区还是分库存储？ | 同库不等于同一事实权限 |

MCP 是交付协议，向量是候选召回机制，可视化是阅读界面，SQLite/图数据库/文件是物理实现。它们可以出现在任一架构中，不能与程序事实主干处于同级分类；MCP 存在也不等于 Agent 效果成立。

## 7. 八层参考骨架与端到端数据流

### 7.1 八层职责

| 层 | 输入 | 产出与事实权限 | 代表证据 |
|---|---|---|---|
| 1 输入与快照 | 仓库、repository_revision、Target Profile、构建命令、生成物 | 可复现 snapshot 与 digest；只确认捕获到的输入/工件 | Clang compdb [[S010](https://clang.llvm.org/docs/JSONCompilationDatabase.html)]、SWHID/SARIF [[S029](https://www.swhid.org/specification/v1.2/0.Introduction/)] |
| 2 身份与基础索引 | snapshot、TU、源码 span | Target-qualified occurrence、symbol/reference、source identity；不确认深层关系 | SCIP [[S011](https://github.com/scip-code/scip)]、Kythe [[S012](https://kythe.io/docs/schema-overview.html)] |
| 3 语义分析提供者 | Target-local AST/IR/index/CPG 与配置 | call、may-call、CFG、dataflow、slice；只在生成器输入范围内成立 | Joern/Fraunhofer [[S015](https://docs.joern.io/cpg-slicing/)] [[S016](https://fraunhofer-aisec.github.io/cpg/GettingStarted/query/)]、deep providers |
| 4 领域原始来源 | 规范、设计文档、ADR、issue、commit、test、log | 不可静默覆盖的原文；只证明来源自身内容 | raw source、source archive、项目资料 |
| 5 版本化来源注册 | 领域原始来源 | source ID、source_revision_id、locator、license、accessed_at；不生成代码关系 | PROV-O/SARIF 模式 [[S029](https://www.w3.org/TR/prov-o/)] |
| 6 断言与链接 | 代码事实、来源、规则、模型候选、人工审核 | typed assertion、四种机器权限、冲突与生命周期 | Graphify/claim-source 参考 [[S021](https://graphify.com/concepts)]、共同合同 |
| 7 查询编排与证据装配 | 索引、分析、断言、预算和问题 | 有范围 evidence bundle、截断、拒答、核验与 fallback；不得新造事实 | Serena、Sourcegraph、codebadger、QLCoder |
| 8 Agent 交付 | evidence bundle 与任务约束 | 有引用答案、审阅建议或受控分析请求；无证据时明确 unknown | Agent evidence 协议与 B10 |

### 7.2 两条事实流只在断言层连接

代码事实流为：输入与快照 → 身份/基础索引 → Target-local 语义分析 → 断言与链接 → 查询编排 → Agent。领域来源流为：原始规范/设计/历史 → 版本化来源注册 → 断言与链接 → 查询编排 → Agent。

两条流只在第 6 层通过 typed assertion 连接：parser/analyzer 不替领域资料解释含义，Wiki/LLM 也不反向改写编译事实。第 6 层物理上可以与程序图同库、与来源注册同库或独立部署；同库/分库是实现选择，不改变四种事实权限和版本边界。

## 8. 项目角色与 Agent 证据地图

下表同时记录 Agent evidence、producer relation 与 review status；三列不可合并。“WiFi MAC 直接证据”只回答是否有当前任务的直接实验，不把通用 C/C++ 支持写成已通过。

| 项目 | 主责层 | Agent 方式 | Agent evidence | Producer relation | Review status | 可借鉴点 | WiFi MAC 直接证据 | 当前角色 |
|---|---|---|---|---|---|---|---|---|
| Serena [[S037](https://github.com/oraios/serena)] | 3、7、8 | LSP-backed 高层 MCP 符号导航 | B：约 20 项日常任务自评 | project first-party | project self-test + official docs | symbol/declaration/reference 小工具面 | 无；宏/Target/函数指针未测 | 两主骨架的导航/证据装配组件 |
| Sourcegraph MCP / SCIP [[S038](https://sourcegraph.com/mcp)] [[S038/SCIP](https://github.com/sourcegraph/scip)] | 2、7、8 | 跨仓 MCP + 开放索引协议 | D：接口可接入，无排序实验 | MCP: company first-party；SCIP: project first-party | MCP: official docs；SCIP: official docs | search/read/xref 与索引交换分层 | 无；产品与 SCIP 开放性须分开 | SCIP 为 identity 候选，MCP 为检索接口候选 |
| Codebase-Memory [[S005](https://arxiv.org/abs/2603.27277)] [[S006](https://github.com/DeusData/codebase-memory-mcp/blob/main/README.md)] | 2、7 | 持久轻量图 + 15 MCP 工具 | A：31 仓第一方受控对照 | author first-party + project first-party | preprint + official docs | 低成本结构发现、增量、coverage 自检 | 无；31 仓实验非 WiFi/Target | 模式 1 的 discovery 候选 |
| CodeGraph [[S007](https://github.com/colbymchenry/codegraph)] | 2、7 | SQLite/FTS5 增量图 + MCP/CLI | A：7 仓、每臂 4 次第一方实验 | project first-party | project self-test + official docs | entry/trace/impact 与成本观测 | 无；coverage 不是调用精度 | 模式 1 的 discovery 候选 |
| Joern / codebadger [[S015](https://github.com/joernio/joern)] [[S039](https://arxiv.org/abs/2603.24837)] | 3、7、8 | Target CPG + 高层 MCP 分析操作 | B：三个作者案例 | Joern: project first-party；codebadger: author first-party | Joern: official docs；codebadger: preprint | 受控 slice/taint/data-dependency 工具 | 无；三案例不含多 Target/Host-Device | B 的 CPG 候选；A 的非权威 supplemental provider 候选 |
| CodeQL / QLCoder [[S013](https://github.com/github/codeql)] [[S040](https://arxiv.org/abs/2511.08462)] | 3、7、8 | 受约束 QL 合成 + LSP/执行反馈 | A：176 CVE/111 Java 项目作者对照 | CodeQL: company first-party；QLCoder: author first-party | CodeQL: official docs；QLCoder: preprint | 小工具箱、语法反馈、延迟完整执行 | 无；Java/CVE 不能外推 WiFi C | 方法学/oracle；不作默认开放核心 |
| Graphify [[S021](https://github.com/Graphify-Labs/graphify)] | 4、6、7 | Skill/CLI/MCP 查询混合图 | D：接口与第一方材料，无 WiFi Agent 实验 | project first-party | official docs | 边来源标签、文档节点、path/explain | 无；Target identity/lifecycle 不足 | 共同链接层设计参考 |
| Understand Anything [[S009](https://github.com/Egonex-AI/Understand-Anything/blob/main/README.md)] | 4、6、8 | 多 Agent 生成可读领域资产 | B：正式第一方工作流，无受控效果 | project first-party | official docs | structure/domain/claim/source 分层、可审阅产物 | 无；没有链接精度或失效实验 | 领域知识生成参考，不作代码真相 |

这张地图说明：项目可以覆盖多层，但接口层不能继承底层尚未证明的事实权限。尤其 codebadger 仍依赖已正确生成的 Joern CPG，QLCoder 仍依赖 CodeQL 数据库与许可，Serena/Sourcegraph 的 MCP/LSP 仍依赖其索引输入。

## 9. 共同代码—领域链接层

### 9.1 身份、版本与最短可靠链

共同实体至少包括 Repository、RepositoryRevision、SourceArtifact、TargetProfile、CodeEntity、TargetOccurrence、AnalysisFact、DomainEntity、SourceRevision、SourceLocation、SourceRegistration、Assertion、Evidence 与 ValidationActivity。

代码仓的不可变版本只能写入 repository_revision；规范、设计文档、issue、test、log 等领域来源以独立 source_revision_id 注册。两者不得复用。最短可靠链为：

DomainEntity → Assertion → TargetOccurrence(repository_revision + Target/build profile + semantic ID + source span) → AnalysisFact(generator + version + config) → Evidence(source_revision_id + locator 或代码 evidence path) → lifecycle。

裸函数名或裸 file-line 不能作为长期链接身份；file:line 适合读时核验，但必须结合创建时 revision、quoted digest、semantic/source anchor 和 Target occurrence。该身份与 provenance 设计分别借鉴 SCIP/Kythe/SWHID/PROV/SARIF，但不声称某个标准已解决全部问题。[[S011](https://github.com/scip-code/scip)] [[S012](https://kythe.io/docs/schema/writing-an-indexer.html)] [[S029](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html)]

### 9.2 四种机器权限

每条 edge 只有一种 machine_status；stale、contradicted、invalid、superseded 是 lifecycle_state，不是第五种权限。

| machine_status | 允许生产者 | 能否支持确定性回答 | 最小审计条件 | 变化后的动作 |
|---|---|---|---|---|
| EXTRACTED | compiler、parser、indexer、固定配置 analyzer | 可以，但只在输入范围内 | repository_revision、Target/profile、工具/配置、source span | 输入或生成器变化后 stale 并重建 |
| RULE_DERIVED | 登记且版本化的确定性规则 | 可以，必须返回 rule trace 与作用域 | rule ID/version、match trace、代码与 source_revision_id 证据 | 任一输入变化后 stale、重跑并保留差异 |
| INFERRED_CANDIDATE | Agent、LLM、embedding、聚类、未审核启发式 | 不可以；只作候选/排序/审核队列 | 方法/模型/prompt/input digest、候选 ID、证据缺口 | 模型/输入/阈值变化后批量作废重算 |
| CURATED | 授权人工领域维护者/审核者 | 可以，但不能伪装成编译事实 | reviewer/time/reason、原始 SourceRevision/Location、适用 Target/产品范围 | 依赖变化后 stale/contradicted/superseded，保留历史 |

Agent 只能创建 INFERRED_CANDIDATE，不能自行升级为其他三类；确定性工具也只能在其输入和生成器权限内写 EXTRACTED/RULE_DERIVED，不能替代领域审核。Graphify 的项目内标签只是来源项目事实，不覆盖本文四状态合同。[[S021](https://graphify.com/concepts)]

### 9.3 双向导航、冲突、失效与重验证

从代码到领域：给定 repository_revision、Target/build profile 和 TargetOccurrence，只返回作用域匹配且 active 的 EXTRACTED、RULE_DERIVED、CURATED assertion；候选单列。从领域到代码：给定 Feature/Event stable ID、当前 repository_revision 与 Target，只返回当前有效 occurrence 与原始来源/分析 trace；没有证据时明确返回“当前 Target 无有效代码证据”。

冲突不能用单一总排序：函数是否在 Target 中存在由当前 compiler/indexer fact 裁决；协议应如何工作由适用版本的权威规范裁决，代码不一致可能是 defect；设计原因由经审核 ADR/人工来源裁决；sound may-analysis 与 runtime observation 可以并存；历史 memory 只能让位于当前 revision 的验证结果。

source digest、compile-command/Target digest、symbol rename/move、analyzer config、source_revision_id、模型/prompt 或人工纠正变化时，分别触发依赖范围内的 stale、重建、重算或人工复核；不得 last-write-wins，也不物理删除历史 verdict。citation 读时核验、dependency invalidation 与 Wiki failure probe 是互补机制。[[S022](https://arxiv.org/html/2605.25480)] [[S023](https://arxiv.org/html/2605.07068)] [[S025](https://github.blog/changelog/2026-05-26-copilot-memory-has-more-controls-for-deletion-scope-and-the-copilot-cli/)]

### 9.4 Host/Device 通过 Event/Message 连接

Host producer 与 Device consumer 属于独立编译视角，不能制造跨二进制 CALLS。共同层建立 Event/Message 实体，分别链接 declared_at、produced_by、serialized/sent_by、channel/subtype、received/dispatched_by、registered_to、consumed_by 和 may_dispatch_to；每一段保留自己的 repository_revision、Target、Side、代码证据与机器权限。这样既可从 Event 导航两侧，也可从 handler 反查 Event/Side/Target，而不掩盖协议边界或多候选函数指针。

## 10. 决策轴如何推导候选

### 10.1 共同硬门槛先于胜负

A/B 都必须满足第 3 章三个硬门槛，并共享第 1、4–8 层合同。共同 assertion layer、source registry、snapshot consistency、许可证审计，以及 Agent evidence/producer relation/review status 三个证据字段不是 A/B 胜负项。

### 10.2 从四轴收敛为两个主骨架

| 决策轴 | 当前可裁决部分 | 对候选的推导 |
|---|---|---|
| 程序事实主干 | 权威 fact residence 位于 Target registry + 联邦语义 provider，还是位于每 Target CPG；两者必须有不同的最小预物化关系、默认路由与禁止越界条件 | 形成可归因的 A 与 B |
| 查询拓扑 | 直接查询与轻量发现后核验都可附着在任一主干 | 形成 0 与 1，不形成第三主骨架 |
| 分析时机 | 两族都应只物化稳定常用事实，把昂贵 deep analysis 按需调用；具体边界待测 | 作为 A/B 的配置与 B12/B14 指标 |
| 断言物理组织 | 同库或分库不改变事实权限、版本与生命周期 | 作为实现选择，不形成架构族 |

先前所谓“轻量发现 + 编译器核验”不再作为第三个程序事实主骨架：它没有定义强事实最终驻留于何处，只定义查询先由低成本组件生成候选，再回到主骨架核验。因此它被严格降为模式 1；词法、向量、RepoMap、Codebase-Memory、CodeGraph 都只能作为可替换 discovery/rerank 组件。

## 11. 两个完整主骨架

本节是基于前述证据的**架构推断**，不是任何单一来源的第一方结论，也不是 WiFiDemo 实测。

### 11.1 A — Agent 原生的联邦语义服务骨架

**数据流**：Target registry 冻结 repository_revision/Target/build profile 与 compilation input → compiler/LSP/SCIP/Kythe 类联邦服务建立 Target-qualified occurrence/reference 与各自语义事实 → federation planner 按所需事实路由权威 provider，必要时调用非权威 supplemental deep provider → 共同 assertion layer 连接 source_revision_id 领域来源 → 装配有界 evidence bundle → Agent。

**权威事实驻留与最小预物化集**：A 的权威 identity/fact residence 是 Target registry 加已登记的 compiler/LSP/SCIP/Kythe 等联邦服务，不是中央 CPG。必须预物化 `repository_revision → Target/build profile → compilation unit/compile command → TargetOccurrence`、`SourceEntity ↔ TargetOccurrence` 以及 definition/reference/source-span spine；AST、CFG、direct-call、may-call、dataflow 与 slice 由收到相应请求的权威 provider 在其命名空间返回，可缓存但不要求集中预构为统一图。

**默认路由与禁止越界不变量**：所有代码问题先解析 Target registry，再按事实类型路由 compiler/index/LSP/SCIP 或专门分析 provider，并保留 provider/config/snapshot lineage。若调用 CPG，它只能是非权威 supplemental provider 或可丢弃缓存；不得成为默认 identity spine、默认查询入口或跨 provider 事实的最终裁决者，也不得把 CPG 内部节点 ID 反写成 A 的全局权威 identity。跨 provider join 只能依据 registry identity 与显式证据，不能因名称相同自动合并。

**八层映射**：A 主责第 2 层 registry/identity/reference spine、第 3 层可替换权威 provider 与第 7 层 federation planner；第 1、4、5、6、8 层使用共同合同。

**优势**：按任务选择 provider、避免预物化所有深分析、组件可替换，高层工具直接面向 compare_targets、trace_event、verify_candidate 等任务。Clang/SCIP/Kythe 与深分析器的公开能力支持组件可组合性，但不证明组合后的效果。[[S010](https://clang.llvm.org/docs/LibASTMatchers.html)] [[S011](https://github.com/sourcegraph/scip-clang)] [[S012](https://github.com/kythe/kythe)]

**代价与失败方式**：跨 provider identity、snapshot 与语义对齐复杂；planner 可能选错工具、fan-out、重复核验或增加延迟；provider 可接入不等于函数指针、CFG/dataflow 或 Event 正确。若为降低成本而让 supplemental CPG 静默成为默认主干，则该实现已经越界，不再属于 A 实验臂。

**Agent 接口**：resolve_target_context、find_code_evidence、compare_targets、explain_relation、trace_event、get_assertions、verify_candidate、request_deep_analysis。每次输入范围、预算与证据类型，返回 provider、Target/revision、证据、截断和拒答。

**关键 unknown**：四 Target compilation input 能否完整驱动各 provider；identity join 与 tool selection 是否稳定；按需分析成本是否低于 B；当前状态为 **unknown / benchmark required**。

### 11.2 B — Target-specific CPG 主骨架

**数据流**：snapshot registry 按 repository_revision/Target 冻结输入 → 每 Target 导入真实 compilation input 并生成独立 CPG → CPG 作为该 Target 的权威 identity/relation spine → CPG 缺口由 compiler/LLVM/deep provider 验证或补充并保留 supplemental 标记 → 共同 assertion layer 连接领域来源 → scoped CPG gateway 装配 evidence bundle → Agent。

**权威事实驻留与最小预物化集**：B 的每 Target CPG 是权威 TargetOccurrence identity 与程序关系主干。每张图至少预物化 Target-qualified source occurrence/source span、AST、CFG、definition/reference 和 direct-call；函数指针 may-call、dataflow、slice 或 custom semantics 可作为有 producer/version/置信边界的 overlay，不能伪装成同权限基础事实。跨 CPG 只通过 registry 中 `SourceEntity ↔ TargetOccurrence` 显式 identity map 对齐，不产生无 Target 的统一关系边。

**默认路由与禁止越界不变量**：`resolve_target_context` 后的代码 identity、reference、AST、CFG 与 direct-call 查询默认进入指定 Target CPG。compiler artifact 负责验证 build/macro/source-set ground truth，LLVM/deep provider 负责核验或补缺；它们不能替代默认 CPG route，也不能在 CPG 外另建权威 identity spine。若查询默认先走 compiler/index federation、CPG 只作可选 provider，则该实现已经越界，不再属于 B 实验臂。

**八层映射**：B 主责第 2 层 Target occurrence/CPG import 与跨图 identity map、第 3 层 Target-local CPG/typed overlay 及第 7 层 scoped gateway；第 1、4、5、6、8 层使用共同合同。

**优势**：最低要求的 AST/reference/direct-call/CFG 位于统一可遍历表示，附加 overlay 可承载 dataflow/slice，多跳路径、裁剪和源码位置可通过集中查询面治理。Joern 与 Fraunhofer CPG 证明这些表示和 API 存在，codebadger 证明可用高层 Agent 操作封装，但三者均未证明 WiFi Target 正确性。[[S015](https://docs.joern.io/dataflow-semantics/)] [[S016](https://fraunhofer-aisec.github.io/cpg/CPG/specs/dfg-function-summaries/)] [[S039](https://github.com/lekssays/codebadger)]

**代价与失败方式**：C frontend 是否忠实消费真实宏/include/生成物未知；每 Target 分图的资源与跨图 identity 成本未知；overlay/custom semantics 可能混合推断与确定性事实；DSL/JVM 运维、traversal 扩张和结果截断可能影响 Agent。

**Agent 接口**：与 A 完全相同的高层合同，默认映射到指定 Target CPG；raw traversal 只在高层合同不能表达目标时作为有审计回退，不能把 DSL 暴露本身当效果。

**关键 unknown**：宏/occurrence/直接与间接边、dataflow、Event 候选路径的实际正确性；预构图成本是否由重复任务摊薄；当前状态为 **unknown / benchmark required**。

### 11.3 A/B 的唯一核心差异

A 与 B 都可以包含 Clang、SCIP、CPG、LLVM 组件，也都使用相同断言层和 Agent 合同；共享层不会抹平程序事实主干。A 的权威 identity/facts 分驻 Target registry 与 compiler/LSP/SCIP 等联邦服务，CPG 只能 supplemental；B 的权威 identity/relation spine 驻留于每 Target CPG，并强制预物化最低 AST/CFG/reference/direct-call 集。不得把 A 写成“只用 Clang”，不得把 B 等同于“选择 Joern 产品”，也不得用组件清单相同来宣称两臂相同。

**A0↔B0 可归因规则**：两臂固定同一 repository_revision、Target/build profile、Agent/model/prompt、任务、总预算、共同 assertion/source layer、高层接口、失败/截断策略和 gold；两者都不启用模式 1 discovery。唯一允许改变的是上述权威 fact residence、最低预物化集和默认路由。每个返回事实必须记录 actual route、authoritative/supplemental 标记与 provider lineage；A0 若默认落到 CPG identity/query spine，或 B0 若绕过 CPG 让 compiler/index federation 成为默认主干，该 run 标为 arm contamination，不能计入 A/B 因果比较。事实准确性先独立于最终 Agent 正确性报告，资源/延迟再单列，不能以共享层收益补偿主干硬失败。

## 12. 两种查询模式与 A0/A1/B0/B1

模式 0 不是“无检索”：它允许主骨架自身索引和有范围查询，只是不增加独立轻量 discovery 前置层。模式 1 的发现结果只能产生候选、排序或上下文压缩，强语义结论必须回主骨架核验。

| 变体 | 程序事实主干 | 查询路径 | 强事实核验点 | 成立条件 | 主要失败方式 | 当前状态 |
|---|---|---|---|---|---|---|
| A0 | A 联邦骨架 | Agent 高层接口经 Target registry 直接路由一个或多个权威 provider | 实际 compiler/LSP/SCIP/专门 provider + 同一 snapshot/Target；CPG 仅 supplemental | tool selection 与 provider join 正确且成本可接受 | 无效调用、fan-out、identity 错配、CPG 越权 | unknown / benchmark required |
| A1 | A 联邦骨架 | 词法/向量/RepoMap/轻量图先发现，再经 registry 调用 A provider | A 的 compiler/index/LSP/SCIP/专门 provider；CPG 仅 supplemental | Token/调用/延迟净收益大于漏召回、核验和一致性成本 | 漏 gold、错误 Target、核验抵消收益、stale discovery | unknown / benchmark required |
| B0 | B CPG 骨架 | 高层接口直接查询指定 Target CPG，缺口才调验证/补缺 provider | 权威 Target-specific CPG + 标记为 supplemental 的 compiler/LLVM/deep 结果 | CPG 查询可控，预物化成本可摊薄 | traversal 扩张、截断、frontend 错误、跨 Target 误查、绕过 CPG | unknown / benchmark required |
| B1 | B CPG 骨架 | 轻量组件定位文件/符号/子图，再进指定 Target CPG | 权威 Target-specific CPG + 标记为 supplemental 的 compiler/LLVM/deep 结果 | 净收益大于漏召回、核验与双索引一致性成本 | snapshot 不一致、候选裁剪破坏路径、双系统无净收益 | unknown / benchmark required |

模式 1 只有在 B07、B10、B14 同时显示检索、最终答案和全成本净收益时才成立；单独 Recall@k、单次 Token 或查询时延不能宣布胜出。

## 13. 统一 WiFiDemo 覆盖矩阵

下表比较的是设计是否有明确承载位置，不是工具效果。四变体都没有运行 WiFiDemo 候选实验，因此变体覆盖只可写为 architecturally accommodated，实测列一律为 unknown / benchmark required；本表没有任何 supported by evidence 单元格。

| WiFiDemo workload | A0 | A1 | B0 | B1 | 当前候选实测 |
|---|---|---|---|---|---|
| W01 Host 共代码/运行时选择 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W02 Device 互斥源码/宏 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W03 Target-specific Host 宏 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W04 条件编译改变跨模块路径 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W05 ops/函数指针与规格表 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W06 Host/Device Event/Message | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W07 Source identity/Target occurrence | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |
| W08 同名函数/日志消歧 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required |

主状态只表示设计有承载位置。下表把承载路径和 arm-specific 风险展开；它仍是架构推断，不是 `supported by evidence`：

| Workload | A 主骨架承载路径与特有风险 | B 主骨架承载路径与特有风险 | 模式 1 特有漏召回/一致性风险（A1/B1） |
|---|---|---|---|
| W01 Host 共代码/运行时选择 | Target registry 保存一个 Host Target 下 chip2/chip8 的 TargetOccurrence，compiler/reference 与按需 points-to provider 返回 ops 候选；跨 provider identity 或运行时条件被误写成唯一调用是 A 风险 | 指定 Host CPG 预存两实现的 AST/reference/direct-call spine，typed overlay 表达 ops initializer/may-target；traversal 把候选误收敛成唯一边是 B 风险 | 轻量层可能只召回一个芯片实现，或丢掉 ops initializer/运行时选择点 |
| W02 Device 互斥源码/宏 | Target registry 与 compiler/preprocessor provider 对每个 Device Target 权威记录 compile command、宏、active source set；provider snapshot 不一致会串 Target | 每个 Device Target CPG 只导入该 Target active source set，compiler artifact 校验 import；frontend 忽略真实宏/include 会污染整图 | stale discovery 可能返回互斥的 excluded source，或用另一 Target 的索引裁剪当前候选 |
| W03 Host 专用宏 | registry 绑定 chip8/chip2 Host profile，compiler provider 比较同一 SourceEntity 的两组 active occurrence/macro evidence；错误 build-profile 路由是特有风险 | 两张 Host CPG 分别保存宏作用后的 AST/CFG/reference，跨图比较 presence；CPG frontend 宏忠实度未知 | 源文件级去重可能隐藏 chip8-only occurrence，或把宏文本出现当两 Target 都 active |
| W04 跨模块条件路径 | registry 对齐 HCC/HMAC occurrence，再组合 compiler/CFG/direct-call provider；不同 provider 的 CFG/call 语义或 revision join 可能不一致 | 每 Target CPG 的最低 AST/CFG/direct-call 集承载路径，必要 overlay 补 dataflow；错误 import/overlay 会形成伪路径 | 文件/符号候选裁剪可能漏掉路径中间模块，使后续核验无从恢复完整链 |
| W05 ops/规格表 | registry/reference spine 定位 initializer 与候选函数，权威 compiler/points-to provider 解释 may-target；CPG 即使被调用也只 supplemental，主要风险是 alias/identity join 与 planner 选错 provider | Target CPG 权威保存 AST/reference/direct-call/initializer spine，points-to/may-call 以 typed overlay 补充；主要风险是 overlay 把候选集过度收敛或混合事实权限 | discovery 可能漏 initializer、规格表或一个候选函数；discovery 与 provider/CPG snapshot 不一致会改变候选集 |
| W06 Host/Device Event/Message | Host/Device provider 只返回各自二进制内关系，共同 assertion layer 以 Event/Message 串联；跨 provider join 不能制造 CALLS，事件字段映射错误是 A 风险 | Host 与 Device 各在其 Target CPG 内保存发送/注册/分发段，共同层用 Event/Message 做跨 CPG 链接；跨图 event identity 错配是 B 风险 | 轻量层可能漏消息结构、发送点、注册点或 handler 中任一段，或在两侧使用不同 revision |
| W07 共享源码身份 | registry/SCIP identity spine 把一个 SourceEntity 映射到两个 Host TargetOccurrence，关系仍由各权威 provider Target-local 返回；identity join 错误会合并两套边 | 两张权威 Target CPG 通过 registry 的显式 cross-CPG `SourceEntity ↔ TargetOccurrence` map 对齐，CPG 内关系不跨 Target；cross-CPG identity 漏接或误接是特有风险 | 轻量去重可能把两个 occurrence 合并成一个上下文，或 stale identity index 返回错误 Target 的边 |
| W08 同名函数/日志消歧 | registry 以 Target、path、semantic identity 返回完整候选集，provider 不可仅按 name/log 选唯一项；主要风险是错误 identity join | 指定 Target CPG 以 path/source span/Target 区分同名节点并返回候选；非限定 traversal 可能跨目录误选 | 词法/向量排序可能只保留高分同名项，或因相同日志把不同芯片候选合并 |

“架构容纳”具体指：第 1–3 层能保存 Target-local 代码证据，第 6 层能表达领域链接/候选/失效，第 7–8 层能有界返回证据与拒答。B01–B06 分别裁决 Target、宏、直接调用、间接调用、Event、identity；B07–B10 裁决检索、领域链接、失效和 Agent 端到端。未通过实验前，不得把任何一格改为 supported by evidence。

## 14. 排除项、开源规则与后续 Benchmark

### 14.1 排除为完整方案，但保留局部能力

1. **纯词法、纯向量或 RepoMap**：没有 Target-specific 程序关系和领域生命周期；保留为检索基线/组件。[[S001](https://arxiv.org/abs/2607.24882)] [[S004](https://aider.chat/docs/repomap.html)]
2. **单独 Tree-sitter 结构图**：没有公开证据证明真实宏、CFG/dataflow、函数指针或四 Target occurrence；Codebase-Memory/CodeGraph 只保留为模式 1 discovery 候选。[[S005](https://arxiv.org/abs/2603.27277)] [[S007](https://github.com/colbymchenry/codegraph)]
3. **直接采用 GitNexus**：PolyForm Noncommercial 与采用边界冲突，且公开 C/C++ import/效果证据不足；保留安全边界和多尺度导航参考。[[S008](https://github.com/abhigyanpatwari/GitNexus/blob/main/LICENSE)]
4. **CodeQL 作为默认开放核心**：查询库值得借鉴，但 CLI/engine 与闭源自动化分析存在单独许可边界；保留 Benchmark oracle、规则与 Agent 反馈参考。[[S013](https://github.com/github/codeql-cli-binaries)]
5. **无来源的 LLM/embedding 事实写入**：Wiki、Skill 与 memory 都有信息损失或负迁移证据，只能生成 INFERRED_CANDIDATE。[[S023](https://arxiv.org/abs/2605.07068)] [[S027](https://arxiv.org/abs/2603.15401)]
6. **Graphify/Understand Anything 直接作为代码事实核心**：保留领域混合图、claim/source 与可审阅资产设计；必须补 Target identity、revision 和 assertion lifecycle。[[S021](https://github.com/Graphify-Labs/graphify)] [[S009](https://github.com/Egonex-AI/Understand-Anything/blob/main/README.md)]

### 14.2 B01–B15 如何裁决

Benchmark 不生成掩盖硬门槛的总分，而按阶段停止：

- **Phase A，B01–B06 与 B11**：Target occurrence、宏/active branch、直接/间接调用、Event 路径、共享身份与跨构建系统 ingestion。任何 Target 泄漏、错误宏真值或不可定位证据均停止该完整方案臂。
- **Phase B，B08–B09 与 B13**：共同 assertion layer 的四状态、双向链接、source_revision_id/repository_revision 分离、失效/修复与领域知识净收益；这组实验不裁决 A/B。
- **Phase C，B07、B10、B12、B14**：日志/混合检索、Agent 高层工具与 raw DSL fallback、深分析泛化、冷启动/增量/故障隔离；分别报告事实准确性、检索效率和最终 Agent 正确性。
- **Phase D，B15**：逐组件 SPDX/SBOM、许可、冷机复现与替代路径；许可失败排除具体实现，不自动否定架构族。

四臂采取配对设计：A0↔A1、B0↔B1 测 discovery 效应，A0↔B0、A1↔B1 测主骨架效应，并报告二因素交互；同 pair 固定任务、Target、repository_revision、Agent、prompt、预算、硬件与失败策略。详细假设、gold、counterfactual、指标和成本见 [B01–B15 backlog](docs/research/benchmark-backlog.md)。

### 14.3 外部 C 案例与版本边界

外部仓只检验可移植性：

| 案例 | 固定来源 | 结构相邻性与 ground truth |
|---|---|---|
| Zephyr v4.4.0 / 684c9e8 | release [[S031](https://github.com/zephyrproject-rtos/zephyr/releases/tag/v4.4.0)]；build/Kconfig/devicetree [[S032](https://docs.zephyrproject.org/4.4.0/build/index.html)] | board/SoC/Kconfig/devicetree/driver 映射 Target/config；保存 .config、生成 devicetree、compdb/对象 |
| RIOT 2026.04.01 / 4a70282 | release [[S033](https://github.com/RIOT-OS/RIOT/releases/tag/2026.04.01)]；structure/build [[S034](https://doc.riot-os.org/build-system/build_system_basics/)] | BOARD/CPU/FEATURE/USEMODULE/driver；保存最终 flags、对象和 Make 依赖 |
| Contiki-NG 5.1 / 2b87baf | release [[S035](https://github.com/contiki-ng/contiki-ng/releases/tag/release%2Fv5.1)]；build/config [[S036](https://docs.contiki-ng.org/en/develop/doc/getting-started/The-Contiki-NG-build-system.html)] | TARGET/BOARD/CPU、arch driver、os/net/mac；保存构建清单与预处理结果 |

三者与 WiFiDemo 结构相邻但不等价；新增案例也必须先登记 fixed commit、许可、结构映射和可构造 gold，不能仅因“是 C 项目”加入。

### 14.4 开源只作最后 tie-break

优先考虑可离线复现、可替换和许可证清晰的实现，但开源不能代替正确性、效果、成本或可运维性。只有在硬门槛全部通过，效果区间与资源/维护没有决定性差异时，才以更开放许可、更低替换成本、更强冷机复现和更少不可再分发组件作为 tie-break。SVF 的 AGPL、CodeQL engine 的授权、GitNexus 的非商业许可及模型权重都须按部署路径单独审计。[[S017](https://github.com/SVF-tools/SVF)] [[S013](https://github.com/github/codeql-cli-binaries)] [[S008](https://github.com/abhigyanpatwari/GitNexus/blob/main/LICENSE)]

## 15. 有效性威胁

- **没有本地候选实验**：本文没有运行 A0/A1/B0/B1、Serena、Sourcegraph、Codebase-Memory、CodeGraph、Joern/codebadger 或 QLCoder 的 WiFiDemo 实验，只能给架构容纳与待测结论。
- **第一方数据偏差**：Codebase-Memory、CodeGraph、Serena、GitHub Memory 等数字或任务来自项目/公司第一方；样本、模型、prompt 与发布选择可能偏向自身方案。
- **案例与同行评审范围有限**：codebadger 是三个作者案例；QLCoder 虽有受控对照但任务是 Java/CVE/CodeQL；经典 CPG 论文证明表示价值，不证明当前 frontend。
- **Agent/项目快速演进**：滚动 README、MCP 接口、模型、索引 schema 与许可可能变化；实验必须固定 commit/release、工具链、模型和原始输出。
- **C/C++ Target 外推**：Zephyr、RIOT、Contiki-NG 与 WiFiDemo 结构相邻而非同一产品；通用 Python/Java/C# Agent 结果也不能直接外推到宏密集多 Target C。
- **Ground truth 不完美**：compiler artifact 能证明编译存在与宏真值，不能自动证明 Feature/Flow/Protocol 意义；Event/Message 和人工领域链接仍需多源或动态证据。
- **许可证变化**：仓库主许可证不等于依赖、engine、模型、数据、容器和再分发路径许可；B15 必须在实验时重新快照。
- **架构推断偏差**：八层、A/B 与 0/1 是本文综合框架，不是论文或项目直接给出的分类；B01–B15 可推翻其成本、正确性或完整性假设。

## 16. 结论

独立调研没有支持“一个 MCP、一个图数据库、一个向量库或一个 CPG 产品即可成为完整 WiFi MAC 知识架构”。共同规律要求确定性入口、低成本发现与高成本核验分工、source-grounded progressive disclosure，以及派生 Wiki/Skill/memory 回到当前代码和原始资料验证；高层任务工具相对 raw DSL 的收益只是 B10 待验证设计原则，不是跨任务一般规律。

这些规律先导出八层骨架和共同断言层，再把真正的架构差异限制为程序事实主干与查询拓扑。当前范围因此缩小为两个主骨架：A Agent 原生的联邦语义服务骨架、B Target-specific CPG 主骨架；以及两种模式：0 直接查询、1 轻量发现后核验，组合为 A0、A1、B0、B1。

四变体都在设计上容纳 W01–W08，并共享 repository_revision/source_revision_id 分离、EXTRACTED/RULE_DERIVED/INFERRED_CANDIDATE/CURATED 权限、Event/Message 跨 Host/Device、可定位证据与生命周期合同。但架构容纳不是工具通过：当前没有任何候选的 WiFiDemo 实测证据，唯一赢家仍为 **unknown / benchmark required**。下一阶段必须按 B01–B15 先淘汰 Target、来源或权限硬失败，再分别比较事实准确性、检索效率、最终 Agent 正确性、资源、运维与许可；只有结果无决定性差异时，开源与可复现性才作为 tie-break。
