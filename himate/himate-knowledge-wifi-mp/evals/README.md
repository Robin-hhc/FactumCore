# 节点机制验收

此目录位于项目根 `repo/himate/himate-knowledge-wifi-mp/evals/`，集中保存知识系统的阶段、领域契约、命令、Workflow 与完整链路验证。阶段测试位于 `stages/<stage>/`，不再属于 Skill 指引包；按阶段分别启动 Python 进程并保留导入命名域。这些是开发测试入口，业务运行与实际分发不依赖测试目录。只使用隔离合成材料，不读取受限 gold。

| 分类 | 管理内容 |
|---|---|
| `stages/` | 八阶段业务测试及本组fixture组织 |
| `contracts/`、`cli/`、`workflows/` | 受锁规则、公开命令协议、编排与宿主资源结构 |
| `integration/` | 完整入库、增量修订、恢复与克隆闭包 |
| `tooling/` | 选择器、运行器、报告与基准工具自身 |
| `support/` | 公共合成材料、项目、CLI调用与故障工具，不承载业务测试用例 |
| `benchmarks/` | 独立工作量与性能采样入口 |

主业务夹具默认调用实际知识根的 `knowledge.py`，不构造带脚本的伪安装Skill。必要的旧传输重试验证明确选择仓内兼容transport；正式库lint协议也可独立验证，不要求Skill私有脚本。实际ZIP部署和宿主装载按各自证据单列，公共夹具可运行不代表真实发行包验收。部署工具测试保留在 `repo/tools/deploy/tests/`。

开发源码的知识根锚定本目录的上级，项目根在 `himate/` 的上级；测试运行器和基准从项目根选择嵌套的源码树。合成业务夹具仍覆盖已配置的平铺、嵌套及自定义知识根，不能把开发源码位置套到业务配置上。复制到这些夹具的公开 Git 元数据按夹具自己的相对根适配；固定 f8 历史审计只在显式选择并验证其清单后沿用该版本的旧布局，不影响当前默认入口。

使用 Python 3.10–3.12 和显式锁定测试环境，在项目根 `repo/` 执行 `python himate/himate-knowledge-wifi-mp/evals/run_acceptance.py --output-dir .scratch/acceptance-new`；结果目录须全新，相对路径以项目根为基准。保留每组 JUnit、stdout/stderr 和汇总 JSON；退出码不能替代逐项报告。当前验证通过仓内 CLI 人工逐阶段调用业务链路，不依赖 OpenFlow 安装、源码或宿主接入；Workflow 仅检查仓内静态结构，留待后续对接。验收运行器不自动安装依赖或修改全局宿主配置。

场景、责任层及本轮去重说明见 [SCENARIOS.md](SCENARIOS.md)。默认全量收集，新增测试不会因为未进入快验清单而遗漏。日常快验使用 `python himate/himate-knowledge-wifi-mp/evals/run_acceptance.py --profile quick --output-dir .scratch/quick-new`，覆盖显式选定的契约、安全边界和公开 CLI 冒烟；交付前仍运行默认 full。可用 `--groups hs-knowledge-apply` 定向某组，八个底层执行阶段和领域测试继续分别在独立进程运行。quick 选择不全、单组空收集、收集失败或超时均不能作为全量通过；超时/启动失败会保留局部输出并写入最终失败汇总，其余分组继续。

每次 `summary.json` 同时保存 profile、jobs、实际选择、Python/平台、提交及规则摘要，统计整套墙时、组墙时、用例总时长和慢用例/文件。并行组耗时之和不是整套墙时；JUnit 单例总时长不能拆成 setup/call/teardown，也没有采样 CLI 次数。添加 `--baseline .scratch/earlier/summary.json` 可观察变化：环境、profile、jobs 相同且完整选择相同才比较总墙时，选择变化时只列共同通过用例并报告增删。旧报告缺元数据明确不可比较。统计始终为软提示，性能变化不影响正确性 pass/fail，机器负载和缓存差异仍须人工判断。

`test_manual_skills.py` 以无 catalog 的公开 CLI 逐个调用 Skill，验证扫描、材料、计划、稿件、业务检查、入库、索引及查询的衔接；`test_node_pipeline.py` 继续覆盖更新、历史与恢复机制。人工安排内容复核，Skill 检查实际数据和确切视图绑定，不检查角色或上游通过凭证。真实宿主触发、六 Target/三 pair、真实 CI 合入与权限验收按实际环境单列验证，缺少输入时保持未完成。本项目自身的历史验收记录在本地 `../docs-llm-wiki/sdd/` 保存，不随仓库分发，历史成绩不合并到当前计数。

真实源码验收是显式独立层，方法见 [真实仓场景](SCENARIOS.md#真实仓验收)。由 Agent 使用用户授权的实际源码与文档，在新隔离知识根复制本次规则和能力，按 Workflow 顺序真实调用 P1—P6，再用独立固定的用户问题调用 query.search→receipt read。固定来源版本、输入摘要、独立审阅、发布清理、实际命中和未命中及耗时；结果保存在该次试验与本地 SDD，不合并进合成 full 的通过计数。该层需要本次明确提供的实际输入与执行位置，适合 Workflow／来源／发布／查询机制变更后的业务验收。

新增公开检查覆盖自动扫描/材料准备/处理记录、逐 Claim 计划与 skip 抽查、只读 lint 0/1/2、固定 CI、同批记录事务和提交前索引/目标查询。共用 indexing 的完整集合/值核验与跨机接纳凭据另有独立预期测试。操作收尾、连续无变化扫描及显式不存在来源范围按公开 CLI 回归；按现有 Workflow 节点顺序验证正常业务链、明确的本轮返工和正式收尾状态，测试复核声明为合成数据，不表示真实宿主运行或角色隔离通过。查询继续消费活动代，响应沿用各节点既有输出与重试规则。

`test_clean_clone.py` 使用隔离合成资料完成 ingest，只提交共享资产，再执行真实 Git clone；消费副本没有生产端的 `.build/`、`artifacts/`、事务日志及旧原件／提取缓存，保留正式 `logs/evidence/published/` 和 `logs/publications/` 闭包，须重新通过正式库检查、索引验证与激活、query／read 和增量扫描。`test_git_asset_boundary.py` 另用 Git 自身检查忽略规则，区分本机缓存与必须可提交的处理记录、使用限制和显式材料。该场景验证跨工作区数据闭包，不证明另一账号权限、实际宿主或部署机文件系统的持久化行为。


当前公开集合为12个Skill，按执行实现隔离加分类领域测试组织；8个底层运行阶段含显式诊断/兼容explore，测试组名称不表示存在对应Skill。P1—P6六个节点依次为：prepare_sources、plan_change、materialize_view、lint_view、record_ingest、apply_view；P1在来源节点正常调用一次run，返工直接prepare；P5使用独立record Skill及knowledge record命令，复用既有记录算法。P4由review Skill与knowledge review承接，是唯一reviewer，其余为coder；治理四步分别绑定patrol-sync/plan/reindex/complete，maintain没有Workflow scope。validate_design.py逐项核对能力集合、节点／owner／转移、布局及真实产物node/exit范围；历史空目录不视为active Skill，旧有SKILL.md的来源包必须迁移删除后才能通过。

P1内扫描与备料的独立测试分别验证观察不备料、固定清单／显式目标备料、定向补料及漂移回P1。P2保留语义／六决策oracle，P3验证实际字节和旧Claim去向，P4独立审阅与完整质量检查及代码证据绑定。stages/apply/承接安全事务、恢复、独立index/regression/submission及真实公开batch，stages/lint/承接原local/merge代码业务oracle，stages/maintain/保事件pending／恢复／advance及只读audit。旧兄弟CLI的缺安装和子调用超时包装随架构消除，保留其业务失败不冒称通过、停点和原字节保护断言。

最终验收使用发出的真实规则锁，不自动重pin陈旧锁；只有测试明确修改规则或注入检查计数时，才在独立夹具中生成并标注该测试版本。support/contracts.py仅帮助可信开发夹具加载同一公共算法，公开CLI仍独立验证复制的规则锁。P6内部验证对象不从JSON passed声明创建；写后基线、完整数据库／正文、原冻结查询和CAS均独立验证。各组测试分别运行，避免私有同名模块污染；新增机制和静态测试不替代真实OpenFlow/API/SSH/六Target/CI/权限验收。

`test_code_symbols.py`、`test_code_ref_contracts.py` 及 query／maintain 包的 `test_code_navigation.py` 验证补充式 `sources[].code_ref`：旧快照绑定与当前符号导航分别检查，涵盖插行、改体、删除、歧义、安全配置绑定、用途边界和公开 CLI。解析使用锁定的 Tree-sitter C/C++ 语法，不执行目标代码；语法或能力不足返回 unavailable。

符号性能诊断可在 `repo/` 执行 `python himate/himate-knowledge-wifi-mp/evals/benchmarks/benchmark_ingest.py --checkout . --output-dir .scratch/symbol-benchmark-new --symbols`。它单独测量 1000 个合成 C 函数的冷解析及同文件操作缓存查询，保留 summary.json；不包含 CLI、文件系统、构建、模型或宿主延迟，也不作为速度阈值。

合成文档链基准使用 `python himate/himate-knowledge-wifi-mp/evals/benchmarks/benchmark_ingest.py --checkout . --output-dir .scratch/flow-benchmark-new --runs 3`。报告真实公开 CLI 的动作、次数与耗时，以及整链最小/中位/最大值；三次样本不推算尾延迟。`--instrument` 单独测内部调用次数，带 profiler 的结果与正常计时分开。两类基准均记录环境、工作量和版本，可加 `--baseline` 比较同类同环境工作量；规则版本作为背景记录，性能变化不设阈值。文档样本仅一张卡、300 行合成原件，不包含 LLM、公司 API、SSH、OpenFlow 等等待，也不是规模或语义质量测试。

`test_manual_skills.py` 的文档主链逐次核对真实 P1—P5 公开调用前后的正式路径与字节，并在 P6 前另开 operation 验证 fresh scan；`test_ingest_stage_interrupt.py` 实际停止隔离 P1 子进程，再用新 operation 验证 fresh scan。暂存映射、归属、正式发布、清理失败只补清理、首次 CAS 和清后提交核验的机制用例分别位于领域及 apply 包测试中。孤儿暂存周期 GC、罕见 P6 部分写入自动修复和真实宿主取消语义不由这些用例证明。

`cli/test_record_cli.py` 验证 record 公开命令与既有记录入口的字节/结果等价、重入、动作限制和路径归属；阶段业务用例仍按八个底层实现分类。Workflow结构检查分别核source的备料出口和record的记录出口，保留记录宿主声明的既有ID，拒绝P5重新加载source Skill。
