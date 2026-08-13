# 代码检索与结构化代码图方案档案

核验日期：2026-08-13

> 2026-08-14 更新：跨检索、程序分析与领域知识方案的固定维度比较、硬门槛和候选分层，见 [evidence-matrix.md](./evidence-matrix.md)。本档案保留逐方案事实，不再用局部能力暗示完整方案排名。

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

## 8. 语义程序表示与深度程序分析路线

### 8.1 技术中立的分层

深度程序分析不是单一工具类别。对 WiFiDemo 类 C 驱动项目，至少要拆成下列层次：

| 层次 | 主要问题 | 代表路线 | 不能自动证明的内容 |
|---|---|---|---|
| 编译输入事实 | 这个文件在什么 Target、宏、include 和工作目录下被编译？ | Clang compilation database、Kythe KCD | 调用/数据流正确性 |
| 语义身份与交叉引用 | 这个 occurrence 定义/引用了哪个符号？ | Clang AST、scip-clang/SCIP、Kythe | CFG、taint、slice |
| 编译器 IR | 在某个已选 Target 中实际产生了什么控制和内存操作？ | LLVM IR、debug metadata、MemorySSA | 源码领域含义、跨 Target 统一身份 |
| 可查询代码数据库 | 如何声明式查询 AST、CFG、dataflow 和安全模式？ | CodeQL | 开放引擎、领域知识治理 |
| 联合图表示 | 如何在一张图中跨 AST/CFG/PDG/DFG 查询？ | Joern、Fraunhofer CPG | frontend 自动等价于真实编译语义 |
| 专门深度分析 | 函数指针、alias、value-flow、抽象状态和 slice 如何求解？ | SVF、PhASAR、Frama-C | Agent-ready 检索和知识存储 |
| 规则化检查 | 如何快速编码项目规范并返回源码告警？ | Semgrep CE | 开源跨文件深层数据流 |

关键结论是：CPG 是表示和查询组织方式，不是精度来源本身。函数指针、dataflow 和 slice 的质量来自 frontend、构建输入、alias/points-to 算法、外部函数摘要和分析预算；把这些边存成图不会自动提高正确性。[S010][S014–S020]

### 8.2 能力标记约定

- `D`：官方文档明确提供该能力，但尚未在 WiFiDemo 实测。
- `P`：仅提供部分能力、需额外组件或有明确范围限制。
- `U`：官方材料不足，保持 unknown。
- `—`：产品定位明确不提供。

| 路线 | 真实编译输入 | 多 Target 隔离 | direct call | function pointer | CFG | dataflow/taint | slice | 源码证据 | 增量/交换 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Clang AST + LLVM IR | D | P | D | P | D | P | — | D | P |
| scip-clang/SCIP | D | P | D | U | — | — | — | D | D |
| Kythe | D | D | D | U | — | — | — | D | D |
| CodeQL | D | P | D | P | D | D | P | D | P |
| Joern | U | U | D | U | D | D | D | D | D |
| Fraunhofer CPG | P | U | D | P | D | D | P | D | D |
| SVF | P | P | D | D | D | D | P | P | P |
| PhASAR | P | P | D | D | D | D | P | P | P |
| Frama-C | P | P | D | D | D | D | D | D | P |
| Semgrep CE | — | — | P | — | P | P | — | D | P |

这里的 `D` 只表示“文档化能力存在”，不表示对 WiFiDemo 的 accuracy 已被证明。例如 Kythe KCD 原生记录 target/revision，但 WiFiDemo 的四个 Target 是否能稳定抽取成四组 hermetic compilation units 仍待实验；SVF 明确维护 function-pointer target 集合，但实际召回率和候选规模仍待测。

## 9. 深度程序分析方案档案

### A01 — Clang AST/LibTooling + LLVM IR

- **定位**：以真实编译命令为入口，分别获得源码级 AST/位置和低层 CFG/SSA/alias 分析载体。
- **最新活动**：官方 Clang/LLVM 24.0.0git 文档在 2026-08 仍持续更新 [S010]。
- **开源/许可证**：Apache-2.0 WITH LLVM-exception。
- **核心表示**：每 translation unit 的 Clang AST、LLVM IR/bitcode、CFG、debug metadata、alias results 与函数内 MemorySSA。
- **事实来源**：`compile_commands.json` 中的工作目录、argv、源文件和可选 output；同一源文件可有多条不同配置命令 [S010]。
- **Agent 接口**：原生是 C++ API、命令行和序列化 IR，不是 MCP；需自建稳定导出、索引和查询层。
- **公开数据**：无可用于本研究排序的 Agent/WiFi Benchmark；官方只定义接口与保守语义。
- **WiFiDemo 直接证据**：W01–W04 强烈要求保留四个 Target 的独立命令与 occurrence；本轮未运行工具。
- **优点**：最接近编译器实际看到的 C；宏/include/语言模式与 Target 绑定；AST source location 精确；IR 为 CFG、alias、MemorySSA 和其他分析提供统一底座。
- **缺点**：AST 以 TU 为边界；IR 可读性和源码构造会损失，优化级别影响图形；MemorySSA 是 intraprocedural；需要大量工程把两层身份重新连接并服务给 Agent。
- **Unknown**：WiFiDemo 是否能由 CMake 为四 Target 产生完整、无重复污染的 compdb；GCC 扩展/内联汇编兼容；函数指针在基础 LLVM AA 下的候选质量。
- **代码—领域链接**：应把 `TargetProfile -> CompileCommand -> TUOccurrence -> AST/IR node -> SourceSpan` 作为确定性主链；Feature/Chip/Side 只链接到 TargetProfile 或有证据的 occurrence，不能直接链接裸 source symbol。
- **可借鉴**：把 compilation database 当作知识图的一级事实，而不是索引器临时参数；同时保存 source ID 与 Target occurrence ID。
- **初步分类**：核心基础路线，几乎不可由纯结构图替代；仍需上层查询和知识治理。

### A02 — scip-clang/SCIP

- **定位**：把 Clang 的精确 C/C++ occurrence、定义和引用导出为开放、紧凑的代码智能交换格式。
- **最新活动**：SCIP v0.7.1 于 2026-04-14 发布；scip-clang 当前基于 Clang 21 [S011]。
- **开源/许可证**：scip-clang 与 SCIP 均为 Apache-2.0；完整 Sourcegraph 服务端不作为本候选的必要依赖。
- **核心表示**：document、symbol、occurrence、relationship 和 source range 的 protobuf index。
- **事实来源**：JSON compilation database；官方展示 include、macro、type references 和跨仓导航。
- **Agent 接口**：输出 `index.scip`，需自建 reader/SQLite/MCP 或接兼容服务；不是 dataflow query engine。
- **公开数据**：官方建议约每 TU 2 MB 临时空间和每核约 2 GB RAM，但无精度 Benchmark [S011]。
- **WiFiDemo 直接证据**：W03/W04 的宏 occurrence、W08 的同名符号消歧适合此路线；本轮未运行。
- **优点**：编译视角与源码位置兼得；开放格式有利于替换 frontend；适合稳定“代码身份层”，比自行解析 clangd YAML 风险低。
- **缺点**：不含 CFG、dataflow、taint、slice；多 Target 若直接合并同一 document，必须由我们另加 Target namespace；不支持 PCH。
- **Unknown**：同一 source range 在多 compdb command 中的 occurrence 合并策略；C static symbol/macro identity 的稳定性；Windows/WSL 产物兼容。
- **代码—领域链接**：领域边可以锚定 SCIP symbol/occurrence 与 Target ID；但必须另存 revision、compile-command digest 和 evidence generator。
- **可借鉴**：采用开放 interchange 隔离 Clang frontend 与知识存储；把 source-range occurrence 作为面向 Agent 的最小证据对象。
- **初步分类**：语义身份层短名单；与深度分析互补，不单独构成知识架构。

### A03 — Kythe

- **定位**：以 hermetic compilation unit 为核心的跨语言、跨 revision、跨 target 交叉引用生态。
- **最新活动**：官方仓库和文档在 2026-08 仍活跃，提供 C++ indexer、extractor、schema 与 serving 工具 [S012]。
- **开源/许可证**：Apache-2.0。
- **核心表示**：content-addressed compilation unit、VName、anchor、semantic node、typed edge、serving tables。
- **事实来源**：捕获真实 compile action 及全部输入/依赖/flags；KCD index 明示 revision、target、source、corpus 与 language 字段。
- **Agent 接口**：交叉引用/decoration API 和命令行；无原生 MCP，需要包装。
- **公开数据**：无 WiFi/Agent 效果数字。
- **WiFiDemo 直接证据**：其 compilation-unit/target 模型与 W01–W07 高度吻合，但本轮未运行 extractor。
- **优点**：Target 和 revision 是原生索引维度；anchor 将语义实体严格指回源码跨度；generated-code 采用不同节点加 `generates` 边，而不是错误合并身份；schema 可扩展。
- **缺点**：部署和构建抽取比 SCIP 重；主要解决 xref，不解决 dataflow/slice；扩展领域 node 后，通用客户端的理解能力有限。
- **Unknown**：CMake 四 Target extraction 的可用性、C function pointer call edge、增量 rebuild 成本、Windows 支持。
- **代码—领域链接**：是本轮最强的确定性身份/证据建模参考：领域实体保持独立 VName，用 typed edge 连到 anchor/semantic node，并保留 corpus/revision/target。
- **可借鉴**：content digest、compile-unit digest、source anchor 和“连接而不合并”原则。
- **初步分类**：身份/provenance 架构强参考；实现复杂度需与 SCIP+自建 metadata 方案比较。

### A04 — CodeQL

- **定位**：把编译后的 C/C++ 程序抽取为关系数据库，用声明式 QL 查询语法、控制流、dataflow 和 taint。
- **最新活动**：CLI v2.25.5 于 2026-05-22 发布，query/model packs 持续更新 [S013]。
- **开源/许可证**：查询与库为 MIT；CLI/engine 单独授权，闭源代码与自动化内部工程分析通常需要商业许可。
- **核心表示**：CodeQL database、QL relations/classes、CFG/dataflow/taint libraries、path query。
- **事实来源**：C/C++ database creation 过程观察 build；库模型与 model pack 补足不可见外部函数。
- **Agent 接口**：CLI、VS Code 和 query packs；需自建受限查询/MCP 门面。
- **公开数据**：本轮不使用 GitHub 产品营销数据或漏洞数排序；只确认功能和许可边界。
- **WiFiDemo 直接证据**：理论上适合 W04/W06 的路径查询，但未验证四 Target database 的隔离和宏 provenance。
- **优点**：成熟声明式查询、C/C++ pointer/pointee dataflow、path explanation、丰富标准库；规则可版本化和测试。
- **缺点**：engine 非开源且闭源项目采用受限；难以替换底层 extractor；设计重心是安全扫描，不是自由扩展的领域知识底座。
- **Unknown**：四 Target 分库资源成本、ops 表函数指针解析质量、数据库事实能否以稳定开放格式全部导出。
- **代码—领域链接**：model pack 展示了“用版本化模型补充库/框架语义”的机制；领域规则仍需独立 metadata 与 evidence，不能锁死在不可开放导出的 query result 中。
- **可借鉴**：声明式规则包、source/sink model、path explanation 和 query test；不宜作为默认开源核心。
- **初步分类**：强 Benchmark 对照与设计参考；因 engine/闭源许可不进入优先开源实现短名单。

### A05 — Joern

- **定位**：以统一 CPG 和 Scala DSL 查询 AST、call/control/dataflow，并导出 data-flow/usage slice。
- **最新活动**：v4 持续发布，检索到 v4.0.548（2026-05-27）；项目由 OverflowDB 迁移到 FlatGraph [S015]。
- **开源/许可证**：Apache-2.0。
- **核心表示**：CPG base schema + overlays、FlatGraph、CPGQL、OSS dataflow、JSON slice。
- **事实来源**：`c2cpg` 等 frontend 从源码目录生成 CPG，后续 overlay 增加 semantic/dataflow；external method 可用 custom semantics。
- **Agent 接口**：shell、script、server、JSON export/slice；无必须依赖通用图数据库。
- **公开数据**：经典 CPG 论文的 18 个 Linux kernel 漏洞只证明 2014 方法案例 [S014]，不能当作当前 Joern 准确率；本轮未发现可比 WiFi/Agent Benchmark。
- **WiFiDemo 直接证据**：尚未运行；官方材料未证明 consumption of compdb 或多 Target occurrence isolation。
- **优点**：跨 AST/CFG/dataflow 的查询体验成熟；切片输出包含 file/line/column，适合 Agent 消费；custom semantics 可表达外部 API flow；开源且活跃。
- **缺点**：当前 C frontend 的真实编译输入能力证据不足；type recovery/custom semantics 可能混合推断与确定性事实；Scala/JVM/DSL 运维成本较高；“CPG”名称不能保证函数指针精度。
- **Unknown**：WiFiDemo 真实宏集、header include、static 同名符号、ops 表函数指针、四 Target 分图资源和跨图身份。
- **代码—领域链接**：可用 TAG/自定义 overlay 挂领域边，但每条边必须另存 `Target/revision/generator/confidence/evidence`；custom semantics 应作为规则层，不能伪装 parser fact。
- **可借鉴**：overlay、统一 traversal DSL、可裁剪 JSON 和 external semantics；后续 Benchmark 中只作为一个 CPG 候选。
- **初步分类**：CPG 路线短名单候选之一，不是预设答案。

### A06 — Fraunhofer AISEC CPG

- **定位**：可嵌入 JVM 项目的 CPG library，以 language frontend + passes 构造 EOG/DFG/CDG 等多层图。
- **最新活动**：文档于 2026-06 更新，README 当前依赖示例为 9.0.2 [S016]。
- **开源/许可证**：Apache-2.0。
- **核心表示**：typed Kotlin graph model、AST/EOG/DFG/CDG、scope/symbol、passes、function summaries 与 inference rules。
- **事实来源**：C/C++ frontend 使用 Eclipse CDT；也可从 LLVM IR 建图；passes 进行 symbol/call/type/dataflow refinement。
- **Agent 接口**：Kotlin query API、library embedding、Neo4j export；没有现成 MCP。
- **公开数据**：无可比较 WiFi/Agent 效果数字。
- **WiFiDemo 直接证据**：未运行；C17 支持与 W01–W08 的宏/Target 要求并不等价。
- **优点**：frontend 与 pass 严格分层；作为 library 易于增加自定义 pass/overlay；function summary 是外部 API/领域规则入口；图模型比单一安全扫描器更可扩展。
- **缺点**：C frontend 的 CDT 依赖和构建配置精度需验证；Neo4j export 增加运维但不是必须；文档化“支持函数指针 trait”不等于解析质量数据。
- **Unknown**：compdb/预处理输入、跨 TU/函数指针 precision、增量更新、四 Target 图大小和 JVM 内存。
- **代码—领域链接**：pass/overlay 可产生 domain typed edge；应给每个 inference/summary 边标注规则版本、Target、证据与置信度。
- **可借鉴**：frontend→passes 分层、可嵌入 library、function summary 和显式 inference rules。
- **初步分类**：CPG 路线短名单候选之一；需与 Joern 在 WiFi C 上实测，而非按知名度选择。

### A07 — SVF

- **定位**：LLVM IR 上专门求解 C/C++ pointer/alias、call graph、ICFG、Memory SSA 和 value-flow。
- **最新活动**：SVF 3.3 于 2026-05-20 发布，当前项目声明支持 LLVM 21 [S017]。
- **开源/许可证**：AGPL-3.0-or-later，另含单独授权的第三方组件；属于强 copyleft，作为内部独立工具运行与嵌入/修改后提供网络服务的合规边界应分别评估。
- **核心表示**：SVF IR、constraint graph、call graph、ICFG、SVFG、interprocedural Memory SSA、points-to sets。
- **事实来源**：每个 Target 编译/链接得到的 LLVM bitcode；分析器构造 indirect-call target 集合和 value-flow。
- **Agent 接口**：C++ API、工具和新增 Python bindings；无原生 MCP/通用查询 DSL。
- **公开数据**：项目列出 CC/FSE/TSE/CGO 等算法论文，但旧算法结果不用于当前实现排序；本轮只确认能力存在。
- **WiFiDemo 直接证据**：W05 的 ops 表和函数指针是其最关键潜在价值；尚未运行。
- **优点**：本轮候选中对函数指针和 value-flow 最专门；可补足 CPG/结构图的 indirect call 弱点；分析敏感度可选择。
- **缺点**：必须先产生完整 bitcode；source construct 和宏 provenance 会弱化；全程序/高敏感度分析可能昂贵；不是知识存储。
- **Unknown**：四 Target bitcode 生成、外部/汇编函数处理、实际函数指针候选 precision/recall、结果稳定 ID，以及预期部署方式下的 AGPL 合规边界。
- **代码—领域链接**：只应输出带 Target 的 `may_call`/`value_flows_to` 候选及 analysis configuration；领域层可把关键 ops slot 映射到 domain role，但不能把 may-call 写成 must-call。
- **可借鉴**：把 function-pointer resolution 作为独立可替换分析 provider，并保留 sensitivity/configuration provenance。
- **初步分类**：深度分析补充短名单，不作为主知识数据库。

### A08 — PhASAR

- **定位**：LLVM IR 上可编程的 interprocedural data-flow framework，重点是 IFDS/IDE/WPDS、taint 和路径重建。
- **最新活动**：当前项目支持 LLVM 16–22.1，并持续维护 C++20 API [S020]。
- **开源/许可证**：MIT。
- **核心表示**：LLVMProjectIRDB、ICFG、call graph、type hierarchy、alias sets、IFDS/IDE facts、taint paths。
- **事实来源**：Target-specific LLVM IR；source/sink/summary 可来自 IR annotation、JSON 或 callback。
- **Agent 接口**：C++ library/CLI 输出；无原生 MCP，但 JSON 配置适合由上层生成受控分析任务。
- **公开数据**：2019 论文含 case study，但当前版本变化较大，本研究不引用旧 runtime 排名。
- **WiFiDemo 直接证据**：适合验证 W06 的 Host/Device event dataflow 和定制 source/sink；尚未运行。
- **优点**：比固定漏洞扫描器更适合定义领域 data-flow problem；支持多种 call graph、path reconstruction 和 SVF points-to integration；宽松许可证。
- **缺点**：IR 构建与 source mapping 工程量大；需要自己定义问题和 summaries；不是查询数据库或知识生命周期系统。
- **Unknown**：WiFiDemo bitcode 可构建性、分析规模、函数指针配置、输出与 source occurrence 的稳定对齐。
- **代码—领域链接**：JSON/callback source/sink 是清晰的规则化领域入口；每条配置必须引用 domain entity、Target、revision、rule version，结果 path 必须回连 source span。
- **可借鉴**：把“领域问题定义”与“通用 dataflow solver”分离，避免把领域规则硬编码进基础图 schema。
- **初步分类**：开源深度 dataflow 短名单；可能与 Clang/SCIP 身份层组合。

### A09 — Frama-C

- **定位**：面向 C 的统一分析平台，以 Eva 抽象解释、ACSL 规格、依赖/PDG、impact 和 slicing 处理高可信问题。
- **最新活动**：33.0 beta 于 2026-06-25 发布；Eva 改进 volatile pointer 支持并新增 secure-flow 选项 [S018]。
- **开源/许可证**：LGPL；可另行双许可。
- **核心表示**：规范化 C AST、abstract states、alarms、ACSL properties、functional dependencies、PDG 和 sliced project。
- **事实来源**：预处理后的 C、入口/库模型、用户 ACSL 规格和插件分析结果。
- **Agent 接口**：CLI、GUI、OCaml plugin API、SARIF 辅助项目；无原生 MCP。
- **公开数据**：Eva 提供 soundness 契约，但无 alarm 不等于“所有领域问题正确”；本轮不引用跨工具准确率。
- **WiFiDemo 直接证据**：嵌入式 C、volatile、函数指针和 slicing 高度相关；尚未验证 GCC 扩展/asm/四 Target。
- **优点**：C 专用且分析类型互补；可生成满足准则的真正程序切片；ACSL 能把人工领域约束转成可验证 property；对 runtime error 具有比结构图更强的语义保证。
- **缺点**：环境与库建模成本高；复杂驱动可能产生大量 alarms/unknown；多 Target 必须分别分析；输出需再结构化给 Agent。
- **Unknown**：WiFiDemo 预处理兼容、volatile/MMIO/asm 模型、全仓规模、slice 可读性与跨 Host/Device event 表达。
- **代码—领域链接**：ACSL property 可作为 `domain claim -> formal property -> proof/alarm -> source span` 链，但人工规格维护成本和适用范围必须显式记录。
- **可借鉴**：区分 proven/invalid/unknown，而不是单一 confidence；将 slicing 用于证据压缩而非知识存储。
- **初步分类**：高可信 C 分析/切片短名单，适合作为按需验证器而非全局主图。

### A10 — Semgrep CE

- **定位**：用近似源码的 pattern DSL 快速编码项目级语法/局部 dataflow 规则并返回精确位置。
- **最新活动**：v1.164.0 于 2026-05-27 发布；官方已有本地 MCP/Agent integrations [S019]。
- **开源/许可证**：Community Edition 为 LGPL-2.1；深层 Pro Engine 为 proprietary。
- **核心表示**：generic AST、pattern/metavariable、单函数/单文件 dataflow 和 rule findings。
- **事实来源**：源码与 YAML 规则；通常不消费真实 compdb，也不建立 Target occurrence。
- **Agent 接口**：CLI、JSON/SARIF、本地 MCP、skills/plugins。
- **公开数据**：官方明确 CE 的单函数/单文件边界；本研究不采用营销页提升百分比。
- **WiFiDemo 直接证据**：适合 W03 的宏约束、API 配对和禁止模式等局部规则；本轮未运行。
- **优点**：规则编写和测试门槛低；源码证据清楚；适合把少量成熟领域规范变为持续检查；Agent 接入现成。
- **缺点**：开源 CE 不具备跨文件/interprocedural C/C++ 深层分析；不理解四 Target 编译差异；finding 不是知识实体数据库。
- **Unknown**：WiFi C parser 对扩展语法的覆盖、规则误报率、宏展开前后匹配行为。
- **代码—领域链接**：每条 rule 可链接 domain policy ID，并把 finding 作为有版本的 evidence；但只能证明“匹配规则”，不能推导完整业务流程。
- **可借鉴**：领域规则包、rule tests、SARIF/MCP 输出和快速反馈；作为检查层而非核心程序分析层。
- **初步分类**：保留为轻量规则组件；排除用 CE 单独承担跨 Target 深度分析。

## 10. Task 4 的阶段性收敛

本轮没有选出单一工具，收敛的是组合边界：

1. **编译真相层不能省略**：Clang compilation database 的“一文件多编译命令”语义与 WiFiDemo 四 Target 直接匹配。无论上层选 CPG、数据库还是 IR，都必须以 Target Profile/compile-command digest 分区。
2. **身份层优先考察开放格式**：scip-clang/SCIP 与 Kythe 都比纯 Tree-sitter 更适合产生可追溯 occurrence；SCIP 轻，Kythe 的 target/revision/provenance 模型更完整。
3. **CPG 保留两个实现候选**：Joern 与 Fraunhofer CPG 使用同一字段继续比较；前者查询/切片成熟，后者 library/pass/overlay 扩展更直接。两者都没有公开证明 WiFiDemo 所需的真实 Target 输入和函数指针质量。
4. **深度分析应可插拔**：SVF/PhASAR 负责 LLVM 层函数指针与 dataflow；Frama-C 负责 C 源码抽象解释、形式规格与 slicing。它们提供的是按需高成本事实，不宜全部预计算进主图。
5. **CodeQL 是重要上界而非默认实现**：查询与模型设计值得借鉴，但 engine 与闭源项目许可使其不符合优先开源核心的方向。
6. **Semgrep 是领域规则执行器，不是图谱**：适合把确认过的局部规范持续化，不能替代跨文件语义。
7. **SVF 的开放源码不等于宽松集成**：技术上保留为函数指针/value-flow 候选，但 AGPL-3.0-or-later 使其部署方式成为独立筛选维度；PhASAR 的 MIT 许可更利于嵌入式组合方案。

### 10.1 当前排除或降级

- 排除“单一 Tree-sitter 图即可回答函数指针、dataflow 和 Target 问题”的假设。
- 排除把未消费真实编译命令的目录级 CPG 当作最终编译事实。
- CodeQL 降为 Benchmark/设计参考，除非后续确认组织已有满足闭源自动化分析的许可证。
- Semgrep CE 降为局部规则组件；Pro Engine 不进入优先开源短名单。
- LLVM IR/SVF/PhASAR/Frama-C 不作为主检索数据库，而作为 Target-specific 按需 analysis provider。

### 10.2 必须进入后续 Benchmark 的问题

| ID | 问题 | 对应 WiFiDemo | 主要候选 | 指标 |
|---|---|---|---|---|
| PA01 | 四 Target 是否产生互不污染的 source occurrence 与宏事实 | W01–W04、W07 | Clang、SCIP、Kythe、两种 CPG | Target precision/recall、source evidence accuracy |
| PA02 | direct call 与同名 static symbol 是否正确消歧 | W08 | SCIP、Kythe、Joern、Fraunhofer CPG | edge precision/recall |
| PA03 | ops 表/函数指针候选是否覆盖真实实现且候选集合可控 | W05 | LLVM AA、SVF、PhASAR、Frama-C、CPG | recall、precision、候选数、耗时 |
| PA04 | Host→Device event 路径能否产生带源码证据的 dataflow/slice | W06 | Joern、Fraunhofer CPG、PhASAR、Frama-C | path precision、gold coverage、slice size |
| PA05 | 外部函数 summary/semantics 错误如何暴露 | W04–W06 | CodeQL、Joern、Fraunhofer CPG、PhASAR | FP/FN、rule provenance、conflict detection |
| PA06 | 修改一个 Target 后哪些事实失效、哪些可复用 | W03、W07 | SCIP、Kythe、CPG、metadata layer | reindex latency、invalidated fact precision |

## 11. 对代码—领域知识链接的新增结论

Task 4 进一步说明领域知识不应直接绑定“函数名”，而应绑定可验证的程序事实：

```text
DomainEntity / Claim
  -> RuleOrSpecification(version, author, confidence)
  -> TargetProfile(revision, compile-command digest)
  -> CodeOccurrence(source span, semantic symbol)
  -> AnalysisFact(kind, generator, configuration)
  -> EvidencePath / Slice
  -> ValidationState(proven | observed | inferred | unknown | invalid)
```

其中有四种成熟机制可学习：Kythe 的 anchor/VName 与 `generates` 边 [S012]，CodeQL/Fraunhofer/Joern 的外部函数 model/summary/semantics [S013][S015][S016]，PhASAR 的 JSON/callback source-sink 配置 [S020]，以及 Frama-C 的 ACSL property 与 proof/alarm 状态 [S018]。共同原则是：领域规则、分析结果和 parser/compiler 事实必须分层，并且能追溯到 Target-specific 源码证据。

## 12. 代码—领域混合知识方案档案

以下档案使用与 R01–R07、A01–A10 相同的字段，但评价对象是知识组织和链接机制，不把文档问答结果当作代码语义准确率。

### H01 — Graphify

- **定位**：把代码、文档、PDF、ADR/RFC 等映射到同一 typed graph，并通过 Skill/CLI/MCP 供 Agent 查询。
- **最新活动**：概念文档更新于 2026-07-01，官方仓库在 2026-08 仍活跃 [S021]。
- **开源/许可证**：官方仓库同时标示 Apache-2.0/MIT 文件；采用前需按具体组件确认适用条款。
- **核心表示**：Tree-sitter 代码节点/边、LLM 语义节点/边、`EXTRACTED`/`INFERRED`/`AMBIGUOUS` 标签、local graph JSON。
- **事实来源**：代码由本地 AST parser；文档/媒体由配置的 LLM；WHY comment、ADR/RFC citation 可成为节点。
- **Agent 接口**：Skill、CLI query/path/explain、stdio/HTTP MCP。
- **公开数据**：官方通用 memory Benchmark 不测 C Target、代码—领域边 precision 或失效修复，不能用于本研究排序。
- **WiFiDemo 直接证据**：未运行；W01–W08 的宏、Target、函数指针均超出公开效果证据。
- **优点**：显式区分解析边、推断边和歧义边；文档与代码可双向遍历；本地开放接口和增量工作流完整。
- **缺点**：Tree-sitter 不是编译事实；公开 schema 缺少 revision-qualified Target occurrence、人工 edge 权威级别和完整 stale lifecycle。
- **Unknown**：C 宏/同名 static/函数指针边质量；文档边的 evidence granularity、rename repair、人工审核与冲突行为。
- **代码—领域链接**：以 inferred doc edge 连接 AST entity，能说明来源类别但不能证明领域关系；必须外接 Target/semantic identity 和 assertion lifecycle。
- **可借鉴**：EXTRACTED/INFERRED/AMBIGUOUS、WHY/ADR 一等节点、path/explain 和 scoped subgraph。
- **初步分类**：混合图短名单/架构参考；不能单独成为 Target-aware 代码事实源。

### H02 — Understand Anything

- **定位**：由 Agent 从仓库结构生成 architecture、process、convention 和 specification 等可读知识资产；R07 已记录其代码探索特征。
- **最新活动**：官方材料访问于 2026-08-13 [S009]。
- **开源/许可证**：MIT。
- **核心表示**：目录/结构分析、LLM 生成领域页面和可浏览关系。
- **事实来源**：代码结构、项目文档与模型推断。
- **Agent 接口**：生成式研究/文档工作流；并非稳定 typed-query code DB。
- **公开数据**：没有代码—领域链接 precision、Target isolation、stale repair 或独立 Agent Benchmark。
- **WiFiDemo 直接证据**：未运行；适合观察是否能生成 Feature/Flow 草稿，不可作为 truth test。
- **优点**：领域页面可读；强调 architecture/process，而非只生成 symbol graph；适合作为人工知识采集入口。
- **缺点**：生成知识的模型/prompt/provenance/confidence 和 revision lifecycle 公开治理不足。
- **Unknown**：外部规范、Target occurrence、人工修正、重命名、矛盾页面和失效传播。
- **代码—领域链接**：主要是 LLM 从代码到领域页面的软链接；若无确定性 anchor 和验证活动，只能处于 inferred 状态。
- **可借鉴**：将“理解产物”独立为可审阅文件，并允许人修改；生成层不直接污染代码事实层。
- **初步分类**：领域知识生成参考，不作为事实或链接底座。

### H03 — LLM-Wiki + WiCER 式知识编译

- **定位**：把原始资料编译成有目录、页面、双向链接和源引用的 Wiki，并以错误/失败 probe 迭代修正。
- **最新活动**：LLM-Wiki 与 WiCER 均发布于 2026-05 [S022][S023]。
- **开源/许可证**：论文/实验材料公开；实现许可证需按对应仓库核验，不在本轮假设为统一组件。
- **核心表示**：Markdown page tree、aliases/tags/facts、bidirectional wikilinks、source archive、Error Book、diagnostic probes。
- **事实来源**：原始文档经 LLM compiler 生成，结构 validator 与 source-grounded checker 修复；WiCER 用失败事实 pinning 重新编译。
- **Agent 接口**：wiki search/read/traversal 或 full-context/KV cache；可包装为本地文件/工具接口。
- **公开数据**：LLM-Wiki 在多文档问题上提升明显但单文档低 2.3 points；WiCER 的 blind compilation catastrophic rate 为 53–60%，1–2 次 refinement 恢复 80% 丢失质量 [S022][S023]。
- **WiFiDemo 直接证据**：未运行；公开实验不含代码、宏或 Target。
- **优点**：保留 raw sources 和 page-level provenance；双向链接适合领域导航；错误/遗漏有显式生命周期和重新验证机制。
- **缺点**：Wiki 是有损派生物；编译/校验昂贵；LLM verifier 近似；不能替代当前代码分析。
- **Unknown**：代码 anchor 接入、revision/Target 更新、规格版本冲突、WiFi 文档规模的 compression/attention crossover。
- **代码—领域链接**：Wiki page 应连到外部 TargetOccurrence ID，而不是复制函数名；source reference 和 diagnostic probe 负责审计及重验证。
- **可借鉴**：raw→compiled→schema 三层、双向 wikilink、Error Book、compile-evaluate-refine。
- **初步分类**：领域叙事/Wiki 层候选；必须与代码身份/事实层组合。

### H04 — RepoMem（Commit/Issue Repository Memory）

- **定位**：以历史 commit/issue 为 episodic memory，以活跃文件摘要为 semantic memory，引导当前代码定位。
- **最新活动**：ICLR 2026 论文与 Microsoft Research 页面当前有效 [S028]。
- **开源/许可证**：论文材料公开；具体实现复用条件需后续核验。
- **核心表示**：历史 commit/issue 检索、活跃文件 summary、Agent memory tools。
- **事实来源**：固定时间点之前的仓库演化历史和生成摘要。
- **Agent 接口**：为 LocAgent 增加 memory search/retrieve tools，再回到当前代码图验证。
- **公开数据**：Verified Acc@5 76.5% 对 LocAgent 71.6%，resolve 40.4% 对 37.0%；历史稀疏分组 Acc@5 反而 -13.1 points [S028]。
- **WiFiDemo 直接证据**：未运行；可利用芯片/feature 历史，但本项目历史密度和 issue 质量未知。
- **优点**：历史能表达当前 snapshot 不含的设计惯例和类似变更；实验证明可改善定位和下游修复。
- **缺点**：memory 是历史线索，不是当前代码事实；相关性错误会明显干扰；主要实验证据来自 Python。
- **Unknown**：WiFiDemo commit/issue 质量、时间衰减、Target-aware retrieval、C 符号映射和最佳 abstention 策略。
- **代码—领域链接**：commit/issue→changed artifacts 是历史证据边；使用时必须解析到当前 revision occurrence 并验证，不能直接继承旧 symbol/file-line。
- **可借鉴**：episodic/semantic memory 分离、严格时间切分、当前代码二次验证、负迁移检测。
- **初步分类**：历史经验检索组件；不是主知识库或确定性链接层。

### H05 — GitHub Copilot Repository Memory

- **定位**：跨 coding/review/CLI Agent 共享 repository-scoped、citation-backed 的可演化事实。
- **最新活动**：2026-05 增加用户/仓库 scope 与删除控制 [S025]。
- **开源/许可证**：专有 GitHub 产品；公开设计可作为架构证据。
- **核心表示**：subject、fact、reason、多个 `file:line` citations、timestamp/scope。
- **事实来源**：Agent 在任务或 Review 中发现并调用 memory tool 写入；使用时检查当前 branch 源码。
- **Agent 接口**：Copilot coding agent、CLI 和 code review 共享 memory。
- **公开数据**：GitHub 第一方 A/B 报告 PR merge 90% 对 83%、review positive feedback 77% 对 75%，p<0.00001；样本量/任务构成未公开 [S025]。
- **WiFiDemo 直接证据**：无；file-line citation 机制可直接借鉴，但缺 Target。
- **优点**：把“何时遗忘”转化为低成本 read-time verification；错误 citation 可自我修正；权限和 repository scope 清晰。
- **缺点**：专有；公开 retrieval/prioritization 简单；没有 typed domain ontology、semantic ID 或 Target occurrence。
- **Unknown**：memory 生成 precision、错误修正率、长期规模、分支合并行为和 C 多 Target 适用性。
- **代码—领域链接**：领域 fact 以多个代码 citation 支撑，当前源码优先；可扩展为 `Target+revision+semantic anchor+file-line`。
- **可借鉴**：citation-backed assertion、just-in-time verification、corrected replacement、scope 和权限。
- **初步分类**：生命周期强参考；产品本身不作为开源实现候选。

### H06 — Progressive Skills / References / MCP

- **定位**：以 Skill metadata 选择领域程序，按需加载 instructions/references，并通过 MCP/API/script 获取当前事实。
- **最新活动**：Google ADK 指南发布于 2026-04，AWS Agent Toolkit 文档当前持续更新 [S024]。
- **开源/许可证**：模式开放；具体 ADK/Toolkit/Skills 各自授权，架构不依赖单一供应商。
- **核心表示**：L1 metadata、L2 SKILL.md instructions、L3 references、deterministic scripts、MCP/API tools。
- **事实来源**：人工/团队维护的程序与资料；运行时工具返回环境/代码事实。
- **Agent 接口**：list/load/read resource 与 MCP tool calls。
- **公开数据**：Google 的约 90% baseline context reduction 是 10-Skill 示例算术，不是正确率实验；SWE-Skills-Bench 提供独立负收益证据 [S024][S027]。
- **WiFiDemo 直接证据**：未运行；可把 Feature/Event 分析方法做成 Skill，而不是把全仓知识塞进 prompt。
- **优点**：渐进披露、上下文可控；稳定 procedure、原始 reference、确定性 tool 职责清楚；天然适合离线开源组合。
- **缺点**：Skill selection 和版本正确性不是自动保证；内容可过期；Skill 不提供代码 identity 或查询引擎。
- **Unknown**：WiFi 领域 Skill 粒度、触发准确率、版本矩阵、Token/收益、自动回归测试与安全治理。
- **代码—领域链接**：Skill 引用 domain ID 和查询模板，MCP 以 Target 参数返回 occurrence/evidence；避免在 Skill 内缓存易漂移 file-line。
- **可借鉴**：metadata/instruction/reference/tool 四层、按需释放、Skill tests 和版本约束。
- **初步分类**：Agent 上下文组织短名单组件；不能替代知识事实和生命周期存储。

### H07 — Specification-as-Skill（SWE-Bench 5G / SWE-Skills-Bench）

- **定位**：把简短、任务匹配的权威规范或工程程序作为推理时领域上下文，并用 paired execution test 评估边际效果。
- **最新活动**：两个 Benchmark 分别发布于 2026-04 与 2026-03 [S026][S027]。
- **开源/许可证**：Benchmark 数据/代码公开；3GPP 文本权利与具体 Skill 内容需独立管理。
- **核心表示**：concise spec Markdown/Skill、task-to-skill mapping、with/without paired condition、deterministic verifier。
- **事实来源**：权威规范条款、公开 Skill、固定 commit 仓库和验收条件。
- **Agent 接口**：在任务上下文中按需注入；不要求建立图数据库。
- **公开数据**：5G 50 项 A/B 总体 +6 resolve points、+12% Token，规格依赖类别 +16.7 至 +25 points、generic 类别为 0；Skills 平均 +1.2%，3 个版本不匹配 Skill 最多 -10%，Token 最高 +451% 且 pass 不变 [S026][S027]。
- **WiFiDemo 直接证据**：未运行；5G Core 的 C/协议规范场景是相邻证据，不等于 WiFi MAC。
- **优点**：直接证明领域知识效用是任务条件性的；paired execution design 可转化为 WiFi Benchmark。
- **缺点**：样本/任务异质；规格摘要由研究者准备；不解决自动链接、更新或冲突。
- **Unknown**：WiFi 规范任务比例、最佳片段长度、自动 clause linking、错误/旧版本规范的负迁移。
- **代码—领域链接**：应记录 `Task/DomainRule -> spec clause/version -> TargetOccurrence -> verifier`，不能只保存一段无来源 prompt。
- **可借鉴**：任务类型分层、paired A/B、Token/负收益、固定 commit 和执行式验收。
- **初步分类**：领域注入评估方法与可选组件；不是独立知识架构。

## 13. Task 5 的知识生命周期收敛

### 13.1 分层对象

| 对象 | 允许来源 | 默认状态 | 变化后的动作 |
|---|---|---|---|
| 代码事实 | compiler/indexer/static analyzer | verified-code | 输入 digest 改变后重建 |
| 推断标签/软链接 | embedding/LLM/聚类 | inferred-candidate/inferred | model/prompt/content 改变后全部重算 |
| 人工知识 | reviewer/领域专家/ADR | manual-reviewed/verified-domain | 依赖 evidence 变化后通知 owner 复核 |
| 原始资料 | 规范、issue、commit、设计文档 | primary-source | 内容/版本不可静默覆盖，生成新 revision |
| 编译知识 | Wiki/page/summary/Skill | derived | source 变化或 probe 失败后 stale/重新编译 |
| 验证记录 | test/analyzer/human review | validation activity | 保留历史，不覆盖旧 verdict |

### 13.2 当前排除或降级

- 排除 embedding score 或 LLM confidence 自动升级为代码事实。
- 排除领域声明只绑定裸函数名或易漂移 file-line。
- 排除不保存 raw sources 的 Wiki/summary 作为唯一真源。
- 排除把所有 Skill、规范和 memory 常驻 prompt；attention dilution 与 Token/负迁移均有实证风险。[S023][S027]
- Graphify/Understand Anything 保留为混合图/知识生成参考，但必须补 Target identity、revision 和 assertion lifecycle。
- GitHub Memory 保留为生命周期参考，产品本身不进入优先开源核心。
- RepoMem 保留为历史检索组件，必须允许历史稀疏或不相关时 abstain。

### 13.3 新增 Benchmark 问题

详细问题见 `docs/research/code-domain-linkage.md` 的 DL01–DL09。Task 6 只基于当前证据给候选分类，不用这些待测问题伪造得分。

## 14. 本轮对架构候选的影响

Task 5 仍不选最终存储技术，但把完整架构的硬要求收窄为：

1. 能表示 repository/revision/Target/occurrence，而不是只有 symbol/file；
2. parser/analyzer fact、rule、manual assertion 和 LLM/embedding candidate 不同层或至少不同状态；
3. 每条领域边能回到当前代码与原始资料，并支持双向导航；
4. 有 assertion-level provenance、confidence、conflict、stale、invalid 和重新验证；
5. Wiki/Skill/memory 按需加载，且允许 abstain/not-applicable；
6. 支持 raw source、compiled knowledge 和 runtime query 的不同更新周期；
7. 后续以 specification-dependent/generic、rich/sparse history、current/stale knowledge 等分层 Benchmark 验证，而不是只测平均通过率。

## 15. Task 6 的候选分层

证据矩阵把纯检索、单独 Tree-sitter 图、直接采用 GitNexus、以 CodeQL 作为默认开放核心、以及未经验证的 LLM/embedding 事实写入，排除为完整方案；它们中的若干能力仍保留为组件或设计参考。[S001–S009][S013][S023][S027]

进入后续实验的不是某个预设赢家，而是三个可替换组件的架构族：L1 编译器原生分层、L2 Target-specific CPG 分层、L3 轻量结构发现加编译器核验。开源偏好只在正确性、效果、成本和运维约束没有决定性差异时作为 tie-break，不能代替实验结论。
