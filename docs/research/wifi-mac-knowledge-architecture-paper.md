# 面向 WiFi MAC 驱动的 Agent 知识图谱建立策略：代码知识、领域文档与双向链接的证据综述

版本：2026-08-27

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

[Agent Retrieval Bench](https://arxiv.org/abs/2607.24882) 在 427 个样本、25 个开源仓库和 308 个冻结快照上比较词法、RepoMap、embedding 与 Agent 轨迹。不同方法分别在 MRR、Recall@20 和 8K Token context yield 上占优，没有单一检索族全面胜出；记录的 Agent 轨迹在 27%–35% 样本中没有命中任何 gold file。[CORE-Bench](https://arxiv.org/abs/2606.11864) 的超过 180,000 个查询和 106,000 个 broader-context 标注又显示，传统代码搜索表现不能直接外推到 issue-to-edit 与 broader-context 场景。这两项独立基准先确定了瓶颈：Agent 经常找不到正确代码，而且不同召回方式互补；但它们本身还没有证明“增加代码检索工具后 Agent 变好”。

有/无工具的受控对照给出了增量证据：

- [CodeGraph](https://github.com/colbymchenry/codegraph) 第一方实验让同一模型回答同一批架构问题，处理组增加结构化代码检索，对照组只使用普通文件读取和搜索。在 7 个仓库、7 种语言、每库 1 个问题、每个实验臂 4 次的条件下，处理组报告工具调用 -88%、时间 -53%、处理 Token -62%、成本 -44%。这证明在该小样本架构问答中，结构检索减少了盲目探索；实验没有独立的答案正确率裁判，因此不能声称准确率同步提高。
- [RIG](https://arxiv.org/abs/2601.10112) 在 8 个仓库、每仓 30 个构建/组件问题、3 个 Agent 上比较“不提供图”和“增加由真实构建/测试工件生成的图”。作者报告平均准确率 +12.2%、时间 -53.9%、每个正确答案耗时 -57.8%。这是“增加确定性仓库检索后准确率和效率同时改善”的直接对照，但只覆盖构建级架构，不覆盖 C 数据流或 WiFi 协议。
- [ContextBench](https://arxiv.org/abs/2602.05892) 在 1,136 个任务、66 个仓库、8 种语言、4 个模型和 5 个 Agent 上区分 explored context 与 utilized context，说明“工具召回过正确内容”不等于“最终答案用对了内容”。因此上述工具收益必须继续用最终任务正确性裁决，而不能只看 Recall 或调用次数。

**推论一：系统必须有可执行的代码检索与代码知识，但不能预设某一种图就是赢家。** 最低层要返回文件、符号、定义、引用和源码位置；轻量关系图用于缩小候选范围；复杂行为问题再增加控制流、数据流或切片。后续实验必须分别报告候选召回、事实准确性和最终 Agent 正确性，验证公开对照中的收益能否在 WiFi MAC 上重现。

### 2.2 文档生成与 Wiki 证据：代码关系不包含完整领域含义

代码结构只能直接表达文件、符号、调用和依赖，不能从语法边本身证明“TX offload 为什么存在”“某个 Event 在协议中的含义”或“失败后为什么必须回收资源”。现有项目正在用文档层补足这些问题：[Understand Anything](https://github.com/Egonex-AI/Understand-Anything) 在确定性结构图上生成 domain、flow、step 和 onboarding；[Graphify](https://github.com/Graphify-Labs/graphify) 把代码图与 README、ADR/RFC、PDF/媒体和生成 Wiki 放入同一可查询图；[RepoDoc](https://arxiv.org/abs/2604.26523) 从 RepoKG 和模块聚类生成带 API 交叉引用与 Mermaid 图的仓库文档。项目能力说明能证明“可以生成什么”，还不能证明生成内容改善了 Agent。

文档问答与文档生成实验提供了效果证据：

- [LLM-Wiki](https://arxiv.org/abs/2605.25480) 把原始资料编译为带目录、页面、双向链接和 source references 的 Wiki。在三个多跳 QA 数据集各 500 个样本的作者实验中，相对最强图基线提高 2.0–8.1 F1；在 AuthTrace 上总体提高 2.1 accuracy points，高多文档问题提高 8.9 points，但单文档问题反而降低 2.3 points。它说明结构化文档在跨材料综合中可能有净收益，也说明简单问题未必需要更重的文档层。
- [WiCER](https://arxiv.org/abs/2605.07068) 比较原始 full-context、RAG、盲目 Wiki 编译和 evaluate/refine。盲目编译的 catastrophic rate 为 53%–60%，经过 1–2 次诊断与精炼后恢复约 80% 的丢失质量，并把 catastrophic failures 相对降低 55%。这说明文档资产的价值来自“组织后再验证”，不是把 LLM 摘要永久写入知识库。
- RepoDoc 的作者实验在 24 个仓库、8 种语言上相对 CodeWiki 报告 API coverage +32.5%、documentation completeness +10.4%；在三种工具都支持的 Python 仓库上，相对 CodeWiki 生成时间约为 1/3、Token -85%。这些指标测文档覆盖、可回答性和成本，不等于代码事实正确率，但直接表明代码图驱动的文档层能增加可用解释性资产。

**推论二：系统必须有可溯源的文档与领域知识。** 原始设计、规范、测试说明和术语表负责表达代码边中没有的“含义与原因”；生成的流程页或 Wiki 负责跨文件综合。公开数据支持文档组织、完整性和多跳问答的增益，但也显示生成会丢失信息，因此生成资产必须保留来源、版本、评估结果和失败状态，不能覆盖源码事实。

### 2.3 双向链接证据：两类知识必须能互相核验

如果代码图和文档只是两个互不相干的索引，Agent 仍要靠模型猜测“这个段落在解释哪个函数”，代码变化后也不知道哪些说明已经过期。双向链接的增量价值应当用“交叉引用覆盖”和“变更后能否找到受影响文档”衡量，而不是继续用普通召回率替代。

RepoDoc 的初始生成实验显示 API coverage +32.5%、completeness +10.4%，但这是整个 RepoKG、聚类和生成流程相对 CodeWiki 的结果，不能单独归因于“双向链接”。更直接的链接/影响传播数据来自 Python 仓库的增量实验：每个仓库选择 20 个真实 commit 场景，完整重生成的 update recall 为 88.0%，使用 RepoKG 双向语义影响传播和选择性重生成后为 97.0%，相对提高 10.2%；同时更新时间 -73%、Token -77%。该结果直接测量变化代码能否被正确反映到受影响文档，但仍不等于单条 code—document link precision。

这些数据尚未独立复现，也没有覆盖 WiFi MAC；但它们把“代码变化→定位受影响文档→更新后覆盖变化”变成了可独立验证的结果链，而不是只列出产品功能。

链接也会制造新错误。LLM-Wiki 报告其检测到的错误中 dangling links 占 29.1%–63.8%；因此链接数量增加不是目标，链接可核验、可失效才是目标。Graphify 用 `EXTRACTED`、`INFERRED` 和 `AMBIGUOUS` 区分解析边、模型推断边和未消歧边；Understand Anything 把确定性结构事实与生成式领域图分层。这些机制没有公开的 WiFi MAC precision 数据，但共同说明链接必须记录产生方法和不确定性。

**推论三：系统必须有可验证的代码—文档双向链接。** RQ1 需要从领域词、架构事实或文档段落下钻到当前 revision/Target 的代码；RQ2 需要从代码上溯到流程、设计理由和原始来源。链接必须支持反向索引、变化失效和重新验证；模型语义映射只能先进入候选层。

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

轻量结构图是在文本命中与深程序语义之间增加一层可查询关系：解析器识别文件、函数、类型、导入、显式调用等实体和边，社区或图遍历再把几十个文本命中压缩为一个局部子图。它擅长回答“入口在哪”“谁显式调用它”“相关文件属于哪个局部模块”，但通常不执行路径可达性、跨函数值传播或指针别名求解。

**CodeGraph：轻量代码图的主对照。** [CodeGraph](https://github.com/colbymchenry/codegraph) 用 Tree-sitter 抽取符号、调用、导入和继承关系，以 SQLite/FTS5 持久化并增量同步。Agent 从自然语言或符号调用 `codegraph_explore`，一次取得相关源码、定义和跨文件关系，而不是反复 grep/read。其第一方有/无图实验在 7 个仓库、7 种语言、每库 1 个架构问题、每实验臂 4 次、Claude Opus 4.8 条件下，报告工具调用 -88%、时间 -53%、处理 Token -62%、成本 -44%。这些数字证明该实验中的探索效率改善，不证明边准确率或 WiFi C 答案正确率。

**Graphify：轻量代码图加多资料入口。** [Graphify](https://github.com/Graphify-Labs/graphify) 的代码阶段同样以本地 Tree-sitter 抽取符号和跨文件关系，生成持久 `graph.json`、社区和 `GRAPH_REPORT.md`，并提供 query/path/explain。与 CodeGraph 的差别不是代码语义更深，而是后续还能把文档、ADR/RFC、PDF/媒体和 Wiki 接入同一图；解析得到的代码边标为 `EXTRACTED`，模型语义边另行标注。它的通用 memory Benchmark 不测 C 调用边或代码—领域链接，因此在本研究中属于“完整产品形态候选”，不是已证明更准的轻量图。

**Understand Anything：确定性结构层加生成式理解层。** [Understand Anything](https://github.com/Egonex-AI/Understand-Anything) 先用 Tree-sitter 形成文件、函数、类和依赖的可复现结构图，再让 LLM 生成摘要、架构层和领域映射；fingerprint 用于发现变化并增量更新。它把“解析事实”和“模型解释”明确分层，这是本研究可借鉴的证据边界；但官方没有给出 C 宏、Target occurrence 或领域映射准确率。

**RepoDoc：以 RepoKG 作为文档骨架。** [RepoDoc](https://arxiv.org/abs/2604.26523) 先构建代码实体与关系组成的 RepoKG，再做模块聚类，最后驱动文档 Agent。它的重点不是交互式代码探索或深程序分析，而是让代码图决定文档模块、API 交叉引用和变化影响范围；文档和链接机制分别在第 4、5 节展开。

[Codebase-Memory](https://arxiv.org/abs/2603.27277) 提供了重要反例：作者在 31 个仓库上报告结构图 Agent 的 answer quality 为 83%，逐文件探索对照为 92%，但 Token 约为对照的 1/10、工具调用约为 1/2.1。结构图可能显著提效，也可能丢失答案所需细节。因此轻量图的合理角色是先找候选符号和局部子图，再回到源码核验；它不能把 Tree-sitter 看到的所有条件分支直接当成某个 Target 的编译事实。

### 3.4 深度程序分析解决更难的行为问题

“深度”不等于“换掉 Tree-sitter”，也不以图数据库大小定义。Tree-sitter、Clang AST 都可以提供语法输入；真正的区别是系统是否在语法之上计算程序行为关系，并允许 Agent 对这些关系提出可执行、可复核的问题。

| 维度 | 轻量结构图通常提供 | 深度程序分析额外计算 | 因而能多回答什么 |
|---|---|---|---|
| 控制 | 函数和显式调用边 | CFG、分支条件、支配/后支配、跨过程路径 | 某错误分支是否可达；cleanup 是否覆盖所有返回路径 |
| 数据 | 参数、字段和局部语法引用 | definition-use、DDG、跨函数 dataflow、taint、slice | 一个长度、状态或 buffer 从哪里来，最终影响哪个 sink |
| 间接关系 | 可见的函数名和简单赋值 | call graph、points-to/alias 候选、custom semantics | ops 表或回调可能落到哪些实现；哪些只是 may-call |
| 结果形态 | 邻接节点和源码片段 | 带方向、路径条件、传播步骤和源码位置的可核验分析路径 | 不只列“相关函数”，而是解释为何这些函数构成同一行为链 |

[Joern](https://docs.joern.io/code-property-graph/) 把 AST、控制流和数据依赖统一为 Code Property Graph，并提供跨过程 dataflow、切片和查询 DSL。一个具体差别是：案例集只确认 `host/wifi/dpe/hcc/hcc_core.c:202-214` 中宏控制的 `dpa_forward_to_device(msg)`/`hcc_tx_queue_put(msg)` 互斥调用，轻量图可以返回这两个显式候选。深分析可进一步被要求调查“`msg` 从哪个分配/赋值点到达该分支”“某个返回值对应的失败路径是否到达释放动作”。后两个是待候选工具回答并由源码/运行 probe 验证的问题，不是案例集已经确认的生命周期事实。若问题只问调用者，轻量图足够；若问题问同一对象是否在所有失败路径释放，就需要数据流、别名和路径信息。分析结果仍应写成 may/must、路径条件和未解析候选，不能把静态近似包装成确定执行轨迹。

[codebadger](https://arxiv.org/abs/2603.24837) 在 Joern 上提供高层 MCP 工具，把切片、污点跟踪、数据依赖和语义导航封装给 Agent，避免让模型直接猜复杂 CPG 查询。论文展示 GGML、libtiff 和 libxml2 三个真实案例：第一个案例的代码库约 8,000 methods，另两个案例分别涉及缓冲区溢出分析与 CVE patch。它证明 Agent 可以操作深分析能力，但只有 3 个作者案例，没有“轻量图 vs 深度图”的大规模正确率对照。

[QLCoder](https://arxiv.org/abs/2511.08462) 给出了执行反馈的重要性数据：Agent 生成 CodeQL 查询后，由 LSP、检索和真实执行结果迭代；在 176 个 CVE、111 个 Java 项目上，作者报告正确查询率 53.4%，仅使用 Claude Code 为 10%。43.4 percentage points 的差距说明深分析不是把更多边塞给模型，而是“生成查询—执行—根据错误和结果修正”的闭环。该实验属于 Java CVE 查询合成，不能外推为 Joern/CodeQL 在 WiFi C 中的胜负。

因此深分析的预期增益集中在间接调用、资源生命周期、跨函数状态/数据传播、错误路径和安全性质，而不是所有代码问答。Clang/LLVM、SVF、PhASAR、Frama-C 等可分别提供编译事实、指针/值流或 C 性质。后续必须用同一批复杂问题对比轻量图和深度图的事实 F1、最终答案通过率、查询失败率、时间和索引成本；如果深分析只在少数题显著获益，就应按需调用而不是全仓默认展开。

### 3.5 构建知识是多 Target C 的必要补强

构建知识不是与 grep、轻量图或 CPG 竞争的第四种完整工具，而是它们共同需要的事实补强层。文本和 Tree-sitter 告诉系统“仓库中写了什么”，CPG 告诉系统“给定输入视角下可能怎样传播”，编译命令、预处理结果、对象清单和链接工件则限定“这个 Target 实际编译了什么”。

[RIG](https://arxiv.org/abs/2601.10112) 从 CMake File API、CTest 等确定性构建/测试工件抽取组件、依赖和测试关系。作者在 8 个仓库、每仓 30 个结构化问题、Claude Code/Cursor/Codex 三个 Agent 的有无 RIG 对照中，报告平均准确率 +12.2%、时间 -53.9%、每个正确答案耗时 -57.8%。该实验只覆盖构建级架构，但支持一个可迁移结论：把确定性构建事实提供给 Agent，比让 Agent 从目录和源码猜 Target 更可靠。对 WiFiDemo，需要按 Target 建索引的候选工具应读取同一份 Target Profile；RIG/Clang 式工件负责约束索引输入和建立评分 gold，不单独算作一个完整答案系统。

跨 Host/Device 分析尤其需要“两个局部代码视角 + 一条协议链接”，而不是一个无边界的全仓调用图。以案例 W06 为例：

1. 对 `chip8-wifi-host` 和 `chip8-wifi-device` 分别读取编译命令、宏和对象清单，生成两个隔离的 occurrence 集合；Host 与 Device 可以分别建立轻量图或 CPG。
2. 在共享源码侧，以 `shared/include/wifi_hcc.h:13-38` 的通道、消息头和 `hcc_tx_msg_stru` 建立稳定 Message schema；它是两侧共同引用的协议对象，不属于任一侧函数调用。
3. Host 侧从 `host/wifi/dpe/hcc/hcc_core.c:202-214` 找到消息 producer/发送证据，并记录当前 Target 下实际生效的宏分支。
4. Device 侧从 `device/wifi/chip8/hcc/hcc_device.c:79-107` 找到按 channel/msg_type 触发的 `g_frw_dispatch`，再从 `device/wifi/chip8/frw/frw_event.c:12-35` 与 `device/wifi/chip8/frw/frw_event_main.c:103-130` 找到事件查表和注册证据。
5. 跨侧只建立 `PRODUCES(Host occurrence, Message)`、`CONSUMES(Device occurrence, Message)`、`DISPATCHED_BY`、`REGISTERED_AS` 等 Event/Message 关系。Agent 查询到边界时切换到另一 Target 图继续分析，不伪造 Host 函数直接 `CALLS` Device handler。

这一组合能回答“哪个 Host Target 产生消息、共享字段是什么、Device 在哪里注册并分发”，而纯轻量调用图无法跨独立二进制建立这条链；深度图可以继续分析两侧局部 dataflow，却也不能单靠语言调用关系推出协议配对。后续 B05 应以 event-edge precision/recall、方向和 Side 正确率、完整路径率、Target leakage 为指标；当前案例只给出可核验设计和源码锚点，不冒充候选工具的实测成绩。

## 4. 文档与领域知识：已有材料、生成文档与 Wiki 编译

### 4.1 检索已有文档

README、设计文档、规范、ADR/RFC、测试说明、issue 和 commit 能表达“为什么”和领域术语。最保守的策略是保留原文，按自然语言召回，再通过其中的符号、路径、测试或 commit 引用回到代码。

优势是来源清晰；缺点是覆盖不完整、可能过期或没有 Target 范围。文档向量相似度只能产生候选，不证明某段说明仍适用于当前代码。

### 4.2 从代码结构生成领域与流程文档

三个重点项目都从代码结构生成解释性资产，但知识来源和维护方式不同。

**Understand Anything：从结构图生成“怎样理解这个仓库”。** 它先形成确定性的文件、函数、类和依赖图，再由多个 Agent 生成 plain-English summary、架构层、guided tour 和 onboarding；`understand-domain` 进一步生成 domain、flow 和 step。用户可以从文件/函数执行 explain，也可以从“payment flow 怎样工作”一类领域问题进入生成式领域图。结构层相同输入可复现，语义层由 LLM 推断，变化文件通过 fingerprint 增量重分析。它适合验证“生成式架构说明是否减少理解成本”，但官方没有领域映射准确率、C 宏或 Target 隔离数据。

**Graphify：把代码、原始文档和生成 Wiki 放入同一产品流程。** 代码由本地 Tree-sitter 解析，README、ADR/RFC、PDF、图像或媒体可选用模型做语义抽取；随后生成 `graph.json`、社区、`GRAPH_REPORT.md` 和可选 Wiki，并通过 query/path/explain 暴露给 Agent。它的优势是三类能力都存在于一个可查询产品形态中；风险是代码解析事实、模型抽取和生成文档的准确率不同，不能因为它们共处一图就给予相同证据等级。官方通用 memory 数据不测 WiFi C 的领域边 precision、Target leakage 或 stale-link repair。

**RepoDoc：由 RepoKG 决定文档结构并维护变化。** 它先构建仓库级 RepoKG，再按代码关系聚类功能模块，由多 Agent 为各模块生成交叉引用说明和 Mermaid 图；代码变化后沿图定位受影响文档，只重建目标部分。作者在 24 个仓库、8 种语言的 RepoDoc/CodeWiki 对照中报告 API coverage +32.5%、completeness +10.4%；相对 CodeWiki 约 3 倍生成速度和 Token -85% 来自三种工具共同支持的 Python 仓库对照。不同数据的样本范围不能合并成一个跨语言结论。这些结果使它成为文档生成和更新的重要完整候选，但不证明 RepoKG 已准确处理嵌入式 C 宏、函数指针或多 Target。

三者都不是原始设计文档的替代品。生成文档的正确角色是：把分散代码组织为跨文件概览，为 Agent 提供领域入口和候选流程；其中每条关键事实仍必须链接到源码、构建工件或原始文档，并在依赖变化后重新验证。

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

五种策略不是五选一。显式引用提供最强但覆盖有限的锚点；结构图驱动生成扩大覆盖；模型语义映射处理术语差异；影响传播负责新鲜度；构建工件把所有代码链接限制到真实 Target。一个成熟答案通常同时经过其中两到四种。

### 5.2 重点工具具体怎样建立链接

**CodeGraph** 的已核验能力集中在代码侧：Tree-sitter 抽取符号、调用、导入和继承关系，`codegraph_explore` 从自然语言或符号请求返回相关源码及调用路径。它能把“某函数的调用者”扩展到其他代码文件；已核验官方材料未建立以领域文档生成、段落级反向依赖和文档变化传播为主线的机制，因此完整闭环需要另接文档/领域层。

**Understand Anything** 明确分开两类产物：下层是 Tree-sitter 得到的结构图，上层是 LLM 生成的 summary、domain、flow、step 和 onboarding；官方接口支持文件/函数 explain 和领域问题查询，并用 fingerprint 发现变化文件。这些能力使“领域对象关联结构节点”成为可验证的候选链接策略，但已核验材料没有证明 domain/flow 到代码节点的持久双向遍历、链接 precision、Target scope 或人工证据覆盖规则，因此不能把它写成已经验证的双向链接实现。

**Graphify** 把代码、`# WHY:` 注释、README、ADR/RFC、PDF/媒体和生成报告表示为同一图中的对象，通过 query/path/explain 穿越关系。解析器生成的代码边为 `EXTRACTED`，LLM 生成的语义边为 `INFERRED`，不能确定唯一对象时为 `AMBIGUOUS`。这种 provenance 标签允许 Agent 在同一路径上区分硬边和软边；仍需另外保存 revision、Target 和失效条件，才能满足 WiFi MAC 的确定性答案要求。

**RepoDoc** 的链接从文档生成流程中产生：RepoKG 和模块聚类决定某段文档依赖哪些 API、模块和关系，生成页保存交叉引用；反向索引再允许代码变化沿依赖传播到受影响段落。初始生成的 API coverage +32.5% 是完整流程收益，不能单独当作 link precision；更直接的影响传播指标是在 Python commit 场景中 update recall 从完整重生成的 88.0% 提高到 97.0%（相对 +10.2%）。它证明变化影响发现可测，但仍没有公开 WiFi C 单条链接 precision。

### 5.3 WiFiDemo 中具体文件和代码怎样链接

链接不能只保存一个易漂移的 `file:line` 字符串。代码端至少分为稳定源码实体与构建 occurrence：前者标识“某 revision 中的文件/符号”，后者标识“该实体在某 Target、编译命令和宏环境下的有效实例”。文档端至少分为原始文档段落、生成文档段落和其中的单条 claim。两端之间的链接记录 relation、provenance、状态和依赖集合，`file:line` 用于展示与复核，不单独承担身份。

以“chip8 Host TX offload 怎样进入 Device 分发”为例，文件级链路如下：

| 顺序 | 代码或文档对象 | 建立的关系 | 关系证据与用途 |
|---|---|---|---|
| 1 | `build.py:14-35` | `DECLARES_TARGET(chip8-wifi-host)`、`DECLARES_TARGET(chip8-wifi-device)` | 固定合法 Target 名称，领域问题先选择编译视角 |
| 2 | `host/CMakeLists.txt:9-14` | `ENABLES(chip8-wifi-host, _PRE_WLAN_FEATURE_HOST_TX_OFFLOAD)` | 构建规则证明宏只在相应 Host Target 生效 |
| 3 | `host/wifi/dpe/hcc/hcc_core.c:202-214` 的 Target occurrence | `CONSTRAINED_BY` 宏；`PRODUCES` TX Message | 预处理/编译工件确认有效分支，源码位置证明 Host producer |
| 4 | `shared/include/wifi_hcc.h:13-38` 的 `hcc_tx_msg_stru` 与消息头 | `HAS_SCHEMA`、`SHARED_BY(Host, Device)` | 用共享 channel/msg_type 和结构字段连接两侧，而不是用函数名猜测 |
| 5 | `device/wifi/chip8/hcc/hcc_device.c:79-107` | `CONSUMES` Message；`DISPATCHED_BY(g_frw_dispatch)` | Device occurrence 证明接收与一级分发 |
| 6 | `device/wifi/chip8/frw/frw_event.c:12-35`、`frw_event_main.c:103-130` | `LOOKS_UP` Event；`REGISTERED_AS` handler candidate | 查表和注册证据把消息继续连接到 Device 处理候选 |
| 7 | “Host TX offload”原始/生成文档段落 | `EXPLAINS` Feature/Flow；`SUPPORTED_BY` 上述 evidence set | 领域词先链接 Feature，再沿 Target、Macro、Message、Event 下钻到两侧代码 |

RQ1 的查询方向是：文档术语 `Host TX offload` → Feature/Flow → `chip8-wifi-host` → 生效宏 → Host occurrence → Message schema → Device dispatcher/handler candidates。RQ2 的方向相反：从任一源码锚点沿 `SUPPORTED_BY/EXPLAINS` 反向索引取得流程页和设计说明。跨侧关系始终是 Message/Event 的 producer/consumer，不是跨二进制 `CALLS`。

生成一段流程说明时，系统还要保存该段落依赖的 evidence set，例如 `{host CMake 条件, Host 分支, 共享消息结构, Device dispatch, FRW 注册}`。如果 `host/CMakeLists.txt` 改宏、共享消息字段变化或注册表改变，这个集合的任一成员发生变化，段落先标记 `stale`，重新抽取后再比较和审核；不能只把旧行号平移到相似代码。

### 5.4 链接的最小证据合同

任何进入确定性答案的链接至少要说明：

- 关系是 implements、explains、produces、constrained-by，还是仅 similarity；
- 代码的 repository revision、Target、symbol 与 `file:line`；
- 文档的版本、具体段落和原始来源；
- 关系由 compiler/parser、固定规则、人工还是 LLM/embedding 产生；
- 当前状态是 active、candidate、stale、contradicted 还是 superseded。

LLM/embedding 可以产生候选和排序，不能自行把关系升级为事实。代码内容、宏/Target、文档版本、解析器或模型变化时，相应链接应失效并重新验证。完整过程见 [代码—文档链接调研](code-domain-linkage.md)。

### 5.5 为什么链接能力决定答案质量

只有代码图时，Agent 容易找到“谁调用谁”，却难以理解项目术语和设计原因；只有 Wiki 时，Agent 能给出流畅解释，却可能找不到当前 Target 的真实代码。双向链接把两类知识变成可核验闭环：领域入口提高候选召回，代码证据限制幻觉，反向依赖保证生成解释随代码更新。

RepoDoc 的 update recall 从 88.0% 到 97.0% 表明反向影响传播可以产生可测增益；LLM-Wiki 中 dangling links 占检测错误的 29.1%–63.8% 又表明错误链接会成为新的失败源。因此第 5 节的目标不是“链接越多越好”，而是同时提高 link precision、evidence coverage、stale detection recall，并降低错误沿用率。只有这些指标通过后，链接数量才有意义。

## 6. 方案能力对比与当前范围收敛

本节只综合前文，不再首次引入重点候选：CodeGraph 的结构抽取与效率对照已在 2.1、3.3 说明；Graphify、Understand Anything、RepoDoc 的代码底座已在 3.3 说明，文档生成已在 4.2 说明，双向链接已在 5.2–5.3 说明。表中的“覆盖某能力”只表示产品机制存在，不表示它已在 WiFi MAC 上达到可接受精度。

| 方案 | 代码知识 | 文档/领域知识 | 双向链接 | 最适合借鉴的策略 | 当前结论 |
|---|---|---|---|---|---|
| CodeGraph | 轻量结构图 | 无主线 | 主要回到源码 | 本地、增量、低成本 Agent 探索 | 保留为轻量图代表 |
| Codebase-Memory | 轻量结构图 | 无主线 | 主要回到源码 | MCP 图查询与效率/质量权衡 | 同类对照 |
| GitNexus | 轻量图、社区、impact | 部分模块上下文 | 图查询连接 | context/impact/explore 高层动作 | 设计参考；效果与许可另审 |
| Serena/SCIP | 符号导航 | 无主线 | 定义/引用位置 | 最低成本成熟导航基线 | 必须保留基线 |
| Joern/codebadger | CPG、CFG、dataflow、slice | 无主线 | 分析路径回到源码 | 深行为事实 + 高层 Agent 工具 | 深分析代表，非预定赢家 |
| RIG | 构建、组件、测试图 | 架构说明 | 构建证据回链 | Target/构建事实锚定 | 所有条件的补强原则 |
| Graphify | 轻量代码图 | 文档、报告、Wiki | 显式/推断/歧义边与 path | 三类知识的一体化产品形态 | 首轮完整能力候选；精度未知 |
| Understand Anything | 确定性结构图 | domain/flow/step | 结构与领域图共同查询 | 从代码生成领域/流程资产 | 首轮完整能力候选；精度未知 |
| RepoDoc | RepoKG | 交叉引用文档、Mermaid | 影响传播与定向重生成 | 图驱动文档生成和更新 | 降为方法参考；暂不投入首轮适配 |
| LLM-Wiki/WiCER | 不负责代码解析 | 可演化 Wiki | 必须外接源码锚点 | 文档 compile/evaluate/refine | 作为文档方法组合使用 |

完整逐项目矩阵见 [证据矩阵](evidence-matrix.md)，详细档案见 [方案清单](solution-inventory.md)。当前范围已经剔除：只有通用对话记忆、只有提示模板、只有无 provenance 向量切块，以及不能回到 revision/Target/source location 的方案。首轮工程实测优先投入 CodeGraph、Joern、Understand Anything 和 Graphify，分别覆盖轻量代码图、深度程序分析、结构图加生成式理解以及一体化图谱产品。RepoDoc 的论文结果仍用于定义文档覆盖、影响传播和增量更新指标，但其官方仓库在 2026-08-27 的快照只有 4 个 commit、约 15 Stars，且仓库根目录未见明确许可证文件或 `pyproject.toml` license 声明；在许可证、维护连续性和可复现安装得到澄清前，不把它列为首轮工程实测对象。Stars 只作为生态信号，降级依据是这些采用风险与首轮投入产出比，而不是用流行度代替效果验证。

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
- Graphify、Understand Anything 的混合图、生成文档和链接策略；
- RepoDoc 的 RepoKG、交叉引用和双向影响传播方法，作为指标与设计参考而非首轮可执行候选；
- LLM-Wiki/WiCER 的文档编译与精炼方法；
- RIG/Clang 式真实构建工件锚定。

SVF、PhASAR、Frama-C、CodeQL 等保留为专项组件或方法学对照，不作为已经完整覆盖两类问答的产品。候选数量仍可根据 Benchmark 变成两套、四套或不同组合。

### 8.3 开源偏好

开放许可证、本地运行、可冻结版本、可导出原始图和可替换模型是重要采用条件。但开源不弥补 Target 泄漏、错误代码边或过期文档；只有效果区间接近且硬门槛均通过时，才以开源、维护活跃度和适配成本决胜。

## 9. 后续 Benchmark 与有效性威胁

### 9.1 六个实验臂：逐项测量工具或先验的增量价值

后续不再只比较抽象的“有图/无图”，而预注册六个实验臂；它们只有在 Benchmark Backlog、适配器和评分器同步后才成为可执行协议：

| 条件 | Agent 获得的额外能力 | 明确不包含 | 要裁决的问题 |
|---|---|---|---|
| C0 基础 grep | 当前源码、`rg`/grep、文件读取 | 预解析符号图、架构 Skill、生成文档 | 最低成本 Agent 能做到什么 |
| C1 CodeGraph 轻量代码图 | C0 + CodeGraph 的符号、显式调用、依赖和局部图查询 | CFG/DDG、领域文档和人工架构先验 | 轻量图是否提高召回或减少探索成本 |
| C2 Joern 深度分析代码图 | C0 + Joern Target-specific CPG、CFG、dataflow、slice 和受限高层分析工具 | 生成领域文档；未证明的跨二进制调用边 | 深分析是否只在间接调用、路径和生命周期题上产生净收益 |
| C3 基础架构事实 Skill | C0 + 一份人工整理、版本固定的简短 Skill | 函数流程、函数归属、调用链、领域解释和自动代码图 | 少量稳定仓库先验能否以很低成本取得主要收益 |
| C4 Understand Anything 混合候选 | UA 的确定性结构图、summary、domain/flow/step、explain 和增量更新 | 额外人工补写答案；官方材料未证明的持久双向链接或 Target 能力不能私下补齐 | 结构事实与生成式架构/领域资产的组合是否改善 Agent 正确率和理解成本 |
| C5 Graphify 完整候选 | Graphify 的代码图、原始/生成文档、领域对象和 query/path/explain | 额外人工补写答案；未实现的 Target 能力不能私下补齐 | 一体化三能力产品是否优于分层工具 |

C3 的 Skill 只允许写入事实性基础信息：哪些目录属于 Host、Device 或 shared，支持哪些芯片版本与 Target，构建入口和 Target 命名是什么。它不允许写入“某函数实现某流程”“某调用链属于某 Feature”或问题答案，否则会把人工 gold 泄漏给 Agent。Skill 按 repository revision 版本化，单独统计编写和维护成本。

所有条件固定 repository/commit、问题 Target、Agent、模型、prompt、工具总预算和重复次数。索引器可使用实验指定的编译输入建立 Target 视角，但 Agent 是否能正确找到并使用这些事实仍是被测内容；评分 gold 始终来自真实编译/预处理工件、源码位置、可运行 probe 和人工复核。Understand Anything 或 Graphify 如果不能表达 Target occurrence、Event/Message、持久链接或 provenance，应把缺口记录为实验结果，不能用实验外脚本静默补成完整方案。

不同实验臂有意提供不同能力，因此能力专项题必须预注册适用范围，`N/A` 不计作失败：

| 任务/指标 | C0 grep | C1 CodeGraph | C2 Joern | C3 架构 Skill | C4 UA | C5 Graphify |
|---|---:|---:|---:|---:|---:|---:|
| 领域到代码、代码到流程的端到端答案 | 测 | 测 | 测 | 测 | 测 | 测 |
| Target/宏/源码位置正确性 | 测 | 测 | 测 | 测 | 测 | 测 |
| direct/indirect call 与 dataflow 任务正确性 | 测 | 测 | 测 | 测 | 测 | 测 |
| 文档链接 precision 与 evidence coverage | N/A | N/A | N/A | N/A | 测 | 测 |
| stale detection、链接修复与误更新 | N/A | N/A | N/A | N/A | 测 | 测 |
| 索引构建/增量资源 | N/A | 测 | 测 | N/A | 测 | 测 |
| Skill 编写/审计/更新成本 | N/A | N/A | N/A | 测 | N/A | N/A |

C0/C1/C2/C3 即使没有文档链接机制，仍要参加统一的端到端问答，检验代码能力或少量先验能否直接完成任务；但它们不参加 link precision 和 stale-link 专项排名。反过来，C4/C5 不能因提供完整产品形态而豁免代码事实硬门槛。UA 的已公开材料没有证明持久双向链接与 stale repair，因此相应专项若无法执行，应记为产品能力缺口而不是 `N/A`；RepoDoc 的 update recall 和选择性重生成实验只用于帮助定义该专项的 gold、指标与预期失败模式。

### 9.2 三类项目逐级验证并选定方向

验证按“Demo 淘汰硬错误—开源项目验证泛化—内部真实项目完成选型”推进；后一阶段不覆盖前一阶段的失败。

**阶段一：WiFiDemo。** 冻结 WiFiDemo commit、四个 chip/host/device Target 和工具版本，所有实验臂先跑 Target occurrence、宏、直接/间接调用、Host/Device Event、领域到代码和代码到流程；只有 C4/C5 运行链接 precision、失效和修复专项。该阶段的目标是建立可执行 gold、快速发现 Target leakage 和伪造跨二进制 `CALLS`。任何实验臂不能返回正确 revision/Target/`file:line`，或把 inactive branch 当确定事实，即停止其“成熟方案”排名，但保留失败数据。

**阶段二：开源真实项目。** 对通过或部分通过 Demo 的方向，在 Zephyr、RIOT、Contiki-NG 及至少一个不同构建结构的 C/C++ 项目上重复核心任务。每个项目冻结 commit、toolchain、构建 Target、submodule 和问题集；问题同时覆盖通用符号导航、构建/配置、函数指针、跨模块流程和项目文档。该阶段裁决收益是否只来自 WiFiDemo 文件布局或预先熟悉的问题，并记录安装成功率、索引时间、增量更新时间、语言/构建适配量和失败模式。

**阶段三：公司内部真实项目。** 在权限允许的冻结快照上使用真实开发/维护问题，而不是把 WiFiDemo 题目改名后复用。由不了解实验臂的领域专家建立或复核 gold，Agent 答案必须给出内部可点击的源码/文档证据；代码和索引保持本地，模型、日志留存和许可证进入采用审计。除正确率与成本外，还测首次接入工作量、每日增量维护、错误知识被工程师采信的风险和团队实际节省时间。

最终选型按三道门裁决：

1. **事实硬门槛**：Target、宏、源码位置、Event/Message 和 provenance 任一关键项持续失败即淘汰。
2. **任务净收益**：分别比较 RQ1、RQ2 及复杂行为题的 Agent 正确率、证据完整率、时间和 Token；不以简单题优势掩盖复杂题失败。
3. **工程采用性**：在效果置信区间接近时，再比较离线运行、许可证、索引/增量成本、可审计性和适配维护量，选定单一主方向或“轻量默认 + 深分析按需”的组合。

预注册问题定义覆盖 Target occurrence、宏、直接/间接调用、Host/Device Event、领域到代码、代码到流程、链接失效、端到端 Agent、外部 C 泛化、资源和许可证，详见 [Benchmark Backlog](benchmark-backlog.md)。正式运行前应把该 Backlog 的旧条件映射同步为本节 C0–C5，避免评分问题与实验臂定义漂移。

### 9.3 指标必须分层

- **事实准确性**：entity/edge/link precision、recall、F1，Target leakage，source-location accuracy。
- **检索效率**：Recall@K、MRR、context yield、Token、工具调用、P50/P95 时延和索引资源。
- **最终 Agent 正确性**：任务通过率、证据完整率、unsupported claims、abstention、反事实敏感性。
- **新鲜度**：stale detection、链接修复 precision/recall、错误沿用率、误更新率。

不能用单一总分让速度补偿事实错误；Agent “看过”正确文件也不等于最终“用对”证据。

### 9.4 有效性威胁

1. **来源偏差**：CodeGraph、RepoDoc、RIG、codebadger、QLCoder 等数据多为作者或第一方评估，尚缺独立复现。
2. **任务差异**：文档 QA、Java CVE 查询、通用仓库架构问答与 WiFi C 的指标不可直接排名。
3. **版本漂移**：滚动项目、模型、Agent scaffold 和查询工具会改变结果；必须固定 commit 与配置。
4. **Ground truth 风险**：复杂指针、宏和事件路径需要编译器、静态分析、运行 probe 与双人复核交叉建立 gold。
5. **生成知识污染**：高可读性不等于高真实性；必须测无证据主张、错误链接与 stale 内容。
6. **外部有效性**：WiFiDemo 是结构化 Demo，不代表总体；开源项目可能缺少公司的宏规模、历史文档和保密约束，内部单项目又可能带组织特例，因此三类项目结果必须分别报告。
7. **Skill 泄漏**：C3 若包含函数流程、问题答案或由 gold 反推的归属，会人为抬高效果；必须在运行前冻结允许字段并审计内容。
8. **完整工具公平性**：Understand Anything 与 Graphify 的原生能力边界不同；统一输入和预算不代表等价实现，任何外接补强都必须作为新实验臂公开，而不能隐藏在适配器中。

## 10. 结论

本轮调研不支持直接选择某个工具，但已经得到比预设完整方案更清晰的决策基础：

1. 面向 Agent 的知识图谱要同时回答领域到代码与代码到解释。
2. 为此，代码知识、文档/领域知识、代码—文档双向链接缺一不可；这是必要能力集合，不是已证明的充分条件。
3. CodeGraph、Serena/SCIP 与 Joern/codebadger 都属于代码知识方案，区别是导航和程序分析深度，不应被割裂讨论。
4. Graphify 与 Understand Anything 同时跨越多个类别，应在首轮分别评估其代码图、生成文档和链接策略；RepoDoc 保留为文档覆盖、影响传播与增量更新的方法参考，LLM-Wiki/WiCER 只代表文档知识管理。
5. 对 WiFi MAC，最关键的额外约束是 Target-specific 构建事实、宏/间接调用以及 Host/Device Event 边界。
6. 当前最合理的收敛是比较基础 grep、CodeGraph 轻量图、Joern 深度图、基础架构事实 Skill，以及 Understand Anything/Graphify 两个完整能力候选；按 WiFiDemo、开源项目、内部真实项目三阶段验证后，再选定主方向或按需组合。

如果后续结果显示多个方案效果接近，应优先以开放许可证和可离线复现的开源组件构建最终方案；在此之前，不把任何候选写成赢家。
