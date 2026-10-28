# 节点机制验收

此目录保存当前设计对齐实现的领域契约、Workflow 和跨包公开 CLI 联检。开发仓的 Skill 单元测试在 `skills/common/knowledge/<Skill>/tests/`，项目结构与能力包检查在本目录；分别启动 Python 进程，避免同名私有模块的测试导入互相污染。这些是开发测试入口，不要求部署项目保留根能力源码目录。只使用隔离合成材料，不读取受限 gold。

使用 Python 3.10–3.12 和显式锁定测试环境，在项目根 `repo/` 执行 `python himate-knowledge-wifi-mp/evals/run_acceptance.py --output-dir .scratch/acceptance-new`；结果目录须全新，相对路径以项目根为基准。保留每组 JUnit、stdout/stderr 和汇总 JSON；退出码不能替代逐项报告。当前验证人工逐个调用 Skill 的业务链路，不依赖 OpenFlow 安装、源码或宿主接入；Workflow 仅检查仓内静态结构，留待后续对接。验收运行器不自动安装依赖或修改全局宿主配置。

`test_manual_skills.py` 以无 catalog 的公开 CLI 逐个调用 Skill，验证扫描、材料、计划、稿件、业务检查、入库、索引及查询的衔接；`test_node_pipeline.py` 继续覆盖更新、历史与恢复机制。人工安排内容复核，Skill 检查实际数据和确切视图绑定，不检查角色或上游通过凭证。真实宿主触发、六 Target/三 pair、真实 CI 合入与权限验收按实际环境单列验证，缺少输入时保持未完成。本项目自身的历史验收记录在本地 `../docs-llm-wiki/sdd/` 保存，不随仓库分发，历史成绩不合并到当前计数。

新增公开检查覆盖自动扫描/材料准备/处理记录、逐 Claim 计划与 skip 抽查、只读 lint 0/1/2、固定 CI、同批记录事务和提交前索引/目标查询。共用 indexing 的完整集合/值核验与跨机接纳凭据另有独立预期测试。操作收尾、连续无变化扫描及显式不存在来源范围按公开 CLI 回归；按现有 Workflow 节点顺序验证正常业务链和已有续办出口，测试复核声明为合成数据，不表示真实宿主运行或角色隔离通过。查询继续消费活动代，响应沿用各节点既有输出与重试规则。

`test_clean_clone.py` 使用隔离合成资料完成 ingest，只提交共享资产，再执行真实 Git clone；消费副本没有生产端的 `.build/`、`artifacts/`、事务日志及原件／提取缓存，须重新通过正式库检查、索引验证与激活、query／read 和增量扫描。`test_git_asset_boundary.py` 另用 Git 自身检查忽略规则，区分本机缓存与必须可提交的处理记录、使用限制和显式材料。该场景验证跨工作区数据闭包，不证明另一账号权限、实际宿主或部署机文件系统的持久化行为。


当前公开集合为9个Skill，ingest的7个节点为scan_sources、prepare_material、plan_change、materialize_view、lint_view、record_ingest、apply_view；P5唯一reviewer，其他coder。validate_design.py逐项核对最终能力集合、节点／owner／转移、布局及真实产物node/exit范围；历史空目录不视为active Skill，旧有SKILL.md的包必须迁移删除后才能通过。

P1/P2独立测试分别验证观察不备料、固定清单／显式目标备料、定向补料及漂移回P1。P3保留语义／六决策oracle，P4验证实际字节和旧Claim去向，P5独立审阅与完整质量检查及代码证据绑定。apply/tests承接安全事务、恢复、独立index/regression/submission及真实公开batch，lint/tests承接原local/merge代码业务oracle，maintain/tests保事件pending／恢复／advance及只读audit。旧兄弟CLI的缺安装和子调用超时包装随架构消除，保留其业务失败不冒称通过、停点和原字节保护断言。

最终验收使用发出的真实规则锁，不自动重pin陈旧锁；只有测试明确修改规则或注入检查计数时，才在独立夹具中生成并标注该测试版本。contract_test_support.py仅帮助可信开发夹具加载同一公共算法，公开CLI仍独立验证复制的规则锁。P7内部验证对象不从JSON passed声明创建；写后基线、完整数据库／正文、原冻结查询和CAS均独立验证。各组测试分别运行，避免私有同名模块污染；新增机制和静态测试不替代真实OpenFlow/API/SSH/六Target/CI/权限验收。

`test_code_symbols.py`、`test_code_ref_contracts.py` 及 query／maintain 包的 `test_code_navigation.py` 验证补充式 `sources[].code_ref`：旧快照绑定与当前符号导航分别检查，涵盖插行、改体、删除、歧义、安全配置绑定、用途边界和公开 CLI。解析使用锁定的 Tree-sitter C/C++ 语法，不执行目标代码；语法或能力不足返回 unavailable。

符号性能诊断可在 `repo/` 执行 `python himate-knowledge-wifi-mp/evals/benchmark_ingest.py --checkout . --output-dir .scratch/symbol-benchmark-new --symbols`。它单独测量 1000 个合成 C 函数的冷解析及同文件操作缓存查询，保留 summary.json；不包含 CLI、文件系统、构建、模型或宿主延迟，也不作为速度阈值。
