# M01 契约与运行基础：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M01 契约与运行基础 | `S/__init__.py,cli.py,contracts.py,scope.py,receipts.py`；`K/governance/{schemas,contracts,templates,specs}/`；薄 check 包装 | `ContractBundle`、`Diagnostic`、`ResultEnvelope`；校验 config/card/source/record；`match_scope(Claim, QueryContext, EvidenceState)` 返回逐断言资格和原因 | 根模块。配置是 Target/pair 路由唯一真源，registries 只存公共枚举；纯解析不代表事实核验。导入、校验与诊断不写业务资产 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/__init__.py` | F | 导出工具版本、支持的 contract family/schema/index 版本和稳定 API；不导入运行时业务事实 | 单独导入不产生文件或连接；匹配版本可加载，不匹配报告兼容诊断 |
| `skills/common/knowledge/_shared/cli.py` | F | 参数解析后调用各模块；统一 schema_version、operation/request ID、status、artifacts、diagnostics 和退出码 | 所有命令支持机器 JSON 与可读摘要；无效参数无写入；失败退出码与信封一致 |
| `skills/common/knowledge/_shared/contracts.py` | F | 从 framework lock 与治理入口解析同版契约，校验摘要/兼容表，调用领域 contracts 的固定接口 | 同版加载一致；损坏/不兼容/未授权引用拒绝；本地与 CI 采用声明的可信契约 |
| `skills/common/knowledge/_shared/scope.py` | F | 展开配置登记；条件组内 AND、组间 OR；结合 purpose、review_mode、验证记录和有效性事件计算逐断言资格 | 错芯片/侧别/宏/快照不满足 current；缺一侧不证实端到端；一个芯片证明不传播至另两芯片 |
| `skills/common/knowledge/_shared/receipts.py` | F | 统一生成 ProjectContextReceipt、操作/人工/本地/合入/搜索记录的信封；检查自身摘要循环和外部证据引用 | 相同规范化输入摘要稳定；篡改载荷可发现；不匹配内容/上下文拒绝；持久证据丢失可诊断 |
| `aiot-wifi-knowledge/governance/AGENTS.md` | F | 说明声明规则、执行器、模板和记录归属 | 规则任务可找到版本、迁移和回归要求 |
| `aiot-wifi-knowledge/governance/index.md` | F | 逐项链接 Schema、Contract、模板及 specs | 路径完整，与实际受信规则版本一致 |
| `aiot-wifi-knowledge/governance/framework.lock.yaml` | F | 记录框架来源、固定 revision、工具/契约版本和摘要 | 版本不兼容失败关闭；可复现加载确切框架版本 |
| `aiot-wifi-knowledge/governance/schemas/frontmatter.schema.json` | F | 定义公共字段、七 Profile 枚举、条件与版本规则 | 缺必填/非法状态/失配 text_ref 给确定诊断；合法合成卡可解析 |
| `aiot-wifi-knowledge/governance/schemas/sources.schema.json` | F | 定义资源身份、字节摘要、恢复和提取结构 | 无 Git 快照不要求虚构 commit；缺摘要或不可恢复条件被正确报告 |
| `aiot-wifi-knowledge/governance/schemas/records.schema.json` | F | 以 record_kind 和 schema_version 区分记录并复用公共摘要字段 | 所有记录可判版本、来源及目标摘要，循环摘要样例被拒绝 |
| `aiot-wifi-knowledge/governance/schemas/workspace.schema.json` | F | 校验 config 与本机覆盖的结构及字段边界 | 缺 side/重复 Target/非法覆盖可诊断，unknown 配置不冒充接入成功 |
| `aiot-wifi-knowledge/governance/schemas/profiles.yaml` | F | 对 entity/flow/protocol/rule/command/runbook/glossary 写声明规则 | 各模板覆盖其 Profile；缺章节的代码卡有准确诊断 |
| `aiot-wifi-knowledge/governance/schemas/registries.yaml` | F | 注册 lifecycle、evidence_kind、relation、diagnostic、record_kind 等 | 枚举引用闭合，新增枚举须兼容声明与回归 |
| `aiot-wifi-knowledge/governance/contracts/__init__.py` | F | 仅导出受信模块和兼容信息 | import 无副作用、契约版本可查询 |
| `aiot-wifi-knowledge/governance/contracts/schema.py` | F | 编译 Schema/Profile/Registry，缓存绑定规则摘要 | 同版本可复现；损坏/未知版本明确失败 |
| `aiot-wifi-knowledge/governance/contracts/knowledge.py` | F | 对 final-view 及相关全库视图校验，输出结构诊断 | 重复 ID、失配锚点和缺章节可定位；输入摘要不变 |
| `aiot-wifi-knowledge/governance/contracts/sources.py` | F | 复用共享 sources 获取结果核锁、摘要、恢复和 locator | 原文字节、版本或 locator 不符能区分报错 |
| `aiot-wifi-knowledge/governance/contracts/scope.py` | F | 复用统一 scope 模块验证 Target、宏、构建和 pair | 六槽范围和三 pair 反例均正确排除 |
| `aiot-wifi-knowledge/governance/contracts/records.py` | F | 验 record_kind、输入/输出绑定、保留引用和信任来源 | 错 head、陈旧人工确认、缺证据包均不能作为有效证明 |
| `aiot-wifi-knowledge/governance/contracts/relations.py` | F | 校验 requires/derived_from/related_to/replacement 的目标、条件与环 | merge/split 后入口可达；断链、循环及越域引用可诊断 |
| `aiot-wifi-knowledge/governance/specs/scope.md` | F | 用六槽三 pair 合成例解释 AND/OR、宏、侧别和版本元组 | 共享代码、缺侧和错芯片反例都有明确处理 |
| `aiot-wifi-knowledge/governance/specs/records.md` | F | 解释各 record_kind、摘要、信任、过期和证据保留 | 清理临时产物后仍能审计已保留卡的确认/证明 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
