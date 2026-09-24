# 细节设计说明书 02 · 知识文档图谱（LLM-Wiki）构建

> **定位**：文档侧实现细节——docs/ 图谱仓（raw0/raw1 + llmwiki + spec）目录结构、知识卡契约、生命周期、三条摄入线、ingest 六决策、llm-wiki 技能。
> **状态**：v0.3 草案，内容自《知识库架构设计-合稿.md》§4 迁移，待按 00-总架构设计 细化。已对照 CANNBot 审阅补充契约职责（§2）、适用范围语义（§2）、四语义分离（§3）、Runbook 观察-推断-验证分离（§5）；新增 Laya 决策引擎结合点（§6），2026-09-23 按 FactumCore 三份 Laya 调研收敛 P0 优先级并补 shadow 三态/截断防护/候选两组语义（§6.4）。
> **关联**：00-总架构设计 §4.2（工具选型概要）、§5 步骤 2.1–2.4、§3.5（知识契约六项职责约定）；04-消费与问答（Query 五步法、渐进式披露、双轨问答、Search Receipt——§6 结合点的消费侧上下文）。

---

## 1. 目录结构

> **docs/ 本质就是 LLM-Wiki 图谱仓**：raw0/ + raw1/ 构成原始来源层（人策展、LLM 只读），llmwiki/ 内知识卡（三类起步）+ schema/ 构成 Wiki 层与 Schema 层（LLM 编译维护），spec/ 单独存放 spec/design SSOT。entities/concepts/runbooks 知识卡统一放 `docs/llmwiki/` 内（**直接放根下，不再套 wiki/ 层**），不散落在外面；它们的原始来源（raw）在 `docs/raw0/`、`docs/raw1/`。

```
docs/                        # 部门 docs/ 下我们的 LLM-Wiki 图谱仓（原始来源层 + Wiki 层 + Schema 层）
├── raw0/                    # [raw] 原始文档存放（pdf/docx 等原始格式；人策展、LLM 只读）
│   ├── 802.11协议/          #   协议类：802.11 系列协议、WiFi MAC 规范（pdf 原版）
│   ├── 芯片规格/            #   芯片类：1108/1112 芯片规格书、寄存器手册
│   ├── 设计文档/            #   设计类：历史设计文档、评审记录
│   └── 调试轨迹/            #   轨迹类：调试会话原始记录、日志归档
├── raw1/                    # [raw] 原始文档初步加工（md 格式；人策展、LLM 只读）
│   ├── 802.11协议/          #   协议类：转 md 后的协议要点（与 raw0 同名分层一一对应）
│   ├── 芯片规格/            #   芯片类：规格要点转 md
│   ├── 设计文档/            #   设计类：设计文档转 md
│   └── 调试轨迹/            #   轨迹类：调试记录初步提炼
├── llmwiki/                 # [wiki+schema] LLM-Wiki 知识图谱（知识卡直接放根下）
│   ├── entities/            #   实体页＝命名路由：模块/子系统一个文件（wal/hmac/dma → wal.md/hmac.md/dma.md）；config.yml wiki_entities 指向这里
│   ├── concepts/            #   概念页（知识主体）：concept-flow-*（TX/RX 通路、Event-Message、ops 表分发）+ concept-rule-*（规则）+ concept-timeline-*（演进）
│   ├── runbooks/            #   调试轨迹提炼：现象/信号/根因/解法/边界/验证（六要素卡，cannbot 新增线）
│   ├── index.md             #   全局索引（每页一行：链接+一句话摘要+可选元数据，查询第一步）
│   ├── glossary.md          #   术语表（802.11/WiFi MAC 中英对照，双链枢纽）
│   ├── log.md               #   操作日志（只追加；条目前缀 `## [YYYY-MM-DD] ingest | 标题`，grep "^## \[" 可解析）
│   ├── purpose.md           #   知识库目标与关键问题
│   └── schema/              #   Schema 层：卡契约 schema.md（Frontmatter 字段表 + 正文四要素 + 生命周期）
│                           #   起步只建 entities/concepts/runbooks 三类；sources/global/decisions/comparisons/synthesis/outputs 不建目录、按需再引入（触发场景见 §1.1）
└── spec/                    # ★=原 codespec 仓（spec/design SSOT，见 05-落地路线与评测 阶段 3）
    ├── changes/             #   变更目录：每个变更一个子目录（proposal/spec/design/… 全量交付件）
    └── specs/               #   已归档 spec 库（组件级 design.md/spec.md，SSOT）
```

### 1.1 三类知识卡怎么分（起步形态 + 按需引入触发场景）

> 文件夹只是组织形态，**检索不按文件夹走**——靠 index.md + 卡 frontmatter（domain/technology/platform/lifecycle）定位。三类各回答一类问题：

**entities/（实体页 = 命名路由）**——一个模块/子系统一个文件，回答"这个模块是干什么的、入口在哪"，是 config.yml `wiki_entities` 指向的锚点：

```markdown
# docs/llmwiki/entities/wal.md
---
title: WAL（WiFi Abstraction Layer）
type: entity
domain: wifi-mac
technology: tx-path
platform: [chip2, chip8]
lifecycle: stable
sources:
  - codebase/drivers/wifi/wal/*.c@a1e0f45
related:
  - concepts/concept-flow-tx-path.md
  - entities/hmac.md
---
## 结论
host 侧 TX/RX 数据通路的抽象层，介于 hmac（协议处理）与 hwal（硬件抽象）之间……
## 适用条件 / 失效边界 / 验证方法
……（四要素）
```

**concepts/（概念页）**——按前缀分三种，回答"流程怎么走 / 规则是什么 / 演进怎么变"，是知识主体：

```markdown
# docs/llmwiki/concepts/concept-flow-tx-path.md        # 通路：TX 从 desc 到空口
# docs/llmwiki/concepts/concept-flow-rx-path.md        # 通路：RX 从空口到上层
# docs/llmwiki/concepts/concept-flow-event-message.md  # 通路：device↔host 事件消息
# docs/llmwiki/concepts/concept-rule-desc-queue.md     # 规则：desc 队列语义
# docs/llmwiki/concepts/concept-timeline-ring-evolution.md # 演进：ring 语义版本变化
```

**runbooks/（调试轨迹）**——一个调试案例一个文件，六要素结构（现象/信号/根因/解法/边界/验证），回答"这个报错怎么解"：

```markdown
# docs/llmwiki/runbooks/rb-rx-csum-error.md
现象：RX 报文 checksum 校验失败，丢包率异常
信号：日志特征 `[RX] csum error` / 计数器 rx_csum_err 增长
根因：…… 解法：…… 边界：…… 验证：……
```

**按需再引入的六类**（不建目录，内容先放别处，出现触发场景再加回）：

| 暂不建的目录 | 内容先放哪 | 何时再引入（growth trigger） |
|---|---|------------------------------|
| `sources/` | 卡 frontmatter `sources` 字段直接指 raw0/raw1 路径 | 同一篇原文被 ≥3 张卡引用，重复读原文变痛 |
| `global/` | 跨仓知识写进对应 concept-flow 卡 | 出现不属于任何单侧模块的 host↔device 接口契约 |
| `decisions/` | 先不建 | 出现真正长期取舍结论（ring 大小、ops 表 vs if-else） |
| `comparisons/` | 先不建 | 出现跨方案/跨版本对比需求 |
| `synthesis/` | 综合理解直接写成 concept 卡 | 同一主题被多篇源重复综合 |
| `outputs/` | 问答回填到对应 concept/entity 卡 | 有价值问答产出变多，需要集中沉淀 |

> **可选工具层**（不装不影响工作）：Obsidian 作可视化展示层（graph view 看 hub/orphan、Dataview 按 frontmatter 生成动态表、Marp 出幻灯片、Web Clipper 采集网页进 raw）；wiki 规模增长后引本地搜索（见 04-消费与问答 §6）。

## 2. 知识卡契约（schema.md 核心）

每张知识卡 = **Frontmatter（结构化元数据） + 正文（四要素）**。

> **契约职责（对齐 00-总架构设计 §3.5A）**：本 schema 是生产（ingest）、查询（query）、检查（lint）**共用的规则源**——AGENTS.md / Skill 只引用规则，config.yml 只负责路由数据，check.sh 只执行校验，同一规则不产生冲突定义；规则演进同时考虑已有卡片与消费流程兼容。

**Frontmatter 字段表**：

| 字段 | 取值/示例 | 用途 |
|------|-----------|------|
| `title` | hmac_tx_process TX 发送通路 | 卡名 |
| `type` | 起步：entity / concept-flow / concept-rule / concept-timeline / runbook；预留（按需再引入）：source / decision / comparison / synthesis / output | 页面类型，决定正文结构 |
| `tags` | 合法集合（如 `tx-path` `desc` `sync`） | 检索过滤 |
| `domain` | wifi-mac | 固定值 |
| `technology` | tx-path / rx-path / event-message / ops-dispatch | 技术范围（专属领域卡仅在该范围内检索） |
| `platform` | chip2 / chip8 / 两者 | 检索必带平台条件 |
| `lifecycle` | draft / stable / deprecated | **检索默认只返回 stable** |
| `sources` | 固定位置列表（见下） | 可核验来源，不进正文复制；起步无 sources/ 目录，直接指 raw0/raw1 或代码仓锚点路径 |
| `related` | 审查后的关联卡（仅导航，不进检索语料） | 关系跳转 |
| `conflicts` | 与本卡冲突的卡/来源列表（可选） | **矛盾显式标记**：摄入时发现冲突即标注，lint 检查一致性，消费时提示 |

> **适用范围语义（对齐 00-总架构设计 §3.5B）**：卡片声明芯片、运行侧、版本与必要的功能条件；只有来源支持的共同行为才可共享，**未知范围不视为通用**；消费先确认目标范围再读卡核对细粒度限制，差异比较分别取证。

**正文四要素**（缺一即不完整）：
1. **结论**——可复用的工程结论（是什么、怎么运作）；
2. **适用条件**——何时适用（平台/版本/输入条件/配置）；
3. **失效边界**——何时不适用、哪些做法不可迁移；
4. **验证方法**——怎么验证结论成立（编译/UT/真机/日志特征）。

**示例（concept-flow 卡）**：

```markdown
---
title: TX 发送通路
type: concept-flow
tags: [tx-path, desc, sync]
domain: wifi-mac
technology: tx-path
platform: [chip2, chip8]
lifecycle: stable
sources:
  - codebase/drivers/wifi/hmac/tx/hmac_tx.c@8102322af
  - docs/raw1/802.11协议/TX流程说明.md
related:
  - entities/wal.md
  - concepts/concept-rule-desc-queue.md
---
## 结论
（TX 通路从上层 desc 到空口的完整处理顺序、关键函数与数据流……）
## 适用条件
（chip2/chip8 通用；依赖 desc 队列规则卡……）
## 失效边界
（xx 场景走特殊帧通路，不走本卡；xxx 版本后 ring 语义变更……）
## 验证方法
（代码图 callers 核对入口；抓空口日志验证时序；对照 spec 锚点……）
```

## 3. 生命周期：draft → stable → deprecated

```
生产（ingest）──▶ draft（候选，未验证）──满足门禁──▶ stable（检索默认可见）
                                                        │
                                       结论错误/不再推荐 ─▶ deprecated（保留解释历史）
```

- 新卡/修改卡默认 **draft**；来源、平台、正文四要素与门禁（§2 + 03-治理机制 §2）均满足才显式进 **stable**；
- Query 默认只返回 stable，避免"新写页面没验证就被 Agent 当事实用"；
- deprecated 卡保留但排检索，防止过时结论误用；
- **四语义分离（对齐 00-总架构设计 §3.5C）**：`stable`=按知识库规则可消费；`sources`=证据入口；复核记录=真实发生的复核及其范围；`待复查`=来源变化后的有效性疑问——它们不能互相推导，固定来源或 lint 成功不等于"已复核"，消费时共同判断。

## 4. 三条摄入线（producer 分流）

| 摄入线 | 来源 | producer | 产出 |
|--------|------|----------|------|
| **文档类** | docs/raw0/（原始 pdf/docx）+ docs/raw1/（初步加工 md）+ 协议/设计资料 | 通用文档编译（来源不变、知识增强：提取元数据 + 构建依赖/引用/上下游关联） | entities / concepts 页（sources 走卡 frontmatter 字段直接指 raw，不单独建页） |
| **通路/规范类** | docs/spec/ 的 spec.md / design.md | spec→实体页映射（组件职责/接口/配置） | entities 页 + 锚点（`[函数](路径:行号)`） |
| **轨迹类** | 调试会话轨迹（Agent 交互记录/工具日志/trace） | 轨迹提炼（解析→挖掘→汇总） | runbooks/ 六要素卡 |

**轨迹类细节（Runbook 六要素）**：

```
现象：遇到了什么报错或异常
信号：识别该问题最关键的报错特征与日志标志
根因：导致错误的底层原因
解法：经过验证的修复方案与关键代码变更
边界：适用的硬件平台、软件版本、输入条件
验证：修复后通过的测试用例与实际收益
```

流程三步：原始日志建模为结构化事件、过滤噪声还原交互 → 按报错特征+修复过程提取"代码+自然语言"片段（按编译/性能/精度分类）→ 跨会话聚类去重、保留相互印证部分，沉淀为系统化经验卡。原始轨迹不入库（含噪声与隐私），只有提炼后的 Runbook 落库。

## 5. ingest 决策：六选一

先查重（Query 同主题并读完候选卡），再决定：

| 决策 | 场景 |
|------|------|
| **create** | 确实没有同主题卡 |
| **update** | 原卡职责不变，补充或修正 |
| **merge** | 多张卡职责重叠 |
| **split** | 一张卡混合多个独立职责 |
| **deprecate** | 结论仍需解释历史，但已错误/不再推荐 |
| **defer** | 来源、范围或验证不足，暂不落库 |

标题不同 ≠ 主题不同；不能自动覆盖跳过已有卡审阅。

**摄入时人参与引导**：优先单源逐次摄入；LLM 读源后先与提问者过一遍要点（确认强调点、指认关键通路、纠正取舍），再写页。人的输入决定"哪些值得写深、哪些略过"，LLM 只负责执行与簿记。

**摄入时矛盾处理**：新来源与已有卡结论冲突时，不静默覆盖——更新相关卡并在 `conflicts` 字段显式标记冲突双方与判定依据，或新建 comparison 页对比差异；冲突未裁决前相关卡不得进 stable。

**Runbook 观察-推断-验证分离（对齐 00-总架构设计 §3.5E）**：Runbook 卡内区分**原始观察**（日志/计数器/trace 实测值）、**原因推断**（分析假设）、**验证结果**（修复后复测证据）三段，不把聊天总结当作原始观测；原始轨迹可引用 AIoTBot 现有归档。

批次完成后：更新逐层 index.md、写当天 log（前缀 `## [YYYY-MM-DD] ingest | 标题`）、执行关系审查、全库 Lint、重建检索索引、目标查询验证新卡可被检索。

---

## 6. Laya 决策引擎结合点（召回管线的岔路口）

> **定位**：Laya（421M 参数本地决策引擎，一次前向传播回答一组自定义问题，输出带校准置信度）不替代检索本身——index.md 定位、qmd 混合搜索、卡正文精读仍是召回主干。Laya 的落点是召回管线上的**分流点、守门点、回填点**，对应 04-消费与问答 的 Query 五步法、渐进式披露（P0-P3）、双轨问答、Search Receipt。

### 6.1 五个结合点（按召回管线顺序）

> **优先级分层（2026-09-23 调研收敛）**：5 个结合点是管线位置的**远期规划**；首期交付收敛为 **P0 两个**（结合点 5 回填路由 + 结合点 2 检索深度分级的降级版"候选阅读排序"），其余为 P1/旁路实验。分层依据见 §6.4。

| # | 结合点 | 管线位置 | Laya 问题类型 | 输出用途 | 优先级 |
|---|--------|---------|--------------|---------|--------|
| 1 | **入口分流** | Query 五步法 步骤1-2 | choice（问题类型：设计动机/实现细节/变更影响）+ noul（是否需交叉印证） | 双轨问答前置路由：Why 题走 wiki Agent，How 题走代码 Agent；低置信度直接升级大模型深判，不进双轨 | P1 |
| 2 | **检索深度分级** | 渐进式披露 P0-P3 门控 | score（检索深度期望：trivial→hard） | 简单事实查询 P0 即返回；端到端设计题预判 hard，提前规划多轮检索预算。直接回应评测报告暴露的问题——Q8 端到端大题 grep-only 全漏组1，根因是缺"这题需要全局意识"的预判 | **P0（降级版：候选阅读排序）** |
| 3 | **覆盖-缺口判定** | 检索结果返回后 | choice（已覆盖/冲突/证据不足/缺口） | Laya 预分类 + 置信度：冲突类升级 LLM 裁决，缺口类直接转代码 Agent 补查。比主模型每次全文读检索结果省 token | P1 |
| 4 | **结果质量守门** | 检索结果消费前 | noul（"这次检索是否答到了"） | 作为是否触发交叉印证的开关，配合置信度分层：≥0.7 自动采信、0.4-0.7 交叉印证（wiki 答案 vs 代码对账）、<0.4 人工 | P1 |
| 5 | **回填路由** | Search Receipt 回流 → 统一摄入入口 | choice（补充/冲突/重复） | 预判与现有卡的关系，路由到 update/merge/create；最终裁决仍需 LLM，但预分类把机械 case 挡在 LLM 之前 | **P0** |

### 6.2 明确排除的落点

- 卡正文的理解与综合——wiki Agent 的活，Laya 无深度阅读能力；
- 冲突消解的最终裁决——需要读代码对账，Laya 只做预分类；
- 替代 index.md / qmd——Laya 无检索能力；
- 知识卡语义 lint——需要全文理解，走 03-治理机制 的双层 lint。

### 6.3 工程约束（UT demo 实测教训）

Laya 对边界情况（部分失败、部分覆盖）区分度弱：UT 结果判定 demo 中"1 个 failed"被误判为 run_passed，置信度仅 0.44。因此 §6.1 结合点 3、4 的输出**必须带置信度分层兜底，不能裸用**；state 预处理（提取关键行放前部）比 criteria 调优更关键。

### 6.4 P0 收敛依据与 shadow 三态模式（2026-09-23 调研）

> 依据：FactumCore 三份 Laya 调研文档（research/laya-wiki-decision-model-research-design.md、workflows/laya-llm-wiki-consumption.md、workflows/laya-llm-wiki-incremental-knowledge.md）。实施细节（协议、字段、配置）以这三份为依据层，本节只保留决策层，不复制内容避免双源维护。

**P0 收敛理由**：5 个结合点同时上不现实。P0 两个任务的共同特征——输入可切成短单元、结果便于人审、误判不直接产生新事实（一个对应消费成本，一个对应 Wiki 积累成本）。结合点 2 的完整版"检索深度分级"需要全局意识，恰是 421M/1024 token 预算的 Laya 不擅长的；降级为"候选阅读排序"（query.relevance.v1：direct/background/irrelevant/unknown 四标签）后输入变成"一个问题 × 一张卡的一个自包含片段"，才可落地。

**shadow 三态模式**（首期 shadow，评测通过才切 assist）：

| 模式 | 行为 | 启用条件 |
|------|------|---------|
| off | Laya 完全不参与，走既有流程 | 默认 |
| shadow | 保留 Laya 建议但完全使用原排序，旁路记录差异 | 首期 |
| assist | 按 Laya 建议调整阅读顺序/队列预分 | 评测通过后 |

**输入截断防护**（针对 Laya 静默截断风险）：不能通过删除否定、Target、宏条件和例外来满足预算；无法构造完整片段就退回原排序并由 Agent 读正文；输入必须经过最终序列预算检查，指令/选项/正文分别核验，无静默截断才可调用。

**候选两组语义**：候选分为"可作为当前知识读取"（stable、scope 相容、来源与快照匹配、无待复查标记）与"只能作为取证线索"（待复查、范围未知、缺证或过期卡）两组；待复查/过期卡不得直接当当前事实，与知识契约"待复查不得进 stable"一脉相承。

**关闭路径**：抽检发现混 Target、误把过期卡当当前事实等严重错误 → 立即切回 off，保留日志定位，不回滚或删除已存在的知识。

**协议引用**：消费出口与增量入口共用 judge（IncrementEvent v1 协议、幂等靠 event_id + 载荷 hash）；卡契约补四个可选复核字段（reviewed_snapshot / pending_reviews / verified_claims / superseded_by），老卡缺字段按"未知"处理不默认已验证——字段定义见 FactumCore 增量方案 §3.2，落地时统一定义在 schema 文档由 ingest/query/lint 共用。

---

## 待细化项（v0.2 → v1.0）

- [ ] raw0/raw1 四类分层（802.11协议/芯片规格/设计文档/调试轨迹）与卡 frontmatter `sources` 字段的路径写法约定
- [ ] llm-wiki 技能四操作（init / ingest / query / lint）的提示词骨架
- [ ] 卡契约各 type 的正文结构模板
- [ ] 首批试点卡清单（ops 表分发、TX/RX 通路、Event-Message）
