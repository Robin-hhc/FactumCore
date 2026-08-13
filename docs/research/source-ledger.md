# 来源与证据台账

访问截止日期：2026-08-13

## 1. 用途

本文件是 `research.md` 中外部事实、数字和能力声明的唯一来源台账。来源必须先完成原文核验，再进入方案档案、证据矩阵和论文正文。搜索结果页、二手摘要和无法定位原始语境的转述不登记为正文证据。

## 2. 来源编号

来源按首次登记顺序使用稳定编号：`S001`、`S002`、`S003`……。编号只表示台账身份，不代表证据等级或推荐顺序。来源被拒绝后保留编号和拒绝原因，避免后续重复采用。

## 3. 核验状态

- `discovered`：已发现原始来源，但尚未完整阅读与核对声明。
- `primary-read`：已阅读与研究问题相关的原文章节、方法、实验和限制。
- `claim-verified`：正文拟使用的声明已在原文定位，并记录完整实验语境。
- `rejected`：不允许支撑核心结论；必须记录原因，例如二手转述、数据语境缺失、版本过旧或营销声明不可核验。

只有 `claim-verified` 来源可以支撑正文中的数字结论。`primary-read` 可以用于技术定义、接口事实和限制说明，但不得产生未登记的性能数字。

## 4. 来源类型与证据用途

| 来源类型 | 可证明内容 | 不可单独证明内容 |
|---|---|---|
| 独立、可复现实验 | 对明确样本、模型、基线和指标的相对效果 | 未覆盖语言、项目结构或新版本上的效果 |
| 同行评审论文或公开预印本 | 论文实验范围内的方法、数据和限制 | 工业生产成熟度或当前项目维护状态 |
| AI 公司官方工程文章 | 产品采用方式、生产架构、治理和上下文设计经验 | 在 WiFi MAC 或其他未测场景中的准确率优势 |
| 开源项目第一方 Benchmark | 项目在其公开方法和样本下报告的结果 | 独立优越性或不同指标之间的直接排名 |
| 开源项目官方功能说明 | 当前接口、数据表示、许可证、安装和维护事实 | 未公开测试的准确率、召回率和 Agent 任务收益 |
| 经典基础论文 | 仍被当前系统使用的概念、表示和算法基础 | 当前工具版本、性能、维护状态和 Agent 效果 |

## 5. 单条来源记录格式

每个来源必须按以下顺序记录：

```text
### Sxxx — 标题
- 状态：discovered | primary-read | claim-verified | rejected
- 发布日期：YYYY-MM-DD；无法确定日时保留已核验的年月
- 访问日期：YYYY-MM-DD
- 来源类型：独立实验 | 论文 | 公司官方实践 | 项目第一方 Benchmark | 项目官方功能说明 | 经典基础论文
- 发布者/作者：原始发布实体
- 原始 URL：直接指向论文、官方文章、官方文档或项目材料
- 独立属性：independent | first-party | company-practice | foundational
- 研究对象：代码仓、任务或系统
- 样本与语言：仓库数、任务数、样本数、语言和项目类型
- 模型/Agent：名称、版本和框架；不适用时写 not-applicable
- 对照基线：原文定义的基线；无对照时写 none
- 指标：原文指标名称和方向
- 可引用声明：准备进入正文的准确转述
- 数字与语境：数字、分母、样本、模型、预算和条件
- 限制：作者声明与本研究识别的外部有效性限制
- WiFi MAC 相关性：直接 | 间接 | 基础定义
- 正文位置：章节和声明主题
```

## 6. 数字引用规则

1. 同一句中的数字、样本量和基线必须来自同一实验设置。
2. 不把项目第一方数据写成独立验证。
3. 不把案例数量少的演示改写为平均准确率或普遍效果。
4. 不跨论文合并不同定义的 accuracy、coverage、pass rate、F1、Token 和 tool calls。
5. 工具版本、模型、Agent scaffold 或预算不明时，数字不能用于候选排序。
6. 旧性能数据不能证明当前版本；旧资料只在持续相关性被说明后用于基础定义。

## 7. 当前登记状态

台账从执行计划 Task 3 开始逐条登记来源。本节只记录状态统计，不预留未核验来源：

| 状态 | 数量 |
|---|---:|
| discovered | 0 |
| primary-read | 18 |
| claim-verified | 12 |
| rejected | 0 |

## 8. 已登记来源

### S001 — Agent Retrieval Bench: Evaluating Repository Context Retrieval for Coding Agents

- 状态：claim-verified
- 发布日期：2026-07-27
- 访问日期：2026-08-13
- 来源类型：论文、独立实验
- 发布者/作者：Bowen Qin、Yi Xie
- 原始 URL：https://arxiv.org/abs/2607.24882；https://agent-retrieval-bench.github.io/
- 独立属性：independent
- 研究对象：面向编码 Agent 的仓库文件级上下文检索
- 样本与语言：427 个样本、25 个开源仓库、308 个冻结的 base-commit 快照、392,000 个文件、790 万个 chunk；论文摘要未声明包含嵌入式 C 仓库
- 模型/Agent：词法检索、RepoMap、开源 embedding、选择性拒答以及记录的 Agent 上下文选择轨迹
- 对照基线：上述检索族互为对照
- 指标：sample-weighted MRR、Recall@20、8K Token 预算下的 context yield、file F1、选择性检索成功率
- 可引用声明：在该基准上不存在全面占优的单一检索族；语义向量、词法与结构化 RepoMap 呈互补关系。
- 数字与语境：Qwen3-Embedding-4B 在正样本 sample-weighted MRR 最好，Qwen3-Embedding-8B 在 Recall@20 最好，RepoMap 在 8K Token 预算下 context yield 最好；记录的 Agent 轨迹在 27%–35% 样本上未命中任何 gold file。数字只适用于论文的 427 样本和冻结语料。
- 限制：结果测量上游文件检索而不是领域问答或程序语义正确性；任务级胜者变化；50 个自然 no-gold 样本上的简单阈值校准未改善选择性成功率；未验证 WiFi MAC 的宏、Target 或 Host/Device 语义。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章检索基线、第 7 章待验证问题

### S002 — CORE-Bench: A Comprehensive Benchmark for Code Retrieval in the Era of Agentic Coding

- 状态：claim-verified
- 发布日期：2026-06-10
- 访问日期：2026-08-13
- 来源类型：论文、独立实验
- 发布者/作者：CORE-Bench 论文作者组
- 原始 URL：https://arxiv.org/abs/2606.11864
- 独立属性：independent
- 研究对象：传统代码搜索、issue-to-edit 定位与 broader-context 检索
- 样本与语言：超过 180,000 个查询、106,000 个 broader-context relevance 标注；由代码搜索任务与 SWE-bench 系列实例构成
- 模型/Agent：代表性 embedding 模型
- 对照基线：传统代码搜索任务与 Agent 场景中的多级检索任务
- 指标：论文定义的检索性能指标；本阶段只引用任务间相对变化，不跨论文抄录未核验的单项分数
- 可引用声明：代表性 embedding 模型从传统代码搜索迁移到 issue-to-edit 和 broader-context 等 Agent 检索时性能明显下降，传统语义检索分数不能替代真实仓库上下文评估。
- 数字与语境：语料规模超过 180,000 个查询和 106,000 个 broader-context relevance 标注；性能结论限定于论文的分层任务和模型集合。
- 限制：论文样本来自通用开源软件与 SWE-bench 系列，不直接证明 C 宏、多 Target 和领域知识链接能力。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章检索基线、第 9 章外部有效性威胁

### S003 — ContextBench: A Benchmark for Context Retrieval in Coding Agents

- 状态：claim-verified
- 发布日期：2026-02-05
- 访问日期：2026-08-13
- 来源类型：论文、独立实验
- 发布者/作者：Han Li 等
- 原始 URL：https://arxiv.org/abs/2602.05892；https://euniai.github.io/ContextBench/
- 独立属性：independent
- 研究对象：编码 Agent 在 issue resolution 中探索和实际使用上下文的过程
- 样本与语言：1,136 个 issue-resolution 任务、66 个仓库、8 种语言，每个任务带人工标注 gold context
- 模型/Agent：4 个 frontier LLM、5 个 coding agent
- 对照基线：不同模型和 Agent scaffold
- 指标：context recall、precision、efficiency，以及 explored/utilized context 差异
- 可引用声明：该实验中 Agent 普遍偏向 recall 而非 precision，并且被探索的上下文与最终被使用的上下文存在明显差距；复杂 scaffold 只带来有限增益。
- 数字与语境：1,136 个任务、66 个仓库、8 种语言、4 个模型、5 个 Agent；不将论文中的“有限增益”外推为所有 Agent 架构的普遍定律。
- 限制：gold context 仍面向 issue resolution，不是领域知识图谱正确性；未公开覆盖 WiFi MAC 的构建变体。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章检索基线、第 7 章 precision/recall 与证据利用率

### S004 — Aider Repository Map 官方文档

- 状态：primary-read
- 发布日期：持续更新；相关设计文章发布于 2023-10-22
- 访问日期：2026-08-13
- 来源类型：项目官方功能说明
- 发布者/作者：Aider 项目
- 原始 URL：https://aider.chat/docs/repomap.html；https://aider.chat/2023/10/22/repomap.html；https://github.com/Aider-AI/aider/blob/main/LICENSE.txt
- 独立属性：first-party
- 研究对象：为 LLM 构造受 Token 预算约束的仓库结构摘要
- 样本与语言：官方文档展示 Aider 自身仓库；语言支持由 Tree-sitter 解析器提供，本文不据此声明 C 宏语义支持
- 模型/Agent：Aider 与其所连接的 LLM
- 对照基线：none
- 指标：none
- 可引用声明：RepoMap 抽取文件中的关键符号与定义行，以文件依赖图做图排序，并在活跃 Token 预算内选择上下文；`--map-tokens` 默认 1k；项目许可证为 Apache-2.0。
- 数字与语境：1k 是产品默认配置，不是效果指标；S001 的独立基准另行测量 RepoMap 类方法。
- 限制：它是上下文压缩和导航组件，不是可查询的全量程序语义数据库，也没有显式领域知识、Target、revision、provenance 或 confidence 模型。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章结构化检索组件

### S005 — Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP

- 状态：claim-verified
- 发布日期：2026-03-28
- 访问日期：2026-08-13
- 来源类型：论文、项目第一方 Benchmark
- 发布者/作者：Martin Vogel 等
- 原始 URL：https://arxiv.org/abs/2603.27277
- 独立属性：first-party
- 研究对象：Tree-sitter 持久代码知识图与 MCP 驱动的代码探索
- 样本与语言：31 个真实仓库；论文版本解析 66 种语言
- 模型/Agent：论文中的 graph agent 与 file-exploration agent
- 对照基线：逐文件探索 Agent
- 指标：answer quality、Token、tool calls，以及 graph-native query 表现
- 可引用声明：论文报告的结构图方案以较低 Token 和工具调用开销换取了低于逐文件探索 Agent 的总体答案质量，但在图原生查询上具有优势。
- 数字与语境：31 个仓库上，Codebase-Memory 报告 83% answer quality，对照为 92%；Token 为对照的约 1/10，工具调用为对照的约 1/2.1；在 31 种语言中的 19 种，其 hub detection 和 caller ranking 匹配或超过对照。该数据由项目作者给出，不是独立复现。
- 限制：论文是 10 页预印本；answer quality 的含义不能与检索 MRR、程序分析 precision 或 WiFi 问答准确率互换；没有 Target-aware C 构建评估。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章结构化代码图、第 6 章适配性

### S006 — Codebase-Memory 官方 README 与发布材料

- 状态：primary-read
- 发布日期：持续更新；访问快照 2026-08-13
- 访问日期：2026-08-13
- 来源类型：项目官方功能说明
- 发布者/作者：DeusData/codebase-memory-mcp
- 原始 URL：https://github.com/DeusData/codebase-memory-mcp/blob/main/README.md；https://github.com/DeusData/codebase-memory-mcp/releases
- 独立属性：first-party
- 研究对象：本地持久代码图、混合 Tree-sitter/LSP 解析和 MCP 查询
- 样本与语言：当前 README 声明 158 种 Tree-sitter 语言，并为 C/C++ 等语言增加混合类型解析；本阶段未复现实测
- 模型/Agent：任意 MCP 客户端；无托管模型要求
- 对照基线：none
- 指标：none；论文性能证据单列于 S005
- 可引用声明：当前项目以 Tree-sitter 结构抽取加轻量跨文件类型解析形成持久图，公开 15 个 MCP 工具；README 明确说明 C/C++ 的跨文件 registry、宏、typedef、头/源链接、模板和方法解析范围；许可证为 MIT。
- 数字与语境：158 种语言和 15 个工具是当前项目能力声明，不是准确率；版本演进快于 S005 论文的 66 语言快照。
- 限制：C/C++ 支持表是第一方能力说明，尚无 WiFiDemo 上的准确率、宏配置隔离或实际编译命令评估；未见稳定的外部领域实体与代码证据 provenance 规范。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章项目档案、第 7 章待测项

### S007 — CodeGraph 官方 README、Benchmark、Release 与 License

- 状态：claim-verified
- 发布日期：Benchmark 重测于 2026-08-05；访问快照 2026-08-13
- 访问日期：2026-08-13
- 来源类型：项目第一方 Benchmark、项目官方功能说明
- 发布者/作者：colbymchenry/codegraph
- 原始 URL：https://github.com/colbymchenry/codegraph；https://github.com/colbymchenry/codegraph/releases；https://github.com/colbymchenry/codegraph/blob/main/LICENSE
- 独立属性：first-party
- 研究对象：本地 Tree-sitter/SQLite 代码图、跨文件解析、增量同步和 MCP 查询
- 样本与语言：Agent Benchmark 为 7 个开源仓库、7 种语言、每库 1 个架构问题、每个实验臂 4 次；另有 C/Redis 与 C++/LevelDB 的依赖覆盖测量
- 模型/Agent：Claude Code headless、Claude Opus 4.8；WITH/ WITHOUT CodeGraph
- 对照基线：保留 Read/Grep/Bash、禁用 CodeGraph CLI 的空 MCP 控制组
- 指标：工具调用、时间、文件读取、处理 Token、成本、会话末残留上下文；另有 resolved cross-file dependent coverage
- 可引用声明：CodeGraph 使用 Tree-sitter 抽取节点/调用/导入/继承边，SQLite+FTS5 持久化并增量同步；第一方实验显示结构图可显著降低单次架构问答探索开销，但会增加会话末残留上下文。
- 数字与语境：2026-08-05 的 7 仓、每臂 4 次中位数实验报告工具调用减少 88%、时间减少 53%、处理 Token 减少 62%、成本减少 44%；同一材料报告会话末残留检索上下文约增加 80%。C/Redis 的跨文件 dependent coverage 为 92.2%，C++/LevelDB 为 94.8%；coverage 分母是“含符号且至少有一个已解析跨文件依赖的源文件”，不是调用边 precision 或 recall。
- 限制：所有数字均为第一方；每库只有 1 个架构问题，且无 WiFi MAC、预处理配置或领域知识问答；动态分派和框架规则可能合成边，需保留边来源；许可证为 MIT。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章项目档案、第 6 章适配性、第 7 章待测项

### S008 — GitNexus 官方 README 与 License

- 状态：primary-read
- 发布日期：持续更新；访问快照 2026-08-13
- 访问日期：2026-08-13
- 来源类型：项目官方功能说明
- 发布者/作者：nxpatterns/gitnexus（历史仓库路径 abhigyanpatwari/GitNexus）
- 原始 URL：https://github.com/nxpatterns/gitnexus；https://github.com/abhigyanpatwari/GitNexus/blob/main/LICENSE
- 独立属性：first-party
- 研究对象：本地/浏览器端 Tree-sitter + LadybugDB 代码知识图、聚类、执行流程、混合搜索与 MCP
- 样本与语言：官方表列 C 与 C++，但两者不支持 imports/named bindings，支持项集中在 export、类型、构造推断等；无公开可比 Benchmark
- 模型/Agent：多种 MCP 客户端；Web UI 可接 LLM
- 对照基线：none
- 指标：none
- 可引用声明：项目把文件树、Tree-sitter AST、跨文件解析、功能聚类、执行流程和混合搜索组合为本地知识图，并提供 stdio MCP、只读模式、仓库 allowlist 和响应 Token 预算。
- 数字与语境：不登记性能数字；README 的功能表只证明项目声明的支持面。
- 限制：许可证是 PolyForm Noncommercial 1.0.0，不满足无条件商业采用的开源许可证预期；C/C++ 表中缺少 import 解析；无 WiFi MAC、多 Target 或代码—领域知识链接评估。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章项目档案、第 8 章直接采用排除项

### S009 — Understand Anything 官方 README、Release 与 License

- 状态：primary-read
- 发布日期：v2.9.0 发布于 2026-07-10；访问快照 2026-08-13
- 访问日期：2026-08-13
- 来源类型：项目官方功能说明
- 发布者/作者：Egonex-AI/Understand-Anything
- 原始 URL：https://github.com/Egonex-AI/Understand-Anything/blob/main/README.md；https://github.com/Egonex-AI/Understand-Anything/releases
- 独立属性：first-party
- 研究对象：Tree-sitter 确定性结构图与 LLM 语义/领域图的混合分析
- 样本与语言：官方 README 未给出可用于本文排序的 C/C++ 精度样本；v2.1.0 引入 business domain graph，v2.3.1 扩展知识实体、claim、source 和语义边
- 模型/Agent：5 个结构/架构 Agent，`understand-domain` 增加领域分析 Agent；支持云端或本地模型
- 对照基线：none
- 指标：none
- 可引用声明：项目明确把 Tree-sitter 产生的可复现结构事实与 LLM 产生的摘要、标签、架构层和业务领域映射分层；结构变化使用 fingerprint 做增量更新，领域映射由 LLM 推断。
- 数字与语境：项目提醒首次全仓分析可能消耗大量 Token，后续默认仅重分析变化文件；这不是量化性能结论。
- 限制：没有公开的结构边或领域映射准确率 Benchmark；领域知识主要由 LLM 从代码生成，未见外部领域文档、Target/revision、claim provenance、confidence 和冲突生命周期的完整治理；许可证为 MIT。
- WiFi MAC 相关性：间接
- 正文位置：第 5 章代码—领域链接路线、第 7 章待验证问题

### S010 — Clang Tooling、Compilation Database 与 LLVM IR 官方文档

- 状态：primary-read
- 发布日期：持续更新；访问版本 Clang/LLVM 24.0.0git
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：LLVM Project
- 原始 URL：https://clang.llvm.org/docs/JSONCompilationDatabase.html；https://clang.llvm.org/docs/LibTooling.html；https://clang.llvm.org/docs/LibASTMatchers.html；https://llvm.org/docs/LangRef.html；https://llvm.org/docs/SourceLevelDebugging.html；https://llvm.org/docs/MemorySSA.html；https://llvm.org/docs/AliasAnalysis.html
- 独立属性：first-party
- 研究对象：C/C++ 编译命令重放、AST 查询、LLVM IR、源码映射、alias 与 MemorySSA
- 样本与语言：官方规范与接口文档；不提供 WiFi MAC 效果样本
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：none
- 可引用声明：`compile_commands.json` 的每个 command object 表示一个 translation unit 的一种编译方式，同一文件可以因不同配置出现多条 command；LibTooling/AST Matchers 可基于这些命令访问 AST 和 source location。LLVM IR 提供 CFG/SSA 等分析载体，debug metadata 可把 IR instruction 映回文件和行；MemorySSA 是函数内的 memory def-use/use-def 表示，alias API 返回 Must/Partial/May/NoAlias 等保守结果。
- 数字与语境：文档版本号和枚举数量只描述接口，不是准确率数据。
- 限制：Clang AST 是 translation-unit 视角；LLVM IR 会丢失或降低部分源码级构造可读性，优化也会改变 IR 形态；MemorySSA 明确是 intraprocedural。上述组件不是现成的知识存储或 Agent 查询服务。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章编译器原生路线、第 6 章 Target-aware 输入

### S011 — scip-clang 与 SCIP 官方材料

- 状态：primary-read
- 发布日期：SCIP v0.7.1 发布于 2026-04-14；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：Sourcegraph/scip-code
- 原始 URL：https://github.com/sourcegraph/scip-clang；https://github.com/scip-code/scip
- 独立属性：first-party
- 研究对象：基于 Clang 21 的 C/C++/CUDA 精确代码索引与开放 SCIP 交换格式
- 样本与语言：官方展示 Boost、Chromium、LLVM 等导航案例；未提供可比较 accuracy Benchmark
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：资源估算约每个 TU 2 MB 临时空间、每核约 2 GB RAM；属于部署建议而非效果数据
- 可引用声明：scip-clang 从 JSON compilation database 生成 `index.scip`，支持 include、macro、type 的 references 和跨仓导航；SCIP 协议为 Apache-2.0。
- 数字与语境：资源估算是项目建议，不能外推到 WiFiDemo；预编译头不受支持。
- 限制：功能目标是代码导航与 occurrence，不提供 CFG、dataflow、taint 或 slice；Sourcegraph 完整服务端并非全部开源，但 SCIP 格式和 scip-clang 源码可独立检查。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章跨文件语义索引、第 6 章代码身份

### S012 — Kythe Compilation Database 与 Schema 官方文档

- 状态：primary-read
- 发布日期：持续更新；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：Kythe Project
- 原始 URL：https://kythe.io/docs/kythe-compilation-database.html；https://kythe.io/docs/schema-overview.html；https://kythe.io/docs/schema/writing-an-indexer.html；https://kythe.io/docs/schema/indexing-generated-code.html；https://github.com/kythe/kythe
- 独立属性：first-party
- 研究对象：可插拔代码索引、hermetic compilation unit、anchor/semantic node/cross-reference schema
- 样本与语言：官方提供 C++、Go、Java indexer；无 WiFi MAC 效果样本
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：none
- 可引用声明：Kythe 的 compilation database 捕获一次真实 compile action、输入、依赖和 flags，并按 revision、target、source、corpus、language 建索引；schema 用 anchor 把定义、引用和 call site 定位到源码跨度，并用 VName 表达语义身份。生成代码可通过 `generates`/`imputes` 边与源实体保持不同身份后再连接。
- 数字与语境：SHA-256 content addressing、字段与边类型是数据模型事实，不是效果数据。
- 限制：核心目标是交叉引用和代码导航；默认 schema 不提供通用 CFG、dataflow 或 slice；构建抽取与服务管线复杂，领域知识需要扩展 schema 和消费端支持。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章可查询交叉引用、第 5 章代码—领域链接模式

### S013 — CodeQL C/C++ 文档、查询库与 CLI 许可

- 状态：primary-read
- 发布日期：CodeQL CLI v2.25.5 发布于 2026-05-22；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：公司官方实践、项目官方功能说明
- 发布者/作者：GitHub
- 原始 URL：https://github.com/github/codeql；https://github.com/github/codeql-cli-binaries；https://codeql.github.com/docs/codeql-language-guides/advanced-dataflow-scenarios-cpp/；https://docs.github.com/en/code-security/concepts/code-scanning/codeql/query-packs
- 独立属性：company-practice
- 研究对象：把代码编译为可查询数据库，并以 QL 定义 C/C++ dataflow/taint 与安全查询
- 样本与语言：C/C++ 为正式 query pack；本阶段未引用漏洞检测效果数字
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：none
- 可引用声明：CodeQL 的开源查询/库仓库采用 MIT，C/C++ dataflow 区分 pointer value 与 pointee，并允许 query/model pack 扩展库/框架语义；CLI/engine 单独授权，闭源代码和自动化工程使用需要相应商业许可。
- 数字与语境：版本与 pack 种类是产品事实，不是准确率数据。
- 限制：核心 engine 不开源且内部闭源 WiFi 代码采用受许可约束；database extractor 和事实 schema 不是自由替换的开放引擎；主要面向安全分析，不是 Agent-ready 领域知识系统。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章声明式代码数据库、第 8 章许可约束

### S014 — Modeling and Discovering Vulnerabilities with Code Property Graphs

- 状态：claim-verified
- 发布日期：2014-05
- 访问日期：2026-08-14
- 来源类型：经典基础论文
- 发布者/作者：Fabian Yamaguchi、Nico Golde、Daniel Arp、Konrad Rieck；IEEE Symposium on Security and Privacy
- 原始 URL：https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf；https://ieeexplore.ieee.org/document/6956589
- 独立属性：foundational
- 研究对象：把 AST、CFG 和 PDG 合并为 property graph，并以 traversal 表达漏洞模板
- 样本与语言：Linux kernel C 源码案例
- 模型/Agent：not-applicable
- 对照基线：论文中的代码审计方法；本研究不复述未重新核验的横向基线分数
- 指标：新发现漏洞数量和查询案例
- 可引用声明：CPG 的经典定义是 AST、CFG 和 program dependence graph 的联合表示，而不是任意“节点+边”的代码图；论文在 Linux kernel 案例中报告发现 18 个此前未知漏洞。
- 数字与语境：18 是论文作者在 2014 Linux kernel 案例中的发现数，不是现代 CPG 的通用准确率，也不能比较 Joern 与其他当前工具。
- 限制：旧论文用于定义表示及历史有效案例；不证明当前 frontend、跨 TU、宏、多 Target、Agent 接口或维护状态。持续相关性由 S015/S016 的 2026 活跃实现与规范补充。
- WiFi MAC 相关性：基础定义
- 正文位置：第 4 章 CPG 定义、第 9 章旧引用用途限定

### S015 — Joern、CPG Specification 与官方查询文档

- 状态：primary-read
- 发布日期：Joern v4 系列持续发布；检索到 v4.0.548（2026-05-27）
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：Joern/Qwiet AI 开源项目
- 原始 URL：https://github.com/joernio/joern；https://docs.joern.io/code-property-graph/；https://docs.joern.io/frontends/；https://docs.joern.io/cpg-slicing/；https://docs.joern.io/dataflow-semantics/；https://cpg.joern.io/
- 独立属性：first-party
- 研究对象：多语言 CPG、Scala DSL、dataflow、custom semantics 与 JSON slicing
- 样本与语言：官方支持 C/C++ 等多种 source/binary frontend；未发现宏密集多 Target C 的公开准确率数据
- 模型/Agent：not-applicable；可通过 server/脚本由 Agent 封装
- 对照基线：none
- 指标：none
- 可引用声明：Joern CPG 提供 AST、call/control/dataflow overlays 与 CPGQL；`joern-slice` 可导出 interprocedural backward data-flow slice 或 usage slice 为 JSON，并携带 file/line/column。未建模 external method 时默认数据流语义为保守传播，custom semantics 可提高精度但引入人工模型依赖。
- 数字与语境：默认 slice depth 20 是 CLI 默认值，不是分析完整性指标。
- 限制：当前官方 frontend 总览没有证明读取 `compile_commands.json` 并为同一源码的多个真实编译配置建立隔离 occurrence；目录级 import 和类型恢复不能替代真实 Target 编译；缺少 Agent/WiFiDemo 对比数据。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章 CPG 候选之一、第 6 章适配性

### S016 — Fraunhofer AISEC Code Property Graph 官方材料

- 状态：primary-read
- 发布日期：文档更新于 2026-06；当前 README 示例版本 9.0.2
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：Fraunhofer AISEC
- 原始 URL：https://fraunhofer-aisec.github.io/cpg/；https://fraunhofer-aisec.github.io/cpg/CPG/impl/language/；https://fraunhofer-aisec.github.io/cpg/GettingStarted/query/；https://fraunhofer-aisec.github.io/cpg/CPG/specs/dfg-function-summaries/；https://github.com/Fraunhofer-AISEC/cpg
- 独立属性：first-party
- 研究对象：可嵌入 library 的多语言 CPG、EOG/DFG/CDG、passes 和 query API
- 样本与语言：C/C++（README 标注 C17）、LLVM IR 等；无 WiFi MAC 效果样本
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：none
- 可引用声明：该项目把 frontend AST 转换与后续 analysis passes 分离，提供 C/C++、LLVM IR、dataflow、reachability、constant propagation、函数摘要和 interprocedural query API；可作为库使用或导出 Neo4j，采用 Apache-2.0。
- 数字与语境：版本、语言数和 API 是功能事实，不是准确率。
- 限制：C/C++ frontend 基于 Eclipse CDT 依赖，未证明真实 compilation database、多 Target occurrence 或函数指针解析精度；外部函数摘要与 inference rules 必须记录来源，否则可能与 parser 事实混淆。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章 CPG 对照、第 5 章 overlay/领域扩展

### S017 — SVF Static Value-Flow Analysis 官方项目与文档

- 状态：primary-read
- 发布日期：SVF 3.3 发布于 2026-05-20
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明、经典论文实现
- 发布者/作者：SVF-tools；Yulei Sui 等
- 原始 URL：https://github.com/SVF-tools/SVF；https://svf-tools.github.io/SVF/；https://svf-tools.github.io/SVF-doxygen/html/classSVF_1_1PointerAnalysis.html
- 独立属性：first-party
- 研究对象：LLVM-based pointer analysis、value-flow、ICFG、Memory SSA 和 source-sink bug detection
- 样本与语言：LLVM-based C/C++；当前项目声明支持 LLVM 21
- 模型/Agent：not-applicable
- 对照基线：相关论文包含算法比较，但本阶段不跨版本引用性能数字
- 指标：none registered for ranking
- 可引用声明：SVF 提供 field/flow/context-sensitive pointer analysis、call graph、ICFG、constraint/value-flow graph、interprocedural Memory SSA，并显式维护 callsite 到 function-pointer target 集合；主项目许可证为 AGPL-3.0-or-later，且包含单独授权的第三方组件。
- 数字与语境：版本号和分析类型是功能事实；旧论文只用于算法基础，不证明当前 WiFiDemo 表现。
- 限制：输入是 LLVM IR，需另外保存 source/Target identity；不是通用图数据库、领域知识系统或现成 Agent API；分析规模、precision 和构建链兼容性必须实测。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章深度 dataflow/函数指针路线、第 6 章能力补足

### S018 — Frama-C、Eva 与 Slicing 官方材料

- 状态：primary-read
- 发布日期：Frama-C 33.0 beta 发布于 2026-06-25；官方用户手册持续更新
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明
- 发布者/作者：CEA List/Inria Frama-C team
- 原始 URL：https://frama-c.com/；https://frama-c.com/html/news.html；https://www.frama-c.com/fc-plugins/eva.html；https://frama-c.com/download/frama-c-user-manual.pdf；https://www.frama-c.com/html/contact.html
- 独立属性：first-party
- 研究对象：C 源码的抽象解释、ACSL 规格、PDG/依赖、impact 与程序切片
- 样本与语言：ISO C；C++ frontend 为实验性，不影响本项目 C 重点
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：Eva 的“无 alarm 则相应运行时错误不会发生”属于 soundness 契约，不是经验准确率
- 可引用声明：Frama-C 以统一 C AST 和 ACSL 作为插件协作媒介；Eva 提供 value analysis，Slicing 使用 Eva 与 functional dependency 结果生成满足准则的程序切片；项目为 LGPL，2026 仍活跃。
- 数字与语境：release/version 是维护事实，不报告跨工具精度数字。
- 限制：严格分析依赖完整环境、入口、库模型、volatile/asm 等建模；可能需要 ACSL 人工规格；输出不是默认的 Agent 查询图，且多 Target 必须分别预处理/分析。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章 C 专用抽象解释与切片、第 6 章验证能力

### S019 — Semgrep Community Edition 与 Pro Engine 官方材料

- 状态：primary-read
- 发布日期：Semgrep v1.164.0 发布于 2026-05-27；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：公司官方实践、项目官方功能说明
- 发布者/作者：Semgrep Inc.
- 原始 URL：https://github.com/semgrep/semgrep；https://semgrep.dev/products/semgrep-vs-ce；https://semgrep.dev/docs/writing-rules/experiments/join-mode/overview；https://semgrep.dev/products/pro-engine/
- 独立属性：company-practice
- 研究对象：类源码 pattern DSL、规则化静态检查、taint 与跨文件分析
- 样本与语言：官方声明 C/C++ 支持；本阶段不采用营销页效果百分比作为候选排序证据
- 模型/Agent：可运行本地 MCP，但核心分析不依赖 LLM
- 对照基线：Community Edition 与 proprietary Pro Engine 的能力边界
- 指标：none registered for ranking
- 可引用声明：Semgrep CE 为 LGPL-2.1，适合轻量规则检查，但官方明确其 dataflow 限于单函数/单文件；C/C++ 的 interfile/interprocedural deep analysis 属于 proprietary Pro Engine。
- 数字与语境：语言数、规则数和营销提升数字不进入本文排序，因为实验设置与 WiFi MAC 不可比。
- 限制：开源 CE 无法承担跨 Host/Device/Target 的深层语义；Pro 能力与许可证不符合“优先开源实现”的默认方向；pattern finding 也不是稳定代码事实数据库。
- WiFi MAC 相关性：间接
- 正文位置：第 4 章声明式规则路线、第 8 章能力/许可排除

### S020 — PhASAR LLVM-based Static Analysis Framework 官方材料

- 状态：primary-read
- 发布日期：持续更新；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：项目官方功能说明、经典论文实现
- 发布者/作者：Paderborn University/Fraunhofer IEM Secure Software Engineering Group
- 原始 URL：https://github.com/secure-software-engineering/phasar；https://link.springer.com/chapter/10.1007/978-3-030-17465-1_22
- 独立属性：first-party
- 研究对象：LLVM IR 上的 IFDS/IDE/WPDS、ICFG、points-to、taint 和 path reconstruction
- 样本与语言：LLVM-based C/C++；当前项目支持 LLVM 16–22.1
- 模型/Agent：not-applicable
- 对照基线：旧论文包含 case study；本阶段不以旧性能数字排序当前实现
- 指标：none registered for ranking
- 可引用声明：PhASAR 允许以 API 定义任意 interprocedural data-flow problem，提供多种 call-graph、alias/points-to、ICFG、IFDS/IDE、taint 和具体 path reconstruction；source/sink 可来自 IR annotation、JSON 或 callback；许可证为 MIT。
- 数字与语境：LLVM 版本范围和功能列表是当前官方材料中的接口事实；2019 论文只用于设计持续性与许可证补充。
- 限制：需要把每个 Target 构建为 LLVM IR；不是现成知识数据库或 MCP；source/sink JSON 是领域规则入口但必须另加 revision、Target、evidence 和审核治理。
- WiFi MAC 相关性：直接基础
- 正文位置：第 4 章 dataflow framework、第 5 章领域 source/sink 映射

### S021 — Graphify 官方仓库与概念文档

- 状态：primary-read
- 发布日期：概念文档更新于 2026-07-01；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：开源项目官方功能说明、项目第一方 Benchmark
- 发布者/作者：Graphify Labs
- 原始 URL：https://github.com/Graphify-Labs/graphify；https://graphify.com/concepts
- 独立属性：first-party
- 研究对象：以 Tree-sitter 解析代码、以 LLM 连接文档/媒体的混合知识图和 Agent Skill/MCP 接口
- 样本与语言：官方声明 36 种代码语言；README 的 memory Benchmark 不是代码—领域链接准确率实验
- 模型/Agent：文档语义阶段使用用户配置的模型；代码阶段不使用 LLM
- 对照基线：官方 LOCOMO/LongMemEval 对照，不用于 WiFi MAC 排序
- 指标：官方报告 memory recall/QA 指标，但没有 Target-aware C、领域边 precision 或失效修复指标
- 可引用声明：Graphify 将 AST 产生的代码边标为 `EXTRACTED`，模型产生的文档/语义边标为 `INFERRED`，不能完全消歧的边标为 `AMBIGUOUS`；`# WHY:`/ADR/RFC 引用可成为一等节点，结果可通过 Skill、CLI 或 MCP 查询。
- 数字与语境：README 中的 LOCOMO 与 LongMemEval 是通用 memory 数据集，不能证明 C 调用图或 WiFi 领域链接质量。
- 限制：Tree-sitter 代码边不等于真实 Target 编译事实；公开材料没有 stable semantic ID、revision/Target occurrence、人工审核优先级或源码重命名后的领域边修复准确率。
- WiFi MAC 相关性：间接
- 正文位置：混合图方案、软硬边分层和 provenance 标签

### S022 — Retrieval as Reasoning: Self-Evolving Agent-Native Retrieval via LLM-Wiki

- 状态：claim-verified
- 发布日期：2026-05-29
- 访问日期：2026-08-14
- 来源类型：论文
- 发布者/作者：Haoliang Ming、Feifei Li、Xiaoqing Wu、Wenhui Que；Tencent/WeChat
- 原始 URL：https://arxiv.org/abs/2605.25480；https://arxiv.org/html/2605.25480
- 独立属性：author-evaluation
- 研究对象：把原始资料编译成带目录、页面、双向链接、源引用和 Error Book 的可演化 Wiki
- 样本与语言：HotpotQA、MuSiQue、2WikiMultiHopQA 各前 500 个样本，以及 AuthTrace
- 模型/Agent：统一使用 GLM-5.1；embedding 为 Qwen3-Embedding-8B
- 对照基线：7 个闭卷、Dense RAG、GraphRAG/LightRAG/HippoRAG 2 等基线
- 指标：F1、AuthTrace judged accuracy、错误类别占比、延迟/工具调用
- 可引用声明：LLM-Wiki 相比最强图基线在三个多跳 QA 数据集提高 2.0–8.1 F1；AuthTrace 总体高 2.1 accuracy points，高多文档问题高 8.9 points，但单文档问题低 2.3 points。页面保存 source references 和双向 wikilinks；Error Book 对结构与内容错误执行发现、归因、约束、注入和重新验证。
- 数字与语境：实验是给定语料的文档问答，不是代码修改或 C 语义验证；dangling links 占检测错误的 29.1–63.8%，说明生成式链接本身需要持续校验。
- 限制：统一模型且主要为作者实验；source-grounded LLM verifier 仍不是确定性证明；更大的 query tool budget 与一次性编译成本没有被消除。
- WiFi MAC 相关性：间接架构证据
- 正文位置：Wiki 编译、双向领域链接、Error Book 生命周期

### S023 — WiCER: Wiki-memory Compile, Evaluate, Refine

- 状态：claim-verified
- 发布日期：2026-05-08
- 访问日期：2026-08-14
- 来源类型：论文、公开实验代码
- 发布者/作者：Juan M. Huerta
- 原始 URL：https://arxiv.org/abs/2605.07068；https://arxiv.org/html/2605.07068
- 独立属性：author-evaluation
- 研究对象：用诊断问题和失败驱动的重新编译，修复 Wiki 编译的信息丢失
- 样本与语言：17 个 RepLiQA 领域、每种条件合计 6,800 个问题；另有 30 篇 Policygenius 文章
- 模型/Agent：Claude Sonnet 用作 Wiki compiler；本地模型用于 full-context/KV cache；LLM-as-judge 评分
- 对照基线：RAG、raw full-context、三种 blind Wiki compression、WiCER 迭代
- 指标：1–5 answer quality、score-1 catastrophic rate、TTFT、压缩率、Token/成本
- 可引用声明：30 篇/67K token 的 curated context 得分 4.38 对 RAG 4.08，TTFT 快 7.3 倍；80 篇/55–95K token 时 full-context 因 attention dilution 低于 RAG（3.47 对 3.64）。blind compilation 得分 2.14–2.32、catastrophic rate 53–60%；1–2 次 WiCER 迭代恢复 80% 丢失质量并将 catastrophic failures 相对降低 55%。
- 数字与语境：每次 80 文档迭代约 130K API input、17K output、约 50 分钟；评估依赖近似 LLM-as-judge，不能外推为 WiFiDemo 效果。
- 限制：修复已知 probe 暴露的遗漏可能挤掉其他事实；17 个主题中一项无收益；不存在代码实体、Target 或编译语义。
- WiFi MAC 相关性：领域文档编译与重验证机制直接相关，代码语义间接
- 正文位置：原始资料—编译知识分层、失败驱动重验证

### S024 — Google ADK 与 AWS Agent Toolkit 的 Skills/Progressive Disclosure 官方材料

- 状态：primary-read
- 发布日期：Google 指南发布于 2026-04；AWS 文档访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：AI 公司官方实践
- 发布者/作者：Google Developers、Amazon Web Services
- 原始 URL：https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/；https://docs.aws.amazon.com/agent-toolkit/latest/userguide/skills.html
- 独立属性：company-practice
- 研究对象：Skill metadata、按需 instructions/references、scripts 与 MCP/API 工具分层
- 样本与语言：官方架构指南与 AWS 产品工作流；没有 WiFi MAC Benchmark
- 模型/Agent：Google ADK Agent；AWS-compatible coding agents
- 对照基线：monolithic prompt 与 progressive disclosure 的估算比较
- 指标：Google 示例的基线 context token 估算；无任务正确率
- 可引用声明：Google 将 Skill 分为约 100-token metadata、少于 5,000-token instructions 和按需 resources，10 个 Skill 的示例把基线 context 从约 10,000 降到约 1,000 token；AWS 将 `SKILL.md`、references、deterministic scripts 与运行时 MCP/API 分开，并在任务结束后释放 Skill 内容。
- 数字与语境：90% 是架构示例的 token 算术，不是受控 Agent 效果实验。
- 限制：官方资料证明工业设计选择和接口边界，不证明领域 Skill 被正确选择、内容当前有效或能改善 WiFi C 任务。
- WiFi MAC 相关性：间接架构证据
- 正文位置：按需上下文、Skill/Reference/Tool 分层

### S025 — GitHub Copilot Agentic Memory 官方设计与 A/B 数据

- 状态：claim-verified
- 发布日期：2026-01-15；访问快照 2026-08-14
- 访问日期：2026-08-14
- 来源类型：AI 公司官方实践、产品第一方 A/B
- 发布者/作者：GitHub；Tiferet Gazit
- 原始 URL：https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/；https://github.blog/changelog/2026-05-26-copilot-memory-has-more-controls-for-deletion-scope-and-the-copilot-cli/
- 独立属性：company-practice
- 研究对象：repository-scoped cross-agent memory、源码 citation、just-in-time verification、纠错与访问范围
- 样本与语言：真实 Copilot coding agent/code review 流量；样本量未公开
- 模型/Agent：GitHub Copilot coding agent、CLI、code review
- 对照基线：有 memory 与无 memory 的产品 A/B
- 指标：PR merge rate、review comment positive feedback、p-value
- 可引用声明：memory 保存 subject/fact/reason 与多个 `file:line` citations，使用前在当前 branch 实时核验；无效或矛盾 citation 触发修正，重新确认会刷新时间戳。GitHub 报告 coding-agent PR merge rate 90% 对 83%，review positive feedback 77% 对 75%，两者 p<0.00001。
- 数字与语境：A/B 未公开样本量、模型分层、任务构成或绝对因果机制；属于 GitHub 产品第一方数据，不可外推 WiFi MAC accuracy。
- 限制：公开数据没有 Target occurrence、typed domain edge 或自动 stale detection 的 precision/recall；目前 retrieval 以近期 memory 注入为主，未来 search/weighted prioritization 尚属计划。
- WiFi MAC 相关性：生命周期设计直接相关
- 正文位置：citation-backed memory、读时验证、冲突与作用域

### S026 — SWE-Bench 5G

- 状态：claim-verified
- 发布日期：2026-04-29
- 访问日期：2026-08-14
- 来源类型：论文、公开 Benchmark
- 发布者/作者：Jiao Chen、Jianhua Tang、Xiaotong Yang、Zuohong Lv
- 原始 URL：https://arxiv.org/abs/2604.26278；https://arxiv.org/html/2604.26278；https://huggingface.co/datasets/tenderzada/SWEBench5G
- 独立属性：author-evaluation
- 研究对象：真实开源 5G Core 缺陷修复与 3GPP 规格片段注入
- 样本与语言：free5GC、Open5GS、Magma 的 210 个验证实例；Go、C、Python；Skill A/B 子集 50 项
- 模型/Agent：Qwen3.5-Flash、Kimi-128k、GPT-4.1、Claude Sonnet 4；最多 5 轮反馈
- 对照基线：无规格与加入平均 350-token 规格文档的 paired A/B
- 指标：diagnosed、patch applied、resolved、Token overhead
- 可引用声明：四模型诊断率均超过 91%，但多轮 resolve 仅 10–30%。Claude Sonnet 4 的 50 项规格注入 A/B 总体由 24% 提升到 30%（+6 points，平均 +12% Token）；三类 specification-dependent bug 提升 +16.7 至 +25 points，六类 generic defensive bug 均为 0。
- 数字与语境：50 项 A/B 中各领域仅 4–8 项；142/210 个验证采用 diff-based intent test，不能与纯运行时测试等同。
- 限制：5G Core 不等于 WiFi MAC；规格摘要由研究者构造并附任务 implication，未评估错误规格、版本冲突或自动代码实体链接。
- WiFi MAC 相关性：直接邻域证据
- 正文位置：领域知识注入的条件收益和后续 Benchmark 设计

### S027 — SWE-Skills-Bench

- 状态：claim-verified
- 发布日期：2026-03-16
- 访问日期：2026-08-14
- 来源类型：论文、公开 Benchmark
- 发布者/作者：Tingxu Han、Yi Zhang、Wei Song、Chunrong Fang、Zhenyu Chen、Youcheng Sun、Lijie Hu
- 原始 URL：https://arxiv.org/abs/2603.15401；https://github.com/GeniusHTX/SWE-Skills-Bench
- 独立属性：author-evaluation; preprint
- 研究对象：真实 GitHub 工程任务中 Skill 注入的边际效用
- 样本与语言：49 个公开 SWE Skills、约 565 个固定 commit 任务、6 个工程子领域
- 模型/Agent：Claude Code + Claude Haiku 4.5；Ubuntu 24.04 CPU-only Docker；执行式 deterministic verifier
- 对照基线：每项任务 with-skill 与 without-skill paired condition
- 指标：pass rate、Token 开销、验收条件覆盖
- 可引用声明：39/49 Skills 没有 pass-rate 提升，平均仅 +1.2%；7 个专门 Skill 最高 +30%，3 个因版本不匹配最高下降 10%；Token 开销可在 pass rate 不变时最高增加 451%。
- 数字与语境：预印本明确标注 preliminary/work in progress；任务由公开 Skill 与生成的需求/测试配对，不代表所有真实维护任务。
- 限制：不同 Skill/仓库异质，平均数不能直接推断具体 WiFi Skill；结果支持“精确匹配、版本兼容、执行验证”，不支持全局否定 Skill。
- WiFi MAC 相关性：直接方法学证据
- 正文位置：Skill 选择、负收益、版本与 Token 成本

### S028 — Improving Code Localization with Repository Memory

- 状态：claim-verified
- 发布日期：2025-10-01；ICLR 2026 版本
- 访问日期：2026-08-14
- 来源类型：同行评审论文、Microsoft Research 官方页面
- 发布者/作者：Boshi Wang、Weijian Xu、Yunsheng Li、Mei Gao、Yujia Xie、Huan Sun、Dongdong Chen
- 原始 URL：https://arxiv.org/abs/2510.01003；https://openreview.net/pdf?id=8yjWLJy2eX；https://www.microsoft.com/en-us/research/publication/improving-code-localization-with-repository-memory/
- 独立属性：author-evaluation
- 研究对象：以历史 commit/issue 为 episodic memory、以活跃文件摘要为 semantic memory 的代码定位
- 样本与语言：SWE-bench Verified 500 项/12 个 Python 仓；SWE-bench Live 子集 130 项/62 个仓
- 模型/Agent：LocAgent + GPT-4o-2024-05-13；每题使用此前最多 7,000 commits 和 200 个活跃文件
- 对照基线：CodeRankEmbed、Agentless、LocAgent、episodic-only、semantic-only、combined RepoMem
- 指标：file localization Acc@1/3/5、issue resolve rate、成本
- 可引用声明：RepoMem 在 Verified 的 Acc@5 为 76.5%，LocAgent 为 71.6%；下游 resolve 为 40.4% 对 37.0%。Live Acc@5 为 66.2% 对 63.1%。但历史较少的 `others` 分组从 67.4% 降到 54.3%，显示不相关 memory 会干扰定位。
- 数字与语境：它改善的是 Python bug localization；丰富历史与收益相关，不能外推到新仓、C 语义或领域事实正确性。
- 限制：memory 由历史文本和摘要形成，不是当前 revision 的确定性代码事实；固定 7,000 commits/200 files 是启发式；需要在使用后回到当前代码验证。
- WiFi MAC 相关性：间接但强方法学证据
- 正文位置：仓库历史 memory、软候选与当前代码验证

### S029 — SWHID、W3C PROV-O 与 SARIF 2.1 官方规范

- 状态：primary-read
- 发布日期：SWHID 成为 ISO/IEC 18670:2025；PROV-O 2013；SARIF 2.1.0 2020
- 访问日期：2026-08-14
- 来源类型：国际/行业标准、经典持续有效规范
- 发布者/作者：SWHID Working Group/ISO、W3C、OASIS
- 原始 URL：https://www.swhid.org/specification/v1.2/0.Introduction/；https://www.iso.org/cms/live/live/en/sites/isoorg/contents/data/standard/08/99/89985.html；https://www.w3.org/TR/prov-o/；https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html
- 独立属性：standards
- 研究对象：软件工件 intrinsic ID、provenance entity/activity/agent/derivation/invalidation、静态分析结果 revision/location/fingerprint
- 样本与语言：规范性数据模型；无效果 Benchmark
- 模型/Agent：not-applicable
- 对照基线：none
- 指标：none
- 可引用声明：SWHID 用内容寻址的 intrinsic ID 精确定位 content、directory、revision 等软件工件；PROV-O 区分 Entity、Activity、Agent、derivation、revision 和 invalidation；SARIF 可记录扫描 revision、多仓 version-control provenance、源码 location 与跨版本 result fingerprint。
- 数字与语境：标准年份不代表实现成熟度或性能；它们提供可借鉴语义，不要求完整照搬 RDF/SARIF 存储。
- 限制：SWHID 不解决符号级 identity/重命名；PROV-O 不定义 WiFi 领域 ontology；SARIF 的 fingerprint 是生产者选择，不能自动证明同一领域事实。
- WiFi MAC 相关性：生命周期与交换模型直接相关
- 正文位置：实体 ID、provenance、失效与重验证分类法

### S030 — Codified Context: Infrastructure for AI Agents in a Complex Codebase

- 状态：primary-read
- 发布日期：2026-02-24
- 访问日期：2026-08-14
- 来源类型：论文、开源伴随项目、观察性案例
- 发布者/作者：Aristidis Vasilopoulos
- 原始 URL：https://arxiv.org/abs/2602.20478；https://github.com/arisvas4/codified-context-infrastructure
- 独立属性：single-project observational
- 研究对象：always-loaded constitution、19 个 domain agents、34 个按需规格文档和 MCP retrieval 的三层上下文
- 样本与语言：一个 108,000-line C# 分布式系统；283 sessions、2,801 human prompts、1,197 agent invocations、16,522 agent turns
- 模型/Agent：Claude Code；单开发者在人工架构指导下使用 Agent 生成代码
- 对照基线：无随机或并行对照；按 Git 历史重建三个阶段
- 指标：规模、会话/交互数、四个观察性案例
- 可引用声明：该项目把 hot conventions、task-specific domain agents 和 cold on-demand specifications 分层，并以 trigger/retrieval 选择上下文；展示了该架构可在长期单项目中运作。
- 数字与语境：规模和会话数字是建设记录，不是正确率或因果收益；作者、项目和工具均为单一实例。
- 限制：无受控基线、主要代码也由同一 Agent 生成、keyword retrieval 较简单；不能证明对成熟 C 驱动仓或多人团队有效。
- WiFi MAC 相关性：间接架构参考
- 正文位置：hot/cold knowledge、领域 Agent 和按需规格

### S031 — Zephyr 4.4.0 release 与仓库

- 状态：primary-read
- 发布日期：2026-04-14
- 访问日期：2026-08-14
- 来源类型：开源项目发布页、仓库
- 发布者/作者：Zephyr Project
- 原始 URL：https://github.com/zephyrproject-rtos/zephyr/releases/tag/v4.4.0；https://github.com/zephyrproject-rtos/zephyr
- 独立属性：project-primary
- 研究对象：大型嵌入式 C RTOS、驱动与多板/多架构构建
- 固定版本：`v4.4.0`，release commit `684c9e8`
- 许可证：Apache-2.0；仓库含 `LICENSES`，具体样本依赖仍需扫描
- 可引用声明：仓库以 C 为主，包含 `arch`、`boards`、`drivers`、`subsys`、Kconfig、devicetree 与 CMake/west 构建；4.4.0 默认最低 C17，并新增 Wi-Fi P2P 支持。
- 限制：体量和构建矩阵远大于 WiFiDemo；不能把整个仓库作为单一 Benchmark 单元。
- WiFi MAC 相关性：高；适合 Target、Kconfig/devicetree、driver/API 与事件路径案例
- 正文位置：后续 Benchmark 数据集

### S032 — Zephyr 官方构建与配置文档

- 状态：primary-read
- 发布日期：持续维护，4.4 文档快照
- 访问日期：2026-08-14
- 来源类型：开源项目官方文档
- 发布者/作者：Zephyr Project
- 原始 URL：https://docs.zephyrproject.org/4.4.0/build/index.html；https://docs.zephyrproject.org/4.4.0/build/kconfig/index.html；https://docs.zephyrproject.org/4.4.0/build/dts/index.html
- 独立属性：project-primary
- 研究对象：board/SoC configuration、Kconfig、devicetree、生成构建产物
- 可引用声明：最终配置和硬件描述由构建生成；Benchmark 应保存 `.config`、生成 devicetree、编译命令和选中源码作为 Target ground truth，而非只读源文件条件。
- 限制：文档定义流程，不提供候选知识图准确率。
- WiFi MAC 相关性：高
- 正文位置：后续 Benchmark ground truth

### S033 — RIOT 2026.04.01 release 与仓库

- 状态：primary-read
- 发布日期：2026-05-22
- 访问日期：2026-08-14
- 来源类型：开源项目发布页、仓库
- 发布者/作者：RIOT community
- 原始 URL：https://github.com/RIOT-OS/RIOT/releases/tag/2026.04.01；https://github.com/RIOT-OS/RIOT
- 独立属性：project-primary
- 研究对象：模块化嵌入式 C OS、board/CPU/driver/network stack
- 固定版本：`2026.04.01`，release commit `4a70282`
- 许可证：LGPL-2.1；外部 source/package 可有不同许可，样本依赖需扫描
- 可引用声明：RIOT 以 board、CPU、driver、sys/pkg 和 module 分层，构建由 BOARD、USEMODULE、FEATURES 与 Makefile 依赖解析决定。
- 限制：FEATURE 与 MODULE 并非一一对应；不能用目录或名称直接生成领域事实。
- WiFi MAC 相关性：高；适合 board/CPU/feature/module 和 radio driver 案例
- 正文位置：后续 Benchmark 数据集

### S034 — RIOT 官方结构与构建文档

- 状态：primary-read
- 发布日期：持续维护
- 访问日期：2026-08-14
- 来源类型：开源项目官方文档
- 发布者/作者：RIOT community
- 原始 URL：https://doc.riot-os.org/general/structure/；https://doc.riot-os.org/build-system/build_system_basics/；https://doc.riot-os.org/build-system/build_system/
- 独立属性：project-primary
- 研究对象：board/CPU/driver/module 结构与 build dependency resolution
- 可引用声明：`info-modules`、`info-build`、最终 CFLAGS 和依赖解析输出可构造 Target ground truth；FEATURE 表示硬件/构建约束，不保证存在同名 MODULE。
- 限制：官方文档没有为知识图工具提供 gold labels。
- WiFi MAC 相关性：高
- 正文位置：后续 Benchmark 结构映射和反事实

### S035 — Contiki-NG 5.1 release 与仓库

- 状态：primary-read
- 发布日期：release page 标记 09-20，年份以 tag 元数据为准
- 访问日期：2026-08-14
- 来源类型：开源项目发布页、仓库
- 发布者/作者：Contiki-NG team
- 原始 URL：https://github.com/contiki-ng/contiki-ng/releases/tag/release%2Fv5.1；https://github.com/contiki-ng/contiki-ng
- 独立属性：project-primary
- 研究对象：低功耗网络嵌入式 C OS、MAC/network stack、platform/CPU/device drivers
- 固定版本：`release/v5.1`，release commit `2b87baf`
- 许可证：BSD-3-Clause 为默认；例外文件/子模块需逐项扫描
- 可引用声明：仓库将 OS/network stack 放在 `os`，硬件相关 CPU/device/platform driver 放在 `arch`，examples/tests 与工具分离。
- 限制：低功耗 802.15.4 网络栈与 Wi-Fi MAC 不同；只作为结构相邻案例。
- WiFi MAC 相关性：中高
- 正文位置：后续 Benchmark 数据集

### S036 — Contiki-NG 官方构建与配置文档

- 状态：primary-read
- 发布日期：持续维护
- 访问日期：2026-08-14
- 来源类型：开源项目官方文档
- 发布者/作者：Contiki-NG team
- 原始 URL：https://docs.contiki-ng.org/en/develop/doc/getting-started/The-Contiki-NG-build-system.html；https://docs.contiki-ng.org/en/develop/doc/getting-started/The-Contiki-NG-configuration-system.html；https://docs.contiki-ng.org/en/master/doc/programming/Repository-structure.html
- 独立属性：project-primary
- 研究对象：TARGET/BOARD/CPU/module、header configuration 与可生成预处理文件
- 可引用声明：`TARGET` 和可选 `BOARD` 选择 platform，Makefile 链接 CPU/module 源码；`%.e` 可生成预处理结果；MAC 层由 `MAKE_MAC` 等配置选择。
- 限制：配置系统多由 Makefile 和 header 共同决定，需要以构建产物为准。
- WiFi MAC 相关性：高
- 正文位置：后续 Benchmark ground truth
