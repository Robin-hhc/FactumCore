# 架构候选证据矩阵

核验日期：2026-08-14

## 1. 读表规则

本矩阵只压缩 `source-ledger.md`、`solution-inventory.md` 和 `code-domain-linkage.md` 已登记的证据，不把“组件公开提供某项功能”外推为“该功能已在 WiFiDemo 上有效”。组件级事实与项目角色继续以 `solution-inventory.md` 为准；本文件比较由当前证据构造的 A/B 两个可归因、可证伪的主实验骨架，以及可附着其上的 0/1 查询模式。

A/B 不是候选空间穷尽声明。B01–B15 若发现新的独立决策轴、共享混杂或硬失败，可以要求下一轮拆分、增加或重定义实验臂；矩阵只描述当前预注册前的初始比较对象。

每个结论单元格只允许以下四种状态：

- `supported by evidence`：已有登记证据直接支持该范围内的陈述；仍须同时读取 Agent evidence 与 Evidence provenance，不能把第一方材料冒充独立实验。
- `architecturally accommodated`：架构已给出承载该能力的层、接口、事实权限和失效边界，但尚未证明 WiFiDemo 效果。
- `unknown / benchmark required`：现有材料不足以裁决，必须由后续 Benchmark 回答。
- `not satisfied`：当前设计没有满足该能力或硬门槛。

方括号内的 `Sxxx` 指向 `source-ledger.md`。架构状态、Agent evidence 和 Evidence provenance 是三条独立轴：

- **Agent evidence**：A 受控实验；B 正式工作流/真实案例；C 社区包装；D 仅理论可接入。
- **Evidence provenance**：independent / peer-reviewed / company-first-party / project-first-party。

两轴不得折叠。MCP 可调用、产品功能说明或开源协议只能证明接口或组件可用，不自动证明 Agent 效果。所有 WiFiDemo 候选工具实验在本轮仍未运行。

## 2. 固定维度矩阵

原矩阵的固定维度全部保留，但当前评估对象改为两个主实验骨架。这里的状态描述架构是否容纳该职责，不是产品得分或完备性证明；凡涉及实际准确率、资源、Agent 效果或采用性，均保守留给 Benchmark。

| 候选 | Target/宏 | 直接调用 | 间接调用 | CFG | dataflow | Host/Device Event | 源码证据 | 代码—领域链接类型 | 链接 provenance | 双向导航 | Target/revision 绑定 | 链接失效/修复 | 歧义/abstention | 索引 | 增量 | 查询 | Agent 效果 | 领域知识 | 离线 | 许可证 | 维护 | 复现 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A Agent 原生的联邦语义服务骨架 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required | architecturally accommodated | architecturally accommodated | unknown / benchmark required | unknown / benchmark required | unknown / benchmark required |
| B Target-specific CPG 主骨架 | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | architecturally accommodated | unknown / benchmark required | architecturally accommodated | architecturally accommodated | unknown / benchmark required | unknown / benchmark required | unknown / benchmark required |

### 2.1 八层覆盖、事实权限与证据边界

| 候选 | 主责骨架层 | Agent evidence | Evidence provenance | source/revision/Target 绑定 | 事实权限 | 是否需要核验 | 当前结论状态 |
|---|---|---|---|---|---|---|---|
| A Agent 原生的联邦语义服务骨架 | 主责第 2 层身份 spine 与第 3 层联邦语义 provider；共享第 1、4–8 层合同，第 7 层实现为 federation planner | D | project-first-party；底层检索、索引、分析与 Agent 组件另有 independent、peer-reviewed、company-first-party 证据 [S001–S020][S024–S028] | 所有 provider 请求必须携带 `repository_id`、`repository_revision`、Target/build profile 与输入 digest；`CodeEvidence` 绑定代码 revision/occurrence/artifact/span，`DomainEvidence` 才绑定 `source_revision_id`/`SourceLocation` [S011][S012][S029] | provider 只能在其生成器与输入范围内产生 `EXTRACTED`/`RULE_DERIVED`；`EXTRACTED code_fact` 只需 code evidence，不得被强制填领域 citation；编排层不新造事实；Agent 只能交付证据包或明确拒答 | 是；B01–B07、B10–B12、B14–B15 | unknown / benchmark required |
| B Target-specific CPG 主骨架 | 主责第 2 层 Target occurrence/CPG 导入与第 3 层 Target-local CPG；共享第 1、4–8 层合同，第 7 层实现为 scoped CPG gateway | D | project-first-party；CPG 与深分析能力由 project-first-party 材料支持，WiFiDemo 正确性无直接实验 [S014–S018] | 每个 CPG snapshot 必须绑定 `repository_id`、`repository_revision`、Target/build profile、frontend/config digest；代码证据只用 `CodeEvidence`，领域来源独立用 `DomainEvidence.source_revision_id` [S015][S016][S029] | CPG/parser/analyzer 只产生其输入范围内的 `EXTRACTED`/`RULE_DERIVED`；跨域链接按 predicate/status 同时要求 code/domain evidence；Agent 不得把 traversal 结果越权升级 | 是；B01–B06、B10–B12、B14–B15 | unknown / benchmark required |

### 2.2 八层组件映射

第 6 层 assertion layer 是共同基础设施，不是 A/B 的差异：两族都必须使用 `code-domain-linkage.md` 定义的身份、四级 machine status、provenance、冲突、失效和重验证合同。物理上同库或分库不是架构族定义。

| 层 | A Agent 原生的联邦语义服务骨架 | B Target-specific CPG 主骨架 | 共同约束 |
|---|---|---|---|
| 1 输入与快照 | snapshot registry 为各语义 provider 冻结输入 | snapshot registry 为每个 Target CPG 冻结输入 | repository、`repository_revision`、Target Profile、构建命令、生成物和 digest 一致 |
| 2 身份与基础索引 | Clang/SCIP/Kythe 类 occurrence、符号、引用索引作为跨 provider identity spine | CPG 导入前建立 Target-qualified occurrence 与跨图 identity 映射 | 共享源码在不同 Target 下是不同 occurrence；源码证据可定位 [S010–S012] |
| 3 语义分析提供者 | Agent 编排 compiler/index/CPG/LLVM/deep provider；按问题选择，不预设统一物化表示 | Target-local CPG 是常用程序事实主干；LLVM/deep provider 按缺口补充 | 分析事实携带 generator/version/config；函数指针、宏和数据流效果均待测 [S014–S020] |
| 4 领域原始来源 | 规范、设计文档、issue、commit、ADR 与人工资料原样注册 | 同 A | 原始来源只证明自身内容，不自动证明代码关系 |
| 5 版本化来源注册 | 独立 source registry | 同 A | `SourceRevision`/`SourceLocation`/license/accessed_at 与代码 `RepositoryRevision` 分离 [S029] |
| 6 断言与链接层 | 共同 assertion service | 同 A | Assertion 使用 `evidence[]` 判别联合：代码事实需 `CodeEvidence`，领域声明需 `DomainEvidence`，代码—领域链接需两者；四级权限、Agent 写入边界与 lifecycle 不因主干而改变 |
| 7 查询编排与证据装配 | federation planner 选择 provider、交叉核验并装配 evidence bundle | scoped CPG gateway 先查询 Target 图，必要时调用外部 provider，再装配 evidence bundle | 编排不得新造事实；预算、截断、拒答和 raw DSL fallback 必须可观测 |
| 8 Agent 交付 | 高层语义工具是主入口 | 同一高层语义合同映射到 CPG 查询；raw traversal 仅受控回退 | 最终答案必须引用正确 `repository_revision`、Target、`file:line`/原始来源，或明确拒答 |

## 3. 当前两个主实验骨架

### A — Agent 原生的联邦语义服务骨架

- **Agent 高层接口**：`resolve_target_context`、`find_code_evidence`、`compare_targets`、`explain_relation`、`trace_event`、`get_assertions`、`verify_candidate`、`request_deep_analysis`。每次调用输入范围、预算和所需证据类型；输出有界 evidence bundle、截断标记、验证状态和拒答理由。
- **优势**：可按任务选择 compiler/index/CPG/deep provider；保持 provider 可替换；能把昂贵分析推迟到问题出现时；高层接口直接面向 Agent 任务而非某个 DSL。
- **风险**：跨 provider identity、结果语义和 snapshot 对齐复杂；多次调用可能增加延迟、Token 与失败面；若 planner 选错工具或未执行核验，联邦能力不会自动转化为正确答案。
- **适用任务**：跨 Target 比较、按需深分析、需要组合代码事实与领域来源、任务类型变化大的诊断与影响分析。
- **不可直接声称的能力**：不能声称联邦方式比 CPG 更准确、更快或更易运维；不能因 provider 可接入就声称函数指针、CFG/dataflow 或 Event 路径正确；不能把共同 assertion layer 的治理能力计为 A 独有优势。
- **可证伪条件**：若 B01–B06/B11 的事实正确性低于 B，或 B10/B14 显示工具选择、跨 provider join、调用与延迟成本抵消模块化收益，则 A 的主张被削弱；若无法稳定绑定同一 snapshot/Target，则该主实验臂硬失败，并可触发后续拆分或重定义。
- **当前结论状态**：`unknown / benchmark required`。

### B — Target-specific CPG 主骨架

- **Agent 高层接口**：与 A 使用同一合同；实现首先将 `resolve_target_context`、`find_code_evidence`、`compare_targets`、`explain_relation` 和 `trace_event` 映射到指定 Target CPG，缺口再交给 assertion、compiler 或 LLVM/deep provider；原始 traversal DSL 只作为有审计的回退。
- **优势**：常用代码关系位于统一可遍历表示中；多跳调用、CFG/dataflow 与 source location 可用同一查询面表达；查询与路径裁剪可以集中治理。
- **风险**：C frontend 是否忠实接收真实宏/include/生成物尚未验证；每 Target 分图的资源和跨图身份成本未知；overlay/custom semantics 可能混合推断与确定性事实；DSL/JVM 运维和结果截断可能影响 Agent。
- **适用任务**：Target-local 多跳结构查询、调用/数据流路径、需要稳定重复查询的代码关系分析，以及可通过 CPG 表达的 Event 候选路径。
- **不可直接声称的能力**：不能因名称为 CPG 就声称真实编译视角、函数指针精度、完整 dataflow 或低成本；不能把 assertion lifecycle、领域知识与来源注册计为 B 独有能力。
- **可证伪条件**：若 B01–B06/B11 显示 Target 泄漏、宏/occurrence/边错误，或 B10/B14 显示预构图成本、查询截断和运维负担高于其任务收益，则 B 的主张被削弱；若无法回到正确 revision/Target/file:line，则该主实验臂硬失败，并可触发后续拆分或重定义。
- **当前结论状态**：`unknown / benchmark required`。

## 4. 0/1 查询模式矩阵

0/1 是附着在 A 或 B 上的查询模式，不是第三个程序事实主干。模式 1 的轻量发现结果只能生成候选、排序或压缩上下文；任何强语义结论都必须回到对应主骨架核验，并沿用共同 assertion layer 的事实权限。

| 变体 | 程序事实主干 | 查询路径 | 轻量发现组件 | 强事实核验点 | 成立条件 | 主要失败方式 | 当前结论状态 |
|---|---|---|---|---|---|---|---|
| A0 联邦骨架 + 直接查询 | A | Agent 高层接口直接路由到一个或多个语义 provider，并装配证据 | 无前置轻量发现；词法/no-graph 只作 Benchmark 基线或显式回退 | 返回结果的实际 provider 与 snapshot/Target scope | 直接工具选择与 provider join 在正确性和成本上可接受 | 无效工具调用、provider fan-out、跨 provider identity 错配 | unknown / benchmark required |
| A1 联邦骨架 + 轻量发现后核验 | A | 词法/向量/RepoMap/轻量结构先产候选，再由联邦 provider 核验 | 可替换的 discovery/rerank 组件 | A 的 compiler/index/CPG/LLVM/deep provider | Token、调用和延迟的净减少大于错误候选、漏召回、核验与一致性成本 | 发现层漏掉 gold、错误 Target、核验次数抵消收益、stale discovery | unknown / benchmark required |
| B0 CPG 骨架 + 直接查询 | B | Agent 高层接口直接查询指定 Target CPG，缺口才调用外部 provider | 无前置轻量发现；词法/no-graph 只作 Benchmark 基线或显式回退 | Target-specific CPG 与必要的外部 deep provider | CPG 查询可控且预物化成本能被重复任务摊薄 | traversal 扩张、结果截断、错误 frontend fact、跨 Target 误查 | unknown / benchmark required |
| B1 CPG 骨架 + 轻量发现后核验 | B | 轻量组件定位文件/符号/子图，再在指定 Target CPG 中核验 | 可替换的 discovery/rerank 组件 | Target-specific CPG 与必要的外部 deep provider | Token、调用和延迟的净减少大于错误候选、漏召回、核验与双索引一致性成本 | discovery/CPG snapshot 不一致、候选裁剪破坏路径、维护双系统无净收益 | unknown / benchmark required |

模式 1 只有在 B07、B10、B14 的分层指标共同显示净收益时才成立；不得仅凭 Recall@k、单次 Token 或单次查询时延宣布胜出。模式 0 也不是“无检索”：它可以使用主骨架自身索引和有范围查询，只是不增加独立轻量发现前置层。

## 5. 共同硬门槛与不可混淆项

当前两个主实验骨架都必须满足：

1. **Target-specific compilation view**：代码实体绑定真实编译命令、宏集、`repository_revision` 和 Target；共享源码在不同 Target 下形成不同 occurrence [S010–S012]。
2. **typed 可定位证据**：代码事实通过 `CodeEvidence` 回到 `repository_revision`、TargetOccurrence、SourceArtifact、文件 span 与生成器，不要求 `SourceRevision`；领域声明通过 `DomainEvidence` 回到 `source_revision_id` 与 `SourceLocation`；跨域链接按 predicate/status 同时携带两者 [S025][S029]。
3. **不确定性治理**：规则、Agent、LLM、embedding 或聚类产生的软链接不能覆盖确定性代码事实，且必须保存 provenance、冲突、失效与重新验证 [S021–S025][S029]。

共同 assertion layer、source registry、snapshot consistency、许可证审计与 Agent evidence 双轴是共享条件，不能作为 A/B 胜负项。对当前初始 arms，A/B 的核心差异只在程序事实主干，0/1 的核心差异只在是否增加轻量发现后核验；这不排除 Benchmark 依据新证据拆分、增加或重定义 arms。

## 6. 明确保留的待测问题

1. 四个 WiFiDemo Target 的 compilation database 是否完整、可重复并能驱动 A/B；
2. 联邦 provider 与 CPG frontend 对宏分支、函数指针、ops 表、CFG/dataflow 和 Event 路径的实际 precision/recall；
3. A 的 planner/tool selection 与跨 provider identity join 是否稳定，B 的 Target 分图与 traversal 是否稳定；
4. 模式 1 对 Recall@k、MRR、context yield、最终答案、Token、调用、延迟和一致性成本的净影响；
5. 代码稳定 ID 跨 revision 的保留率，以及领域链接在改名、移动、宏变化和 Target 删除后的失效/修复质量；
6. 高层接口的工具选择正确率、无效调用、raw DSL fallback、截断、拒答和最终 Agent 正确性；
7. 各具体组合的全量/增量资源、故障隔离、离线复现、许可证与替代路径。
