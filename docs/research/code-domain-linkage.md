# 代码与领域知识链接机制调研

日期：2026-08-14
状态：Task 5 研究产物；不构成最终架构选型

## 1. 问题边界

本文件回答 RQ4–RQ6：Feature、Flow、Event、Protocol Rule、设计原因和 Known Edge Case 如何链接到当前 revision、当前 Target 下的代码事实；链接如何双向导航、携带 provenance/confidence、处理冲突，并在代码或知识变化后失效和重新验证。

“同一数据库中同时出现代码和文档”不等于两者已经建立可靠链接。链接至少是一条可独立审计的 assertion，并且必须区分：

- 代码事实：编译器、Parser 或分析器在特定输入上产生的结果；
- 领域声明：规范、设计文档、人工经验或历史变更表达的含义；
- 链接声明：某领域实体与某代码 occurrence/分析事实之间的 typed edge；
- 查询候选：embedding、LLM 推断或启发式规则推荐的待核验关系。

## 2. 建议使用的最小实体集合

| 实体 | 最小身份 | 作用 |
|---|---|---|
| `Repository` | canonical repo ID | 隔离同名文件和多仓来源 |
| `Revision` | commit ID；可附 SWHID revision ID | 冻结一次可重现的源码状态 [S029] |
| `SourceArtifact` | repo + revision + path + content digest/SWHID | 表达文件内容，不把路径当永久身份 |
| `TargetProfile` | target name + toolchain + macro/include/flags digest | 表达真实编译视角 |
| `CodeEntity` | frontend namespace + semantic symbol ID/signature | 表达函数、类型、变量等语义实体 |
| `TargetOccurrence` | CodeEntity + TargetProfile + TU + source span | 表达同一源码在某 Target 中实际存在的 occurrence |
| `AnalysisFact` | kind + inputs + generator/version/config digest | 表达 call、may-call、CFG、dataflow、slice 等结果 |
| `DomainEntity` | namespace + stable domain ID | 表达 Feature、Flow、Event、Protocol、Rule、Document |
| `Assertion` | assertion ID + subject + typed edge + object | 把领域实体、代码 occurrence 和分析事实连接起来 |
| `Evidence` | content/revision ID + locator + quote/digest | 说明 assertion 的依据 |
| `ValidationActivity` | validator + version + time + inputs + result | 支持 verified/inferred/manual 状态与重新验证 |

SWHID 的 intrinsic content/revision ID、Kythe 的 VName/anchor、SCIP occurrence 和 SARIF 的 revision/location/fingerprint 可作为身份与交换设计参考，但没有单一标准同时解决符号重命名和多 Target occurrence。[S011][S012][S029]

## 3. 规范链接链

```text
DomainEntity(Feature | Flow | Event | Protocol | Rule | Document)
  -> Assertion(edge_type, provenance, confidence, review_state)
  -> TargetOccurrence(repository, revision, target, TU, semantic ID, file-line)
  -> AnalysisFact(kind, generator, version, configuration)
  -> Evidence(source span | spec clause | test | path | slice)
  -> ValidationState(candidate | verified | contradicted | stale | invalid)
```

领域实体不应直接连接裸函数名。最短可靠落点是当前 revision/Target 中的 `TargetOccurrence`；如果链接依据是调用路径或数据流，则落点还应包含产生该路径的 `AnalysisFact`。

## 4. 链接分类法

### 4.1 横向比较

| 链接方式 | 典型粒度与产生者 | 双向导航 | provenance / confidence | 冲突处理 | 失效与重新验证 |
|---|---|---|---|---|---|
| 稳定代码实体 ID | compiler/indexer 的 Function/Type/Symbol；SCIP/Kythe/SWHID 参考 | 强：symbol→refs 和 occurrence→symbol | generator/version/semantic ID；通常为 `verified-code` | 同 ID 不同 definition 视为 identity conflict | revision 或 frontend schema 变化时重新索引；rename 需基于新旧语义/内容映射 |
| Target occurrence | compiler command + TU + macro/include digest + source span | 强：Target→occurrence→symbol，也可反查哪些 Target 包含它 | exact compile input；不使用模糊 confidence | 不同 Target 的相反事实可同时成立，不互相覆盖 | command digest、源内容、依赖头变化即失效并重建 |
| 显式 typed edge | `implements_feature`、`produces_event`、`constrained_by`、`explained_by` | 强：索引 subject/object 两端 | edge rule、author、evidence、review state | 按事实类型而非全局单一优先级裁决 | 任一端 revision、rule version 或 evidence digest 变化时进入 stale |
| 文档 symbol/file-line 引用 | 文档、ADR、规范中的 symbol、path、line/range | 中：需要解析 citation 并建反向索引 | document revision、locator、quoted digest | citation 与当前源码矛盾时标 contradicted | 行号移动先用 quoted digest/AST anchor 修复，失败则人工复核；裸 file-line 不可静默漂移 |
| 命名/目录/宏规则 | 规则引擎依据路径、prefix、宏、注册表 | 中：可从 rule 与匹配 occurrence 双向查询 | rule ID/version、match trace；`rule-derived` | 与 compiler fact 冲突时 compiler 决定“代码是否存在”；人工/规范决定“领域含义是否成立” | source/Target/rule digest 改变即重跑；结果必须保留旧新差异 |
| embedding 相似度 | 文档块↔代码摘要、概念↔symbol 的近邻 | 弱：可保存双向候选，但不是语义边 | model/version/chunk/query/score/top-k；`inferred-candidate` | 不参与覆盖 verified/manual assertion，只生成候选或排序 | 任一内容、embedding model、chunker 变化时失效；必须重新计算并重新阈值校准 |
| LLM 推断 | 模型从代码、文档、历史生成实体和关系 | 中：若输出结构化 edge 可双向查 | model/prompt/input digests/evidence set/confidence；`inferred` | 与原始资料或代码证据冲突时降级/拒绝；模型不能自行宣布 verified | 输入或模型/prompt 变化即 stale；通过规则、源码、测试或人工重新验证 |
| 人工映射 | 专家把 Feature/Flow/Rule 映射到 occurrence/path | 强：结构化保存后天然双向 | author/reviewer/time/reason/evidence；`manual-reviewed` | 对领域意图可高于模型/启发式，但不能覆盖当前编译事实 | 依赖的 revision/Target/evidence 变化时通知 owner；必须显式确认、修复或废弃 |

### 4.2 为什么 `file-line` 不能单独作为长期身份

GitHub memory 的公开设计证明 `file:line` citation 适合低成本读时核验：使用 memory 前读取当前 branch 的引用位置，若内容矛盾或位置不存在，就写入修正版。[S025] 但长期知识系统还需要：

1. 保存 citation 创建时的 revision 与引用内容 digest；
2. 以 semantic ID 或 AST/source anchor 辅助行号移动修复；
3. 把修复视为新的 validation activity，不能悄悄改写历史 assertion；
4. 对多 Target 源文件，citation 必须落到 Target occurrence，而不是只落到文件。

### 4.3 typed edge 的事实强度

建议每条 edge 同时保存 `edge_type` 和 `epistemic_status`，避免把关系名称与可信程度混为一谈：

| 状态 | 含义 | 可否直接回答 Agent |
|---|---|---|
| `verified-code` | 当前 revision/Target 上由确定性工具重建并通过一致性检查 | 可以，但需返回 source evidence |
| `verified-domain` | 权威规范或经审核人工声明，且证据仍有效 | 可以，同时说明适用范围 |
| `manual-reviewed` | 专家确认，但未形成可执行证明 | 可以，标明 reviewer 与更新时间 |
| `rule-derived` | 可重复规则产生，规则前提可能不完整 | 可以作为解释性事实，必须返回 rule trace |
| `inferred` | LLM 生成且有 evidence，但尚未独立确认 | 只能作为候选或调查线索 |
| `inferred-candidate` | embedding/聚类/名称相似 | 只能用于检索排序 |
| `contradicted` | 当前证据与 assertion 冲突 | 不得作为正面答案；应暴露冲突 |
| `stale` | 输入改变，尚未重新验证 | 默认不作为事实；可以提示历史线索 |
| `invalid` | 已证伪或作用域错误 | 保留审计，不参与正常检索 |

## 5. provenance 与知识生命周期

### 5.1 Assertion 最小字段

```yaml
assertion_id: domain-link:<uuid>
subject: domain:<namespace>:<id>
predicate: implements_feature | participates_in_flow | produces_event | constrained_by | explained_by
object: occurrence:<repo>:<revision>:<target>:<semantic-id>:<span>
status: inferred | rule-derived | manual-reviewed | verified-domain | verified-code
generator:
  kind: parser | analyzer | rule | llm | embedding | human
  name: <tool-or-author>
  version: <version>
inputs:
  repository_revision: <commit>
  target_profile_digest: <digest>
  source_artifact_digest: <digest>
  rule_or_prompt_digest: <digest>
evidence:
  - kind: source-span | spec-clause | test | path | slice | document
    locator: <stable-id-and-file-line>
confidence:
  kind: exact | calibrated-score | ordinal | none
  value: <optional>
review:
  reviewer: <optional>
  validated_at: <timestamp>
  valid_for: <revision-or-range>
invalidation:
  state: active | stale | contradicted | invalid
  caused_by: <optional event>
```

W3C PROV-O 的 Entity/Activity/Agent、generation/derivation/revision/invalidation 可作为 provenance 语义参考；不要求最终一定采用 RDF。[S029]

### 5.2 失效事件

| 事件 | 受影响对象 | 默认动作 |
|---|---|---|
| source content digest 改变 | file-line、occurrence、分析路径和人工链接 | 精确 dependency closure 标 stale；重建代码事实 |
| compile command/Target digest 改变 | 该 Target 下全部 occurrence 与分析事实 | 整个 Target snapshot 失效，不传播到其他 Target |
| symbol rename/move | semantic ID、文档 citation、人工映射 | 尝试 content/AST/rename map；保留旧 assertion 并生成 replacement |
| analyzer/version/config 改变 | 该 generator 产生的 AnalysisFact | 并行生成新版本；差异视为 evidence conflict |
| domain document/spec revision 改变 | derived rule、Skill、Wiki page、领域 edge | 按 source reference 反向找到 assertions，进入重新验证队列 |
| embedding/model/prompt 改变 | 全部软链接 | 批次作废重算，不能沿用旧 score |
| human correction | 被否定或替代的 assertion | 保存 supersedes/contradicts，不物理删除审计历史 |

### 5.3 冲突优先级不是单一总排序

必须先判断冲突发生在哪个维度：

- “某函数是否在 Target 中存在”：当前 compiler/indexer fact 高于目录规则、LLM 和人工猜测。
- “某协议应当如何工作”：适用版本的权威规范高于代码现状；代码不一致可能代表缺陷，而不是规范错误。
- “项目为何采用某设计”：经审核 ADR/人工声明高于从代码形状推断的理由。
- “某调用是否可能发生”：sound may-analysis 与 observed runtime trace 可以同时保留；二者语义不同，不互相覆盖。
- “旧经验是否仍适用”：当前 revision 的验证结果高于历史 memory；历史仍可作为候选定位依据。

GitHub 的 citation-backed just-in-time verification 是轻量实现参考；LLM-Wiki 的 source archive、双向 wikilink 和 Error Book 是批量编译/修复参考；WiCER 表明必须用失败 probe 检测被编译 Wiki 丢掉的事实。[S022][S023][S025]

## 6. 混合方案的同题比较

### 6.1 Graphify

- **Function→Feature/Flow/Event/Rule/Document**：AST node 经 `EXTRACTED` 代码边，再经 `INFERRED` 文档/语义边到文档或概念；WHY/ADR/RFC 可成为节点。[S021]
- **领域概念→当前源码**：可反向遍历 typed graph 并返回 `file:line`，但公开设计没有 Target occurrence 或 revision-qualified domain edge。
- **产生者**：代码边由 Tree-sitter；文档/跨源边由 LLM；无法消歧的关系为 `AMBIGUOUS`。
- **移动/重命名修复**：支持 changed-file update/Git hook；未公开领域边修复 precision，也没有证明 semantic rename continuity。
- **冲突优先级**：至少在标签上区分 EXTRACTED/INFERRED/AMBIGUOUS，但未公开人工 assertion、规范权威级别和 stale 状态的完整裁决。
- **判断**：值得借鉴边 provenance 和混合图 UX；不能直接作为 Target-aware C 事实底座。

### 6.2 Understand Anything

- **Function→领域知识**：从确定性代码结构出发，由多个 Agent 生成 architecture/process/convention/specification artifacts [S009]。
- **领域概念→当前源码**：生成文档可引用代码，但公开材料未证明 stable symbol/occurrence ID 和当前 Target 反查。
- **产生者**：代码基础结构与 LLM 生成知识混合；模型、prompt、证据和审核字段的公开治理不足。
- **移动/重命名修复**：可以重新生成，但未公开 assertion-level invalidation/repair。
- **冲突优先级**：缺少可核验的 manual/LLM/parser 三方冲突模型。
- **判断**：可借鉴“先生成可读知识资产再供 Agent 使用”，不能把生成页面当 verified code fact。

### 6.3 LLM-Wiki

- **Function→领域知识**：原论文对象是文档而非代码；迁移到代码场景需把 CodeEntity 作为 page/alias/tag，并保留 source reference。
- **领域概念→当前源码**：双向 wikilink 支持反查，但必须把源码 anchor/Target occurrence 作为外部确定性实体接入。[S022]
- **产生者**：LLM 编译页面和语义 link；deterministic validator 检查结构，source-grounded LLM 检查内容。
- **移动/重命名修复**：增量 compilation + Error Book 可修复 dangling link、malformed ref 和 contradiction；未原生解决 Git rename/Target。
- **冲突优先级**：source archive 是最终审计依据，Error Book 记录 open/closed 约束；仍需当前代码工具重新验证。
- **判断**：适合组织 Feature/Flow/规范叙事层，不应承担编译事实层。

### 6.4 WiCER 式编译 Wiki

- **Function→领域知识**：不规定实体链接；重点是 compiled artifact 是否丢失回答所需事实。
- **领域概念→当前源码**：需要另外的 source/occurrence anchor；probe 必须覆盖双向问题。
- **产生者**：LLM compiler；失败 probe、诊断和约束驱动后续重新编译。[S023]
- **移动/重命名修复**：输入变化或 probe 失败触发重新编译；旧 Wiki 不能无条件沿用。
- **冲突优先级**：raw sources 保持真源；Wiki 是有损派生物。
- **判断**：最值得借鉴的是 compile→evaluate→refine，而不是 KV cache 这一特定服务方式。

### 6.5 RepoMem

- **Function→领域知识**：历史 issue/commit 提供类似问题和过往修改；semantic memory 提供活跃文件摘要。[S028]
- **领域概念→当前源码**：memory 先推荐文件/commit，再由 LocAgent 在当前代码结构中验证；不是直接持久 typed domain edge。
- **产生者**：Git 历史、BM25/摘要与 Agent 检索。
- **移动/重命名修复**：历史 commit 固定不变；当前代码是否仍适用由实时探索验证。
- **冲突优先级**：当前代码应高于历史 memory；稀疏/不相关历史造成 `others` Acc@5 -13.1 points，说明必须允许 abstain。
- **判断**：历史经验是检索线索，不是当前事实；适合补充“为什么这样改过”。

### 6.6 GitHub Copilot Repository Memory

- **Function→领域知识**：memory 保存 subject/fact/reason 和多个源码 citations，可表达跨文件同步规则。[S025]
- **领域概念→当前源码**：通过 citations 回到位置；当前公开 retrieval 以近期 repository memories 为主。
- **产生者**：Agent 在任务/Review 中调用 memory tool；repository contributor 权限约束写入来源。
- **移动/重命名修复**：读时检查 citation；失效或矛盾则生成 corrected memory，核验通过则刷新 timestamp。
- **冲突优先级**：当前 branch 源码证据高于 memory；memory 只在实时验证后使用。
- **判断**：是最直接的 citation-backed、read-time validation 工业参考；仍缺 Target 和 typed domain schema。

### 6.7 Progressive Skills / References / MCP

- **Function→领域知识**：代码/领域索引先选相关 Skill metadata，再按需加载 instructions 和 reference；需要事实时调用 MCP/CLI。[S024]
- **领域概念→当前源码**：Skill 必须显式规定查询工具和 Target 参数；Skill 本身不应复制整份代码事实。
- **产生者**：人工/团队编写 Skill 和 reference；deterministic script/MCP 产生运行时事实。
- **移动/重命名修复**：Skill 应引用 domain ID/query，不硬编码 file-line；版本变化需独立测试 Skill。
- **冲突优先级**：当前工具结果高于 Skill 中缓存的代码描述；版本不匹配 Skill 可降低通过率。[S027]
- **判断**：适合把稳定程序、检查清单和领域导航方式放在 Skill；原始规范留在 reference，代码事实按需查询。

### 6.8 Codified Context

- **Function→领域知识**：always-loaded constitution 提供全局约束，trigger 选择 domain agent，MCP 检索 cold specifications。[S030]
- **领域概念→当前源码**：主要依赖文档/agent instructions，缺少稳定 code occurrence 机制。
- **产生者**：人工架构指导下由 Agent/开发者维护三层文档。
- **移动/重命名修复**：把文档当 living specification，但公开项目没有 assertion-level invalidation。
- **冲突优先级**：constitution/agent/spec 的重叠是有意的，但缺少机器可检查冲突裁决。
- **判断**：支持 hot/cold 分层的工程可行性，不提供因果效果或成熟链接模型。

### 6.9 已登记的活跃结构图同类项目

Codebase-Memory、CodeGraph 和 GitNexus 已在 R04–R06 登记，不重复建立档案。[S005–S008]

- **Function→领域知识**：三者首先提供 parser/结构图导航；公开材料没有证明外部 Feature/Flow/Protocol assertion 是一等对象。
- **领域概念→当前源码**：可利用 search/trace/community 作为候选入口，但缺少 revision-qualified Target occurrence 反查。
- **产生者**：Tree-sitter/解析规则为主，community/summary 等可能包含算法或模型推断；各类边需继续拆分 provenance。
- **移动/重命名修复**：项目具有重建或增量能力，但没有公开代码—领域边 repair precision/recall。
- **冲突优先级**：当前 schema 重点是代码结构，不是人工领域 assertion、权威规范与模型推断的冲突治理。
- **判断**：保留为代码证据/导航层候选；Graphify 在公开材料中对 EXTRACTED/INFERRED/AMBIGUOUS 和文档节点的说明更直接，但同样没有解决 Target identity。

## 7. 领域知识注入的效果边界

### 7.1 相邻电信数据

SWE-Bench 5G 的 50 项 paired A/B 是当前最接近本项目的公开证据：平均约 350-token 的 3GPP context 使 Claude Sonnet 4 resolve 从 24% 到 30%，平均 Token +12%；对 policy authorization/control/session management 三类规格依赖任务提升 +16.7 至 +25 points，而六类 generic nil/crash 防御任务全部为 0。[S026]

这只能支持以下条件性结论：

- 权威规格与任务真正匹配时，简短领域资料可能改善修复；
- 通用代码缺陷不应默认加载协议规范；
- “链接到哪一条规范”比“提供更多规范”更关键；
- 后续 WiFi Benchmark 必须按 specification-dependent 与 generic bug 分层。

### 7.2 Skill 的负收益

SWE-Skills-Bench 的约 565 个任务中，39/49 Skills 没有 pass-rate 提升，平均仅 +1.2%；3 个版本不匹配 Skill 最多降低 10%，Token 在结果不变时最高增加 451%。[S027] 因此 Skill selection、version compatibility、任务适配与执行式 verifier 必须是一等组件。

### 7.3 Wiki 与 Memory 的负收益

- WiCER：长上下文在 80 文档时因 attention dilution 低于 RAG，blind Wiki 编译又会因信息丢失出现 53–60% catastrophic rate。[S023]
- LLM-Wiki：结构化 Wiki 强于多文档综合，但单文档细节问题比 HippoRAG 2 低 2.3 points；dangling link 是主要错误类别。[S022]
- RepoMem：历史丰富仓的定位通常提升，历史稀疏 `others` 分组反而从 67.4% 降至 54.3%。[S028]

因此所有领域上下文机制都必须支持 `abstain/not-applicable`，并保留回到原始代码/资料的路径。

## 8. WiFi MAC 的链接模板

### 8.1 Feature

```text
Feature(host_tx_offload)
  --enabled_for [manual-reviewed/rule-derived]--> TargetProfile(chip8-wifi-host)
  --implemented_by [verified-domain]--> TargetOccurrence(function/member/macro)
  --evidenced_by--> CompileFact(macro defined) + SourceSpan + BuildArtifact
```

Feature 与 Target 的适用性可以来自构建配置/人工规则；Feature 与具体代码的链接必须进一步落到 Target occurrence，不能因目录名或函数名相似直接 verified。

### 8.2 Flow

```text
Flow(host_to_device_tx)
  --has_step--> FlowStep(send_event)
  --realized_by [manual-reviewed]--> TargetOccurrence(...)
  --supported_by--> AnalysisFact(call/dataflow/path)
  --constrained_by--> ProtocolRule(...)
```

人工可定义 Flow 的业务步骤，分析器只证明某次配置下存在的代码关系；二者不应合并成一类边。

### 8.3 Event

```text
Event(EVENT_ID)
  --declared_at--> TargetOccurrence(enum/define)
  --produced_by--> TargetOccurrence(sender)
  --consumed_by--> TargetOccurrence(handler registration)
  --may_dispatch_to--> AnalysisFact(function-pointer candidates)
```

`produced_by`、`registered_to` 和 `may_dispatch_to` 语义必须分开；函数指针候选不能冒充唯一 handler。

### 8.4 Protocol Rule / Known Edge Case

```text
ProtocolRule(rule-id, spec-version, clause)
  --constrains--> DomainEntity(Event/Flow/Field)
  --checked_by--> Test/StaticRule/FormalProperty
  --observed_violation_at--> TargetOccurrence
KnownEdgeCase
  --derived_from--> Issue/Commit/TestFailure
  --relevant_to [inferred/manual-reviewed]--> CodeEntity/TargetOccurrence
```

规范规则与当前实现冲突时，应产出 potential defect，而不是自动把规范 assertion 作废；历史 Edge Case 必须在当前 Target 上重新验证。

## 9. 后续 Benchmark 问题

| ID | 问题 | Gold/干预 | 指标 |
|---|---|---|---|
| DL01 | symbol/file-line、semantic ID、content anchor 哪种在 rename/move 后修复最好 | 人工构造 rename/move commits | repair precision/recall、错误重连率 |
| DL02 | 四 Target 中同一源码的领域边是否串扰 | W01–W04 的 Target gold | Target precision/recall、cross-target leakage |
| DL03 | 命名/目录/宏规则能否发现 Feature/Event 链接 | 人工审核 rule matches | precision/recall、abstention |
| DL04 | embedding/LLM 候选是否减少人工工作且不污染 verified facts | blind review candidates | review yield、false promotion rate、Token |
| DL05 | read-time citation verification 与 batch invalidation 哪种成本/正确性更好 | 修改源码/文档/Target 后查询 | stale-use rate、repair latency、reads/query |
| DL06 | 规格注入对 WiFi specification-dependent 与 generic task 的差异 | paired with/without concise spec | resolve delta、Token delta、negative-transfer rate |
| DL07 | compiled Wiki 是否遗漏关键宏/例外/设计原因 | diagnostic probes + raw-source gold | answer quality、catastrophic loss、recovery iterations |
| DL08 | 历史 memory 在丰富/稀疏/过期历史下何时应 abstain | 时间切分 issue/commit 集 | localization Acc@k、negative transfer、age calibration |
| DL09 | 冲突来源能否被暴露而非静默覆盖 | 故意注入错误 manual/LLM/rule assertions | conflict recall、wrong-answer rate |

## 10. Task 5 阶段性结论

1. 领域知识应与代码事实分层存储或至少分层标注；物理上是否同库不是首要问题。
2. 确定性链接的核心不是裸 symbol，而是 repository + revision + TargetProfile + semantic entity + source occurrence。
3. typed edge 必须是一等 assertion，携带 generator、inputs、evidence、provenance、confidence、review 和 invalidation 状态。
4. embedding 和 LLM 推断适合候选发现与检索排序，不得自动升级为 verified code/domain fact。
5. 原始资料、编译 Wiki、Skill、memory 和分析结果具有不同更新周期；任何派生知识都必须能回到原始资料和当前源码。
6. 读时 citation verification、批量 dependency invalidation 和失败 probe 驱动的 Wiki refinement 是互补机制。
7. 近期数据反复显示 negative transfer：错误/过期 Skill、稀疏历史 memory、过长上下文和盲目 Wiki 压缩都可能降低效果。
8. 当前阶段仍不决定使用单一图、关系库、文件 Wiki 或混合存储；Task 6 将只按证据和硬门槛分类候选。
