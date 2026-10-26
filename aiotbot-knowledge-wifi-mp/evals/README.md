# 节点机制验收

此目录保存当前设计对齐实现 的领域契约、Workflow 和跨包公开 CLI 联检。各 Skill 的单元测试位于仓根 `skills/common/knowledge/<Skill>/tests/` 中，分别启动 Python 进程，避免同名私有模块的测试导入互相污染。只使用隔离合成材料，不读取受限 gold。

使用 Python 3.11（也兼容 3.12）和显式锁定测试环境，在项目根 `repo/` 执行 `python aiotbot-knowledge-wifi-mp/evals/run_acceptance.py --output-dir .scratch/acceptance-new`；结果目录须全新，相对路径以项目根为基准。保留每组 JUnit、stdout/stderr 和汇总 JSON；退出码不能替代逐项报告。可选环境 `FACTUM_OPENFLOW_SOURCE` 指向验证器固定 SHA 的上游源码，`FACTUM_POSIX_SHELL` 指向实际 POSIX Shell；缺少时相关检查明确 skipped，不算通过。验收运行器不自动安装依赖或修改全局宿主配置。

`test_node_pipeline.py` 串联 raw、候选、独立内容复核、stable、索引、查询和入库后更新。文档无需真人事件或宿主信任配置；缺失复核、作者冲突和视图失配仍拒绝入库。真实宿主隐式触发、六 Target/三 pair、真实 CI 合入与权限验收按实际环境单列验证，缺少输入时保持未完成。本项目自身的历史验收记录在本地 `../docs-llm-wiki/sdd/` 保存，不随仓库分发，历史成绩不合并到当前计数。

新增公开检查覆盖自动扫描/材料准备/处理记录、逐 Claim 计划与 skip 抽查、只读 lint 0/1/2、固定 CI、同批记录事务和提交前索引/目标查询。共用 indexing 的完整集合/值核验与跨机接纳凭据另有独立预期测试。新 search 索引过期检查仍不在本轮范围。
