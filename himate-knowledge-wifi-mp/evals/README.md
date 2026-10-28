# 节点机制验收

此目录保存当前设计对齐实现的领域契约、Workflow 和跨包公开 CLI 联检。开发仓的 Skill 单元测试在 `skills/common/knowledge/<Skill>/tests/`，项目结构与能力包检查在本目录；分别启动 Python 进程，避免同名私有模块的测试导入互相污染。这些是开发测试入口，不要求部署项目保留根能力源码目录。只使用隔离合成材料，不读取受限 gold。

使用 Python 3.10–3.12 和显式锁定测试环境，在项目根 `repo/` 执行 `python himate-knowledge-wifi-mp/evals/run_acceptance.py --output-dir .scratch/acceptance-new`；结果目录须全新，相对路径以项目根为基准。保留每组 JUnit、stdout/stderr 和汇总 JSON；退出码不能替代逐项报告。当前验证人工逐个调用 Skill 的业务链路，不依赖 OpenFlow 安装、源码或宿主接入；Workflow 仅检查仓内静态结构，留待后续对接。验收运行器不自动安装依赖或修改全局宿主配置。

`test_manual_skills.py` 以无 catalog 的公开 CLI 逐个调用 Skill，验证扫描、材料、计划、稿件、业务检查、入库、索引及查询的衔接；`test_node_pipeline.py` 继续覆盖更新、历史与恢复机制。人工安排内容复核，Skill 检查实际数据和确切视图绑定，不检查角色或上游通过凭证。真实宿主触发、六 Target/三 pair、真实 CI 合入与权限验收按实际环境单列验证，缺少输入时保持未完成。本项目自身的历史验收记录在本地 `../docs-llm-wiki/sdd/` 保存，不随仓库分发，历史成绩不合并到当前计数。

新增公开检查覆盖自动扫描/材料准备/处理记录、逐 Claim 计划与 skip 抽查、只读 lint 0/1/2、固定 CI、同批记录事务和提交前索引/目标查询。共用 indexing 的完整集合/值核验与跨机接纳凭据另有独立预期测试。操作收尾、连续无变化扫描及显式不存在来源范围按公开 CLI 回归；按现有 Workflow 节点顺序验证正常业务链和已有续办出口，测试复核声明为合成数据，不表示真实宿主运行或角色隔离通过。查询继续消费活动代，响应沿用各节点既有输出与重试规则。

`test_clean_clone.py` 使用隔离合成资料完成 ingest，只提交共享资产，再执行真实 Git clone；消费副本没有生产端的 `.build/`、`artifacts/`、事务日志及原件／提取缓存，须重新通过正式库检查、索引验证与激活、query／read 和增量扫描。`test_git_asset_boundary.py` 另用 Git 自身检查忽略规则，区分本机缓存与必须可提交的处理记录、使用限制和显式材料。该场景验证跨工作区数据闭包，不证明另一账号权限、实际宿主或部署机文件系统的持久化行为。
