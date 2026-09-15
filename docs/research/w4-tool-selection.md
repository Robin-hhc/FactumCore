# 选型分析：开源工具分类、提及频次与本地部署建议

> 数据源：内部技术社区 154 篇全文（12 案例 C1–C16 + T1–T130 剔除留档 + 工具横评帖等）
> 目的：从调研案例中归纳方案类型，统计开源工具被提及/引用频次，收敛出「代码索引（CodeGraph/codebase-memory-mcp 主选比 + Graphify 对照，2026-09-10 决策以 A 类实现为主）+ 文档管理（LLM-Wiki 自建）」两条线，按评测方案（K0 grep 基线对照）给出本地部署候选与落地路线图
> 日期：2026-09-04（基于 12 案例 + 标准放宽复审后的全量语料重算）；决策与落地路线更新至 2026-09-10
>
> **脱敏说明**：内部工具/系统专有名词改为类别描述（某深度代码知识库工具/某内部文档搜索引擎/某自研静态分析扫描器/某内部代码文档生成 SaaS/代码索引 CLI/深度摄入技能），内部 URL 已删除，内部仓名用「host/device 多仓」等领域概念指代。外部开源工具名（CodeGraph / Graphify / codebase-memory-mcp / tree-sitter / SQLite / MCP / Obsidian / DeepWiki / GitNexus / Understand-Anything 等）未脱敏。
>
> **口径说明（本次重算 vs 2026-09-02 初版）**：① 语料从 140+ 篇扩到 154 篇（新增 C13–C16 四案例 + 第五轮六篇）；② 统计口径统一为「大小写不敏感 + 含命令/包名/MCP 工具变体（如 `/graphify`、`graphifyy`、`codegraph_*`），排除跨工具误配（某内部代码文档生成 SaaS ≠ CodeGraph）」，因此 LLM Wiki/CodeGraph/Graphify 等高频工具数字较初版明显上升，属口径统一所致，非语料突变。

## 一、开源工具提及频次（154 篇全文 grep 统计）

| 工具 | 提及次数 | 出现文件数 | 类型 | 许可证 |
|------|---------|-----------|------|--------|
| **LLM Wiki（Karpathy 概念，Obsidian 为载体）** | 639 | 48 | 文档/知识图谱（概念生态，非单一工具） | MIT（各实现不一） |
| **CodeGraph（colbymchenry）** | 330 | 38 | 代码事实图谱 | **MIT** |
| **Graphify（safishamsi）** | 302 | 17 | 双图一体（代码+文档+多模态） | MIT |
| **某内部代码文档生成 SaaS** | 173 | 28 | 代码→文档自动生成 | 内部（不进开源比对） |
| **codebase（codebase-memory-mcp / CodeBase 仓级索引 / codebase-cli）** | 83 | 16 | 代码事实图谱 | MIT |
| tree-sitter（底层解析技术，非独立工具） | 64 | 22 | 解析层 | MIT |
| Understand-Anything（UA） | 62 | 11 | 代码图谱+可视化 | MIT |
| **某深度代码知识库工具（内源）** | 61 | 17 | 深度代码知识库（4+1 视图+六件套+跨仓契约） | 内源（C14 案例工具） |
| DeepWiki | 60 | 7 | 代码→文档自动生成 | 闭源 SaaS |
| GitNexus | 49 | 9 | 代码事实图谱 | **PolyForm Noncommercial** ❌ 禁商用 |
| 某内部文档搜索引擎 | 23 | 17 | 纯文档检索（BM25+向量+多模态） | 内部（C14 案例对比工具） |
| CodeGraphContext | 19 | 2 | 代码索引→图数据库 | 待核 |
| CocoIndex | 18 | 1 | 语义 RAG 底座（非调用图） | 待核 |
| code-graph-mcp | 16 | 1 | tree-sitter AST 图+混合检索 | 待核 |
| gortex | 10 | 4 | 代码图谱（跨仓） | 待核 |
| agentmemory | 8 | 5 | Agent 记忆 | 待核 |
| 某自研静态分析扫描器（C11） | 7 | 2 | 代码静态分析（类继承/模块依赖/接口实现图） | 自研（C11 案例工具） |

**结论**：LLM Wiki（639/48，概念生态热度，含 Obsidian 载体 + 各开源实现 + 内源封装）和 CodeGraph（330/38）仍是社区里被引用最多的两个；Graphify（302/17）在新增 C13/C16 两个真实 Graphify 部署案例后跃居第三，是「双图一体」路线里唯一有真实代码仓落地 + 明确「为何不全量 Graphify」论证的工具。codebase（83/16）排第四，在 C1 和实战对比帖里作为 CodeGraph 的降级替补出现。

**新案例带出的内部工具**（C14 选型对比帖「某深度代码知识库工具 vs 某内部文档搜索引擎 vs 某内部代码文档生成 SaaS」+ C11 自研）：某深度代码知识库工具（内源）、某内部代码文档生成 SaaS（code→doc）、某内部文档搜索引擎、某自研静态分析扫描器——均为内部/内源工具，**不进本地开源部署比对**，但某深度代码知识库工具的「4+1 视图+六件套+跨仓契约」是代码知识库侧最结构化的参照（见 C14）。

## 二、方案收敛：代码索引（主选比 + Graphify 对照）+ 文档管理（LLM-Wiki 自建）

从调研案例归纳后，我们的方案收敛为**两条线**：**代码图谱索引**用确定性代码图工具（CodeGraph / codebase-memory-mcp 主选比，Graphify 作对照基线）；**文档管理**几乎只有一个成熟路径——**LLM-Wiki 理念的自建图谱仓**（某内部代码文档生成 SaaS/DeepWiki 是闭源 SaaS 不可用、某内部文档搜索引擎/某深度代码知识库工具是内部工具，开源可本地部署且被验证的只有 LLM-Wiki）。原「自带代码 + 文档图谱管理」分类（Graphify/UA 双图一体）**已砍**：Graphify 归入代码索引对照（不承担主链路），文档侧统一走 LLM-Wiki 自建（其余候选退出理由见 A 节 blockquote）。

**最终决策（2026-09-10 讨论定稿，基于社区 130+ 篇文章分析提取的 7 条高质量案例）**：以 **A 类实现为主**——代码侧用确定性代码图（CodeGraph / codebase-memory-mcp 比选后选定，Graphify 作对照）、文档侧用 LLM-Wiki 自建图谱仓，即本节两条线；部分细节可借鉴 **B 类设计思路**；后续也可结合 **Graphify 作为比较**（对照基线，不承担主链路）。依据：A 类基于成熟开源工具、可维可测性高、相关底层软件 C 语言案例较多；B 类大部分案例为 Graphify 工具的简单应用，对复杂业务 + 多仓项目效果不佳，需根据项目特点自开发图谱工具、定义图谱规则，开发量重，且无底层软件 C 语言案例（多为 B 端或 TypeScript/Java/Python 等上层项目）。

### A. 代码图谱索引：CodeGraph / codebase-memory-mcp 主选比 + Graphify 对照（本阶段先做）

| 工具 | 提及（次/篇） | 许可证 | 原理（一句话） | 索引能力 | 查询能力 | 实测注意 |
|------|---------|--------|----------------|---------|---------|---------|
| **CodeGraph** | 330 / 38 | MIT | tree-sitter 解析 AST → 符号/调用图 → SQLite+FTS5 本地存储；预索引 + 文件监听自动同步（2s 防抖）；自带 Node 运行时零依赖 | 20+ 语言、17 框架路由识别；索引快（v1.5.0 较 1.4.1 平均提速 89%，C++ 最慢）；无硬上限（实测 10k+ 文件稳定） | MCP 暴露 8 个查询工具（explore/callers/callees/impact/node/files…）；Token 消耗最低 | 本机已装 v1.5.0；C 侧宏/函数指针/ops 表断链待实测 |
| **codebase-memory-mcp** | 83 / 16 | MIT | tree-sitter + SQLite + MCP，支持多仓 | 多仓；实战（10 仓 7450 文件） | MCP 查询 | 实战中作 CodeGraph 降级替补，多仓误匹配 3 个无关仓（该对比出自 CodeGraph 宣传帖，需自测复核） |
| **Graphify** | 302 / 17 | MIT | **双图一体**：代码 tree-sitter AST（硬连线）+ 文档/PDF/图片 LLM 抽取，两次提取+聚类+分析进同一张图；关系标注 EXTRACTED/INFERRED/AMBIGUOUS 区分事实与推测 | 代码侧 tree-sitter；多模态（文档/PDF/图片）；~10k 节点内存受限 | 图谱遍历 + 交互式 HTML+JSON；Token 消耗极低 | 索引慢（多模态）；结构化内容（代码）优异、零散文档平平；C13/C16 真实部署案例（均 Java） |

> **其余候选不进入本轮比对**：GitNexus（PolyForm 禁商用 + ~4 万文件 OOM 上限）；UA（~2700 节点上限、按需解析无持久化索引、文档侧是代码单向投影而非独立文档管理）；CodeGraphContext / CocoIndex / code-graph-mcp / gortex（提及量低、许可证待核）；某深度代码知识库工具 / 某自研静态分析扫描器（内源/自研，不可本地部署——某深度代码知识库工具的 4+1 视图 + 流程六件套 + 跨仓契约作为代码知识库侧的**设计参照**，C11 的某自研静态分析扫描器思路见下补充）。
>
> 补充：「内核级三引擎融合」（基础软件院创意帖，概念方案未落地）= tree-sitter 语法引擎 + Clang 语义引擎 + 文本引擎（注释/commit/邮件列表），内核特化 container_of 反向依赖边、ops 表函数指针间接调用边——**与我们函数指针/ops 表边界问题（直接 caller 为 0）完全同题**，值得跟踪作者。

### B. 文档管理：LLM-Wiki 理念的自建图谱仓（唯一成熟路径，后续搭建）

**为什么是它**：文档侧候选里某内部代码文档生成 SaaS/DeepWiki 是闭源 SaaS（代码不出本地要求下不可用）、某内部文档搜索引擎/某深度代码知识库工具是内部工具，**开源可本地部署且理念被验证的只有一个——Karpathy 的 LLM-Wiki**（639 次提及 / 48 篇，社区热度第一）。

**这是个啥**：LLM 当「知识编译器」的方法论。传统知识管理是非结构化文档网盘（写完即过期）；传统 RAG 每次查询都从头大海捞针；LLM-Wiki 是**预先整合**——原始文档放 `raw/`，LLM 读后拆解成**页面类型**：实体页（entity：组件/子系统/人物/工具）、概念页（concept：技术概念/机制/方法论）、源摘要页（source summary）、综合页（synthesis：跨源分析）、对比页（comparison）、时间线页（timeline）、矛盾页（contradiction：来源冲突与待验证问题）（七种页面类型），用 `[[wikilink]]` 互链成网，增量维护在 `wiki/`（「你和原始来源之间」）。三层架构：**Schema 层**（CLAUDE.md/AGENTS.md，人 + LLM 共同维护的目录结构/命名/frontmatter/工作流契约）→ **Wiki 层**（LLM 全权维护）→ **原始来源层**（raw/，人策划、LLM 只读）。核心工作流：**ingest → query → lint**（lint 检查孤岛页/重复概念/缺失引用/过期结论/冲突未处理/索引漂移/日志缺失）。**知识随每个来源和每个问题越用越丰富**——高价值问答写回 wiki（Karpathy 原话：Wiki 是持久的复合产物，交叉引用已在那里、矛盾已被标记）。

**跟 Obsidian 啥关系**：LLM-Wiki 是**方法论/概念**，Obsidian 是**载体**——社区里两者几乎同义，因为最流行的实现就跑在 Obsidian Vault 上（Markdown + `[[wikilink]]` 双向链接天然契合）。分工：LLM Agent（CodeAgent CLI + llm-wiki 技能）是编译引擎，Obsidian 只是**可视化展示层**（看知识页面、浏览双向链接关系图谱、Web Clipper 抓网页）。实现链：概念（Karpathy gist）→ 载体（Obsidian）→ 开源实现（bootstrap-skill / karpathy-llm-wiki / graphify 等）→ 内源产品化（某深度代码知识库工具，加了 4+1 视图/六件套/跨仓契约/git 集成）。

**原理：它到底怎么做到与代码链接的**：引擎本身**不读代码**——raw/ 放的是文档，LLM 只做「文档↔文档」的知识编译（上述页面类型互链 + INDEX/Glossary/LOG 枢纽），代码侧由代码索引工具（CodeGraph 等）管，**两张图之间没有引擎预建的边**。链接的「胶水」是**命名/路径对齐 + Agent 消费时编排**，三种动作：
1. **生成时锚点**：写 wiki 文档时，引用代码一律带 `[函数/类名](相对路径:行号)`（C5 锚点密度 ≥80%、C11 file:line）——把文档钉在源码的具体行上；
2. **消费时路由**：Agent 提问那一刻，靠「实体页名=仓名/模块名」（C1）、「三层目录按架构元素名对齐 + config.yml 记录映射」（C9）、「AGENTS.md 关键词→去哪查」（C1/C11）定位到对应代码索引再查；
3. **设计时查询**：设计/需求澄清先查知识库（KB-First，C14），能答的自动答、答不了才问人。
> 为什么这样可行：代码事实（谁调谁）由确定性的代码图保证 100% 准确，文档负责「为什么/业务背景」（LLM 生成），锚点和路由负责在消费时把两者拼起来——**任一侧改动不破坏另一侧**（C1 核心原则：代码仓是唯一真源，Wiki 只是辅助）。

**raw/ 的边界：为什么不直接放代码仓 / spec 文件**：
- **代码仓不进 raw**：引擎是「文档编译器」不是代码解析器。代码事实（谁调谁、符号、调用边）是 tree-sitter/CodeGraph 这类**确定性分析器**的领域——100% 准确、零 Token、增量快；让 LLM 把代码编译进 wiki 会幻觉、过时（代码每次 commit 都在变）、成本爆炸。C1 就是三条平行摄入线：代码索引 CLI 管代码（9,817 文件/52,031 符号）、spec→entities、raw→sources+concepts，**代码根本不进 wiki**。代码与文档的对接发生在「消费时」（实体页名=仓名、行号锚点、AGENTS.md 路由），不在摄入时——这正是 A 类「不预建统一图」的核心。
- **spec 可以进 wiki，但不进 raw**：C1 的实际做法是某内部代码文档生成 SaaS 的 spec.md/design.md **直接映射 entities**（组件职责/接口/配置），raw/ 放的是更原始的服务 Wiki 文档 → sources+concepts，两条摄入线平行。原因有二：① **spec 是产物不是证据**——spec/design 本身是 LLM/某内部代码文档生成 SaaS 生成的，可能有幻觉/过时（C5 门禁防的正是「文档声称代码里没有的东西」），若只从 spec 摄入，「产物的产物」的错误会固化且无从发现；raw 的原始文档（协议/历史资料/评审记录）提供第三方证据，C9 双轨互证正是拿「代码实际」对「知识库」，冲突如实报告。② **职责分离**——spec 仓是活的（SDD 持续迭代、review、版本），raw 是稳的摄入基线（人策展、LLM 只读）；直接连 spec 仓，每次 spec 变更都触发 wiki 重编译，中间隔 raw 做缓冲后只需重 ingest 受影响页（C14 增量更新的 git diff 映射思路）。
- 一句话：**代码图管「怎么连」（确定性）、spec 仓管「应当怎样」（人维护 SSOT）、raw 管「原始证据」（存档）、wiki 管「知识合成」（LLM 维护）**——每层一个所有者、一种变更频率、一种验证方式，互不污染。

**5 个精选案例重新检视**：它们不止链接机制不同，**wiki/文档知识库的内部组织也不一样**——分四种组织维度：

| 案例 | 文档知识库怎么组织 | 目录依据 | 特点 |
|------|-------------------|---------|------|
| C1 | knowledge-base/wiki/：entities/（13 个组件页，驱动适配器/网卡芯片/各子系统…）+ concepts/（6 个，**concept-flow-\* 横切流程 + concept-rule-\* 规则**）+ sources/（28 源摘要）+ purpose.md/schema.md/index.md/log.md | 按知识类型 | 概念页内部分「流程」与「规则」两类 |
| C5 | raw/（代码实证）→ requirement/（需求理解）→ design/（架构还原）**三层递进、禁止跳层** + GAP 四色标注 | 按「事实→需求→设计」递进 | 层级即可信度，文档是代码的投影 |
| C9 | knowledge/<架构元素名>/，与 code/、design/ 三层**同名对齐**，config.yml 记录「哪个元素对应哪些仓 + 哪个知识库」 | 按架构元素 | 目录名=业务对象名，两侧对上 |
| C11 | 五类语义文档：ARCHITECTURE.md + domain-models/ + design-decisions/ + api-contracts/ + data-models/ | 按文档类别 | 从 Karpathy 的 concepts/entities 转制 |
| C14 | knowledge/global/（**contracts/** 26 份跨仓契约 + domains/ 15 业务领域 + use-cases/ 5 端到端用例）+ repos/{repo}/（overview/architecture/api-surface/data-models/constraints/specifications/candidate-flow + **flows/ 六件套**：调用树/主干流程/分支/跨边界数据流/数据结构/自查报告 + submodules/） | 按「跨仓 + 仓库 + 流程」 | 最结构化，代码知识库侧参照 |

链接机制（三动作在 5 案例的分布）：

| 案例 | 生成时锚点 | 消费时路由 | 设计时查询 |
|------|-----------|-----------|-----------|
| C1 | — | 实体页名=仓名 + Auto-Trigger 关键词路由 + P0–P3 加载优先级 | — |
| C5 | `[类名](路径:行号)` 密度 ≥80% + code_evidence_verifier 门禁 | — | — |
| C9 | — | code/knowledge/design 同名对齐 + config.yml + 双轨问答（wiki Agent 答 Why + 代码 Agent 答 How + 主 Agent 互证） | — |
| C11 | 二层文档引一层代码位置（file:line） | AGENTS.md 指针导航「改 X 先读 Y 再查 Z」 | — |
| C14 | — | — | KB-First 查询（query skill，4/6 澄清问题 KB 自动答） |

**wiki 内部组织方式怎么选**（按 flow / entities / feature 还是别的）：社区 + 案例里出现的组织维度有四种，各有适用场景：
1. **按知识类型**（entity/concept/source/synthesis/comparison/timeline/contradiction）——Karpathy 原版（社区多篇实战一致），适合**文档型知识**：页面类型语义清晰、lint 规则好写；
2. **按流程**（flows 六件套）——C14 某深度代码知识库工具，适合**流程分析密集型**场景（我们的 RQ2 代码→流程解释正属此类）；
3. **按需求/模块/决策**（features/modules/decisions，request+spec+implementation+verification 四件套）——C4 园区知识库，适合**SDD 需求流**、贴合上库记录维护；
4. **按架构元素对齐**（code/knowledge/design 同名 + config.yml）——C9，适合**多仓两侧对齐**。

> **我们的取舍**：文档侧知识库**以「按知识类型」为骨架**（entities/concepts/sources + 枢纽文件），但 **concepts/ 内部分 concept-flow-\*（横切流程：TX/RX 通路、Event-Message 机制、函数指针/ops 表分发）与 concept-rule-\*（设计规则）**（C1 的做法）——我们的核心知识就是流程，flow 是最高频的提问对象；同时**吸收 C14 的 global/ 跨仓契约目录**（host↔device 的接口/Event-Message 调用链就是我们的「跨仓契约」）、**C4 的 decisions/**（长期取舍，如 ring 大小、ops 表 vs if-else）、**outputs/**（查询产出回流，知识复利）。不采用 C5 的递进层次组织 wiki 内部（那套更适合代码→文档的逆向工程产物，我们的文档侧是领域知识，不是代码投影）。

**结合我们的项目：文件夹怎么分配**。三仓 workspace（C1 结构与我们的场景最贴——同为多仓网卡驱动）：

```
wifi-kb-workspace/
├── AGENTS.md            # 入口指南：Schema（目录/命名/frontmatter/工作流契约）+ 指针导航 + 关键词路由
├── codebase/            # 代码侧：host/device 多仓 git submodule 只读挂载 + .codegraph/ 代码索引（C1）
├── codespec/            # spec 仓：SDD 流程维护的 spec.md/design.md（SSOT，后续搭建，C1）
├── knowledge/           # 文档侧：LLM-Wiki 图谱仓
│   ├── raw/             # 原始文档：协议/设计/历史资料（人策划、LLM 只读）
│   └── wiki/
│       ├── entities/    # 实体页：模块/子系统（wal/hmac/dma → wal.md/hmac.md/dma.md）＝命名路由
│       ├── concepts/    # 概念页：concept-flow-*（TX/RX 通路、Event-Message、ops 表分发）+ concept-rule-*（规则）
│       ├── sources/     # 源摘要页：每篇原文留一页
│       ├── global/      # 跨仓知识（C14）：contracts/（host↔device 接口与 Event-Message 契约）+ use-cases/（端到端链路）
│       ├── decisions/   # 长期取舍（C4/C11）：ring 大小、ops 表 vs if-else、芯片差异
│       ├── outputs/     # 查询产出回流：问答综合/对比，越用越丰富
│       ├── index.md     # 全局索引（带一句话摘要，供 LLM 快速纵览）
│       ├── glossary.md  # 术语表（802.11/WiFi MAC 术语中英对照，双链枢纽）
│       ├── log.md       # 操作日志（只追加，grep 可解析）
│       ├── purpose.md   # 知识库目标与关键问题（C1）
│       └── schema.md    # Wiki 结构规则 + YAML frontmatter 规范（C1）
├── .skills/             # 工具链：代码查询 / LLM-Wiki / SDD 流程技能（C1）
└── config.yml           # 代码仓 ↔ 架构元素 ↔ wiki 实体映射（C9，两侧对齐的前提）
```

**消费时：模型怎么从 wiki 找到代码（不止命名对齐）**。文档侧不需要「每个函数都标注链接」——链接发生在「文档给出符号/语义 → 代码索引确定性解析」这层，四条通道：
1. **符号精确解析（代替 grep）**：文档写的函数名/符号名，消费时走代码索引的**符号表查询**，不是 grep 字符串匹配——C1 的代码索引 CLI 预建 52,031 个符号（每仓精确计数），`代码索引 repo query <仓名> --query <符号> --kind hybrid --format json`；CodeGraph 对应 node/search。符号表由 AST 解析预建，**区分同名、返回文件:行 + 签名 + 调用边**，查询是索引查找（毫秒级）。「实体页名=仓名」的作用正在于此：**把符号查询限定到正确仓库**，而不是为了 grep 命中。
2. **语义→符号映射层**（C11 domain-models/）：业务术语 ↔ 代码包/符号的映射表沉淀在文档里（「订单」→ com.example.order；「结算服务对应哪个包」），消费时 LLM 先读映射拿到**正确的符号名**再走通道 1——解决「知道业务、不知道代码叫啥」的盲搜。这是文档侧真正核心的链接资产：**不是链接到具体行，而是链接到「正确的符号名」**。
3. **确定性调用图遍历**：文档给「入口符号 + 意图」，代码图沿 callers/callees/impact 确定性走（CodeGraph 8 个查询工具、C11 用代码图符号查询对账 scan 产物查漏补缺）——链接发生在**查询链**上：从文档给的入口出发，图自己把上下游串起来，不需要每个函数都标注。
4. **消费时双 Agent 对账**（C9）：wiki Agent 答 Why（文档语义）、代码 Agent 答 How（代码实际）、主 Agent 交叉印证——文档标注可能过时/写错，但代码 Agent 的查询结果是**对账基准**，冲突如实报告，而不是将错就错。
> 效率对比（C1 自报）：跨仓分析 240→15min、问题定位 180→20min——快在「符号表索引查找 + 限定仓库 + 沿图走」，不是靠 grep 全仓扫。

**链接约定怎么落地**（对应上面的三种动作）：
- **生成时锚点**：wiki 文档里引用函数一律写 `[函数名](codebase/.../src.c:234)`；代码 merge 触发 git diff → 锚点校验门禁（C5 code_evidence_verifier 思路，声称的符号必须在源码里真实存在），失效即重跑受影响子域（C5 实测省 50–80%）；
- **消费时路由**：实体页名 = 模块/仓名（wal.md ↔ codebase 里 wal 仓）；AGENTS.md 写死路由表（TX/RX 通路 → concepts/concept-flow-tx-rx.md，代码/实现 → codegraph 查询，设计/规范 → codespec/specs/）；查询走双轨——wiki Agent 答 Why + 代码 Agent 答 How + 主 Agent 交叉印证（C9）；
- **设计时查询**：SDD 澄清先查 wiki（KB-First），能答的自动答、答不了才问人（C14）；
- **spec 与 raw 两条摄入线**：codespec/ 的 spec.md/design.md 直接映射 wiki 实体页（C1：spec/design → entities/\*，组件职责/接口/配置），knowledge/raw/ 的原始文档映射 sources+concepts——spec 变更 → 只重 ingest 受影响实体页（C14 增量更新的 git diff 映射思路）并做冲突检测；codespec/ 是 SSOT、wiki 只是辅助（C1 原则）。

**怎么用**：工具链 = CodeAgent CLI + llm-wiki 技能（开源基础能力）+ 深度摄入技能（可选增强）+ Obsidian（可选）。四个操作：
- `/wiki-init`：初始化 knowledge/ 目录（raw/ 只读 + wiki/ 骨架 + index.md/glossary.md/log.md/purpose.md/schema.md），Schema 写进 AGENTS.md；
- `/wiki-ingest`（基础）/ 深度摄入技能（3 轮反思递进提取 + 自动健康检查）：文档放 raw/ → LLM 提取实体概念 → 建/更新页面 → 维护双向链接 → 更新索引日志，一个源文件可能产出 10-15 个页面；
- `/wiki-query`：语义检索，给出带引用的答案；
- `/wiki-lint`：机械检查（孤立页面/失效链接）+ 语义检查（矛盾/过期/索引漂移），保持知识库健康。
Wiki 可暴露为 MCP 服务（关键词搜索/语义搜索/笔记读取），供 Agent 直接调用。

**实测注意（内网模型 + 真实业务文档）**：准确率 8/10 优于 GraphRAG、lint 能抓孤立页/失效链接；但**单 query 2–5 分钟、Token 成本高、依赖首次 ingest 质量**（hex 文件切分过细出 6 万 md 翻车）——自建时切分粒度要控制。

## 三、评测方案：代码工具主选比 + Graphify 对照 + 文档链路联测

### 阶段划分（决策后三条线错峰推进）

| 阶段 | 内容 | 状态 |
|------|------|------|
| **本阶段（先做）** | 代码索引工具**主选比**：CodeGraph vs codebase-memory-mcp（A 类确定性代码图，二选一） | **进行中**（题目征集中） |
| 本阶段（并行） | **Graphify 对照**：同一套题跑 Graphify，验证「B 类在复杂业务 + 多仓 + C 语言上效果不佳」的样本结论 | 与主选比并行 |
| 本阶段（并行） | **LLM-Wiki 文档链路联测**：建最小 wiki 骨架，验证「wiki→代码」链接四通道能跑通 | 与主选比并行 |
| 后续搭建 1 | **LLM-Wiki 自建图谱仓**（文档管理，二·B 节） | 独立搭建，无需比对 |
| 后续搭建 2 | **spec 仓**（SDD 流程维护的规格文档仓） | 后续搭建，与 LLM-Wiki 配套 |

> **为什么不是「三工具并列比选」**：2026-09-10 决策已定——**A 类实现为主**（确定性代码图 + LLM-Wiki 文档侧），因此：
> - 代码侧只在两个 A 类确定性代码图工具里**二选一**（CodeGraph / codebase-memory-mcp），这是**主选比**，结论直接影响主链路；
> - **Graphify 是 B 类代表**，保留在评测里作**对照基线**，用来验证样本分析里的判断（复杂业务 + 多仓 + C 语言下 B 类效果不佳），**不进入推荐**；
> - **LLM-Wiki 是唯一可落地的文档侧方案**（二·B 节，某内部代码文档生成 SaaS/DeepWiki 闭源 SaaS、某内部文档搜索引擎/某深度代码知识库工具内部），不存在工具比选，直接按 B 节路径搭建；但它与代码索引的链接通道（四通道）是我们方案的核心假设，需要提前联测。

### 基准题（沿用评测方案）

按以下口径出题与评分（详见评测集「出题表」与模板文档）：

- **两类题**（从应用场景出发，不按工具能力分）：**NL→代码**（自然语言描述需求/改动意图 → 定位相关代码 file:line/调用链）、**代码→业务**（给一段代码 → 讲清业务流程/设计意图/上下游）
- **难度**：易（单文件内定位）/ 中（跨 2–3 文件/模块）/ 难（跨仓/函数指针/宏/ops 表/隐式调用）
- **目标 22 题**：NL→代码 11 + 代码→业务 11（易 6 / 中 10 / 难 6）
- **征集状态**：**已开始**，全组每人 3–5 题、从迭代开发真实场景出发，**预计超过 20 题真实问答**用于测试；收齐后把「正确答案要点」拆成结构化 gold——`key_facts`（必须命中，每条 1 分）/ `nice_facts`（加分，每条 0.5 分）/ `forbidden_claims`（幻觉，每条 -2 分），并逐题标注「纯代码可答 / 纯文档可答 / 需两侧协同」，用于区分 A 线（代码生成文档）与 B 线（人工领域知识）下的预期差异

### 评测设计（三线跑法）

跑法三线：

1. **主选比**：CodeGraph 与 codebase-memory-mcp 各自在 **host/device 多仓**（C 驱动，函数指针/ops 表边界问题）上索引，跑**同一套基准题**（同模型/同 prompt/同预算），按四个维度记分；
2. **Graphify 对照**：同一套基准题跑 Graphify，重点看「难」类题（跨仓/函数指针/宏/ops 表）是否如样本分析预期地失效——对照结果只作验证证据，**不进推荐**；
3. **文档链路联测**：用最小 LLM-Wiki 骨架（raw/ + wiki/ 一个实体页 + 一个 concept-flow 页）联测「wiki→代码」四通道（符号精确解析 / 语义→符号映射 / 确定性调用图遍历 / 双 Agent 对账），用基准题里标注「需两侧协同」的题目验证链接假设。

四个维度（主选比记分，对照参考）：

**① 索引能力**（一次性成本，决定能否跑起来）
- 索引时间：全仓首次索引耗时（实测：CodeGraph 预构建快、v1.5.0 较 1.4.1 平均提速 89%；Graphify 多模态抽取慢；codebase-memory-mcp 待测）
- 资源占用：内存/磁盘（实测：Graphify ~10k 节点内存受限；CodeGraph 无硬上限、实测 10k+ 文件稳定）
- **C 语言覆盖**：tree-sitter C 能否正确建**宏/函数指针表/ops 表**的符号与调用边——我们的核心难点（函数指针直接 caller=0）
- 增量同步：文件监听自动增量（CodeGraph 2s 防抖）vs 手动重索引

**② 查询能力**（每次问答的成本与可达性）
- MCP 工具集：CodeGraph 8 个查询工具（explore/callers/callees/impact/node/files…）；codebase-memory-mcp 多仓查询；Graphify 图谱遍历+交互式 HTML/JSON（对照）
- 跨仓：host/device 多仓各自索引 vs 合并索引，跨仓调用链能否串起来（C1 适配点）
- **函数指针/ops 表**：caller=0 时 callers/impact 能否给出间接调用链——**主选两工具差异的主要暴露点**
- 查询失败率：同一题在工具上答不出来的次数

**③ 资源成本**
- 时间：单题响应时间；Token：单题消耗（实测：CodeGraph Token 最低）

**④ 事实正确率**（最终胜负手）
- 按 gold 打分：key_facts 命中率 / nice_facts 加分 / forbidden_claims 幻觉数
- Agent 正确率：完整问答链（NL→代码定位→代码→业务解释）的整体正确

**输出**：主选比得分表（每维度 + 总分）→ 能力画像（谁快 / 谁全 / 谁省 Token / 谁断链少）→ 推荐结论（CodeGraph / codebase-memory-mcp 二选一 + 降级替补关系）；Graphify 对照结果单独一栏（验证/证伪样本判断）；文档链路联测结论（四通道哪条通、哪条要补，写回二·B 节落地）。

### 原则与已知注意

- **基线对照**：保留 grep/rg（K0）作固定下限，区分「工具增益」与「题本身 grep 就能答」
- **对照与主选分开记分**：Graphify 对照结果不参与主选排名，只作为「B 类不适合我们场景」的验证证据
- **案例和厂商自称数据仅做参考**：对比帖均出自厂商/社区，只作方向参考，最终以本地实测为准
- **函数指针/ops 表断链**：好题示例专门留了这类题（ops 表/函数指针表设计意图），是主选两工具差异最可能暴露的地方
- **内部工具不进本地部署比对**：某深度代码知识库工具（内源，C14）、某内部代码文档生成 SaaS、某内部文档搜索引擎、某自研静态分析扫描器（C11）无法在开源基准上部署实测；某深度代码知识库工具的「4+1 视图+六件套+跨仓契约」与 C13 的「LLM Wiki+Graphify 异构混合」作为**设计参照**而非部署候选

---

## 四、落地路线图：从评测到知识库建成与运营

评测不是终点，选型结论要落到「知识库真被迭代开发用起来」。以下按阶段列出落地步骤、依赖的文档与流程建立。

### 阶段 0：工具比选（本阶段，进行中）

- **步骤**：全组征集真实场景题 → 标注 gold（key_facts / nice_facts / forbidden_claims + 「纯代码可答/纯文档可答/需两侧协同」）→ 主选比（CodeGraph vs codebase-memory-mcp，四维度记分）→ Graphify 对照 + LLM-Wiki 链路联测并行 → 选定代码索引工具、确认链接四通道。
- **依赖文档/流程**：评测集「出题表」（模板文档）、gold 结构化标注规范、基准题 22 题、K0 grep 基线。
- **产出**：工具推荐结论 + 链路联测结论（回写三节，作为阶段 1 的输入）。

### 阶段 1：代码侧落地（选型后第 1–2 周）

- **步骤**：建三仓 workspace 骨架（codebase / specs / knowledge）→ host/device 多仓 git submodule 只读挂载 → 选定工具全仓建索引 → 写 AGENTS.md 入口路由 + config.yml 映射。
- **依赖文档/流程**：C1 workspace 结构（三仓骨架）；C1 索引口径（统一索引、符号表计数、hybrid 查询、P0–P3 加载优先级）；C9 config.yml 机制（仓 ↔ 架构元素 ↔ wiki 实体映射）；AGENTS.md 模板（Schema + 指针导航 + 关键词路由）。
- **验收**：全仓索引完成；「纯代码可答」类题用选定工具直接能答（对照基准题 gold）。

### 阶段 2：文档侧落地（LLM-Wiki 建库，第 3–6 周）

- **步骤**：收集 raw/ 原始文档（协议/设计/历史资料，人策展、LLM 只读）→ /wiki-init 建骨架 → /wiki-ingest 分批摄入（控制切分粒度，防 hex 文件切分过细翻车）→ /wiki-lint 巡检 → 按「按知识类型骨架 + concept-flow/rule + global 契约 + decisions/ + outputs/」组织（二·B 节文件夹分配）。
- **依赖文档/流程**：二·B 节文件夹分配；llm-wiki 技能四操作（/wiki-init、/wiki-ingest、/wiki-query、/wiki-lint）；深度摄入技能（可选增强）；C1/C14/C4/M2 的 wiki 组织取舍；Obsidian（可选可视化层）。
- **验收**：核心组件实体页（wal/hmac/dma 等模块）+ TX/RX 通路 concept-flow 页建成；lint 干净（无孤岛页/失效链接）。

### 阶段 3：spec 仓 + SDD 流程接入（第 6 周起，与迭代开发衔接）

- **步骤**：spec 仓建立 → SDD 流程产出 spec.md/design.md（SSOT）→ 锚点标注规范（`[函数名](路径:行号)`）→ 锚点校验门禁接 CI → 上库记录驱动增量重跑。
- **依赖文档/流程**：SDD 流程（proposal/design/spec/task 文档流及模板）；C5 锚点门禁思路（代码证据校验式，防文档幻觉）；C14 增量更新（git diff 映射）；上库记录流程（git 提交历史 / CI 门禁）。
- **验收**：新迭代 spec 带锚点；代码 merge 时门禁自动校验锚点有效性、失效即定位并重跑受影响子域。

### 阶段 4：链路联测与运营（持续）

- **步骤**：双轨问答上线（wiki Agent 答 Why + 代码 Agent 答 How + 主 Agent 交叉印证）→ 上库记录驱动增量重跑 → 知识复利回流（outputs/）→ 定期 wiki-lint + 冲突检测巡检。
- **依赖文档/流程**：C9 双轨问答编排；C5 增量重跑（实测省 50-80%）；outputs 回流（查询产出写回 wiki）；C4 decisions/（长期取舍记录）；C6 冲突检测思路（文档矛盾巡检）。
- **验收**：迭代开发中 Agent 问答准确率达标；文档保鲜率（锚点失效即时发现、wiki 无孤岛/矛盾）。

### 落地依赖清单（哪些文档/流程要提前建立）

| 依赖物 | 来源案例/方法 | 用途 | 建立时机 |
|--------|--------------|------|---------|
| 评测集「出题表」+ gold 标注 | 评测方案 | 基准题与打分 | 阶段 0（进行中） |
| AGENTS.md（Schema + 指针导航 + 关键词路由） | C1/C9/C11 | 入口导航与链接路由 | 阶段 1 |
| config.yml（仓 ↔ 架构元素 ↔ wiki 映射） | C9 | 两侧对齐 | 阶段 1 |
| 三仓 workspace 骨架 | C1/C5/C9/C11/C14 | 代码/spec/wiki 分离 | 阶段 1 |
| llm-wiki 技能 + 深度摄入技能 | LLM-Wiki 方法论 / C1 | wiki 建库四操作 | 阶段 2 |
| raw/ 原始文档库（人策展） | C1 | 文档摄入基线 | 阶段 2 |
| SDD 流程文档流（proposal/design/spec/task 模板） | SDD 方法论 | spec 仓 SSOT 产出 | 阶段 3 |
| 锚点校验门禁 + 上库记录流程 | C5/C11 | 防文档幻觉、增量重跑 | 阶段 3 |
| wiki-lint / 冲突检测巡检 | C9/C6 | 文档保鲜 | 阶段 4 |
| 双轨问答 Agent 编排 | C9 | 消费时链接 | 阶段 4 |
