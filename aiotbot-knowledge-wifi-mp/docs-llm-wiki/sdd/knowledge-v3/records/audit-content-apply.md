# knowledge-v3 规格审计：P3/P4 与 P6/P7

审计性质：只读规格对照，未修改实现、历史 SDD、真实 raw 或正式知识正文，未读取 gold；源码与隔离测试的静态检查不代表真实宿主、真人或业务代码验收。

唯一设计基线：`docs-llm-wiki/sdd/knowledge-v3/baseline/知识库详细设计.md`，SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`（本次重新核对）。以下路径均相对 `aiotbot-knowledge-wifi-mp/`，行号为审计时文件。

## 1. P3 仍要求先完成卡稿，缺少独立的逐 Claim 计划

- 设计：§5.3 行 456—504，先阅读比较事实、条件和依据，确定拟改／保留内容、作者与欠账，再交 P4 写稿；§6.2 行 732，本批目标问题与期望 Card／Claim 由 P3 给出。
- 当前：`hs-knowledge-change-plan/scripts/planning.py:189-242` 仅接受六决策和 caller 提供的候选 ID；201 行还允许以本次决策自身作为默认完整集合。223—225 行必须读取已写好的 `card_inputs`，后续才形成计划。345—352、421—436 行保存决策、理由、卡／替代和最终写集合，但没有受冻结处理单元约束的逐 Claim 拟改／保留／条件／证据／作者，以及目标查询计划。
- 功能差异：即使 Agent 声称“已处理全部”，调用方漏掉某来源单元仍可能结构通过；P3 不能在尚无卡稿时表达可供 P4 使用的完整计划。已有 `request` 原样封存不等于新增字段已被校验。
- 最小修正：保留六卡动作、完整引用校验和 rederive；增加 Agent-authored 计划输入，绑定 P1/P2 冻结单元，说明每条结论的修改、保留、条件、来源及欠账、目标 Card/Claim 与作者、代表性查询及预期。脚本只校验结构、身份与覆盖，不生成语义。P4 将稿件与计划对应后再固定最终字节。来源 skip 另作处理结果，不能加入第七卡动作。
- 公开测试 seam：现 `change-plan/tests/test_cli.py` 的 coverage、defer、merge/split、plan rederive 用例可延伸；新增无卡稿可固定计划、遗漏扫描单元拒绝、同一卡多来源合并一作者、目标查询绑定、改稿偏离计划被拒绝。

## 2. 没有实质 skip 的独立抽查及 P3/P4 共同内容复核协议

- 设计：§5.3 行 471—488、493—494；§5.4 行 524、530。新／改原件的无增量和 new/update 归卡须由独立复核者按风险抽查；未抽项不等于复核通过，P1 未变已完成的扫描跳过不重审。
- 当前：`planning.py:22` 的六动作正确，但无独立的 source skip outcome；无写内容只返回 deferred（444 行）。`change-plan/artifacts/review-guide.md:1-3` 仅提示身份／指纹；`local-check/SKILL.md:6-14` 和 `local-check/scripts/check.py:287-335` 已具备可信签名的代码语义报告，覆盖确切视图／代码上下文／模式，但没有作者身份、抽查集合、未抽集合和归卡裁决协议；现 `local-check/artifacts/review-guide.md:1` 主要是代码门禁拒绝样例，不是设计要求的 P3/P4 内容审阅指南。
- 最小修正：在 `local-check/references/review-guide.md` 写清逐断言核对、多源融合、旧 Claim 去向与 skip/new-update 风险抽查。由实际独立复核者提供报告，固定 scan/plan/source/view、作者与复核者、抽查理由／范围／结果／未抽项；脚本验证引用与范围，不宣称能判定“阅读充分”或证明语义。发现错归回 P2/P3，材料不足 defer；无卡稿的实质 skip 在 P3 完成同一协议，P4 仅复用未变化裁决。需要真实宿主支持独立上下文时明确停点，不能用普通 Agent 自报升级成可信结果。
- 公开测试 seam：`local-check/tests/test_public_code_gate.py` 的签名／缺证据／伪造／确切上下文测试保留；新增作者与复核者冲突、漏列未抽项、绑定旧 plan 的抽查、实质 skip 未审不能提交、扫描跳过不强迫重审，以及抽查发现错归的返回路径。

## 3. 当前明确拒绝混合稿，无法同时满足两类适用证据

- 设计：§5.4 行 532，“混合稿满足全部适用要求”。
- 当前：`planning.py:407-411` 直接抛 `MIXED_REVIEW_MODE`；`confirmation-prepare/scripts/prepare.py:133-136`、`confirmation-record/scripts/confirmation.py:18-23` 仅接受 manual_document 整体视图；`local-check/scripts/check.py:248-284,615-619` 只接受 code_gate 整体视图，遇文档卡拒绝；`apply/scripts/transaction.py:112-151,189-193` 按单个 review_mode 选唯一 proof，并要求新卡同模式。
- 最小修正：视图保留整体身份和完整写集合，列出卡级适用要求与 proof set。纯文档部分必须取得真实人对确切最终内容的明确签名动作，代码部分保留逐 Claim 可信语义依据；共享导航／来源锁属于整体固定视图。不要通过删掉人签名／代码签名检查或笼统把混合稿归成纯文档来兼容。可保留现单模式请求的兼容入口。
- 公开测试 seam：复用 confirmation、local-check 与 `apply/tests/test_public_governance.py` 的 public CLI harness；混合稿具备两组真实绑定证据才通过，缺任何一组阻断；纯文档仍免代码核验；任一相关字节、来源、规则或基线变化使对应证据失效。

## 4. 最终视图的可信人动作基础正确，但展示前尚无新固定预检门禁

- 设计：§5.4 行 512—526、532；P4 在展示之前复用固定预检，P5 最终全库 lint。
- 当前：`prepare.py:133-215` 的 `checked_view` 后直接生成完整字节展示、来源展示和随机 challenge；`confirmation-prepare/scripts/support.py` 中 checked_view 对应公共实现仅做身份／路径／指纹核对，没有新的 checks 全量预检调用。现 prepare 可在未跑 candidate-inspect 时独立调用。旧 lint Workflow 先 inspect 的顺序不能约束公开 prepare CLI。
- 必须保留：`confirmation-record/scripts/support.py:365-426` 从受信 catalog 查 Ed25519 公钥，核实 display/view/challenge、真人 actor、决定与有效期；`confirmation.py:16-45`、`transaction.py:112-133` 再核对完整写删集合及同一签名动作。fixture 签名器被限制到明确隔离根，不能作为真实人验收。
- 最小修正：prepare 直接复用新的固定 checks 对确切合成视图预检并检查结果，不能只相信请求声称“已检查”。P5 再绑定最终视图做完整报告；apply 校验 P5 gate，不能只依赖现 `validate_final_cards`（transaction.py:155-196 的卡关系检查未覆盖全部新 lint 项）。此项与治理/lint审计协同。
- 公开测试 seam：格式／来源／导航无效的视图在生成展示前拒绝；无回复、伪造 actor、签名、挑战、旧字节、过期动作仍拒绝。已有 `confirmation-record/tests/test_confirmation_record.py:86-140` 与 `apply/tests/test_apply.py:184` 为必须保留的拒绝样例。

## 5. P6 共享记录与 P7 控制写集没有实现接点

- 设计：§5.6 行 562—589；§5.7 行 606—616；§6.4 行 780—786。一个共享处理记录真源，逐冻结单元对账，区分观察版本、实际采用、执行节点；P6 校验，P7 补记落位结果后复验；卡、导航、来源锁、记录同批。允许记录失败事实，但不携带失败卡，实质 skip 抽查仍适用。
- 当前：`governance/contracts/records.py:6-28` 只有 digest seal/verify 与 shape 转发，无处理覆盖或跨文件绑定；`governance/schemas/records.schema.json:12-45` 无 ingest processing record。`view-materialize/scripts/materialize.py:20-24,94-108` 无写卡就 deferred，正常视图只固定卡、导航和来源锁。`apply/scripts/support.py:327-344` 的 checked_view 以及 `transaction.py:23-24` 只允许 knowledge、sources.lock 和 index.md，不能纳入 `logs/ingest/`。
- 最小修正：P6 新 record 接口接收 scan/plan/lint/适用review与实际采用关系，按被冻结单元逐一覆盖，合法失败／defer／skip 与未覆盖均明确；P7 使用同一CAS/备份/journal加入确切的本批 `logs/ingest/<id>.yaml`，据实落位补记并复验，不能改动已确认的知识字节。受控事务写集可独立封装内容视图与记录写集，证据仍绑定原内容视图。仅记录分支必须硬验证卡／导航／来源锁的写删集合为空，并且不能把 P5 编造为通过、把 defer 编造为完成。路径白名单只增确切记录目录，不把 logs 整体变成可写发布区。
- 提交边界：根 `.gitignore:25-29` 目前仅排除部分 evidence/备份，其他操作／原始日志并非整体忽略。新增放行 ingest 时同时明确排除恢复日志、原始人动作与运行产物；提交使用精确本批清单。
- 公开测试 seam：record 对账及 schema 的固定接受／拒绝样例；一源多卡／部分完成，失败无指纹，合法失败事实；record-only带一字节知识写入拒绝、未通过卡不得夹带、缺 skip 样本拒绝；中断发生在卡写后／记录写前可恢复，外部记录修改CAS冲突保留；补记校验失败不能误报整批完成。

## 6. 提交前索引和本批目标查询没有可验证的发布门禁

- 设计：§5.7 行 595—618；§6.2 行 732；§6.3 行 759—761。内容实际落位后完整验证本机索引，再执行 P3 本批目标查询，通过后才允许本批提交；record-only省略此门禁；运行故障只重试收尾。
- 当前：`publish-handoff/scripts/publish.py:10-64` 只调用公开 apply verify-result；65—89 行将提交、push、索引/回归与旧合入语义门禁列成 pending obligations；90—125 行即可产出 awaiting_external_publish，接口不要求已通过索引和本批query refs。旧 `workflows/.../hs-knowledge-lint/workflow.yaml:259-319` 虽声明先build/regression再publish，其不受约束的handoff公开CLI仍可提前执行，且 ingest 在另一Workflow交接处已结束。
- 最小修正：统一 ingest 的P7编排绑定实际apply结果、实际索引完整验证、P3本批目标查询及同代read报告，然后提供可提交精确清单。handoff若继续作为可提交状态证明，应校验这些依赖；不能把“pending索引”交接误称提交就绪。实际Git动作由已授权宿主／编排者执行，节点不需获得无限制push/merge授权。Git重试先核对已形成的本批提交，非整工作区提交。新 search 索引过期检查为明确暂缓项，不在此次添加。
- 公开测试 seam：`apply/tests/test_public_governance.py:307-331` 的完整链延伸：apply成功但无index/query不能进入提交就绪；索引完整验证失败、期望卡未召回、Target误入、跨代read各阻断；record-only只校验记录；索引运行故障重试不调用apply，内容query失败形成新修订并保留原apply事实。

## 7. 恢复基础应复用，仅补高层停点和共享状态

- 现有能力已符合核心要求：`transaction.py:244-284` 用受审原视图和proof复核journal；319—355逐项核对old/final及落位；517—549阻止并发未恢复写入且committed重入返回原结果；559—612恢复原事务、回滚前核对备份并保留外部修改；615—672完整CAS和持久备份/准备日志。`recover/scripts/recover.py:11-100` 只委托catalog固定的同一apply引擎，无第二写入引擎。
- 缺口边界：`governance-handoff/scripts/handoff.py:31-44` 和现Workflow仍是“另启lint治理”，没有P1—P7统一停点／P6结果／索引／提交的接续状态。原 committed apply 返回并不证明索引/共享记录/提交完成。
- 最小修正：在原单一事务引擎上扩展受控记录写集，在 ingest 状态中区分等待确认、材料缺口、未完成写入、已落位、索引/query故障、待提交与已提交。未完成写入优先recover；已落位不再apply。相关 .build 丢失时先核对持久journal/apply事实，不能当“未开始”重写。真实不可恢复的证明明确阻断，不用公开digest代替可信签名。
- 必保测试：`apply/tests/test_apply.py` 中完整CAS、故障resume、rollback、外部修改、假同意、篡改raw路径、writer lock、并发恢复与committed重入；`apply/tests/test_public_governance.py:331` 证明recover委托唯一公开引擎。

## 建议实施顺序与接口划分

1. 先统一 scan-unit / authored-plan / source-outcome / review-result / processing-record / final-content-view / controlled-transaction / post-apply-gate 的输入输出身份；不创建新的Workflow运行引擎。
2. P3计划与P3/P4复核指南/报告，再由P4物化确切卡稿；保持脚本不决定语义。
3. 混合证据和固定预检/P5最终报告；保留现真实性、确切视图和fixture隔离约束。
4. P6逐项对账与record-only；P7加入同一事务、恢复及共享记录复验。
5. P7实际索引/query就绪门禁、精确提交清单、幂等续办；同步单一ingest编排及使用说明。

本次为静态审计，没有执行完整测试；列出的测试是既有公开入口与建议扩展的验收seam，不能作为新行为已通过的证据。
