# 架构候选证据矩阵

核验日期：2026-08-14

## 1. 读表规则

本矩阵只压缩 `source-ledger.md`、`solution-inventory.md` 和 `code-domain-linkage.md` 已登记的证据，不把“项目存在某项功能”外推为“该功能已在 WiFiDemo 上有效”。每个单元格只使用四种状态：

- `verified`：有独立实验、标准正文或已逐项复核的原始结果支持；
- `claimed`：项目、公司或论文作者材料明确声明，但尚未在 WiFiDemo 独立复现；
- `unsupported`：现有材料明确不提供该能力，或方案定位与该能力冲突；
- `unknown`：材料不足，不能据缺失信息推断为不支持。

方括号内的 `Sxxx` 指向 `source-ledger.md`。`claimed` 不等于低质量，`unknown` 也不等于失败；二者都必须进入后续实验清单。

## 2. 固定维度矩阵

| 候选 | Target/宏 | 直接调用 | 间接调用 | CFG | dataflow | Host/Device Event | 源码证据 | 代码—领域链接类型 | 链接 provenance | 双向导航 | Target/revision 绑定 | 链接失效/修复 | 歧义/abstention | 索引 | 增量 | 查询 | Agent 效果 | 领域知识 | 离线 | 许可证 | 维护 | 复现 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R01 词法检索 | unsupported [S001] | unsupported [S001] | unsupported [S001] | unsupported [S001] | unsupported [S001] | unknown [S001] | claimed [S001] | unsupported [S001] | unknown [S001] | claimed [S001] | unknown [S001] | unknown [S001] | claimed [S001] | claimed [S001] | unknown [S001] | claimed [S001] | verified [S001] | unsupported [S001] | claimed [S001] | unknown [S001] | claimed [S001] | verified [S001] |
| R02 代码向量检索 | unsupported [S002] | unsupported [S002] | unsupported [S002] | unsupported [S002] | unsupported [S002] | unknown [S002] | claimed [S001] | claimed [S001] | unknown [S001] | claimed [S001] | unknown [S002] | unknown [S002] | verified [S001] | claimed [S001] | unknown [S001] | claimed [S001] | verified [S001] | unsupported [S002] | claimed [S001] | unknown [S001] | claimed [S001] | verified [S002] |
| R03 Aider RepoMap | unsupported [S004] | claimed [S004] | unsupported [S004] | unsupported [S004] | unsupported [S004] | unknown [S004] | claimed [S004] | unsupported [S004] | unknown [S004] | claimed [S004] | unknown [S004] | unknown [S004] | unknown [S004] | claimed [S004] | unknown [S004] | claimed [S004] | verified [S001] | unsupported [S004] | claimed [S004] | claimed [S004] | claimed [S004] | verified [S001] |
| R04 Codebase-Memory | unknown [S006] | claimed [S006] | claimed [S006] | unknown [S006] | unknown [S006] | unknown [S006] | claimed [S006] | claimed [S006] | unknown [S006] | claimed [S006] | unknown [S006] | claimed [S006] | unknown [S006] | claimed [S006] | claimed [S006] | claimed [S006] | verified [S005] | claimed [S006] | claimed [S006] | claimed [S006] | claimed [S006] | verified [S005] |
| R05 CodeGraph | unknown [S007] | claimed [S007] | claimed [S007] | unknown [S007] | unknown [S007] | unknown [S007] | claimed [S007] | claimed [S007] | unknown [S007] | claimed [S007] | unknown [S007] | claimed [S007] | unknown [S007] | claimed [S007] | claimed [S007] | claimed [S007] | claimed [S007] | unsupported [S007] | claimed [S007] | claimed [S007] | claimed [S007] | claimed [S007] |
| R06 GitNexus | unknown [S008] | claimed [S008] | claimed [S008] | unknown [S008] | unknown [S008] | unknown [S008] | claimed [S008] | claimed [S008] | unknown [S008] | claimed [S008] | unknown [S008] | claimed [S008] | unknown [S008] | claimed [S008] | claimed [S008] | claimed [S008] | unknown [S008] | unsupported [S008] | claimed [S008] | claimed [S008] | claimed [S008] | unknown [S008] |
| R07 Understand Anything | unknown [S009] | claimed [S009] | unknown [S009] | unknown [S009] | unknown [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | unknown [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | unknown [S009] |
| A01 Clang/LLVM | claimed [S010] | claimed [S010] | claimed [S010] | claimed [S010] | claimed [S010] | unsupported [S010] | claimed [S010] | unsupported [S010] | claimed [S010] | claimed [S010] | claimed [S010] | unknown [S010] | claimed [S010] | claimed [S010] | claimed [S010] | claimed [S010] | unknown [S010] | unsupported [S010] | claimed [S010] | claimed [S010] | claimed [S010] | unknown [S010] |
| A02 SCIP/scip-clang | claimed [S011] | claimed [S011] | unknown [S011] | unsupported [S011] | unsupported [S011] | unsupported [S011] | claimed [S011] | unsupported [S011] | claimed [S011] | claimed [S011] | claimed [S011] | claimed [S011] | unknown [S011] | claimed [S011] | claimed [S011] | claimed [S011] | unknown [S011] | unsupported [S011] | claimed [S011] | claimed [S011] | claimed [S011] | unknown [S011] |
| A03 Kythe | claimed [S012] | claimed [S012] | unknown [S012] | unsupported [S012] | unsupported [S012] | unsupported [S012] | claimed [S012] | unsupported [S012] | claimed [S012] | claimed [S012] | claimed [S012] | claimed [S012] | unknown [S012] | claimed [S012] | claimed [S012] | claimed [S012] | unknown [S012] | unsupported [S012] | claimed [S012] | claimed [S012] | claimed [S012] | unknown [S012] |
| A04 CodeQL | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | unsupported [S013] | claimed [S013] | unsupported [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | claimed [S013] | unknown [S013] | unsupported [S013] | claimed [S013] | claimed [S013] | claimed [S013] | unknown [S013] |
| A05 Joern | unknown [S015] | claimed [S015] | unknown [S015] | claimed [S015] | claimed [S015] | unsupported [S015] | claimed [S015] | unsupported [S015] | claimed [S015] | claimed [S015] | unknown [S015] | claimed [S015] | claimed [S015] | claimed [S015] | claimed [S015] | claimed [S015] | unknown [S015] | unsupported [S015] | claimed [S015] | claimed [S015] | claimed [S015] | unknown [S015] |
| A06 Fraunhofer CPG | unknown [S016] | claimed [S016] | claimed [S016] | claimed [S016] | claimed [S016] | unsupported [S016] | claimed [S016] | claimed [S016] | claimed [S016] | claimed [S016] | unknown [S016] | claimed [S016] | claimed [S016] | claimed [S016] | claimed [S016] | claimed [S016] | unknown [S016] | claimed [S016] | claimed [S016] | claimed [S016] | claimed [S016] | unknown [S016] |
| A07 SVF | claimed [S017] | claimed [S017] | claimed [S017] | claimed [S017] | claimed [S017] | unsupported [S017] | claimed [S017] | unsupported [S017] | claimed [S017] | claimed [S017] | claimed [S017] | unknown [S017] | unknown [S017] | claimed [S017] | unknown [S017] | claimed [S017] | unknown [S017] | unsupported [S017] | claimed [S017] | claimed [S017] | claimed [S017] | unknown [S017] |
| A08 PhASAR | claimed [S020] | claimed [S020] | claimed [S020] | claimed [S020] | claimed [S020] | unsupported [S020] | claimed [S020] | unsupported [S020] | claimed [S020] | claimed [S020] | claimed [S020] | unknown [S020] | unknown [S020] | claimed [S020] | unknown [S020] | claimed [S020] | unknown [S020] | unsupported [S020] | claimed [S020] | claimed [S020] | claimed [S020] | unknown [S020] |
| A09 Frama-C | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | unsupported [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | unknown [S018] | claimed [S018] | claimed [S018] | claimed [S018] | claimed [S018] | unknown [S018] |
| A10 Semgrep CE | unsupported [S019] | claimed [S019] | unsupported [S019] | claimed [S019] | claimed [S019] | unsupported [S019] | claimed [S019] | unsupported [S019] | claimed [S019] | claimed [S019] | unknown [S019] | claimed [S019] | claimed [S019] | claimed [S019] | claimed [S019] | claimed [S019] | unknown [S019] | unsupported [S019] | claimed [S019] | claimed [S019] | claimed [S019] | unknown [S019] |
| H01 Graphify | unknown [S021] | claimed [S021] | unknown [S021] | unknown [S021] | unknown [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | unknown [S021] | claimed [S021] | claimed [S021] | claimed [S021] | claimed [S021] | unknown [S021] |
| H02 UA 双层图 | unknown [S009] | claimed [S009] | unknown [S009] | unknown [S009] | unknown [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | unknown [S009] | claimed [S009] | claimed [S009] | claimed [S009] | claimed [S009] | unknown [S009] |
| H03 LLM-Wiki | unsupported [S022] | unsupported [S022] | unsupported [S022] | unsupported [S022] | unsupported [S022] | claimed [S022] | claimed [S022] | verified [S022] | verified [S022] | verified [S022] | claimed [S022] | verified [S022] | verified [S023] | claimed [S022] | claimed [S022] | claimed [S022] | verified [S022] | verified [S022] | claimed [S022] | unknown [S022] | claimed [S022] | verified [S023] |
| H04 RepoMem | unsupported [S028] | unsupported [S028] | unsupported [S028] | unsupported [S028] | unsupported [S028] | unknown [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | claimed [S028] | verified [S028] | claimed [S028] | claimed [S028] | unknown [S028] | claimed [S028] | verified [S028] |
| H05 GitHub Memory | unsupported [S025] | unsupported [S025] | unsupported [S025] | unsupported [S025] | unsupported [S025] | claimed [S025] | verified [S025] | verified [S025] | verified [S025] | verified [S025] | verified [S025] | verified [S025] | claimed [S025] | claimed [S025] | claimed [S025] | claimed [S025] | verified [S025] | verified [S025] | claimed [S025] | unknown [S025] | claimed [S025] | verified [S025] |
| H06 渐进式 Skills | unsupported [S024] | unsupported [S024] | unsupported [S024] | unsupported [S024] | unsupported [S024] | claimed [S024] | claimed [S024] | claimed [S024] | claimed [S024] | claimed [S024] | claimed [S024] | claimed [S024] | claimed [S027] | claimed [S024] | claimed [S024] | claimed [S024] | verified [S027] | verified [S027] | claimed [S024] | unknown [S024] | claimed [S024] | verified [S027] |
| H07 任务规格/规则包 | unsupported [S026] | unsupported [S026] | unsupported [S026] | unsupported [S026] | unsupported [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | claimed [S026] | verified [S026] | verified [S026] | claimed [S026] | unknown [S026] | claimed [S026] | verified [S026] |

## 3. 完整方案硬门槛

一个完整候选架构必须在设计上容纳以下三项能力；“以后可以补”只有在补充层、稳定接口和失效行为已经写清时才算容纳：

1. **Target-specific compilation view**：代码实体必须绑定真实编译命令、宏集、revision 和 Target；共享源码在不同 Target 下是不同 occurrence。[S010–S012]
2. **可定位源码证据**：事实和领域声明必须能回到 revision、Target、文件、行范围与生成器；结果不能只给摘要或相似度。[S025][S029]
3. **不确定性治理**：规则、LLM 或 embedding 产生的链接必须与确定性代码事实分层，并记录 provenance、confidence/review status、冲突、失效和重验证。[S021–S025][S029]

组件不必单独满足全部硬门槛。例如词法检索可以是优秀组件，但不能据此被称为完整知识架构。

## 4. 候选分层

### 4.1 排除为“完整方案”

| 对象 | 排除理由 | 仍可借鉴 |
|---|---|---|
| 纯词法、纯向量、RepoMap | 不提供 Target-specific 程序关系或领域声明生命周期；近期检索研究也没有支持单一检索族全面领先。[S001–S004] | exact-match、语义召回、预算化上下文排序 |
| 单独使用 Tree-sitter 结构图 | 项目材料未证明真实编译宏、函数指针、CFG/dataflow 和多 Target occurrence。[S006–S009] | 低成本导航、增量索引、MCP 查询 |
| GitNexus 直接采用 | PolyForm Noncommercial 限制预期采用，同时 C/C++ import 能力与独立效果数据不足。[S008] | allowlist、只读 MCP、cluster/process 多尺度导航 |
| CodeQL 作为默认开放核心 | 查询库开放，但引擎/CLI 许可边界不等同于可自由再分发的开源分析内核。[S013] | 查询语言、路径解释和 Benchmark oracle |
| LLM/embedding 直接写确定性事实 | 近期结果显示盲目注入知识可显著伤害任务；未经验证的领域边必须允许拒绝和失效。[S023][S025][S027] | 候选生成、摘要、导航入口 |

### 4.2 架构参考

- **Kythe/SCIP**：稳定身份、交叉引用和 Target/revision 建模参考；不承担深层数据流。[S011][S012]
- **Understand Anything/Graphify**：确定性结构与推断领域边分层、claim/source 类型参考；准确率和 C 编译语义保持 unknown。[S009][S021]
- **GitHub Memory、LLM-Wiki、RepoMem**：引用、反馈、刷新、跨会话记忆和按需重验证参考；不能替代代码分析。[S022][S025][S028]
- **CodeQL**：声明式语义查询和解释路径参考；不默认进入开放核心。[S013]

### 4.3 组件候选

- 编译事实与源码语义：Clang/LLVM；身份交换：SCIP 或 Kythe。[S010–S012]
- 联合图查询：Joern、Fraunhofer CPG；二者均需验证真实 Target 输入和函数指针行为。[S015][S016]
- 按需深分析：SVF、PhASAR、Frama-C；许可证、IR 映射和成本分别进入 Benchmark。[S017][S018][S020]
- 轻量导航：Codebase-Memory、CodeGraph；词法、向量和 RepoMap 作为互补检索。[S001–S007]
- 规则和知识交付：Semgrep CE、版本化领域断言、渐进式 Wiki/Skill；不得覆盖编译事实。[S019][S022–S027]

### 4.4 完整架构短名单

这三个对象是待验证的**架构族**，不是已经证明的产品组合：

| 编号 | 架构族 | 满足硬门槛的设计方式 | 主要 unknown |
|---|---|---|---|
| L1 | 编译器原生分层架构 | Target registry + compilation database；Clang/SCIP/Kythe 提供身份与源码证据；按需接 LLVM/SVF/PhASAR/Frama-C；独立 assertion 层治理领域链接。[S010–S012][S017][S018][S020][S029] | 构建接入成本、跨层 ID、增量和 Agent 查询成本 |
| L2 | Target-specific CPG 分层架构 | 每 Target/revision 独立构图；Joern 或 Fraunhofer CPG 只存代码事实；领域断言与 provenance 独立；深分析器按缺口补充。[S014–S018][S029] | frontend 对真实宏、函数指针和共享源码 occurrence 的正确性 |
| L3 | 轻量结构发现 + 编译器核验架构 | Codebase-Memory/CodeGraph 提供低成本发现；所有强语义结论通过 compiler/deep provider 核验；领域层只保存带状态的链接。[S005–S007][S010][S021–S025] | 双系统一致性、核验命中率、延迟与维护复杂度 |

当前证据不足以在 L1–L3 中确定唯一方案。开源优先只在证据未显示决定性效果、正确性或运维差异时作为 tie-break；它不是对性能的替代判断。下一轮实验必须先验证硬门槛，再比较成本与 Agent 效果。

## 5. 明确保留的 unknown

1. 四个 WiFiDemo Target 的 compdb 是否完整且可重复；
2. Joern、Fraunhofer CPG、Clang/LLVM 和轻量结构图对宏分支、函数指针、ops 表的实际 precision/recall；
3. 代码稳定 ID 跨 revision 的保留率与误链接率；
4. 领域链接在改名、移动、宏变化和 Target 删除后的失效/修复质量；
5. 不同检索组合对最终 Agent 正确率、证据完整率和 abstention 的影响；
6. 全量索引、增量更新、常驻磁盘/内存、查询 P95 与上下文 Token 成本；
7. 各依赖、模型权重、服务端组件和再分发路径的最终许可证审计。
