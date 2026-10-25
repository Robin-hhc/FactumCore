# V3 冻结设计与治理、lint、CI 实现差异

审计日期：2026-10-25。只读审计实现；本报告为唯一新增工件。未读取真实 raw、knowledge 正文或受限 gold，未运行真实宿主／CI。历史 v1/v2 工件保留原字节。

基线：`aiotbot-knowledge-wifi-mp/docs-llm-wiki/sdd/knowledge-v3/baseline/知识库详细设计.md`，SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。以下位置均相对 FactumCore 根。

## 已有能力应保留复用

- `governance/contracts/validation.py` 已拒绝 JSON/YAML 重复键、非有限 JSON、路径越界／别名，并验证锁与规则文件摘要；不是重新发明解析／路径层的任务。
- `knowledge.py:43 parse_card` 已校验 Schema、Profile 必需章节、Card/Claim ID、Claim 正文定位、来源关联、范围引用与空范围；`validate_relations:160` 已检查完整关系图、目标卡／Claim、replacement 与依赖环；`match_scope:222` 保守处理 unknown。
- `source_resources.py:22 validate_source_ref` 已绑定 logical resource 与 snapshot 身份；`recover_snapshot:58` 已核对本地确切副本的哈希／字节数，但调用与定位检查尚不足，见 G04。
- `hs-knowledge-candidate-inspect/scripts/inspect_candidate.py:8 execute` 已核对操作、计划、精确拟写字节、旧基线、来源集合，合成全库关系图，并阻止未完成事务。不能因为没有新文件名就把这些功能列为缺失。
- `hs-knowledge-index-build/scripts/node.py` 已有 SQLite 构建、快照正文、资格、活动代 CAS；`hs-knowledge-query-regression/scripts/node.py` 已有固定 required/forbidden/order 断言。这些正向证据／资格边界不可因拆出纯索引函数而删除。
- 现有测试入口包括 `evals/tests/test_contracts.py`、`evals/tests/test_workflows.py` 及 candidate-inspect/index-build 各 Skill 的 tests。它们证明旧协议场景，不等于新设计全部已满足。

## 必须修改的差异

| ID／优先级 | 冻结设计依据 | 当前实现证据与影响 | 最小修改与公开验证 seam |
|---|---|---|---|
| G01 / P1：独立只读 lint 与检查报告协议未落实 | §3.1 L1—L5；§5.5:538–560 | `skills/common/knowledge/hs-knowledge-lint/` 不存在。旧 candidate-inspect `execute:8` 依赖候选 operation/plan，`:23` 委托 change-plan，`:131` 再调用 view-materialize，会生成／重建 `.build` 工件；不能用于无需 catalog 的正式库只读 lint。返回 manual_ready/code_ready，不是按类别汇总的 passed/failed/incomplete/not-applicable 报告。 | 新增薄 lint Skill 与 `contracts/checks.py` 静态检查注册。抽取已有候选核对／关系逻辑；正式库直接读固定视图。统一报告绑定对象、规则、模式、范围、覆盖与稳定 Finding，完整／局部报告可区分。公开 CLI 对空报告、坏报告、exit/status 不一致返回 2；问题 1，缺输入／运行故障 2，通过 0。测试正式库无 catalog、候选写删叠加、同次多问题汇总、部分范围不能门禁、只产生报告／临时目录、未完成事务仅阻断不恢复。不要顺便更改其他旧节点的 0/2/3 传输协议。 |
| G02 / P1：CI 仍依赖本机 catalog 与代码语义引擎 | §3.2:315–326；§5.8:634–645 | `K/check.py:101 main` 强制 catalog/input/output/rules；`:132` 找安装的 merge-check 并子进程委托；`:191–199` 失败退出 2、incomplete 3。实际 `hs-knowledge-merge-check/scripts/merge.py:18` 读取候选 FinalView，`:21` 拒绝纯文档，随后写 `.build/operations` 并调用 local-check 语义引擎。现有 wrapper 是旧设计下可信安装包转调，不是固定 CI 独立检查。FactumCore 当前无 `.github/`、`.gitcode/` 作业入口，未见受保护基线叠加候选数据的可执行配置。 | 将 check.py 改为可信版本的 checks 适配器，直接接受候选完整数据视图与作业固定原文／代码／映射；check.sh 仅选显式 Python 转调。增加实际 CI 作业或明确可运行的受保护基线入口，候选只叠加卡、导航、来源锁、处理记录，不能选择检查代码／规则。测试无 `.build`／catalog／私人事件时纯文档可做结构检查；候选恶意改检查器／规则／作业不影响本次门禁；符号链接／gitlink、缺必需输入、报表异常均失败；CI 不写入候选。保留正向代码证据条件在 P3/P4，不能把旧引擎删掉后假称已做语义核验。 |
| G03 / P1：缺导航、Markdown 链接／标题锚点与冲突标记的完整检查 | §3.1:295,298；§5.5:553,555,558；§6.2:717,723 | candidate-inspect `:98` 明确跳过 index.md、AGENTS.md。`knowledge.py:14 _unfenced` 仅屏蔽 fence；`:43 parse_card` 只识别显式 Claim anchor 或 lines 引用，无通用链接／标题锚点、父导航覆盖、inline-code 屏蔽与冲突标记检查。现有关系图检查有效，但不等于正文／导航链接检查。 | 在共用 validation/knowledge/checks 层增加保留行号的 Markdown 解析结果，固定标题 slug／去重，屏蔽 fence 与 inline code 中的伪链接；文件和 fragment 同时验证；对完整候选叠加视图检查父导航／删除后反向引用；检测真实正文冲突标记。测试候选未落地目标可链接、删除目标留下反向链接失败、同名标题去重、缺 fragment 失败、示例代码不误报、局部报告范围正确。复用现有关系 DFS，不重写。 |
| G04 / P1：来源／代码固定引用只验证身份，未形成完整可读定位检查 | §3.1:296–297；§5.5:545,554；§5.8:645 | `source_resources.py:22 validate_source_ref` 仅要求 locator 为非空并核对 source_id/snapshot_id；`frontmatter.schema.json:83 locator` 允许任何非空对象。`recover_snapshot:58` 只允许 logs/evidence 本地对象，candidate-inspect validate_card 路径不调用恢复，更未证明 lines/page/paragraph/table/attachment 可读。既有 source 身份检查不能判定越界行段或同名新副本。代码正向语义检查另有旧 local-check，不应作为新静态 L3 的替身。 | 提供显式确切源对象 resolver，复用 recover_snapshot 的字节核验；依据受控 locator kind 校验位置并返回可读范围。代码固定引用仅核对作业给定 checkout、路径、哈希、行段及真实 config 映射。失配为 failed；必需原版／checkout 不可得为 incomplete；纯文档代码项 N/A。测试随机 locator 被拒、行段越界、页／表定位的支持／不支持边界、原版 hash 失配、同名新文档不能替代旧快照、精确旧版从显式输入恢复；输入不全不默许通过。 |
| G05 / P1：索引构建与查询回归不可直接给 lint／CI 复用 | §3.1:299；§5.5:547；§5.8:638；§6.2:719,732 | 构建全在 index-build `node.py:429 execute`；进入 writer 锁，读取 maintenance state/active/apply-result/proof，输出正式 artifacts，含资格和发布核验。query-regression `node.py:6 execute` 最后调用 index-build activate，适用于本地 P7，不能直接用于临时 lint／CI。 | 抽取 `contracts/indexing.py` 纯 build/verify/read/query-regression 函数；输入精确卡集合、规则身份与显式资格数据，产物仅写传入临时目录。本地 adapter 保留 writer、资格证据、发布／CAS 与 activate；CI/lint adapter 不读取私人操作日志，不切换活动索引。公开 CLI 测试只提供提交数据即可构建临时库，所有输入摘要／active.json 前后不变，原本非终态事务与代码资格拒绝例继续通过。 |
| G06 / P1：index verify 只核对外部摘要，缺重算完整性 | §5.5:556–547；§6.2:725–730 | index-build `node.py:394 verify` 检查 manifest 路径、database_digest、正文 blob sha；shared 再核发布。未执行 SQLite integrity_check、Schema/tokenizer/capability 校验、完整 Card/Claim 集合重算、metadata/postings/relations 逐项重算。攻击者或故障若重封 manifest 摘要，缺／多／错检索记录可被当成 verified。数据库元数据目前只写 rules_digest；固定 query 回归不能覆盖全量检索记录。 | 在共用 indexing.verify 对精确输入全量重算并比对表结构、版本、集合、内容、Claim 映射与查询记录，结合现有正文快照哈希与资格证据而非取代它们。测试删一条 Claim、加多余 posting、等行数换词、篡改 metadata/body、坏 DB、错规则／分词器版本后重算文件摘要仍被拒；合法确定性构建可重验。属于构建完整性，不是用户暂缓的 search 过期检查。 |
| G07 / P1：处理记录一致性与提交可解释的历史引用未落实 | §5.8:637；§6.2:713,716,720 | `contracts/records.py` 仅 seal:6 / verify:12 / shape:23 / binding:27；没有本批新增／变更记录与来源、卡、版本关系检查。records.schema.json 的 record_kind 枚举缺 ingest_record / lint/check_report 等新概念（不要求采用这些确切拼写，但当前旧类型也未承载新语义）。templates 无 ingest-record.yaml。 | 由 P1/P6/P7 负责人确定唯一 ingest record 形状；records 合约只负责形状及跨文件一致性、正确版本引用，记录写入／CAS 仍归现有节点。CI 对变更记录用引入时 Git 内容／明确版本解释，不能强迫全部历史记录永远匹配当前卡。测试新增／改／删／跳过每项有对应结论与来源版本、记录引用不存在卡／错来源失败、合法历史卡改版不使旧记录误报、缺原始真人事件不能伪造同意。与 P6/P7 同批发布机制联动，别另造并行水位。 |
| G08 / P2：规则包能力、受控事实与装载尚未扩展 | §6.2:713–721,732；§5.8:643 | framework.lock 只固定五个现有 contract 模块。validation.load_rules:180 的必需模块列表及各节点 support.py:289 domain、:361 modules 固定 validation/knowledge/source_resources/records；新增模块需加到可信编译装载流程。registries.yaml 仅 lifecycle/review_mode/evidence_kind/usage；这些值同时硬编码 frontmatter.schema.json，而 validation/knowledge 未使用 registry 来验证一致性；没有允许目录、locator kinds 的唯一受控注册。Profile 当前只有必需章节，无支持字段组合的机制。 | 对本次新增检查能力声明兼容版本／能力并固定所有实现、Schema/Registry/Profile 指纹；共用装载返回 checks/indexing，不绕过已验字节加载。Schema保留类型形状，Registry/Profiles提供受控事实与组合，必要时生成或启动核验一致性，避免漂移；config.yml 继续唯一项目／六Target映射，不能复制真实代码路径进 registry。测试缺新能力／未pin模块／旧包不兼容返回 incomplete、不偷退旧规则；pin后篡改失败；受控词变更必须影响检查；新旧记录兼容迁移接受／拒绝固定样例。可保留2.0记录版本并显式引入规则能力版本，无须机械大版本重写历史。 |

## 推荐共享边界

下列是分工建议，不是另造运行引擎；各命名可按现有编码风格调整。

```text
checks.prepare_view(mode, root, candidate?, commit?) -> immutable InputView
  files(bytes/path), exact object identity, scope, old baseline, source lock,
  current batch records; candidate = official + writes - deletes

checks.run(view, rules, explicit_inputs, scope, temporary_dir) -> CheckReport
  static groups: view / format / source / relation / index / records
  each status: passed / failed / incomplete / not_applicable
  findings: stable check_id + code + severity + path/line + reason
  coverage: complete repository versus enumerated local objects
  identity: checked object, input digests, rules/capability identity

checks.validate_report(report, expected_object, expected_rules, required_scope)
checks.exit_code(report) -> 0 / 1 / 2

indexing.build(cards, rules, temp_dir, explicit_qualification) -> generation
indexing.verify(generation, exact_cards, rules) -> full verification
indexing.read/query(generation, ...) -> same-generation content

records.validate_ingest_records(records, view, source_lock, version_resolver)
source_resources.validate_reference(ref, lock, exact_object_resolver, mapping)
```

CI 应明确分开 `trusted_program_root/rules` 与 `candidate_data_root`；不能在候选目录 `import checks` 后再声称有锁。现有 lock/cached-byte 编译加载做法可作为基础。手动 lint 不应该为了得到规则而要求安装 catalog。

## 推荐实施顺序与验收边界

1. 先确定 CheckReport／InputView／ingest-record 共享接口，并给出接受／拒绝样例；再补来源／Markdown／记录共用检查。
2. 抽出完整 indexing 构建／核验，保持旧 P7 资格与活动代防护；添加只读 lint 适配器，候选检查改复用它。
3. 切换固定 CI 入口和可信基线作业，调整旧 wrapper 测试至新 0/1/2；其他旧节点协议按兼容策略处理。
4. 回归公开 CLI，重点验证无 catalog 正式库 lint、全库合成视图门禁、报告异常失败、CI 候选不能改规则、临时构建不激活、确认／代码证据不可降级。

本报告未将用户暂缓的 search 索引过期检查列为修改项；未主张合并所有 Skill；未把现有18个节点替换为新引擎；未将静态合规、fixture 测试或 exit 0 解释为语义正确、真人同意、真实六 Target 接入或线上 CI 已安装。
