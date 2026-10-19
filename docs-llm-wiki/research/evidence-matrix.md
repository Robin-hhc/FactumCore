# 面向 Agent 的知识图谱方案证据矩阵

日期：2026-08-25

## 1. 读表规则

本矩阵比较市面方案采用了什么知识建立策略，以及它们怎样支持：

- **Q1：自然语言/领域问题 → 具体代码片段**；
- **Q2：具体代码片段 → 流程与领域解释**。

能力标记：`●` 表示官方材料明确提供；`◐` 表示部分覆盖或必须外接组件；`—` 表示不是该方案主线；`?` 表示公开材料不足。标记说明功能范围，不代表效果优越。

证据等级：

- **独立实验**：研究者可复现的跨方案或跨 Agent 评估。
- **作者评估**：论文作者或项目团队对自己方法的实验。
- **第一方功能**：官方 README/文档证明接口存在，但不证明效果。

## 2. 核心矩阵

| 方案/策略 | 代码知识 | 文档/领域知识 | 代码—文档链接 | Q1 领域→代码 | Q2 代码→解释 | 新鲜度机制 | Agent 接入 | 当前证据 | WiFi MAC 关键未知项 |
|---|---:|---:|---:|---|---|---|---|---|---|
| 词法检索（rg 等） | ◐ | ◐ | — | 精确词命中后读源码 | 从锚点继续搜索 | 直接读当前文件 | shell/内建工具 | 独立检索基线 [S001–S003] | 术语不匹配、关系扩展和 Target 隔离 |
| 向量检索 | ◐ | ● | ◐ | 语义召回候选 chunk | 召回相似说明 | 需重切块/重嵌入 | 通用 RAG | 独立检索研究 [S001–S003] | 无答案拒答、错误 Target、相似不等于关系 |
| Aider RepoMap | ● | — | — | 以符号/文件摘要召回 | 用依赖排序提供仓库概览 | 当前仓映射重建 | Aider 内建 | 第一方功能；独立基准含同类方法 [S001][S004] | C 宏和跨文件关系精度 |
| Codebase-Memory | ● | — | — | MCP 符号/关系查询 | 沿图组织局部结构 | 增量索引 | MCP | 作者论文与第一方 Benchmark [S005][S006] | 预处理、Target 与 C 行为事实 |
| CodeGraph | ● | — | ◐ | 自然语言/符号→explore→源码 | 调用/依赖/社区→局部解释 | 增量同步 | MCP/CLI | 第一方 7 仓 Agent Benchmark [S007] | 小样本；无 WiFi C、领域链接和独立复现 |
| GitNexus | ● | ◐ | ◐ | context/explore 找符号与文件 | impact/社区形成模块视图 | 仓库重新分析 | MCP/浏览器 | 第一方功能 [S008] | C 解析、Target、领域解释准确率 |
| Serena | ● | — | — | Agent 转为 symbol/definition/reference | 沿引用读取局部代码 | 语言服务器实时索引 | MCP | 第一方约 20 任务自评 [S037] | LSP 对宏、指针和跨 Target 的边界 |
| Sourcegraph MCP / SCIP | ● | ◐ | ◐ | search + definition/reference | 符号引用与历史辅助解释 | 索引按提交更新 | MCP/开放索引协议 | 第一方功能 [S038] | 不含 CFG/DDG；产品与协议边界不同 |
| RIG | ● | ◐ | ● | 构建/组件问题→目标、文件、测试 | 文件→组件依赖与测试架构 | 由构建工件重建 | 图接口给 Agent | 作者 8 仓×30 问×3 Agent [S042] | 只覆盖构建/测试架构；WiFi Target 仍需实测 |
| Joern | ● | — | ◐ | 上层将问题转为 CPG 查询 | CFG/DDG/dataflow/slice→行为路径 | CPG 按 revision/Target 重建 | 脚本/server；需封装 | CPG 经典论文与第一方功能 [S014][S015] | 宏、函数指针、Target occurrence 与查询成本 |
| codebadger | ● | — | ◐ | 自然语言→高层 MCP→Joern | 高层 slice/taint/dataflow→解释 | 依赖 Joern CPG | MCP | 作者 3 个真实案例 [S039] | 无受控 WiFi C 实验；案例不能当普遍效果 |
| CodeQL | ● | — | ◐ | 专家/Agent 查询定位路径 | source-to-sink 与查询结果解释 | 数据库重建/增量能力依配置 | CLI/API；需工具封装 | 官方功能 [S013] | 许可、真实构建、C 问答成本与准确率 |
| QLCoder | ● | ◐ | ◐ | 漏洞描述→查询合成→执行反馈 | 查询路径形成解释 | 重跑查询/数据库 | Agent + LSP + MCP | 作者 176 CVE/111 Java 项目对照 [S040] | 结果是 Java CVE 查询，不可外推 WiFi C |
| Fraunhofer AISEC CPG | ● | — | ◐ | 需上层自然语言适配 | CPG pass/关系查询 | 重建图与 pass | 需自建接口 | 第一方功能 [S016] | Agent 工作流与 C/Target 效果数据不足 |
| SVF / PhASAR / Frama-C | ● | — | — | 先找到代码锚点再专项分析 | 指针、值流、切片或证明 | 由 IR/分析输入重建 | 需自建高层工具 | 第一方功能 [S017][S018][S020] | 适用问题、资源成本与 Agent 封装收益 |
| Graphify | ● | ● | ● | 文档/概念→query/path/explain→代码 | 代码社区/路径→report/wiki | 增量/重新生成；细节待测 | Skill/CLI/MCP | 第一方功能 [S021] | 链接 precision、Target、stale detection；memory 数字不适用 |
| Understand Anything | ● | ● | ● | domain/flow 问答→结构实体 | 文件/函数→domain/flow/step | fingerprint 增量更新 | 内建 Agent/查询 | 第一方功能 [S009] | 无公开结构边、领域映射和 WiFi C 效果数据 |
| RepoDoc | ● | ● | ● | 模块文档/交叉引用→API/代码 | RepoKG→模块文档/Mermaid | 双向影响传播与定向重生成 | 多 Agent 写作 | 作者 24 仓、8 语言评估 [S041] | 文档事实准确率、嵌入式 C、Target 与独立复现 |
| LLM-Wiki | — | ● | ◐ | Wiki 解析概念；需外接代码锚点 | 探索结果编译为主题页 | 自演化 Wiki | Agent-native retrieval | 作者论文 [S022] | 不负责可靠 C 解析或源码链接 |
| WiCER | — | ● | ◐ | Wiki-memory 检索；需外接代码锚点 | compile/evaluate/refine 维护解释 | 评测驱动精炼 | Agent 工作流 | 作者论文 [S023] | 不是代码图；代码与版本证据需另建 |

## 3. 按建立策略而不是产品名比较

| 建立策略 | 代表方案 | 主要收益假设 | 可证伪问题 |
|---|---|---|---|
| 普通文本/符号导航 | rg、Serena、SCIP | 成本最低，精确符号和字面量足够解决大量任务 | 加图后是否真的提高 gold evidence recall 或最终答案正确率？ |
| 轻量结构图 | CodeGraph、Codebase-Memory、GitNexus | 用 AST/调用/依赖减少 Agent 盲目探索 | C 宏、Target 和函数指针造成多少错误边？ |
| 深度程序图/专项分析 | Joern、codebadger、CodeQL、SVF 等 | 对 dataflow、slice、间接调用等复杂问题提供可验证路径 | 正确率收益是否覆盖建图、查询和外部语义成本？ |
| 生成式领域/文档知识 | UA、Graphify、RepoDoc、LLM-Wiki/WiCER | 把跨文件结构组织为可理解的领域与流程资产 | 生成主张有多少无证据、遗漏或过期？ |
| 显式/推断链接 | Graphify、UA、RepoDoc | 让领域→代码和代码→解释形成闭环 | 链接 precision/recall、新鲜度和版本/Target 正确率如何？ |
| 构建工件锚定 | RIG、Clang compdb | 用实际编译事实隔离 Target、组件和测试 | 能否覆盖 WiFiDemo 的四个 Target，且不泄漏未编译源码？ |

## 4. 公开数据能够说明什么

| 数据 | 能说明 | 不能说明 |
|---|---|---|
| Agent Retrieval Bench：427 样本、25 仓、308 快照；Agent 轨迹在 27%–35% 样本未命中任何 gold file [S001] | 代码检索仍是独立瓶颈，多种检索互补 | 任一知识图谱在 WiFi C 上一定胜出 |
| ContextBench：1,136 任务、66 仓、8 语言、4 模型、5 Agent [S003] | explored context 与 utilized context 要分开测 | 图关系或领域链接正确率 |
| CodeGraph 第一方：7 仓、每臂 4 次的架构问答，工具调用 -88%、时间 -53%、Token -62%、成本 -44% [S007] | 轻量结构图可能显著减少探索成本 | 独立效果、复杂 C 行为、领域问答与多 Target 正确性 |
| RepoDoc 作者评估：24 仓、8 语言，报告 coverage/completeness 与生成/更新成本改善 [S041] | 图驱动交叉引用文档及增量更新值得纳入实验 | WiFi MAC 领域事实、链接精度或独立优越性 |
| RIG 作者评估：8 仓、每仓 30 问、3 Agent，平均准确率 +12.2%、时间 -53.9% [S042] | 构建工件产生的证据图可能帮助 Agent 回答架构问题 | 数据流、协议流程和生成文档质量 |
| QLCoder 作者评估：176 CVE、111 Java 项目，正确查询 53.4% vs 10% [S040] | 查询合成结合执行反馈可显著优于纯 Agent 生成 | C/WiFi 问答效果，或 CodeQL 比 Joern 更优 |

这些数字的任务、模型、分母和指标不同，不能合并成总分或直接排名。

## 5. 当前收敛结果

### 5.1 后续实验应保留的条件

1. **普通导航**：词法 + 符号工具，作为最低成本基线。
2. **轻量代码图**：以 CodeGraph 为代表，检验结构图的额外收益。
3. **深度程序分析**：以 Joern + codebadger 式高层工具为代表，检验复杂行为问题收益。
4. **代码图 + 文档/领域知识 + 链接**：借鉴 Graphify、UA、RepoDoc 的策略，检验完整双向问答。
5. **构建事实补强**：所有涉及 Target 的条件都使用真实编译工件；这是公平性约束，不是独立答案系统。

具体产品可以替换，实验条件名称不预设最终实现。

### 5.2 不能跨过的门槛

- 答案必须定位到正确 revision、Target 和 `file:line`。
- 未编译分支不能作为当前 Target 的确定事实。
- Host/Device 交互必须表示为 Event/Message，不能伪造跨二进制 `CALLS`。
- LLM/embedding 关系必须标为候选或推断，不能覆盖编译器/源码证据。
- 代码或文档变化后，过期链接必须可检测、可审计。
- 事实准确性、检索效率和最终 Agent 正确率分别报告，不用单一 aggregate score 掩盖失败。

## 6. 当前结论

现有证据足以说明成熟方案正在收敛于三类互补能力，但不足以宣布某个现成产品同时、准确地覆盖 WiFi MAC 的代码知识、领域知识和双向链接。开源优先是效果接近后的 tie-break，而不是在 Benchmark 前替代准确性判断。
