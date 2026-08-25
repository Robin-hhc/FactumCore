# 面向 WiFi MAC 驱动的 Agent 知识图谱建立策略：代码知识、领域文档与双向链接的证据综述

版本：2026-08-25

## 摘要

本文研究在结构类似 WiFiDemo 的嵌入式 C WiFi MAC 驱动仓库中，什么样的知识图谱建立策略最可能帮助 Agent 完成两类任务：从模糊自然语言问题定位到具体代码片段，以及从具体代码片段反向整理跨文件流程与领域含义。研究不复用 FactumCore 或 WiFiGraph 的既有实现，也不在缺少统一实验时宣布工具赢家。

通过近期代码检索基准、程序分析论文、AI/开源项目官方材料和少量仍具时效性的经典来源，本文得到一个研究综合：成熟、准确的 Agent 知识图谱需要同时具备**代码知识、文档与领域知识、代码—文档双向链接**三项能力。它们分别解决“代码实际是什么”“代码意味着什么”和“两类知识如何互相核验及随版本更新”的问题。Agent、MCP 或对话上下文只是调用这些知识的方式，不构成独立的知识类别。

在代码知识侧，普通符号工具、CodeGraph 等轻量结构图与 Joern/codebadger 等深度程序分析属于同一连续谱：前者更轻、更快，后者能回答 dataflow、slice 和间接路径等更深问题。文档侧可分为已有文档检索、Understand Anything/Graphify/RepoDoc 式代码驱动文档生成，以及 LLM-Wiki/WiCER 式 Wiki 编译与精炼。链接侧主要采用显式引用、模型语义映射、图驱动生成、影响传播和构建工件锚定。公开证据尚未覆盖多 Target、宏密集、Host/Device 分离的 WiFi MAC 场景，因此本文只缩小候选范围并预注册后续 Benchmark；效果接近时优先采用开放、可离线复现的方案。

## 1. 研究问题、范围与方法

### 1.1 两个核心问题

本文不再从产品内部架构出发，而从 Agent 的实际问答过程出发：

- **RQ1：领域到代码。** 用户说“Host TX offload 发送失败后怎样回收资源”时，系统怎样理解领域术语、找到正确 Target 的入口、沿关系扩展，并返回可核验的 `file:line`？
- **RQ2：代码到解释。** 用户从 `wal_send_data`、某个宏或错误分支出发时，系统怎样整理调用、消息、数据传播、流程步骤和设计原因，并说明每条结论来自代码、文档还是模型推断？

### 1.2 工作负载

WiFiDemo 只作为结构案例，不在本轮运行候选实验。其固定快照和源码证据登记在 [WiFiDemo 工作负载案例](wifidemo-workload-casebook.md)。对知识图谱最重要的结构特征包括：

- 多个 chip/host/device Target，共享源码与互斥源码并存；
- 宏和条件编译改变同一文件中的有效实体和调用关系；
- ops 表、回调和函数指针使文本调用关系不完整；
- Host 与 Device 独立编译，通过 Event/Message 交互；
- 领域术语、日志、设计说明与函数名不总是一致。

因此，目录中“存在某段代码”不能直接证明它在当前 Target 中有效；跨 Host/Device 关系也不能伪装成进程内 `CALLS`。

### 1.3 证据方法

检索截止到 2026-08-25。近期方案优先采用近半年论文和当前官方材料；Joern/CPG、Clang/LLVM 等基础技术允许使用经典论文或持续维护的官方文档。只纳入论文、公开实验、AI 公司技术材料、开源项目官方文档和标准；搜索摘要与二手综述不支撑正文结论。

项目第一方或作者数字均保留样本、模型、基线和限制，不与不同指标直接排名。来源、固定版本和核验状态见 [来源与证据台账](source-ledger.md)。

## 2. 从现有证据推导三项必要能力

在进入工具分类前，必须先回答：为什么一个面向 Agent 的成熟知识图谱不能只有代码索引，或只有文档 RAG？

### 2.1 代码检索证据：候选召回必要，但单一方法不足

[Agent Retrieval Bench](https://arxiv.org/abs/2607.24882) 在 427 个样本、25 个开源仓库和 308 个冻结快照上比较词法、RepoMap、embedding 与 Agent 轨迹。不同方法分别在 MRR、Recall@20 和 8K Token context yield 上占优，没有单一检索族全面胜出；记录的 Agent 轨迹在 27%–35% 样本中没有命中任何 gold file。该结果证明“找到相关文件”本身就是独立瓶颈，但只测检索，不证明程序关系或领域解释正确。

[CORE-Bench](https://arxiv.org/abs/2606.11864) 的超过 180,000 个查询和 106,000 个 broader-context 标注显示，传统代码搜索表现不能直接外推到 issue-to-edit 与 broader-context 场景。[ContextBench](https://arxiv.org/abs/2602.05892) 在 1,136 个任务、66 个仓库、8 种语言、4 个模型和 5 个 Agent 上进一步区分 explored context 与 utilized context：召回过的内容并不等于最终被正确使用。

**推论一：系统必须有代码知识。** 它至少要保存文件、符号、定义、引用、调用/依赖和源码位置；复杂行为问题还需要控制流、数据流或切片。文档相似度不能替代这些事实。

### 2.2 文档生成与 Wiki 证据：代码关系不包含完整领域含义

[Understand Anything](https://github.com/Egonex-AI/Understand-Anything) 在确定性 Tree-sitter 结构图之上生成 domain、flow、step 和 onboarding 资产；[Graphify](https://github.com/Graphify-Labs/graphify) 把代码图与文档、ADR/RFC、PDF/媒体和生成 Wiki 放入同一可查询图；[RepoDoc](https://arxiv.org/abs/2604.26523) 则从 RepoKG 和模块聚类生成带 API 交叉引用与 Mermaid 图的仓库文档。这些项目采用不同实现，却共同补充了代码图不直接表达的术语、职责、流程和设计意图。

[LLM-Wiki](https://arxiv.org/abs/2605.25480) 与 [WiCER](https://arxiv.org/abs/2605.07068) 进一步表明，长文档不能只切块后一次检索：知识可以被编译为主题 Wiki，再通过错误发现、评估和重新精炼维护。LLM-Wiki 在其文档多跳 QA 作者实验中相对最强图基线提高 2.0–8.1 F1，但检测错误中 dangling links 占 29.1%–63.8%，恰好说明生成链接本身也必须验证。WiCER 的作者实验显示 blind Wiki compilation 会出现 53%–60% catastrophic rate，而 1–2 次 evaluate/refine 恢复约 80% 的丢失质量；这些数据属于通用文档问答，不是代码效果。

**推论二：系统必须有文档与领域知识。** 它需要保留原始设计/规范，也可以生成流程和 Wiki，但生成资产必须有来源、版本和质量反馈，不能覆盖源码事实。

### 2.3 双向链接证据：两类知识必须能互相核验

RepoDoc 从代码图生成交叉引用文档，并在代码变更后通过双向语义影响传播定位受影响内容；作者在 24 个仓库、8 种语言上报告 API coverage +32.5%、completeness +10.4%、约 3 倍生成速度与 Token -85%，增量更新时间 -73%、Token -77%、update recall +10.2%。这些结果尚非独立复现，也未覆盖 WiFi MAC，但直接证明“代码图→文档→变更回溯”是一项可独立测量的能力。

Graphify 用 `EXTRACTED`、`INFERRED` 和 `AMBIGUOUS` 区分解析关系、模型推断和未消歧关系；Understand Anything 把确定性结构与生成式领域图分层。这说明把两类内容放进同一存储还不够：系统还要知道链接怎样产生、适用于哪个版本、变化后怎样失效。

**推论三：系统必须有代码—文档双向链接。** RQ1 需要从领域词和文档下钻到代码证据；RQ2 需要从代码上溯到流程、设计理由和文档。任何关键解释都应能回链代码或原始文档，模型语义映射只能先作为候选。

### 2.4 研究综合

综合上述不同来源，本文提出：**面向两类 Agent 问答的成熟、准确知识图谱，应同时具备代码知识、文档与领域知识、代码—文档链接三项能力。** 这是本文的跨来源归纳，不是单篇论文证明的充分必要定理；三项能力“存在”也不代表其在 WiFi MAC 中“正确”。后续三章因此分别按这三类能力调研方案。

## 3. 代码知识：从普通导航到深度程序分析

### 3.1 同一类别中的三种深度

| 深度 | 代表 | 主要建立策略 | 最擅长的问题 | 主要缺口 |
|---|---|---|---|---|
| 文本/符号导航 | rg、Serena、SCIP | 文本索引、definition/reference | 精确字面量、符号位置和引用 | 不直接证明跨文件行为 |
| 轻量结构图 | CodeGraph、Codebase-Memory、GitNexus | Tree-sitter/LSP 抽取实体、调用、依赖、社区 | 入口、调用者、模块和影响范围 | 通常没有完整 CFG/DDG、宏配置和指针别名 |
| 深度程序分析 | Joern/codebadger、CodeQL、SVF 等 | CPG、IR、CFG、dataflow、taint、slice | 数据传播、路径条件、间接关系、安全性质 | 构建/查询成本更高，需要正确 Target 输入 |

“代码导航与检索”与“CPG/深度程序分析”不是两个互不相关的东西。它们都负责把 Agent 从问题带到代码证据，只是关系深度、成本和可回答问题不同。

### 3.2 普通工具是必须保留的基线

[Serena](https://github.com/oraios/serena) 通过语言服务器向 Agent 提供 symbol、definition、declaration 和 references；[SCIP](https://github.com/scip-code/scip) 是保存 definition/reference/implementation 的开放索引协议，[Sourcegraph MCP](https://sourcegraph.com/mcp) 则将 search/read/navigation 暴露给 Agent。它们没有领域图或 CFG/DDG，但对精确符号、日志和引用问题可能已足够，必须作为知识图方案的最低成本对照。

### 3.3 轻量结构图的优势是快速缩小代码范围

[CodeGraph](https://github.com/colbymchenry/codegraph) 用 Tree-sitter 抽取符号、调用、导入和继承关系，以 SQLite/FTS5 持久化并增量同步。Agent 从自然语言或符号调用 `codegraph_explore`，取得相关源码与关系路径。其第一方实验在 7 个仓库、7 种语言、每库 1 个架构问题、每实验臂 4 次、Claude Opus 4.8 条件下，报告工具调用 -88%、时间 -53%、处理 Token -62%、成本 -44%；样本小、问题单一且没有 WiFi C，因此只能支持“可能降低探索成本”。

[Codebase-Memory](https://arxiv.org/abs/2603.27277) 同样把 Tree-sitter 代码图包装成 MCP。作者在 31 个仓库上报告 83% answer quality，对照逐文件探索为 92%，但 Token 约为对照 1/10、工具调用约为 1/2.1。这组结果提示结构图可能以少量答案质量换取显著效率，而不是无条件更优。[GitNexus](https://github.com/nxpatterns/gitnexus) 的 context、impact、explore 与社区视图也说明高层图操作适合 Agent，但缺少可用于本研究排序的 C 准确率实验。

轻量图的合理角色是：先找候选符号和局部子图，再回到源码核验。它不能把 Tree-sitter 看到的源码分支直接当成某个 Target 的编译事实。

### 3.4 深度程序分析解决更难的行为问题

[Joern](https://docs.joern.io/code-property-graph/) 把 AST、控制流和数据依赖统一为 Code Property Graph，并提供 dataflow、切片和查询 DSL。它比轻量图更适合回答“值从哪里来”“错误分支如何到达”“跨函数传播经过哪些步骤”，但 Joern 本身不是自然语言接口。

[codebadger](https://arxiv.org/abs/2603.24837) 的关键做法是在 Joern 上提供高层 MCP 工具，把切片、污点跟踪、数据依赖和语义导航封装给 Agent，避免让模型直接猜复杂 CPG 查询。论文展示 GGML、libtiff 和 libxml2 三个真实案例，其中 GGML 案例约 8,000 methods；这是可行性证据，不是大规模正确率对照。

[QLCoder](https://arxiv.org/abs/2511.08462) 展示另一种可借鉴机制：Agent 生成 CodeQL 查询后，由 LSP、检索和真实执行反馈迭代。在 176 个 CVE、111 个 Java 项目上，作者报告正确查询率 53.4%，仅 Claude Code 为 10%。该结果只证明 Java CVE 查询合成中的反馈闭环，不能外推为 Joern/CodeQL 在 WiFi C 中的胜负。

Clang/LLVM、SVF、PhASAR、Frama-C 等可作为编译事实、指针/值流或 C 性质的专项提供者。是否需要全量 CPG，还是轻量图加按需深分析，必须由复杂问题的正确率收益与资源成本共同裁决。

### 3.5 构建知识是多 Target C 的必要补强

[RIG](https://arxiv.org/abs/2601.10112) 从 CMake File API、CTest 等确定性构建/测试工件抽取组件、依赖和测试关系。作者在 8 个仓库、每仓 30 个结构化问题、Claude Code/Cursor/Codex 三个 Agent 的有无 RIG 对照中，报告平均准确率 +12.2%、时间 -53.9%、每个正确答案耗时 -57.8%。该实验只覆盖构建级架构，但方法直接适用于 WiFiDemo 的一个关键原则：Target、组件和实际参与编译的文件应来自构建工件，而不是目录猜测。

## 4. 文档与领域知识：已有材料、生成文档与 Wiki 编译

### 4.1 检索已有文档

README、设计文档、规范、ADR/RFC、测试说明、issue 和 commit 能表达“为什么”和领域术语。最保守的策略是保留原文，按自然语言召回，再通过其中的符号、路径、测试或 commit 引用回到代码。

优势是来源清晰；缺点是覆盖不完整、可能过期或没有 Target 范围。文档向量相似度只能产生候选，不证明某段说明仍适用于当前代码。

### 4.2 从代码结构生成领域与流程文档

三个代表项目覆盖不同侧重：

- **Understand Anything**：确定性 Tree-sitter 结构图在下，LLM 生成摘要、domain、flow、step 和 onboarding；适合从文件/函数上溯解释，也支持从领域问题下钻代码。公开材料没有领域映射或 C/Target 准确率。
- **Graphify**：本地代码解析与可选文档/PDF/媒体语义抽取结合，输出 `graph.json`、社区、`GRAPH_REPORT.md` 和可选 Wiki；query/path/explain 把图暴露给 Agent。它覆盖三类能力，但公开的通用问答数据不测代码—领域链接。
- **RepoDoc**：RepoKG 和模块聚类为多 Agent 文档生成提供骨架，重点是交叉引用、Mermaid 和增量重生成；作者数据较完整，但仍缺嵌入式 C、Target 与独立复现。

生成文档的正确用途是给 Agent 提供跨文件概览和领域入口；其关键主张仍必须回链代码或原始文档。

### 4.3 Wiki 是文档知识管理方法，不是代码分析器

LLM-Wiki 将原始资料编译为带目录、页面、双向链接和 source references 的 Wiki，并用 Error Book 发现和修复结构/内容错误。WiCER 用诊断问题评价 blind compilation 的遗漏，再重新编译。这些方法值得用于领域知识的 compile/evaluate/refine，但它们不解析 C、也不产生 Target-specific 调用/dataflow。

因此，LLM-Wiki/WiCER 只能与代码知识和源码锚点组合。没有稳定代码实体、文档来源和双向链接的通用上下文机制，不进入本研究的知识图谱候选。

## 5. 代码—文档链接：让两类问答形成闭环

### 5.1 五种链接策略

| 策略 | 代表 | 怎样支持领域→代码 | 怎样支持代码→解释 | 风险 |
|---|---|---|---|---|
| 显式引用 | ADR/RFC、`# WHY:`、Graphify、RepoDoc | 解析 symbol/path/commit/API 引用 | 反向索引找到设计说明 | 覆盖少，rename/行移动后断链 |
| 结构图驱动生成 | RepoDoc、UA、Graphify | 从生成页中的代码引用下钻 | 以模块/调用关系生成流程 | 模型把 may 写成 must 或补写意图 |
| 模型语义映射 | UA domain graph、Graphify inferred edge | 领域词映射为符号候选 | 函数群归纳为领域概念 | 不稳定，只能先作为候选 |
| 影响传播与重生成 | RepoDoc | 文档引用集合可回查代码 | 变化代码定位待更新文档 | update recall 不足会静默过期 |
| 构建工件锚定 | RIG、Clang compilation database | 限定到实际 Target/组件/文件 | 解释目标、依赖与测试关系 | 不覆盖协议意图和完整行为 |

### 5.2 链接的最小证据合同

任何进入确定性答案的链接至少要说明：

- 关系是 implements、explains、produces、constrained-by，还是仅 similarity；
- 代码的 repository revision、Target、symbol 与 `file:line`；
- 文档的版本、具体段落和原始来源；
- 关系由 compiler/parser、固定规则、人工还是 LLM/embedding 产生；
- 当前状态是 active、candidate、stale、contradicted 还是 superseded。

LLM/embedding 可以产生候选和排序，不能自行把关系升级为事实。代码内容、宏/Target、文档版本、解析器或模型变化时，相应链接应失效并重新验证。完整过程见 [代码—文档链接调研](code-domain-linkage.md)。

### 5.3 为什么链接能力决定答案质量

只有代码图时，Agent 容易找到“谁调用谁”，却难以理解项目术语和设计原因；只有 Wiki 时，Agent 能给出流畅解释，却可能找不到当前 Target 的真实代码。双向链接把两类知识变成可核验闭环：领域入口提高候选召回，代码证据限制幻觉，反向依赖保证生成解释随代码更新。

## 6. 方案能力对比与当前范围收敛

| 方案 | 代码知识 | 文档/领域知识 | 双向链接 | 最适合借鉴的策略 | 当前结论 |
|---|---|---|---|---|---|
| CodeGraph | 轻量结构图 | 无主线 | 主要回到源码 | 本地、增量、低成本 Agent 探索 | 保留为轻量图代表 |
| Codebase-Memory | 轻量结构图 | 无主线 | 主要回到源码 | MCP 图查询与效率/质量权衡 | 同类对照 |
| GitNexus | 轻量图、社区、impact | 部分模块上下文 | 图查询连接 | context/impact/explore 高层动作 | 设计参考；效果与许可另审 |
| Serena/SCIP | 符号导航 | 无主线 | 定义/引用位置 | 最低成本成熟导航基线 | 必须保留基线 |
| Joern/codebadger | CPG、CFG、dataflow、slice | 无主线 | 分析路径回到源码 | 深行为事实 + 高层 Agent 工具 | 深分析代表，非预定赢家 |
| RIG | 构建、组件、测试图 | 架构说明 | 构建证据回链 | Target/构建事实锚定 | 所有条件的补强原则 |
| Graphify | 轻量代码图 | 文档、报告、Wiki | 显式/推断/歧义边与 path | 三类知识的一体化产品形态 | 重点研究；精度未知 |
| Understand Anything | 确定性结构图 | domain/flow/step | 结构与领域图共同查询 | 从代码生成领域/流程资产 | 重点研究；精度未知 |
| RepoDoc | RepoKG | 交叉引用文档、Mermaid | 影响传播与定向重生成 | 图驱动文档生成和更新 | 重点研究；C/Target 未验证 |
| LLM-Wiki/WiCER | 不负责代码解析 | 可演化 Wiki | 必须外接源码锚点 | 文档 compile/evaluate/refine | 作为文档方法组合使用 |

完整逐项目矩阵见 [证据矩阵](evidence-matrix.md)，详细档案见 [方案清单](solution-inventory.md)。当前范围已经剔除：只有通用对话记忆、只有提示模板、只有无 provenance 向量切块，以及不能回到 revision/Target/source location 的方案。

## 7. 代表方案怎样完成两类问答

### 7.1 CodeGraph 类轻量代码图

**RQ1**：Agent 把问题转为关键词/符号，轻量图召回相关节点，沿调用和依赖扩展，再读取具体源码。

**RQ2**：从函数或文件沿调用/社区关系构造局部模块图，再由 Agent 总结。

**边界**：速度与探索成本可能占优，但领域术语解析、设计原因、宏/Target 和深数据流需要外接。

### 7.2 Joern + codebadger 类深度分析

**RQ1**：先由文本、文档或轻量图找到入口/source/sink，再由高层 MCP 工具执行 CPG/dataflow/slice。

**RQ2**：从具体代码锚点沿 CFG/DDG/dataflow 取得跨函数路径，按源码位置整理解释。

**边界**：能回答更深的“怎样执行”，但不自动回答“为什么设计”；查询、构建和 Target 正确性必须独立验证。

### 7.3 Graphify / Understand Anything 类混合图

**RQ1**：领域问题先进入文档/领域图，再用 query/path/explain 走到结构代码实体。

**RQ2**：代码社区和路径被归纳成 domain、flow、step、report 或 Wiki，并回链图节点。

**边界**：一体化程度高，但公开材料没有代码—领域链接 precision、stale detection 或 WiFi C Agent 正确率。

### 7.4 RepoDoc 类图驱动文档

**RQ1**：用户先在模块化交叉引用文档中定位概念，再沿 API/代码引用下钻。

**RQ2**：RepoKG 与模块聚类驱动多 Agent 生成说明；代码变化后只重建受影响内容。

**边界**：最直接覆盖代码到流程及更新，但程序事实深度和领域真实性仍取决于底层图与证据。

### 7.5 LLM-Wiki / WiCER 类文档编译

**RQ1**：Wiki 负责解析术语和历史知识，必须借助保存的源码锚点或外部代码图落到代码。

**RQ2**：把多次代码探索编译为主题页，并通过 probe/evaluate/refine 修复遗漏。

**边界**：适合维护文档知识，不是 C 程序分析替代品。

### 7.6 一个更可能成熟的组合过程

现有证据共同指向一种过程，而不是某个已证明的产品组合：

1. 用文档/Wiki/领域图解释术语和形成检索词。
2. 用词法、符号和轻量图快速召回候选代码。
3. 沿调用、引用、构建依赖和社区关系扩展。
4. 只对需要 dataflow、间接调用或路径条件的问题运行深度分析。
5. 回到正确 revision/Target 的源码位置核验。
6. 将结果组织为流程说明，关键主张回链代码/文档。
7. 代码或文档变化后，让链接失效并按影响范围重建。

该过程仍是假设，必须用后续实验比较每一步的增量价值。

## 8. 对 WiFiDemo 的适用性、保留与排除

### 8.1 硬门槛

任何候选在 WiFiDemo 上必须满足：

1. 同一源码在不同 Target 下形成隔离的 occurrence 与关系；
2. 生效宏和 active branch 以真实编译/预处理工件为准；
3. direct/indirect call 分开，未解析函数指针保留候选与不确定性；
4. Host/Device 之间使用 Event/Message 及两侧证据，不造跨二进制 `CALLS`；
5. 每个答案主张回到正确 revision、Target 和 `file:line`；
6. 生成文档和模型链接能随代码/文档变化失效。

### 8.2 当前保留的研究对象

- 普通文本/符号导航基线；
- CodeGraph 代表的轻量结构图；
- Joern + codebadger 式高层工具代表的深度程序分析；
- Graphify、Understand Anything、RepoDoc 的混合图、生成文档和双向更新策略；
- LLM-Wiki/WiCER 的文档编译与精炼方法；
- RIG/Clang 式真实构建工件锚定。

SVF、PhASAR、Frama-C、CodeQL 等保留为专项组件或方法学对照，不作为已经完整覆盖两类问答的产品。候选数量仍可根据 Benchmark 变成两套、四套或不同组合。

### 8.3 开源偏好

开放许可证、本地运行、可冻结版本、可导出原始图和可替换模型是重要采用条件。但开源不弥补 Target 泄漏、错误代码边或过期文档；只有效果区间接近且硬门槛均通过时，才以开源、维护活跃度和适配成本决胜。

## 9. 后续 Benchmark 与有效性威胁

### 9.1 五个实验条件

后续使用 C0 普通导航、C1 轻量代码图、C2 深度程序分析、C3 代码图+原始文档、C4 代码图+生成文档+双向链接。所有条件使用相同 repository/commit/Target、Agent、模型、prompt 和预算；Target 范围由真实构建工件约束。

15 个预注册问题覆盖 Target occurrence、宏、直接/间接调用、Host/Device Event、领域到代码、代码到流程、链接失效、端到端 Agent、外部 C 泛化、资源和许可证，详见 [Benchmark Backlog](benchmark-backlog.md)。外部案例可使用 Zephyr、RIOT、Contiki-NG 及其他结构相关的开源 C 项目，不局限于嵌入式 WiFi。

### 9.2 指标必须分层

- **事实准确性**：entity/edge/link precision、recall、F1，Target leakage，source-location accuracy。
- **检索效率**：Recall@K、MRR、context yield、Token、工具调用、P50/P95 时延和索引资源。
- **最终 Agent 正确性**：任务通过率、证据完整率、unsupported claims、abstention、反事实敏感性。
- **新鲜度**：stale detection、链接修复 precision/recall、错误沿用率、误更新率。

不能用单一总分让速度补偿事实错误；Agent “看过”正确文件也不等于最终“用对”证据。

### 9.3 有效性威胁

1. **来源偏差**：CodeGraph、RepoDoc、RIG、codebadger、QLCoder 等数据多为作者或第一方评估，尚缺独立复现。
2. **任务差异**：文档 QA、Java CVE 查询、通用仓库架构问答与 WiFi C 的指标不可直接排名。
3. **版本漂移**：滚动项目、模型、Agent scaffold 和查询工具会改变结果；必须固定 commit 与配置。
4. **Ground truth 风险**：复杂指针、宏和事件路径需要编译器、静态分析、运行 probe 与双人复核交叉建立 gold。
5. **生成知识污染**：高可读性不等于高真实性；必须测无证据主张、错误链接与 stale 内容。
6. **外部有效性**：WiFiDemo 是主要案例但不是总体；需要多个构建系统和 C 架构案例。

## 10. 结论

本轮调研不支持直接选择某个工具，但已经得到比预设完整方案更清晰的决策基础：

1. 面向 Agent 的知识图谱要同时回答领域到代码与代码到解释。
2. 为此，代码知识、文档/领域知识、代码—文档双向链接缺一不可；这是必要能力集合，不是已证明的充分条件。
3. CodeGraph、Serena/SCIP 与 Joern/codebadger 都属于代码知识方案，区别是导航和程序分析深度，不应被割裂讨论。
4. Graphify、Understand Anything、RepoDoc 同时跨越多个类别，应分别评估其代码图、生成文档和链接策略；LLM-Wiki/WiCER 只代表文档知识管理。
5. 对 WiFi MAC，最关键的额外约束是 Target-specific 构建事实、宏/间接调用以及 Host/Device Event 边界。
6. 当前最合理的收敛是保留普通导航、轻量图、深度图、图+文档链接四级对照，并通过 C0–C4 与 B01–B15 实验确定哪些能力真正产生净收益。

如果后续结果显示多个方案效果接近，应优先以开放许可证和可离线复现的开源组件构建最终方案；在此之前，不把任何候选写成赢家。
