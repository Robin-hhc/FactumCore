# Card Markdown：技术解析与作者要求

正式知识卡使用 UTF-8 Markdown。本文说明 Card/Claim 的技术身份和作者填写要求；Schema、摘要、章节和锚点通过不代表结论正确，也不是纯文档的自动语义门禁。纯文档仍由真实人确认最终内容，代码卡走对应代码检查路径。

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

Claim.context_ids 和关系的 context_ids 只能引用本卡 scope.contexts 中已存在的 context_id。条件组内 AND、组间 OR；unknown 不等于 universal。不要凭原件文件夹、共享代码或资料标题补造芯片、侧别、宏、构建或 Host/Device pair 的适用性。

更新时作者明确判断是延续同一断言还是形成新断言；新结论不能只沿用旧 ID 隐藏替换。程序不猜语义相似度，不将相似字符串当作同一结论。修改后的正文、来源或范围必须重新走对应确认/检查。

## 来源引用语法

Card.sources 保存**固定 snapshot_id**，例如 `raw:<digest>`，不使用当前文件名、URL 或浮动版本作为知识证据身份。Claim.source_ids 保存逻辑 **source_id**；解析器通过该 Card 选定快照的 `snapshot_id → source_id` 映射验证引用。两个字段不能互换。

`parse_card(data, knowledge_root, source_snapshots=capture["snapshots"])` 可解析尚未正式登记的新捕获。没有显式快照列表时读取 `governance/sources.lock.yaml` 的映射；有 Card.sources 却没有映射返回 SOURCE_BINDING_REQUIRED。可选 source_refs 进一步限制允许选择的固定快照。只有其他未选快照具有该逻辑 source_id 时，不能用它为本卡 Claim 放行。

此函数只验证映射一致性，调用者仍要通过 sources.load_capture 验证真实持久证据及摘要。附件有独立 source_id/snapshot_id，引用附件事实时必须在 Card.sources 中选择相应附件快照。来源定位放在正文证据段和人工差异包中；来源缺失、无法提取或仅链接的资料不能伪造“已完整读取”。

## 生命周期与修改入口

模板默认 draft/manual_document、未知范围，作者应按证据补齐内容。生产只写 candidates、ChangeSet、final-view 和 review-package；final-view 含拟落位 stable 的确切字节，正式卡、导航和来源锁在 apply 前不变。

人工确认绑定最终卡、来源集合、范围、相关基线和全部拟写文件；真实贡献者本人可确认。部分接受要先生成缩窄的新 final-view，再重新展示并确认。无回复、Agent 署名或名字参数不构成确认。manual_document 不要求 LocalCheckRecord/MergeGateRecord，解析/摘要/CAS 只用于防写错对象。

本地 stable、已合入/未合入、当前有效性是不同状态。落位不等于已建立索引、已共享发布、最新代码已核验或已部署访问控制。未完成能力以 SDD 及实际验收记录为准。
