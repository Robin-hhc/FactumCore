# 代码检索与结构化代码图方案档案

核验日期：2026-08-13

## 1. 本轮问题边界

本档案只回答两类问题：

1. Agent 怎样以可控成本找到相关文件、符号和源码证据；
2. 轻量结构图怎样提供文件、符号、调用、引用、继承和部分框架关系。

它不把上述能力写成 CFG、数据流、污点、切片、别名分析或编译配置语义。后一类能力属于 Task 4 的“语义程序表示与深度程序分析路线”，将按 compiler AST/index/IR、跨文件语义索引、可查询代码数据库、CPG 和声明式静态分析等类别独立比较，不预设 Joern 胜出。

评价基于两组证据：近期独立检索研究 [S001–S003]，以及项目论文、官方文档、第一方 Benchmark 与许可证 [S004–S009]。本轮未在 WiFiDemo 上运行任何候选工具。

## 2. 跨方案结论

### 2.1 检索不是单选题

[S001] 在 427 个样本、25 个仓库上比较词法、RepoMap、开源 embedding 和 Agent 轨迹，没有一个检索族在所有任务及指标上全面占优：embedding 分别占据 MRR 和 Recall@20 的最佳结果，RepoMap 在 8K Token 预算下的 context yield 最好。该结果与 [S002] 的大规模分层检索结论一致：传统代码搜索中的 embedding 表现不能直接外推到 issue-to-edit 或 broader-context 任务。

因此，本研究把词法检索、向量检索和结构化检索保留为可组合的检索层或 Benchmark 基线，而不把任一方案当作完整知识架构。

### 2.2 “找过”不等于“用对”

[S003] 在 1,136 个 issue-resolution 任务上的过程评估显示，Agent 倾向提高 recall 而牺牲 precision，且 explored context 与 utilized context 存在明显差距。这意味着后续 Benchmark 不能只测“是否返回 gold file”，还需测返回证据是否进入最终答案、答案是否引用正确 Target 和源码位置。

### 2.3 轻量结构图已是成熟的 Agent 上下文组件，但尚不是 WiFi MAC 事实层

Codebase-Memory、CodeGraph 和 GitNexus 均采用 Tree-sitter 类结构抽取、持久图/数据库与 MCP 查询；Aider RepoMap 采用符号抽取、文件依赖图和预算化图排序。[S005] 与 [S007] 的第一方实验共同说明：结构化上下文可显著减少逐文件探索的 Token 或工具调用，但总体答案质量、常驻上下文、图边覆盖和真实语义正确性必须分开测量。

对 WiFiDemo 而言，这些系统尚未证明以下事实：同一源码在四个 Target 中的 occurrence 隔离、真实编译宏、Host/Device 差异、互斥源码集合、函数指针/ops 表的运行时绑定，以及领域声明到 revision/Target/file:line 的可追溯链接。故本轮只能将它们归为检索/结构层候选，不能替代后续深度程序分析和知识治理层。

## 3. 快速比较

| 方案 | 核心表示 | C/C++ 公开支持 | Agent 接口 | 公开效果数据 | 代码—领域链接 | 许可证 | 初步分类 |
|---|---|---|---|---|---|---|---|
| 词法检索（BM25/FTS/grep 类） | Token/路径/文本倒排 | 天然可索引文本，不理解 C 语义 | CLI、搜索 API 或自建 MCP | [S001] 中为必要基线，任务级胜者变化 | 仅名称和文本共现，无持久语义链接 | 取决于实现 | 必留基线/组件 |
| 代码向量检索 | chunk/file embedding | 与模型语料和切分有关 | 向量库 API/MCP | [S001] 在 MRR、Recall@20 各有最佳模型；[S002] 显示 Agent 场景显著退化 | 隐式相似度；默认无可审计 typed edge | 取决于模型和库 | 必留基线/组件 |
| Aider RepoMap | 符号摘要 + 文件依赖图 + 图排序 | Tree-sitter 提供语法抽取；未证明宏/Target 语义 | 作为提示上下文，不是独立事实 API | [S001] 在 8K 预算 context yield 最好 | 可稳定指回文件/定义行；无领域实体模型 | Apache-2.0（项目） | 保留为预算化结构检索参考 |
| Codebase-Memory | Tree-sitter + 轻量类型解析 + 持久图 | README 明示 C/C++ 跨文件、宏/typedef、头源链接等 | 15 个 MCP 工具 | [S005]：31 仓，83% vs 92% answer quality；约 10× 少 Token、2.1× 少工具调用，第一方 | 代码证据链接较强；外部领域知识与 Target provenance 未见完整模型 | MIT | 结构层短名单候选 |
| CodeGraph | Tree-sitter/Rust kernel + SQLite/FTS5 + 增量图 | C、C++；另公开 Redis/LevelDB coverage | MCP、CLI、本地库 | [S007]：7 仓第一方 Agent 实验；另有跨文件 coverage | framework route 可形成领域邻近边；缺显式领域 KB/claim 治理 | MIT | 结构层短名单候选 |
| GitNexus | Tree-sitter + LadybugDB + 聚类/流程 + hybrid search | C/C++ 在支持表中，但 imports/named bindings 缺失 | stdio MCP、HTTP、Web UI | 未发现可比公开 Benchmark | cluster/process 是代码推导结构；无外部领域知识 provenance | PolyForm Noncommercial 1.0.0 | 排除直接采用；保留设计参考 |
| Understand Anything | Tree-sitter 确定性图 + LLM 语义/领域图 | README 未提供可排序的 C/C++ 准确率证据 | Agent skills、本地图和 Dashboard | 未发现可比公开 Benchmark；首次分析 Token 可能较高 | 当前候选中最明确的 domain/flow/claim/source 设计，但领域映射依赖 LLM | MIT | 领域链接架构参考；不作代码事实核心 |

## 4. 方案档案

### R01 — 词法检索

- **定位**：最廉价、可解释的路径/符号/错误日志/宏名检索基线。
- **最新活动**：方法本身不绑定单一项目；2026-07 的 [S001] 仍将其作为正式对照。
- **开源/许可证**：实现可选 SQLite FTS5、Lucene、ripgrep 等；本轮不绑定实现，许可证需在最终选型时逐项核验。
- **核心表示**：倒排索引、Token 频率、路径与文本字段。
- **事实来源**：原始源码、构建文件、日志和文档字面内容。
- **Agent 接口**：可通过 CLI、SQL、搜索 API 或 MCP 封装。
- **公开数据**：[S001] 表明其仍可能在某些任务胜出，但不存在普遍领先；[S002] 说明传统代码搜索分数不能代表 broader-context 能力。
- **WiFiDemo 直接证据**：本轮未运行。W03 的 `_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD`、W04 的条件编译宏和 W08 的函数名适合作为后续 exact-match 查询。
- **优点**：低成本、低延迟、结果可解释；精确宏、日志串、枚举和文件路径通常具有高信息量；适合 no-gold 时保守返回。
- **缺点**：同义词、隐式调用、运行时绑定和跨文件语义弱；同名函数可能产生大量误报；无法区分相同源码在不同 Target 下的 occurrence。
- **Unknown**：不同字段权重、C 标识符切词、宏与日志专用 analyzer 对 WiFiDemo 的收益。
- **代码—领域链接**：仅能通过共同词项、人工标签或显式映射表连接；检索分数不能直接变成 `implements_feature` 等知识边。
- **可借鉴**：所有领域实体和代码证据都保留 exact-match 字段；作为结构图/向量检索失败时的可解释回退。
- **初步分类**：必留 Benchmark 基线与生产组件，不作为完整架构。

### R02 — 代码向量检索

- **定位**：从自然语言需求、设计描述和错误现象召回词面不一致的代码上下文。
- **最新活动**：2026-06/07 的 [S001][S002] 提供了近期大规模证据。
- **开源/许可证**：需同时核验 embedding 模型权重、推理框架和向量库许可证；本轮不锁定模型。
- **核心表示**：file/chunk embedding 与近邻索引。
- **事实来源**：源码、注释、文档或拼接后的结构摘要。
- **Agent 接口**：向量检索 API 或 MCP；必须返回原始文件、行范围和 revision 作为证据载荷。
- **公开数据**：[S001] 中 Qwen3-Embedding-4B 的正样本 sample-weighted MRR 最好，Qwen3-Embedding-8B 的 Recall@20 最好，但 RepoMap 在 8K 预算 context yield 最好；[S002] 显示 embedding 从传统搜索到 Agent 检索显著退化。
- **WiFiDemo 直接证据**：本轮未运行。W05 的“运行时选择芯片 ops”与源码词面可能不完全一致，适合后续评估语义召回。
- **优点**：跨词面召回强；能把自然语言领域概念引向相关注释和实现；适合与词法/结构结果融合。
- **缺点**：相似度不可证明程序关系；chunk 切分可能拆散宏条件、声明和定义；模型升级会引入索引漂移；no-gold 拒答仍困难 [S001]。
- **Unknown**：中文领域词、C 宏、短标识符、代码/文档混合 embedding 的最优切分和 rerank 策略。
- **代码—领域链接**：只能生成候选链接；必须经规则、人工或可定位的分析证据转成 typed edge，并记录模型、版本、分数和审核状态。
- **可借鉴**：用于 candidate generation，不让 embedding 相似度直接覆盖 Target-aware 代码事实。
- **初步分类**：必留 Benchmark 基线与可选召回组件，不作为事实层。

### R03 — Aider RepoMap

- **定位**：在有限上下文窗口中提供全仓关键符号和关系的预算化摘要。
- **最新活动**：官方文档访问快照为 2026-08-13；核心设计自 2023 年起持续使用 [S004]。
- **开源/许可证**：Aider 项目为 Apache-2.0；最终复用代码前仍需核验具体模块及依赖。
- **核心表示**：Tree-sitter 符号定义/引用、以文件为节点的依赖图、图排序、源码定义关键行。
- **事实来源**：源码语法结构和当前对话/已选文件上下文。
- **Agent 接口**：将裁剪后的 map 直接送入 LLM；默认 `--map-tokens` 为 1k [S004]。
- **公开数据**：[S001] 的独立实验中，RepoMap 在 8K Token 预算下 context yield 最好，但不是 MRR 或 Recall@20 的总体最佳。
- **WiFiDemo 直接证据**：本轮未运行。W08 的同名处理函数、W01 的双芯片文件关系可检验其排序和消歧能力。
- **优点**：表示紧凑、无向量依赖、定义行可解释；把“全仓地图”与“打开全文”分层。
- **缺点**：主要为上下文选择服务，不能回答复杂图查询；语法引用不等于预处理后的调用；没有领域知识与生命周期治理。
- **Unknown**：C/C++ tag query 对宏、函数指针、静态同名符号和生成代码的覆盖；对四 Target 分图的成本。
- **代码—领域链接**：可作为领域实体链接后的“可读代码摘要”，但自身没有领域 node/edge、confidence、conflict 或 provenance 模型。
- **可借鉴**：Token 预算应成为检索 API 的一等参数；图排序可作为结构层结果的 reranker。
- **初步分类**：保留为结构检索与上下文压缩参考，不作为知识图存储。

### R04 — Codebase-Memory

- **定位**：本地持久代码知识图与 MCP 代码探索服务。
- **最新活动**：当前 README 访问于 2026-08-13，能力表已描述论文之后的 C/C++ 解析增强；论文快照发布于 2026-03-28 [S005][S006]。
- **开源/许可证**：MIT。
- **核心表示**：Tree-sitter AST 结构抽取、轻量混合类型解析、持久图、call chain、community、HTTP/cross-service 关系。
- **事实来源**：源码、部分基础设施文件和项目内 ADR；C/C++ 解析声明包含跨文件 registry、宏、typedef 链、头源链接、模板和类层次方法解析 [S006]。
- **Agent 接口**：15 个 MCP 工具，包含 search、trace、architecture、impact、coverage、Cypher 和 ADR 管理等 [S006]。
- **公开数据**：[S005] 第一方论文在 31 仓报告 83% answer quality，对照逐文件探索为 92%，同时约 10× 少 Token、2.1× 少工具调用；graph-native 查询在 31 种语言中的 19 种匹配或超过对照。
- **WiFiDemo 直接证据**：本轮未运行，也没有公开 WiFi MAC 案例。
- **优点**：开源、本地、MCP 原生；结构查询面较完整；C/C++ 能力说明比纯 Tree-sitter 项目更贴近 WiFiDemo；论文同时暴露了质量与效率的交换，而非只报告优势。
- **缺点**：第一方 Benchmark 不能证明独立优越性；当前 README 与论文版本差异大；轻量类型解析仍不等于编译器产生的 Target-specific 语义；“宏支持”不等于按真实宏集构造互斥图。
- **Unknown**：能否导入 compilation database/真实编译命令；预处理分支、函数指针、同名静态符号和跨 Target 隔离的 precision/recall；图中边是否携带 rule/line/revision provenance。
- **代码—领域链接**：项目可管理 ADR 并索引图，但公开材料没有证明可把外部 Feature/Chip/Side/Target 声明以稳定 ID、证据边、confidence 和生命周期接入代码事实。
- **可借鉴**：MCP 查询面、局部 coverage 自检、持久图与增量索引；后续可把其作为轻量结构层实现候选参与 WiFiDemo Benchmark。
- **初步分类**：结构层短名单候选；不能单独完成领域知识架构。

### R05 — CodeGraph

- **定位**：面向 Agent 的本地增量代码图，强调跨文件导航、impact/trace 与密集上下文返回。
- **最新活动**：官方于 2026-08-05 重测 Agent Benchmark；2026-05-27 的 v0.9.6 release 修复 C/C++ bare-basename `#include` 解析 [S007]。
- **开源/许可证**：MIT。
- **核心表示**：Rust kernel + Tree-sitter，节点包括函数/类/方法，边包括 calls/imports/extends/implements；SQLite + FTS5，引用解析后以文件 watcher 增量同步。
- **事实来源**：源码语法结构、语言/框架特定解析规则和合成的动态分派/路由边。
- **Agent 接口**：MCP、CLI 和本地库；主要工具返回 entry points、相关符号、代码片段、trace 和 blast radius。
- **公开数据**：[S007] 的 7 仓、7 语言、每仓 1 个架构问题、每臂 4 次第一方实验报告工具调用减少 88%、时间减少 53%、处理 Token 减少 62%、成本减少 44%；同一材料同时报告会话末残留检索上下文约增加 80%。C/Redis 与 C++/LevelDB 的特定 cross-file dependent coverage 分别为 92.2% 和 94.8%，不能解释为边准确率。
- **WiFiDemo 直接证据**：本轮未运行；官方 C 样本为 Redis，不是嵌入式驱动。
- **优点**：本地、开源、增量和 SQLite 便于运维；明确提供 C/C++；Benchmark 方法公开了控制组污染修正和残留上下文代价；框架专用规则展示了“通用抽取 + 领域适配器”的工程路线。
- **缺点**：第一方实验样本问题少；密集一次性返回会占据更多会话窗口；合成边若无细粒度 provenance，可能与确定性代码边混淆；没有真实编译视角。
- **Unknown**：预处理宏、函数指针、ops 表、链接期选择和四 Target occurrence；是否允许外部领域 schema 作为一等节点；所有边的 source rule/confidence 可否导出。
- **代码—领域链接**：framework route 是“代码结构到应用概念”的规则化链接先例，但 WiFi Feature/Chip/Side 需要独立 schema、Target 锚点和证据链，不能复用 Web route 假设。
- **可借鉴**：SQLite/FTS5、本地增量索引、response token budget、边覆盖自检、专用解析规则；后续纳入结构层 Benchmark。
- **初步分类**：结构层短名单候选；不能单独承担深度语义或领域治理。

### R06 — GitNexus

- **定位**：本地/浏览器零服务器代码图，集成结构解析、功能聚类、执行流程、hybrid search 与 Graph-RAG Agent。
- **最新活动**：当前 README 和 changelog 访问于 2026-08-13，仍在更新 MCP、解析器和 Agent 集成 [S008]。
- **开源/许可证**：源代码公开，但许可证是 PolyForm Noncommercial 1.0.0；商业或内部产品采用必须单独获得许可，不能按 MIT/Apache 类开源处理。
- **核心表示**：Tree-sitter AST、LadybugDB、跨文件引用解析、社区聚类、entry-point 到 call-chain 的 process。
- **事实来源**：源码结构与语言启发式；浏览器模式使用 WASM，本地模式使用 native bindings。
- **Agent 接口**：stdio MCP、HTTP、本地 Web UI；提供只读模式、允许仓库列表和确定性响应 Token 上限。
- **公开数据**：未发现可与 [S005][S007] 对齐的官方或独立 Benchmark，故不登记性能数字。
- **WiFiDemo 直接证据**：本轮未运行。
- **优点**：MCP 安全边界和多仓策略较完整；聚类/process 把底层符号图压缩为更适合 Agent 的导航单元；本地隐私路线清晰。
- **缺点**：许可证直接限制采用；官方语言表中 C/C++ 不支持 imports/named bindings，和 WiFiDemo 的头文件/跨文件需求存在明显缺口；无可比效果数据。
- **Unknown**：C 函数指针与宏行为、聚类稳定性、process precision、边 provenance、外部领域知识接入。
- **代码—领域链接**：cluster/process 是从代码推导的高层结构，不等于人工/文档定义的领域事实；没有看到 claim/source/confidence/revision 生命周期。
- **可借鉴**：MCP read-only 模式、repo allowlist、响应预算和结构→cluster→process 的多尺度导航。
- **初步分类**：排除为直接采用候选；保留架构参考。若未来许可证改变，也必须先通过 C/Target Benchmark。

### R07 — Understand Anything

- **定位**：把可复现的结构图与 LLM 生成的架构/业务领域图分层，提供本地可视化和增量分析。
- **最新活动**：v2.9.0 于 2026-07-10 发布；v2.1.0 引入 business domain graph，v2.3.1 增加 domain、flow、step、claim、source 等类型 [S009]。
- **开源/许可证**：MIT。
- **核心表示**：Tree-sitter 确定性结构事实 + LLM 生成摘要、标签、架构层、business-domain mapping、tour；保存为项目内 JSON 图。
- **事实来源**：源码、解析结构以及 LLM 对原始源码和结构的推断；知识模式还可处理 article/entity/topic/claim/source。
- **Agent 接口**：多个 Agent skill 与本地 Dashboard；首次全仓分析后按 fingerprint 增量更新。
- **公开数据**：未发现结构边、领域映射或问答准确率的可比 Benchmark；官方只定性提示首次全仓分析会消耗较多 Token [S009]。
- **WiFiDemo 直接证据**：本轮未运行，README 也未提供可排序的 C/C++ 准确率证据。
- **优点**：当前候选中最直接展示“确定性代码事实与非确定性领域解释分层”的开源实现；domain/flow/step/claim/source schema 对本研究有直接启发；增量 fingerprint 有利于重验证。
- **缺点**：领域知识主要由 LLM 从代码推断，容易把“推测”写成“事实”；没有公开 accuracy、confidence calibration 或冲突处理数据；全仓初始化成本未知且可能较高；结构层能力不等于 C 编译语义。
- **Unknown**：外部设计文档如何与代码实体稳定对齐；同一源码多 Target occurrence；LLM 生成节点的模型/version/prompt provenance、confidence、人工审核和失效传播。
- **代码—领域链接**：可借鉴两条明确通道：确定性结构边与 LLM 语义边分层，以及 `claim/source` 类型；但我们需要进一步加上 `Target + revision + file:line + generator + confidence + review_status`，并在代码变化后定向重验证。
- **可借鉴**：领域图不污染代码事实层、可视化切换、增量 fingerprint、claim/source 类型和多阶段 review。
- **初步分类**：领域知识链接架构参考；不进入核心代码事实引擎短名单。

## 5. 本轮缩小范围

### 5.1 保留到后续 Benchmark

- **必留基线**：词法检索、代码向量检索、RepoMap 类预算化结构检索。
- **结构层实现短名单**：Codebase-Memory、CodeGraph。
- **领域链接架构参考**：Understand Anything；重点学习确定性结构与非确定性领域边分层，而不是直接采用其 LLM 生成结果。

### 5.2 当前排除

- **把纯词法或纯向量检索作为完整知识架构**：它们没有程序关系、Target occurrence 和领域事实治理。
- **把任一 Tree-sitter 结构图当作深度程序分析**：calls/imports/extends 等边不能替代 CFG、数据流、别名、污点或切片。
- **直接采用 GitNexus**：PolyForm Noncommercial 许可证与预期采用条件冲突，且 C/C++ import 能力和效果数据不足；其 MCP 安全与多尺度导航设计仍可学习。
- **把 LLM 生成的领域映射直接写入确定性事实层**：缺少 provenance、confidence、人工审核和变更失效机制。

## 6. 对 Task 4 的输入约束

下一轮深度程序分析调研必须至少回答以下问题，且不得只围绕 Joern：

1. 是否使用真实 compiler invocation、`compile_commands.json`、预处理结果或等价 Target Profile；
2. C 的函数指针、宏、typedef、条件编译、静态同名符号、跨文件与链接期关系分别覆盖到什么程度；
3. 提供 AST/index/IR、CFG、call graph、data-flow、taint、slice 中哪些事实，边的 precision/recall 如何评估；
4. 是否能导出稳定实体 ID、revision、Target、file:line、edge generator 与 confidence；
5. 如何与本档案中的词法/向量/结构检索层组合，而不是重复建设；
6. 许可证、离线部署、增量更新、资源成本和 Agent 查询接口是否满足工程约束。

## 7. 对“代码—领域知识链接”的阶段性要求

本轮证据支持一个保守的分层模型，但不构成最终选型：

| 链接层 | 可接受来源 | 必需属性 | 禁止的替代关系 |
|---|---|---|---|
| 确定性代码链接 | compiler/static analyzer、可定位语法规则、人工确认 | stable code ID、revision、Target、file:line、generator | embedding 相似度不得冒充调用/实现关系 |
| 规则化领域链接 | 配置/命名/表驱动规则、人工映射 | domain ID、typed edge、rule version、evidence、review status | 文件夹名称不得直接等价于 Chip/Side/Feature 事实 |
| 推断领域链接 | embedding/LLM/聚类 | model、prompt/rule、score/confidence、候选状态、证据集合 | 未审核推断不得覆盖确定性事实 |
| 生命周期链接 | revision/Target 变化检测 | created_at、validated_at、invalidated_by、conflict state | 代码变更后不得无条件沿用旧领域声明 |

这使 CodeGraph/Codebase-Memory 一类结构图可以成为代码证据提供者，Understand Anything 一类领域生成流程可以成为候选映射提供者，但最终知识架构必须在二者之上增加 Target-aware identity、provenance、confidence、冲突和重验证机制。
