# 知识图谱建立策略的后续 Benchmark Backlog

日期：2026-08-25

## 当前执行状态（2026-08-25）

- 本仓只交付验收用例，不实现 Agent、模型客户端、代码工具适配器、运行器或报告器；执行由外部 DeepSeek harness 负责。
- 已设计 40 个公开问题（20 个自然语言到代码、20 个代码到流程），并选出 12 题 pilot 子集。
- 40 份 source-anchored gold 草案已完成首轮源码核对；第二人工评审尚未完成，所以全部保持 `draft`，不能当作正式判分答案。
- C0/C1/C2 尚未由外部 harness 正式运行，因此当前没有工具效果、模型正确率或“是否需要文档”的实验结论。接入边界见 [`../experiments/wifidemo-code-only-pilot.md`](../experiments/wifidemo-code-only-pilot.md)。
- C3/C4 文档实验、外部 C 项目、mutation、stale-link 与文档增量价值仍全部 pending；本轮没有测量文档是否带来增益。

## 1. 目的与边界

本轮不在 WiFiDemo 上实施实验，只预注册后续需要验证的问题。实验不比较预设的完整系统设计，而比较 Agent 获得知识的条件：普通导航、轻量代码图、深度程序分析、文档/领域知识以及代码—文档链接。

首轮已批准的可执行切片见 [`../superpowers/specs/2026-08-25-wifidemo-code-only-agent-acceptance-design.md`](../superpowers/specs/2026-08-25-wifidemo-code-only-agent-acceptance-design.md)：它只比较 C0/C1/C2，直接运行40题代码-only Agent验收，并把 C0 收窄为项目实际使用的纯文本搜索与源码读取。C3/C4、外部项目和文档增量仍保留在本文件作为后续研究，不混入首轮结论。

所有结果分三层报告：

1. **事实准确性**：图中的实体、关系、Target、文档链接是否正确。
2. **检索效率**：是否更快、更少 Token/调用地找到 gold evidence。
3. **最终 Agent 正确性**：答案或任务是否正确、完整、有证据且能拒答。

不合并为单一总分。事实硬失败不能由速度或 Token 节省抵消。

## 2. 实验条件

| 条件 | Agent 可用知识 | 用途 |
|---|---|---|
| C0 普通导航 | 当前源码、rg、文件读取；不提供预解析 definition/reference/call graph | 最低成本基线 |
| C1 轻量代码图 | C0 + Tree-sitter/符号/调用/依赖图；代表为 CodeGraph | 测结构图的增量价值 |
| C2 深度程序分析 | C0 + Target-specific CPG/dataflow/slice；代表为 Joern + 高层工具 | 测复杂行为事实的增量价值 |
| C3 代码图 + 原始文档 | C1 或 C2 + README/设计/规范/测试文档检索 | 测领域材料的增量价值 |
| C4 代码图 + 生成文档 + 双向链接 | C3 + Graphify/UA/RepoDoc 式领域资产、源码回链和增量失效 | 测完整闭环的增量价值 |

RIG/Clang 式真实构建工件用于约束所有条件的 Target 范围，不作为额外“知识优势”混入比较。若具体工具无法接受同一构建输入，必须记录为适配限制。

## 3. 固定控制变量

- 冻结 repository、commit、Target、工具版本、索引配置、模型、外部 harness 版本、prompt、总 Token/时间预算。
- 每个任务允许多个等价工具路径，但 gold facts、证据范围和评分器版本固定。
- 保存完整工具调用、查询、原始返回、读取文件、最终答案和成本。
- 每个随机条件运行多次，报告原始值、方差/区间和失败案例。
- 对生成式知识分别运行 current、stale、wrong-target、no-document 条件。
- 先完成事实层测试，再运行 Agent；事实层失败的条件保留失败记录，不做性能外推。

## 4. WiFiDemo 主案例 B01–B10

| ID | 问题 | 适用条件 | Gold evidence | 主要指标 | 反事实/扰动 | 裁决内容 |
|---|---|---|---|---|---|---|
| B01 Target occurrence | 同一源码在不同构建 Target 中是否正确隔离 | C0–C4 | 四个目标的 compiler argv、object 清单、`flags.make`/compdb | occurrence P/R/F1、Target leakage、缺失 TU | 交换 chip/host/device Target | 所有代码知识条件的首个硬门槛 |
| B02 宏与条件编译 | 能否返回真实生效宏和 active branch | C0–C4 | compiler `-dM/-E`、对象符号、AST/IR | 宏值准确率、active-branch F1、跨 Target 泄漏 | 翻转 host-offload 宏而不改源码 | 轻量图/CPG 是否尊重真实构建 |
| B03 直接调用与源码证据 | 跨文件 direct call 是否解析并回到正确 `file:line` | C0–C4 | compiler AST/IR direct callee + 双人复核 | call-edge P/R/F1、同名消歧、location accuracy | 重命名同名函数或改变 `static` | 普通导航、轻量图、深度图的基础代码事实 |
| B04 间接调用与 ops 表 | 函数指针候选是否既不漏真值也不无界扩张 | C1–C4 | 链接后符号/IR、人工路径、可运行 probe | may-target recall、candidate precision、候选集大小 | 替换实现并加入不可达假 target | 深分析相对轻量图的必要性与成本 |
| B05 Host/Device Event 路径 | send/receive/dispatch/handler 是否形成正确消息路径 | C1–C4 | 枚举/表项、调用边、人工事件序列、可用 trace | event-edge P/R/F1、方向/Side、完整路径率 | 修改 event ID 或交换 handler | 代码图与领域规则能否避免伪造跨二进制调用 |
| B06 共享代码与符号身份 | shared source 能否共享内容身份但隔离 Target occurrence | C1–C4 | content/revision ID、compiler occurrence、人工等价类 | merge/split error、rename/move match | 移动、改注释、改宏、语义改动 | 增量索引与跨版本链接基础 |
| B07 领域/日志问题到代码 | 模糊领域词或日志能否定位 gold code anchors | C0–C4 | 日志字面量、领域同义词、调用者、Target、人工 anchors | Recall@K、MRR、context yield、无答案拒答 | 删除字面量、同义改写、加入相似干扰 | 文档、轻量图、深分析对 Q1 的净收益 |
| B08 代码到流程解释 | 从函数/宏生成的流程是否覆盖正确步骤和证据 | C0–C4 | 人工步骤图、调用/Event/dataflow、文档主张 | step/edge P/R、顺序正确率、evidence coverage、unsupported claim | 替换 handler、改变分支或移除文档 | 各知识条件对 Q2 的净收益 |
| B09 链接失效与修复 | 代码/Target/文档变化后能否发现并修复过期链接 | C3–C4 | 预期受影响链接集、重建事实与文档 | invalidation P/R、修复 P/R、错误沿用率、误更新率 | rename、行移动、宏翻转、文档版本交换、revert | 双向链接的新鲜度和增量成本 |
| B10 Agent 端到端 | 两类问题的最终答案是否正确、可核验且高效 | C0–C4 | assertion-style facts、允许答案集、执行式 verifier | task pass、事实正确率、证据完整率、Target leakage、abstention、Token、调用、时延 | 对 gold fact 做单点变化并要求答案同步 | 检索收益是否真正转化为 Agent 收益 |

## 5. 外部 C 案例 B11–B15

案例集应组合 WiFiDemo 与结构相邻或具有复杂 C 架构的开源项目。当前固定候选为 Zephyr 4.4.0、RIOT 2026.04.01、Contiki-NG 5.1，并可增加许可清晰、构建可冻结的其他 C 项目（S031–S036）。版本、submodule、工具链和 Target 必须冻结。

| ID | 问题 | 适用条件 | Gold evidence | 主要指标 | 反事实/扰动 | 裁决内容 |
|---|---|---|---|---|---|---|
| B11 构建真值可移植性 | 同一策略能否适配 CMake/Kconfig/devicetree、GNU Make/FEATURE、Make/header | C0–C4 | compiler argv、objects、生成配置、预处理输出 | 成功率、TU coverage、Target leakage、适配人时 | 切换 board/feature/MAC | 构建工件锚定是否可移植 |
| B12 深分析泛化 | 间接调用/dataflow 优势是否超出 WiFiDemo 单例 | C1 vs C2 | 人工 + compiler/IR + runtime probe 交叉 gold | edge/path P/R、超时率、每 KLOC 成本 | 注入不可达 target、wrapper、macro alias | CPG/专项分析的真实增量价值 |
| B13 文档与领域知识净收益 | 领域材料是否只在匹配任务与版本下提高 Agent | C1/C2 vs C3/C4 | specification-dependent 与 generic 任务成对 verifier | pass 差、证据覆盖、错误引用、abstention、Token | current/stale/wrong-version/no-doc | 何种文档知识值得长期维护 |
| B14 索引与增量运维 | 正确性过门后，收益是否覆盖索引和一致性成本 | C0–C4 | clean rebuild 与 incremental snapshot 对照 | build/index/query P50/P95、磁盘、内存、stale facts、Token/调用 | 中断构建、损坏索引、回滚 revision | 轻量图、深度图和生成文档的运行代价 |
| B15 许可证与复现 | 候选是否能开源、离线、可替换地复现 | C0–C4 的具体组件组合 | SPDX/SBOM、LICENSE/NOTICE、容器、模型与数据清单 | 未知许可数、不可再分发组件、冷机复现成功率 | 替换同类组件后重跑关键实验 | 效果接近时的开源 tie-break 与部署边界 |

每个 ID 在本文件中只对应一个预注册问题；实施时可以拆成多个测试用例，但不得改变问题含义后仍沿用旧结果。

## 6. 两类问答的评分协议

### 6.1 Q1：领域到代码

Gold 不应只是一份文件列表，而应包含：必要文件、必要符号/行锚点、Target、允许替代证据、无答案条件。报告：

- file/symbol/anchor Recall@K 与 MRR；
- 在固定 Token 预算中的 context yield；
- 错误 Target、无关候选和完全漏检率；
- Agent 最终实际使用的 evidence，而不仅是曾经探索的 evidence；
- 无答案和证据不足时的 abstention。

### 6.2 Q2：代码到流程

Gold 使用可执行或双人复核的步骤图：节点是代码动作/Event/Message/领域步骤，边包含顺序、调用或数据依赖。报告：

- step/edge precision、recall、F1 与顺序正确率；
- 关键主张的源码/文档 evidence coverage；
- 把 may-call 写成 must-call、把推断写成事实、把跨二进制消息写成 `CALLS` 的错误率；
- 流程解释随单点代码变化同步更新的比例。

## 7. 运行顺序与停止条件

1. **Ground truth**：先执行 B01–B06、B11。任何条件若泄漏 Target、不能回到正确源码或把 inactive branch 当事实，则停止其后续 Agent 效果排名。
2. **双向任务**：执行 B07–B10，分别报告 Q1 和 Q2；不因某一方向优秀就认定整体成熟。
3. **外部有效性**：执行 B12–B14，确认结果不是 WiFiDemo 或单个问题特例。
4. **采用审计**：执行 B15。若效果区间相近且无硬约束差异，优先开放许可证、离线可复现、维护活跃且适配成本低的方案。

若 C1 在多数简单任务与 C0 相当但显著减少成本，可以作为导航增强；若 C2 只在间接调用/dataflow 任务显著获益，应按需使用而非全量强制；若 C4 不能稳定检测 stale link，则即使文档可读性高也不能进入确定性答案路径。

## 8. 预注册输出

实施实验前必须发布：

- 冻结的仓库/commit/Target/工具/模型清单；
- 每个任务的 gold facts、证据和反事实 patch；
- 评分器及至少一个正例、等价路径、错误调用、遗漏和截断 fixture；
- 每个条件允许的工具、预算、失败与重试规则；
- 原始结果、统计脚本、失败案例和许可证清单。

只有这些材料完整后，实验才可以支持最终选型。
