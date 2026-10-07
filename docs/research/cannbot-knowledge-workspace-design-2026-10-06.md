# CANNBot 知识库与 Workspace 结构设计

> **用途**：按 [AIoTBot 主设计](/E:/FactumCore/docs/架构设计.md) 的目录图方式，单独还原 CANNBot 的知识库及其外围工作区，供后续逐项对齐。
> **审阅日期**：2026-10-06。依据 2026-09-30 拉取并实际安装的官方源码快照；本次重新核对本地文件和 HEAD，未更新远端。
> **表达范围**：展开知识正文、来源、规则、技能、索引、治理以及工程资料的位置；产品源码和框架内部实现省略。大批主题目录、卡片和源码文件用 `…` 表示。

**先纠正 raw 的位置：`cannbot-knowledge` 的 Git 收录内容没有 raw 资源，但恢复资源后的磁盘根目录有 `cann-docs-raw/` 和 `cann-ops-raw/`。两者位于 `knowledge/` 正文目录之外，仍在完整知识仓之内。** “raw 都放在知识仓外”这个笼统说法不准确。[恢复目标 get_resources.sh:49](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/get_resources.sh:49)、[Git 忽略规则 .gitignore:10](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.gitignore:10)

## 1. 图的读法与外层布局

上游没有一个统一固定的总 workspace 仓。下面选择官方支持、且已在本地实装的“业务工程 + 独立完整知识仓”组合画法。共同父目录只是便于与 AIoTBot 对照，各仓也可以位于不同磁盘位置。业务工程可以直接是一份组件源码仓，不要求额外创建名为 `project` 或 `main` 的目录。[工程安装目标](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/script/bin/cannbot.js:57)、[知识根选择](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:202)

- `[G]`：该仓 Git 管理的文件或目录，包括 Git 中声明的链接。
- `[L]`：恢复或生成的本地内容；知识仓中的这些区域被 Git 忽略。
- `[R]`：工作流定义的运行时位置；本地没有执行完整业务任务来生成这些工件。
- `→`：链接或配置指向；`<…>` 是说明性占位符，不是上游固定目录名。

## 2. 整个 Workspace 目录图

```text
CANNBot workspace/                       # 组合示意父目录，不是上游统一大仓
├── cannbot/                             # [G] 工具框架、插件与 harness，内部省略
│   ├── vendor/
│   │   └── cannbot-skills/               # 公共工程技能仓：工具构建使用锁定的子模块版本
│   └── …
├── cannbot-skills/                       # 可选独立检出：用于技能开发/调研，不是运行必需的重复仓
│   └── …
├── <其他组件源码仓>/                    # ops-nn、ops-math、ge、runtime、driver 等独立仓，省略
│   └── …                                # 各仓源码、自有 docs 和 Agent 规则随各仓维护
├── <业务工程 P>/                        # 插件安装目标；也可以直接是上述某个组件源码仓
│   ├── AGENTS.md                        # 工程插件规则 + 知识查询/贡献入口
│   ├── .agents/
│   │   └── skills/
│   │       ├── …                        # 安装的工程技能，来自插件及公共技能仓
│   │       ├── knowledge-query/          # → K/.agents/skills/knowledge-query，只读查询
│   │       ├── ascendc-api-knowledge-query/ # → K 中对应技能，API 专用查询
│   │       ├── knowledge-ingest/         # → K 中对应技能，contributor 模式才安装
│   │       ├── knowledge-lint/           # → K 中对应技能，contributor 模式才安装
│   │       ├── ops-knowledge-vv-ingest/  # → K 中对应技能，contributor 模式才安装
│   │       └── ops-knowledge-cv-ingest/  # → K 中对应技能，contributor 模式才安装
│   ├── .opencode/                       # 本地选择 OpenCode 格式；其他客户端采用各自适配位置
│   │   ├── agents/                      # 安装的工程角色，细节省略
│   │   │   └── …
│   │   ├── skills/                      # 知识技能适配链接 → P/.agents/skills
│   │   │   └── …
│   │   └── cannbot-plugin.json           # 插件安装记录
│   ├── .cannbot/
│   │   ├── knowledge.env                # 完整知识仓 K 的绝对路径、consumer/contributor 模式
│   │   ├── plugins/
│   │   │   └── <plugin>/                # 插件资产，省略
│   │   │       └── …
│   │   ├── dependencies/
│   │   │   └── <plugin>/                # 插件声明的源码依赖；不是知识仓的固定证据快照
│   │   │       └── …
│   │   └── <任务>/                      # [R] 每个任务独立；安装插件不会自动生成任务
│   │       └── workflowN/               # [R] W：本轮 work_dir，具体文件由插件/任务决定
│   │           ├── workflowN.yaml       # 节点、依赖、执行任务与验收条件
│   │           ├── <需求、方案、报告等>  # 本轮工程资料原件，具体结构见第 4 节
│   │           └── .workflow/           # harness 的状态与会话记录
│   └── …                                # 业务代码、测试及组件自身长期设计文档，省略
└── cannbot-knowledge/                    # K：完整知识仓，不等于内部 knowledge/ 正文目录
    ├── AGENTS.md                        # [G] 仓级边界、机器规则指针、生产/消费/治理约定
    ├── CLAUDE.md                        # [G] 链接 → AGENTS.md，同一规则入口
    ├── README.md                        # [G] 知识库定位及 docs/recipes 导航
    ├── CONTRIBUTING.md                  # [G] 知识贡献、公共组件贡献与评审流程
    ├── install.sh                       # [G] 获取完整 K、依赖/资源/索引准备、项目入口安装
    ├── get_resources.sh                 # [G] 恢复登记的文档归档和固定提交源码
    ├── check.sh                         # [G] 仓库质量检查入口
    ├── requirements.txt                 # [G] 知识系统运行依赖
    ├── requirements-dev.txt             # [G] 开发与检查依赖
    ├── knowledge/                       # [G] 唯一 OKF Bundle：全部可检索知识卡及逐层导航
    │   ├── index.md                     # 全库导航；声明 OKF 版本，不作为卡片参与检索
    │   ├── common/                      # 通用领域
    │   │   ├── index.md
    │   │   └── platforms/
    │   │       ├── index.md
    │   │       └── concepts/            # 硬件平台概念，例如 ascend_910_95.md
    │   │           ├── index.md
    │   │           └── …
    │   ├── ops/                         # 算子领域；下一层按 DSL 或 shared 路由
    │   │   ├── index.md
    │   │   ├── ascendc/
    │   │   │   ├── index.md
    │   │   │   ├── apis/                # API 契约；官方文档页受控镜像也是 API 卡
    │   │   │   │   ├── ai_cpu_api/      # 各组内部继续按真实主题分层，每级都有 index.md
    │   │   │   │   ├── appendix/
    │   │   │   │   ├── simd_api/
    │   │   │   │   ├── simt_api/
    │   │   │   │   ├── utils_api/
    │   │   │   │   └── …                # index.md、卡片及更深主题；含 glossary.md 等真实页
    │   │   │   ├── concepts/            # 原理、机制及概念卡
    │   │   │   │   └── …
    │   │   │   ├── examples/            # 可复用示例卡
    │   │   │   │   └── …
    │   │   │   ├── guides/              # 使用指南；受控官方 Guide 镜像及相关知识
    │   │   │   │   └── …
    │   │   │   ├── operators/           # 固定源码证据支持的完整算子知识卡
    │   │   │   │   ├── aclnn/           # 公开 ACLNN/API → Kernel 链路
    │   │   │   │   │   ├── cv/
    │   │   │   │   │   ├── math/
    │   │   │   │   │   ├── nn/
    │   │   │   │   │   └── transformer/ # 各组再按官方 category 分层，末层是算子卡
    │   │   │   │   ├── direct/          # 独立 Direct Invoke 路线
    │   │   │   │   │   ├── cv/
    │   │   │   │   │   ├── math/
    │   │   │   │   │   ├── nn/
    │   │   │   │   │   └── transformer/ # 同样按 category/算子卡组织
    │   │   │   │   └── index.md
    │   │   │   ├── optimizations/       # 性能优化方法；已有 matmul/reductions/vector 分组
    │   │   │   │   └── …
    │   │   │   └── runbooks/            # 诊断、处置与验证闭环卡，不保存整条原始会话
    │   │   │       ├── compilation/
    │   │   │       ├── performance/
    │   │   │       ├── precision/
    │   │   │       ├── runtime/
    │   │   │       ├── validations/
    │   │   │       └── index.md
    │   │   ├── triton/
    │   │   │   ├── index.md
    │   │   │   ├── apis/                # 已有 ir/ 下 API 卡
    │   │   │   │   └── …
    │   │   │   ├── examples/
    │   │   │   │   └── …
    │   │   │   ├── guides/
    │   │   │   │   └── …
    │   │   │   ├── optimizations/
    │   │   │   │   └── …
    │   │   │   └── runbooks/            # 已有 performance/ 分组
    │   │   │       └── …
    │   │   ├── shared/                  # 有证据支持、不依赖单一 DSL 的共享知识
    │   │   │   ├── index.md
    │   │   │   └── guides/
    │   │   │       └── …
    │   │   ├── pypto/
    │   │   │   └── index.md             # 当前快照仅导航占位，不表示已有知识卡
    │   │   └── tilelang/
    │   │       └── index.md             # 当前快照仅导航占位
    │   ├── model/                       # 模型领域；下一层按任务作用域路由
    │   │   ├── index.md
    │   │   ├── embodied/
    │   │   │   ├── index.md
    │   │   │   └── concepts/…
    │   │   ├── spatial/
    │   │   │   ├── index.md
    │   │   │   └── concepts/…
    │   │   ├── training/
    │   │   │   ├── index.md
    │   │   │   ├── concepts/…
    │   │   │   └── guides/…
    │   │   └── inference/
    │   │       ├── index.md
    │   │       ├── concepts/…
    │   │       ├── guides/…
    │   │       ├── optimizations/…
    │   │       └── runbooks/…
    │   ├── contrib/                     # 贡献者经验领域
    │   │   ├── index.md
    │   │   └── ascendc/
    │   │       ├── index.md
    │   │       └── optimizations/
    │   │           └── controlled_code_perturbation/… # 已有贡献者优化经验
    │   ├── graph/
    │   │   └── index.md                 # 当前仅导航占位；源码仓 ge 存在不代表这里已有卡
    │   └── runtime/
    │       └── index.md                 # 当前仅导航占位；不等于 runtime 源码或 raw 缺失
    ├── cann-docs-raw/                   # [L] 官方 docs/examples 归档；按来源组件原布局恢复
    │   ├── .complete                    # 来源 URL 与准备时间，不是固定内容哈希证明
    │   ├── asc-devkit/
    │   │   ├── docs/
    │   │   │   ├── zh/
    │   │   │   │   ├── api/             # 官方 API 原页，知识摄入的主要来源之一
    │   │   │   │   ├── guide/           # 官方指南原页
    │   │   │   │   ├── figures/         # 归档内图像等资源
    │   │   │   │   └── …
    │   │   │   ├── en/…
    │   │   │   └── …
    │   │   └── …
    │   ├── ops-nn/
    │   │   ├── docs/…                   # 官方组件文档
    │   │   ├── examples/…               # 归档还含示例，不能视为纯 PDF/Word 原件箱
    │   │   └── …                        # 还含 activation/matmul 等部分源码资源
    │   ├── ge/
    │   │   ├── docs/
    │   │   │   ├── zh/…                 # 含 api/design/user_guides 等官方文档
    │   │   │   └── en/…
    │   │   └── …
    │   ├── runtime/…
    │   ├── ops-cv/…
    │   ├── ops-math/…
    │   ├── ops-transformer/…
    │   ├── hccl/…
    │   ├── hcomm/…
    │   ├── hixl/…
    │   ├── amct/…
    │   ├── cann-samples/…
    │   ├── docs/…
    │   ├── metadef/…
    │   ├── oam-tools/…
    │   ├── opbase/…
    │   ├── pyasc/…
    │   ├── pypto/…
    │   └── tensorflow/…
    ├── cann-ops-raw/                    # [L] 登记的固定提交源码证据，独立于开发 checkout
    │   └── ascendc/
    │       ├── ops-nn/
    │       │   ├── .objects.git/        # 本地 Git 对象缓存
    │       │   └── 955f8b33985b6d72989ebff341bb9c2c564a51bc/ # detached worktree，源码省略
    │       ├── ops-math/
    │       │   ├── .objects.git/
    │       │   └── 165d41f02a43a62324b434cb6bda7c533b14da3e/ # 固定工作树，源码省略
    │       ├── ops-cv/
    │       │   ├── .objects.git/
    │       │   └── bb717d075d129fd1fc7b96b2886824a1d153ed2f/ # 固定工作树，源码省略
    │       └── ops-transformer/
    │           ├── .objects.git/
    │           └── be33d95bb755cedec3108f70805c1874d1792540/ # 固定工作树，源码省略
    ├── governance/                      # [G] 全 Bundle 共享规则，不按每个领域重复维护
    │   ├── schemas/
    │   │   ├── frontmatter.schema.json  # 字段白名单、数据类型和基础枚举
    │   │   ├── profiles.yaml            # 公共必选字段、路径 Profile → OKF type 及字段组合
    │   │   └── registries.yaml          # domain/route/platform/tag、路径值与本地来源注册
    │   ├── contracts/
    │   │   ├── schema.py               # 读取并组合机器规则
    │   │   ├── knowledge.py            # 知识卡统一校验
    │   │   ├── indexes.py              # 逐层 index.md 导航条目的生成/比较
    │   │   ├── source_resources.py     # 文档归档与固定源码的来源解析及只读验证
    │   │   └── checks/                 # 路径、平台、来源、正文、链接、生命周期、导航、日志等检查
    │   │       └── …
    │   └── specs/                      # 知识系统治理规范；不是业务 SDD spec/design 存档
    │       ├── okf.md                  # Bundle、Concept 和 OKF 边界
    │       ├── paths.md                # 分类路径与导航约定
    │       ├── frontmatter.md          # 字段语义、来源、生命周期与复核事件
    │       ├── schemas.md              # 机器契约分工及校验规则
    │       └── skills.md               # Ingest/Query/Lint 等技能的输入输出与权限契约
    ├── .agents/
    │   └── skills/                     # [G] 知识技能规范源；不属于 cannbot-skills 工程技能仓
    │       ├── knowledge-query/         # 检索与按需审计；SKILL.md、modes/、references/ 等
    │       │   └── scripts/
    │       │       ├── knowledge_query.py # 查询入口
    │       │       ├── knowledge_index.py # 索引构建/验证入口
    │       │       └── retrieval/       # 知识根定位、SQLite 索引及词项检索实现
    │       ├── ascendc-api-knowledge-query/ # SKILL.md + references/、scripts/，复用 Query
    │       ├── knowledge-ingest/        # 统一生产和修订；SKILL.md、references/ 等
    │       │   └── scripts/
    │       │       ├── knowledge_ingest.py # 建卡、同步导航及生产收尾
    │       │       ├── knowledge_graph.py  # 从卡间已有链接派生图
    │       │       ├── source_resources.py # 恢复固定源码证据
    │       │       ├── fixed_archive_docs.py # 官方归档受控转换
    │       │       └── …
    │       ├── knowledge-lint/          # SKILL.md + references/、scripts/，共享契约检查
    │       ├── ops-knowledge-vv-ingest/ # SKILL.md + references/、templates/，源码级 Operator 生产
    │       ├── ops-knowledge-cv-ingest/ # SKILL.md + references/、templates/，另一算子计算路线的生产
    │       └── ops-knowledge-trace-ingest/ # SKILL.md + references/、scripts/，仓内 trace → Runbook
    ├── .claude/
    │   └── skills                      # [G] 链接 → ../.agents/skills，客户端适配，不是另一技能真源
    ├── .opencode/
    │   └── skills                      # [G] 链接 → ../.agents/skills
    ├── docs/                           # [G] 系统说明，禁止成为第二份领域事实库
    │   ├── design_principles.md         # 知识系统设计原则
    │   ├── installation_and_usage.md   # 安装和使用指南
    │   └── figures/                    # 系统说明图，非知识卡来源图仓
    │       └── cannbot-repo-map.png
    ├── recipes/                        # [G] 场景化实践，引用规则与 Skill，不另定义强制规则
    │   ├── answer_with_evidence.md      # 有证据的回答
    │   ├── api_search.md                # API 查询
    │   ├── contribute_knowledge.md      # 贡献知识
    │   └── operator_development.md     # 开发时消费知识
    ├── evals/                          # [G] 检索、治理、来源恢复、安装及文档回归；当前为平铺文件
    │   ├── retrieval_cases.yaml        # 检索案例
    │   ├── run_retrieval.py             # 检索回归执行
    │   └── test_*.py                    # 各类接受/拒绝与回归测试
    ├── logs/                           # [G] YYYY-MM-DD.md：已发生的知识/治理变更，不是原始会话
    │   └── …
    ├── artifacts/                      # [L] 本地派生产物，不提交，不作为知识正文真源
    │   ├── indexes/                    # 本地实装已经生成
    │   │   └── knowledge.sqlite3       # 卡片、词项 posting、指纹与索引元数据
    │   └── graphs/                     # 按需定义；本地当前未生成
    │       └── …                       # 卡节点与 links_to 边的 JSON/HTML 派生图
    ├── .build/                         # [L] producer 按需暂存；本地当前未生成
    │   └── ops-knowledge-trace-ingest/
    │       └── <日期>/<trace_id>/…      # 候选 DRAFT、manifest、reconstruction 等，不直接当正文
    ├── .gitcode/                       # [G] 社区贡献入口与质量门禁
    │   ├── workflows/
    │   │   └── cannbot-knowledge_actions.yml
    │   ├── scripts/
    │   │   ├── knowledge_check.sh       # 知识检查编排
    │   │   ├── content_check.py         # 内容检查
    │   │   ├── format_check.py          # 格式检查
    │   │   └── graph_check.py           # 链接图检查
    │   ├── ISSUE_TEMPLATE/             # 知识需求/错误及其他贡献模板
    │   │   └── …
    │   └── PULL_REQUEST_TEMPLATE/
    │       └── PULL_REQUEST_TEMPLATE.md
    └── …                               # Git 元数据、许可证及通用开发缓存等省略
```

图中 `knowledge/` 的目录来自本地冻结 Git 路径树。每个知识目录都有 `index.md`；为避免重复，部分目录把它合并在 `…` 中。`graph`、`runtime`、`pypto`、`tilelang` 的 index-only 状态是当前内容观察，不能从分类注册或产品源码存在推导知识覆盖。[正文边界 AGENTS.md:7](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/AGENTS.md:7)、[路径与占位语义 paths.md:34](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/specs/paths.md:34)

知识文件名不决定卡类型。例如 API 树中的 `glossary.md` 不应仅因名字就被移到另一目录；路径 Profile 和 Frontmatter `type` 由共享契约约束。当前注册的 Profile 还包括 `interoperability`、`glossaries`，但注册不等于当前已经创建对应目录。[Profile 定义](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/schemas/profiles.yaml:22)、[分类与类型区别](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/AGENTS.md:8)

| 图中区域 | 核对依据 |
|---|---|
| 工程技能和依赖安装 | [cannbot.js:448](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/script/bin/cannbot.js:448)、[公共技能 gitlink 配置](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/.gitmodules:1) |
| 项目知识入口、配置和链接 | [install.sh:772](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:772)、[install.sh:808](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:808)、[install.sh:892](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:892) |
| raw 来源及固定源码工作树 | [registries.yaml:85](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/schemas/registries.yaml:85)、[恢复实现 source_resources.py:36](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-ingest/scripts/source_resources.py:36) |
| 共享规则与设施职责 | [README.md:86](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/README.md:86)、[AGENTS.md:29](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/AGENTS.md:29) |
| SQLite 索引和词项表 | [retrieval/index.py:37](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-query/scripts/retrieval/index.py:37)、[retrieval/index.py:222](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-query/scripts/retrieval/index.py:222) |
| 按需图谱和 trace 暂存 | [schemas.md:69](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/specs/schemas.md:69)、[trace SKILL.md:163](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/ops-knowledge-trace-ingest/SKILL.md:163) |

## 3. raw 究竟哪些在知识仓内，哪些在外

| 材料 | 最终位置 | 与知识正文/Git 的关系 |
|---|---|---|
| 官方 docs/examples 资源归档 | `K/cann-docs-raw/` | K 内、Bundle 外、Git 忽略；按来源组件布局，不是 raw0/raw1 双层体系 |
| 四个登记仓的固定源码证据 | `K/cann-ops-raw/ascendc/<repo>/<40位commit>/` | K 内、Bundle 外、Git 忽略；独立对象缓存与固定工作树 |
| 下载 tar 包、解压中间目录 | `${TMPDIR:-/tmp}/cannbot-docs.XXXXXX/` | 默认在系统临时区，`TMPDIR` 可改变位置；最终把恢复内容移回 K 并清理临时区 |
| 当前业务开发源码 | `P/` 或调用方指定的其他组件仓 | 开发工作树，按自己的仓规则管理，不是 raw 缓存 |
| 工程插件依赖源码 | `P/.cannbot/dependencies/<plugin>/<repo>/` | K 外；供工程技能使用，不能视为卡片固定来源版本 |
| registry 任务研究参考源码 | `W/requirements/references/{cann,ascend,competitor}/` | 任务 W 内、K 外；用于本次需求/公式/实现分析 |
| 原始开发会话/轨迹 | 工作流、客户端原生日志或调用方提供的输入路径 | 没有统一规定全部搬进 K/raw；trace producer 另做规范化、候选和审查 |

以上位置由资源脚本、Registry、安装器和工作流分别定义。[临时下载与最终搬回](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/get_resources.sh:108)、[工程依赖根](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/script/bin/cannbot.js:448)、[任务研究源码](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-registry-invoke/workflows/op-develop.yaml:73)、[轨迹输入范围](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/ops-knowledge-trace-ingest/SKILL.md:155)

`cann-docs-raw` 使用持续更新的官方归档，完成标记记录 URL 和准备时间，并不固定归档内容哈希；源码证据则固定到 Registry 登记的 40 位 commit，并检查来源远端、HEAD 和工作树洁净状态。这两类来源的版本保证不同。[资源契约](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/specs/skills.md:85)、[固定源码验证](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/contracts/source_resources.py:115)

## 4. spec、design、task 的位置与另一种 Workspace 变体

工程任务的需求、规格、设计和执行记录不属于 `K/knowledge/`。`governance/specs/` 是知识系统自己的治理规范，与业务 SDD 的规格原件不同。

`ops-direct-invoke` 默认把每轮输入、方案、报告和交付件放在 `P/.cannbot/<任务>/workflowN/`；任务可以显式声明将最终代码、测试或文档交付到项目路径。它没有要求所有插件统一使用 `spec.md/design.md/tasks.md` 三个文件名。[direct 工作目录契约](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-direct-invoke/AGENTS.md:32)

`ops-registry-invoke` 的预检节点则定义了**将完整 K 放进本轮 W 内**的另一种布局。下图是工作流合同，不能当成本地 direct 实装已经生成的任务结果：

```text
<本轮 WORK_DIR W>/                       # [R] 由调用方/harness 指定
├── cannbot-knowledge/                   # 完整 K，不是只复制 knowledge/
│   ├── knowledge/…                     # 只读消费，共享卡不被任务改写
│   ├── cann-docs-raw/…                  # 资源准备后恢复，仍在 K 内
│   ├── cann-ops-raw/…                   # 固定源码证据，仍在 K 内
│   ├── governance/…                    # 与技能同版本的共享规则
│   ├── .agents/skills/…
│   ├── artifacts/
│   │   ├── indexes/knowledge.sqlite3
│   │   └── preflight.md                 # 本轮消费摘要，引用卡路径，不是共享知识卡
│   └── …                               # 完整 K 的其余设施同第 2 节
├── requirements/
│   ├── REQUIREMENTS.md                  # 本次需求分析原件
│   ├── references/
│   │   ├── cann/…                       # CANN 参考实现源码
│   │   ├── ascend/…                     # Ascend 生态参考源码
│   │   └── competitor/…                 # 其他框架参考源码
│   └── research/
│       ├── cann/
│       │   ├── code_walkthrough.md      # 既有实现调用链研究
│       │   ├── code_design.md           # 既有实现设计分析，不是本次待实现设计
│       │   └── formula.md               # 从既有实现提取公式
│       └── …
├── spec/
│   └── spec.yaml                        # 本次结构化工程规格
├── design/
│   ├── INDEX.md                         # 本次设计组织入口，不是知识 Bundle 的 index.md
│   ├── Overview.md                      # 本次功能、定义、公式和数值语义
│   └── branches/…                       # 实现分支设计
├── op/…                                 # 本次算子源码包，内部省略
├── .workflow/…                          # 节点状态、日志及会话
└── …                                    # 测试、安装包和其他运行设施省略
```

工作流节点与 task 定义位于 Workflow YAML；本轮未发现一个要求所有任务额外生成 `tasks.md` 的通用契约。[registry 知识准备与只读约束](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-registry-invoke/workflows/op-develop.yaml:15)、[需求与研究原件](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-registry-invoke/workflows/op-develop.yaml:172)、[规格](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-registry-invoke/workflows/op-develop.yaml:209)、[设计](/E:/FactumCore/.scratch/cann-research-20260930/cannbot/plugins-official/ops-registry-invoke/workflows/op-develop.yaml:263)

**这些工程原件不会因工作流完成而自动进入知识 Bundle。** 可复用结论需要另行进入 Ingest 或相应 producer，形成符合 Profile、来源和适用范围要求的知识卡；trace producer 也只发布通过门禁和审查的 Runbook，不把整条会话、设计包或任务清单当作知识卡。[生产职责](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/specs/skills.md:3)、[trace 落库边界](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/ops-knowledge-trace-ingest/SKILL.md:51)

## 5. 规则、索引、消费和治理如何串起来

| 层次 | 真源/入口 | 职责与边界 |
|---|---|---|
| 业务工程入口 | `P/AGENTS.md` | 插件流程和知识使用入口；按技能执行，不把所有领域知识塞进入口文件 |
| 知识根定位 | `P/.cannbot/knowledge.env` | 指向完整 K；不是源码仓—架构元素—知识实体—符号的统一映射表 |
| 仓级规则指针 | `K/AGENTS.md` | 规定 Bundle 边界、任务范围及各规则真源的位置 |
| 机器规则 | `K/governance/schemas/` + `contracts/` | Ingest、Query、Lint 共用，不由每个 Skill 再维护一套 |
| 人读导航 | `K/knowledge/**/index.md` | 逐层分类和卡片入口；不作为检索卡，也不作为图节点 |
| 机器检索索引 | `K/artifacts/indexes/knowledge.sqlite3` | 从合法卡片构建 SQLite 词项检索索引；不是向量库，也不是源码调用图 |
| 关系派生图 | `K/artifacts/graphs/` | 仅将卡片作为节点、已有卡间 Markdown 链接作为 `links_to`；不包含源码/导航节点 |
| 内容及规则变更记录 | `K/logs/YYYY-MM-DD.md` | 记录已经发生的操作；不代替原始 trace，也不作为机器规则源 |

机器检索收录 `knowledge/` 下除 `index.md` 外的 Markdown 卡，保存结构字段、正文、词项 posting 和指纹。Query 默认按 `stable` 等条件过滤后返回候选，Agent 再打开完整卡片、核对范围与来源；索引缺失或陈旧时停止，不在只读查询中偷偷重建。索引只是定位证据，平台支持、版本适用和技术结论仍需内容核验。[索引输入及实现](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-query/scripts/retrieval/index.py:175)、[Query 契约](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/governance/specs/skills.md:25)

```text
消费：P/AGENTS → 知识 Query 入口 → knowledge.env 定位 K
      → SQLite 候选 → 完整知识卡 → 按需核验原始文档/固定源码 → 带证据回答

生产：登记来源或真实任务轨迹 → Ingest/专项 producer → 候选与内容核验
      → 同步导航/日志 → 全库 Contract/Lint → 重建索引、目标 Query 与相关回归
      → 准备 PR → committer 评审合入

规则：schemas + registries + contracts 同时约束生产、查询和 lint
      governance/specs 解释规则，Skill 执行流程，evals/CI 验证规则
```

生产链表示 Agent/维护者执行的外层贡献流程，不是一个脚本自动完成建卡、发布和合入。Ingest 的创建步骤本身不更新导航和日志，统一收尾与检索验证还需按任务执行，外部提交须遵循贡献规则。[Ingest 收尾](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-ingest/SKILL.md:38)、[贡献边界](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/CONTRIBUTING.md:39)

查询本身不直接回写知识；新发现和纠错重新进入生产流程。通用卡通常蒸馏结论，登记官方 API/Guide 页是受控正文镜像的例外。`stable`、来源记录和实际复核事件分别表达不同事实，Lint 通过不等于内容结论已验证。[写入和来源纪律](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/AGENTS.md:45)、[只读 Query](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/.agents/skills/knowledge-query/SKILL.md:73)

## 6. 本地实物与证据版本

实际安装目标为 [本地 workspace](/E:/FactumCore/.scratch/cann-research-20260930/workspace/README.md)，完整 K 为 [本地知识仓](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/README.md)。这次实装已具备工程插件、37 个有效技能入口、3 个工程角色、4 个依赖仓、知识配置、raw 恢复资源和 Query 索引；通过项目配置查库已成功。**没有执行完整算子开发/NPU 验收，任务目录及业务 spec/design 不应标成已产出。** 详细检查见 [verification.json](/E:/FactumCore/.scratch/cann-research-20260930/workspace/inspection/verification.json)。

知识安装的默认 consumer 为 2 项查询技能，contributor 为 6 项；第 7 项 trace producer 保留在知识仓内。完整 K 可以与项目同级，也可以由独立/远程安装器默认放在 `~/.cannbot/cannbot-knowledge`，项目仅通过配置及链接使用。[安装模式](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:808)、[默认外置位置](/E:/FactumCore/.scratch/cann-research-20260930/cannbot-knowledge/install.sh:214)

知识仓 Git 中的 `.claude/skills`、`.opencode/skills` 和 `CLAUDE.md` 是符号链接；本地 Windows checkout 将这些 Git 链接保存为目标文本文件。实际业务工程安装的知识技能采用目录 junction，不能把 checkout 中的文本文件误称为已经可用的客户端链接。当前实装的工程技能采用上游支持的打包复制模式，知识技能保持连接完整 K。[本地安装方式记录](/E:/FactumCore/.scratch/cann-research-20260930/workspace/README.md:36)

| 官方仓 | 本地冻结提交 |
|---|---|
| [cannbot](https://gitcode.com/cann/cannbot/tree/918af01713a6ba074512e57ea1a431f1c5702b0e) | `918af01713a6ba074512e57ea1a431f1c5702b0e` |
| [cannbot-knowledge](https://gitcode.com/cann/cannbot-knowledge/tree/e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35) | `e7c4942d27aa753cf0a98a1a3edf56aa1e4c8c35` |
| [cannbot-skills 独立检出](https://gitcode.com/cann/cannbot-skills/tree/94216ba2f0b569cfad22c7794ad99426a07ab7b6) | `94216ba2f0b569cfad22c7794ad99426a07ab7b6` |
| cannbot 锁定的 vendor 技能子模块 | `9ae606b331085597f05b67cfa165f2dcd3369a2e`，与独立检出的 HEAD 不同 |

后续对齐时，应把整个 K 对应到我们的 `aiot-knowledge`，把其中 `knowledge/` 对应到 `llmwiki/` 正文层。raw0/raw1、组件规范 SSOT、WiFi 跨仓代码与实体映射是我们自己的明确设计，不能因为名称相似就宣称上游具备同一套布局和职责。
