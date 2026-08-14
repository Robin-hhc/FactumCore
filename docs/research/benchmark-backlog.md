# 架构选型后续 Benchmark Backlog

版本：2026-08-14

## 1. 目的与边界

本文件把证据矩阵中的 `architecturally accommodated` 和 `unknown / benchmark required` 转成可执行问题。当前研究没有运行这些实验，也不把计划写成结果。Benchmark 的目标不是生成一个掩盖硬门槛的总分，而是回答：由当前证据构造的 A Agent 原生联邦语义服务与 B Target-specific CPG 两个主实验骨架能否产生正确、可追溯、Target-aware 的代码事实；共同 assertion layer 是否能可靠连接领域知识；0/1 查询模式是否提高 Agent 最终答案，并在什么成本下成立。

当前初始裁决对象如下；它们是可归因、可证伪的实验起点，不是候选空间穷尽证明。若 B01–B15 暴露混杂变量、共享硬失败或新的独立决策轴，Benchmark 可以在预注册下一轮前拆分、增加或重定义实验臂，并版本化记录原因；单轮成对比较一旦开始，其 arm definition 仍须冻结。

- **程序事实主干**：A 与 B；共同第 1、4–8 层不是胜负项。
- **查询模式**：0 直接查询，1 轻量发现后核验；模式 1 不是第三个事实主干。
- **部署变体**：A0、A1、B0、B1。
- **共同 assertion layer**：B08、B09、B13 只验证其权限、provenance、失效和净收益，不把结果写成 A/B 差异。

## 2. 固定实验条件

每个实验记录并冻结以下变量，否则结果不可横向比较：

1. repository URL、commit/tag、submodule、补丁和许可证快照；
2. Target、toolchain/container、构建命令、宏、include、生成文件和 compilation database；
3. 候选工具/模型/embedding/reranker 版本、配置、索引 schema 与 prompt/scaffold；
4. Agent 模型、Token 上限、工具列表、轮次、temperature/seed（若可控）和失败重试策略；
5. 预处理规则、忽略路径、generated/vendor code 策略与硬件/CPU/内存；
6. gold 生成脚本、人工复核人、反事实补丁、原始输出与复现实验日志。

同一问题至少报告三层指标，不能互相替代：

- **事实准确性**：precision、recall、F1、source-location accuracy、Target leakage、calibration/abstention；
- **检索效率**：Recall@k、MRR、context yield、工具调用、Token、索引/增量/查询时延和资源；
- **最终 Agent 正确性**：答案/补丁通过率、证据完整率、错误引用率、counterfactual sensitivity。

### 2.1 成对受控对比与交互

四臂不是一次无控制的横向排名。每个任务、Counterfactual 和重复 seed/run 都按下表形成配对样本；同一 pair 使用相同任务顺序、Agent 模型与 prompt/scaffold、高层工具合同、Token/工具调用/轮次上限、Target、`repository_revision`、输入 digest、硬件和失败重试策略。配对内不得给模式 1 追加预算；discovery、核验与 fallback 均从同一总预算扣除。

| 裁决效应 | 固定 pair | 必须保持不变 | 唯一允许的主差异 |
|---|---|---|---|
| A 上的 discovery 效应 | A0 ↔ A1 | A 主骨架实现、全部事实/deep provider 的版本与配置、snapshot/Target、Agent、高层工具合同和总预算 | A1 增加已冻结版本/配置的轻量 discovery；A0 直接查询 A |
| B 上的 discovery 效应 | B0 ↔ B1 | B 主骨架实现、CPG 与全部 deep provider 的版本与配置、snapshot/Target、Agent、高层工具合同和总预算 | B1 增加与 A1 同一版本/配置/候选预算的轻量 discovery；B0 直接查询 B |
| 模式 0 下的骨架效应 | A0 ↔ B0 | 直接查询模式、snapshot/Target、Agent、高层工具合同、共同 assertion layer、外接 deep provider（若调用）和总预算 | 程序事实主干由 A 换为 B；主干固有 provider/存储实现按臂冻结并公开 |
| 模式 1 下的骨架效应 | A1 ↔ B1 | 轻量 discovery 的实现/索引/版本/配置/候选预算、snapshot/Target、Agent、高层工具合同、共同 assertion layer、外接 deep provider（若调用）和总预算 | 程序事实主干由 A 换为 B；主干固有 provider/存储实现按臂冻结并公开 |

每个事实准确性、检索效率和最终 Agent 指标分别报告四臂原值及上述 pair 的 paired delta/区间，不折叠为总分。另报告二因素交互 `Δinteraction = (A1 - A0) - (B1 - B0)`：它只表示 discovery 效应是否随主骨架改变，不能单独替代任一硬门槛或主效应。若某臂因硬门槛停止，保留失败记录并将依赖该臂的 delta/interaction 标为不可估计，不用剩余臂外推。

## 3. WiFiDemo 主案例

以下编号直接映射 `wifidemo-workload-casebook.md` 的 W01–W08。

| ID | 候选 | 假设 | 输入结构 | Ground truth | 指标 | Counterfactual | 成本 | 影响的决策 |
|---|---|---|---|---|---|---|---|---|
| B01 Target occurrence | A、B；Clang/SCIP/Kythe 与 Joern/Fraunhofer CPG provider | 同一文件在四个 Target 下能形成隔离 occurrence，不串入未编译源码 | W01–W04 的四个构建 Target、共享源码和互斥目录 | `build.py` 成功构建后的 compiler argv、object 清单、`flags.make`/compdb；人工抽查 occurrence | occurrence P/R/F1、Target leakage、缺失 TU、重复实体率 | 交换 chip2/chip8 或 host/device 宏，要求结果随构建改变 | 全量构建与四份索引时间、磁盘、内存 | A/B 是否通过首个硬门槛；联邦 occurrence spine 与 Target 分图的正确性 |
| B02 宏与条件编译 | A、B；compiler frontend 与 CPG frontend | 查询返回真实生效宏和被排除分支，不把源码文本中的 `#if` 当事实 | W03/W04 的 host offload 宏、条件分支和生成构建文件 | compiler `-dM/-E`、对象符号、实际分支的 AST/IR；人工最小断言 | 宏值准确率、active-branch F1、跨 Target 泄漏 | 翻转 `_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD`，保持源码不变 | 预处理/AST/CPG 生成增量时间 | A/B 怎样承载编译真值；CPG 是否可作主干、compdb 是否必须前置 |
| B03 直接调用与源码证据 | A、B；identity/index 与 CPG provider | direct call 能跨文件解析并回到正确 revision/Target/file:line | W02/W08 的入口、同名 static/global 函数和跨文件调用 | compiler AST/IR direct callee + 两人复核；保存行锚点 | call-edge P/R/F1、同名消歧、location accuracy | 重命名一个同名函数或改变 `static` 可见性 | 抽取和查询延迟 | A/B 的 direct-call 与 source-evidence 正确性；identity/index 与 CPG 的边界 |
| B04 间接调用与 ops 表 | A、B；CPG 与 SVF/PhASAR/Frama-C 等 deep provider | 对 W05 的函数指针/ops 既不漏掉真实 target，也不无界扩张候选 | 初始化表、赋值链、call site、Target 配置 | 链接后符号/IR、人工逐路径标注、可运行 probe（可用时） | may-target recall、candidate precision、候选集大小、路径证据完整率 | 在另一 Target 替换一个 ops 实现并加入不可达假 target | 深分析时间/内存；摘要建模工时 | A/B 的 provider 编排与事实主干能否保守承载间接调用；deep provider 是否按需运行 |
| B05 Host/Device Event 路径 | A、B + 共同 assertion layer | send/receive/dispatch/handler 能连接成带方向、侧别与证据的 Event 路径 | W06 的消息 ID、发送/接收 API、dispatch 和 handler | 枚举/表项、direct/indirect call、人工事件序列；必要时日志/trace | event-edge P/R/F1、方向/Side 准确率、完整路径率 | 修改 event ID 或交换 handler，检查旧链接失效 | 领域规则编写与重验证时间 | A/B 提供路径证据的质量；共同 assertion 的规则/推断边界与动态证据需求 |
| B06 共享代码与符号身份 | A、B；SCIP/Kythe/CPG 与 SWHID/SARIF 风格 identity | shared source 在不同 Target 下既可合并 source identity，又能隔离 occurrence/semantic facts | W01 共享文件、W08 同名函数 | content/revision ID、compiler occurrence、人工等价类 | merge/split error、跨 revision retention、rename/move match accuracy | 仅移动文件、仅改注释、仅改宏、语义改动四种 patch | ID 计算与迁移成本 | A/B 的 source identity、Target occurrence 与跨 revision 增量策略 |
| B07 日志到代码再到领域 | A0/A1/B0/B1；保留 lexical 与 no-graph 基线 | exact log/宏名由词法优先；模式 1 只有在轻量发现提高召回且最终回到主干代码证据时才成立 | W07 日志串与 W08 问题描述 | log literal/source、调用者、Target、人工关联的 Event/Feature | Recall@k、MRR、context yield、错误 Target、最终答案正确率 | 删除字面日志、同义改写问题、加入相似干扰日志 | 索引、查询、Token/工具调用 | 0/1 查询模式在 A/B 上的净收益；向量或轻量图是否值得保留 |
| B08 领域标签链接 | 共同 assertion layer；A/B 仅作为等价代码证据输入 | Feature/Chip/Side/Event 链接可区分 `EXTRACTED`、`RULE_DERIVED`、`INFERRED_CANDIDATE`、`CURATED`，并按 predicate/status 强制 `CodeEvidence`、`DomainEvidence` 或两者，且支持双向导航与拒答 | W01–W08 的最小领域标签及原始设计注意事项 | 双人标注 typed assertions 与 `evidence[]` 判别联合；代码事实只标 code evidence，领域声明只标 domain evidence，跨域链接标两者；分歧保留 conflict | link P/R/F1、evidence-kind/类型准确率、provenance 完整率、calibration、abstention | 加入无证据标签、同名领域词、缺少一侧 evidence 的跨域链接和过时设计声明 | 标注/审核时间、查询 Token | 共同领域 schema、Agent/LLM 候选权限和人工审核边界；不裁决 A/B |
| B09 链接失效与修复 | 共同 assertion layer；在 A/B 代码事实输入上各重放一次 | 代码/Target/`repository_revision` 或领域 `source_revision_id` 变化能精准标 stale/invalid，并避免未受影响链接全量重审 | B02/B05/B06 的 patch 序列和断言图 | 预期受影响 assertion 集、重建后的 compiler facts | invalidation precision/recall、错误沿用率、自动修复正确率、重验范围 | revert、rename、Target 删除、宏翻转、evidence 行移动 | 增量时延、重验调用和人工审核量 | 共同 assertion lifecycle、依赖追踪及代码/来源 revision 分离；不裁决 A/B |
| B10 Agent 端到端 | A0/A1/B0/B1 及 no-graph/lexical 基线 | 模式 1 只有在最终回答引用正确 Target 和证据、且效率净收益覆盖错误候选与核验成本时才有价值 | W01–W08 改写为固定问答/诊断/变更影响任务 | assertion-style expected facts、允许答案集合、执行式 verifier；保留每步高层工具与 raw DSL 轨迹 | 高层工具选择正确率、无效工具调用、原始 DSL 退回次数（raw DSL fallback）、结果截断、abstention、Token、工具调用、task pass、evidence completeness、unsupported claim、Target leakage、最终任务正确率 | 对 gold fact 做单点变更，答案必须同步变化 | 每臂至少多次运行的模型费用和方差；区分 discovery、核验与 fallback 成本 | 0/1 查询模式的净收益、高层接口是否足够、检索质量与最终推理质量是否脱节 |

### 3.1 B10 Agent 接口标注与评分协议

B10 在运行前为每个任务发布机器可读的 scorer annotation；annotation 与执行 trace、provider 原始响应和最终答案一起版本化。协议不要求唯一工具序列，而是允许一个或多个等价计划：

1. **valid/equivalent plan**：每个允许计划表示为有限状态 DAG；边记录可接受的高层工具族、必需的 Target/`repository_revision`/参数约束、预期 evidence ID/type，以及可选的等价工具集合、可交换步骤和预先声明的 recovery/diagnostic 动作。能从起点走到接受态并取得任务所需 gold evidence 的路径均为 valid plan；多个 DAG 或同一 DAG 的多条接受路径均为 equivalent plans。评分器不以单一人工轨迹作为唯一 gold。
2. **tool-selection opportunity**：一次实际高层工具选择尝试记为一个 opportunity；在仍有可表达该 goal 的高层工具边时使用 raw DSL，也记为一个高层 opportunity；若运行在仍有必需高层下一步的非接受态终止，再记一个 omission opportunity。分母固定为 `高层工具选择尝试 + 代替高层工具的非必要 raw DSL 尝试 + 必需高层步骤未选择次数`，包含重复和错误调用，不能只按 gold 步骤数计算。annotation 明示高层合同不能表达该 goal 时，justified raw DSL fallback 不进入高层 opportunity 分母，单独按第 5 条评分。
3. **valid selection 与高层工具选择正确率**：在调用发生时，若高层工具、参数作用域和 evidence goal 能匹配至少一个尚可达的 equivalent plan 高层边，则为 valid selection 并按该边推进；否则不推进计划状态。`tool-selection accuracy = valid high-level selections / tool-selection opportunities`。若一次调用同时匹配多条计划，只计一次 valid selection，并保留所有仍可达计划，直到后续轨迹消歧。
4. **invalid call**：以下任一情形由 annotation/scorer 确定为 invalid：不匹配任何仍可达计划边；Target 或 `repository_revision` 错误；违反冻结预算/allowlist；在没有 annotation 标记的 recovery 理由时重复获取已经足够的 evidence；调用结果类型不可能满足当前 evidence goal。invalid call 的计数和 `invalid calls / tool-selection opportunities` 单独报告；超时/工具故障另标 infrastructure failure，不自动归咎于选择错误。
5. **DSL fallback**：任何绕过冻结高层合同、直接调用 provider 原始 DSL/traversal/query language 的选择均计一次 fallback。只有 annotation 明示“现有高层工具不能表达该 evidence goal”，且该调用匹配对应 fallback 边时才是 justified fallback；它不进入高层 opportunity 分母。其余为 unjustified fallback，同时按 invalid call 计，并在存在可用高层边时进入高层 opportunity 分母。分别报告总次数、justified/unjustified 次数，以及 `fallbacks / 全部工具选择次数`；高层工具正确率仍使用第 2 条的独立分母。
6. **truncation 与 truncation-lost-gold**：每个工具响应记录请求 limit、返回条数、`truncated` 标记和 evidence IDs。对所有 truncated 响应，以同一 snapshot/provider/query/config 在 scorer 环境中提高到预登记 oracle cap 重放；若 gold evidence 位于 oracle 结果但不在 Agent 实际响应中，则记 `truncation-lost-gold = 1`。分别报告 `lost-gold / truncated responses`、受影响任务数和后续是否通过等价路径恢复；oracle 重放不计入 Agent 预算或工具选择分母。
7. **最终答案独立评分**：task pass、最终任务正确率、evidence completeness、unsupported claim、Target leakage、abstention 和 Counterfactual sensitivity 以任务/run 为分母独立评分，不与 tool-selection accuracy、invalid-call rate、fallback 或 truncation 指标合成。合法工具计划不保证答案正确，非最短但 valid 的计划也不因长度单独判错；效率由 Token、调用、轮次和延迟另报。

发布 scorer 时必须附至少一个 valid trace、一个等价顺序 trace、一个 invalid-call trace、一个 omission trace 和一个 truncation-lost-gold fixture，并在 A0/A1/B0/B1 上使用同一 annotation 版本。annotation 若遗漏实际可行的等价计划，先由盲审裁决并发布新版本，再重算全部四臂，禁止只修正单臂分数。

## 4. 外部 C 案例集

外部仓库只补充结构多样性，不替代 WiFiDemo。下列 ref/object 由 2026-08-14 对官方 GitHub 仓库执行 `git ls-remote --tags` 核验；annotated tag 固定 dereferenced commit，lightweight tag 固定其直接 commit。开始实验时若上游 ref 与下列 commit 不一致，以完整 commit 为准并记录原因。

| 数据集 | 固定版本 | 许可证边界 | 与 WiFiDemo 的结构映射 | 可构造 Ground truth | 适合任务 |
|---|---|---|---|---|---|
| Zephyr | annotated tag `v4.4.0`；tag object `4f50f0ba8905f27b2f60123d0ee0934fda6fe134`；dereferenced commit `684c9e8f32e4373a21098559f748f06915f950c9` [S031] | Apache-2.0；扫描 `LICENSES` 与模块依赖 | board/SoC/Kconfig/devicetree/driver/subsystem 对应 Target/Chip/config/driver；规模更大 | 构建生成 `.config`、devicetree、compdb/对象；固定 board/sample 后人工标注 driver/API/Event [S032] | Target/宏、生成配置、API→driver、Wi-Fi/网络事件、跨模块调用 |
| RIOT | annotated tag `2026.04.01`；tag object `56ab5471996e422657d7fac81bd76da3b07378df`；dereferenced commit `4a70282b1f1ac6e004138b4ada684a4dc4639653` [S033] | RIOT 主体 LGPL-2.1；外部 source/package 单审 | BOARD/CPU/FEATURE/USEMODULE/driver/sys 对应 Chip/Target/feature/module；radio driver 相邻 | `info-modules`、`info-build`、最终 CFLAGS、对象和 Make 依赖；FEATURE 不得自动等同 MODULE [S034] | Target/module 选择、feature-domain 链接、driver abstraction、反例消歧 |
| Contiki-NG | lightweight tag `release/v5.1`（不是 branch）；commit `2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4` [S035] | 默认 BSD-3-Clause；例外文件和 Cooja submodule 单审 | TARGET/BOARD/CPU、`arch` driver、`os/net/mac`、MAKE_MAC 对应平台/侧别/MAC 实现选择 | Make 构建清单、`%.e` 预处理结果、TARGET/BOARD 与 MAKE_MAC；人工标注 MAC driver path [S036] | MAC 选择、条件编译、platform-independent/arch-specific 分层、Event/packet path |

若上述仓库仍不能覆盖某项 C 结构，可增加单一目的的案例，例如 S026 已冻结的 Open5GS 规格依赖任务；新增项必须先登记 fixed commit、许可证、结构映射和可构造 gold，不能因为“是 C 项目”就加入。

## 5. 跨仓实验问题

| ID | 候选 | 假设 | 输入结构 | Ground truth | 指标 | Counterfactual | 成本 | 影响的决策 |
|---|---|---|---|---|---|---|---|---|
| B11 构建真值可移植性 | A、B | 同一 ingestion contract 可覆盖 CMake/Kconfig/devicetree、GNU Make/FEATURE 和 Make/header 配置，而不写死 WiFiDemo | 四仓固定 Target 各 2–4 个 | compiler argv、对象、生成配置、预处理输出 | 成功率、TU coverage、Target leakage、每仓适配代码量 | 切换 board/feature/MAC，检查选中源变化 | 首次适配与后续维护人时 | A/B 的 ingestion boundary 与 Target correctness 是否可移植；是否接受项目 adapter |
| B12 深分析泛化 | CPG provider 与 LLVM/deep provider（SVF/PhASAR/Frama-C） | function pointer/dataflow 的相对优劣不会只在 WiFiDemo 单例成立 | 四仓选择含回调表、driver vtable、packet buffer 的小切片 | 人工+编译器/运行 probe 交叉 gold | edge/path P/R、超时率、每 KLOC 成本 | 注入不可达 target、wrapper 和 macro alias | 分析资源与 external semantics 工时 | CPG provider 与 LLVM/deep provider 的实际效果、组合边界及按需调用策略 |
| B13 领域知识净收益 | 共同 assertion layer；Wiki/Skill/memory 仅作为 `INFERRED_CANDIDATE` 或有来源的派生输入 | 只有任务匹配且版本正确的知识提高 Agent；generic 或 stale 内容可无收益或负收益 | 每仓 specification-dependent 与 generic 任务配对 | with/without/stale/wrong-version 四臂，执行式 verifier | resolve/pass 差、Token 差、错误引用、abstention | 交换版本、注入冲突规则、移除当前代码证据 | 内容编制与维护成本 | 共同 assertion layer 中何种知识进入常驻、按需或候选层；不裁决 A/B [S023][S026–S028] |
| B14 索引与增量运维 | A0/A1/B0/B1；保留 no-graph/lexical 基线 | 正确性通过硬门槛后，模式 1 只有在导航 Token、调用或延迟的净收益大于错误候选、核验、双索引一致性和故障成本时才成立 | 四仓冷启动 + 小/中/大 patch | clean rebuild 对比 incremental snapshot | build/index/query P50/P95、磁盘/内存、stale fact、Token、工具调用、核验调用、故障隔离 | 中断构建、损坏一个 index、回滚 revision | 硬件时长与运维复杂度 | 0/1 查询模式净收益、生产拓扑、缓存与轻量发现层是否值得采用 |
| B15 许可证与复现 | A0/A1/B0/B1 的具体组件组合及逐项替代路径 | 研究可复现不等于可在产品中组合/再分发；架构族结论不得锁死为单一组件 | 工具、库、模型、容器、数据和外部仓清单 | SPDX/SBOM、LICENSE/NOTICE、官方许可文本和冷机重跑 | 未知许可数、不可再分发组件数、复现成功率、环境偏差 | 分别替换 A 的 identity/deep provider、B 的 CPG provider、模式 1 的 discovery 组件后重跑关键实验 | 法务复核和镜像存储 | A0/A1/B0/B1 可部署边界、排除项、开源 tie-break 与可替代性 |

## 6. 执行顺序与停止条件

1. **Phase A：ground truth** — B01–B06、B11。分别裁决 A/B 的事实主干与 Target correctness；若候选无法稳定绑定 Target、源码证据或 `repository_revision`，或 B02 预登记硬门槛 assertion 中任一宏值/active branch 与 compiler ground truth 不一致、任一其他 Target 的分支被返回为当前 Target active fact，则记为硬失败并停止该主实验臂的后续评估，但可继续作为局部组件或触发下一轮 arm 拆分/重定义。
2. **Phase B：知识链接** — B08–B09、B13。只验证共同 assertion layer；若 `INFERRED_CANDIDATE` 不能保守 abstain、失效或回溯来源，不允许进入确定性事实视图。
3. **Phase C：Agent 与成本** — B07、B10、B12、B14。只有前两阶段通过后，才比较 0/1 查询模式、CPG/LLVM/deep provider 的实际效果与资源。
4. **Phase D：采用审计** — B15。审计 A0/A1/B0/B1 的具体组合和替代路径；许可证或离线复现失败可以排除具体实现，但不能自动否定同一架构族。

任何单一 aggregate score 都不得覆盖 B01/B02/B03/B08/B09 的硬失败；B02 的宏真值、active-branch F1 和跨 Target 泄漏必须逐项公开，不得被其他指标补偿。若候选效果区间接近且没有决定性约束差异，再以开放许可证、可离线复现、维护活跃度和更低适配成本作为 tie-break。
