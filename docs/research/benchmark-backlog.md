# 架构选型后续 Benchmark Backlog

版本：2026-08-14

## 1. 目的与边界

本文件把证据矩阵中的 `claimed` 和关键 `unknown` 转成可执行问题。当前研究没有运行这些实验，也不把计划写成结果。Benchmark 的目标不是生成一个掩盖硬门槛的总分，而是回答：候选是否能产生正确、可追溯、Target-aware 的代码事实；是否能可靠连接领域知识；这些能力是否提高 Agent 最终答案，并在什么成本下成立。

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

## 3. WiFiDemo 主案例

以下编号直接映射 `wifidemo-workload-casebook.md` 的 W01–W08。

| ID | 候选 | 假设 | 输入结构 | Ground truth | 指标 | Counterfactual | 成本 | 影响的决策 |
|---|---|---|---|---|---|---|---|---|
| B01 Target occurrence | L1/L2/L3；Clang、SCIP、Kythe、Joern、Fraunhofer CPG、两种轻量图 | 同一文件在四个 Target 下能形成隔离 occurrence，不串入未编译源码 | W01–W04 的四个构建 Target、共享源码和互斥目录 | `build.py` 成功构建后的 compiler argv、object 清单、`flags.make`/compdb；人工抽查 occurrence | occurrence P/R/F1、Target leakage、缺失 TU、重复实体率 | 交换 chip2/chip8 或 host/device 宏，要求结果随构建改变 | 全量构建与四份索引时间、磁盘、内存 | L1–L3 是否通过首个硬门槛；每 Target 分图还是统一图 |
| B02 宏与条件编译 | L1/L2；compiler frontend 与 CPG frontend | 查询返回真实生效宏和被排除分支，不把源码文本中的 `#if` 当事实 | W03/W04 的 host offload 宏、条件分支和生成构建文件 | compiler `-dM/-E`、对象符号、实际分支的 AST/IR；人工最小断言 | 宏值准确率、active-branch F1、跨 Target 泄漏 | 翻转 `_PRE_WLAN_FEATURE_HOST_TX_OFFLOAD`，保持源码不变 | 预处理/AST/CPG 生成增量时间 | CPG 能否作事实核心；compdb 是否必须前置 |
| B03 直接调用与源码证据 | 全部结构/语义候选 | direct call 能跨文件解析并回到正确 revision/Target/file:line | W02/W08 的入口、同名 static/global 函数和跨文件调用 | compiler AST/IR direct callee + 两人复核；保存行锚点 | call-edge P/R/F1、同名消歧、location accuracy | 重命名一个同名函数或改变 `static` 可见性 | 抽取和查询延迟 | 轻量图是否足够；SCIP/Kythe 与 CPG 的边界 |
| B04 间接调用与 ops 表 | L1/L2；SVF、PhASAR、Frama-C、Joern、Fraunhofer CPG | 对 W05 的函数指针/ops 既不漏掉真实 target，也不无界扩张候选 | 初始化表、赋值链、call site、Target 配置 | 链接后符号/IR、人工逐路径标注、可运行 probe（可用时） | may-target recall、candidate precision、候选集大小、路径证据完整率 | 在另一 Target 替换一个 ops 实现并加入不可达假 target | 深分析时间/内存；摘要建模工时 | 选择 deep provider；是否按需运行而非全量常驻 |
| B05 Host/Device Event 路径 | L1/L2/L3 + assertion layer | send/receive/dispatch/handler 能连接成带方向、侧别与证据的 Event 路径 | W06 的消息 ID、发送/接收 API、dispatch 和 handler | 枚举/表项、direct/indirect call、人工事件序列；必要时日志/trace | event-edge P/R/F1、方向/Side 准确率、完整路径率 | 修改 event ID 或交换 handler，检查旧链接失效 | 领域规则编写与重验证时间 | 代码—领域链接应规则化还是推断化；是否需动态证据 |
| B06 共享代码与符号身份 | SCIP、Kythe、CPG、SWHID/SARIF 风格 identity | shared source 在不同 Target 下既可合并 source identity，又能隔离 occurrence/semantic facts | W01 共享文件、W08 同名函数 | content/revision ID、compiler occurrence、人工等价类 | merge/split error、跨 revision retention、rename/move match accuracy | 仅移动文件、仅改注释、仅改宏、语义改动四种 patch | ID 计算与迁移成本 | 统一 identity schema 与增量策略 |
| B07 日志到代码再到领域 | 词法、向量、RepoMap、结构图、混合检索 | exact log/宏名由词法优先，自然语言症状由混合检索提高召回，且最终落到代码证据 | W07 日志串与 W08 问题描述 | log literal/source、调用者、Target、人工关联的 Event/Feature | Recall@k、MRR、context yield、错误 Target、最终答案正确率 | 删除字面日志、同义改写问题、加入相似干扰日志 | 索引、查询、Token/工具调用 | L3 的发现层组合；向量是否带来净收益 |
| B08 领域标签链接 | H01–H07 + assertion layer | Feature/Chip/Side/Event 链接可区分 extracted/rule/manual/inferred，且支持双向导航与拒绝 | W01–W08 的最小领域标签及原始设计注意事项 | 双人标注 typed assertions；分歧保留 conflict，不强制多数投票 | link P/R/F1、类型准确率、provenance 完整率、calibration、abstention | 加入无证据标签、同名领域词和过时设计声明 | 标注/审核时间、查询 Token | 领域 schema、LLM 候选权限和人工审核边界 |
| B09 链接失效与修复 | 三个架构族 | 代码/Target/revision 变化能精准标 stale/invalid，并避免未受影响链接全量重审 | B02/B05/B06 的 patch 序列和断言图 | 预期受影响 assertion 集、重建后的 compiler facts | invalidation precision/recall、错误沿用率、自动修复正确率、重验范围 | revert、rename、Target 删除、宏翻转、evidence 行移动 | 增量时延、重验调用和人工审核量 | assertion lifecycle、依赖追踪和 revision 绑定 |
| B10 Agent 端到端 | L1/L2/L3 及 no-graph/lexical 基线 | 更强事实层只有在最终回答引用正确 Target 和证据时才有价值 | W01–W08 改写为固定问答/诊断/变更影响任务 | assertion-style expected facts、允许答案集合、执行式 verifier | task pass、evidence completeness、unsupported claim、Target leakage、Token/工具调用 | 对 gold fact 做单点变更，答案必须同步变化 | 每臂至少多次运行的模型费用和方差 | 架构族排序；检索质量与推理质量是否脱节 |

## 4. 外部 C 案例集

外部仓库只补充结构多样性，不替代 WiFiDemo。开始实验时若上游 tag 与下列 hash 不一致，以 hash 为准并记录原因。

| 数据集 | 固定版本 | 许可证边界 | 与 WiFiDemo 的结构映射 | 可构造 Ground truth | 适合任务 |
|---|---|---|---|---|---|
| Zephyr | `v4.4.0` / `684c9e8` [S031] | Apache-2.0；扫描 `LICENSES` 与模块依赖 | board/SoC/Kconfig/devicetree/driver/subsystem 对应 Target/Chip/config/driver；规模更大 | 构建生成 `.config`、devicetree、compdb/对象；固定 board/sample 后人工标注 driver/API/Event [S032] | Target/宏、生成配置、API→driver、Wi-Fi/网络事件、跨模块调用 |
| RIOT | `2026.04.01` / `4a70282` [S033] | RIOT 主体 LGPL-2.1；外部 source/package 单审 | BOARD/CPU/FEATURE/USEMODULE/driver/sys 对应 Chip/Target/feature/module；radio driver 相邻 | `info-modules`、`info-build`、最终 CFLAGS、对象和 Make 依赖；FEATURE 不得自动等同 MODULE [S034] | Target/module 选择、feature-domain 链接、driver abstraction、反例消歧 |
| Contiki-NG | `release/v5.1` / `2b87baf` [S035] | 默认 BSD-3-Clause；例外文件和 Cooja submodule 单审 | TARGET/BOARD/CPU、`arch` driver、`os/net/mac`、MAKE_MAC 对应平台/侧别/MAC 实现选择 | Make 构建清单、`%.e` 预处理结果、TARGET/BOARD 与 MAKE_MAC；人工标注 MAC driver path [S036] | MAC 选择、条件编译、platform-independent/arch-specific 分层、Event/packet path |

若上述仓库仍不能覆盖某项 C 结构，可增加单一目的的案例，例如 S026 已冻结的 Open5GS 规格依赖任务；新增项必须先登记 fixed commit、许可证、结构映射和可构造 gold，不能因为“是 C 项目”就加入。

## 5. 跨仓实验问题

| ID | 候选 | 假设 | 输入结构 | Ground truth | 指标 | Counterfactual | 成本 | 影响的决策 |
|---|---|---|---|---|---|---|---|---|
| B11 构建真值可移植性 | L1/L2/L3 | 同一 ingestion contract 可覆盖 CMake/Kconfig/devicetree、GNU Make/FEATURE 和 Make/header 配置，而不写死 WiFiDemo | 四仓固定 Target 各 2–4 个 | compiler argv、对象、生成配置、预处理输出 | 成功率、TU coverage、Target leakage、每仓适配代码量 | 切换 board/feature/MAC，检查选中源变化 | 首次适配与后续维护人时 | ingestion boundary 是否稳定；是否接受项目 adapter |
| B12 深分析泛化 | CPG 与 LLVM-based providers | function pointer/dataflow 的相对优劣不会只在 WiFiDemo 单例成立 | 四仓选择含回调表、driver vtable、packet buffer 的小切片 | 人工+编译器/运行 probe 交叉 gold | edge/path P/R、超时率、每 KLOC 成本 | 注入不可达 target、wrapper 和 macro alias | 分析资源与 external semantics 工时 | Joern/Fraunhofer/SVF/PhASAR/Frama-C 组件范围 |
| B13 领域知识净收益 | Wiki/Skill/memory/assertion layer | 只有任务匹配且版本正确的知识提高 Agent；generic 或 stale 内容可无收益或负收益 | 每仓 specification-dependent 与 generic 任务配对 | with/without/stale/wrong-version 四臂，执行式 verifier | resolve/pass 差、Token 差、错误引用、abstention | 交换版本、注入冲突规则、移除当前代码证据 | 内容编制与维护成本 | 何种知识进入常驻、按需或候选层 [S023][S026–S028] |
| B14 索引与增量运维 | 三架构族 | 正确性通过硬门槛后，L3 可能降低常用导航成本，但双系统一致性可能抵消收益 | 四仓冷启动 + 小/中/大 patch | clean rebuild 对比 incremental snapshot | build/index/query P50/P95、磁盘/内存、stale fact、Token、故障隔离 | 中断构建、损坏一个 index、回滚 revision | 硬件时长与运维复杂度 | 生产拓扑、缓存、是否采用轻量发现层 |
| B15 许可证与复现 | 所有进入 shortlist 的具体实现 | 研究可复现不等于可在产品中组合/再分发 | 工具、库、模型、容器、数据和外部仓清单 | SPDX/SBOM、LICENSE/NOTICE、官方许可文本和冷机重跑 | 未知许可数、不可再分发组件数、复现成功率、环境偏差 | 替换限制组件后重跑关键实验 | 法务复核和镜像存储 | 排除项、开源 tie-break、可部署边界 |

## 6. 执行顺序与停止条件

1. **Phase A：ground truth** — B01–B06、B11。若候选无法稳定绑定 Target、源码证据或 revision，停止其“完整方案”评估，但可继续作为局部组件。
2. **Phase B：知识链接** — B08–B09、B13。若推断边不能保守 abstain、失效或回溯来源，不允许进入 verified fact 层。
3. **Phase C：Agent 与成本** — B07、B10、B12、B14。只有前两阶段通过后，才比较任务效果与资源。
4. **Phase D：采用审计** — B15。许可证或离线复现失败可以排除具体实现，但不能自动否定同一架构族。

任何单一 aggregate score 都不得覆盖 B01/B03/B08/B09 的硬失败。若候选效果区间接近且没有决定性约束差异，再以开放许可证、可离线复现、维护活跃度和更低适配成本作为 tie-break。
