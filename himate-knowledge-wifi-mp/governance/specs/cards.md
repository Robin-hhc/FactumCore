# Card Markdown：技术解析与作者要求

正式知识卡使用 UTF-8 Markdown。本文说明 Card/Claim 的技术身份和作者填写要求；Schema、摘要、章节和锚点通过不代表结论正确，也不是纯文档的自动语义门禁。纯文档与代码卡均由独立 Agent 复核最终内容，代码卡另走对应代码检查路径。

## 输入与七个 Profile

输入必须是作者或 Agent 已结合证据写出的显式完整 Markdown。程序不会把原件首段机械摘录成知识卡。`governance/templates/` 提供 entity、flow、protocol、rule、command、runbook、glossary 模板；保留的 `{{...}}` 是待作者填写的位置，模板本身不是知识事实。

Card 最前使用单独一行 `---` 包围 YAML frontmatter；关闭标记之后的文本是正文，解析器保留正文换行和字符。支持 UTF-8 BOM，拒绝重复 YAML 键、非法编码和 NUL。Schema 字段真源是 `schemas/frontmatter.schema.json`，七类章节真源是 `schemas/profiles.yaml`，由 `framework.lock.yaml` 固定摘要。

| Profile | 主要回答什么 | 作者需要说明的边界 |
|---|---|---|
| entity | 对象的职责、接口和依赖 | 文档声明与实际实现分开 |
| flow | 有条件的步骤、调用和消息链 | 缺 Host/Device 另一侧证据就保留片段范围 |
| protocol | 标准机制、字段、状态和约束 | 标准条款不等于产品已经支持 |
| rule | 对象、约束、例外和批准身份 | 建议与已批准规则分开，未知批准状态不编造 |
| command | 命令语法、条件和输出解释 | 文档示例不等于命令已经在当前环境运行 |
| runbook | 现象、信号、排查分支和恢复 | 备选根因与已确认根因分开 |
| glossary | 术语定义、别名和语境 | 同名多义分开，精确符号保留大小写 |

所需章节使用独立 ATX 标题，如 `## 证据`；章节名称与 profiles.yaml 一致。解析器只检查结构存在，不评价段落是否真实或完整。围栏代码示例中的标题、锚点不用于满足正文结构。导航 index.md 不是第八个 Profile，不参与正文评分。

## 稳定身份、正文定位与范围

Card.id 是域内稳定身份，路径迁移不改变它。Claim.id 标识卡内可单独判断证据、范围和有效性的断言。卡内不允许重复 Claim ID、Context ID、来源引用或重复锚；全库唯一性和跨卡关系在 apply 的完整技术视图内复核，单卡解析不声称已经完成全库检查。

Claim.text_ref 只使用下列两种形式：

```markdown
<a id="claim-message-path"></a>
这里是该断言的正文。
```

- `#claim-message-path`：显式 `<a id="..."></a>` 必须独占一行，使用单引号或双引号；选择锚下一行至下一个显式锚之前，最后一个锚到正文结束。锚自身不属于断言文字。
- `lines:2-4`：正文从 1 开始的行号，包含第 2 至第 4 行及原换行。frontmatter 不计入正文行号。需要更细范围时使用明确锚或行段，不能用不存在的自动标题 slug。

解析结果的 start/end 是正文 Unicode 字符偏移，左闭右开；不是 UTF-8 字节偏移。body_digest 是保留换行后的正文 UTF-8 字节摘要。任何选择结果必须非空；原字节、正文摘要和这些位置不证明语义成立。

Claim.context_ids 和关系的 context_ids 只能引用本卡 scope.contexts 中已存在的 context_id；解析后为每个 Claim 编译完整 scope。条件组内 AND、组间 OR；unknown 不等于 universal。不要凭原件文件夹、共享代码或资料标题补造芯片、侧别、宏、构建或 Host/Device pair 的适用性。

更新时作者明确判断是延续同一断言还是形成新断言；新结论不能只沿用旧 ID 隐藏替换。程序不猜语义相似度，不将相似字符串当作同一结论。修改后的正文、来源或范围必须重新走独立复核和对应检查。

## 来源引用语法

契约 2.0 的 Card.sources 每项保存 `evidence_ref`、逻辑 `source_id`、固定 `snapshot_id` 和具体 `locator`。Claim.source_refs 只引用本卡唯一的 evidence_ref，不再使用 1.0 的 source_ids。逻辑来源对应多个版本时仍能定位到确切快照和段落，不推断“最新”。

`parse_card(data, path, rules)` 解析卡内结构、Claim span 和条件组；`validate_card(card, view, rules)` 校验完整来源与关系。候选尚未正式落位时，调用者将当前锁与新捕获合并到 rules 的临时副本 `source_lock`，不改正式锁。其他未选快照具有相同逻辑 source_id 不能为当前 Claim 放行。

这些函数只验证映射一致性，调用者仍要通过 source-prepare 的公开恢复入口或同一规则锁内的公共来源函数核验持久字节、定位与摘要。附件有独立来源与快照，引用附件事实时须显式选择。资料缺失、无法提取或仅链接时保留缺口，不能伪造“已完整读取”。

## 生命周期与修改入口

模板默认 draft/manual_document、未知范围，作者应按证据补齐内容。生产只写 candidates、ChangeSet、final-view 和 review-package；final-view 含拟落位 stable 的确切字节，正式卡、导航和来源锁在 apply 前不变。

`manual_document` 保留为文档类的协议取值，不再表示真人确认。内容复核核对最终卡、来源集合、范围、计划、拟写文件和未解决问题；作者回避及上下文隔离由 OpenFlow 管理，不用作者名字或上游通过票据在 Skill 内放行。文档类不需要代码材料；代码结论核对实际源码、配置条件与逐 Claim 依据，构建／运行断言须有对应实际材料。用户可在入库前要求退回或缩小范围；入库后修订走新操作，不覆盖旧事务。

本地 stable、已合入/未合入、当前有效性是不同状态。落位不等于已建立索引、已共享发布、最新代码已核验或已部署访问控制。未完成能力以 SDD 及实际验收记录为准。
