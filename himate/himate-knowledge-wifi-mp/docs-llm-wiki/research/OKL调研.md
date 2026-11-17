# OpenKnowledgeLibrary（OKL）调研报告

> 调研对象：`D:\knowledge_graph\OKL\OpenKnowledgeLibrary-master`（版本 0.2.2，`package.json`）
> 取证方式：源码静态阅读 + `docs/guides` 全量文档阅读
> 报告日期：2026-11-16
> 说明：本报告未实际执行 `okl` 命令、未跑通一次完整 ingest，所有运行期结论均来自代码与文档，标注为"设计行为"或"待实测"。

---

## 一、结论摘要

1. **OKL 不是知识库网站，也不是多租户知识平台**，而是一套面向 Agent 的**工程知识生产工具链**：Markdown 正文 + 双向链接 + 声明式 Pipeline + Gate/Lint/评测 + CLI/Skill。
2. **部署形态是单机单用户开发者工具**。仓库内无 Dockerfile、docker-compose、K8s manifest；`.cloudbuild/` 只有编译流水线，没有部署编排。
3. **知识入库是一条不可变 DAG**：`ingest.yaml` 共 14 个阶段（10 个主干 + 3 个 bundle 条件阶段 + reconcile），上游 Gate 失败会撤销当前及全部后继 Stage 的持久确认。
4. **知识消费严格只读**：`okl-query` 通过路由表选择视角、多库 discover；底层 CLI 只接受单个 `kbRoot`，跨库编排由 Skill 读取 `catalog.yaml` 完成。
5. **治理偏结构性、弱内容正确性**：Gate + Lint（6 个 checker）+ 七维加权评测 + 可观测。`self-reported` 门禁存在"自证"风险，即由产出方自己声明通过。
6. **真实落地价值在 SDD 集成**：光产品线 GC-SOP（7 阶段）与 SEF（8 阶段，MA5800 OLT）把"查库"做成流程硬门禁，四级判定门不可降级。
7. **当前知识视图覆盖 4 个**（用例/逻辑/实现/运行），**部署视图尚未支持**；契约归入逻辑视图，不是独立的第五视图。

---

## 二、产品定位与形态

### 2.1 是什么

OKL（OpenKnowledgeLibrary）自述为"面向 agent 软件设计与开发的工程知识库 skill 套件"。从代码结构看，它由四部分组成：

| 组成 | 位置 | 作用 |
|---|---|---|
| 声明式 Pipeline | `assets/pipelines/*.yaml` | 定义知识生产的有向无环流程（DAG） |
| Gate 校验器 | `assets/gates/*.mjs`（11 个） | 阶段出口的硬门禁 |
| 能力层脚本 | `scripts/kernel`、`scripts/capabilities`、`scripts/cli`、`scripts/platform` | 实际执行引擎（TypeScript 编译为 `dist/`） |
| Web 工作台 | `src/web/server`、`src/web/client` | 本地可视化查看与操作 |

### 2.2 不是什么

- **不是网站/服务**：`okl web` 是本地回环工作台，默认端口 3090，仅本机访问。
- **不是多租户平台**：没有账号体系、权限模型、租户隔离。
- **不是 RAG 检索服务**：没有向量库、没有独立检索守护进程，检索靠 Markdown 索引页 + Agent 阅读。
- **不是代码索引引擎**：代码图谱属于代码仓侧的独立工具，OKL 只在消费时通过约定对接。

### 2.3 安装与宿主

- **安装方式**：`npx` 一键安装，或源码安装（`npm run build` 后使用 `dist/okl.js`）。
- **宿主 target（5 类）**：`claude`、`opencode`、`cac`、`agents`、`chrys`。
- **资产落点**：默认复制到 `~/.okl/assets/`。
- **升级行为**：**全量覆盖**，不保留本地对资产的修改——这是升级时的主要风险点。
- **运行要求**：Node.js >= 18。

---

## 三、知识范围与视图

### 3.1 四层知识范围

OKL 把工程知识按抽象层级组织，从"用户怎么用"到"系统怎么跑"逐层下沉：

1. **用例层**：用户场景、业务用例、repo usecases。
2. **逻辑层**：领域模型、契约（contracts）、数据与状态、质量规则、决策记录。
3. **实现层**：模块地形（terrain）、子模块、API、特性耦合、约束。
4. **运行层**：流程（procedures）、运行态约束、排障知识。

### 3.2 关于"五视图"的校正

此前流传的"五视图"说法不准确。当前实际支持 **4 个视图**：

- 用例视图
- 逻辑视图（**契约归入此视图**，不是独立第五视图）
- 实现视图
- 运行视图

**部署视图尚未支持**，属后续版本规划。

---

## 四、部署流程

### 4.1 部署链路

```
npx 安装 / 源码构建
   → 选择宿主 target（claude / opencode / cac / agents / chrys）
   → 资产复制到 ~/.okl/assets/
   → 初始化知识库根目录（kbRoot）
   → 配置 .okl/settings.json（可选多库）
   → okl web（本地 3090 端口）或 CLI 调用
```

### 4.2 部署特征

- **零容器依赖**：不需要 Docker/K8s，本质是 Node CLI + 本地文件。
- **升级即覆盖**：资产全量覆盖，本地定制需自行备份。
- **单机单用户**：没有并发写入控制、没有服务端调度。
- **网络依赖**：内部 CodeHub 安装链路在当前网络环境下是否可用，需实测（见待核实项）。

---

## 五、知识入库流程（Ingest）

### 5.1 阶段总览（14 个）

`assets/pipelines/ingest.yaml` 实际定义：

**主干 10 个阶段：**

| # | Stage | 作用 |
|---|---|---|
| 1 | `source-split` | 源材料切分（按 batch） |
| 2 | `fragment-distill` | 片段蒸馏 |
| 3 | `topic-compose` | 主题合成（index、capabilities、flows、architecture、components、contracts、data-states、quality-rules、decisions、procedures、specifications） |
| 4 | `terrain` | 模块地形（overview、architecture） |
| 5 | `submodules` | 子模块细化（overview、api-both、feature-coupling、constrains、data-models、state-transition） |
| 6 | `global-relate` | 全局关联（use-cases、domains、contracts） |
| 7 | `coverage` | 覆盖度检查 |
| 8 | `deep-dive` | 深挖 |
| 9 | `global-synthesis` | 全局综合（index、system-architecture） |
| 10 | `backlinks` | 反向链接生成 |

**3 个 bundle 条件阶段：**

| Stage | 触发条件 |
|---|---|
| `candidate-flows` | 需要候选流程分析时 |
| `repo-usecases` | 需要仓库用例时 |
| `supplements` | 需要补充材料（glossary、api-surface、api-depend、data-models、specifications、constraints、resource-analysis、human-interfaces）时 |

**1 个收口阶段：**

| Stage | 作用 |
|---|---|
| `reconcile` | 冲突消解与一致性收口 |

> 说明：指南所说的"10 个 Pipeline 阶段"与 YAML 的 14 个阶段并不矛盾——10 是主干，3 个是 bundle 条件阶段，1 个是 reconcile。

### 5.2 阶段顺序校正

指南表格把 `supplements` 排在 `candidate-flows` 之前，**与 YAML 不符**。实际顺序为：

```
candidate-flows → repo-usecases → supplements
```

### 5.3 不可变 DAG 语义

- 流程是**不可变 DAG**：阶段顺序在 YAML 中固定，运行期不可重排。
- **上游 Gate 失败 → 撤销当前及全部后继 Stage 的持久确认**。这意味着一次失败会导致已完成的后续阶段状态全部回退，重跑成本高。
- **单次 ingest 建议规模：5 万 ~ 50 万行**。低于此规模收益有限，高于此规模需分批。

---

## 六、知识消费流程

### 6.1 消费入口

- **`okl-query` Skill**：严格只读，不写库。
- **路由表选视角**：按问题类型选择用例/逻辑/实现/运行视角。
- **多库 discover**：读取 `catalog.yaml` 发现可用知识库。

### 6.2 架构约束

- **底层 CLI 只接受单个 `kbRoot`**，不具备跨库查询能力。
- **跨库编排由 Skill 层完成**：Skill 读 `catalog.yaml`，逐个库调用 CLI，再合并结果。
- **只读保证**：消费路径不产生写入副作用，可安全重复调用。

### 6.3 消费质量的关键

消费效果高度依赖**索引页质量**（`index`、`system-architecture`、`backlinks`）与**命名/路径约定**。索引差 → Agent 找不到入口 → 消费失败。

---

## 七、知识治理

### 7.1 Gate（阶段门禁）

- `assets/gates/` 共 **11 个 `.mjs`** 校验器，包括 `link-integrity`、`produces-exist`、`contract-residue`、`candidate-flows-deep-dived`、`forward-*` 系列、`problem-ledger-analyzed`、`security-view-lint`、`self-reported` 等。
- Gate 是**硬门禁**：不通过则不推进阶段。
- **`self-reported` 风险**：由产出方自行声明通过，缺少独立验证，存在"自证"问题。

### 7.2 Lint（静态检查）

实际有 **6 个 checker**（`scripts/capabilities/knowledge-base/lint/checks/`）：

| Checker | 检查内容 |
|---|---|
| `links` | 链接完整性 |
| `frontmatter` | 元数据字段合法性 |
| `template` | 模板符合性 |
| `composite` | 组合规则 |
| `filename` | 文件命名规范 |
| `sources` | 来源引用 |

> 说明：指南提到的"7/8 类检查"属**方法论清单**，与 CLI 实际 6 个 checker 不是同一层概念，不能直接对比数量。

### 7.3 评测（七维加权）

`scripts/capabilities/evaluation/evaluate.ts` 中定义的权重（总和为 1）：

| 维度 | 权重 |
|---|---|
| `linkGraph` | 0.25 |
| `structure` | 0.20 |
| `pipeline` | 0.15 |
| `sourceEvidence` | 0.15 |
| `frontmatter` | 0.10 |
| `coverage` | 0.10 |
| `consistency` | 0.05 |

- **缺失维度由 `weightedScore` 重新归一化**，不会因缺项直接判零。
- `coverage` 维度是复合分：源覆盖率 0.30 + 覆盖文档准确度 0.35 + 跨仓边界覆盖 0.35（无跨仓场景时改为 0.30 / 0.70）。
- **`consistency` 依赖 LLM 参与**，稳定性待实测。

### 7.4 可观测

`scripts/capabilities/observability` 提供运行轨迹与阶段状态记录，用于排查 Pipeline 卡点。

### 7.5 治理能力评价

- **强项**：链接、结构、来源、模板等**结构性一致性**有明确机器校验。
- **弱项**：**内容正确性**缺少独立验证；`self-reported` 门禁可被绕过；`consistency` 依赖 LLM 判断。
- **结论**：OKL 的治理是"防结构腐化"，不是"防内容错误"。

---

## 八、生命周期闭环

```
源材料 → 切分 → 蒸馏 → 合成 → 地形/子模块 → 全局关联 → 覆盖检查
   → 深挖 → 全局综合 → 反链 → reconcile → 发布
   → 消费（okl-query） → 反馈 → update-source / forward / troubleshoot
   → 回到入库
```

- **Update 边界**：`update-source.yaml` 处理增量更新，但**不重建全库**，只更新受影响范围。
- **Forward 流程**：`forward.yaml` 用于把外部知识前向引入，含四阶段（topics composed → topics reconciled → fragments distilled → contract 校验）。
- **Troubleshoot 双轨**：`troubleshoot.yaml` 与 `troubleshoot-issue.yaml` 分别面向常规排障与问题单驱动排障，两者之间有桥梁。
- **DT 知识**：`dt-ingest.yaml` 处理数字孪生/设备类知识。
- **Global-Ingest**：`global-ingest.yaml` 用于多库全局摄入，依赖 `catalog.yaml` 注册。

---

## 九、多库治理

### 9.1 配置位置

- **权威配置**：`.okl/settings.json` 中的 `oklKnowledgeBases` 字段。
- **字段结构**：
  - `sysKbRoots`（必填，数组）：系统知识库根目录。
  - `candidates`（必填，数组）：候选知识库根目录。
- **回退配置**：`~/.okl/settings.json` 仅作**只读回退**。

### 9.2 发现规则

- **本地配置存在后，不再递归发现**——本地配置是权威范围。
- **显式绝对路径会绕过发现**，退化为单库模式。
- 校验严格：字段缺失、类型错误、目录不存在都会直接报错（`invalidConfiguration`）。

---

## 十、SDD 集成与落地价值

### 10.1 光产品线 GC-SOP（7 阶段）

把"查知识库"做成流程中的**硬门禁**：不查库不能进入下一阶段。

### 10.2 SEF（8 阶段，MA5800 OLT）

在 GC-SOP 基础上扩展，同样把查库作为强制步骤。

### 10.3 四级判定门

判定结果分四级，**不可降级**——不能因为"时间紧"把"未命中"降级为"通过"。

### 10.4 元认知止损

明确止损规则：

> **首次未命中 → 换方式重试一次；第二次仍未命中 → 立即止损，严禁第三次。**

这条规则防止 Agent 在检索上无限循环，是 OKL 落地中最有价值的一条工程约束。

### 10.5 能力分级 L1~L4

| 级别 | 能力特征 |
|---|---|
| L1 | 能读库、能按索引找到页面 |
| L2 | 能按视角路由、能跨库 discover |
| L3 | 能把查库嵌入流程门禁、能判定命中/未命中 |
| L4 | 能回写知识、能维护知识库质量 |

### 10.6 组织要求

- 设**知识工程师**角色。
- 知识库纳入**配置管理与代码评审**。
- 需求完成后**回写知识**。

---

## 十一、工程亮点

1. **声明式 Pipeline + 硬 Gate**：流程可读、可校验，避免"口头流程"。
2. **不可变 DAG**：阶段顺序固定，失败回退语义明确。
3. **七维加权评测**：结构质量可量化，缺项自动归一化。
4. **严格只读消费**：查询无副作用，可安全重复。
5. **多库 discover + 单库 CLI**：职责清晰，跨库编排放在 Skill 层。
6. **元认知止损**：把"何时放弃检索"写成规则，防止 Agent 死循环。
7. **本地 Web 工作台**：回环访问，零外部依赖。

---

## 十二、风险与建议

| 风险 | 说明 | 建议 |
|---|---|---|
| 升级全量覆盖 | `~/.okl/assets/` 升级即覆盖，本地定制丢失 | 定制内容外置，升级前备份 |
| `self-reported` 自证 | 产出方自己声明通过 | 关键 Gate 增加独立校验或抽样复核 |
| 内容正确性弱 | 治理偏结构，不验内容对错 | 引入人工抽检 + 来源可追溯要求 |
| 大规模 ingest 成本 | 5~50 万行建议区间，失败回退贵 | 分批摄入，先小样本验证 |
| 跨库靠 Skill 编排 | CLI 单库，跨库逻辑在 Skill 层 | 固定 `catalog.yaml` 规范，避免路径漂移 |
| 部署视图缺失 | 无法表达部署拓扑 | 暂用运行视图 + 外部文档补充 |
| `consistency` 不稳定 | 依赖 LLM 判断 | 关键场景改为确定性规则 |

---

## 十三、文档与代码偏差清单（5 项）

| # | 偏差 | 应以何为准 |
|---|---|---|
| 1 | `forward/` vs `external/` 命名 | 概念文档 §2.2、多知识库指南 L23 为旧命名，**以 `external/` 为准** |
| 2 | 指南表格把 `supplements` 排在 `candidate-flows` 前 | YAML 实为 **candidate-flows → repo-usecases → supplements** |
| 3 | Lint 检查项数量口径不一 | CLI 实际 **6 个 checker**；指南的 7/8 类是方法论清单 |
| 4 | 指南所述 CI 触发/定时巡检自动更新 | 仓库内**无实现**，应标注为设计目标 |
| 5 | 部署视图 | 当前**未支持**，属后续版本 |

---

## 十四、待核实项

| # | 待核实内容 | 核实方式 |
|---|---|---|
| 1 | 实际跑 `okl-ingest` 的耗时、token 消耗与产出质量 | 小样本实测 |
| 2 | `okl-global-ingest` 的 `catalog.yaml` 注册格式与多库发现实际行为 | 构造双库实测 |
| 3 | 评测 `consistency` 维度在 LLM 参与下的稳定性 | 同输入多次评测对比 |
| 4 | Web 工作台实际交互完整度（Pipeline 图编辑、轨迹分析） | 启动 `okl web` 实测 |
| 5 | 内部 CodeHub 安装链路在当前网络环境的可用性 | 实际安装验证 |

---

## 十五、取证说明

- **已读源码**：`package.json`、`assets/pipelines/ingest.yaml`、`assets/gates/`、`scripts/capabilities/evaluation/evaluate.ts`、`scripts/capabilities/knowledge-base/lint/checks/`、`scripts/capabilities/knowledge-base/discovery-settings.ts`。
- **已读文档**：`docs/guides` 全部 5 份（用户手册 1504 行、光产品线构建指南 789 行、多知识库 290 行、Forward 160 行、Global-Ingest 140 行）。
- **未做**：未执行 `okl` 命令，未跑通 ingest，未启动 Web 工作台。运行期行为均标注为设计行为或待实测。
- **结论边界**：本报告结论适用于版本 0.2.2；后续版本可能变化。
