# Research Synthesis and Candidate Reassessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 WiFi MAC 代码知识架构调研重构为“调研发现—共同骨架—项目分类—候选推导—待实验裁决”的完整论文，并用两种核心架构族及两种查询模式替代旧 L1/L2/L3。

**Architecture:** 保留现有四条调研主线和 WiFiDemo 工作负载，将程序事实、领域知识和 Agent 交付映射到工具无关的八层骨架；具体项目按职责和 Agent 证据等级归类。候选只由程序事实主干与查询拓扑等同级决策轴生成，形成 A0、A1、B0、B1 四个待 Benchmark 变体，不宣布未经实验验证的赢家。

**Tech Stack:** Markdown、Git、`rg`、项目现有证据台账与审计文档、论文/AI 公司官方资料/开源项目官方资料。

## Global Constraints

- 当前阶段不运行 WiFiDemo 或外部 C 项目的候选工具实验，不新增本地性能结果。
- 只使用论文原文、AI 公司官方文章、开源项目官方仓库/文档/Benchmark 支撑核心结论。
- 近期材料优先，但仍具时效性的经典程序分析论文和官方资料不因日期被排除。
- 第一方 Benchmark、同行评审结果、真实案例和架构推断必须明确分开。
- 代码事实必须绑定 repository、revision、Target/build profile 和 source span。
- Agent 项目优先，但 MCP 只证明可连接性，不证明 Agent 效果。
- 代码与领域知识通过独立的 assertion/link layer 连接；LLM 或 embedding 只能产生候选。
- 旧 L1/L2/L3 不再作为最终候选分类；轻量发现是 A/B 均可采用的查询模式。
- 当前结论只缩小实验范围，不确定唯一赢家；效果接近时才以开源、离线和可维护性作为 tie-break。
- 保留 `目标代码仓注意事项.md` 原文，不将当前研究结论改写成历史注意事项。
- 不修改 WiFiDemo、WiFiGraph 或 FactumCore `main` 工作树；所有修改留在 `research/wifi-mac-architecture` 工作树。

---

## File Map

- Modify: `docs/research/source-ledger.md` — 登记新增 Agent 原生导航、CPG-Agent 和 CodeQL-Agent 一手来源及可引用边界。
- Modify: `docs/research/solution-inventory.md` — 增加八层骨架映射、Agent 证据等级和项目统一卡片，删除旧候选推导。
- Modify: `docs/research/code-domain-linkage.md` — 统一四级断言权限、来源注册、双向链接和失效模型。
- Modify: `docs/research/evidence-matrix.md` — 用 A/B 主骨架与 0/1 查询模式替代 L1/L2/L3，形成统一比较矩阵。
- Modify: `docs/research/benchmark-backlog.md` — 将 B01–B15 的候选引用和待裁决决策迁移到 A0/A1/B0/B1。
- Modify: `research.md` — 按批准的十五节论证顺序重构论文正文。
- Modify: `docs/research/audit-report.md` — 更新来源规模、候选规模、审计结果和仍开放问题。
- Preserve unchanged: `目标代码仓注意事项.md` — 历史输入，只作引用和范围核验。

### Task 1: 登记 Agent 结合的一手证据

**Files:**
- Modify: `docs/research/source-ledger.md:67-end`

**Interfaces:**
- Consumes: 现有 S001–S036 编号、来源记录格式和 `claim-verified` 规则。
- Produces: S037–S040 四条可供后续文档引用的 Agent 结合证据记录。

- [ ] **Step 1: 重新打开四组原始来源并核对当前内容**

逐个读取并记录访问日期 `2026-08-14`：

```text
S037 Serena
https://github.com/oraios/serena
https://oraios.github.io/serena/04-evaluation/000_evaluation-intro.html

S038 Sourcegraph MCP / SCIP
https://sourcegraph.com/mcp
https://github.com/sourcegraph/scip

S039 codebadger / Bridging Code Property Graphs and Language Models
https://arxiv.org/abs/2603.24837
https://github.com/lekssays/codebadger

S040 QLCoder
https://arxiv.org/abs/2511.08462
https://github.com/neuralprogram/qlcoder
```

Expected: 每个事实都从上述原始页面取得；搜索结果摘要不进入台账。

- [ ] **Step 2: 按现有格式追加 S037–S040**

每条记录必须填写：来源类型、时间、访问状态、项目/论文版本、样本与语言、指标、可引用声明、限制、适用骨架层和 Agent 证据等级。

必须保留以下边界：

- Serena 支持 MCP、C/C++ LSP 与符号级导航；其评估是项目第一方的 Agent 自评和可重跑方法，不是独立固定 Benchmark。
- Sourcegraph MCP 提供搜索、定义和引用等 Agent 操作，SCIP 是开放代码智能表示；Sourcegraph 产品开放性与 SCIP 开放性分别描述。
- codebadger 将 Joern CPG 封装为切片、污点、数据依赖和导航等高层 MCP 工具；GGML、libtiff、libxml2 是三个真实案例，不写成大规模受控优越性证明。
- QLCoder 在 176 个 CVE、111 个 Java 项目上报告 53.4% 正确查询，对照 Claude Code 为 10%；该数字证明 Agent+LSP/CodeQL 查询合成价值，不外推为 WiFi C 项目代码理解准确率。

- [ ] **Step 3: 更新台账登记状态**

将来源总数从 36 更新为 40，并按实际记录重新统计 `claim-verified`、论文、AI 公司官方材料和开源项目材料数量。若一条记录同时含论文与仓库，以台账当前计数规则归类，不重复伪造样本数。

- [ ] **Step 4: 验证编号、URL 与数字声明**

Run:

```powershell
rg -n '^### S03[7-9]|^### S040|53\.4%|176|111|GGML|libtiff|libxml2|Serena|Sourcegraph' docs/research/source-ledger.md
rg -n '搜索结果|reddit|Wikipedia' docs/research/source-ledger.md
git diff --check
```

Expected: S037–S040 各出现一次；关键数字和案例均位于对应来源记录；第二条命令不在 S037–S040 的证据正文中发现二手来源；空白检查通过。

- [ ] **Step 5: 提交来源台账**

```powershell
git add -- docs/research/source-ledger.md
git diff --cached --check
git commit -m "docs: add agent integration evidence"
```

### Task 2: 用八层骨架重新组织项目档案

**Files:**
- Modify: `docs/research/solution-inventory.md:18-end`

**Interfaces:**
- Consumes: S001–S040、八层骨架和 A-D Agent 证据规则。
- Produces: 项目到骨架层的映射、统一项目卡片、共同规律与差异，以及不依赖旧 L1/L2/L3 的组件分类。

- [ ] **Step 1: 在项目档案前增加八层骨架总表**

表格固定使用以下八行：

```text
1 输入与快照
2 身份与基础索引
3 语义分析提供者
4 领域原始来源
5 版本化来源注册
6 断言与链接层
7 查询编排与证据装配
8 Agent 交付
```

每行说明输入、产出、事实权限、代表项目和当前空缺；横切项另列 snapshot consistency、provenance、invalidation、evaluation、license 和 observability。

- [ ] **Step 2: 增加 Agent 证据双轴规则**

在目录前部增加 A-D Agent 使用等级，同时保留来源性质这一独立轴：

```text
Agent evidence: A 受控实验；B 正式工作流/真实案例；C 社区包装；D 仅理论可接入
Evidence provenance: independent / peer-reviewed / company-first-party / project-first-party
```

明确 `A + project-first-party` 不等于独立证据，`B + peer-reviewed case study` 也不等于受控对照。

- [ ] **Step 3: 增加导航层项目卡片**

在 R 系列档案中追加：

- `R08 — Serena`：LSP/clangd 语义导航、MCP 高层工具、C/C++ 支持、第一方 Agent 评估、编辑能力不属于本研究核心；
- `R09 — Sourcegraph MCP/SCIP`：跨仓检索/定义/引用、SCIP 身份与索引价值、产品与开放组件边界。

每张卡片必须包含骨架层、Agent 等级、来源等级、输入/输出、可引用数据、对 WiFi MAC 的适用性、限制和候选角色。

- [ ] **Step 4: 增加深分析 Agent 接口卡片**

在 A 系列档案中追加：

- `A11 — codebadger/Joern Agent Interface`：作为 Joern 上层 Agent 编排接口，不重复把它描述为新的 CPG 引擎；
- `A12 — QLCoder/CodeQL Agent Loop`：作为“受约束 DSL 生成 + LSP 反馈”的参考，不升级 CodeQL 的开放核心地位。

明确 codebadger 的启示是预实现高层分析操作优于默认暴露原始 CPGQL；QLCoder 的启示是小而明确的工具箱、语法反馈和延迟完整执行。

- [ ] **Step 5: 写成熟方案的共同点与差异**

共同点至少包含：确定性结构或语义工具、渐进检索、source-grounded 结果、有边界高层 Agent 操作、派生上下文与事实源分离。

差异只按以下决策轴组织：程序事实主干、查询拓扑、分析时机、断言层物理组织。数据库品牌、可视化和 MCP 是否存在不得单独构成架构族。

- [ ] **Step 6: 删除旧 Task 6 三候选结论并重写项目角色**

把原 `## 15. Task 6 的候选分层` 改为“项目角色与候选生成输入”，只输出：

- 排除为完整方案；
- 架构参考；
- 组件候选；
- 可进入两个主骨架的程序事实或 Agent 接口组件。

此处不再出现 L1、L2、L3 或第三个“轻量发现架构族”。

- [ ] **Step 7: 验证档案结构与旧分类清理**

Run:

```powershell
rg -n '^## |^### R0[89]|^### A1[12]|Agent evidence|Evidence provenance|输入与快照|查询编排' docs/research/solution-inventory.md
rg -n 'L1|L2|L3|三个可替换组件的架构族' docs/research/solution-inventory.md
git diff --check
```

Expected: 新卡片和八层骨架均存在；第二条命令无旧候选结论匹配；格式检查通过。

- [ ] **Step 8: 提交项目档案重构**

```powershell
git add -- docs/research/solution-inventory.md
git diff --cached --check
git commit -m "docs: classify solutions by architecture skeleton"
```

### Task 3: 固化代码与领域知识的共同链接层

**Files:**
- Modify: `docs/research/code-domain-linkage.md:17-end`

**Interfaces:**
- Consumes: 现有实体、Assertion 字段、Graphify/Understand Anything 调研和已批准的共同链接模型。
- Produces: A0/A1/B0/B1 共用的四级断言权限、来源注册和失效协议。

- [ ] **Step 1: 区分领域原始来源与版本化来源注册**

在实体集合和规范链接链中明确：Document/Specification/Issue/Test/Log 是原始来源，SourceRevision/SourceLocation/License/AccessedAt 属于来源注册信息；Wiki、Skill、Memory 只能引用这些对象。

- [ ] **Step 2: 将链接分类统一为四个机器可读状态**

全文统一使用：

```text
EXTRACTED
RULE_DERIVED
INFERRED_CANDIDATE
CURATED
```

定义每个状态的允许生产者、最小证据、可见范围、是否能支持确定性回答、升级条件和失效行为。Graphify 的 `INFERRED`/`AMBIGUOUS` 只作为来源项目自己的术语，不覆盖本研究的四级权限。

- [ ] **Step 3: 补齐 Assertion 最小字段**

字段至少包括：subject/object stable ID、repository、revision、Target/build profile scope、predicate、source citation、source span、producer、method/version、confidence、review state、created/validated time、lifecycle state、invalidation reason。

- [ ] **Step 4: 增加 Agent 写入权限和双向查询示例**

写明 Agent 只能创建 `INFERRED_CANDIDATE`，不能自行升级为确定性事实。至少给出两条任务级查询：

```text
从 TargetOccurrence 找到相关 Feature/Flow/ProtocolRule 及原始引用
从 Feature/Event 找到当前 revision 与 Target 下仍有效的代码 occurrence 和证据路径
```

- [ ] **Step 5: 验证状态、字段与生命周期**

Run:

```powershell
rg -n 'EXTRACTED|RULE_DERIVED|INFERRED_CANDIDATE|CURATED|SourceRevision|source span|invalidation reason|双向' docs/research/code-domain-linkage.md
rg -n 'LLM.*确定性事实|embedding.*确定性事实' docs/research/code-domain-linkage.md
git diff --check
```

Expected: 四个状态均有定义；来源注册、最小字段、Agent 权限和双向链接均能定位；模型不得直接写事实的语句明确存在。

- [ ] **Step 6: 提交共同链接模型**

```powershell
git add -- docs/research/code-domain-linkage.md
git diff --cached --check
git commit -m "docs: unify code domain assertion lifecycle"
```

### Task 4: 重建候选矩阵和 Benchmark 决策映射

**Files:**
- Modify: `docs/research/evidence-matrix.md:5-end`
- Modify: `docs/research/benchmark-backlog.md:26-end`

**Interfaces:**
- Consumes: 八层骨架、项目角色、共同断言层和现有 B01–B15 Ground truth。
- Produces: 两种主骨架、四个部署变体和能够裁决其差异的实验清单。

- [ ] **Step 1: 在证据矩阵中增加八层覆盖规则**

保留现有固定维度，但为每个方案增加：主责骨架层、Agent evidence、source/revision/Target 绑定、事实权限、是否需要核验、当前结论状态。

状态只允许：

```text
supported by evidence
architecturally accommodated
unknown / benchmark required
not satisfied
```

- [ ] **Step 2: 用两个核心架构族替换完整架构短名单**

完整架构短名单固定为：

```text
A Agent 原生的联邦语义服务骨架
B Target-specific CPG 主骨架
```

分别列出八层组件映射、Agent 高层接口、优势、风险、适用任务、不可直接声称的能力和可证伪条件。

- [ ] **Step 3: 增加 0/1 查询模式矩阵**

形成四个部署变体：

```text
A0 联邦骨架 + 直接查询
A1 联邦骨架 + 轻量发现后核验
B0 CPG 骨架 + 直接查询
B1 CPG 骨架 + 轻量发现后核验
```

明确 1 模式不是第三个程序事实主干；它只有在减少 Token/调用/延迟的净收益大于错误候选、核验和一致性成本时才成立。

- [ ] **Step 4: 更新 B01–B15 候选列与决策列**

逐行执行以下迁移：

- B01–B06、B11：比较 A 与 B 的事实主干和 Target correctness；
- B07、B10、B14：比较 0 与 1 查询模式，并保留 lexical/no-graph 基线；
- B08、B09、B13：验证共同 assertion layer，不将其误写为 A/B 差异；
- B12：比较 CPG provider 与 LLVM/deep provider 的实际效果；
- B15：审计 A0/A1/B0/B1 的具体组件组合与替代路径。

把旧“L3 可能降低导航成本”改写为“模式 1 是否产生净收益”。

- [ ] **Step 5: 增加 Agent 接口实验记录点**

在 B10 或其说明中固定记录：高层工具选择正确率、无效工具调用、原始 DSL 退回次数、结果截断、abstention、Token、工具调用和最终任务正确率。此处只记录未来实验设计，不产生当前数据。

- [ ] **Step 6: 验证旧候选消失且 Benchmark 数量保持**

Run:

```powershell
rg -n 'A0|A1|B0|B1|联邦语义服务|Target-specific CPG|supported by evidence|architecturally accommodated' docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -n 'L1|L2|L3|三架构族|三个架构族' docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -c '^\| B[0-9][0-9] ' docs/research/benchmark-backlog.md
git diff --check
```

Expected: 第一条覆盖四个变体和状态词；第二条无匹配；B01–B15 仍各出现一次；格式检查通过。

- [ ] **Step 7: 提交矩阵与 Benchmark 迁移**

```powershell
git add -- docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
git diff --cached --check
git commit -m "docs: redefine architecture benchmark candidates"
```

### Task 5: 按完整推导链重写论文正文

**Files:**
- Modify: `research.md:1-end`

**Interfaces:**
- Consumes: S001–S040、W01–W08、重构后的方案档案、共同链接层、候选矩阵和 B01–B15。
- Produces: 可独立阅读、从调研综合自然推导到 A0/A1/B0/B1 的论文正文。

- [ ] **Step 1: 更新标题、摘要和研究贡献占位结构**

标题不再以“候选收敛”作为未经解释的终点。摘要先留在正文编辑中，但只写已被后文章节支撑的内容：四条调研线、八层骨架、两个主骨架、两种模式、共同断言层和待 Benchmark 结论。

- [ ] **Step 2: 保留并校准方法与 WiFiDemo 工作负载**

保留时间窗口、证据等级、数字解释和 W01–W08。增加 Agent evidence A-D 与来源性质双轴说明，明确 C/C++ 项目结构相邻即可进入未来外部案例集。

- [ ] **Step 3: 更新四条独立调研主线**

在代码导航中加入 Serena、Sourcegraph MCP/SCIP；在深分析中加入 codebadger 和 QLCoder；在领域知识中继续使用 Graphify、Understand Anything、Wiki/Skill/Memory。每项数字紧邻 S 编号和直接 URL，并写明样本与限制。

- [ ] **Step 4: 新增“共同规律”章节**

至少综合五点：

1. 确定性结构或语义工具作为代码入口；
2. 低成本发现与高成本核验分工；
3. source-grounded 与 progressive disclosure；
4. 高层任务工具优于默认暴露复杂 DSL；
5. 派生 Wiki/Skill/Memory 不替代当前代码和原始领域来源。

- [ ] **Step 5: 新增“关键差异”章节**

只讨论程序事实主干、查询拓扑、分析时机和断言层物理组织。解释为什么数据库、MCP、向量和可视化不是同级架构分类。

- [ ] **Step 6: 新增八层参考骨架及端到端数据流**

按输入与快照、身份与基础索引、语义分析、领域原始来源、版本化来源注册、断言与链接、查询编排、Agent 交付依次说明。明确两条事实流只在断言层连接，物理存储可以同库或分库。

- [ ] **Step 7: 新增按骨架的项目地图与 Agent 证据表**

表格至少列项目、主责层、Agent 方式、Agent evidence、来源性质、可借鉴点、WiFi MAC 直接证据和当前角色。重点展示 Serena、Sourcegraph、Codebase-Memory、CodeGraph、Joern/codebadger、QLCoder/CodeQL、Graphify、Understand Anything。

- [ ] **Step 8: 重写代码与领域知识链接章节**

正文使用 `EXTRACTED`、`RULE_DERIVED`、`INFERRED_CANDIDATE`、`CURATED` 四类，并说明双向导航、版本范围、冲突、失效和重验证。Host/Device 继续通过 Event/Message 连接。

- [ ] **Step 9: 从决策轴推导 A/B 与 0/1**

先说明旧 L3 为什么是查询模式，再分别给出 A、B 的数据流、八层映射、优缺点、Agent 接口和关键 unknown；最后形成 A0、A1、B0、B1 四变体。

- [ ] **Step 10: 建立统一 WiFiDemo 覆盖矩阵**

矩阵按 W01–W08 比较四变体，并且单元格只使用：`supported by evidence`、`architecturally accommodated`、`unknown / benchmark required`、`not satisfied`。当前没有 WiFiDemo 工具实验，因此不得把任何候选对 W01–W08 的适配写成实测通过。

- [ ] **Step 11: 重写排除项、开源规则和后续 Benchmark**

保留纯检索、单独 Tree-sitter、GitNexus 许可边界、CodeQL 开放核心和无来源 LLM 事实等排除理由；Graphify/Understand Anything 归为领域设计参考；B01–B15 作为未来裁决依据。开源只在硬门槛和效果无决定性差异时 tie-break。

- [ ] **Step 12: 最后写摘要、有效性威胁和结论**

结论只能声称：范围缩小为两个主骨架与两种模式，尚未确定唯一赢家。有效性威胁至少包含无本地候选实验、第一方数据偏差、Agent/项目快速演进、C/C++ Target 外推和许可证变化。

- [ ] **Step 13: 验证正文论证顺序和禁用旧术语**

Run:

```powershell
rg -n '^## |^### ' research.md
rg -n '共同规律|关键差异|八层|Agent evidence|联邦语义服务|Target-specific CPG|A0|A1|B0|B1|INFERRED_CANDIDATE' research.md
rg -n 'L1|L2|L3|进入 Benchmark 的三个架构族' research.md
git diff --check
```

Expected: 候选章节出现在共同规律、差异和八层骨架之后；第二条覆盖所有新概念；第三条无旧候选匹配；格式检查通过。

- [ ] **Step 14: 提交论文主体**

```powershell
git add -- research.md
git diff --cached --check
git commit -m "docs: restructure architecture candidate analysis"
```

### Task 6: 更新审计报告并执行证据终审

**Files:**
- Modify: `docs/research/audit-report.md:1-end`
- Inspect: `research.md`
- Inspect: `docs/research/source-ledger.md`
- Inspect: `docs/research/solution-inventory.md`
- Inspect: `docs/research/code-domain-linkage.md`
- Inspect: `docs/research/evidence-matrix.md`
- Inspect: `docs/research/benchmark-backlog.md`

**Interfaces:**
- Consumes: 全部重构产物和提交历史。
- Produces: 数字、来源、Agent 证据、候选分类和范围均可复核的审计报告。

- [ ] **Step 1: 重新统计来源与候选规模**

Run:

```powershell
rg -c '^### S[0-9]{3} ' docs/research/source-ledger.md
rg -c '核验状态：`claim-verified`' docs/research/source-ledger.md
rg -c '^\| B[0-9][0-9] ' docs/research/benchmark-backlog.md
```

Expected: 来源记录为 40；claim-verified 数量以命令实际输出为准；Benchmark 为 B01–B15 共 15 项。

- [ ] **Step 2: 审计正文中的全部数字**

Run:

```powershell
rg -n '[0-9]+([.,][0-9]+)?%|[0-9]+([.,][0-9]+)?[×xX]|[0-9]+ 个|[0-9]+ 倍' research.md
```

Expected: 每个效果数字都带 S 编号或直接原始 URL，并在台账中记录样本、基线和限制；架构编号、W/B 编号和年份不误计为效果数据。

- [ ] **Step 3: 审计 Agent 证据措辞**

Run:

```powershell
rg -n 'Agent evidence|第一方|同行评审|受控|自评|案例|MCP' research.md docs/research/solution-inventory.md
```

Expected: MCP 不被描述为效果证明；Serena 自评、codebadger 案例、Codebase-Memory/CodeGraph Benchmark 和 QLCoder 受控结果的证据性质分别明确。

- [ ] **Step 4: 审计代码—领域链接与 Target 边界**

Run:

```powershell
rg -n 'repository|revision|Target|source span|provenance|confidence|stale|invalid|重新验证|EXTRACTED|RULE_DERIVED|INFERRED_CANDIDATE|CURATED' research.md docs/research/code-domain-linkage.md
rg -n 'Host/Device|Event/Message|跨二进制.*CALLS' research.md docs/research/code-domain-linkage.md
```

Expected: 主体身份、四级权限、生命周期和 Host/Device 表达均存在；不存在把跨二进制消息路径称为确定性 `CALLS` 的肯定结论。

- [ ] **Step 5: 审计候选与范围措辞**

Run:

```powershell
rg -n -i '最终选型|唯一方案|一定优于|已经证明.*WiFi|必须采用|直接替代' research.md docs/research/evidence-matrix.md
rg -n 'L1|L2|L3|三个架构族|三套方案' research.md docs/research
```

Expected: 第一条只在否定、限制或未来工作语境出现；第二条不得在当前候选结论中出现。若旧设计说明含历史文字，不修改历史 spec，但审计报告说明它已被 2026-08-14 spec 取代。

- [ ] **Step 6: 审计来源 URL 和本地交叉引用**

逐个打开正文新增 URL，确认它们仍指向 S037–S040 的原始来源。检查 Markdown 本地链接指向存在文件：

```powershell
rg -n '\]\(docs/research/[^)]+\.md\)' research.md
Get-ChildItem docs/research -File | Select-Object Name
```

Expected: 无搜索结果页、聚合转载或悬空本地路径。

- [ ] **Step 7: 更新审计报告**

`audit-report.md` 必须记录：来源总数、claim-verified 数量、来源类型分布、效果数字声明数量、两个核心架构族、四个部署变体、排除/参考/组件数量、15 项 Benchmark，以及仍未解决的 Target frontend、函数指针、ID、invalidation、Agent 效果和许可证问题。

- [ ] **Step 8: 执行全树格式与占位符检查**

Run:

```powershell
rg -n '\[未完成\]|\[占位\]|<补充内容>|[T]BD|T[O]DO|implement[ ]later' research.md docs/research
git diff --check
git status --short
```

Expected: 无占位符和空白错误；状态只包含 `audit-report.md` 的计划内修改。

- [ ] **Step 9: 提交审计结果**

```powershell
git add -- docs/research/audit-report.md
git diff --cached --check
git commit -m "docs: audit reassessed architecture research"
```

### Task 7: 最终验证并推送研究分支

**Files:**
- Inspect: `research.md`
- Inspect: `docs/research/*.md`
- Inspect: `docs/superpowers/specs/2026-08-14-research-synthesis-and-candidate-reassessment-design.md`
- Inspect: `docs/superpowers/plans/2026-08-14-research-synthesis-and-candidate-reassessment.md`
- Preserve unchanged: `目标代码仓注意事项.md`

**Interfaces:**
- Consumes: Task 1–6 的已提交产物。
- Produces: 工作树干净、提交历史可审计并已推送的 `research/wifi-mac-architecture` 分支。

- [ ] **Step 1: 执行最终范围检查**

Run:

```powershell
git status --short
git diff --check HEAD~6..HEAD
git diff --name-status 3015105..HEAD
git log --oneline --decorate -8
```

Expected: 工作树干净；从历史注意事项提交之后只修改 `research.md`、`docs/research/**`、新 spec 和新 plan；无 WiFiDemo、WiFiGraph 或 `main` 工作树文件。

- [ ] **Step 2: 执行最终结构检查**

Run:

```powershell
rg -n '^## ' research.md
rg -n 'A0|A1|B0|B1' research.md docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -n 'L1|L2|L3|进入 Benchmark 的三个架构族' research.md docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -c '^### S[0-9]{3} ' docs/research/source-ledger.md
rg -c '^\| B[0-9][0-9] ' docs/research/benchmark-backlog.md
```

Expected: 正文顺序符合设计；四变体在三份决策文档中一致；旧分类无匹配；来源 40 条；Benchmark 15 项。

- [ ] **Step 3: 执行最终证据抽查**

随机抽查至少以下四条正文声明并回到台账和原始来源：

```text
Codebase-Memory 的 31 仓、83%/92%、10×、2.1×
codebadger 的三个真实案例与非受控限制
QLCoder 的 176 CVE、111 Java 项目、53.4%/10%
Serena 的 MCP/C++ 能力与第一方 Agent 自评属性
```

Expected: 数字、样本、证据性质和外推限制四项同时存在。

- [ ] **Step 4: 推送当前研究分支**

```powershell
git push origin research/wifi-mac-architecture
```

Expected: 远端分支更新到最终本地 HEAD。不得在未获明确指示时合并 `main` 或改写远端历史。

- [ ] **Step 5: 输出交付摘要**

报告最终 commit、远端分支、修改文件、来源/Benchmark 数量、两个核心架构族、四个部署变体、验证命令结果和仍待未来实验裁决的问题。
