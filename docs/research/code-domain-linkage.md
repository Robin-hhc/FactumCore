# 代码与领域知识链接机制调研

日期：2026-08-14
状态：Task 5 研究产物；不构成最终架构选型

## 1. 问题边界

本文件回答 RQ4–RQ6：Feature、Flow、Event、Protocol Rule、设计原因和 Known Edge Case 如何链接到当前 `repository_revision`、当前 Target 下的代码事实；链接如何双向导航、携带 provenance/confidence、处理冲突，并在代码或知识变化后失效和重新验证。

“同一数据库中同时出现代码和文档”不等于两者已经建立可靠链接。链接至少是一条可独立审计的 assertion，并且必须区分：

- 代码事实：编译器、Parser 或分析器在特定输入上产生的结果；
- 领域声明：规范、设计文档、人工经验或历史变更表达的含义；
- 链接声明：某领域实体与某代码 occurrence/分析事实之间的 typed edge；
- 查询候选：embedding、LLM 推断或启发式规则推荐的待核验关系。

## 2. 建议使用的最小实体集合

| 实体 | 最小身份 | 作用 |
|---|---|---|
| `Repository` | canonical repository ID | 隔离同名文件和多仓来源 |
| `RepositoryRevision` | repository ID + immutable code commit/SWHID revision ID | 冻结一次可重现的被分析源码状态 [S029] |
| `SourceArtifact` | repository ID + `repository_revision` + path + content digest/SWHID | 表达代码文件内容，不把路径当永久身份 |
| `TargetProfile` | target name + toolchain + macro/include/flags digest | 表达真实编译视角 |
| `CodeEntity` | frontend namespace + semantic symbol ID/signature | 表达函数、类型、变量等语义实体 |
| `TargetOccurrence` | CodeEntity + TargetProfile + TU + source span | 表达同一源码在某 Target 中实际存在的 occurrence |
| `AnalysisFact` | kind + inputs + generator/version/config digest | 表达 call、may-call、CFG、dataflow、slice 等结果 |
| `DomainEntity` | namespace + stable domain ID | 表达 Feature、Flow、Event、Protocol、Rule，以及原始领域来源 `Document` / `Specification` / `Issue` / `Test` / `Log` |
| `SourceRevision` | source stable ID + immutable `source_revision_id`/content digest | 来源注册：冻结某一原始领域来源版本，不把版本号写进领域实体身份 |
| `SourceLocation` | `source_revision_id` + locator/span + quoted digest | 领域来源注册：定位条款、段落或日志片段；可随领域来源版本变化重建，不承载代码位置 |
| `SourceRegistration` | source stable ID + `source_revision_id` + license + accessed_at | 来源注册：保存 `License`、`AccessedAt`、获取方式和适用限制；`source_revision_id` 外键关联 `SourceRevision` |
| `Assertion` | assertion ID + subject + typed edge + object | 以 `predicate_class` 和 `evidence[]` 把领域实体、代码 occurrence 和分析事实连接起来 |
| `Evidence` | evidence ID + `kind: code` 或 `kind: domain` | 判别联合；`CodeEvidence` 回到代码仓 revision/occurrence/artifact/span，`DomainEvidence` 回到领域 `SourceRevision`/`SourceLocation` |
| `ValidationActivity` | validator + version + time + inputs + result | 记录四级权限的产生、审核与重新验证活动 |

`Document`、`Specification`、`Issue`、`Test` 和 `Log` 是原始领域来源对象；`SourceRevision`、`SourceLocation`、`License` 和 `AccessedAt` 是其版本化来源注册信息。`SourceRegistration.source_revision_id` 与 `SourceLocation.source_revision_id` 必须外键关联 `SourceRevision.source_revision_id`，使领域材料版本可机器追溯；它们绝不能复用代码仓的 `repository_revision`。代码证据则必须通过 `RepositoryRevision`、`TargetOccurrence`、`SourceArtifact` 和代码 source span 定位，不能借用 `SourceRevision`/`SourceLocation`。Wiki、Skill 和 Memory 都是派生知识资产：只能以 stable ID 引用这些原始对象及其注册信息，不能替代它们成为无来源的事实根。SWHID 的 intrinsic content/revision ID、Kythe 的 VName/anchor、SCIP occurrence 和 SARIF 的 revision/location/fingerprint 可作为身份与交换设计参考，但没有单一标准同时解决符号重命名和多 Target occurrence。[S011][S012][S029]

## 3. 规范链接链

```text
DomainEntity / CodeEntity / TargetOccurrence / AnalysisFact
  -> Assertion(predicate_class, predicate, machine_status, evidence[], confidence, review_state)
       |-> CodeEvidence(kind=code)
       |     -> RepositoryRevision + TargetOccurrence + SourceArtifact + code source span
       |     -> optional AnalysisFact / build-artifact trace
       |-> DomainEvidence(kind=domain)
       |     -> SourceRevision + SourceLocation + quoted/content digest
       -> Lifecycle(active | stale | contradicted | invalid | superseded)
```

`Evidence` 是由 `kind` 判别的联合，不是一组同时必填的字段。`kind: code` 不得包含 `source_revision_id` 或 `SourceLocation`；`kind: domain` 不得把 `source_revision_id` 当成代码 revision。领域实体不应直接连接裸函数名。最短可靠代码落点是当前 `repository_revision`/Target 中的 `TargetOccurrence`；如果链接依据是调用路径或数据流，`CodeEvidence` 还应引用产生该路径的 `AnalysisFact`。

## 4. 链接分类法

### 4.1 横向比较

| 链接方式 | 典型粒度与产生者 | 双向导航 | provenance / confidence | 冲突处理 | 失效与重新验证 |
|---|---|---|---|---|---|
| 稳定代码实体 ID | compiler/indexer 的 Function/Type/Symbol；SCIP/Kythe/SWHID 参考 | 强：symbol→refs 和 occurrence→symbol | generator/version/semantic ID；`EXTRACTED` | 同 ID 不同 definition 视为 identity conflict | `repository_revision` 或 frontend schema 变化时重新索引；rename 需基于新旧语义/内容映射 |
| Target occurrence | compiler command + TU + macro/include digest + source span | 强：Target→occurrence→symbol，也可反查哪些 Target 包含它 | exact compile input；`EXTRACTED`，不使用模糊 confidence | 不同 Target 的相反事实可同时成立，不互相覆盖 | command digest、源内容、依赖头变化即失效并重建 |
| 显式 typed edge | `implements_feature`、`produces_event`、`constrained_by`、`explained_by` | 强：索引 subject/object 两端 | `RULE_DERIVED` 的 edge rule 或 `CURATED` 的 author/reviewer，以及 evidence | 按事实类型而非全局单一优先级裁决 | 任一端 `repository_revision`、rule version 或 evidence digest 变化时进入 stale |
| 文档 symbol/file-line 引用 | 文档、ADR、规范中的 symbol、path、line/range | 中：需要解析 citation 并建反向索引 | 文档侧 `DomainEvidence` 的 `source_revision_id`/locator/quoted digest，加代码侧 `CodeEvidence` 的 `repository_revision`/occurrence/artifact/span | citation 与当前源码矛盾时标 contradicted | 行号移动先用 quoted digest/AST anchor 修复，失败则人工复核；裸 file-line 不可静默漂移 |
| 命名/目录/宏规则 | 规则引擎依据路径、prefix、宏、注册表 | 中：可从 rule 与匹配 occurrence 双向查询 | rule ID/version、match trace；`RULE_DERIVED` | 与 compiler fact 冲突时 compiler 决定“代码是否存在”；人工/规范决定“领域含义是否成立” | source/Target/rule digest 改变即重跑；结果必须保留旧新差异 |
| embedding 相似度 | 文档块↔代码摘要、概念↔symbol 的近邻 | 弱：可保存双向候选，但不是语义边 | model/version/chunk/query/score/top-k；`INFERRED_CANDIDATE` | 不参与覆盖 `EXTRACTED`/`CURATED` assertion，只生成候选或排序 | 任一内容、embedding model、chunker 变化时失效；必须重新计算并重新阈值校准 |
| LLM 推断 | 模型从代码、文档、历史生成实体和关系 | 中：若输出结构化 edge 可双向查 | model/prompt/input digests/evidence set/confidence；`INFERRED_CANDIDATE` | 与原始资料或代码证据冲突时拒绝作为事实；模型不能自行升级 | 输入或模型/prompt 变化即 stale；通过规则、源码、测试或人工重新验证 |
| 人工映射 | 专家把 Feature/Flow/Rule 映射到 occurrence/path | 强：结构化保存后天然双向 | author/reviewer/time/reason/evidence；`CURATED` | 对领域意图可高于模型/启发式，但不能覆盖当前编译事实 | 依赖的 `repository_revision`/Target/evidence 变化时通知 owner；必须显式确认、修复或废弃 |

### 4.2 为什么 `file-line` 不能单独作为长期身份

GitHub memory 的公开设计证明 `file:line` citation 适合低成本读时核验：使用 memory 前读取当前 branch 的引用位置，若内容矛盾或位置不存在，就写入修正版。[S025] 但长期知识系统还需要：

1. 对代码位置保存 `CodeEvidence.repository_revision`、`SourceArtifact`、Target occurrence 与 anchor digest；对引用该位置的领域文档另存 `DomainEvidence.source_revision_id`、`SourceLocation` 与 quoted digest；
2. 以 semantic ID 或 AST/source anchor 辅助行号移动修复；
3. 把修复视为新的 validation activity，不能悄悄改写历史 assertion；
4. 对多 Target 源文件，citation 必须落到 Target occurrence，而不是只落到文件。

### 4.3 统一的机器可读断言权限

每条 edge 同时保存 `predicate` 与下列唯一的 `machine_status`，避免把关系名称、产生方式、审核结果和生命周期混为一谈。`stale`、`contradicted`、`invalid` 与 `superseded` 仅是 `lifecycle_state`，不是第五种事实权限。

| `machine_status` | 允许生产者 | 最小证据 | 可见范围 | 能否支持确定性回答 | 升级条件 | 失效行为 |
|---|---|---|---|---|---|---|
| `EXTRACTED` | 编译器、Parser、Indexer 或固定配置的确定性抽取器 | 按 predicate class：代码事实至少一个 `CodeEvidence`；领域原文的机械摘录至少一个 `DomainEvidence`。代码事实不要求、也不得伪造 `SourceRevision` | 对应输入范围内的代码结构/分析输出，或登记领域来源中直接明示的内容；不产生跨域语义 | 可以；答案必须返回相应 evidence kind 的 revision、位置与生成器 | 不以模型评分升级；代码—领域含义必须另建 `RULE_DERIVED`/`CURATED` assertion | 代码输入或领域来源各按自己的 revision/digest 失效；重建而非静默改写 |
| `RULE_DERIVED` | 已登记且版本化的确定性规则引擎；规则维护者可发布规则但不绕过证据要求 | 规则 ID/version、完整 match trace；代码规则需 `CodeEvidence`，领域规则需 `DomainEvidence`，跨域链接需两者 | 规则明示的 repository/`repository_revision`/Target 与领域范围 | 可以作为可复现的派生回答；必须返回 rule trace、作用域与 `evidence[]` | 经人工审核规则前提和边语义后可另建 `CURATED`；不得丢失原证据 | 任一实际依赖的代码输入、领域 `source_revision_id` 或规则版本变化时标为 `stale` 并重跑；保留新旧差异 |
| `INFERRED_CANDIDATE` | Agent、LLM、embedding、聚类、名称/目录启发式或未审核的外部建议 | 生成方法/version、prompt 或 query/input digest、候选 stable ID、实际使用的 `evidence[]`；缺少 predicate 所需 kind 时写入 `evidence_gaps` | 候选检索、人工审核队列和排序；不得混入确定性事实视图 | 不可以；只能回答为待核验线索并返回证据缺口 | 仅有具备项目授权的人类审核者，在补齐 predicate 所需 evidence kinds 后才能另建 `CURATED`；确定性工具也可独立产出 `EXTRACTED`/`RULE_DERIVED` | 模型、prompt、embedding、输入内容或阈值变化时批量标为 `stale`；不得复用旧分数作确认 |
| `CURATED` | 具备项目授权的人工领域维护者/审核者；可引用 `EXTRACTED`/`RULE_DERIVED`，但不能抹掉其证据 | 审核者、审核时间、理由；领域声明需 `DomainEvidence`，代码—领域链接同时需 `CodeEvidence` 与 `DomainEvidence` | 明示的代码 revision/Target（若涉及代码）与产品/规范/领域范围 | 可以；返回审核者、适用范围与 predicate 所需证据，且不能伪装成编译事实 | 后续人工审核只能建立 replacement/superseding assertion；Agent 无权升级 | 任一实际依赖的代码/Target、领域来源或人工纠正变化时标为 `stale`、`contradicted` 或 `superseded`；保留历史审计 |

Agent 只能创建 `INFERRED_CANDIDATE`，不能自行升级为 `EXTRACTED`、`RULE_DERIVED` 或 `CURATED`，也不能自行把候选写成确定性事实。LLM 不得直接写入确定性事实；embedding 不得直接写入确定性事实。确定性工具只能写入其输入范围内的 `EXTRACTED` 或 `RULE_DERIVED`，并不替代领域审核。

Graphify 的 `EXTRACTED`、`INFERRED` 和 `AMBIGUOUS` 是该来源项目对其图边的术语；本文只把它们记录为项目调研事实，不能覆盖、映射或扩展本研究上述四级权限。

## 5. provenance 与知识生命周期

### 5.1 `Evidence` 判别联合与 predicate/status 约束

```yaml
# CodeEvidence：代码事实的唯一位置证据；不含 SourceRevision/SourceLocation
evidence_id: evidence:<uuid>
kind: code
repository_id: <canonical-code-repository-id>
repository_revision: <immutable-code-commit-or-SWHID-revision-id>
target_occurrence_id: <target-qualified-occurrence-id>
source_artifact_id: <repository-revision-qualified-artifact-id>
source_span:
  path: <repository-relative-path>
  start_line: <positive-integer>
  end_line: <positive-integer>
  anchor_digest: <content-or-anchor-digest>
analysis_fact_id: <optional-analysis-fact-id>
build_artifact_trace: <optional-compiler-input-or-artifact-reference>
---
# DomainEvidence：领域来源的唯一位置证据；不把 source_revision_id 当代码 revision
evidence_id: evidence:<uuid>
kind: domain
source_id: <stable-domain-source-id>
source_revision_id: <immutable-domain-source-revision-or-content-digest>
source_location: <source-revision-id-plus-stable-locator>
quoted_digest: <quoted-content-digest>
```

最低证据由 `predicate_class × machine_status` 决定，而不是要求所有 assertion 都有领域 citation：

| `predicate_class` | 允许的确定性 `machine_status` | `evidence[]` 最低要求 | 禁止的偷换 |
|---|---|---|---|
| `code_fact`，如 `present_in_target`、`calls`、`may_call`、`has_cfg_edge` | `EXTRACTED` / `RULE_DERIVED` | 至少一个 `kind: code`；规则派生还需 rule trace | 不得为了满足 schema 伪造 `SourceRevision`/`SourceLocation`；领域引用不是代码 ground truth |
| `domain_statement`，如 `states_rule`、`documents_reason`、`records_edge_case` | `EXTRACTED` / `RULE_DERIVED` / `CURATED` | 至少一个 `kind: domain`；审核型声明另需 reviewer/reason | 不得把代码 commit 填进 `source_revision_id` |
| `code_domain_link`，如 `implements_feature`、`participates_in_flow`、`produces_event`、`constrained_by`、`explained_by` | `RULE_DERIVED` / `CURATED` | 至少一个 `kind: code` **且** 至少一个 `kind: domain` | compiler/parser 代码事实不能单独证明领域语义；因此不得把跨域链接写成 `EXTRACTED` |
| 任一 predicate 的待核验候选 | `INFERRED_CANDIDATE` | 保存实际使用的 code/domain evidence；缺少上述最低 kind 时必须在 `evidence_gaps` 中列出 | 缺口未补齐前不得进入确定性事实视图或升级 |

### 5.2 Assertion 最小字段

```yaml
assertion_id: domain-link:<uuid>
predicate_class: code_fact | domain_statement | code_domain_link
subject_stable_id: domain:<namespace>:<id>
predicate: implements_feature | participates_in_flow | produces_event | constrained_by | explained_by
object_stable_id: occurrence:<repository-id>:<repository-revision>:<target>:<semantic-id>:<span>
scope:
  repository_id: <required-only-when-code-is-in-scope>
  repository_revision: <required-only-when-code-is-in-scope>
  target_build_profile_scope: <required-only-when-target-qualified-code-is-in-scope>
  domain_scope: <optional-product/specification/domain-scope>
machine_status: EXTRACTED | RULE_DERIVED | INFERRED_CANDIDATE | CURATED
producer: <tool-or-authorized-human>
method_version: <parser/analyzer/rule/model/embedding/review-method-and-version>
evidence:
  - evidence_id: evidence:<code-uuid>
    kind: code
    repository_id: <canonical-code-repository-id>
    repository_revision: <immutable-code-commit-or-SWHID-revision-id>
    target_occurrence_id: <target-qualified-occurrence-id>
    source_artifact_id: <repository-revision-qualified-artifact-id>
    source_span: <path-plus-line-range-and-anchor-digest>
  - evidence_id: evidence:<domain-uuid>
    kind: domain
    source_id: <stable-domain-source-id>
    source_revision_id: <immutable-domain-source-revision-or-content-digest>
    source_location: <source-revision-id-plus-stable-locator>
    quoted_digest: <quoted-content-digest>
evidence_gaps: []
confidence:
  kind: exact | calibrated-score | ordinal | none
  value: <optional>
review:
  state: unreviewed | approved | rejected | superseded
  reviewer: <optional-authorized-human>
created_at: <timestamp>
validated_at: <timestamp-or-null>
lifecycle_state: active | stale | contradicted | invalid | superseded
invalidation:
  reason: <invalidation reason or null>
  caused_by: <optional-event-and-input-digest>
```

这里的 `predicate_class`、`subject_stable_id` / `object_stable_id`、`predicate`、`machine_status`、`producer`、`method_version`、`evidence[]`、`confidence`、`review.state`、`created_at` / `validated_at`、`lifecycle_state` 和 `invalidation.reason` 是 Assertion 最小字段；`scope` 内字段与所涉代码/领域范围条件必填。上例是 `code_domain_link`，所以同时展示两种 evidence；`code_fact` 只需 `CodeEvidence`，`domain_statement` 只需 `DomainEvidence`。`repository_revision` 只能标识被分析代码仓的不可变版本并出现在代码 scope/`CodeEvidence`；`source_revision_id` 只能关联领域来源注册并出现在 `DomainEvidence`。实现可以扩展字段，但不得重新合并这两个 revision 命名空间。

### 5.3 双向查询合同

下列查询是 A0/A1/B0/B1 共用的协议，而不是某个 Agent 的私有提示词；每个结果都必须返回 assertion ID、`machine_status`、`lifecycle_state` 与原始证据路径。

1. **从代码到领域：**给定 `TargetOccurrence`（`repository_id`、`repository_revision`、Target/build profile 和 occurrence stable ID），只查询具有匹配 `CodeEvidence`、仍为 `active` 的 `RULE_DERIVED` / `CURATED` `code_domain_link` assertion，返回关联的 `Feature`、`Flow`、`ProtocolRule`、`Event`，并分别返回其 code/domain `evidence[]`；`INFERRED_CANDIDATE` 只能作为可选“待审核候选”分组返回。纯 `EXTRACTED code_fact` 可作为链接的代码输入，但不会因被同次查询读到而自动获得领域语义。
2. **从领域到代码：**给定 `Feature` 或 `Event` stable ID、当前 `repository_id` / `repository_revision` 和 Target/build profile，只查询仍为 `active`、具有匹配 `CodeEvidence` 且 `DomainEvidence` 回到适用领域来源的 `code_domain_link`，返回当前有效 `TargetOccurrence`、两类证据、分析/规则 trace 和失效检查路径；没有匹配 occurrence 时明确返回“当前 Target 无有效代码证据”，不能回退为裸函数名或历史 Memory 的断言。

Host/Device 的二进制边界仍须经 `Event`/`Message` 断言连接；不得为了图遍历制造跨二进制的 `CALLS` edge。

W3C PROV-O 的 Entity/Activity/Agent、generation/derivation/revision/invalidation 可作为 provenance 语义参考；不要求最终一定采用 RDF。[S029]

### 5.4 失效事件

| 事件 | 受影响对象 | 默认动作 |
|---|---|---|
| source content digest 改变 | file-line、occurrence、分析路径和人工链接 | 精确 dependency closure 标 stale；重建代码事实 |
| compile command/Target digest 改变 | 该 Target 下全部 occurrence 与分析事实 | 整个 Target snapshot 失效，不传播到其他 Target |
| symbol rename/move | semantic ID、文档 citation、人工映射 | 尝试 content/AST/rename map；保留旧 assertion 并生成 replacement |
| analyzer/version/config 改变 | 该 generator 产生的 AnalysisFact | 并行生成新版本；差异视为 evidence conflict |
| domain document/spec `source_revision_id` 改变 | derived rule、Skill、Wiki page、领域 edge | 按 `source_revision_id` 反向找到 assertions，进入重新验证队列 |
| embedding/model/prompt 改变 | 全部软链接 | 批次作废重算，不能沿用旧 score |
| human correction | 被否定或替代的 assertion | 保存 supersedes/contradicts，不物理删除审计历史 |

### 5.5 冲突优先级不是单一总排序

必须先判断冲突发生在哪个维度：

- “某函数是否在 Target 中存在”：当前 compiler/indexer fact 高于目录规则、LLM 和人工猜测。
- “某协议应当如何工作”：适用版本的权威规范高于代码现状；代码不一致可能代表缺陷，而不是规范错误。
- “项目为何采用某设计”：经审核 ADR/人工声明高于从代码形状推断的理由。
- “某调用是否可能发生”：sound may-analysis 与 observed runtime trace 可以同时保留；二者语义不同，不互相覆盖。
- “旧经验是否仍适用”：当前 `repository_revision` 的验证结果高于历史 memory；历史仍可作为候选定位依据。

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
- **判断**：可借鉴“先生成可读知识资产再供 Agent 使用”，不能把生成页面当编译器产生的代码事实。

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
  --enabled_for [CURATED/RULE_DERIVED]--> TargetProfile(chip8-wifi-host)
  --implemented_by [CURATED; evidence[]=code+domain]--> TargetOccurrence(function/member/macro)
  --evidenced_by--> CodeEvidence(CompileFact + SourceArtifact/span + BuildArtifact trace)
```

Feature 与 Target 的适用性可以来自构建配置/人工规则；Feature 与具体代码的链接必须进一步落到 Target occurrence，不能因目录名或函数名相似直接成为确定性事实。

### 8.2 Flow

```text
Flow(host_to_device_tx)
  --has_step--> FlowStep(send_event)
  --realized_by [CURATED]--> TargetOccurrence(...)
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
  --relevant_to [INFERRED_CANDIDATE/CURATED]--> CodeEntity/TargetOccurrence
```

规范规则与当前实现冲突时，应产出 potential defect，而不是自动把规范 assertion 作废；历史 Edge Case 必须在当前 Target 上重新验证。

## 9. 后续 Benchmark 问题

| ID | 问题 | Gold/干预 | 指标 |
|---|---|---|---|
| DL01 | symbol/file-line、semantic ID、content anchor 哪种在 rename/move 后修复最好 | 人工构造 rename/move commits | repair precision/recall、错误重连率 |
| DL02 | 四 Target 中同一源码的领域边是否串扰 | W01–W04 的 Target gold | Target precision/recall、cross-target leakage |
| DL03 | 命名/目录/宏规则能否发现 Feature/Event 链接 | 人工审核 rule matches | precision/recall、abstention |
| DL04 | embedding/LLM 候选是否减少人工工作且不污染 `EXTRACTED`/`CURATED` assertion | blind review candidates | review yield、false promotion rate、Token |
| DL05 | read-time citation verification 与 batch invalidation 哪种成本/正确性更好 | 修改源码/文档/Target 后查询 | stale-use rate、repair latency、reads/query |
| DL06 | 规格注入对 WiFi specification-dependent 与 generic task 的差异 | paired with/without concise spec | resolve delta、Token delta、negative-transfer rate |
| DL07 | compiled Wiki 是否遗漏关键宏/例外/设计原因 | diagnostic probes + raw-source gold | answer quality、catastrophic loss、recovery iterations |
| DL08 | 历史 memory 在丰富/稀疏/过期历史下何时应 abstain | 时间切分 issue/commit 集 | localization Acc@k、negative transfer、age calibration |
| DL09 | 冲突来源能否被暴露而非静默覆盖 | 故意注入错误 manual/LLM/rule assertions | conflict recall、wrong-answer rate |

## 10. Task 5 阶段性结论

1. 领域知识应与代码事实分层存储或至少分层标注；物理上是否同库不是首要问题。
2. 确定性链接的核心不是裸 symbol，而是 `repository_id` + `repository_revision` + TargetProfile + semantic entity + source occurrence。
3. typed edge 必须是一等 assertion，携带 generator、inputs、evidence、provenance、confidence、review 和 invalidation 状态。
4. embedding 和 LLM 推断适合候选发现与检索排序，只能形成 `INFERRED_CANDIDATE`，不得自动升级为确定性事实。
5. 原始资料、编译 Wiki、Skill、memory 和分析结果具有不同更新周期；任何派生知识都必须能回到原始资料和当前源码。
6. 读时 citation verification、批量 dependency invalidation 和失败 probe 驱动的 Wiki refinement 是互补机制。
7. 近期数据反复显示 negative transfer：错误/过期 Skill、稀疏历史 memory、过长上下文和盲目 Wiki 压缩都可能降低效果。
8. 当前阶段仍不决定使用单一图、关系库、文件 Wiki 或混合存储；Task 6 将只按证据和硬门槛分类候选。
