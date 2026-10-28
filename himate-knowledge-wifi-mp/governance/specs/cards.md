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

<a id="代码来源的可选符号补充"></a>

### 活动代码来源的符号引用

活动（`lifecycle` 非 `deprecated`）卡中，来源锁登记为 `code` 的每个来源项必须填写 `code_ref`，与 `review_mode` 和是否被 Claim 采用无关；固定 lint／CI 缺失时报 `CODE_REF_REQUIRED`，当前活动旧卡需通过 ingest 补齐。raw 和附件不接受该字段。原四字段及 Claim.source_refs 保持原含义，不增加卡级符号表；历史记录、旧来源恢复和 deprecated 卡仍可使用原四字段，不自动迁移或重签。一个来源引用描述一个符号，同文件的多个符号使用不同 `evidence_ref`，共用已登记的 `source_id` 和实际采用的快照。

纯文档不强制关联代码，P5 根据实际内容判断是否遗漏必要源码入口。一旦登记代码来源，必须选择受支持的真实符号；不提供 `file`／`range` 符号类型，不能仅凭整文件或行段代替符号。歧义或不支持的语法须保留阻断／缺口并补齐材料，不能伪造名字或改成文件引用放行。

当前符号导航仅支持下述 C/C++ 符号，不支持 Makefile 等构建文件中的规则，也没有匿名 union 实例或精确结构字段的独立 selector。捕获这类原始字节不等于符号导航可用；不能用外层结构或相邻符号冒充所需成员的身份，活动代码来源仍受必填和实际解析检查约束。

下面是字段示意；ID、快照与旧行段须替换为实际捕获结果。`code_ref` 不重复登记仓库或路径：实际文件由来源锁和项目配置解析。

```yaml
sources:
  - evidence_ref: send-entry
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 10, end: 30}
    code_ref:
      kind: function
      name: send_packet
      scope: []
      parameter_types: ["const packet_t *", "size_t"]
  - evidence_ref: packet-state
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 40, end: 45}
    code_ref: {kind: enum, name: packet_state, scope: []}
  - evidence_ref: ready-state
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 42, end: 42}
    code_ref: {kind: enum_member, name: PACKET_READY, scope: [packet_state]}
  - evidence_ref: header-limit
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 3, end: 3}
    code_ref: {kind: macro, name: PACKET_HEADER_SIZE, form: object}
  - evidence_ref: packet-flag
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 5, end: 6}
    code_ref: {kind: macro, name: PACKET_FLAG, form: function, parameter_count: 2, variadic: false}
  - evidence_ref: packet-alias
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 8, end: 8}
    code_ref: {kind: type_alias, name: packet_t}
  - evidence_ref: packet-limit
    source_id: registered-code
    snapshot_id: adopted-code-v1
    locator: {kind: lines, start: 9, end: 9}
    code_ref: {kind: variable, name: packet_limit}
  - evidence_ref: send-declaration
    source_id: registered-code-header
    snapshot_id: adopted-header-v1
    locator: {kind: lines, start: 10, end: 10}
    code_ref: {kind: function, name: send_packet, role: declaration, parameter_types: ["const packet_t *", "size_t"]}
```

`kind` 支持 `function`、`struct`、`class`、`enum`、`enum_member`、`macro`、`type_alias`、`variable`；`name` 为确切符号名。`scope` 按由外到内的限定名填写，省略表示全局 `[]`，不表示任意作用域；枚举成员包含父枚举名。函数可选 `parameter_types` 和 `qualifiers`（`const`、`volatile`、`&`、`&&`）消歧，省略与显式无参 `[]` 不同。参数名和函数体不参与身份，只做语法归一化，不承诺 typedef 展开或编译器级类型等价。

匿名父类型恰有一个直接 typedef 名时，该名称可用于内嵌符号的 scope；多直接别名、指针别名及更深的类型等价不作展开。返回函数指针的函数使用其自身参数，返回类型中的参数不参与该函数身份。

函数的可选 `role` 为 `definition/declaration`，省略时定位实际定义；仅显式 `role: declaration` 选择函数原型，声明不证明存在实现。类型定位含定义体的声明，类型前置声明不作为实现入口。`type_alias` 选择 C typedef（含回调／指针别名）或 C++ using；`variable` 仅选择文件／namespace 层普通声明，包括 extern、数组和函数指针，不选择局部变量或类型成员。这两类仅使用 kind/name/scope/language，不接受函数或宏专用字段；其他 kind 也不接受 role。

宏可选 `form: object/function`、`parameter_count` 和 `variadic`；计数只含固定命名参数，不含省略号。对象式宏不填写参数信息，不求值替换体；其他类型不填写函数或宏专用字段。可选 `language` 仅为 `c/cpp`；省略时按文件扩展名选择，`.h` 默认 C，C++ 头文件显式填 `cpp`，不尝试多个解析器猜语言。

固定证据检查仍恢复 `snapshot_id` 对应原字节并核对 `locator`；声明符号时，还核对该版符号与所引用行段相关。当前导航另读实际配置允许的当前文件，结果单列为 `code_navigation`。`resolved` 表示唯一定位，`missing` 表示未找到，`ambiguous` 表示不能唯一选择，`unavailable` 表示材料或解析能力不足；条件分支不能据同名推断活动定义。固定检查中 missing／ambiguous 为失败，unavailable 为未完成，解析失败不冒充符号不存在。

文件其他区域有语法错误时，仅在目标声明／定义及必要签名可靠、且不确定区域不可能包含同名候选的情况下允许定位，并返回 `partial_parse: true`。目标本身有不受支持的语法或同名风险时仍 unavailable；有解析不确定性而未找到目标时也不能报 missing。部分解析不证明整文件可编译或宏已经展开。

插行或函数体变化后，当前位置只进入查询／检查结果，不回写旧 `snapshot_id/locator`；`current_source_matches` 仍表示整文件字节一致，不能被符号存在替代。导航成功不证明参数含义、实现流程、宏生效、构建／运行结果或知识语义。CodeGraph 可辅助找候选与调用关系，不保存其内部节点 ID，也不用限量搜索未命中证明符号不存在。

`parse_card(data, path, rules)` 解析卡内结构、Claim span 和条件组；`validate_card(card, view, rules)` 校验完整来源与关系。候选尚未正式落位时，调用者将当前锁与新捕获合并到 rules 的临时副本 `source_lock`，不改正式锁。其他未选快照具有相同逻辑 source_id 不能为当前 Claim 放行。

这些函数只验证映射一致性，调用者仍要通过 source-prepare 的公开恢复入口或同一规则锁内的公共来源函数核验持久字节、定位与摘要。附件有独立来源与快照，引用附件事实时须显式选择。资料缺失、无法提取或仅链接时保留缺口，不能伪造“已完整读取”。

## 生命周期与修改入口

模板默认 draft/manual_document、未知范围，作者应按证据补齐内容。生产只写 candidates、ChangeSet、final-view 和 review-package；final-view 含拟落位 stable 的确切字节，正式卡、导航和来源锁在 apply 前不变。

`manual_document` 保留为文档类的协议取值，不再表示真人确认。内容复核核对最终卡、来源集合、范围、计划、拟写文件和未解决问题；作者回避及上下文隔离由 OpenFlow 管理，不用作者名字或上游通过票据在 Skill 内放行。文档类不需要代码材料；代码结论核对实际源码、配置条件与逐 Claim 依据，构建／运行断言须有对应实际材料。用户可在入库前要求退回或缩小范围；入库后修订走新操作，不覆盖旧事务。

本地 stable、已合入/未合入、当前有效性是不同状态。落位不等于已建立索引、已共享发布、最新代码已核验或已部署访问控制。未完成能力以 SDD 及实际验收记录为准。
