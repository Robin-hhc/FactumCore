# 第二批实施细化：raw → 候选 → 人工确认 → stable

状态：本批实施约束与验收计划；实现和实际验证状态按各任务记录更新。本文细化 T03/T05/T06/T07，不改变已批准总体设计；实际 CLI、Schema、任务状态和测试记录仍以各自真源为准。不得把本文中的拟定接口当作已经实现或验证。

`W` 为开发 workspace，`S=W/skills/common/knowledge/_shared`，`K=W/aiot-wifi-knowledge`。用户已指定当前统一 FactumCore 单仓发布；框架与领域按目录分层，SDD 留在 W，原件、卡片、来源锁与业务记录留在 K。合成 fixture 只用于测试，不能进入真实知识正文成为 stable。

## 1. 本批纵向闭环与交付边界

| 票 | 输入 | 输出与拥有文件 | 本批完成条件 | 后续边界 |
|---|---|---|---|---|
| T03 / M03 | K 内允许的一个 raw 主文件、显式必要附件、稳定 source_id、已知版本或 unknown | S/sources.py；持久证据 bundle；符合 sources Schema 的 resources/snapshots；提取文本和 locator | 无网络捕获真实字节；原路径变化后可由 bundle 校验恢复；失败不登记伪完整来源 | Git/dirty/export 代码快照在 T04；未安装解析器的 Word/PDF/OCR 不冒充支持 |
| T05 / M04 | 已校验捕获包、Agent 提供的显式 Card Markdown、决策与理由、现有相关卡基线 | S/cards.py、S/changes.py；本 operation 的 plan、changeset、candidate、final-view、review-package | 七 Profile 可解析；单卡 create/update 生成拟写 stable 的确切最终字节；正式资产不变 | merge/split/deprecate 可列计划和去向；复杂跨卡 apply 在 T09；不能机械摘录冒充语义归纳 |
| T06 / M05 | 固定 review-package、final-view、相关基线；真实人对本次最终视图的动作 | S/changes.py；logs/document-reviews/<review_id>.json；待确认状态保存在 operation | 确认绑定确切最终内容；无真人动作、拒绝、暂缓和旧确认都不能放行 | 宿主用户回复适配器只有在真实接入后才能宣称；不自动为本开发任务生成真知识卡 |
| T07 / M05 | 相符的接受记录、ChangeSet、确切 final-view 与当前相关基线 | 跨进程锁；transaction journal/backups；清单内 knowledge/navigation/sources.lock；operation 结果 | 先记录恢复材料再替换；CAS/全库 ID 与引用技术一致性；字节一致、幂等且保留无关修改 | T08 完整恢复入口、T09 跨卡操作、T10 索引激活仍保持未完成 |

这条链只到本地 stable 文件落位。没有索引构建/激活，不能声明已经完成检索消费；没有实际提交/合入/推送，不能声明已上库。发布由本轮已有用户授权及提供的实际远端地址执行，捕获/确认/apply 命令本身不运行 Git 发布。

## 2. 共用接口、身份和摘要

沿用现有 CLI JSON 信封与退出码：`schema_version,status,operation_id,input_digests,output_refs,diagnostics,retryability,result`；成功 0、输入或契约失败 2、工具异常 3。本批正常等待或 defer 可通过 result 的 phase/decision 表达，不能使现有 CLI 在未知 status 下误报失败/成功。最终状态集合、输出及退出码须在实现测试中一起固定。

同一摄入事务的 operation_id 在 plan、materialize、confirm、apply 及所有生成记录中保持一致。信封不能每一步新建无关联的 UUID。调用者输入的操作 ID、卡 ID、附件名、bundle_ref 和所有目标相对路径都当作数据；它们不成为 shell、动态模块或任意文件读写入口。

摘要共用 receipts.digest_bytes/digest_json；JSON 采用现有 UTF-8、排序键、紧凑分隔符和禁止 NaN 规则。摘要对象不得包含自身摘要字段。一个确认至少同时固定：

- `operation_id`、`changeset_digest`、`final_view_digest`；
- `target_file_digests`：卡片、来源锁和导航等实际拟写文件的最终字节；
- `baseline_digest`：相关输入路径及预期摘要，创建时显式记录不存在；
- `source_set_digest` 及精确 `source_snapshot_refs`；
- `scope_digest`、card/claim 身份与本次具体决定；
- 受信契约包与工具身份，人工动作来源、时间、引用及限制。

ManualReviewRecord 的现行 Schema 已有 target/source/scope/baseline 字段。额外的 final-view、ChangeSet、契约/工具及人动作绑定可放入现有 `extensions`；不要为了实现便利悄悄扩大必填字段或破坏 T01 既有记录。任何兼容调整都需更新锁摘要、规格与回归。

source_id 是逻辑资料身份，snapshot_id 是特定字节/附件集合的版本身份，不能靠相同文件名推断同版本。Card.sources 使用固定快照引用，Claim.source_ids 在该固定来源集合中可解析；引用语法、附件从属关系与恢复方式在实现前由 sources/cards 两侧共同冻结。来源锁追加旧/新快照，不覆盖旧快照。

## 3. T03：可恢复 raw 捕获

### 3.1 函数和 CLI

本批共享函数：

```python
capture_document(knowledge_root, path, *, source_id, declared_version="unknown", attachments=None)
# -> {bundle_ref, manifest_digest, resources, snapshots, text, ...}

load_capture(knowledge_root, bundle_ref, manifest_digest)
# -> 按持久包恢复并验证后的同一逻辑捕获结果
```

公开 CLI：`document capture --knowledge-root K --path RAW_RELATIVE_PATH --source-id ID [--declared-version VERSION] [--attachment RAW_RELATIVE_PATH ...]`；恢复入口为 `document load-capture --knowledge-root K --bundle-ref REF --manifest-digest DIGEST`。

### 3.2 捕获要求

主文件和附件都只能来自 `docs-raw/conventions|chips|storys|specs|protocols/` 的实际文件。docs-raw/sources、AGENTS/index 等控制文件、URL、仓外映射及越界链接明确拒绝/延期，不能自动读取正文中的链接。输入规则也要作用于每一个附件，不只主文件。

解析 K、允许根和目标的真实路径，按目录边界核验。拒绝符号链接/Windows junction 绕出；每次读取及最终复核都检查实际解析位置，不能只检查最初字符串。固定读取字节后对同一份字节做摘要和解析，读取前后核对实际原件，变化返回 INPUT_CHANGED；不以 mtime/size 单独证明内容稳定。

证据载荷落在既有 `K/logs/evidence/<bundle_id>/`：manifest.json、objects/<digest>.bin、extractions/<id>/text.txt 与 locators.json。先创建完整不可变包，再发布可解析引用；manifest 的摘要保存于外层引用，避免自摘要。写入失败的临时产物不可被当成 available bundle。

manifest 应覆盖主件与附件的相对位置、真实字节摘要/长度、kind、编码、版本、提取器版本/参数、提取文本和定位摘要。不能以任意绝对本机路径作为共享恢复引用。load_capture 必须校验 manifest 摘要、清单路径安全、每个对象/提取载荷摘要和 Schema；缺失或篡改返回可定位诊断，不回退读“当前同名文件”。

首个实现明确列支持格式，例如 UTF-8/UTF-8 BOM 文本与 Markdown。未支持的 PDF/Word/图片/OCR 要返回不支持或待人工处理，不猜编码，不以空文本当完整提取。必要附件缺失或无法提取时不输出“完整资料已读完”；允许仅保留二进制附件时也须将该限制带到 review-package，不能用部分结果制造删除差异。

输入原件始终只读。恢复依据不留在 .build 独占，清理候选后仍可重放所用来源；bundle 是证据缓存而非新的摄入入口，后续捕获仍只从 raw 允许目录开始。

## 4. T05：显式内容到候选和最终视图

### 4.1 内容与决策接口

实际函数边界：`cards.parse_card(raw_bytes, knowledge_root, source_snapshots=...)` 解析一份确切字节、frontmatter、原正文、稳定 ID、text_ref/span 和技术引用；`changes.create_plan(...)` 形成显式决策计划；`changes.materialize(...)` 固定候选与拟写视图。CLI 为 `ingest plan` / `ingest materialize`。changes.py 保留公共入口，内部 confirmations.py 负责终端人动作与记录，transactions.py 负责锁、技术视图和事务；它们是共享程序内部拆分，不增加领域事实真源。

输入必须包含 Agent 已结合固定原件生成的完整 Markdown/body、明确 Profile、结论和限制。程序负责安全解析、身份与摘要、模板/路径组织和差异包；不能在没有 Agent 业务内容时把首段摘录加上“摘要”标签当作生成知识卡。材料中的指令是材料，不成为运行命令。

plan 显示 create/update/merge/split/deprecate/defer 六种决策、理由、来源、既有卡和拟定去向；no_change 是实际内容不变的正常结果。不能同名自动合并，不能复用变化了的结论 ID 掩盖新断言。当前可落位 create/update；其他复杂决策在 apply 时明确返回 DEFERRED_OPERATION，而不是留下半实现正式资产。

### 4.2 final-view 和相关基线

本 operation 下生成 candidates/<card-id>.md、plan.json、changeset.json、final-view/<target-relative-path> 和 review-package.md。最终卡在 final-view 中已经是将来拟落位的 stable 确切字节；不得确认 draft 后再偷偷补 stable/来源/范围字段。正式 knowledge、来源锁和导航在 apply 前摘要不变。

ChangeSet 至少记录明确的相对目标清单、每个目标的预期旧摘要或 absent、最终新摘要、来源/ID/关系增量、相关 baseline、幂等键和 review_mode。基线覆盖本次实际依赖的卡、相关导航、sources.lock 和契约；不把每次追加日志或无关 dirty 文件都塞进 CAS，避免并行工作互相误阻塞。

重复 materialize 同一持久捕获包、内容字节和基线应生成同一最终字节/摘要。operation 的完成状态与真实产物一致；任何内容、来源、scope 或基线修订形成新的最终视图身份，旧人工决定自动过期。

review-package 展示：原件/附件及所用版本、逐 Claim 新旧内容和证据 locator、适用上下文、未知/提取限制、确切目标文件与摘要、完整差异、当前决策和待人决定的内容。不隐藏来源锁/导航等“附带”写入；这些最终字节也属于确认范围。

## 5. T06：真实人工动作与记录绑定

### 5.1 信任边界

`confirmed_by="某姓名"` 或 `--accepted` 只能声明字符串，不能证明真实人同意。普通 Agent 提供的 JSON 同样不能自行提升为真人动作。当前用户授权“开发并测试”也不构成对尚不存在的业务知识最终内容的确认；本轮仅在合成临时知识根内验证 accepted 路径。

最小可实现生产入口是明确交互式终端：先展示本次 review-package/目标摘要与限制，再读取人输入的决定和本次最终视图 challenge；提示放 stderr，最终 stdout 仍输出单个 JSON。非交互 stdin、空输入、EOF/超时或只给名字参数均不能生成 accepted 记录。真人可为贡献者本人，不增加审批人。

终端交互只提供明确的人动作入口，不是抗同权限恶意进程的身份认证系统。宿主用户回复路径需要一个明确接入的可信 adapter，提供真实会话回复引用、主体、时间、已展示的 view digest 和决定；未经该 adapter 的用户文本文件只能当导入数据。不要声称已验证不存在的宿主通路或不可伪造身份。

合成测试通过依赖注入的 synthetic human-action provider 重放动作，记录必须标为 synthetic 并只在测试临时根使用；生产 CLI 不开放 `--synthetic-human` 放行开关。实际 fixture 不写入真实 K/logs 或 knowledge。

### 5.2 状态转换

`confirm_document(final_view, human_action)` 重新验证当前候选、来源包、scope、基线与人工所见摘要，再生成 ManualReviewRecord。记录保存在 logs/document-reviews/<review_id>.json，且不得将记录自身加入 target_file_digests。

- 无动作：operation 为 waiting；不填写虚构 confirmed_by/confirmed_at/confirmation_ref 来满足 Schema。人工记录现行必填字段不适合空等待状态，等待应保存在 operation/计划而非假确认。
- accepted / confirmed_no_impact / deprecated：必须对应本次明确决定与最终文件；本批 apply 仅接受与当前具体操作匹配的允许决定。
- returned / deferred：可以保留真实决定审计，不能 apply。
- partially_accepted：仅记录“需重建”。先生成缩小后的候选和 final-view，再展示新摘要并取得新人工动作；原整包或第一次部分接受不能放行新视图。

Review 失效判断不是只比较卡正文。换源/附件、scope、来源锁增量、导航、相关基线或契约身份变化同样必须重新展示确认。scope 的 hash 只绑定人工所见范围，不证明该范围的技术适用性。

整个 manual_document 分支不调用 lint Skill、lint local、lint merge，不要求 LocalCheckRecord 或 MergeGateRecord。解析、身份、摘要、CAS 和引用检查用于避免写错对象；它们不证明文档语义正确，不变相扩成自动语义门禁。原件中的实现/实测陈述仍须在卡中保留设计/历史/证据限制，人工确认不能自动变成“最新代码已验证”。

## 6. T07：跨进程事务、CAS 与技术一致性

### 6.1 写入协议

`apply(knowledge_root, operation_id, review_ref)` / `ingest apply --knowledge-root K --operation-id ID --review-ref REF` 仅处理当前 materialized ChangeSet。它不重新生成内容，不补来源，不修卡，不提交或推送。

1. 解析真实 K 并验证所有 operation/record/目标/备份路径；拒绝绝对目标、..、重复规范化目标、大小写别名、保留设备名、链接绕出及任意不在允许清单的路径。
2. 取得领域协作**跨进程**排他文件锁；Windows 不能只用线程锁或只判断 lock 文件存在。锁句柄/路径不得绕到别域，进程退出应释放 OS 锁。锁争用返回 BUSY/可重试诊断，不能强删别人的锁。锁本体可使用现有操作目录内的受控运行文件，不增加业务顶层目录；各进程必须竞争同一真实 K 对应的锁身份。
3. 在锁内重新读取 final-view、Review、捕获包和相关 baseline；检查所有绑定相符，CAS 对比明确目标旧摘要/不存在条件。输入读取与摘要绑定同一份字节，不能先 hash A 后另读 B 并解析。
4. 构造“当前全库加本次覆盖”技术视图，重核全域 card/claim 身份、来源引用、替代/关系目标闭合和必要无环条件，包含 touched_paths 外别处刚新增的同 ID。允许无法由本次自动维护的既有无关内容保留；发现会破坏该技术视图的冲突时在写入前退出，不运行文档 lint。
5. 校验所有最终新字节摘要。先完整保存备份并核摘要，持久化 backup-manifest 与 prepared journal，记录目标原摘要/新摘要、顺序和恢复状态，然后才允许第一次替换。
6. 每个文件使用同目录受控临时写入、flush/fsync 和原子替换；每步在 journal 留下可诊断状态。替换前再次确认目标仍是预期旧字节，若遇未遵守协作锁的外部编辑，停止并保留现场。所有目标结束后复核新摘要，再将 journal 标为 committed，最后更新 operation 结果。

普通文件系统不提供全库多文件原子替换。锁只协调采用本协议的写者；不能保证与任意外部编辑器恶意并发的全局原子性。消费者未来只读已激活完整代次，不能因文件陆续替换就构建/激活半套索引。

### 6.2 失败、幂等和恢复边界

重复 apply 同一 operation 且已 committed、当前目标仍是记录新摘要时返回原结果，不重复写 Review、锁、来源快照或导航。若 committed 后目标被他人修改，不能重试覆盖；返回 APPLIED_STATE_CHANGED，保留当前内容与原提交结果。

写入前失败保持所有正式资产不变。写入途中异常应给出 operation、journal 和已写目标；可立即受控回滚时仅恢复当前仍匹配本操作新摘要的文件。原先 absent 的目标只有仍是本操作新字节时才可删除；别人改后的字节不覆盖、不删除。回滚后逐文件核旧摘要。

进程硬中断无法依靠 finally 保证回滚，因此下一次 apply 必须发现非终态 journal，返回 RECOVERY_REQUIRED 并保留备份/诊断，而不是重新从头覆盖。完整跨进程 recover 命令与续做策略属于 T08；本批至少做到不会留下无说明的半套文件或将 prepared/replacing 当 committed。journal 丢失/损坏、备份不符、外部新编辑都要 fail closed 并显示人工恢复材料。

## 7. 可执行验收矩阵

所有例子在临时合成 K 内运行，命令从任意 cwd 调用公开 CLI；规则包使用现行锁。测试记录保存命令、退出码、JSON/文件摘要和故障点。fixture 的人动作不能计为真实知识确认或实际 WiFi 业务覆盖。

| ID | 票 / 设计验收 | 输入/故障 | 可断言结果 |
|---|---|---|---|
| B02-01 | T03 / E09 | 五类 raw 中 UTF-8 Markdown/中文空格路径 | 捕获主件、实际摘要、文本/locator；原件前后字节不变 |
| B02-02 | T03 / E09 | URL、sources、控制 index/AGENTS、仓外文件、软链/junction 绕出 | 明确诊断、非零/延期；网络接口 spy 调用数为 0 |
| B02-03 | T03 / E10 | 主件相同、附件改变/缺失 | 不误判主资料无变化；缺附件不产出完整成功包 |
| B02-04 | T03 / E10 | 读取期间更换原字节，包含 size/mtime 相同情况 | INPUT_CHANGED；不登记完整快照 |
| B02-05 | T03 / E15 | 捕获后改变/移走 raw；从 bundle 恢复 | 原字节、文本和 locator 摘要相同；不读取当前同名替代文件 |
| B02-06 | T03 / E15 | 篡改 manifest/object/text/locator、缺必要载荷、bundle_ref 越界 | 恢复失败有精确对象诊断；不回退成成功 |
| B02-07 | T03 / E10 | 不支持的 PDF/Word/OCR 或无效编码 | 不伪造支持/空提取成功；限制可带入候选或明确延期 |
| B02-08 | T05 / E03 | 七 Profile 显式合成 Markdown | 可解析稳定身份与锚/span；重复 ID、断锚、来源/上下文断引用定位失败 |
| B02-09 | T05 / E11 | 缺 Agent body；只给原件 | 不自动制造“语义卡”；要求显式内容或 defer |
| B02-10 | T05 / E11 | 六决策 + no_change；复杂跨卡计划 | 决策和理由可读；仅 create/update 可 apply，复杂操作明确延期 |
| B02-11 | T05 / E11 | 同捕获包/内容/基线两次 materialize | final-view 与拟写文件摘要一致；正式资产摘要不变 |
| B02-12 | T06 / E12 | 无回复/EOF、非交互 stdin、仅 confirmed_by 名字 | 无 accepted 记录；operation waiting；apply 无法通过 |
| B02-13 | T06 / E12 | synthetic provider 的接受、本人确认、退回、暂缓 | 仅接受匹配决定可进入 apply；测试标记清晰且不写真实 K |
| B02-14 | T06 / E13 | 确认后改一字、换附件/来源、scope、导航/锁或契约 | REVIEW_STALE 或相应基线冲突；没有正式写入 |
| B02-15 | T06 / E12 | 部分接受后重建缩小 view | 旧整包/部分记录不能 apply；新最终视图需要新动作 |
| B02-16 | T07 / E17 | 接受后的 create/update 正常落位 | knowledge/锁/导航与 final-view 确切字节完全一致；卡为 stable |
| B02-17 | T07 / E13 | touched target 外新增同 card/claim ID，或关系目标被删 | 锁内全库技术视图拒绝，双方现状保留 |
| B02-18 | T07 / E17 | 相关基线改动与无关 dirty 文件各一例 | 相关变动拒绝；无关修改原样保留、不加入变更清单 |
| B02-19 | T07 / E17 | 两个独立子进程竞争同领域锁 | 一次只有一个写者；失败方 BUSY/重试后 CAS 冲突；无重叠替换 |
| B02-20 | T07 / E18 | 每个备份/journal/替换步骤故障注入；另有硬 kill 子进程 | 正常错误可诊断/受控恢复；硬中断留可恢复 journal，下一次要求恢复而非盲写 |
| B02-21 | T07 / E19 | 重复 apply；committed 后外部编辑再重复 | 首者幂等返回同结果；后者不覆盖新编辑 |
| B02-22 | T06/T07 / E14 | 对整个 document 链 monkeypatch lint/check_local/check_merge 为立即失败 | 完整合成 document 链仍可成功，调用次数为 0；无伪 Local/Merge pass 产物 |
| B02-23 | 全链 / E11–E17 | 新进程 capture→plan/materialize→synthetic confirm→apply | 所有阶段 operation/source/view/review 身份闭合，原件和无关文件不变，未声称索引/真实确认/业务覆盖 |

## 8. 审查重点与本批不得混报的结果

审查至少覆盖三个面：来源/路径/字节恢复；人动作与最终视图绑定；事务锁/CAS/全库身份/故障现场。实现者自测之外，由未写对应代码的审查者检查 diff、负测和失败语义。找到问题后补回归、复测并在开发记录关联修复，不只写“已 review”。

对“真实人”只能报告实际入口/适配机制与此次有无动作；对“stable”只能报告真实卡字节落位；对“可消费”须等索引模块；对“完整恢复”须等 T08。合成 6 Target/3 pair 配置测试不计真实源码接入；fixture 知识不推成业务事实。模块上库和推送用各自真实 Git SHA、分支与远端复核记录，不能用本地 commit 代替远端合入。
