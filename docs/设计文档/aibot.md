# 5 AIoTBot架构

AIoTBot架构是基于对保密区 AIoT 业务开发环境、业界优秀实践（cannbot-skills / openharmony-skills / hibot-skills / cannbot-knowledge）、各个领域业务管理差异以及为了进行能力共建共用的目的综合分析得出。架构横向为Skills层和knowledge层、纵向为Tool 工具层。

## 5.1 AIoTBot架构图

（图：AIoTBot 整体架构图，原图略）

AIoTBot架构横向包含两个大层，分别是Skills层和knowledge层；纵向为Tool工具层，用于管理Skills资源以及harness工程控制。AIoTBot 核心组件如下：

| 层 | 核心组件 | 定位 |
|----|----------|------|
| Skills层 | Atomic Skill | 解决一个明确能力点的最小能力单元 | 
| Skills层 | Workflow Skill | 串联多个 atomic skill，定义阶段、输入输出、失败回退、验收证据 |
| Skills层 | SubAgent | 专注特定领域或复杂任务的专业执行者 | 
| Skills层 | Team | 协调多个 Skill 与 SubAgent 的协同作战单元 | 
| Skills层 | Hook | harness 工程钩子：事件监听、权限守卫 | 
| Knowledge层 | 领域知识库 | 各领域独立建设管理的知识仓 |
| Knowledge层 | 知识卡 | 知识正文的最小单元（结论 + 溯源） | 
| Knowledge层 | 流程技能 | knowledge-ingest / knowledge-lint/knowledge-query |
| Tool层 | aiotbot-tools | Skills 资源管理、版本管理、harness 工程管理 |

### 5.1.1 Skills 层

Skills层当前阶段采用 Atomic Skills + Workflow Skills + SubAgent + Team 四层架构方式，配合 Hook 实现 harness 工程控制，组件由 aiotbot-skills 仓承载。

- **Atomic skill** 解决一个明确能力点的最小能力单元。一段能被多个 agent 工具复用的能力放在一个目录里，核心是 `SKILL.md`，再配上可选的使用指导和辅助文件。
- **Workflow skill** 串联多个 atomic skill，定义阶段、输入输出、失败回退、验收证据，将分散的能力点编排为完整流程。公共工作流（sdd 规格驱动开发、test-design 测试设计）和领域工作流分别在 `workflows/common/` 和 `workflows/domain/` 下管理。
- **SubAgent** 专注特定领域或复杂任务的专业执行者。它封装了垂直场景下的深度能力，如代码生成、数据分析或特定硬件调试，通过接收高层指令并返回高质量结果，实现能力的专业化分工与复用。SubAgent 和 Team 统一存放在 `agent/` 目录下。
- **Team** 协调多个Skill与SubAgent的协同作战单元。它模拟人类团队协作模式，负责任务拆解、角色分配、状态同步及冲突解决，将复杂问题转化为多智能体并行或串行工作流，确保最终交付物的完整性与一致性。
- **Hook**：承载 harness 工程钩子，包括公共领域钩子和领域钩子，当前阶段未展开分析，未来可以进行扩展。可参考 cannbot-skills 的 hooks 设计，在工具执行前拦截写操作、按角色限制可写路径，实现权限防护。

Skills根据功能特点可以分为IPD研发流程生命周期的技能、公司业务通用技能、领域技能三种类型。相关技能需要遵守本文中的规范。

- 生命周期的技能：需求、设计、开发、测试、CI/CD、问题排查等完整研发生命周期的技能。在领域间共享，由技能owner管理。
- 公司业务通用技能：根据公司的业务特点，形成的特有技能，比如代码小型化优化、代码高性能优化、ROM化、安全编程等技能。在领域间共享，由技能owner管理。
- 领域技能：WiFi、BGLE、定位、雷达、SLP、NFC、NPU、MCU、平台、IR、显示、音频、媒体、视频等核心领域专用技能。在领域内部单独管理。

### 5.1.2 Knowledge 层

Knowledge层采用知识卡片的方式管理 AIoT业务 相关知识库，给出知识库的目录架构、卡片契约、来源治理和消费/增量维护规范。

**领域知识库**：知识库在领域内部单独管理。领域知识库可以独立建仓，或者直接放在代码仓中，建议独立建仓管理。一个领域一个仓，由各领域独立建设，管理内容和权限。知识仓内部框架目录基本相同，技能跨仓复用零适配。知识库可以参考aiotbot-knowledge-wifi案例，知识仓库举例：

- aiotbot-knowledge-wifi: wifi领域知识库。
- aiotbot-knowledge-bgle: bgle领域知识库。
- aiotbot-knowledge-gnss: gnss领域知识库。

**知识卡**：知识正文的最小单元，是知识库中唯一参与检索的对象。按"读者带着什么问题来"切分为实体卡、流程卡、协议卡、规范卡、命令卡、诊断卡、术语卡七类；卡片只写"结论 + sources 指针"，不复制原文段落，被指向的原始材料统一落在 `docs-raw/`。

**流程技能**：知识库的"操作说明书"，不装任何领域事实，可跨领域知识仓复用。

### 5.1.3 Tool 工具层

Tool 工具层由 aiotbot-tools 承载，包含以下功能，未来可以进行功能扩展：

- **Skills 资源管理**：负责 skill 的中心库与货架分离、挂载与分发、开关与分组机制，实现"资产即 skill"的准入、分发和迭代闭环。
- **版本管理**：负责 skills 仓、tools 仓的导入、升级和版本一致性管理，保证多 agent、多宿主下技能版本可追溯、可回退。
- **harness 工程管理**：负责 harness 工程（hooks、agent、workflow 等）的资源组织与工程控制，为 Skills 资源提供运行期支撑。

## 5.2 AIoTBot skills目录架构

aiotbot-skills技能仓目录结构如下所示。

- skills：存放Atomic Skills，包括三方技能、公共领域技能、领域技能。
- workflows：存放Workflow Skills，包括公共领域技能、领域技能。
- hook：存放harness工程钩子，包括公共领域钩子、领域钩子。当前未展开分析，未来可以进行扩展。
- agent：存放subagent 和 team。

```
skills/
  third-party/
  common/           # 公共 Skills，面向跨领域、跨子系统、跨团队复用的通用能力
    requirements/   #   需求阶段
    design/         #   设计阶段
    fulldesign/     #   全量设计阶段
    development/    #   开发阶段
    testing/        #   测试阶段
    cicd/           #   CI/CD 阶段
    troubleshooting/ #   问题排查阶段
    codesize/        #  codesize优化
    rom/             #  rom化技能
    knowledge/      #  知识技能
  domain/           # 领域 Skills，面向具体框架、子系统或技术域的专用能力，内部可再细分
    platform/       #   platform子系统
    wifi/           #   WiFi 子系统
    bgle/           #   bgle 子系统
    gnss/           #   定位 子系统
    slp/            #   slp 子系统
    radar/          #   radar 子系统
    nfc/            #   nfc子系统
    npu/            #   npu子系统
    mcu/            #   mcu子系统
    kernel/         #   内核 子系统
workflows/          # 工作流定义
  common/           # 公共 工作流，面向跨领域、跨子系统、跨团队复用的通用能力
    sdd/            # SDD规格驱动开发
    test-design/    # 测试设计工作流
  domain/           # 领域 工作流，面向具体框架、子系统或技术域的专用能力，内部可再细分
    platform/       #   platform子系统
    wifi/           #   WiFi 子系统
    bgle/           #   bgle 子系统
    gnss/           #   定位 子系统
    slp/            #   slp 子系统
    radar/          #   radar 子系统
    nfc/            #   nfc子系统
    npu/            #   npu子系统
    mcu/            #   mcu子系统
    kernel/         #   内核 子系统
hook/               # 钩子定义
  common/         # 公共 钩子，面向跨领域、跨子系统、跨团队复用的通用能力
  domain/           # 领域 钩子，面向具体框架、子系统或技术域的专用能力，内部可再细分
    platform/       #   platform子系统
    wifi/           #   WiFi 子系统
    bgle/           #   bgle 子系统
    gnss/           #   定位 子系统
    slp/            #   slp 子系统
    radar/          #   radar 子系统
    nfc/            #   nfc子系统
    npu/            #   npu子系统
    mcu/            #   mcu子系统
    kernel/         #   内核 子系统
agent/               # agent定义
common/         # 公共 agent，面向跨领域、跨子系统、跨团队复用的通用能力
domain/           # 领域 agent，面向具体框架、子系统或技术域的专用能力，内部可再细分
  platform/       #   platform子系统
  wifi/           #   WiFi 子系统
  bgle/           #   bgle 子系统
  gnss/           #   定位 子系统
  slp/            #   slp 子系统
  radar/          #   radar 子系统
  nfc/            #   nfc子系统
  npu/            #   npu子系统
  mcu/            #   mcu子系统
  kernel/         #   内核 子系统  
docs/             # 公共文档定义
scripts/          # 公共管理脚本定义、安装、检查、升级、插件等
LICENSE             # 版权说明
README.md           # 项目介绍
aiot-skills-namespace-and-placement-spec.md # aiot Skills 命名空间与目录放置规范，入库前必须遵守
```

## 5.3 AIoTBot knowledge目录架构

aiotbot-knowledge知识库仓目录结构如下所示。

- skills/common/knowledge/：存放知识库相关 Skills
- AGENTS.md：会话入口，消费路由契约
- config.yml：四张映射表，把代码仓、架构元素、领域知识实体、符号别名集中登记为一份配置事实
- main/：真实代码工作区
- aiot-knowledge/：领域知识仓根，下一级是 domain，一领域一仓，内部目录完全同构
  - knowledge/：知识卡，唯一检索对象，处理后知识的仓库
  - docs-raw/：源文档，原始证据层（LLM 只读）
  - governance/：治理文件夹，存放契约，模板，规范等
  - .build/ · logs/ · evals/ · artifacts/ · docs-llm-wiki/：配套支撑层

```
skills/
└── common/
    └── knowledge/
        ├── knowledge-ingest/        # Agent 建卡、融合和统一收尾流程
        ├── knowledge-lint/          # 结构、来源检查与语义复核流程
        └── knowledge-query/         # 初版 SQLite 词面检索与索引工具
AGENTS.md                            # 入口：领域/流程路由、卡契约指针、config.yml 说明
config.yml                           # 代码仓 ↔ 架构元素 ↔ 领域知识实体 ↔ 符号映射
main/                                # 真实代码工作区
├── device/
│   ├── combo/ common/ datapath/ platform/ sensorhub/
│   └── wifi/
│       ├── chip-a/
│       │   ├── .codegraph/          # [新增]代码图谱db文件，本地生成不上库
│       │   └── …
│       ├── chip-b/
│       │   ├── .codegraph/          # [新增]代码图谱db文件，本地生成不上库
│       │   └── …
│       └── …
├── drivers/
│   ├── combo/ common/ datapath/ platform/ sensorhub/
│   └── wifi/
│       ├── .codegraph/              # [新增]代码图谱db文件，本地生成不上库
│       └── …
└── …
aiot-knowledge/
├── platform/                        # Platform 领域知识仓（结构同构，不展开）
├── bgle/                            # BGLE 领域知识仓（结构同构，不展开）
├── gnss/                            # GNSS 领域知识仓（结构同构，不展开）
├── slp/                             # SLP 领域知识仓（结构同构，不展开）
├── radar/                           # Radar 领域知识仓（结构同构，不展开）
├── nfc/                             # NFC 领域知识仓（结构同构，不展开）
├── npu/                             # NPU 领域知识仓（结构同构，不展开）
├── mcu/                             # MCU 领域知识仓（结构同构，不展开）
└── wifi/                            # WiFi 领域知识仓；以下展开内部结构
├── AGENTS.md                    # 知识边界、规则指针与技能入口
├── README.md                    # 定位、实际能力、资料导航
├── CONTRIBUTING.md              # 生产、核验和贡献流程
├── check.py / check.sh          # 结构、来源完整性及历史导入快照检查
├── docs-raw/                    # 知识所在的原始文档
│   ├── sources/                 # 来源登记表（md）：每条 = 链接 + 版本 + hash + 密级
│   │   ├── dbox                 # dbox设计文档，链接到dbox，与薪火平台共管理
│   │   ├── 3ms                  # 3ms文档，链接到3ms，与薪火平台共管理
│   │   └── wiki                 # wiki文档，链接到wiki，与薪火平台共管理
│   ├── conventions              # clean code、编码规范等，内部公开，上库git仓
│   ├── chips                    # 芯片相关文档，内部公开，上库git仓
│   ├── storys                   # 迭代设计文档，内部公开，上库git仓
│   ├── specs                    # sdd流程AI生成设计文档，内部公开，上库git仓
│   └── protocols                # 内部公开协议文档，内部公开，上库git仓
├── governance/
│   ├── AGENTS.md / index.md     # 共享治理维护规则与任务导航
│   ├── templates/               # 9类 draft 卡、目录导航、复核和维护记录模板
│   ├── sources.lock.yaml        # source → 声明版本/落点/hash/bytes/恢复说明；当前空锁
│   ├── schemas/
│   │   ├── frontmatter.schema.json
│   │   ├── sources.schema.json  # 来源锁字段形状
│   │   ├── profiles.yaml
│   │   └── registries.yaml      # 本地来源根等注册项
│   ├── contracts/               # knowledge、source_resources 与共享 validation
│   └── specs/                   # 共享契约及编写、复核、生命周期规范
├── knowledge/                   # 唯一知识正文根；
│   ├── AGENTS.md                # WiFi 领域规则，不虚构实际模块与 Target
│   ├── index.md                 # 当前仅入口，无技术卡；以下 Profile 随真实建卡创建
│   ├── concepts/                # 原理、机制及概念卡
│   │   ├── entities/            # 实体卡：模块/OPS/回调职责入口（dbox、storys、specs、chips 设计文档蒸馏）
│   │   ├── flows/               # 流程卡：跨仓消息、收发链路（dbox、storys、specs 设计文档蒸馏）
│   │   └── protocols/           # 协议卡：802.11 帧格式、状态机、计时器（协议蒸馏）
│   ├── rules/                   # 规范卡：编码规范、Clean Code、门禁约束（conventions 蒸馏）
│   ├── commands/                # 命令卡：维测命令语法、参数、典型输出、误用案例（wiki 蒸馏）
│   ├── runbooks/                # 诊断卡：现象→信号→根因→解法→边界→验证（wiki 经验蒸馏）
│   └── glossaries/              # 术语卡：组内黑话与缩写
├── .build/                      # ignored 转换、规范化、候选暂存，按需产生
├── logs/                        # 按日期记录已发生的导入与维护
├── docs-llm-wiki/               # LLM WIKI系统说明（design_principles / installation_and_usage）；禁止成为第二份领域事实库
├── evals/                       # 检索案例、回归执行与接受/拒绝测试
└── artifacts/                   # 本地派生索引、验证报告，Git 忽略

```
