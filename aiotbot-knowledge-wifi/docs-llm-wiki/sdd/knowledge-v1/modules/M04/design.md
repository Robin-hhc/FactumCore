# M04 卡片与六决策：开发设计

## 接口与依赖

| 模块 | 文件 | 对外接口 | 依赖与边界 |
|---|---|---|---|
| M04 卡片与六决策 | `S/cards.py,changes.py` 的 plan/materialize；七类模板/正文导航；关系 Contract | `parse_card`、`plan_ingest`、`materialize` 返回 `Card/Claim`、六决策计划、`ChangeSet`、最终 stable 字节与 review-package | 依赖 M01/M03。只写 `.build/<operation_id>/`；no_change/defer 正常结束。业务语义来自证据和有说明的生产活动，不把字段解析当正确性证明 |

## 本模块拥有的文件与生成规则

| 路径 | 类别 | 开发动作 | 验收要求 |
|---|---|---|---|
| `skills/common/knowledge/_shared/cards.py` | F | 解析七 Profile、card/claim IDs、text_ref、scope、sources、relations；保存正文 span 和原始字节摘要 | 相同内容可重复解析一致；重复 ID、断锚、畸形元数据有定位诊断；span 可用于去重检索 |
| `aiot-wifi-knowledge/governance/templates/entity.md` | F | 含职责、边界、接口、依赖、证据及公共 frontmatter | 填合成内容后匹配 entity Profile |
| `aiot-wifi-knowledge/governance/templates/flow.md` | F | 含起终点、步骤、调用/消息、异常、条件和分侧证据 | 缺 Device 证据的样例仅得出 Host 片段结论 |
| `aiot-wifi-knowledge/governance/templates/protocol.md` | F | 含机制、字段/状态、约束、标准版本及产品支持边界 | 同条款与产品实现可分别定位来源 |
| `aiot-wifi-knowledge/governance/templates/rule.md` | F | 含规则对象、约束、例外、批准身份和检查办法 | 原件批准未知时候选明确保留 unknown |
| `aiot-wifi-knowledge/governance/templates/command.md` | F | 含语法、参数、前置条件、输出判读、误用、验证 | 无运行证据的文档样例不标实测成功 |
| `aiot-wifi-knowledge/governance/templates/runbook.md` | F | 含现象、信号、分支、步骤、根因状态、解法和验证 | 每个分支有条件，未知根因不会写为确定归因 |
| `aiot-wifi-knowledge/governance/templates/glossary.md` | F | 含定义、别名、歧义、范围和来源 | 歧义词能给分组解释而非错误别名扩展 |
| `aiot-wifi-knowledge/governance/templates/index.md` | F | 列 ID、标题、范围摘要和链接 | 导航未进入正文候选/评分，条目链接闭合 |
| `aiot-wifi-knowledge/governance/specs/cards.md` | F | 解释字段含义、七类章节和合成正反例 | 作者可按规范选择 Profile 并写出可追踪 Claim |
| `aiot-wifi-knowledge/governance/specs/lifecycle.md` | F | 分开三维状态和两种 review_mode；说明迁移及恢复 | 本地消费、文档人工确认、CI 只读三种情形无冲突 |
| `aiot-wifi-knowledge/knowledge/AGENTS.md` | F | 写明先检索再精读/回源、按范围回答及两种治理路径 | Agent 能说明引用、Target、确认方式和缺口 |
| `aiot-wifi-knowledge/knowledge/index.md` | F | 导航七类入口和主题分区，条目引用稳定 ID | 全部正文可从入口到达，孤儿/失链可诊断 |
| `aiot-wifi-knowledge/knowledge/concepts/index.md` | F | 链到 entities、flows、protocols | 三子入口闭合 |
| `aiot-wifi-knowledge/knowledge/concepts/entities/index.md` | F | 按实体主题/范围列 ID 和链接 | 导航与实际实体卡集合对应 |
| `aiot-wifi-knowledge/knowledge/concepts/entities/<card-id>.md` | D | 以 entity 模板与来源提炼问题、职责及边界 | 可回答职责/接口；设计与实现不混淆 |
| `aiot-wifi-knowledge/knowledge/concepts/flows/index.md` | F | 按场景、侧别和完整/片段范围导航 | 缺侧卡导航明确可见边界 |
| `aiot-wifi-knowledge/knowledge/concepts/flows/<card-id>.md` | D | 逐步骤绑定 Claim 与证据，标条件及消息/调用边 | 六 Target 请求仅返回已支持范围，pair 缺口不会被补造 |
| `aiot-wifi-knowledge/knowledge/concepts/protocols/index.md` | F | 按机制/标准版本列入口 | 读者可选择确切标准版本 |
| `aiot-wifi-knowledge/knowledge/concepts/protocols/<card-id>.md` | D | 描述机制与条款，产品支持另列实现断言 | 可回溯原条款，未验证实现保持缺口 |
| `aiot-wifi-knowledge/knowledge/rules/index.md` | F | 按对象、适用域和批准身份导航 | 未批准建议不会显示为全域强制规则 |
| `aiot-wifi-knowledge/knowledge/rules/<card-id>.md` | D | 写条件、例外、检查方法和来源 | 旧规则可恢复，新规则适用范围明确 |
| `aiot-wifi-knowledge/knowledge/commands/index.md` | F | 按工具/用途/环境导航 | 用户可识别命令是否已在当前环境验证 |
| `aiot-wifi-knowledge/knowledge/commands/<card-id>.md` | D | 给前置条件、参数、输出判读、误用和验证方法 | 缺环境/结果时不输出“已验证可用” |
| `aiot-wifi-knowledge/knowledge/runbooks/index.md` | F | 按现象、信号和场景组织 | 导航条件能区分不同排查分支 |
| `aiot-wifi-knowledge/knowledge/runbooks/<card-id>.md` | D | 用条件分支写排查与恢复，并记录根因状态 | 依据不足时保留备选原因和下一步，而非编造闭环 |
| `aiot-wifi-knowledge/knowledge/glossaries/index.md` | F | 按词/别名/语境导航 | 同名多义可分组定位 |
| `aiot-wifi-knowledge/knowledge/glossaries/<card-id>.md` | D | 给定义、语境、别名及来源 | 查询歧义词给候选，明确符号保留大小写 |
| `aiot-wifi-knowledge/.build/<operation_id>/plan.json` | R | ingest plan 固定来源、scope、操作及理由 | 重跑返回同计划/no_change；缺证据 defer |
| `aiot-wifi-knowledge/.build/<operation_id>/changeset.json` | R | 记录旧/新摘要、Claim/来源/关系变化和 review_mode | 并发新增重复 ID 不被漏过，其他任务文件不被覆盖 |
| `aiot-wifi-knowledge/.build/<operation_id>/candidates/<card-id>.md` | R | 六决策生成候选，关联操作和来源 | 未确认候选不会进入 current 回答 |
| `aiot-wifi-knowledge/.build/<operation_id>/final-view/<target-relative-path>` | R | 组合 stable 卡、废弃/替代、来源锁和导航增量 | 通过后改任一目标可被摘要检查发现 |

完整职责与约束字段见 ../../traceability.json，同一路径只有一个主模块。F 为固定实现，D/R/X 是实例、产物或外部入口，P 首发延期；不得手造不存在的业务工程或成功证据。
