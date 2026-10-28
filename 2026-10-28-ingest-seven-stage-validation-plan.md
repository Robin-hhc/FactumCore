# ingest 七阶段重构验证计划

2026-10-28。状态：SDD 规划稿，未实施、未执行本计划，也不表示现有测试通过。本文件是本次跟踪上库的开发规划，不修改现行 Workflow、Skill、规则或共享设计，不作为部署输入。

**文档位置：**本次六份 SDD 暂存项目根并纳入 Git；开发完成后按后续指示移入文档忽略目录。入口见[SDD 总览](ingest七阶段重构SDD计划.md)。

依据[七阶段设计对齐稿](2026-10-28-ingest-seven-stage-design-proposal.md)及本轮已确认的职责：P5 集中知识质量审查，P7 只负责安全落位及实际检索收尾；不增加 passed 票据、角色身份认证或真人确认。需求编号 R01—R10 按本轮 SDD 分工暂定，后续需求正文沿用这些编号，变更须同步追溯表。

## 1. 验证对象和完成边界

主线为七个 OpenFlow 节点：P1 扫描、P2 备料、P3 决策及处置清单、P4 完整批次预览、P5 独立审阅与一次固定 lint、P6 机械生成记录、P7 安全落位和检索收尾。P5 是唯一独立 reviewer 节点；其他阶段由作者／执行者负责。P1 可直接结束或按真实停点直达 P7；修订返回 P2/P3/P4；恢复、索引、查询及启用不增加第八个必走节点。

最终公开能力按 **18 → 8** 的推荐范围设计验证。保留：

| 用途 | 最终保留的公开 Skill |
|---|---|
| 七阶段主线的五个入口 | `hs-knowledge-source-scan`、`hs-knowledge-change-plan`、`hs-knowledge-view-materialize`、`hs-knowledge-lint`、`hs-knowledge-apply` |
| 日常入口及独立业务 | `hs-knowledge-explore`、`hs-knowledge-query`、`hs-knowledge-maintain` |

迁移后删除的十个公开包为 `hs-knowledge-source-capture`、`hs-knowledge-candidate-inspect`、`hs-knowledge-candidate-revise`、`hs-knowledge-local-check`、`hs-knowledge-governance-handoff`、`hs-knowledge-index-build`、`hs-knowledge-query-regression`、`hs-knowledge-recover`、`hs-knowledge-publish-handoff`、`hs-knowledge-merge-check`。删除以业务替代入口和本计划相关用例实际验证为前提；本计划不执行删除。数量按有效公开 Skill 入口／分发清单计算，不按磁盘上残留目录数计算。

删除包不删除其必要业务能力：来源捕获／恢复迁入 P2 及消费入口所用公共函数；写入清单、完整候选稿及修订集中 P4；逐 Claim 代码审阅及记录绑定集中 P5；安全恢复、独立索引操作和声明式回归保留于存续公开入口；只读查询、维护巡检及共享资产消费继续可用。旧名字无需永久可调用，但明确约定保留的接口及历史数据语义必须有验证。

本批完成须有实际事务结果、完整实际候选索引、原冻结目标查询及真实启用事实。仅记录批以记录安全落位结束，欠账保留。Git 提交、CI、合入和另一台机器的接受状态分别记录，不从本地 ingest 完成推断。

## 2. 需求追溯和证据层次

| 需求 | 本计划采用的含义 |
|---|---|
| R01 七节点职责 | 七阶段、明确角色和返回／续办路径；多个内部动作不增加必走节点 |
| R02 P5 质量 | 计划／归卡／实质 skip／成稿／必要代码语义由独立 reviewer 审阅；一次固定 lint；脚本及 CI 不启动 LLM |
| R03 P7 安全收尾 | 不重跑整库质量 lint；保留输入一致性、锁／CAS／备份／事务／回读及实际索引／回归／启用保护 |
| R04 无 Skill 执行依赖 | 最终保留八包的生产路径不启动兄弟 Skill CLI，不导入兄弟私有脚本；复用领域公共函数与业务数据 |
| R05 业务能力不丢 | 被删包的必要来源、卡片动作、审阅记录、恢复、索引、回归和原交接业务各有明确归宿 |
| R06 团队共享及干净 clone | 只共享约定资产，消费端不依赖生产者私有流程材料和索引，不继承原生产者续办义务 |
| R07 版本和旧操作 | 新旧规则／操作有边界；历史原字节保留，真正旧未完事务用原配套能力处理 |
| R08 可测性能 | 记录阶段墙钟、模型等待、CLI 启动、重复计算和远程往返；结构验收与耗时证据分开 |
| R09 查询维护不回归 | 用途、实际代码／来源、同代读取、维护限制、巡检只读及增量判断保持正确 |
| R10 分发安装引用清理 | 最终八包及依赖／规则锁一致；旧十包的活动引用和执行回退清零，安装／升级有可验证行为 |

| 标记 | 环境与证据 | 可以支持的结论 | 不能代替的结论 |
|---|---|---|---|
| S 静态 | Workflow／布局、公开入口及契约、引用／依赖／打包清单的只读检查 | 七节点结构、引用完整、分发白名单、明显的执行依赖 | 宿主真的分配独立上下文、真实调用次数、实际运行正确性 |
| I 隔离合成 | 临时知识根、合成原文／代码／记录、真实公开 CLI 和必要进程／Git clone；故障注入仅限测试进程 | 本环境中的数据、恢复、并发、索引、返回及共享机制 | 实际知识语义、公司 API、SSH 等待、真实 SMB／ACL、断电持久化或六 Target 验收 |
| H 真实 SSH／宿主 | 已获授权的实际 OpenFlow、安装包、执行端、非受限小样本及明确网络条件 | 该宿主版本和执行端的角色／上下文、阶段交棒、SSH 结果核对、逐阶段实测 | 未覆盖宿主、其他机器／账号、生产全库或未测硬件行为 |

每条执行记录保存需求／用例 ID、输入及代码／规则版本、实际命令或宿主动作、报告和原始诊断、预期／实际差异、未执行范围。报告位于知识根已有 `.build/validation/<本次运行>/` 等允许产物区；隔离测试数据使用独立临时目录。不得读取受限 gold、写改真实原件或将凭据／生产者私有材料作为共享夹具。

## 3. 需求追溯用例表

表中“现有基础”指第 4 节中读到的现有测试源码，可复用其业务预期；不是本轮执行结果。新入口名称未定时使用中文动作描述，不在本计划中虚构终端命令。

本计划列出 V01—V43 共43组用例，现有测试基础用 E01—E18 标识。用例均为待实施／待执行的验证要求，不是43项已通过测试；一组用例可展开多个正反场景。

| ID | 需求／层次 | 场景与输入 | 必须观察的结果及负向预期 | 现有基础／新增重点 |
|---|---|---|---|---|
| V01 | R01、R02、R10／S、I | 加载七阶段 Workflow 和布局；正常文档批按公开入口执行 | 主线恰有七节点，P5 唯一 reviewer；不残留独立计划复核、预检、技术检查、代码核验、修订或恢复必走节点；实际正常路径与声明出口一致 | E01、E02；改旧节点清单，保留路径和角色约束预期 |
| V02 | R01、R02、R03、R05／I | 六类允许 raw 中分别新增纯文档；含与已有主题重叠和独立新主题 | 先材料／判断／完整稿，P5 完成实际审阅声明及一次固定 lint；P6 后 P7 同批落位、检索及启用；代码项不适用，不强加六 Target 或构建材料 | E02、E03；合成审阅仅证明机制 |
| V03 | R02、R05／I | 模块映射中的静态源码卡：current 有实际范围；historical／guidance 保留 unknown 条件 | P5 校验逐 Claim 理由、定位、源码／配置指纹和所需条件；静态源码不凭空要求编译；缺当前适用条件不伪装产品实现 | E06、E07；将旧 local-check 场景改到 P5 公共边界 |
| V04 | R02、R05／I | 文档与代码混合稿；分别声明静态、build、runtime 及测量要求，篡改或缺少对应材料 | 整体视图与各分区绑定，代码逐 Claim 有依据；测量缺运行材料不通过；不启动构建、不补猜 Target、不把文档通过扩大到代码 | E06；保留证据类型与材料不匹配预期，不保留必需签名／作者身份门槛 |
| V05 | R01、R02／I | P5 遇必要原版／旧卡／源码／配置或定位缺失 | 内容批返回 P2；补材料影响判断时经 P3/P4；未执行项明确，不写正式区，不冒称完整 lint 通过 | E07、E11；新增七节点返回动作断言 |
| V06 | R01、R02／I | 归卡、条件、合并拆分、skip 理由或目标查询预期错误 | 返回 P3 重判，再 P4 产生新预览、P5 重审；不得只改报告或放宽检索用途求通过 | E05、E10；语义错误由合成审阅问题驱动，不能宣称脚本自动懂语义 |
| V07 | R01、R02／I | 计划正确但正文／字段／链接／导航／来源登记组装错误 | 返回 P4；新完整稿重新进 P5，旧审阅不改绑；不重新决定无关单元，正式原字节不变 | E05、E07 |
| V08 | R02、R08／I | 一个固定候选正常一次通过；另例语义审阅先发现阻断 | 成功版本只在 P5 运行一次完整 lint；语义阻断可直接退回并注明机器检查未执行；P4/P7 不借解析／索引调用链重跑整库 Profile、关系、历史覆盖等质量规则 | E01、E07；新增公开执行轨迹与实际计算观察，不只比 YAML 节点数 |
| V09 | R02、R03／I | P5 后改变未写卡、来源锁、原文、采用旧卡、实际源码／配置、规则或写集基线之一 | P7 核完整业务输入指纹并停止原批写入；不靠 passed 报告或只比候选文件名／view digest 放行；按变化回相应阶段 | E08、E09；扩展“未在本批写集内但属于已审输入”的漂移 |
| V10 | R02、R03／I | P3 逐单元处置清单经 P4/P5 固定后生成 P6 记录，再 P7 补写入事实 | P6完整转写决定、理由、范围及欠账；不能重判skip/create；P7补记是新记录对象，保留结构／绑定／落盘核验；不得提前写已提交、CI或合入 | E04、E07、E08；新增处置预览与记录转写逐项比对 |
| V11 | R01、R02、R03／I | 仅有合法 skip／defer／failed／uncovered，内容写删集合为空 | P4有空写集和处置预览；P5审处置及适用项，内容／代码／索引项不适用；P6/P7只落记录，不构建／启用索引，欠账不被记成完成 | E04、E08；保持仅记录批的实际写入范围预期 |
| V12 | R02、R05／I | 原件不可读／必要材料不足，决定仅记录真实缺失与下一步 | P5可审记录事实充分后到P6，不因已明确的欠账无限退P2；同样缺口不能生成stable内容，也不能伪造“已审无增量”的skip | E04、E07、E08；新增欠账分支与内容批缺材料分支对照 |
| V13 | R02、R05／I | 实质skip与P1已完成的未变跳过混合；保留抽样和未审范围 | P5核实实质skip依据及抽样范围；未审项不写成已复核；P1纯扫描跳过不被反复语义审阅；不可读单元不能靠substantive skip完成 | E04、E05、E07 |
| V14 | R01、R08、R09／I | 完成后重复扫描；另例raw为空但有维护欠账或本机检索收尾 | 真正无变化无义务在P1结束且不造新记录；维护欠账仍可见；本机原操作待收尾直接P7，不重新提炼或apply | E02、E04；保留原no-op与finalization_pending预期 |
| V15 | R01、R02、R07／I | 原件未变，用户明确修卡；包括只改表达与改断言两类 | 建立新操作，准备相关原文／旧卡，经P3/P4/P5/P6/P7；受影响内容重审，未变判断可参考；旧事务、旧卡和旧报告不改签 | E03、E05、E15 |
| V16 | R02、R03、R04／I | 用合法业务输入独立调用P7，删除／不提供私有复核报告、passed标记、角色／Workflow身份；另例提供错绑可选业务材料 | 不因缺上游票据阻断；若提供材料，其确切绑定仍核实；成功只说明安全写入／实际收尾，不自动生成语义supported认证，也不承诺代替P5质量审查 | E03、E06、E08；旧“apply必跑质量检查”的预期迁P5，不能继续强加新P7 |
| V17 | R03、R04、R08／I | 正常P7完整批次及从每个持久停点重入 | 同一公开入口组合事务、实际索引、原查询和启用；不启动兄弟Skill CLI／LLM；保存各子阶段事实，未启用不得报整批完成 | E02、E08、E09、E10；新增完整批次入口 |
| V18 | R03／I | 入库前或备份期间外部改变写集文件；别名／越界目标 | 完整写集CAS在首次写之前阻断；备份后漂移仍被发现；外部字节保留，原件／规则不成为允许写入目标 | E08；保留真实文件hash与负向写入预期 |
| V19 | R03、R09／I | 两个写入者、未完事务屏障；活动代上并发只读查询 | 写入互斥，未完事务阻断冲突写入；不同query独立receipt／结果，同代读取不被新代启用混淆；不把单写者扩成串行所有查询 | E08、E09、E12；真实SMB语义另属H层 |
| V20 | R03／I | 模拟无声写入／删除／回滚失败，以及逐文件成功后其他文件又变化 | 写后回读与最终全写集核对拒绝假committed／rolled_back；事务与恢复线索保留；不能拿系统调用成功或installed标记代替实际字节 | E08；故障只作用于隔离测试进程 |
| V21 | R03、R05、R07／I | 真实子进程替换一张卡后硬退出；通过存续公开恢复动作inspect/resume/rollback | 按原journal／备份恢复同一写集或回滚；保护外部修改；不创建新事务冒充恢复；可选审阅文件删除不妨碍安全恢复 | E08；改恢复调用归属，保留进程硬退出及逐字节oracle；不声称断电持久化 |
| V22 | R01、R03／I、H | apply／回归／启用执行后丢失响应，或SSH断开且进程可能仍运行 | 先查原进程、journal、报告与活动观察；已落位只续办尾部，已启用有确切事实；不重复apply，不因响应丢失改expected_active或另启并行入口 | E02、E04、E08；新增响应丢失与实际远端仍运行组合 |
| V23 | R03、R05／I | 已落位后索引构建失败；候选代已有后查询／启用失败 | 环境故障只重试实际尾部；有内容错误时新修订，不重放原写入；P1识别原停点并直接P7 | E02、E04、E09、E10 |
| V24 | R03、R05／I | 正确行数但索引行值／集合／正文／Claim映射／版本被篡改或缺漏 | 实际候选代完整核验失败；同进程复用只对固定输入和未变产物有效，重启不继承内存“已验”；新代不能仅以数量相同通过 | E09；保留索引全量集合和值的独立oracle |
| V25 | R03／I | 回归通过后其他操作切活动指针，或知识／validity epoch在启用前改变 | 锁内按原expected_active及当前状态拒绝过期启用；不可用新基线覆盖；成功需指针回读和启用事实，不因查询通过就报完成 | E09、E10；去重复全验时保留此边界 |
| V26 | R03、R05／I | 不经过ingest，独立构建／全验／启用实际本地索引，包括空库和其他旧终态journal | 存续公开入口能完成原独立索引用途；不要求apply／私有复核／生产者身份；真正未结束事务仍是写屏障；未知动作无副作用 | E09；旧index-build包删除前迁公共入口并迁测试调用 |
| V27 | R03、R05／I | 独立声明式回归；空用例、无预期、非法用途、Claim排除错误、同代read不符 | 存续公开入口保留明确oracle与非空案例要求；错误不启用；正常ingest沿原P3预期，不能用无关案例或拓宽purpose替换 | E10、E12；独立回归模式与ingest冻结预期分开测试 |
| V28 | R05、R06、R09／I | 当前原件替换、私有缓存缺失、来源对象／附件／页段／适配器篡改；MD、PDF、DOCX等支持格式 | P2及独立消费入口可恢复确切采用版本、字节及定位；缺原版／适配器明确缺口，不偷换当前原件；不联网补原文、不执行原文指令、不扩大读取范围 | E07、E11、E14；原source-capture公共用例迁入存续入口，保持原字节和locator预期 |
| V29 | R05、R09／I | 实际来源／代码／模块映射变化、显式维护事件、依赖下游、historical与current／guidance混合 | 维护限制与传播按Claim用途及实际材料判断；historical确切旧证据可恢复时不因今日漂移伪造新债；current与显式语义限制不被错误清除 | E04、E12、E13；不得把迁包变成改写历史事件 |
| V30 | R05、R09／I | 独立query/search/read、purpose过滤、build材料变化、精确receipt、多Agent并发读取 | 保持当前资格、来源、模块范围及同代读取协议；不追P5/P7通过链，不隐式触发ingest／写入；无合格命中与索引不可用明确区分 | E12、E14；不将新批次输入指纹变成日常query全库门禁 |
| V31 | R04、R05、R09／S、I | 独立maintain inspect-context／audit-references和只读lint巡检Workflow | 引用漂移与原定位／旧当前指纹按实际报告；巡检不改卡、来源锁、事件／水位或活动索引，不嵌套ingest，不自动修订；保留返回明确修订输入的用途 | E01、E13；改内部兄弟调用，保留只读资产hash及报告事实 |
| V32 | R02、R06、R09／I | 删除生产者私有审阅／角色标签后运行正式库lint及固定CI；候选P5另提供本次代码审阅记录 | 正式／CI模式不因缺私有审阅记录失败，不启动LLM或执行候选程序；P5候选模式仍校验所提供记录结构／证据绑定及实际质量输入 | E06、E07、E14；显式区分候选与正式／CI适用项 |
| V33 | R05、R06、R09／I | 仅提交约定共享资产后执行真实Git clone；副本无生产者.build、索引、journal及缓存 | 新副本经正式lint、独立索引／回归及query/read消费；scan可识别共享已处理事实，不继承原生产者尾部义务；缺确切原版或当前代码按真实缺口处理 | E14；继续使用真实clone，改初始化及索引动作入口 |
| V34 | R06、R10／S、I | 检查共享资产白名单、gitignore及能力包内容 | 正式卡、来源锁、必要原版恢复材料、处理记录／使用限制可按约定共享；本机配置、凭据、私有复核、索引／缓存／受忽略的本地SDD不混入能力分发或业务提交；本次根目录SDD是明确授权的开发文档提交，不作为运行依赖 | E14；只用隔离合成材料与Git忽略规则验证 |
| V35 | R07、R10／I | 旧规则未完journal、旧终态journal、旧committed但待尾部、规则升级后同字节卡 | 原字节不改签；真正旧未完操作用可取得的原配套规则／能力处理；新规则不重放旧committed；无法恢复时明确阻断，不通过改digest消除 | E04、E08、E15；删除旧包前演练原版本恢复路径；新活动安装清单仍是八包 |
| V36 | R04、R05、R10／S、I | 从测试安装环境实际移除旧十包，依赖／入口注册仅有最终八包 | 七阶段、explore/query/maintain及独立来源／恢复／索引／回归用途仍可调用；不能靠旧目录、PATH、catalog、旧pyc或私有import兜底 | E01、E11、E16；新增“物理缺包”负向验收，不能只查调用字符串 |
| V37 | R07、R10／S、I | 分发、依赖锁、规则锁、文档／模板／测试运行器、宿主Skill注册及升级安装 | 活动引用无旧十包入口或失效路径，锁按实际内容验证；缺件／篡改明确失败；保留历史引用不被重写，但不作为活动依赖；八包干净安装和旧安装升级各有实际清单 | E01、E07、E16；新增包级清单与安装产物检查，不预填安装已成功 |
| V38 | R04、R08、R10／S、I | 七阶段和独立query／maintain运行时观察子进程、模块来源及公开入口轨迹 | 不启动兄弟Skill CLI，不导入被迁包私有模块；允许必要Git等本职外部工具；公共函数不是复制的隐藏旧Skill执行器；测试也不借旧十包生成唯一夹具 | E02、E03、E13、E17；静态搜索和动态观察互补 |
| V39 | R08／I、H | 同一输入／规则／模型配置的改前改后样本，分别本机与SSH执行 | 保存总墙钟、P1—P7时间、模型等待、CLI启动数／时间、SSH往返、来源读取及索引计算事实；报样本数／冷热状态／重试；无足够重复样本不宣称分位数或固定提速比 | 新增测量；现有timeout测试不是性能baseline，90分钟反馈是现场线索而非本轮测得值 |
| V40 | R01、R02、R03、R08／H | 实际OpenFlow安装八包、实际SSH执行端和公司API，以授权小样本跑文档／必要代码及一次中断续办 | 核宿主真实coder/reviewer任务与上下文、七节点交棒、执行端请求／响应路径、进程和事实收尾；分开记API排队／首字／生成、SSH连接和远程执行；实际SMB／ACL仅在对应环境另验证 | 无现有合成测试可替代；缺连接、配置或授权时记未执行，不把S/I通过扩大为H通过 |
| V41 | R02、R05／I | 六种卡动作create/update/merge/split/deprecate/defer；旧Claim保留、退役映射及多源融合 | P3/P4保留原卡身份／去向和显式保留范围；P5发现遗漏／错误归卡；不能因删旧规划／修订包丢失merge/split等能力，也不能默删旧Claim | E03、E05；保留手工可判定的具体正文／Claim映射oracle |
| V42 | R05、R07、R09／I | 通过apply迁入的独立入口生成内容批／仅记录批的本批提交清单；隔离Git夹具准备真实提交，再给出正确或错误commit、非HEAD提交、blob字节不符、应删除文件仍在或夹带无关改动的提交 | 清单只含本批确切写删及适用正式记录；仅记录批不夹带知识文件。实际提交核对逐一读取真实HEAD／commit/blob、删除和提交变更范围，拒绝错误字节、旧HEAD及无关改动；不能凭摘要记录自称submitted。能力调用本身不执行Git写入／push／merge，不将readiness、submitted、本地入库、CI及远端接纳混同 | E18、E08、E14；已有清单／字节反例迁apply；真实提交成功、删除／越界范围、仅记录批及无Git写入的公开入口组合需新增，Git提交只由隔离夹具准备 |
| V43 | R03、R04、R05、R09／I | 分别独立调用maintain的register-source-change／register-code-change，在限制和pending状态已落地、事件尚未发布处中断，再调用recover-events；另例删除或篡改pending payload／确切证据，并在事件未恢复、源码已修复但仍有语义／适用性限制时调用advance | 登记先持久限制／epoch再发布事件；恢复使用原event identity、快照和证据，完成后pending消除且重试不重复登记或增长epoch。payload缺失／错绑、证据缺失／指纹不符时明确阻断并保留已有pending及限制，不造新事件冒充恢复；未完成事件不得被advance绕过。advance仅在实际来源条件满足时清除机械freshness限制，显式语义／适用性限制仍保留，不宣称独立复核完成；全程无兄弟Skill CLI，不写知识、来源锁或活动索引 | E13、E11；复用现有raw事件发布中断及机械恢复断言，新增代码登记中断、payload／证据不足、advance语义限制与原状态保持的独立公开入口组合 |

## 4. 已有测试的复用与迁移约定

以下来自本轮只读盘点。`E` 仅为本计划路径缩写，不是新增测试文件或已通过标记。完整路径相对项目根 `repo/`；同一格后续只写文件名时，沿用前一个完整路径的目录。现有同名私有模块测试仍按[evals入口](himate-knowledge-wifi-mp/evals/README.md)分进程组织，避免导入污染掩盖实际失败。

| 基础 | 读到的实际测试源码 | 复用／必须调整的部分 |
|---|---|---|
| E01 结构与分发 | `himate-knowledge-wifi-mp/evals/tests/test_workflows.py`、`himate-knowledge-wifi-mp/evals/validate_design.py` | 保留入口文档／CLI／artifact引用、角色和合法出口的负向预期；将旧节点数、旧包白名单及独立local-check路由改为七节点／八包。静态合法不能认证实际宿主隔离 |
| E02 公开流程与续办 | `skills/common/knowledge/hs-knowledge-source-scan/tests/test_supported_workflow.py` | 现有 `test_complete_planned_document_nodes_then_three_noop_runs`、`test_supported_p7_stop_resumes_existing_exit_without_reapplying` 已按公开CLI和图顺序组织；迁为七节点调用，保留完成后no-op、不重放apply及精确原查询／CAS预期 |
| E03 端到端与显式修订 | `himate-knowledge-wifi-mp/evals/tests/test_manual_skills.py`、`test_node_pipeline.py`、`test_post_ingest_correction.py` | 无catalog人工公开调用、文档／代码、原件未变修卡、旧字节保留可复用。替换旧capture／review／index等调用归属；旧“apply自身质量审查”断言迁到P5，P7保留安全行为断言 |
| E04 扫描、处置与进度 | `skills/common/knowledge/hs-knowledge-source-scan/tests/test_cli.py`、`test_completion_status.py`、`test_historical_context.py` | 保留仅记录欠账、范围完整、原件／维护义务分离、formal-only历史、rolled_back终态、原CAS缺失为unknown等oracle；完成事实聚合适配新报告位置，不继续要求旧审阅／lint票据 |
| E05 计划与旧Claim | `skills/common/knowledge/hs-knowledge-change-plan/tests/test_v3_plan.py`、`test_v3_flow.py`、`test_review_preserved_claim.py`、`test_cli.py` | 保留逐单元覆盖、查询purpose、六动作、preserve与旧Claim去向；旧review动作不再充当主线独立节点，代码/成稿审阅绑定改由P5验证 |
| E06 代码审阅与身份边界 | `skills/common/knowledge/hs-knowledge-local-check/tests/test_public_code_gate.py`、`test_module_mapping.py`；`himate-knowledge-wifi-mp/evals/tests/test_agent_review_contract.py`、`test_source_analysis_admission.py` | 复用实际源码／配置／逐Claim证据的公开用例及无注册密钥、无角色身份前置要求的预期；迁至P5或共用契约。旧用例名中的signed不自动成为新要求，兼容签名素材不证明真实语义或身份 |
| E07 固定lint与CI | `skills/common/knowledge/hs-knowledge-lint/tests/test_cli.py`；`himate-knowledge-wifi-mp/evals/tests/test_governance_v3.py`、`test_document_source_checks.py`、`test_contracts.py` | 保留0/1/2、只读、规则锁、历史正文／locator、可信CI规则和不执行候选程序预期；扩展P5候选代码记录适用项，保证正式／CI模式无需生产者私有审阅 |
| E08 安全写入与恢复 | `skills/common/knowledge/hs-knowledge-apply/tests/test_apply.py`、`test_public_governance.py`；`himate-knowledge-wifi-mp/evals/tests/test_process_recovery.py`、`test_cli_response_compatibility.py` | 保留锁、CAS、备份、真实硬退出、外部修改、写后回读、原响应重试及不认证上游身份；新完整P7动作单列覆盖。旧入口如在迁移期保留，不悄悄改变其已有结果语义 |
| E09 索引完整性与启用 | `skills/common/knowledge/hs-knowledge-index-build/tests/test_journal_liveness.py`、`test_public_qualification.py`、`test_current_code_identity.py`、`test_portable_acceptance.py`、`test_review_source_lineage.py`、`test_review_shared_pending.py`；`himate-knowledge-wifi-mp/evals/tests/test_indexing_contract.py` | 公共索引／启用用例改走存续入口；保留集合／行值／正文／版本、真实来源／代码、活动指针和未完事务oracle。`test_indexing_contract.py`等共用契约测试继续作为独立期望，不绑定旧包名 |
| E10 声明式回归 | `skills/common/knowledge/hs-knowledge-query-regression/tests/test_cli.py`、`test_purpose.py`、`test_v3_gate.py` | 保留空用例／无oracle拒绝、purpose和同代结果预期；独立回归不要求作者批次／apply证明。迁调用入口，不保留嵌套index/query CLI或旧gate措辞 |
| E11 来源能力 | `skills/common/knowledge/hs-knowledge-source-capture/tests/test_cli.py`、`test_code_capture.py`、`test_workspace_capture.py`；`himate-knowledge-wifi-mp/evals/tests/test_snapshot_checkout_recovery.py`、`test_real_source_compat.py` | 原公共CLI捕获／恢复用例迁到P2及保留的独立消费动作；保留确切旧版、附件、原始地址、缓存缺失／篡改、映射和越界拒绝。来源内容不提供执行／联网／发布授权 |
| E12 查询 | `skills/common/knowledge/hs-knowledge-query/tests/test_public_receipt.py`、`test_purpose.py`、`test_live_code_scope.py`、`test_build_materials.py`、`test_source_runtime.py`、`test_qualification.py`；`himate-knowledge-wifi-mp/evals/tests/test_concurrent_query.py` | 保留目的／范围／材料资格、receipt、同代正文和并发只读预期；移除内部兄弟CLI依赖，不把ingest新流程凭证加入query |
| E13 维护及巡检 | `skills/common/knowledge/hs-knowledge-maintain/tests/test_cli.py`、`test_context_inspection.py`、`test_reference_audit.py` | 保留只读audit、来源／代码漂移、旧证据缺口、维护事件／水位和默认动作不变预期。`test_cli.py`已有raw变化幂等、手动advance不冒称语义复核、无apply／索引历史的机械恢复，以及`test_interrupted_event_publish_keeps_blocks_and_resumes_without_epoch_duplication`；迁为保留公开入口效果验证。V43的代码中断、pending payload／证据缺口及语义／适用性限制组合仍须新增；旧测试若观察 `Context.call` 子调用需换公共边界，不能依赖被删包存在 |
| E14 共享闭包 | `himate-knowledge-wifi-mp/evals/tests/test_clean_clone.py`、`test_git_asset_boundary.py` | 保留真正Git clone、生产者缓存缺失、文档／代码消费和Git可提交／忽略资产预期；新安装仅八包，消费端索引通过存续入口重建，不拷生产者私有树 |
| E15 版本及历史 | `test_post_ingest_correction.py`中的规则升级用例；source-scan `test_cli.py`中的old-rule pending系列；apply `test_apply.py`／`test_public_governance.py`中的旧journal系列 | 保留历史原字节、新规则重判、旧终态与真未完区分、旧committed不重放；为实际旧配套分发的可取得性新增演练，不能只将合成digest换成当前值 |
| E16 发现及工作区 | `skills/common/knowledge/hs-knowledge-explore/tests/test_setup.py`、`test_cli.py`；`himate-knowledge-wifi-mp/evals/tests/test_workspace_mapping.py`、`test_nested_workspace.py` | 保留真实配置与嵌套知识根解析、空模块不虚构源码、已有上下文复用、依赖检查边界；更新能力列表和引用，不能强制新catalog／机器绑定 |
| E17 运行限制 | `himate-knowledge-wifi-mp/evals/tests/test_skill_call_timeouts.py`、`test_git_read_isolation.py` | 兄弟调用消失后的旧timeout常量／调用数预期需要删除或重写；保留有界运行、Git只读不触发懒拉取／外部协议等目的。它们不提供公司API或SSH性能数据 |
| E18 提交清单与真实提交核对 | `skills/common/knowledge/hs-knowledge-publish-handoff/tests/test_publish_handoff.py`；当前算法参考同包 `scripts/publish.py` 的`publish_handoff/verify_submission` | 已有用例只覆盖无需apply／query票据的确切清单、选定文件字节变化拒绝、单凭Agent结果记录不能声称发布。先迁这些业务断言到apply，再为V42补真实HEAD／commit/blob／删除／无关范围、仅记录批和无Git写入的公开调用；当前源码存在verify_submission算法不等于对应公开用例已验证，旧包及私有import不能成为最终八包夹具依赖 |

迁移现有测试时遵守两项约束：

1. 不把“旧节点／旧CLI仍被调用”当作必须保留的业务oracle；也不因为接口变了就删掉原先保护的来源、Claim、范围、恢复、索引和查询预期。
2. 被删除包内的测试及夹具要先迁入存续包或领域evals；最终验收移走旧十包后仍能执行，防止测试靠旧包生成输入而生产安装缺少同一能力。共用函数可做精确契约测试，整链仍需走存续公开入口，不能以直接调用私有实现替代公开能力验收。

## 5. 性能测量与真实宿主验收

先固定改前／改后的版本、规则、原件及已有关联卡、查询预期、Python／依赖、模型／推理配置、工作区规模和本机／SSH拓扑。原始回放输入应可重复，但不伪造模型已完成语义审阅；固定合成记录的机制计时与真实Agent审阅计时分别报告。

| 测量内容 | 记录方式／判定边界 |
|---|---|
| P1—P7墙钟与总墙钟 | 保存各阶段起止、暂停／修订／重试；启动到最终启用为内容批口径，记录批另列 |
| Agent／API等待 | 宿主或API实际可取得的请求开始、首字、生成结束、重试和用量；不可取得项记unknown，不用CLI时间相减猜造 |
| SSH损耗与远程执行 | 尽可能分开连接／认证、命令传输、远端进程、结果读取；不记录认证秘密；不能仅有总SSH时间就断言均是网络损耗 |
| CLI与重复计算 | 实际启动次数及耗时、规则加载、来源读取、写入清单／候选生成、关系检查、临时／实际索引核验；用同一输入和明确冷热状态比较 |
| 运行结果一致性 | 耗时对比前先核语义预期、最终共享资产、查询排除／命中、真实启用和欠账状态；更快但少做业务不算性能改进 |

本计划不设从90分钟必降到某分钟、某比例提速或固定API往返数的通过承诺。结构目标是七节点、固定候选正常只在P5调用一次完整lint、主线无兄弟Skill CLI、P7无全库质量lint；时间改善需实测后单独结论。必要时按样本规模报告逐次结果及中位数；样本不足不出稳定分位数。API服务条件改变、真实审阅轮数不同、输入库规模或缓存状态不同须写明，不能合并为同一baseline。

H层最小执行记录应包含实际OpenFlow版本、安装八包摘要、调用端／执行端入口、工作区配置身份、SSH命令结果核对、真实reviewer任务及独立上下文证据，以及完整／中断续办的实际报告。先用获授权的小样本定位长耗时阶段，再扩到需要的业务样本。测试通过不授予发送消息、联网获取新原文、真实CI合入或发布权限。

## 6. 实施后的执行顺序和准入记录

1. 先完成接口／数据版本设计和能力归宿表，冻结新公开动作的实际名字与输入输出；将R01—R10正文与V编号同步。当前尚未实现的行为保持“待实现”，不能以旧实现跑绿代替。
2. 跑S层结构／引用／锁／分发检查；补齐并迁移与变化直接相关的I层公开入口用例，先保护来源、P5质量与P7安全边界。
3. 验证文档／代码整链、返回和仅记录分支，再做故障、共享clone及查询维护回归；每组留独立报告，按需使用Python 3.10—3.12实际支持环境，未执行组合列明。
4. 在隔离安装中物理移除旧十包，重复最终八包的相关公开能力及安装／引用负向检查。旧未完操作恢复准备未验证前不销毁唯一配套能力，不借兼容名永久隐藏旧依赖。
5. 结构与业务用例达到对应准入条件后，另进行H层宿主／SSH／API测量。S/I结果与H结果分开签注；没有真实环境输入就记录“未执行及缺口”，不伪造验收。

用例状态使用“待设计／待实现／待执行／通过／失败／未完成／不适用”，每个状态指向本次证据。没有按本计划执行前，所有计划用例都不应预标通过。测试数量、总退出码、历史成绩或合成reviewer标签均不能替代需求逐项覆盖和证据范围说明。
