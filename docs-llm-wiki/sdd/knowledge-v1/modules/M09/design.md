# M09 Skills/Workflow与部署验收：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M09 Skills/Workflow 与部署验收 | 四个 hs-common Skill、两个 Workflow、merge-stage；入口说明、使用/维护、evals | 生产 P1–P5、治理 G1–G9、消费 C1–C7 阶段日志/交接摘要；安装适配与 acceptance runner | 编排 M01–M08，不复制引擎。全局可见 Skill 的选择与触发须在目标宿主实测，不保证每个宿主必触发；用户级 AGENTS 由用户自行配置，不属于产品托管范围；部署与外部授权由真实环境验证 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `AGENTS.md` | F | 写清目录归属、知识入口、代码/raw 来源边界、Skill/Workflow 完整标识、发布授权与局部 AGENTS 阅读顺序 | 仓内会话能找到唯一配置与领域入口；仓外发现后读取同一入口；不存在重复或相互冲突的路由规则 |
| `skills/common/knowledge/hs-common-workspace-explore/SKILL.md` | F | 元数据围绕分析/排障/设计/审查/修改代码及路径触发；正文调用 `project resolve`，读取实际入口并形成两阶段绑定 | 仓外只给路径能隐式选择；换仓重绑；无知识关联不虚构成功，仍允许原任务的授权源码分析 |
| `skills/common/knowledge/hs-common-workspace-explore/references/project-binding.md` | F | 列出确定性解析顺序、ProjectContextReceipt 字段、缓存键和所有失败分支；与 workspace.py 输出逐项对应 | 仅列文件或自报已读不能升级；配置/权限/入口变化使旧绑定失效；压缩恢复后可核验引用，否则重绑 |
| `skills/common/knowledge/hs-common-knowledge-ingest/SKILL.md` | F | 按任务选择代码或 raw 文档 reference，调用 source/document/ingest 命令；解释 plan 与变更包后交治理 Workflow | 两种来源能生成确定 final-view；失败不触碰正式卡；重复 apply 幂等且不重复生产 |
| `skills/common/knowledge/hs-common-knowledge-ingest/references/code-producer.md` | F | 定义模块边界、调用/注册/回调、宏与构建闭包，跨 Host/Device 证据清单和 code_gate 选择 | 缺接收侧/宏/配置时只产片段或缺口；共享文件不自动证明三个芯片；图版本冲突回源码核验 |
| `skills/common/knowledge/hs-common-knowledge-ingest/references/raw-document-producer.md` | F | 指导选择明确原件、固定版本、提取定位、比较旧卡和制作人工确认包，调用 document capture/update-plan | 本地原件可形成带页/章节证据的候选；外链/路径绕出被拒绝；变化中的文件重取；无确认不生效 |
| `skills/common/knowledge/hs-common-knowledge-lint/SKILL.md` | F | 按 local/merge 模式加载对应 reference，调用同一 checks 实现，解释 fail/incomplete/expired 的返回路径 | 本地和 CI 对同一规则产生一致诊断；输入检查前后摘要相同；纯文档任务不触发代码门禁 |
| `skills/common/knowledge/hs-common-knowledge-lint/references/local-check.md` | F | 说明 Schema/Profile、来源、scope、断言证据、关系闭合、导航和基线检查，输出 LocalCheckRecord | 有效 final-view 取得匹配记录；改一处字节/来源/scope 后旧记录失效；lint 自身不移动文件 |
| `skills/common/knowledge/hs-common-knowledge-lint/references/merge-check.md` | F | 固定 H/B/T/V，说明受信政策、逐断言复用/继承/重验、证明过期与外部证据归档 | 新代码与断言冲突时失败退回本地；必需代码不可访问为 incomplete；无输入改写；错误 head 的报告拒绝 |
| `skills/common/knowledge/hs-common-knowledge-query/SKILL.md` | F | 加载 query-plan，调用 index/query/source 能力；按问题路由到卡片、原文或代码 | 回答有渠道、范围、卡与来源版本；无覆盖/过期明确缺口；查询不会修改知识正文 |
| `skills/common/knowledge/hs-common-knowledge-query/references/query-plan.md` | F | 定义 current/guidance/historical、预算、候选后精读、逐断言证据和输出前事件复查 | 错 Target/侧别不能挤占正确候选；切代后精读仍一致；阻断事件立即影响旧代查询 |
| `workflows/common/hs-common-knowledge-ingest/SKILL.md` | F | 按 §4.2 定义 P1 绑定、P2 固定来源、P3 比较计划、P4 候选及 P5 摘要交接；按代码/raw 路径调用 ingest Skill | 两来源均产可复核最终包；交接摘要可核验；缺口保留；相同输入恢复不重复生成或改变候选 |
| `workflows/common/hs-common-knowledge-lint/SKILL.md` | F | 按 §4.3 定义 G1 接收、G2C/G2D 分流、G3 apply、G4 索引、G5 授权提交，及独立 G6–G9 检查/合入/发布交接 | 人工未答不应用；检查失败回生产修订；本地 stable 可查；上库失败不撤销本地生命周期；不擅自提交 |
| `workflows/common/hs-common-knowledge-lint/references/merge-stage.md` | F | 固定受信 H/B/T/V/政策/工具，调用 lint merge，保存外部证明；列出 committer 合入与授权 shared 构建的独立职责 | CI 输入输出隔离；过期或不同 head 拒绝；纯文档不注册必需代码 lint 状态；合入内容与确认证明一致 |
| `aiot-wifi-knowledge/AGENTS.md` | F | 写清资产地图、阅读顺序、三条链路入口与修改边界 | 从领域根开始任务可找到正确入口且不批量读取全仓 |
| `aiot-wifi-knowledge/README.md` | F | 汇总部署步骤、六 Target 登记状态及可运行命令；链接详细运维文档 | 首次使用者可完成最小安装；所有入口链接可解析 |
| `aiot-wifi-knowledge/CONTRIBUTING.md` | F | 分别写代码卡两道检查、raw 文档人工确认、框架变更审查流程 | 代码/文档各按说明完成一次合成贡献，证据和最终字节对应 |
| `aiot-wifi-knowledge/.gitignore` | F | 排除 .build、artifacts、临时锁和敏感本机配置；保留应评审的卡、治理与必要记录 | 临时索引不被误提交，ManualReviewRecord 等必要记录仍可按范围纳入评审 |
| `aiot-wifi-knowledge/logs/workflows/<workflow_run_id>.json` | R | 记录类型/版本、operation、parent_run、阶段输入输出摘要及暂停原因 | 中断后从实际完成阶段恢复，不重复 apply/提交 |
| `aiot-wifi-knowledge/evals/AGENTS.md` | F | 声明只读公开/合成输入及实际运行记录 | 执行轨迹没有 gold/其他组材料 |
| `aiot-wifi-knowledge/evals/README.md` | F | 链接用例、夹具、命令、预期及结果记录方式 | 可按说明重跑合成验收并识别未测范围 |
| `aiot-wifi-knowledge/evals/run_acceptance.py` | F | 调共享 CLI，在隔离临时领域根执行用例并输出实际结果 | 同输入有确定断言，失败有可定位证据 |
| `aiot-wifi-knowledge/evals/cases/production.json` | F | 定义原件、代码、查重、候选及交接正反例 | 六决策及 raw 控制文件排除均有结果 |
| `aiot-wifi-knowledge/evals/cases/governance.json` | F | 定义代码 local/merge 与人工文档确认场景 | stable 本地可用、错 head/陈旧确认不可复用 |
| `aiot-wifi-knowledge/evals/cases/consumption.json` | F | 定义中文双字/符号、硬过滤、去重/短语及代次样例 | 受阻断 Claim 无分数/摘要泄漏，旧代精读一致 |
| `aiot-wifi-knowledge/evals/cases/scope.json` | F | 用合成宏、配置和协议版本构造错芯片/错侧/缺侧例 | 每一槽及 pair 都有正反例，unknown 不扩大适用 |
| `aiot-wifi-knowledge/evals/cases/recovery.json` | F | 在各写入/激活阶段注入中断并模拟外部编辑 | 旧完整代或新完整代可用，journal 可恢复且不丢修改 |
| `aiot-wifi-knowledge/evals/fixtures/workspace/config.yml` | F | 配置六逻辑槽/三候选 pair 和临时源路由 | 解析成功，换错 chip/side 时拒绝错误关联 |
| `aiot-wifi-knowledge/evals/fixtures/raw/sample.md` | F | 给章节、版本、附件引用和可修改段落 | 更新后生成可解释章节差异并等待人工确认 |
| `aiot-wifi-knowledge/evals/fixtures/cards/sample-flow.md` | F | 给 Claim、条件组、来源和单侧/跨侧边界 | 能覆盖缺侧、替代和逐 Claim 失效用例 |
| `aiot-wifi-knowledge/evals/fixtures/code/host.c` | F | 含发送入口、条件宏和消息 ID | 宏裁剪/消息 ID 改变触发对应 Claim 影响 |
| `aiot-wifi-knowledge/evals/fixtures/code/device.c` | F | 含分发/回调/接收及不兼容版本例 | 缺注册/版本冲突例返回 partial/incomplete |
| `aiot-wifi-knowledge/docs-llm-wiki/design_principles.md` | F | 由详设提炼核心不变量与修改入口 | 原文/正文/索引、两种确认及只读 CI 可区分 |
| `aiot-wifi-knowledge/docs-llm-wiki/installation_and_usage.md` | F | 写框架版本、配置、全局入口、三链路命令和故障例 | 新环境可完成合成端到端且不需手动 bootstrap |
| `aiot-wifi-knowledge/docs-llm-wiki/maintenance.md` | F | 写事件、双进度、备份、journal、重建、回滚、授权撤销与升级 | 运维按文档恢复中断操作并重建同身份可用代次 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
