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
| primary-read | 4 |
| claim-verified | 5 |
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
