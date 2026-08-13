# WiFi MAC 代码知识架构方案调研与候选收敛执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Only use `superpowers:subagent-driven-development` if the user explicitly requests subagent delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一篇基于可审计公开证据的 WiFi MAC 代码知识架构调研，系统比较成熟方案、排除明显不适配者、提取可借鉴设计，并形成开源优先的后续 Benchmark 候选短名单。

**Architecture:** 研究过程分为证据台账、目标工作负载案例、解决方案档案、代码—领域知识链接模式、横向证据矩阵、候选收敛和论文综合七个边界清晰的产物。任何数字和能力声明先进入证据台账，再进入方案档案与正文；无法由公开证据裁决的问题进入后续 Benchmark 清单，不在当前研究中通过临时实验补齐。

**Tech Stack:** Markdown、Git、PowerShell、`rg`、GitHub/项目官方文档、论文原文、AI 公司官方技术文章、WiFiDemo 源码只读案例。

## Global Constraints

- 当前成果是成熟方案调研与候选收敛，不要求给出唯一或最终选型。
- 不运行候选工具，不开展 WiFiDemo 对比实验，不实现生产系统。
- WiFiDemo 只用于目标结构和代码案例；引用必须包含文件、符号和当前行号。
- 主要来源只允许论文原文、AI 公司官方技术文章、开源项目官方资料和公开 Benchmark。
- 近期资料优先；经典旧资料可用于仍然有效的基础技术，但必须解释持续相关性。
- 第一方 Benchmark、独立实验、公司实践和功能说明必须明确区分。
- 数字声明必须记录样本、模型、基线、指标定义、时间和限制。
- 不同定义的 accuracy、coverage、pass rate、F1、Token 和 tool calls 不直接合并。
- 缺少可比数据的能力标记为 `unknown`，不换算为零分，也不根据功能列表填入准确率。
- 深度程序分析按技术路线中立调查；Joern 只是候选之一，不作为默认基线或预设答案。
- 每个混合知识方案必须说明代码实体与领域知识如何链接、如何双向导航、如何绑定 Target/revision，以及如何失效和重新验证。
- 外部案例优先选择嵌入式项目；样本不足时允许选择具有相关结构的其他开源 C 项目。
- 效果相近仅表示公开证据未显示决定性差异；此时优先让开源、自托管、接口开放的方案进入后续 Benchmark。
- 用户新增的 `目标代码仓注意事项.md` 是只读研究输入；未经用户另行授权，不修改或纳入本计划的提交。

## File Map

- Create: `docs/research/source-ledger.md` — 来源登记、证据等级、数字语境和引用状态的唯一台账。
- Create: `docs/research/wifidemo-workload-casebook.md` — WiFiDemo 结构特征和代码案例，不含工具效果结论。
- Create: `docs/research/solution-inventory.md` — 每个成熟方案的统一档案、优缺点、适用边界和可借鉴设计。
- Create: `docs/research/code-domain-linkage.md` — 代码事实与领域知识之间的链接模式、身份、provenance 和生命周期比较。
- Create: `docs/research/evidence-matrix.md` — 方案与 WiFi MAC 硬约束的横向证据矩阵。
- Create: `docs/research/benchmark-backlog.md` — 当前公开证据无法裁决、需后续实验回答的问题。
- Modify: `research.md` — 面向读者的最终调研论文，引用上述证据但保持自包含。
- Read only: `目标代码仓注意事项.md` — 目标场景约束输入。
- Read only: `E:/WiFiDemo/WiFiDemo/**` — 项目结构和代码案例来源。

---

### Task 1: 建立证据台账与论文骨架

**Files:**
- Create: `docs/research/source-ledger.md`
- Modify: `research.md`

**Interfaces:**
- Consumes: 已确认的研究设计 `docs/superpowers/specs/2026-08-13-wifi-mac-knowledge-architecture-research-design.md`。
- Produces: 后续所有任务共用的来源编号 `S001`、`S002`…和固定论文章节。

- [ ] **Step 1: 创建来源台账说明与记录模板**

在 `docs/research/source-ledger.md` 中写明每条来源必须包含：来源编号、标题、发布日期、来源类型、发布者、原始 URL、访问日期、证据等级、研究对象、样本量、模型/Agent、基线、指标、主要数字、限制、第一方/独立属性、正文使用位置和核验状态。

核验状态只使用：`discovered`、`primary-read`、`claim-verified`、`rejected`。

- [ ] **Step 2: 为来源类型和证据等级写出判定规则**

明确区分：论文受控实验、独立复现、公司生产实践、项目第一方 Benchmark、功能说明。写明公司实践只能证明采用和工程经验，功能说明只能证明接口或能力宣称。

- [ ] **Step 3: 将 `research.md` 重构为已批准的十一章骨架**

章节固定为：摘要、背景、研究方法、工作负载模型、成熟方案、架构族比较、WiFi MAC 适配、证据缺口、候选收敛、有效性威胁、结论。保留现有可复核内容，但把提前给出的最终架构结论移回相应候选分析位置。

- [ ] **Step 4: 检查台账字段和论文标题完整性**

Run:

```powershell
rg -n '^## ' docs/research/source-ledger.md research.md
rg -n 'S[0-9]{3}|discovered|primary-read|claim-verified|rejected' docs/research/source-ledger.md
```

Expected: 台账字段和十一章标题均可定位；没有空白标题。

- [ ] **Step 5: 提交研究骨架**

```powershell
git add -- docs/research/source-ledger.md research.md
git diff --cached --check
git commit -m "docs: establish architecture research evidence ledger"
```

### Task 2: 建立 WiFiDemo 工作负载案例集

**Files:**
- Create: `docs/research/wifidemo-workload-casebook.md`

**Interfaces:**
- Consumes: `目标代码仓注意事项.md` 和 `E:/WiFiDemo/WiFiDemo` 当前源码。
- Produces: 供论文“工作负载模型”和方案适配分析引用的案例编号 `W01` 至 `W08`。

- [ ] **Step 1: 固定八类案例与其研究意义**

案例必须覆盖：Host 共代码、Device 按芯片编译、Target-specific 宏、条件编译路径差异、运行时 ops 选择、Host/Device Event 链、公共代码归属、日志/同名符号定位。

- [ ] **Step 2: 从当前源码定位每个案例的入口符号**

Run:

```powershell
rg -n 'CHIP_TYPE|_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD' E:/WiFiDemo/WiFiDemo/CMakeLists.txt E:/WiFiDemo/WiFiDemo/host/CMakeLists.txt E:/WiFiDemo/WiFiDemo/device/CMakeLists.txt
rg -n 'chip_ops_select|hal_ops_select|spec_select|platform_init' E:/WiFiDemo/WiFiDemo/host
rg -n 'hcc_tx_event_send_to_device|dpa_forward_to_device|frw_event_dispatch|hcc_device_rx_handler' E:/WiFiDemo/WiFiDemo/host E:/WiFiDemo/WiFiDemo/device
```

Expected: 每类案例至少找到一个源码或构建文件入口；行号以执行时输出为准。

- [ ] **Step 3: 为每个案例写结构、代码证据和架构要求**

每个 `Wxx` 使用固定字段：问题模式、最小代码片段、`file:line`、为什么普通调用图不足、候选架构必须表达什么、当前研究不声称什么。

- [ ] **Step 4: 交叉核对案例没有工具性能结论**

Run:

```powershell
rg -n -i '更准确|优于|提升|降低.*token|precision|recall|pass rate' docs/research/wifidemo-workload-casebook.md
```

Expected: 若有匹配，只能出现在“当前研究不声称”字段；正文不得把代码案例写成工具 Benchmark。

- [ ] **Step 5: 提交工作负载案例集**

```powershell
git add -- docs/research/wifidemo-workload-casebook.md
git diff --cached --check
git commit -m "docs: capture WiFiDemo architecture workload cases"
```

### Task 3: 调研代码检索与语法结构图方案

**Files:**
- Modify: `docs/research/source-ledger.md`
- Create: `docs/research/solution-inventory.md`

**Interfaces:**
- Consumes: Task 1 的来源字段和 Task 2 的 `Wxx` 场景。
- Produces: 源码/文本检索基线与 Tree-sitter/结构图类方案档案。

- [ ] **Step 1: 建立统一方案档案模板**

每个方案固定记录：定位、最新活动、开源与许可证、核心表示、事实来源、Agent 接口、公开数据、目标场景直接证据、优点、缺点、`unknown`、可借鉴设计、初步分类。

- [ ] **Step 2: 登记代码检索基线的一手资料**

至少覆盖 lexical/BM25、向量检索、RepoMap/仓库地图和近期 Coding Agent context retrieval Benchmark。只登记原论文、作者项目或官方资料。

- [ ] **Step 3: 登记结构图方案的一手资料**

至少覆盖 Codebase-Memory、CodeGraph、GitNexus、Understand Anything，以及检索中发现的同类近期成熟方案。对每项核对实际开源状态、支持语言、最近 release/commit 和公开 Benchmark 方法。

- [ ] **Step 4: 提取数字并保留实验语境**

每个性能数字在台账中同时记录样本量、语言、模型、基线和第一方/独立属性；只把 `claim-verified` 数字写入方案档案。

- [ ] **Step 5: 对照 `W01` 至 `W08` 填写直接证据与 `unknown`**

没有宏密集、多 Target C/C++ 数据时写 `unknown`；项目宣称支持 C/C++ 不能替代 Target correctness 证据。

- [ ] **Step 6: 验证方案档案字段齐全**

Run:

```powershell
rg -n '^## |^### ' docs/research/solution-inventory.md
rg -n 'first-party|independent|unknown|许可证|可借鉴设计|初步分类' docs/research/solution-inventory.md
```

Expected: 每个方案均包含证据属性、未知项和可借鉴设计。

- [ ] **Step 7: 提交代码检索与结构图调研**

```powershell
git add -- docs/research/source-ledger.md docs/research/solution-inventory.md
git diff --cached --check
git commit -m "docs: survey code retrieval and structural graph systems"
```

### Task 4: 调研语义代码表示与深度程序分析路线

**Files:**
- Modify: `docs/research/source-ledger.md`
- Modify: `docs/research/solution-inventory.md`

**Interfaces:**
- Consumes: 统一方案档案和 WiFiDemo `Wxx` 场景。
- Produces: 编译器语义索引/IR、可查询程序表示、CPG、CFG、数据流和程序切片路线的证据化档案。

- [ ] **Step 1: 先定义技术中立的路线与纳入标准**

路线至少包括：编译器 AST/索引与 IR、跨文件语义索引、可查询代码数据库、CPG、声明式静态分析、CFG/控制依赖、dataflow/taint 和程序切片。统一按 C/C++ 预处理输入、compile database、跨 translation unit、函数指针、证据位置、查询接口、开源性和维护状态筛选。

- [ ] **Step 2: 调研编译器原生语义索引和 IR 路线**

从 Clang AST/LibTooling/index、LLVM IR 及检索到的活跃同类方案中选择有官方资料和可用接口的代表；记录它们提供的是编译事实、交叉引用还是深度分析，不能把编译器能力自动等同于 Agent-ready 知识系统。

- [ ] **Step 3: 调研可查询代码数据库和声明式分析路线**

覆盖 CodeQL 类代码数据库、Kythe 类交叉引用系统及检索到的 C/C++ 活跃项目。分别记录源代码是否开放、查询层是否开放、数据是否可导出、是否适合完全离线内部部署，以及公开数据能证明什么。

- [ ] **Step 4: 调研 CPG 和图式程序表示路线**

覆盖 CPG 的经典定义、Joern、Fraunhofer CPG 及检索到的活跃同类方案。Joern 只占一个候选档案；其官方文档、当前 C/C++ frontend 和 Agent 集成案例与其他路线使用同一字段评估。案例研究必须标明样本限制，不能改写为横向准确率结论。

- [ ] **Step 5: 调研独立静态分析、dataflow 和切片能力**

调查能补足或替代图式表示的开源分析引擎与论文方案；区分“能检测某类缺陷”“能导出稳定代码事实”“能被 Agent 高层查询”三种不同能力。

- [ ] **Step 6: 统一映射 WiFi MAC 已证与未证能力**

对所有路线把 Target preprocessing、direct call、function pointer、CFG、dataflow、slice、源码证据和增量更新分别标记。没有公开宏密集多 Target C 数据时，将其列入 `unknown` 和 Benchmark backlog。

- [ ] **Step 7: 核验路线平衡与旧引用持续相关性**

Run:

```powershell
rg -n '编译器|语义索引|代码数据库|CPG|静态分析|dataflow|程序切片' docs/research/solution-inventory.md
rg -n '经典|持续相关|当前版本|发布日期|unknown' docs/research/source-ledger.md docs/research/solution-inventory.md
```

Expected: 至少三个非 Joern 技术路线有独立档案；每个旧来源都有用途限定或近期状态补充。

- [ ] **Step 8: 提交程序分析调研**

```powershell
git add -- docs/research/source-ledger.md docs/research/solution-inventory.md
git diff --cached --check
git commit -m "docs: survey semantic code analysis approaches"
```

### Task 5: 调研代码与领域知识的混合方案及链接机制

**Files:**
- Modify: `docs/research/source-ledger.md`
- Modify: `docs/research/solution-inventory.md`
- Create: `docs/research/code-domain-linkage.md`

**Interfaces:**
- Consumes: 统一方案档案、研究问题 RQ4-RQ6。
- Produces: Knowledge Graph、Wiki、Memory、Skill 和按需上下文方案档案，以及独立的代码—领域知识链接模式比较。

- [ ] **Step 1: 登记代码与文档混合图项目**

至少覆盖 Graphify、Understand Anything 及检索到的活跃同类项目；区分确定性 Parser 边、LLM 语义边、人工边和 provenance 设计。

- [ ] **Step 2: 登记 Wiki/Memory/RAG 的近期论文证据**

至少覆盖 LLM-Wiki、WiCER 和近期代码库/Agent memory 研究。记录 Wiki 编译收益、信息丢失、检索失败、attention dilution 和迭代修正数据的原始实验语境。

- [ ] **Step 3: 登记 AI 公司领域知识实践**

至少覆盖 Google progressive disclosure、GitHub repository memory、AWS Skills/References/MCP 分层。明确这些资料证明的是工业设计选择，而非 WiFi MAC 准确率。

- [ ] **Step 4: 登记领域知识注入效果论文**

至少覆盖 SWE-Bench 5G 和 SWE-Skills-Bench；按任务类型记录收益条件、负收益和 Token 开销，避免得出“知识越多越好”。

- [ ] **Step 5: 提取对 WiFi MAC 可借鉴的知识生命周期设计**

分别讨论代码事实、推断标签、人工知识、原始资料、过期、重新验证和 provenance；不在此步提前确定最终存储技术。

- [ ] **Step 6: 建立代码—领域知识链接分类法**

在 `docs/research/code-domain-linkage.md` 中逐项比较：稳定代码实体 ID、Target occurrence、显式 typed edge、文档中的 symbol/file-line 引用、命名/目录/宏规则、embedding 相似度、LLM 推断和人工映射。每类记录粒度、双向导航、provenance、confidence、冲突处理和可失效性。

- [ ] **Step 7: 对每个混合方案回答同一组链接问题**

必须回答：从 Function 如何找到 Feature/Flow/Event/Rule/Document；从领域概念如何回到当前 revision 和 Target 的源码；链接由 Parser、规则、LLM 还是人工产生；源码移动、重命名和重新索引后如何修复；多个来源冲突时谁有优先级。

- [ ] **Step 8: 核验没有把软链接冒充代码事实**

Run:

```powershell
rg -n '实体 ID|Target occurrence|typed edge|file-line|embedding|LLM 推断|人工映射|失效|重新验证' docs/research/code-domain-linkage.md
rg -n 'verified|inferred|manual|provenance|confidence' docs/research/code-domain-linkage.md
```

Expected: 每种链接方式均标明事实强度和生命周期；LLM/embedding 只作为软链接或候选发现，除非另有验证证据。

- [ ] **Step 9: 提交混合知识与链接机制调研**

```powershell
git add -- docs/research/source-ledger.md docs/research/solution-inventory.md docs/research/code-domain-linkage.md
git diff --cached --check
git commit -m "docs: survey code domain knowledge linkage patterns"
```

### Task 6: 构建横向证据矩阵并收敛候选

**Files:**
- Create: `docs/research/evidence-matrix.md`
- Modify: `docs/research/solution-inventory.md`

**Interfaces:**
- Consumes: 所有 `claim-verified` 来源、方案档案、代码—领域知识链接模式和 `W01` 至 `W08`。
- Produces: 排除、架构参考、组件候选、短名单四类结论。

- [ ] **Step 1: 创建矩阵列和证据编码**

列固定为：Target/宏、直接调用、间接调用、CFG、dataflow、Host/Device Event、源码证据、代码—领域链接类型、链接 provenance、双向导航、Target/revision 绑定、链接失效/修复、歧义/abstention、索引、增量、查询、Agent 效果、领域知识、离线、许可证、维护、复现。

单元格只允许：`verified`、`claimed`、`unsupported`、`unknown`，并附来源编号。

- [ ] **Step 2: 定义完整方案硬门槛和组件例外**

完整方案短名单必须能够设计性地容纳 Target-specific 编译视角、源码证据和不确定性。未满足者可成为组件候选或架构参考，不能因单项速度数据进入完整方案短名单。

- [ ] **Step 3: 为每个方案填写矩阵并给出分类理由**

每个分类理由至少引用一个来源编号；`unknown` 较多的方案标记为待验证，不写“已优于”。

- [ ] **Step 4: 执行开源优先的平局处理**

只有现有可比证据未显示决定性差异时，才比较离线、自托管、许可证、开放接口、维护和二次开发；记录这是后续 Benchmark 优先级，不是最终性能判决。

- [ ] **Step 5: 检查矩阵没有无来源结论或伪量化**

Run:

```powershell
rg -n '\| (verified|claimed|unsupported|unknown)' docs/research/evidence-matrix.md
rg -n -i '总分|综合得分|统计等效|一定优于|必然' docs/research/evidence-matrix.md
```

Expected: 每个证据状态带 `Sxxx`；没有在异构数据上生成总分或统计等效结论。

- [ ] **Step 6: 提交证据矩阵与候选分类**

```powershell
git add -- docs/research/evidence-matrix.md docs/research/solution-inventory.md
git diff --cached --check
git commit -m "docs: classify architecture candidates by evidence"
```

### Task 7: 形成后续 Benchmark 研究清单

**Files:**
- Create: `docs/research/benchmark-backlog.md`

**Interfaces:**
- Consumes: 证据矩阵中的 `unknown`、冲突数据和短名单。
- Produces: 下一阶段实验开发可直接转化为 Benchmark 设计的问题清单。

- [ ] **Step 1: 将每个关键 `unknown` 转换为可检验问题**

每项包含：研究问题、候选方案、假设、输入代码结构、ground truth、指标、反事实、资源成本和决定哪项选型。

- [ ] **Step 2: 设计 WiFiDemo 内部有效性 Benchmark 主题**

记录 Target occurrence、宏条件、direct/indirect call、ops、Event、公共代码、日志定位和领域标签八类主题，但不实现测试工具。

- [ ] **Step 3: 记录外部有效性候选数据集筛选门槛**

优先记录 Zephyr、RIOT、Contiki-NG 等嵌入式候选；同时允许其他开源 C 项目，只要覆盖复杂构建变体、条件编译、函数指针/回调、插件或协议分发、跨组件事件、公共代码复用或代码—领域文档映射中的至少一种。每项记录固定版本、许可证、结构对应关系和可构造 ground truth 的程度。

- [ ] **Step 4: 规定未来实验的公平性控制**

固定代码 commit、模型、Agent scaffold、Token/tool budget、预处理参数和硬件；区分工具事实准确率、检索效率和 Agent 最终任务正确率。

- [ ] **Step 5: 提交 Benchmark backlog**

```powershell
git add -- docs/research/benchmark-backlog.md
git diff --cached --check
git commit -m "docs: define follow-up architecture benchmark backlog"
```

### Task 8: 综合撰写最终调研论文

**Files:**
- Modify: `research.md`

**Interfaces:**
- Consumes: 所有研究辅助文档和 `claim-verified` 来源。
- Produces: 自包含、可审阅的成熟方案调研与候选收敛论文。

- [ ] **Step 1: 写研究方法和来源选择**

明确检索截止日期、来源范围、时间相关性规则、证据等级、排除标准和“当前不实验”的边界。

- [ ] **Step 2: 用 WiFiDemo 案例写工作负载模型**

从 `W01` 至 `W08` 选择最小必要代码片段，解释为什么宏、Target、ops 和跨 Host/Device Event 会改变知识架构要求。

- [ ] **Step 3: 按问题而非项目名单组织成熟方案章节**

先解释代码导航、语义代码分析、代码—领域知识链接、领域知识管理、Agent context 五类问题，再在每类中比较代表性项目，避免连续堆叠 README 功能或以 Joern 为中心组织章节。

- [ ] **Step 4: 写优缺点、排除项和可借鉴设计**

每个核心判断贴近引用；第一方数据用“项目报告”，公司设计用“官方实践”，独立实验明确写“独立”。

- [ ] **Step 5: 写候选短名单和开源优先路线**

不宣布唯一赢家。说明每个候选为何留下、哪些能力仍为 `unknown`、哪种开源组件组合值得优先进入 Benchmark。

- [ ] **Step 6: 写证据缺口、有效性威胁和后续工作**

明确公开 Benchmark 与 WiFi MAC 结构的差异、模型和指标不可比性、项目自测偏差、快速版本演进，以及后续实验如何裁决。

- [ ] **Step 7: 最后写摘要和结论**

摘要只报告调研发现、排除原则、候选范围和后续验证需求，不写当前证据无法支持的最终技术栈。

- [ ] **Step 8: 提交论文主体**

```powershell
git add -- research.md
git diff --cached --check
git commit -m "docs: rewrite WiFi MAC architecture research"
```

### Task 9: 执行证据、引用和范围终审

**Files:**
- Modify: `docs/research/source-ledger.md`
- Modify: `docs/research/solution-inventory.md`
- Modify: `docs/research/code-domain-linkage.md`
- Modify: `docs/research/evidence-matrix.md`
- Modify: `docs/research/benchmark-backlog.md`
- Modify: `research.md`

**Interfaces:**
- Consumes: 完整研究产物。
- Produces: 无悬空数字、无越界结论、可交付审阅的最终版本。

- [ ] **Step 1: 审计正文中的每一个数字**

Run:

```powershell
rg -n '[0-9]+([.,][0-9]+)?%|[0-9]+([.,][0-9]+)?[×xX]|[0-9]+ 个|[0-9]+ 倍' research.md
```

Expected: 每个数字所在段落有原始来源链接，并能映射到 `source-ledger.md` 的 `claim-verified` 记录。

- [ ] **Step 2: 审计来源类型和引用 URL**

逐个打开正文 URL，确认是论文原文、AI 公司官方文章或开源项目官方资料；搜索结果页、聚合转载和无法定位原始数字的页面从正文移除。

- [ ] **Step 3: 审计第一方、独立和案例措辞**

Run:

```powershell
rg -n 'benchmark|Benchmark|案例|独立|第一方|项目报告|官方实践' research.md
```

Expected: 所有项目 Benchmark 均标明第一方或独立属性；案例不被描述为统计证明。

- [ ] **Step 4: 审计代码—领域知识链接结论**

Run:

```powershell
rg -n '链接|实体|revision|Target|provenance|confidence|失效|重新验证' research.md docs/research/code-domain-linkage.md
```

Expected: 每个进入短名单的混合方案都说明链接创建者、绑定粒度、证据、方向和生命周期；软链接不被描述为已验证代码事实。

- [ ] **Step 5: 审计范围和最终选型措辞**

Run:

```powershell
rg -n -i '最终选型|唯一方案|一定优于|已经证明.*WiFi|直接替代|必须采用' research.md
```

Expected: 若有匹配，只能出现在否定、限制或未来工作语境中。

- [ ] **Step 6: 审计辅助文档一致性和占位符**

Run:

```powershell
rg -n '\[未完成\]|\[占位\]|<补充内容>' research.md docs/research
git diff --check
```

Expected: 无占位符、无空白结论、无 Markdown 空白错误。

- [ ] **Step 7: 核对工作区只包含计划内修改**

Run:

```powershell
git status --short
git diff --name-status HEAD~1..HEAD
```

Expected: `目标代码仓注意事项.md` 仍保持用户原状态；研究提交只包含 `research.md` 和 `docs/research/**`。

- [ ] **Step 8: 提交终审修订**

```powershell
git add -- research.md docs/research/source-ledger.md docs/research/solution-inventory.md docs/research/code-domain-linkage.md docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
git diff --cached --check
git commit -m "docs: audit architecture research evidence and scope"
```

- [ ] **Step 9: 输出最终核验摘要**

报告：来源总数、`claim-verified` 数量、论文/公司/项目来源分布、包含数字的声明数量、排除项数量、架构参考数量、组件候选数量、短名单数量和 Benchmark backlog 条目数量。任何未核验来源不得计入核心结论。
